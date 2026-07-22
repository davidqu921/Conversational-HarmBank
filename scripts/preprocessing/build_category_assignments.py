"""Build reviewed conversation pools used by the publication CAB pipeline."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.cab.prepare_round4_segmentation_pools import (
    load_and_classify,
    load_clean_ids,
    write_assignments,
    write_id_list,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CODINGS = (
    PROJECT_ROOT / "data_prep" / "human_label_5" / "resolved_coding_results"
    / "round5_reviewed_completed_codings.csv"
)
DEFAULT_TRANSCRIPTS = PROJECT_ROOT / "data_prep" / "clean_transcript.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab_round5_reviewed_all"
CATEGORIES = ("success_attack", "unsuccess_attack", "no_attack", "unclassified")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify frozen reviewed labels into CAB source pools."
    )
    parser.add_argument("--codings", type=Path, default=DEFAULT_CODINGS)
    parser.add_argument("--clean-transcripts", type=Path, default=DEFAULT_TRANSCRIPTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean_ids = load_clean_ids(args.clean_transcripts)
    assignments, skipped = load_and_classify(args.codings, clean_ids)
    ids_by_category = {
        category: [row["id"] for row in assignments if row["category"] == category]
        for category in CATEGORIES
    }
    for category, ids in ids_by_category.items():
        write_id_list(args.out_dir / category / "ids.txt", ids)
    write_assignments(args.out_dir / "category_assignments.csv", assignments)

    print(f"Reviewed coding rows included: {len(assignments)}")
    print(f"Rows excluded because the cleaned transcript is absent: {skipped}")
    for category in CATEGORIES:
        print(f"{category}: {len(ids_by_category[category])}")


if __name__ == "__main__":
    main()

