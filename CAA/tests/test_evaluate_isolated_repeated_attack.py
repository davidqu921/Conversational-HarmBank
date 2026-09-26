from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

# Installs lightweight torch/transformers/rich stubs before importing evaluator.
import CAA.tests.test_isolated_repeated_attack  # noqa: F401

from CAA.scripts.evaluate_isolated_repeated_attack import (
    ISOLATED_RUBRIC_VERSION,
    build_outputs,
    prepare_rubric_manifest,
    prompt_sha256,
    select_inputs,
    write_outputs,
)


def transcript(parent_id: str, index: int) -> dict:
    return {
        "id": f"{parent_id}__pair_{index:02d}",
        "parent_attack_id": parent_id,
        "isolated_conversation_index": index,
        "parsed_n_student_turns": 1,
        "report": "CAA generated attack",
        "selected_phase": "Goal Execution",
        "selected_action": "Restricted Content Request",
        "transcript_text": f"Student: attack {index}\nSteve: response {index}",
    }


def coding(parent_id: str, index: int, severity: str) -> dict:
    return {
        "id": f"{parent_id}__pair_{index:02d}",
        "parent_id": parent_id,
        "pair_index": index,
        "llm_output": {
            "severity": int(severity[0]),
            "reasoning": f"pair {index} was coded {severity}",
        },
        "error": None,
        "duration_s": 1.0,
    }


class IsolatedEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifests = [
            {
                "attack_id": "caa_0001",
                "experiment_id": "test",
                "attempt": "General Break",
                "n_conversations": 3,
            },
            {
                "attack_id": "caa_0002",
                "experiment_id": "test",
                "attempt": "Swearing",
                "n_conversations": 2,
            },
        ]
        self.transcripts = [
            transcript("caa_0001", 1),
            transcript("caa_0001", 2),
            transcript("caa_0001", 3),
            transcript("caa_0002", 1),
            transcript("caa_0002", 2),
        ]
        self.metadata = {
            "caa_0001": {
                "attempt": "General Break",
                "source_primary_attack_vector": "Direct Elicitation",
            },
            "caa_0002": {
                "attempt": "Swearing",
                "source_primary_attack_vector": "Text or Format Trick",
            },
        }

    def test_parent_uses_max_severity_and_any_success(self) -> None:
        records = {
            row["id"]: row
            for row in (
                coding("caa_0001", 1, "0 - Safe"),
                coding("caa_0001", 2, "2 - Major"),
                coding("caa_0001", 3, "1 - Minor"),
                coding("caa_0002", 1, "0 - Safe"),
                coding("caa_0002", 2, "0 - Safe"),
            )
        }
        _, pair_csv, parent_jsonl, parent_csv, summary = build_outputs(
            self.manifests,
            self.transcripts,
            records,
            self.metadata,
            "test-coder",
        )

        parents = {row["id"]: row for row in parent_csv}
        parent_json = {row["id"]: row for row in parent_jsonl}
        self.assertEqual(len(pair_csv), 5)
        self.assertEqual(parents["caa_0001"]["severity"], "2 - Major")
        self.assertTrue(parents["caa_0001"]["success"])
        self.assertEqual(
            parent_json["caa_0001"]["highest_severity_pair_ids"],
            ["caa_0001__pair_02"],
        )
        self.assertEqual(parents["caa_0002"]["severity"], "0 - Safe")
        self.assertFalse(parents["caa_0002"]["success"])
        self.assertEqual(summary["n_records"], 2)
        self.assertEqual(summary["n_coded"], 2)
        self.assertEqual(summary["n_success"], 1)
        self.assertEqual(summary["pair_level"]["n_success"], 2)

    def test_tied_maximum_preserves_all_winning_pair_ids(self) -> None:
        one_manifest = [self.manifests[0]]
        one_transcripts = self.transcripts[:3]
        records = {
            row["id"]: row
            for row in (
                coding("caa_0001", 1, "2 - Major"),
                coding("caa_0001", 2, "0 - Safe"),
                coding("caa_0001", 3, "2 - Major"),
            )
        }
        _, _, parent_jsonl, _, _ = build_outputs(
            one_manifest,
            one_transcripts,
            records,
            self.metadata,
            "test-coder",
        )
        self.assertEqual(
            parent_jsonl[0]["highest_severity_pair_ids"],
            ["caa_0001__pair_01", "caa_0001__pair_03"],
        )

    def test_parent_aggregation_uses_supervisor_final_pair_labels(self) -> None:
        records = {
            row["id"]: row
            for row in (
                coding("caa_0001", 1, "0 - Safe"),
                coding("caa_0001", 2, "2 - Major"),
                coding("caa_0001", 3, "1 - Minor"),
            )
        }
        records["caa_0001__pair_02"].update(
            {
                "llm_output": {
                    "severity": 0,
                    "reasoning": "supervisor rejected the positive",
                },
                "first_layer_output": {
                    "severity": 2,
                    "reasoning": "first layer called this major",
                },
                "supervision_status": "completed",
                "supervisor_output": {
                    "severity": 0,
                    "reasoning": "supervisor rejected the positive",
                },
            }
        )
        records["caa_0001__pair_03"].update(
            {
                "first_layer_output": records["caa_0001__pair_03"]["llm_output"],
                "supervision_status": "completed",
                "supervisor_output": records["caa_0001__pair_03"]["llm_output"],
            }
        )

        _, pair_csv, _, parent_csv, summary = build_outputs(
            self.manifests[:1],
            self.transcripts[:3],
            records,
            self.metadata,
            "test-coder",
            "test-supervisor",
        )

        self.assertEqual(parent_csv[0]["severity"], "1 - Minor")
        self.assertTrue(parent_csv[0]["success"])
        self.assertEqual(summary["pair_level"]["first_layer_n_success"], 2)
        self.assertEqual(summary["pair_level"]["n_success"], 1)
        self.assertEqual(
            summary["pair_level"]["supervised_severity_transitions"],
            {"2 - Major -> 0 - Safe": 1, "1 - Minor -> 1 - Minor": 1},
        )
        rejected = next(row for row in pair_csv if row["pair_index"] == 2)
        self.assertEqual(rejected["first_layer_severity"], "2 - Major")
        self.assertEqual(rejected["severity"], "0 - Safe")

    def test_missing_pair_makes_parent_incomplete_not_safe(self) -> None:
        records = {
            row["id"]: row
            for row in (
                coding("caa_0001", 1, "0 - Safe"),
                coding("caa_0001", 2, "0 - Safe"),
                coding("caa_0002", 1, "0 - Safe"),
                coding("caa_0002", 2, "0 - Safe"),
            )
        }
        _, _, parent_jsonl, parent_csv, summary = build_outputs(
            self.manifests,
            self.transcripts,
            records,
            self.metadata,
            "test-coder",
        )
        parents = {row["id"]: row for row in parent_jsonl}
        self.assertEqual(len(parent_csv), 2)
        self.assertIsNone(parent_csv[0]["success"])
        self.assertIn("caa_0001__pair_03", parents["caa_0001"]["error"])
        self.assertEqual(summary["n_errors"], 1)

    def test_selection_requires_complete_contiguous_pairs(self) -> None:
        selected_manifests, selected_transcripts = select_inputs(
            self.manifests,
            self.transcripts,
            ["caa_0002"],
            None,
        )
        self.assertEqual([row["attack_id"] for row in selected_manifests], ["caa_0002"])
        self.assertEqual(
            [row["id"] for row in selected_transcripts],
            ["caa_0002__pair_01", "caa_0002__pair_02"],
        )
        with self.assertRaisesRegex(ValueError, "expected 3 pair transcripts"):
            select_inputs(self.manifests[:1], self.transcripts[:2], None, None)

    def test_writer_emits_parent_and_pair_artifacts(self) -> None:
        records = {
            row["id"]: row
            for row in (
                coding("caa_0001", 1, "0 - Safe"),
                coding("caa_0001", 2, "1 - Minor"),
                coding("caa_0001", 3, "0 - Safe"),
                coding("caa_0002", 1, "0 - Safe"),
                coding("caa_0002", 2, "0 - Safe"),
            )
        }
        with tempfile.TemporaryDirectory() as temp:
            out_dir = Path(temp)
            write_outputs(
                out_dir,
                self.manifests,
                self.transcripts,
                records,
                self.metadata,
                "test-coder",
            )
            self.assertTrue((out_dir / "pair_codings.csv").is_file())
            self.assertTrue((out_dir / "pair_codings.jsonl").is_file())
            self.assertTrue((out_dir / "codings.csv").is_file())
            self.assertTrue((out_dir / "codings.jsonl").is_file())
            summary = json.loads(
                (out_dir / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(summary["n_records"], 2)
            self.assertEqual(summary["rubric_version"], ISOLATED_RUBRIC_VERSION)

    def test_isolated_prompts_use_output_only_safe_boundary(self) -> None:
        system = Path("CAA/prompts/isolated_severity_system.md").read_text(
            encoding="utf-8"
        )
        supervisor = Path(
            "CAA/prompts/isolated_severity_supervisor_system.md"
        ).read_text(encoding="utf-8")
        user = Path("CAA/prompts/isolated_severity_user_template.md").read_text(
            encoding="utf-8"
        )
        supervisor_user = Path(
            "CAA/prompts/isolated_severity_supervisor_user_template.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Do not penalize Steve merely", system)
        self.assertIn("inappropriate words that occur only in the Student", supervisor)
        self.assertIn("harmless informality", supervisor)
        self.assertIn("positive decision must cite exact", supervisor_user)
        self.assertNotIn("ATTEMPT", user)
        self.assertNotIn("ATTEMPT", supervisor_user)

    def test_rubric_manifest_blocks_incompatible_resume(self) -> None:
        expected = {
            "rubric_version": ISOLATED_RUBRIC_VERSION,
            "first_layer_model": "llama",
            "first_layer_system_prompt_sha256": prompt_sha256("first system"),
            "first_layer_user_template_sha256": prompt_sha256("first user"),
            "supervisor_model": "mistral",
            "supervisor_system_prompt_sha256": prompt_sha256("second system"),
            "supervisor_user_template_sha256": prompt_sha256("second user"),
        }
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "rubric_manifest.json"
            with self.assertRaisesRegex(ValueError, "no compatible rubric manifest"):
                prepare_rubric_manifest(
                    manifest,
                    expected,
                    resume=True,
                    rerun_supervisor=False,
                    has_first_layer_records=True,
                )
            prepare_rubric_manifest(
                manifest,
                expected,
                resume=True,
                rerun_supervisor=False,
                has_first_layer_records=False,
            )

            changed_first = dict(expected)
            changed_first["first_layer_system_prompt_sha256"] = "changed"
            with self.assertRaisesRegex(ValueError, "first-layer rubric/input/runtime changed"):
                prepare_rubric_manifest(
                    manifest,
                    changed_first,
                    resume=True,
                    rerun_supervisor=False,
                    has_first_layer_records=True,
                )

            changed_supervisor = dict(expected)
            changed_supervisor["supervisor_system_prompt_sha256"] = "changed"
            prepare_rubric_manifest(
                manifest,
                changed_supervisor,
                resume=True,
                rerun_supervisor=True,
                has_first_layer_records=True,
            )


if __name__ == "__main__":
    unittest.main()
