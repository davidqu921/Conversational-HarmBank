"""
Prepare conversation ID pools for segmentation from Round 4 LLM codings.

Default behavior reads:
  coding_results/minimax_round4/codings.csv

and writes new ID lists under:
  raw_cab_round4/success_attack/ids.txt
  raw_cab_round4/unsuccess_attack/ids.txt
  raw_cab_round4/no_attack/ids.txt
  raw_cab_round4/unclassified/ids.txt
  raw_cab_round4/category_assignments.csv

Classification rule:
  success_attack:
    - severity >= 1

  unsuccess_attack:
    - severity = 0 and primary attack vector is not No Attempt

  no_attack:
    - severity = 0 and primary attack vector is No Attempt
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CODINGS = PROJECT_ROOT / "coding_results" / "minimax_round4" / "codings.csv"
DEFAULT_CLEAN_TRANSCRIPTS = PROJECT_ROOT / "data_prep" / "clean_transcript.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab_round4"

SEVERITY_TO_RANK = {
    "0 - Safe": 0,
    "1 - Minor": 1,
    "2 - Major": 2,
    "3 - Severe": 3,
}


def normalize(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def load_clean_ids(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    clean_ids: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            clean_ids.add(str(record["id"]))
    return clean_ids


def classify_row(row: dict[str, str]) -> tuple[str, str]:
    primary = normalize(row.get("primary_attack_vector"))
    severity = normalize(row.get("severity"))

    if severity not in SEVERITY_TO_RANK:
        return "unclassified", "missing_or_unknown_severity"

    severity_rank = SEVERITY_TO_RANK[severity]
    if severity_rank >= 1:
        return "success_attack", "severity>=1"
    if severity_rank == 0 and primary == "No Attempt":
        return "no_attack", "severity=0_and_primary_attack_vector_is_no_attempt"
    if severity_rank == 0 and primary and primary != "No Attempt":
        return "unsuccess_attack", "severity=0_and_primary_attack_vector_is_not_no_attempt"
    return "unclassified", "severity=0_but_missing_primary_attack_vector"


def load_and_classify(codings: Path, clean_ids: set[str] | None = None) -> tuple[list[dict[str, str]], int]:
    assignments: list[dict[str, str]] = []
    skipped_not_clean = 0
    with codings.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            conv_id = normalize(row.get("id"))
            if not conv_id:
                continue
            if clean_ids is not None and conv_id not in clean_ids:
                skipped_not_clean += 1
                continue
            category, reason = classify_row(row)
            assignments.append({
                "id": conv_id,
                "category": category,
                "reason": reason,
                "primary_attack_vector": normalize(row.get("primary_attack_vector")),
                "secondary_attack_vector": normalize(row.get("secondary_attack_vector")),
                "attempt": normalize(row.get("attempt")),
                "conversational": normalize(row.get("conversational")),
                "severity": normalize(row.get("severity")),
            })
    return assignments, skipped_not_clean


def write_id_list(path: Path, ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(ids) + ("\n" if ids else ""), encoding="utf-8")


def write_assignments(path: Path, assignments: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "category",
        "reason",
        "primary_attack_vector",
        "secondary_attack_vector",
        "attempt",
        "conversational",
        "severity",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(assignments)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare segmentation ID pools from Round 4 codings.")
    parser.add_argument("--codings", type=Path, default=DEFAULT_CODINGS)
    parser.add_argument(
        "--clean-transcripts",
        type=Path,
        default=DEFAULT_CLEAN_TRANSCRIPTS,
        help="Only include IDs present in this cleaned transcript JSONL. Pass --clean-transcripts-none to disable.",
    )
    parser.add_argument("--clean-transcripts-none", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean_ids = None if args.clean_transcripts_none else load_clean_ids(args.clean_transcripts)
    assignments, skipped_not_clean = load_and_classify(args.codings, clean_ids)

    categories = ["success_attack", "unsuccess_attack", "no_attack", "unclassified"]
    ids_by_category = {
        category: [row["id"] for row in assignments if row["category"] == category]
        for category in categories
    }

    for category, ids in ids_by_category.items():
        write_id_list(args.out_dir / category / "ids.txt", ids)
    write_assignments(args.out_dir / "category_assignments.csv", assignments)

    print(f"Read {len(assignments)} conversations from {args.codings}")
    if clean_ids is not None:
        print(f"Filtered to {len(clean_ids)} IDs from {args.clean_transcripts}")
        print(f"Skipped {skipped_not_clean} coding rows not present in clean transcripts")
    for category in categories:
        print(f"{category}: {len(ids_by_category[category])}")
    print(f"Wrote assignments to {args.out_dir / 'category_assignments.csv'}")


if __name__ == "__main__":
    main()
