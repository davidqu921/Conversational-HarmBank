"""
Build the global Conversation Attack Bank (CAB).

This is a pure aggregation step. It reads:

  - conversation_seg/results_2/*/turn_segments.csv
  - conversation_seg/results_2/*/phase_segments.csv
  - conversation_seg/results_2/*/validation_report.csv
  - coding_results/minimax_all/codings.jsonl

and writes one JSON object per conversation with action/phase trajectories plus
attempt, outcome, and severity labels from the whole-conversation coding pass.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEG_RESULTS = PROJECT_ROOT / "conversation_seg" / "results_2"
DEFAULT_CODINGS = PROJECT_ROOT / "coding_results" / "minimax_all" / "codings.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sort_turn_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: int(row.get("turn") or 0))


def sort_phase_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: int(row.get("start_turn") or 0))


def ordered_unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip()
        if value and value not in seen:
            out.append(value)
            seen.add(value)
    return out


def collapse_adjacent(values: list[str]) -> list[str]:
    out: list[str] = []
    previous = None
    for value in values:
        if not value:
            continue
        if value == previous:
            continue
        out.append(value)
        previous = value
    return out


def load_validation_status(seg_results_dir: Path) -> dict[str, str]:
    status_by_id: dict[str, str] = {}
    for validation_path in sorted(seg_results_dir.glob("*/validation_report.csv")):
        for row in read_csv(validation_path):
            cid = row.get("id", "").strip()
            if cid:
                status_by_id[cid] = row.get("status", "").strip() or "unknown"
    return status_by_id


def load_turn_segments(seg_results_dir: Path) -> tuple[dict[str, list[dict[str, str]]], dict[str, str]]:
    rows_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    source_by_id: dict[str, str] = {}
    for turn_path in sorted(seg_results_dir.glob("*/turn_segments.csv")):
        source = turn_path.parent.name
        for row in read_csv(turn_path):
            cid = row.get("id", "").strip()
            if not cid:
                continue
            rows_by_id[cid].append(row)
            source_by_id[cid] = source
    return dict(rows_by_id), source_by_id


def load_phase_segments(seg_results_dir: Path) -> dict[str, list[dict[str, str]]]:
    rows_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for phase_path in sorted(seg_results_dir.glob("*/phase_segments.csv")):
        for row in read_csv(phase_path):
            cid = row.get("id", "").strip()
            if cid:
                rows_by_id[cid].append(row)
    return dict(rows_by_id)


def outcome_from_success(success_label: str) -> str:
    if success_label == "Yes - Broken":
        return "success"
    if success_label == "Maybe":
        return "maybe"
    if success_label == "No - Safe":
        return "not_success"
    return ""


def coding_from_llm_output(output: dict[str, Any]) -> dict[str, Any]:
    attempts: list[str] = []
    for coding in output.get("codings") or []:
        for attempt in coding.get("attempts") or []:
            attempt = str(attempt).strip()
            if attempt:
                attempts.append(attempt)
    success_label = str(output.get("success", "")).strip()
    return {
        "attempt_type": ordered_unique(attempts) or ["No Attempt"],
        "success_label": success_label,
        "outcome": outcome_from_success(success_label),
        "severity": str(output.get("severity", "")).strip(),
    }


def load_codings(codings_jsonl: Path) -> dict[str, dict[str, Any]]:
    """Load coding JSONL with latest successful record winning per id."""
    if codings_jsonl.suffix.lower() != ".jsonl":
        raise ValueError(f"CAB requires nested coding JSONL, not a flat export: {codings_jsonl}")
    codings: dict[str, dict[str, Any]] = {}
    with codings_jsonl.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("error") or not rec.get("llm_output"):
                continue
            cid = str(rec.get("id", "")).strip()
            if cid:
                codings[cid] = coding_from_llm_output(rec["llm_output"])
    return codings


def build_record(
    cid: str,
    source: str,
    validation_status: str,
    turn_rows: list[dict[str, str]],
    phase_rows: list[dict[str, str]],
    coding: dict[str, Any],
) -> dict[str, Any]:
    sorted_turns = sort_turn_rows(turn_rows)
    sorted_phases = sort_phase_rows(phase_rows)
    raw_action_trajectory = [row.get("action", "").strip() for row in sorted_turns if row.get("action", "").strip()]
    action_trajectory = collapse_adjacent(raw_action_trajectory)
    phase_trajectory = [row.get("phase", "").strip() for row in sorted_phases if row.get("phase", "").strip()]

    return {
        "conversation_id": cid,
        "source_pool": source,
        "validation_status": validation_status,
        "action_trajectory": action_trajectory,
        "action_trajectory_length": len(action_trajectory),
        "raw_action_trajectory_length": len(raw_action_trajectory),
        "phase_trajectory": phase_trajectory,
        "phase_trajectory_length": len(phase_trajectory),
        "attempt_type": coding.get("attempt_type", ["No Attempt"]),
        "outcome": coding.get("outcome", ""),
        "success_label": coding.get("success_label", ""),
        "severity": coding.get("severity", ""),
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_json(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def write_summary_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "conversation_id",
        "source_pool",
        "validation_status",
        "action_trajectory_length",
        "raw_action_trajectory_length",
        "phase_trajectory_length",
        "attempt_type",
        "outcome",
        "success_label",
        "severity",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({
                **{field: record.get(field, "") for field in fieldnames},
                "attempt_type": "; ".join(record.get("attempt_type", [])),
            })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seg-results-dir", type=Path, default=DEFAULT_SEG_RESULTS)
    parser.add_argument("--codings", type=Path, default=DEFAULT_CODINGS, help="Nested coding JSONL. Flat CSV exports are intentionally not supported.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--include-needs-review", action="store_true", help="Include validation status other than ok.")
    args = parser.parse_args()

    validation_status = load_validation_status(args.seg_results_dir)
    turn_rows_by_id, source_by_id = load_turn_segments(args.seg_results_dir)
    phase_rows_by_id = load_phase_segments(args.seg_results_dir)
    codings = load_codings(args.codings)

    records: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for cid in sorted(turn_rows_by_id, key=lambda value: int(value) if value.isdigit() else value):
        status = validation_status.get(cid, "missing_validation")
        if status != "ok" and not args.include_needs_review:
            skipped.append({"id": cid, "reason": f"validation_status={status}"})
            continue
        coding = codings.get(cid)
        if not coding:
            skipped.append({"id": cid, "reason": "missing_coding"})
            continue
        records.append(build_record(
            cid=cid,
            source=source_by_id.get(cid, ""),
            validation_status=status,
            turn_rows=turn_rows_by_id[cid],
            phase_rows=phase_rows_by_id.get(cid, []),
            coding=coding,
        ))

    for cid in sorted(set(validation_status) - set(turn_rows_by_id), key=lambda value: int(value) if value.isdigit() else value):
        skipped.append({"id": cid, "reason": "missing_turn_segments"})

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out_dir / "conversation_attack_bank.jsonl", records)
    write_json(args.out_dir / "conversation_attack_bank.json", records)
    write_summary_csv(args.out_dir / "conversation_attack_bank_summary.csv", records)
    write_jsonl(args.out_dir / "conversation_attack_bank_skipped.jsonl", skipped)

    print(f"CAB records: {len(records)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Output directory: {args.out_dir}")


if __name__ == "__main__":
    main()
