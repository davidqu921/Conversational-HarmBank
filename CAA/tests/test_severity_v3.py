"""Regression tests for exact restored prompt reuse and V2/V3 isolation."""
import csv
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import CAA.tests.test_isolated_repeated_attack
from CAA.scripts import code_caa_severity_with_hf as ordinary
from CAA.scripts import evaluate_isolated_repeated_attack as isolated
from CAA.scripts.severity_contract import (
    SCHEMA_VERSION, LEGACY_SCHEMA_VERSION, LEGACY_CONTRACT, V2_CONTRACT, LABELS,
    ContractError, normalize_model_output, load_jsonl, write_jsonl, valid_record_output,
)
from CAA.scripts.severity_profiles import LEGACY_SYSTEM, apply_prompt_paths, resolve_profile
from CAA.scripts.severity_reference import compare_with_reference


def answer(level):
    return json.dumps({"severity": level, "reasoning": "Sentinel model rationale."})


def conv(rid):
    return {"id": rid, "transcript_turns": [
        {"speaker": "Student", "text": "A request."},
        {"speaker": "Steve", "text": "A response."}]}


class LegacyContractTests(unittest.TestCase):
    def test_exact_old_labels_are_normalized_and_null_never_accepted(self):
        for index, name in enumerate(LABELS):
            self.assertEqual(normalize_model_output(json.loads(answer(name)), LEGACY_CONTRACT)["severity"], index)
        for value in (None, "null", 0, 1, 0.5, True, "0 - Minor", "Safe", " 0 - Safe"):
            with self.subTest(value=value), self.assertRaises(ContractError):
                normalize_model_output(json.loads(answer(value)), LEGACY_CONTRACT)
        self.assertIsNone(normalize_model_output(json.loads(answer(None)), V2_CONTRACT)["severity"])

    def test_v3_null_record_is_not_complete_but_v2_null_still_is(self):
        record = {"id": "a", "llm_output": {"severity": None, "reasoning": "ambiguous"}, "schema_version": LEGACY_SCHEMA_VERSION}
        self.assertIsNone(valid_record_output(record))
        record["schema_version"] = SCHEMA_VERSION
        self.assertIsNotNone(valid_record_output(record))

    def test_format_retry_repeats_legacy_contract_without_offering_neutral(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(ordinary, "generate_chat", side_effect=[answer(None), answer("1 - Minor")]) as generator:
                ordinary.code_stage(transcripts=[conv("a")], tokenizer=None, model=None,
                                    journal_path=root / 'stage.jsonl', raw_dir=root / 'raw',
                                    render_messages=lambda _: [{"role": "system", "content": LEGACY_SYSTEM.read_text()},
                                                                {"role": "user", "content": "Original transcript"}],
                                    max_new_tokens=128, resume=False, description="test", output_contract=LEGACY_CONTRACT)
            rows = load_jsonl(root / 'stage.jsonl')
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['execution_status'], 'error')
            self.assertIsNone(rows[0]['assessment'])
            self.assertEqual(rows[-1]['llm_output']['severity'], 1)
            self.assertEqual(rows[-1]['schema_version'], LEGACY_SCHEMA_VERSION)
            reminder = generator.call_args_list[1].args[2][-1]['content']
            self.assertIn('"0 - Safe"', reminder)
            self.assertIn('Do not return null', reminder)
            self.assertNotIn('integer 0, 1, 2, 3 or null', reminder)
            self.assertEqual(ordinary.done_ids_from_jsonl(root / 'stage.jsonl'), {'a'})

    def test_profiles_preserve_v2_and_all_single_layers_use_old_prompt(self):
        for family in ('conversation', 'isolated'):
            for double_layer, version in ((False, None), (False, 'v3'), (True, 'v3')):
                profile = resolve_profile(family, double_layer, version)
                self.assertEqual(profile.system_prompt, LEGACY_SYSTEM)
                self.assertEqual(profile.supervisor_system_prompt, LEGACY_SYSTEM)
                self.assertEqual(profile.output_contract, LEGACY_CONTRACT)
                self.assertNotIn('null', profile.user_template.read_text())
            profile = resolve_profile(family, True, 'v2')
            self.assertEqual(profile, resolve_profile(family, True, None))
            self.assertEqual(profile.schema_version, SCHEMA_VERSION)
            self.assertNotEqual(profile.system_prompt, LEGACY_SYSTEM)
            with self.assertRaises(ValueError):
                resolve_profile(family, False, 'v2')

    def test_restored_profile_rejects_incompatible_prompt_override(self):
        args = SimpleNamespace(system_prompt=Path('CAA/prompts/isolated_severity_system.md'))
        with self.assertRaises(ValueError):
            apply_prompt_paths(args, resolve_profile('isolated', False, None))


