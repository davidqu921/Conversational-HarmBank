"""
Build a turn-action-level CAB for Round 5 reviewed data.

Success attacks use fillback turn actions aligned to the human-reviewed phase
coding. Unsuccessful and no-attack conversations use direct LLM turn segments
from conversation_seg/results_4.

Outputs default to raw_cab_round5_reviewed_all:
  - turn_action_conversation_bank.jsonl
  - turn_action_conversation_bank.csv
  - turn_action_conversation_bank_issues.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSIGNMENTS = PROJECT_ROOT / "raw_cab_round5_reviewed_all" / "category_assignments.csv"
DEFAULT_SEG_RESULTS_DIR = PROJECT_ROOT / "conversation_seg" / "results_4"
DEFAULT_SUCCESS_TURNS = DEFAULT_SEG_RESULTS_DIR / "success_attack" / "fillback_turn_segments.csv"
DEFAULT_SUCCESS_VALIDATION = DEFAULT_SEG_RESULTS_DIR / "success_attack" / "fillback_validation_report.csv"
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab_round5_reviewed_all"


def compact(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def sort_id_key(conv_id: str) -> tuple[int, str]:
    return (int(conv_id), conv_id) if conv_id.isdigit() else (sys.maxsize, conv_id)


def sort_turn_key(row: dict[str, Any]) -> tuple[int, str]:
    turn = str(row.get("turn", ""))
    return (int(turn), turn) if turn.isdigit() else (sys.maxsize, turn)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def collapse_adjacent(values: list[str]) -> list[str]:
    out: list[str] = []
    previous = None
    for value in values:
        value = compact(value)
        if not value or value == previous:
            continue
        out.append(value)
        previous = value
    return out


def load_assignments(path: Path) -> dict[str, dict[str, str]]:
    assignments: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        conv_id = compact(row.get("id"))
        if conv_id:
            assignments[conv_id] = {key: compact(value) for key, value in row.items()}
    return assignments


def load_validation(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    validation: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        conv_id = compact(row.get("id"))
        if conv_id:
            validation[conv_id] = {key: compact(value) for key, value in row.items()}
    return validation


def load_turn_segments(path: Path, turn_source: str) -> dict[str, list[dict[str, Any]]]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not path.exists():
        return {}
    for row in read_csv(path):
        conv_id = compact(row.get("id"))
        turn = compact(row.get("turn"))
        phase = compact(row.get("phase"))
        action = compact(row.get("action"))
        if not conv_id or not turn or not phase or not action:
            continue
        turn_record = {
            "turn": int(turn) if turn.isdigit() else turn,
            "text": row.get("text", ""),
            "phase": phase,
            "action": action,
            "source": turn_source,
        }
        phrase_index = compact(row.get("phrase_index"))
        phrase_turns = compact(row.get("phrase_turns"))
        if phrase_index:
            turn_record["phrase_index"] = int(phrase_index) if phrase_index.isdigit() else phrase_index
        if phrase_turns:
            turn_record["phrase_turns"] = phrase_turns
        by_id[conv_id].append(turn_record)
    for rows in by_id.values():
        rows.sort(key=sort_turn_key)
    return dict(by_id)


def load_all_turn_segments(
    seg_results_dir: Path,
    success_turns: Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    rows_by_id: dict[str, list[dict[str, Any]]] = {}
    turn_source_by_pool = {
        "success_attack": "human_reviewed_phase_fillback",
        "unsuccess_attack": "llm_direct",
        "no_attack": "llm_direct",
    }
    paths_by_pool = {
        "success_attack": success_turns,
        "unsuccess_attack": seg_results_dir / "unsuccess_attack" / "turn_segments.csv",
        "no_attack": seg_results_dir / "no_attack" / "turn_segments.csv",
    }
    source_by_id: dict[str, str] = {}
    for pool, path in paths_by_pool.items():
        loaded = load_turn_segments(path, turn_source_by_pool[pool])
        for conv_id, turns in loaded.items():
            rows_by_id[conv_id] = turns
            source_by_id[conv_id] = turn_source_by_pool[pool]
    return rows_by_id, source_by_id


def split_attempts(value: str, primary: str) -> list[str]:
    text = compact(value)
    if not text and primary == "No Attempt":
        return ["No Attempt"]
    if not text:
        return []
    parts: list[str] = []
    for chunk in text.replace("|", ";").split(";"):
        chunk = compact(chunk)
        if chunk:
            parts.append(chunk)
    return parts or [text]


def build_record(
    conv_id: str,
    assignment: dict[str, str],
    turns: list[dict[str, Any]],
    turn_source: str,
    validation: dict[str, str],
) -> dict[str, Any]:
    action_sequence = [compact(turn.get("action")) for turn in turns if compact(turn.get("action"))]
    phase_sequence = [compact(turn.get("phase")) for turn in turns if compact(turn.get("phase"))]
    validation_status = validation.get("status") or ("ok" if assignment.get("category") != "success_attack" else "missing_validation")
    turn_coverage_issue = validation_status != "ok"
    primary = assignment.get("primary_attack_vector", "")

    return {
        "conversation_id": conv_id,
        "source_pool": assignment.get("category", ""),
        "turn_source": turn_source,
        "validation_status": validation_status,
        "turn_coverage_issue": turn_coverage_issue,
        "primary_attack_vector": primary,
        "secondary_attack_vector": assignment.get("secondary_attack_vector", ""),
        "attempt": assignment.get("attempt", ""),
        "attempt_type": split_attempts(assignment.get("attempt", ""), primary),
        "conversational": assignment.get("conversational", ""),
        "severity": assignment.get("severity", ""),
        "turn_count": len(turns),
        "raw_action_trajectory_length": len(action_sequence),
        "action_trajectory_length": len(collapse_adjacent(action_sequence)),
        "raw_phase_trajectory_length": len(phase_sequence),
        "phase_trajectory_length": len(collapse_adjacent(phase_sequence)),
        "action_sequence": action_sequence,
        "action_trajectory": collapse_adjacent(action_sequence),
        "phase_sequence": phase_sequence,
        "phase_trajectory": collapse_adjacent(phase_sequence),
        "turns": turns,
    }


def build_records(
    assignments: dict[str, dict[str, str]],
    turns_by_id: dict[str, list[dict[str, Any]]],
    turn_source_by_id: dict[str, str],
    success_validation: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for conv_id in sorted(assignments, key=sort_id_key):
        assignment = assignments[conv_id]
        source_pool = assignment.get("category", "")
        if source_pool not in {"success_attack", "unsuccess_attack", "no_attack"}:
            continue
        turns = turns_by_id.get(conv_id, [])
        if not turns:
            issues.append({
                "id": conv_id,
                "source_pool": source_pool,
                "severity": "error",
                "issue": "missing_turn_segments",
                "detail": "No turn-action rows found for this conversation.",
            })
            continue
        validation = success_validation.get(conv_id, {}) if source_pool == "success_attack" else {}
        record = build_record(
            conv_id=conv_id,
            assignment=assignment,
            turns=turns,
            turn_source=turn_source_by_id.get(conv_id, ""),
            validation=validation,
        )
        if record["turn_coverage_issue"]:
            issue_fields = [
                "missing_turns",
                "extra_turns",
                "duplicate_turns",
                "invalid_action_turns",
                "action_phase_mismatch_turns",
                "missing_reviewed_phase_turns",
                "api_error",
            ]
            detail = "; ".join(
                f"{field}={validation.get(field)}"
                for field in issue_fields
                if validation.get(field)
            )
            issues.append({
                "id": conv_id,
                "source_pool": source_pool,
                "severity": "warning",
                "issue": f"validation_status={record['validation_status']}",
                "detail": detail or "Fillback validation status is not ok.",
            })
        records.append(record)
    return records, issues


def flatten_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append({
            "conversation_id": record["conversation_id"],
            "source_pool": record["source_pool"],
            "turn_source": record["turn_source"],
            "validation_status": record["validation_status"],
            "turn_coverage_issue": record["turn_coverage_issue"],
            "primary_attack_vector": record["primary_attack_vector"],
            "secondary_attack_vector": record["secondary_attack_vector"],
            "attempt": record["attempt"],
            "conversational": record["conversational"],
            "severity": record["severity"],
            "turn_count": record["turn_count"],
            "action_trajectory_length": record["action_trajectory_length"],
            "raw_action_trajectory_length": record["raw_action_trajectory_length"],
            "phase_trajectory_length": record["phase_trajectory_length"],
            "action_trajectory": " -> ".join(record["action_trajectory"]),
            "phase_trajectory": " -> ".join(record["phase_trajectory"]),
        })
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a turn-action-level CAB for Round 5 reviewed data.")
    parser.add_argument("--assignments", type=Path, default=DEFAULT_ASSIGNMENTS)
    parser.add_argument("--seg-results-dir", type=Path, default=DEFAULT_SEG_RESULTS_DIR)
    parser.add_argument("--success-turns", type=Path, default=DEFAULT_SUCCESS_TURNS)
    parser.add_argument("--success-validation", type=Path, default=DEFAULT_SUCCESS_VALIDATION)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assignments = load_assignments(args.assignments)
    turns_by_id, turn_source_by_id = load_all_turn_segments(args.seg_results_dir, args.success_turns)
    success_validation = load_validation(args.success_validation)
    records, issues = build_records(assignments, turns_by_id, turn_source_by_id, success_validation)

    write_jsonl(args.out_dir / "turn_action_conversation_bank.jsonl", records)
    write_csv(
        args.out_dir / "turn_action_conversation_bank.csv",
        flatten_records(records),
        [
            "conversation_id",
            "source_pool",
            "turn_source",
            "validation_status",
            "turn_coverage_issue",
            "primary_attack_vector",
            "secondary_attack_vector",
            "attempt",
            "conversational",
            "severity",
            "turn_count",
            "action_trajectory_length",
            "raw_action_trajectory_length",
            "phase_trajectory_length",
            "action_trajectory",
            "phase_trajectory",
        ],
    )
    write_csv(
        args.out_dir / "turn_action_conversation_bank_issues.csv",
        issues,
        ["id", "source_pool", "severity", "issue", "detail"],
    )

    print(f"Loaded {len(assignments)} category assignments")
    print(f"Wrote {len(records)} turn-action CAB records to {args.out_dir / 'turn_action_conversation_bank.jsonl'}")
    print(f"Issues: {len(issues)}")


if __name__ == "__main__":
    main()
