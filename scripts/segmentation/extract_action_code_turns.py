"""
Extract code-like action labels from segmentation turn CSVs for review.

Examples:

  python -m scripts.segmentation.extract_action_code_turns --prefix A
  python -m scripts.segmentation.extract_action_code_turns --code A5

By default this scans conversation_seg/results/*/turn_segments.csv and writes a
review CSV under conversation_seg/review/.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "conversation_seg" / "results"
DEFAULT_REVIEW_DIR = PROJECT_ROOT / "conversation_seg" / "review"


def action_matches(action: str, prefix: str | None, code: str | None) -> bool:
    action = action.strip()
    if code:
        return re.match(rf"^{re.escape(code)}(?:\b|\.|\s|$)", action, flags=re.IGNORECASE) is not None
    if prefix:
        return re.match(rf"^{re.escape(prefix)}\d+(?:\b|\.|\s|$)", action, flags=re.IGNORECASE) is not None
    return False


def iter_turn_segment_files(results_dir: Path) -> list[Path]:
    return sorted(results_dir.glob("*/turn_segments.csv"))


def extract_rows(turn_csvs: list[Path], prefix: str | None, code: str | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in turn_csvs:
        source = path.parent.name
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                action = row.get("action", "")
                if not action_matches(action, prefix, code):
                    continue
                rows.append({
                    "source": source,
                    "id": row.get("id", ""),
                    "turn": row.get("turn", ""),
                    "action": action,
                    "phase": row.get("phase", ""),
                    "text": row.get("text", ""),
                })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--prefix", default="A", help="Extract code-like actions beginning with this prefix, e.g. A -> A5.")
    parser.add_argument("--code", help="Extract a specific action code, e.g. A5. Overrides --prefix.")
    parser.add_argument("--out", type=Path, help="Output CSV path.")
    args = parser.parse_args()

    turn_csvs = iter_turn_segment_files(args.results_dir)
    if not turn_csvs:
        raise FileNotFoundError(f"no turn_segments.csv files found under {args.results_dir}")

    rows = extract_rows(turn_csvs, args.prefix if not args.code else None, args.code)

    if args.out:
        out_path = args.out
    else:
        label = args.code or f"{args.prefix}_prefix"
        out_path = DEFAULT_REVIEW_DIR / f"action_code_{label}_turns.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "id", "turn", "action", "phase", "text"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Scanned {len(turn_csvs)} turn segment files")
    print(f"Extracted {len(rows)} rows")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
