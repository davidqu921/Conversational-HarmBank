"""
Build Round 5 human review templates from Round 4 LLM codings.

Each reviewer receives a CSV shard. For each coding dimension, reviewers enter:
  - ✓ if they fully agree with the LLM label
  - the corrected label if they disagree

Defaults:
  LLM codings: coding_results/minimax_round4/codings.csv
  output dir:  data_prep/human_label_5
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CODINGS = PROJECT_ROOT / "coding_results" / "minimax_round4" / "codings.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data_prep" / "human_label_5"

REVIEW_COLUMNS = [
    "primary_attack_vector_review",
    "secondary_attack_vector_review",
    "attempt_review",
    "conversational_review",
    "severity_review",
]

OUTPUT_COLUMNS = [
    "id",
    "reviewer_part",
    "llm_primary_attack_vector",
    "primary_attack_vector_review",
    "llm_secondary_attack_vector",
    "secondary_attack_vector_review",
    "llm_attempt",
    "attempt_review",
    "llm_conversational",
    "conversational_review",
    "llm_severity",
    "severity_review",
    "llm_reasoning",
    "review_notes",
]


def load_codings(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sort_key(row: dict[str, str]) -> tuple[int, str]:
    conv_id = str(row["id"])
    return (int(conv_id), conv_id) if conv_id.isdigit() else (math.inf, conv_id)


def build_rows(codings: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for coding in sorted(codings, key=sort_key):
        conv_id = str(coding["id"])
        rows.append({
            "id": conv_id,
            "reviewer_part": "",
            "llm_primary_attack_vector": coding.get("primary_attack_vector", ""),
            "primary_attack_vector_review": "",
            "llm_secondary_attack_vector": coding.get("secondary_attack_vector", ""),
            "secondary_attack_vector_review": "",
            "llm_attempt": coding.get("attempt", ""),
            "attempt_review": "",
            "llm_conversational": coding.get("conversational", ""),
            "conversational_review": "",
            "llm_severity": coding.get("severity", ""),
            "severity_review": "",
            "llm_reasoning": coding.get("reasoning", ""),
            "review_notes": "",
        })
    return rows


def split_evenly(rows: list[dict[str, Any]], num_parts: int) -> list[list[dict[str, Any]]]:
    shards: list[list[dict[str, Any]]] = [[] for _ in range(num_parts)]
    for idx, row in enumerate(rows):
        shards[idx % num_parts].append(row)
    return shards


def write_csv(path: Path, rows: list[dict[str, Any]], part_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            row = dict(row)
            row["reviewer_part"] = part_name
            writer.writerow(row)


def write_manifest(path: Path, shards: list[list[dict[str, Any]]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "num_conversations", "first_id", "last_id"])
        writer.writeheader()
        for idx, rows in enumerate(shards, start=1):
            writer.writerow({
                "file": f"round5_llm_review_part{idx}.csv",
                "num_conversations": len(rows),
                "first_id": rows[0]["id"] if rows else "",
                "last_id": rows[-1]["id"] if rows else "",
            })


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Round 5 LLM coding review CSV templates.")
    parser.add_argument("--codings", type=Path, default=DEFAULT_CODINGS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--num-reviewers", type=int, default=4)
    parser.add_argument("--limit", type=int, help="Optional cap on number of LLM-coded conversations to split.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    codings = load_codings(args.codings)
    if args.limit is not None:
        codings = sorted(codings, key=sort_key)[:args.limit]
    rows = build_rows(codings)
    shards = split_evenly(rows, args.num_reviewers)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for idx, shard in enumerate(shards, start=1):
        write_csv(args.out_dir / f"round5_llm_review_part{idx}.csv", shard, f"part{idx}")
    write_manifest(args.out_dir / "round5_llm_review_manifest.csv", shards)

    print(f"Read {len(codings)} LLM codings from {args.codings}")
    print(f"Wrote {len(shards)} review files to {args.out_dir}")
    print("Shard sizes: " + ", ".join(str(len(shard)) for shard in shards))


if __name__ == "__main__":
    main()
