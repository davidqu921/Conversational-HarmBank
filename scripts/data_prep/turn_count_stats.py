"""
Compute turn-count summary statistics for cleaned transcripts and segmentations.

Defaults:
  transcript input: data_prep/clean_transcript.jsonl
  segmentation dir: conversation_seg/results_2

Examples:
  python scripts/data_prep/turn_count_stats.py
  python -m scripts.data_prep.turn_count_stats --seg-root conversation_seg/results
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRANSCRIPTS = PROJECT_ROOT / "data_prep" / "clean_transcript.jsonl"
DEFAULT_SEG_ROOT = PROJECT_ROOT / "conversation_seg" / "results_2"
DEFAULT_GROUPS = ("success_attack", "unsuccess_attack", "no_attack")
DEFAULT_PERCENTILES = (10, 25, 50, 75, 80, 85, 90, 95, 99)
DEFAULT_CUTOFFS = (5, 10, 15, 20, 25, 30, 40, 50)
DEFAULT_BINS = ((1, 5), (6, 10), (11, 15), (16, 20), (21, 25), (26, 30), (31, 40), (41, 50))


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


def mean(values: list[int]) -> float:
    return statistics.fmean(values) if values else 0.0


def median(values: list[int]) -> float:
    return float(statistics.median(values)) if values else 0.0


def percentile(values: list[int], pct: int) -> float:
    if not values:
        return 0.0
    if pct <= 0:
        return float(min(values))
    if pct >= 100:
        return float(max(values))

    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * (pct / 100)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def iqr(values: list[int]) -> float:
    return percentile(values, 75) - percentile(values, 25)


def summarize(values: list[int]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "mean": mean(values),
        "median": median(values),
        "min": min(values) if values else 0,
        "max": max(values) if values else 0,
        "iqr": iqr(values),
    }


def coverage(values: list[int], cutoff: int) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if value <= cutoff) / len(values)


def print_distribution(name: str, values: list[int], cutoffs: tuple[int, ...]) -> None:
    if not values:
        print(f"{name}: no values")
        return

    stats = summarize(values)
    print(f"{name} distribution")
    print(
        f"  count={stats['count']} mean={stats['mean']:.2f} "
        f"median={stats['median']:.2f} iqr={stats['iqr']:.2f} "
        f"min/max={stats['min']}/{stats['max']}"
    )
    print(
        "  percentiles: "
        + " ".join(f"p{pct}={percentile(values, pct):.1f}" for pct in DEFAULT_PERCENTILES)
    )
    print(
        "  coverage: "
        + " ".join(f"<={cutoff}:{coverage(values, cutoff) * 100:.1f}%" for cutoff in cutoffs)
    )
    print(f"  histogram:")
    print_histogram(values)
    print()


def print_histogram(values: list[int]) -> None:
    total = len(values)
    max_bar_width = 32
    covered = 0
    for low, high in DEFAULT_BINS:
        count = sum(1 for value in values if low <= value <= high)
        covered += count
        bar = "#" * round((count / total) * max_bar_width)
        print(f"    {low:>2}-{high:<2} {count:>4} {count / total * 100:>5.1f}% {bar}")

    overflow = total - covered
    if overflow:
        high = DEFAULT_BINS[-1][1]
        bar = "#" * round((overflow / total) * max_bar_width)
        print(f"    >{high:<3} {overflow:>4} {overflow / total * 100:>5.1f}% {bar}")


def transcript_turn_counts(path: Path) -> list[int]:
    counts: list[int] = []
    for record in load_jsonl(path):
        try:
            counts.append(int(record["n_turns"]))
        except (KeyError, TypeError, ValueError) as exc:
            conv_id = record.get("id", "<missing id>")
            raise ValueError(f"Transcript {conv_id} has invalid n_turns") from exc
    return counts


def segmentation_user_turn_count(record: dict[str, Any]) -> int | None:
    llm_output = record.get("llm_output")
    if not isinstance(llm_output, dict):
        return None
    turns = llm_output.get("turns")
    if not isinstance(turns, list):
        return None
    return len(turns)


def segmentation_turn_counts(path: Path) -> tuple[list[int], int]:
    counts: list[int] = []
    skipped = 0
    for record in load_jsonl(path):
        count = segmentation_user_turn_count(record)
        if count is None:
            skipped += 1
            continue
        counts.append(count)
    return counts, skipped


def print_transcript_stats(path: Path) -> None:
    counts = transcript_turn_counts(path)
    stats = summarize(counts)
    print("Clean transcript conversation turns")
    print(f"  file: {path}")
    print(f"  conversations: {stats['count']}")
    print(f"  mean turns: {stats['mean']:.2f}")
    print(f"  median turns: {stats['median']:.2f}")
    print(f"  IQR turns: {stats['iqr']:.2f}")
    print(f"  min/max turns: {stats['min']}/{stats['max']}")
    print()
    print_distribution("Clean transcript conversation turns", counts, DEFAULT_CUTOFFS)


def print_segmentation_stats(seg_root: Path, groups: tuple[str, ...]) -> None:
    print("Segmentation user turns")
    print(f"  root: {seg_root}")
    print()
    print(
        f"{'group':<18} {'records':>7} {'valid':>7} {'skipped':>7} "
        f"{'mean':>8} {'median':>8} {'min':>5} {'max':>5}"
    )
    print("-" * 73)
    for group in groups:
        path = seg_root / group / "segmentations.jsonl"
        records = load_jsonl(path)
        counts, skipped = segmentation_turn_counts(path)
        stats = summarize(counts)
        print(
            f"{group:<18} {len(records):>7} {stats['count']:>7} {skipped:>7} "
            f"{stats['mean']:>8.2f} {stats['median']:>8.2f} "
            f"{stats['min']:>5} {stats['max']:>5}"
        )
    print()
    all_counts: list[int] = []
    for group in groups:
        path = seg_root / group / "segmentations.jsonl"
        counts, _ = segmentation_turn_counts(path)
        all_counts.extend(counts)
        print_distribution(f"{group} user turns", counts, DEFAULT_CUTOFFS)
    print_distribution("all segmentation user turns", all_counts, DEFAULT_CUTOFFS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate mean/median conversation turns and segmentation user turns."
    )
    parser.add_argument("--transcripts", type=Path, default=DEFAULT_TRANSCRIPTS)
    parser.add_argument("--seg-root", type=Path, default=DEFAULT_SEG_ROOT)
    parser.add_argument(
        "--groups",
        nargs="+",
        default=list(DEFAULT_GROUPS),
        help="Segmentation subdirectories under --seg-root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print_transcript_stats(args.transcripts)
    print_segmentation_stats(args.seg_root, tuple(args.groups))


if __name__ == "__main__":
    main()
