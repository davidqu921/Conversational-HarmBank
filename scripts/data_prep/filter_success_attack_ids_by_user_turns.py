"""
Write success-attack conversation IDs and user-turn counts whose segmented
user-turn count is <= the selected threshold.

Defaults:
  input:  conversation_seg/results_2/success_attack/segmentations.jsonl
  output: data_prep/success_attack_id_with_turn_less_than_15
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "conversation_seg" / "results_2" / "success_attack" / "segmentations.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data_prep" / "success_attack_id_with_turn_less_than_15"
DEFAULT_MAX_USER_TURNS = 15


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} is not valid JSON") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_no} is not a JSON object")
            records.append(record)
    return records


def user_turn_count(record: dict[str, Any]) -> int | None:
    llm_output = record.get("llm_output")
    if not isinstance(llm_output, dict):
        return None
    turns = llm_output.get("turns")
    if not isinstance(turns, list):
        return None
    return len(turns)


def filter_ids(records: list[dict[str, Any]], max_user_turns: int) -> tuple[list[tuple[str, int]], int, int]:
    kept_rows: list[tuple[str, int]] = []
    skipped_invalid = 0
    skipped_too_long = 0

    for record in records:
        count = user_turn_count(record)
        if count is None:
            skipped_invalid += 1
            continue
        if count > max_user_turns:
            skipped_too_long += 1
            continue
        kept_rows.append((str(record["id"]), count))

    return kept_rows, skipped_invalid, skipped_too_long


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter success_attack IDs by segmented user-turn count."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-user-turns", type=int, default=DEFAULT_MAX_USER_TURNS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_jsonl(args.input)
    kept_rows, skipped_invalid, skipped_too_long = filter_ids(records, args.max_user_turns)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "user_turns"])
        writer.writerows(kept_rows)

    print(f"Read {len(records)} records from {args.input}")
    print(f"Wrote {len(kept_rows)} rows with user turns <= {args.max_user_turns} to {args.output}")
    print(f"Skipped {skipped_too_long} records with user turns > {args.max_user_turns}")
    print(f"Skipped {skipped_invalid} records with missing/invalid llm_output.turns")


if __name__ == "__main__":
    main()
