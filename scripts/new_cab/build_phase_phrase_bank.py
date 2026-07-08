"""
Build a phrase-level Conversation Attack Bank from reviewed/LLM segmentations.

Success attacks use the human-reviewed normalized phrase coding:
  conversation_seg/human_coding_template/normalized_seg_coding.csv

Unsuccessful and no-attack conversations use direct LLM phase segments:
  conversation_seg/results_4/{unsuccess_attack,no_attack}/phase_segments.csv

Outputs default to raw_cab_round5_reviewed_all:
  phrase_conversation_bank.jsonl
  phrase_conversation_bank.csv
  phrase_conversation_bank_issues.csv
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
DEFAULT_REVIEWED_SUCCESS = PROJECT_ROOT / "conversation_seg" / "human_coding_template" / "normalized_seg_coding.csv"
DEFAULT_SEG_RESULTS_DIR = PROJECT_ROOT / "conversation_seg" / "results_4"
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab_round5_reviewed_all"


def compact(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def sort_id_key(conv_id: str) -> tuple[int, str]:
    return (int(conv_id), conv_id) if conv_id.isdigit() else (sys.maxsize, conv_id)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_turn_range(turns: str) -> tuple[int, int] | None:
    text = compact(turns).lstrip("T")
    if "-T" in text:
        left, right = text.split("-T", 1)
    elif "-" in text:
        left, right = text.split("-", 1)
        right = right.lstrip("T")
    else:
        return None
    left = left.strip().lstrip("T")
    right = right.strip().lstrip("T")
    if not left.isdigit() or not right.isdigit():
        return None
    return int(left), int(right)


def load_assignments(path: Path) -> dict[str, dict[str, str]]:
    assignments: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        conv_id = compact(row.get("id"))
        if conv_id:
            assignments[conv_id] = {key: compact(value) for key, value in row.items()}
    return assignments


def phrase_indices(fieldnames: list[str]) -> list[int]:
    indices: list[int] = []
    for field in fieldnames:
        if field.startswith("phrase") and field.endswith("_turns"):
            raw = field[len("phrase"):-len("_turns")]
            if raw.isdigit():
                indices.append(int(raw))
    return sorted(indices)


def load_reviewed_success(path: Path) -> dict[str, list[dict[str, Any]]]:
    phrases_by_id: dict[str, list[dict[str, Any]]] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        indices = phrase_indices(reader.fieldnames or [])
        for row in reader:
            conv_id = compact(row.get("id"))
            if not conv_id:
                continue
            phrases: list[dict[str, Any]] = []
            for idx in indices:
                turns = compact(row.get(f"phrase{idx}_turns"))
                phase = compact(row.get(f"phrase{idx}_label"))
                if not turns or not phase:
                    continue
                parsed = parse_turn_range(turns)
                if parsed is None:
                    continue
                phrases.append({
                    "phrase_index": len(phrases) + 1,
                    "start_turn": parsed[0],
                    "end_turn": parsed[1],
                    "phase": phase,
                    "source": "human_reviewed",
                })
            phrases_by_id[conv_id] = phrases
    return phrases_by_id


def load_llm_phase_segments(seg_results_dir: Path, source_pool: str) -> dict[str, list[dict[str, Any]]]:
    path = seg_results_dir / source_pool / "phase_segments.csv"
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not path.exists():
        return {}
    for row in read_csv(path):
        conv_id = compact(row.get("id"))
        start = compact(row.get("start_turn"))
        end = compact(row.get("end_turn"))
        phase = compact(row.get("phase"))
        if not conv_id or not start.isdigit() or not end.isdigit() or not phase:
            continue
        by_id[conv_id].append({
            "phrase_index": 0,
            "start_turn": int(start),
            "end_turn": int(end),
            "phase": phase,
            "source": "llm",
        })
    for phrases in by_id.values():
        phrases.sort(key=lambda item: (item["start_turn"], item["end_turn"]))
        for idx, phrase in enumerate(phrases, start=1):
            phrase["phrase_index"] = idx
    return dict(by_id)


def make_record(conv_id: str, assignment: dict[str, str], phrases: list[dict[str, Any]]) -> dict[str, Any]:
    phase_trajectory = [phrase["phase"] for phrase in phrases]
    return {
        "conversation_id": conv_id,
        "source_pool": assignment.get("category", ""),
        "primary_attack_vector": assignment.get("primary_attack_vector", ""),
        "secondary_attack_vector": assignment.get("secondary_attack_vector", ""),
        "attempt": assignment.get("attempt", ""),
        "conversational": assignment.get("conversational", ""),
        "severity": assignment.get("severity", ""),
        "phrase_count": len(phrases),
        "phase_trajectory_length": len(phase_trajectory),
        "phase_trajectory": phase_trajectory,
        "phrases": phrases,
    }


def build_records(
    assignments: dict[str, dict[str, str]],
    reviewed_success: dict[str, list[dict[str, Any]]],
    llm_by_pool: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for conv_id in sorted(assignments, key=sort_id_key):
        assignment = assignments[conv_id]
        source_pool = assignment.get("category", "")
        if source_pool == "success_attack":
            phrases = reviewed_success.get(conv_id, [])
            phrase_source = "reviewed_success"
        elif source_pool in {"unsuccess_attack", "no_attack"}:
            phrases = llm_by_pool.get(source_pool, {}).get(conv_id, [])
            phrase_source = f"llm_{source_pool}"
        else:
            continue

        if not phrases:
            issues.append({
                "id": conv_id,
                "source_pool": source_pool,
                "severity": "error",
                "issue": "missing_phrase_segments",
                "detail": f"No phrases found in {phrase_source}",
            })
            continue
        records.append(make_record(conv_id, assignment, phrases))
    return records, issues


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def flatten_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append({
            "conversation_id": record["conversation_id"],
            "source_pool": record["source_pool"],
            "primary_attack_vector": record["primary_attack_vector"],
            "secondary_attack_vector": record["secondary_attack_vector"],
            "attempt": record["attempt"],
            "conversational": record["conversational"],
            "severity": record["severity"],
            "phrase_count": record["phrase_count"],
            "phase_trajectory": " -> ".join(record["phase_trajectory"]),
        })
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a phrase-level CAB from reviewed success phrases and LLM non-success phrases.")
    parser.add_argument("--assignments", type=Path, default=DEFAULT_ASSIGNMENTS)
    parser.add_argument("--reviewed-success", type=Path, default=DEFAULT_REVIEWED_SUCCESS)
    parser.add_argument("--seg-results-dir", type=Path, default=DEFAULT_SEG_RESULTS_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assignments = load_assignments(args.assignments)
    reviewed_success = load_reviewed_success(args.reviewed_success)
    llm_by_pool = {
        "unsuccess_attack": load_llm_phase_segments(args.seg_results_dir, "unsuccess_attack"),
        "no_attack": load_llm_phase_segments(args.seg_results_dir, "no_attack"),
    }
    records, issues = build_records(assignments, reviewed_success, llm_by_pool)

    write_jsonl(args.out_dir / "phrase_conversation_bank.jsonl", records)
    write_csv(
        args.out_dir / "phrase_conversation_bank.csv",
        flatten_records(records),
        [
            "conversation_id",
            "source_pool",
            "primary_attack_vector",
            "secondary_attack_vector",
            "attempt",
            "conversational",
            "severity",
            "phrase_count",
            "phase_trajectory",
        ],
    )
    write_csv(args.out_dir / "phrase_conversation_bank_issues.csv", issues, ["id", "source_pool", "severity", "issue", "detail"])

    print(f"Loaded {len(assignments)} category assignments")
    print(f"Wrote {len(records)} phrase CAB records to {args.out_dir / 'phrase_conversation_bank.jsonl'}")
    print(f"Issues: {len(issues)}")


if __name__ == "__main__":
    main()
