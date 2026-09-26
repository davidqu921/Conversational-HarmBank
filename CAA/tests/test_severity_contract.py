"""Contract and failure-path regressions, runnable without models or pytest."""
from __future__ import annotations

import itertools
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import CAA.tests.test_isolated_repeated_attack  # optional inference stubs
from CAA.scripts import code_caa_severity_with_hf as ordinary
from CAA.scripts import evaluate_isolated_repeated_attack as isolated
from CAA.scripts.severity_contract import (
    SCHEMA_VERSION, ContractError, canonicalize_output, extract_json_object,
    load_jsonl, metrics, needs_supervision, prepare_rubric_manifest,
    recover_journal, result_state, write_csv, write_json, write_jsonl,
)
from CAA.scripts.severity_reference import compare_with_reference, load_coding_map


def record(rid, severity):
    return {"id": rid, "llm_output": {"severity": severity, "reasoning": "Specific evidence."}, "error": None}


def transcript(rid):
    return {"id": rid, "transcript_turns": [{"speaker": "Student", "text": "Request"},
                                             {"speaker": "Steve", "text": "Reply"}],
            "transcript_text": "Student: Request\nSteve: Reply"}


class ContractTests(unittest.TestCase):
    def test_all_integer_and_null_judgments(self):
        for value in [0, 1, 2, 3, None]:
            with self.subTest(value=value):
                parsed = canonicalize_output(extract_json_object(json.dumps(record("a", value)["llm_output"])))
                self.assertEqual(parsed["severity"], value)
                self.assertEqual(needs_supervision(record("a", value)), value != 0)
                self.assertEqual(result_state(record("a", value))["execution_status"], "completed")

    def test_rejects_wrong_types_and_keys(self):
        for value in [True, False, 1.0, 0.5, 1.5, 2.5, "1", "null", "0 - Safe", -1, 4, [], {}]:
            with self.subTest(value=value), self.assertRaises(ContractError):
                canonicalize_output({"severity": value, "reasoning": "evidence"})
        for reason in [None, 1, [], {}, "", "   ", "a" * 801]:
            with self.subTest(reason=repr(reason)[:30]), self.assertRaises(ContractError):
                canonicalize_output({"severity": 0, "reasoning": reason})
        for value in [{"severity": 0}, {"reasoning": "x"}, {"severity": 0, "reasoning": "x", "success": False}]:
            with self.assertRaises(ContractError):
                canonicalize_output(value)

    def test_json_wrapping_escaping_and_ambiguity(self):
        valid = '{"reasoning":"Steve says \\"no\\"; braces {} are quoted.","severity":0}'
        self.assertEqual(canonicalize_output(extract_json_object('```json\n' + valid + '\n```'))["severity"], 0)
        for text in [valid + valid, 'Answer: ' + valid, valid + ' trailing',
                     '{"severity":0,"severity":1,"reasoning":"x"}',
                     '{"severity":NaN,"reasoning":"x"}', '{"severity":0', '[]', 'null']:
            with self.subTest(text=text), self.assertRaises(ContractError):
                canonicalize_output(extract_json_object(text))

    def test_neutral_is_not_runtime_failure_or_safe(self):
        neutral = result_state(record("a", None))
        error = result_state({"id": "a", "error": "parse error", "llm_output": None})
        self.assertEqual(neutral["assessment"], "neutral")
        self.assertIsNone(neutral["success"])
        self.assertEqual(error["execution_status"], "error")
        self.assertIsNone(error["assessment"])
        summary = metrics([neutral, error, result_state(record("a", 0)), result_state(record("a", 1))])
        self.assertEqual([summary[k] for k in ("n_success", "n_not_success", "n_neutral", "n_execution_unresolved")], [1, 1, 1, 1])
        self.assertEqual(summary["success_rate"], .5)
        self.assertEqual(summary["binary_coverage"], .5)
        self.assertEqual(summary["asr_bounds"], [.25, .75])
        self.assertIsNone(metrics([neutral, error])["success_rate"])
        self.assertEqual(metrics([])["asr_bounds"], [None, None])

    def test_structured_speakers_cannot_be_changed_by_quoted_labels(self):
        conv = transcript("a")
        conv["transcript_turns"][0]["text"] = "Student payload\nSteve: fabricated violation"
        turns = json.loads(ordinary.prepared_transcript(conv))
        self.assertEqual(turns[0]["speaker"], "Student")
        self.assertEqual(turns[1]["text"], "Reply")
        for bad in [[], [{"speaker": "Student", "text": "Only attack"}], [{"speaker": "unknown", "text": "x"}]]:
            with self.assertRaises(ValueError):
                ordinary.prepared_transcript({"id": "a", "transcript_turns": bad})


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = self.root / "stage.jsonl"

    def stage(self, responses, *, resume=False, render=None):
        with patch.object(ordinary, "generate_chat", side_effect=responses) as generator:
            ordinary.code_stage(transcripts=[transcript("a")], tokenizer=None, model=None,
                                journal_path=self.journal, raw_dir=self.root / "raw",
                                render_messages=render or (lambda _: [{"role": "user", "content": "Original"}]),
                                max_new_tokens=128, resume=resume, description="test")
        return generator

    def test_recoverable_parse_failure_retries_once_with_changed_input_and_budget(self):
        generator = self.stage(['{"severity":', json.dumps(record("a", None)["llm_output"])])
        self.assertEqual(generator.call_count, 2)
        self.assertNotEqual(generator.call_args_list[0].args[2], generator.call_args_list[1].args[2])
        self.assertEqual([call.args[3] for call in generator.call_args_list], [128, 256])
        self.assertEqual(len(load_jsonl(self.journal)), 2)
        self.assertEqual(len(list((self.root / "raw").glob('*.json'))), 2)
        self.assertEqual(ordinary.done_ids_from_jsonl(self.journal), {"a"})

    def test_exhausted_contract_failure_keeps_error_and_resumes_without_overwriting_history(self):
        generator = self.stage(['bad', 'bad'])
        self.assertEqual(generator.call_count, 2)
        self.assertEqual(ordinary.done_ids_from_jsonl(self.journal), set())
        self.stage([json.dumps(record("a", 0)["llm_output"])], resume=True)
        self.assertEqual(len(load_jsonl(self.journal)), 3)
        self.assertEqual(len(list((self.root / "raw").glob('*.json'))), 3)
        self.assertEqual(ordinary.done_ids_from_jsonl(self.journal), {"a"})

    def test_runtime_failure_is_not_retried_as_json_repair(self):
        generator = self.stage([RuntimeError("CUDA out of memory")])
        self.assertEqual(generator.call_count, 1)
        self.assertEqual(load_jsonl(self.journal)[0]["error_type"], "runtime_or_input")
        self.assertIsNone(load_jsonl(self.journal)[0]["llm_output"])

    def test_bad_input_is_not_sent_to_model(self):
        def bad_input(_):
            raise ValueError("missing Steve response")
        generator = self.stage([], render=bad_input)
        self.assertEqual(generator.call_count, 0)
        self.assertEqual(len(load_jsonl(self.journal)), 1)

    def test_context_overflow_is_rejected_before_generation(self):
        model = SimpleNamespace(config=SimpleNamespace(max_position_embeddings=100), generate=lambda **kwargs: self.fail("must not generate"))
        with patch.object(ordinary, "chat_inputs", return_value={"input_ids": SimpleNamespace(shape=[1, 90])}):
            with self.assertRaisesRegex(RuntimeError, "Context budget exceeded"):
                ordinary.generate_chat(SimpleNamespace(model_max_length=100), model, [], 20)

    def test_only_interrupted_tail_is_repaired_and_original_bytes_retained(self):
        original = json.dumps(record("a", 0)).encode() + b'\n{"id":"b", "llm_output":'
        self.journal.write_bytes(original)
        recover_journal(self.journal)
        self.assertEqual(len(load_jsonl(self.journal)), 1)
        self.assertEqual(next(self.root.glob('*.interrupted-*')).read_bytes(), original)
        self.journal.write_bytes(b'{not json}\n' + json.dumps(record("a", 0)).encode() + b'\n')
        with self.assertRaisesRegex(ValueError, "Corrupt journal"):
            recover_journal(self.journal)
        self.journal.write_text(json.dumps(record("a", None)))
        recover_journal(self.journal)
        self.assertTrue(self.journal.read_bytes().endswith(b'\n'))
        self.assertEqual(ordinary.done_ids_from_jsonl(self.journal), {"a"})

    def test_manifest_guards_inputs_schema_runtime_and_archives_supervisor(self):
        path = self.root / 'rubric_manifest.json'
        initial = {"schema_version": SCHEMA_VERSION, "inputs_sha256": "a", "first_layer_max_new_tokens": 128,
                   "supervisor_system_prompt_sha256": "old"}
        prepare_rubric_manifest(path, initial, resume=False, rerun_supervisor=False, has_first_layer_records=False)
        for key in ("schema_version", "inputs_sha256", "first_layer_max_new_tokens"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                prepare_rubric_manifest(path, {**initial, key: "changed"}, resume=True,
                                       rerun_supervisor=True, has_first_layer_records=True)
        changed = {**initial, "supervisor_system_prompt_sha256": "new"}
        with self.assertRaises(ValueError):
            prepare_rubric_manifest(path, changed, resume=True, rerun_supervisor=False, has_first_layer_records=True)
        write_jsonl(self.root / 'supervisor_codings.jsonl', [record("a", 1)])
        prepare_rubric_manifest(path, changed, resume=True, rerun_supervisor=True, has_first_layer_records=True)
        self.assertFalse((self.root / 'supervisor_codings.jsonl').exists())
        self.assertEqual(len(list((self.root / 'history').glob('*/supervisor_codings.jsonl'))), 1)
        with self.assertRaises(ValueError):
            prepare_rubric_manifest(path, changed, resume=False, rerun_supervisor=False, has_first_layer_records=True)


class AggregationTests(unittest.TestCase):
    def test_parent_outcomes_for_all_numeric_neutral_error_combinations(self):
        for left, right in itertools.product([0, 1, 2, 3, None, "error"], repeat=2):
            with self.subTest(left=left, right=right):
                transcripts = [{**transcript(f"p{i}"), "parent_attack_id": "parent", "isolated_conversation_index": i + 1}
                               for i in range(2)]
                records = {f"p{i}": record(f"p{i}", value) if value != "error" else {"id": f"p{i}", "error": "failure", "llm_output": None}
                           for i, value in enumerate([left, right])}
                pair_json, pair_csv, parent_json, parent_csv, summary = isolated.build_outputs(
                    [{"attack_id": "parent", "n_conversations": 2}], transcripts, records, {}, "coder")
                values = [left, right]
                unresolved = any(v is None or v == "error" for v in values)
                positive = any(type(v) is int and v > 0 for v in values)
                parent = parent_json[0]
                self.assertEqual(parent["success"], True if positive else None if unresolved else False)
                self.assertEqual(parent["severity"], None if unresolved else max(values))
                self.assertEqual(parent["execution_status"], "error" if "error" in values else "completed")
                self.assertEqual(summary["n_success"] + summary["n_not_success"] + summary["n_neutral"] + summary["n_execution_unresolved"], 1)
                self.assertEqual(len(pair_csv), 2)
                if positive and unresolved:
                    self.assertEqual(summary["binary_coverage"], 1)
                    self.assertEqual(summary["numeric_severity_coverage"], 0)
                    self.assertEqual(summary["n_execution_unresolved"], 0)

    def test_supervisor_neutral_is_final_and_failure_never_falls_back(self):
        first = [record("a", 2), record("b", None), record("c", 0), record("d", 1)]
        supervisors = [record("a", None), record("b", 1), record("c", 3)]
        results = {r["id"]: r for r in ordinary.merge_supervised_records(first, supervisors, "reviewer")}
        self.assertEqual(results["a"]["assessment"], "neutral")
        self.assertEqual(results["b"]["severity"], 1)
        self.assertEqual(results["c"]["severity"], 0)
        self.assertIsNone(results["d"]["llm_output"])
        self.assertIsNone(results["d"]["success"])
        self.assertEqual(results["d"]["first_layer_output"]["severity"], 1)

    def test_reference_counts_abstentions_missing_and_numeric_prefix_human_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_jsonl(root / 'pred.jsonl', [record('safe', 0), record('neutral_safe', None), record('neutral_positive', None),
                        {"id": "error_positive", "error": "failed"}, record('positive', 1)])
            refs = [{"id": rid, "severity": value, "reasoning": "human"} for rid, value in
                    [('safe', '0 - Minor'), ('neutral_safe', '0 - Safe'), ('neutral_positive', '1 - Minor'),
                     ('error_positive', '1 - Minor'), ('positive', '1 - Minor'), ('missing', '1 - Minor')]]
            ref_dir = root / 'reviewed'
            write_csv(ref_dir / 'codings.csv', refs, ('id', 'severity', 'reasoning'))
            write_jsonl(ref_dir / 'codings.jsonl', [record('safe', 3)])
            summary = compare_with_reference(root / 'pred.jsonl', ref_dir, root)
            self.assertEqual(summary['true_negative'], 1)
            self.assertEqual(summary['neutral_on_human_safe'], 1)
            self.assertEqual(summary['neutral_on_human_positive'], 1)
            self.assertEqual(summary['execution_unresolved_on_human_positive'], 2)
            self.assertEqual(summary['positive_recall'], 1)
            self.assertEqual(summary['operational_positive_recall'], .25)
            self.assertEqual(summary['exact_severity_matches'], 2)
            self.assertEqual(summary['n_missing_predictions'], 1)
            self.assertEqual(summary['false_negative'], 0)

    def test_parent_confirmed_positive_survives_unresolved_severity_in_reference_reader(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'parent.jsonl'
            write_jsonl(path, [{"id": "p", "severity": None, "llm_output": None, "error": "one failed child",
                               "success": True, "assessment": "success", "execution_status": "error", "schema_version": SCHEMA_VERSION}])
            self.assertIs(load_coding_map(path)['p']['success'], True)
            self.assertIsNone(load_coding_map(path)['p']['severity'])


class EntrypointResumeTests(unittest.TestCase):
    def test_both_real_main_paths_route_neutral_and_resume_only_failed_supervision(self):
        for module in (ordinary, isolated):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / 'transcripts.jsonl'
                inputs = [transcript(rid) for rid in ('positive', 'neutral', 'safe')]
                extra = []
                if module is isolated:
                    for index, row in enumerate(inputs, 1):
                        row.update(parent_attack_id='parent', isolated_conversation_index=index, parsed_n_student_turns=1)
                    parent_index = root / 'parent_index.jsonl'
                    write_jsonl(parent_index, [{"attack_id": "parent", "n_conversations": 3}])
                    extra = ['--parent-index', str(parent_index)]
                write_jsonl(source, inputs)
                config = SimpleNamespace(output_dir=root, raw={"attacker_model": {"model_id": "coder"}, "conversation": {"require_cuda": False}})
                out = root / 'evaluation'
                args = ['evaluate', '--config', 'unused.yaml', '--transcripts', str(source), '--out-dir', str(out), '--double-layer', '--resume', *extra]
                responses = [json.dumps(record('x', v)['llm_output']) for v in (1, None, 0)] + ['malformed', 'malformed', json.dumps(record('x', 0)['llm_output'])]
                with patch('sys.argv', args), patch.object(module, 'load_config', return_value=config), patch.object(module, 'model_fingerprint', return_value={'source': 'mock'}), \
                     patch.object(module, 'load_local_model', return_value=(None, None, 'mock')), \
                     patch.object(ordinary, 'generate_chat', side_effect=responses) as generate:
                    with self.assertRaises(SystemExit):
                        module.main()
                    self.assertEqual(generate.call_count, 6)
                    # Supervisor inputs never carry the earlier positive rationale or severity.
                    self.assertNotIn('First-layer candidate', str(generate.call_args_list[-1].args[2]))
                with patch('sys.argv', args), patch.object(module, 'load_config', return_value=config), patch.object(module, 'model_fingerprint', return_value={'source': 'mock'}), \
                     patch.object(module, 'load_local_model', return_value=(None, None, 'mock')) as load_model, \
                     patch.object(ordinary, 'generate_chat', return_value=json.dumps(record('x', None)['llm_output'])) as generate:
                    module.main()
                    self.assertEqual(load_model.call_count, 1)  # supervisor only
                    self.assertEqual(generate.call_count, 1)
                with patch('sys.argv', args), patch.object(module, 'load_config', return_value=config), patch.object(module, 'model_fingerprint', return_value={'source': 'mock'}), \
                     patch.object(module, 'load_local_model', side_effect=AssertionError('completed neutral must not rerun')):
                    module.main()
                summary = json.loads((out / 'summary.json').read_text())
                self.assertEqual(summary['n_errors'], 0)
                self.assertEqual(summary['n_neutral'], 1)
                self.assertEqual(summary['n_success'], 0)
                with patch('sys.argv', [*args, '--rerun-supervisor']), patch.object(module, 'load_config', return_value=config), \
                     patch.object(module, 'model_fingerprint', return_value={'source': 'mock'}), \
                     patch.object(module, 'load_local_model', return_value=(None, None, 'mock')) as load_model, \
                     patch.object(ordinary, 'generate_chat', return_value=json.dumps(record('x', 0)['llm_output'])) as generate:
                    module.main()
                    self.assertEqual(load_model.call_count, 1)
                    self.assertEqual(generate.call_count, 2)
                self.assertEqual(len(list((out / 'history').glob('*/supervisor*codings.jsonl'))), 1)
                self.assertEqual(json.loads((out / 'summary.json').read_text())['n_neutral'], 0)


class CompatibilityGuardTests(unittest.TestCase):
    def test_legacy_binary_readers_reject_versioned_numeric_exports(self):
        from CAA.scripts import review_severity_outputs
        from CAA.scripts.analysis import aggregate_four_attack_evaluations, aggregate_reviewed_evaluations
        from CAA.scripts.analysis import compare_matched_conditions_mcnemar, compare_reviewed_attack_objectives
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'codings.csv'
            row = {"id": "a", "severity": "0 - Safe", "success": "False", "attempt": "test",
                   "source_primary_attack_vector": "test", "reasoning": "benign", "duration_s": "1",
                   "schema_version": SCHEMA_VERSION}
            write_csv(path, [row], tuple(row))
            for reader in (review_severity_outputs.read_csv, compare_matched_conditions_mcnemar.load_codings,
                           compare_reviewed_attack_objectives.read_csv):
                with self.subTest(reader=reader), self.assertRaises(ValueError):
                    reader(path)
            for module in (aggregate_four_attack_evaluations, aggregate_reviewed_evaluations):
                with self.assertRaisesRegex(ValueError, 'versioned neutral-aware'):
                    module.validate_summary({'schema_version': SCHEMA_VERSION}, path)

    def test_reference_reader_missing_output_is_error_and_duplicate_csv_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_jsonl(root / 'missing.jsonl', [{'id': 'a', 'llm_output': None}])
            self.assertEqual(load_coding_map(root / 'missing.jsonl')['a']['execution_status'], 'error')
            write_csv(root / 'duplicate.csv', [{'id': 'a', 'severity': '0 - Safe'}] * 2, ('id', 'severity'))
            with self.assertRaisesRegex(ValueError, 'Duplicate coding ID'):
                load_coding_map(root / 'duplicate.csv')

    def test_isolated_rejects_multi_turn_input_even_with_stale_parsed_count(self):
        row = {**transcript('a'), 'parent_attack_id': 'parent', 'isolated_conversation_index': 1, 'parsed_n_student_turns': 1}
        row['transcript_turns'].append({'speaker': 'Steve', 'text': 'Unseen extra history'})
        with self.assertRaisesRegex(ValueError, 'exactly one Student'):
            isolated.select_inputs([{'attack_id': 'parent', 'n_conversations': 1}], [row], None, None)
