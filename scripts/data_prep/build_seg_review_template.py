"""
Build a human review template for LLM conversation segmentation results.

The input is an LLM phase_segments.csv file where each row is one phrase. The
output is a wide CSV where each conversation is one row, num_phrases has a
blank review column, and each LLM phrase has blank review columns next to its
turn range and label.

Defaults:
  input:  conversation_seg/results_4/success_attack/phase_segments.csv
  output: conversation_seg/human_coding_template/seg_review_template.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE_SEGMENTS = PROJECT_ROOT / "conversation_seg" / "results_4" / "success_attack" / "phase_segments.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "conversation_seg" / "human_coding_template" / "seg_review_template.csv"


def compact(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def sort_id_key(conv_id: str) -> tuple[int, str]:
    return (int(conv_id), conv_id) if conv_id.isdigit() else (sys.maxsize, conv_id)


def sort_phrase_key(row: dict[str, str]) -> tuple[int, int]:
    start_turn = compact(row.get("start_turn"))
    end_turn = compact(row.get("end_turn"))
    return (
        int(start_turn) if start_turn.isdigit() else sys.maxsize,
        int(end_turn) if end_turn.isdigit() else sys.maxsize,
    )


def infer_source_pool(path: Path, explicit_source_pool: str | None) -> str:
    if explicit_source_pool:
        return explicit_source_pool
    if path.name == "phase_segments.csv":
        return path.parent.name
    return ""


def load_phase_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"id", "phase", "start_turn", "end_turn"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
        for row in reader:
            conv_id = compact(row.get("id"))
            if conv_id:
                by_id[conv_id].append(row)

    for rows in by_id.values():
        rows.sort(key=sort_phrase_key)
    return by_id


def phrase_turns(row: dict[str, str]) -> str:
    return f"T{compact(row.get('start_turn'))}-T{compact(row.get('end_turn'))}"


def infer_n_user_turns(phrase_rows: list[dict[str, str]]) -> str:
    end_turns = [compact(row.get("end_turn")) for row in phrase_rows]
    numeric_end_turns = [int(turn) for turn in end_turns if turn.isdigit()]
    if not numeric_end_turns:
        return ""
    return str(max(numeric_end_turns) // 2)


def build_template_rows(
    phase_rows_by_id: dict[str, list[dict[str, str]]],
    source_pool: str,
) -> tuple[list[dict[str, Any]], int]:
    output_rows: list[dict[str, Any]] = []
    max_phrases = 0

    for conv_id in sorted(phase_rows_by_id, key=sort_id_key):
        phrase_rows = phase_rows_by_id[conv_id]
        max_phrases = max(max_phrases, len(phrase_rows))
        output_row: dict[str, Any] = {
            "id": conv_id,
            "source_pool": source_pool,
            "n_user_turns": infer_n_user_turns(phrase_rows),
            "num_phrases": len(phrase_rows),
            "num_phrases_review": "",
        }
        for idx, phrase_row in enumerate(phrase_rows, start=1):
            output_row[f"phrase{idx}_turns"] = phrase_turns(phrase_row)
            output_row[f"phrase{idx}_turns_review"] = ""
            output_row[f"phrase{idx}_label"] = compact(phrase_row.get("phase"))
            output_row[f"phrase{idx}_label_review"] = ""
        output_rows.append(output_row)

    return output_rows, max_phrases


def fieldnames(max_phrases: int) -> list[str]:
    names = ["id", "source_pool", "n_user_turns", "num_phrases", "num_phrases_review"]
    for idx in range(1, max_phrases + 1):
        names.extend([
            f"phrase{idx}_turns",
            f"phrase{idx}_turns_review",
            f"phrase{idx}_label",
            f"phrase{idx}_label_review",
        ])
    return names


def write_template(path: Path, rows: list[dict[str, Any]], max_phrases: int) -> None:
    names = fieldnames(max_phrases)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a human review CSV for LLM phase segmentations.")
    parser.add_argument("--phase-segments", type=Path, default=DEFAULT_PHASE_SEGMENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--source-pool",
        help="Value for the source_pool column. Defaults to the parent directory name of phase_segments.csv.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_pool = infer_source_pool(args.phase_segments, args.source_pool)
    phase_rows_by_id = load_phase_rows(args.phase_segments)
    output_rows, max_phrases = build_template_rows(phase_rows_by_id, source_pool)
    write_template(args.output, output_rows, max_phrases)

    print(f"Read {sum(len(rows) for rows in phase_rows_by_id.values())} phrases from {args.phase_segments}")
    print(f"Conversations: {len(output_rows)}")
    print(f"Max phrases per conversation: {max_phrases}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