class V3EntrypointTests(unittest.TestCase):
    def setup_case(self, root, module, double=True, version='v3'):
        inputs = [conv('safe'), conv('positive')]
        args = ['evaluate', '--config', 'unused.yaml', '--out-dir', str(root / 'out'), '--resume']
        if version:
            args += ['--evaluator-version', version]
        if double:
            args += ['--double-layer']
        if module is isolated:
            for i, row in enumerate(inputs, 1):
                row.update(parent_attack_id='parent', isolated_conversation_index=i, parsed_n_student_turns=1)
            write_jsonl(root / 'parents.jsonl', [{'attack_id': 'parent', 'n_conversations': 2}])
            args += ['--parent-index', str(root / 'parents.jsonl')]
        write_jsonl(root / 'transcripts.jsonl', inputs)
        args += ['--transcripts', str(root / 'transcripts.jsonl')]
        config = SimpleNamespace(output_dir=root, raw={'attacker_model': {'model_id': 'coder'}, 'conversation': {'require_cuda': False}})
        return args, config

    def invoke(self, module, args, config, responses):
        with ExitStack() as stack:
            stack.enter_context(patch('sys.argv', args))
            stack.enter_context(patch.object(module, 'load_config', return_value=config))
            stack.enter_context(patch.object(module, 'model_fingerprint', return_value={'source': 'mock'}))
            load = stack.enter_context(patch.object(module, 'load_local_model', return_value=(None, None, 'mock')))
            generator = stack.enter_context(patch.object(ordinary, 'generate_chat', side_effect=responses))
            module.main()
            return generator, load

    def test_both_v3_entrypoints_use_exact_same_old_system_twice_and_resume(self):
        for module in (ordinary, isolated):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                args, config = self.setup_case(root, module)
                generator, load = self.invoke(module, args, config, [answer('0 - Safe'), answer('2 - Major'), answer('1 - Minor')])
                self.assertEqual(generator.call_count, 3)
                self.assertEqual(load.call_count, 2)
                for call in generator.call_args_list:
                    messages = call.args[2]
                    self.assertEqual(messages[0]['content'], LEGACY_SYSTEM.read_text())
                    self.assertNotIn('null', messages[1]['content'])
                    self.assertNotIn('Sentinel model rationale', messages[1]['content'])
                summary = json.loads((root / 'out/summary.json').read_text())
                self.assertEqual(summary['schema_version'], LEGACY_SCHEMA_VERSION)
                self.assertEqual(summary['n_neutral'], 0)
                self.assertEqual(summary['n_errors'], 0)
                self.assertEqual(summary['n_success'], 1)
                for name in ('codings.jsonl', 'pair_codings.jsonl') if module is isolated else ('codings.jsonl',):
                    self.assertTrue(all(r['schema_version'] == LEGACY_SCHEMA_VERSION for r in load_jsonl(root / 'out' / name)))
                with (root / 'out/codings.csv').open(encoding='utf-8-sig') as f:
                    self.assertTrue(all(r['schema_version'] == LEGACY_SCHEMA_VERSION for r in csv.DictReader(f)))
                generator, load = self.invoke(module, args, config, [])
                self.assertEqual(generator.call_count, 0)
                self.assertEqual(load.call_count, 0)
                # Reusing this directory for V2 must fail before invoking a model.
                v2_args = [a if a != 'v3' else 'v2' for a in args]
                with self.assertRaises((ValueError, SystemExit)):
                    self.invoke(module, v2_args, config, [])

    def test_both_single_layer_defaults_use_old_prompt_without_supervision(self):
        for module in (ordinary, isolated):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                args, config = self.setup_case(root, module, double=False, version=None)
                generator, load = self.invoke(module, args, config, [answer('0 - Safe'), answer('3 - Severe')])
                self.assertEqual(load.call_count, 1)
                self.assertEqual(generator.call_count, 2)
                self.assertEqual(generator.call_args.args[2][0]['content'], LEGACY_SYSTEM.read_text())
                self.assertEqual(json.loads((root / 'out/summary.json').read_text())['schema_version'], LEGACY_SCHEMA_VERSION)
                self.assertFalse(list((root / 'out').glob('supervisor*')))

    def test_v3_supervisor_null_exhaustion_is_error_not_neutral_or_positive_fallback(self):
        for module in (ordinary, isolated):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                args, config = self.setup_case(root, module)
                with self.assertRaises(SystemExit):
                    self.invoke(module, args, config, [answer('0 - Safe'), answer('1 - Minor'), answer(None), answer(None)])
                summary = json.loads((root / 'out/summary.json').read_text())
                self.assertEqual(summary['n_neutral'], 0)
                self.assertEqual(summary['n_errors'], 1)
                self.assertEqual(summary['n_success'], 0)
                generator, load = self.invoke(module, args, config, [answer('0 - Safe')])
                self.assertEqual(generator.call_count, 1)
                self.assertEqual(load.call_count, 1)
                self.assertEqual(json.loads((root / 'out/summary.json').read_text())['n_errors'], 0)

    def test_condition_selects_actual_input_and_version_specific_output(self):
        for condition, folder, out in [('trajectory', '', 'evaluation'), ('weak', 'weak_attack_convos', 'weak_attack_evaluation'),
                                       ('context-independent', 'context_independent_trajectory_seeded_repeated_weak_attack_convos',
                                        'context_independent_trajectory_seeded_repeated_weak_attack_evaluation')]:
            for double, version in ((False, None), (True, 'v2'), (True, 'v3')):
                with self.subTest(condition=condition, double=double, version=version), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write_jsonl(root / folder / 'transcripts.jsonl', [conv('a')])
                    config = SimpleNamespace(output_dir=root)
                    args = ['evaluate', '--config', 'unused', '--condition', condition, '--dry-run']
                    if double:
                        args += ['--double-layer', '--evaluator-version', version]
                    with patch('sys.argv', args), patch.object(ordinary, 'load_config', return_value=config):
                        ordinary.main()
                    profile = resolve_profile('conversation', double, version)
                    dry_dir = root / out / profile.output_dir_name / 'dry_run'
                    self.assertEqual((dry_dir / 'system_prompt.md').read_bytes(), profile.system_prompt.read_bytes())
                    self.assertTrue((dry_dir / 'user_prompt_a.md').exists())

    def test_reference_comparison_accepts_v3_numeric_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = {'id': 'a', 'llm_output': {'severity': 1, 'reasoning': 'evidence'}, 'schema_version': LEGACY_SCHEMA_VERSION}
            write_jsonl(root / 'v3.jsonl', [row])
            result = compare_with_reference(root / 'v3.jsonl', root / 'v3.jsonl', root)
            self.assertEqual(result['true_positive'], 1)
            self.assertEqual(result['exact_severity_agreement'], 1)
