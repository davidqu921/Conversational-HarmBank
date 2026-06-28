"""
Build a phrase-level human segmentation labeling template.

The input human template supplies the conversation IDs and source pools. The LLM
phase segmentation files supply phrase boundaries, but not labels for humans.

Defaults:
  input:  conversation_seg/human_coding_template/human_seg.csv
  phases: conversation_seg/results_2/{source_pool}/phase_segments.csv
  output: conversation_seg/human_coding_template/human_phrase_seg.csv
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HUMAN_SEG = PROJECT_ROOT / "conversation_seg" / "human_coding_template" / "human_seg.csv"
DEFAULT_PHASE_ROOT = PROJECT_ROOT / "conversation_seg" / "results_2"
DEFAULT_OUTPUT = PROJECT_ROOT / "conversation_seg" / "human_coding_template" / "human_phrase_seg.csv"


def load_human_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_phase_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            by_id[row["id"]].append(row)

    for rows in by_id.values():
        rows.sort(key=lambda row: int(row["start_turn"]))
    return by_id


def get_phase_rows(
    conv_id: str,
    source_pool: str,
    phase_root: Path,
    phase_cache: dict[str, dict[str, list[dict[str, str]]]],
) -> tuple[str, list[dict[str, str]]]:
    if source_pool not in phase_cache:
        phase_cache[source_pool] = load_phase_rows(phase_root / source_pool / "phase_segments.csv")
    rows = phase_cache[source_pool].get(conv_id, [])
    if rows:
        return source_pool, rows

    for phase_path in phase_root.glob("*/phase_segments.csv"):
        fallback_pool = phase_path.parent.name
        if fallback_pool not in phase_cache:
            phase_cache[fallback_pool] = load_phase_rows(phase_path)
        rows = phase_cache[fallback_pool].get(conv_id, [])
        if rows:
            return fallback_pool, rows

    return source_pool, []


def phrase_range(row: dict[str, str]) -> str:
    return f"T{row['start_turn']}-T{row['end_turn']}"


def infer_n_user_turns(human_row: dict[str, str], phrase_rows: list[dict[str, str]]) -> str:
    n_user_turns = (human_row.get("n_user_turns") or "").strip()
    if n_user_turns:
        return n_user_turns
    if not phrase_rows:
        return ""
    max_end_turn = max(int(row["end_turn"]) for row in phrase_rows)
    return str(max_end_turn // 2)


def build_template_rows(human_rows: list[dict[str, str]], phase_root: Path) -> tuple[list[dict[str, Any]], int]:
    phase_cache: dict[str, dict[str, list[dict[str, str]]]] = {}
    output_rows: list[dict[str, Any]] = []
    max_phrases = 0

    for human_row in human_rows:
        source_pool = human_row["source_pool"]
        conv_id = human_row["id"]
        source_pool, phrase_rows = get_phase_rows(conv_id, source_pool, phase_root, phase_cache)
        max_phrases = max(max_phrases, len(phrase_rows))

        output_row: dict[str, Any] = {
            "id": conv_id,
            "source_pool": source_pool,
            "n_user_turns": infer_n_user_turns(human_row, phrase_rows),
            "num_phrases": len(phrase_rows),
        }
        for idx, phrase_row in enumerate(phrase_rows, start=1):
            output_row[f"phrase{idx}_turns"] = phrase_range(phrase_row)
            output_row[f"phrase{idx}_label"] = ""
        output_rows.append(output_row)

    return output_rows, max_phrases


def fieldnames(max_phrases: int) -> list[str]:
    names = ["id", "source_pool", "n_user_turns", "num_phrases"]
    for idx in range(1, max_phrases + 1):
        names.extend([f"phrase{idx}_turns", f"phrase{idx}_label"])
    return names


def write_template(path: Path, rows: list[dict[str, Any]], max_phrases: int) -> None:
    names = fieldnames(max_phrases)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            for idx in range(1, max_phrases + 1):
                row.setdefault(f"phrase{idx}_turns", "NA")
                row.setdefault(f"phrase{idx}_label", "NA")
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a phrase-level human segmentation CSV template."
    )
    parser.add_argument("--human-seg", type=Path, default=DEFAULT_HUMAN_SEG)
    parser.add_argument("--phase-root", type=Path, default=DEFAULT_PHASE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    human_rows = load_human_rows(args.human_seg)
    output_rows, max_phrases = build_template_rows(human_rows, args.phase_root)
    write_template(args.output, output_rows, max_phrases)

    print(f"Read {len(human_rows)} conversations from {args.human_seg}")
    print(f"Max phrases per conversation: {max_phrases}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
