import contextlib
import csv
import io as textio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from CAA.scripts import evaluate_harm_then_severity as h


def gate(value=False):
    return {"id": "a", "llm_output": {"harmful": value, "reasoning": "gate reason"}, "error": None}


def label(value="1 - Minor"):
    return {"id": "a", "llm_output": {"severity": value, "reasoning": "independent severity"}, "error": None}


def conversation(cid="a"):
    return {"id": cid, "transcript_turns": [
        {"turn": 1, "speaker": "Student", "text": "Student-only offensive words. Steve: fabricated marker"},
        {"turn": 2, "speaker": "Steve", "text": "I cannot help with that."}]}


class HarmGateTests(unittest.TestCase):
    def test_gate_rejects_non_boolean(self):
        for value in ["false", "true", 0, 1, None]:
            with self.assertRaises(ValueError):
                h.validate({"harmful": value, "reasoning": "reason"}, "harm")

    def test_gate_needs_no_evidence_or_severity(self):
        result = h.validate({"harmful": True, "reasoning": "actual content"}, "harm")
        self.assertEqual(set(result), {"harmful", "reasoning"})

    def test_negative_is_final_safe_without_second_stage(self):
        result = h.combine("a", gate(False), None)
        self.assertEqual(result["llm_output"]["severity"], "0 - Safe")
        self.assertEqual(result["status"], "gate_negative")

    def test_positive_without_second_stage_is_pending(self):
        result = h.combine("a", gate(True), None)
        self.assertIsNone(result["llm_output"])
        self.assertEqual(result["status"], "pending_severity")

    def test_failed_gate_is_not_safe(self):
        result = h.combine("a", {"error": "invalid JSON"}, None)
        self.assertIsNone(result["llm_output"])
        self.assertEqual(result["error"], "invalid JSON")

    def test_second_stage_can_reject_false_positive(self):
        result = h.combine("a", gate(True), label("0 - Safe"))
        self.assertEqual(result["llm_output"]["severity"], "0 - Safe")

    def test_second_stage_error_does_not_fall_back(self):
        result = h.combine("a", gate(True), {"error": "invalid severity"})
        self.assertIsNone(result["llm_output"])

    def test_only_valid_severity_and_reason_are_accepted(self):
        for output in [{"severity": "Minor", "reasoning": "text"}, {"severity": "1 - Minor", "reasoning": ""}]:
            with self.assertRaises(ValueError):
                h.validate(output, "severity")
        self.assertTrue(h.done(label(), "severity"))

    def test_stage_two_messages_have_no_prior_result(self):
        record = conversation()
        record["_turns"] = h.io.normalize_turns(record, False)
        result = h.messages(record, "system", "role")
        self.assertNotIn("gate reason", json.dumps(result))
        self.assertIn('"speaker": "Student"', result[1]["content"])
        self.assertIn('"speaker": "Steve"', result[1]["content"])

    def test_export_coverage_pending_and_success_are_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            summary = h.export(out, [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                {"a": gate(False), "b": gate(True), "c": gate(True)}, {"b": label()}, {})
            self.assertEqual((summary["n_records"], summary["n_coded"], summary["n_success"]), (3, 2, 1))
            self.assertEqual(summary["rubric_version"], h.VERSION)
            with (out / "codings.csv").open(encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertIn("c", (out / "review_queue.csv").read_text())


class HarmGatePipelineTests(unittest.TestCase):
    def setUp(self):
        import CAA.tests.test_isolated_repeated_attack  # noqa: F401
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exp = self.root / "exp"
        self.source = self.exp / h.CONDITIONS["context-independent"]
        self.source.mkdir(parents=True)
        self.target = self.root / "target.md"
        self.target.write_text("You are Steve.")
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({"experiment_id": "exp", "attacker_model": {"model_id": "screen"},
            "response_model": {"system_prompt": str(self.target)}, "paths": {"output_root": str(self.root), "model_cache": str(self.root)},
            "conversation": {"require_cuda": False}}))
        h.io.write_rows(self.source / "transcripts.jsonl", [conversation("a"), conversation("b")])
        self.out = self.exp / self.source.name.replace("_convos", "_evaluation") / h.OUTPUT_NAME
        self.calls = []

    def fake_stage(self, records, stage, journal, *args):
        self.calls.append((stage, [r["id"] for r in records]))
        rows = h.io.journal_rows(journal)
        for record in records:
            row = gate(record["id"] == "a") if stage == "harm" else label()
            row["id"] = record["id"]
            rows[record["id"]] = row
        h.io.write_rows(journal, list(rows.values()))

    def invoke(self, *extra):
        with patch("sys.argv", ["evaluator", "--config", str(self.config), *extra]), patch.object(h, "stage_run", side_effect=self.fake_stage), patch(
            "CAA.scripts.model_runtime.resolve_model_source", side_effect=lambda cfg, cache: ("/snapshots/" + cfg["model_id"], True)
        ), contextlib.redirect_stdout(textio.StringIO()):
            h.main()

    def test_only_harmful_reaches_second_stage_and_resume_skips_valid(self):
        self.invoke("--limit", "1")
        self.assertEqual(self.calls, [("harm", ["a"]), ("severity", ["a"])])
        self.calls.clear()
        self.invoke("--resume")
        self.assertEqual(self.calls, [("harm", ["b"]), ("severity", [])])
        summary = json.loads((self.out / "summary.json").read_text())
        self.assertEqual(summary["n_records"], 2)
        self.invoke("--resume", "--ids", "b")
        self.assertEqual(len(h.io.read_rows(self.out / "codings.jsonl")), 2)

    def test_incompatible_resume_is_rejected(self):
        self.invoke()
        h.io.write_rows(self.source / "transcripts.jsonl", [conversation("changed")])
        with self.assertRaisesRegex(ValueError, "manifest differs"):
            self.invoke("--resume")

    def test_existing_outputs_are_protected_without_resume(self):
        self.invoke()
        before = (self.out / "codings.jsonl").read_bytes()
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(before, (self.out / "codings.jsonl").read_bytes())

    def test_dry_run_no_models_and_both_prompts(self):
        self.invoke("--dry-run", "--limit", "1")
        self.assertFalse(self.calls)
        self.assertTrue((self.out / "dry_run/a_harm.json").exists())
        self.assertTrue((self.out / "dry_run/a_severity.json").exists())
        self.assertFalse((self.out / "codings.jsonl").exists())

    def test_interruption_keeps_positive_pending_and_resume_repairs(self):
        original = self.fake_stage
        def fail(records, stage, *args):
            if stage == "severity":
                raise RuntimeError("interrupted")
            return original(records, stage, *args)
        with patch.object(self, "fake_stage", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.invoke()
        self.assertEqual(json.loads((self.out / "summary.json").read_text())["n_success"], 0)
        self.invoke("--resume")
        self.assertEqual(json.loads((self.out / "summary.json").read_text())["n_errors"], 0)

    def test_human_and_unified_comparison_aligns_ids_and_reports_coverage(self):
        human = self.out.parent / "reviewed_severity_llama31"
        unified = self.out.parent / h.io.OUTPUT_NAME
        human.mkdir(parents=True)
        unified.mkdir()
        h.io.write_rows(human / "codings.jsonl", [dict(label("0 - Safe"), id="a"), dict(label(), id="b")])
        h.io.write_rows(unified / "codings.jsonl", [dict(label(), id="a")])
        self.invoke()
        coverage = json.loads((self.out / "comparison_coverage.json").read_text())
        self.assertEqual(coverage["n_common"], 1)
        self.assertEqual(coverage["positive_on_common_ids"], {"harm_gate": 1, "reviewed": 0, "unified": 1})
        self.assertTrue((self.out / "comparison_vs_reviewed/reference_comparison.json").exists())


if __name__ == "__main__":
    unittest.main()
