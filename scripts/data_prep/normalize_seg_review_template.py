"""
Normalize a reviewed LLM segmentation template into a clean phrase coding CSV.

The script resolves human review columns, merges adjacent phrases with the same
phase label, and writes:
  - normalized_seg_coding.csv
  - normalized_seg_coding_issues.csv

Review semantics match check_seg_review_template.py:
  - V/v/check/ok means keep the LLM value.
  - A non-empty review value replaces the LLM value.
  - A blank review value falls back to the LLM value and is reported.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from scripts.data_prep.check_seg_review_template import (
    DEFAULT_INPUT,
    PHASE_LABELS,
    check_label,
    check_turns,
    compact,
    issue,
    parse_int,
    parse_reviewed_int,
    phrase_indices,
    reviewed_value,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "conversation_seg" / "human_coding_template" / "normalized_seg_coding.csv"
DEFAULT_ISSUES = PROJECT_ROOT / "conversation_seg" / "human_coding_template" / "normalized_seg_coding_issues.csv"


def turns_text(start: int, end: int) -> str:
    return f"T{start}-T{end}"


def sort_issue_key(item: dict[str, str]) -> tuple[int, str, str, str, str]:
    conv_id = item["id"]
    return (
        int(conv_id) if conv_id.isdigit() else sys.maxsize,
        conv_id,
        item["severity"],
        item["check"],
        item["phrase_index"],
    )


def load_rows(path: Path) -> tuple[list[dict[str, str]], list[int]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        indices = phrase_indices(reader.fieldnames)
        if not indices:
            raise ValueError(f"No phrase columns found in {path}")
        rows = [row for row in reader if compact(row.get("id"))]
    return rows, indices


def resolve_phrases(
    row: dict[str, str],
    indices: list[int],
    issues: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], int | None]:
    num_phrases = parse_reviewed_int(
        row,
        "num_phrases",
        "num_phrases_review",
        issues,
        required_review=True,
    )
    if num_phrases is None:
        return [], None

    phrases: list[dict[str, Any]] = []
    for idx in indices:
        if idx > num_phrases:
            if compact(row.get(f"phrase{idx}_turns_review")) or compact(row.get(f"phrase{idx}_label_review")):
                issues.append(issue(
                    row,
                    "warning",
                    "review_beyond_num_phrases",
                    f"phrase{idx}_turns_review/phrase{idx}_label_review",
                    "reviewed phrase exists after resolved num_phrases and was ignored",
                    phrase_index=idx,
                    expected=f"only phrases 1-{num_phrases}",
                ))
            continue

        turns_field = f"phrase{idx}_turns_review"
        label_field = f"phrase{idx}_label_review"
        raw_turns = reviewed_value(
            row,
            f"phrase{idx}_turns",
            turns_field,
            issues,
            phrase_index=idx,
            required_review=True,
        )
        raw_label = reviewed_value(
            row,
            f"phrase{idx}_label",
            label_field,
            issues,
            phrase_index=idx,
            required_review=True,
        )
        parsed_turns = check_turns(row, idx, turns_field, raw_turns, issues)
        label = check_label(row, idx, label_field, raw_label, issues)
        if parsed_turns and label in PHASE_LABELS:
            phrases.append({
                "original_idx": idx,
                "start": parsed_turns[0],
                "end": parsed_turns[1],
                "label": label,
            })
    return phrases, num_phrases


def merge_adjacent_same_label(row: dict[str, str], phrases: list[dict[str, Any]], issues: list[dict[str, str]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for phrase in phrases:
        if not merged:
            merged.append(dict(phrase))
            continue

        previous = merged[-1]
        if previous["label"] != phrase["label"]:
            merged.append(dict(phrase))
            continue

        expected_start = previous["end"] + 2
        if phrase["start"] > expected_start:
            issues.append(issue(
                row,
                "warning",
                "merged_duplicate_label_with_turn_gap",
                f"phrase{phrase['original_idx']}_turns_review",
                "adjacent duplicate labels were merged, but their turn ranges had a gap",
                phrase_index=f"{previous['original_idx']}-{phrase['original_idx']}",
                value=turns_text(phrase["start"], phrase["end"]),
                expected=f"start at T{expected_start}",
            ))
        elif phrase["start"] <= previous["end"]:
            issues.append(issue(
                row,
                "warning",
                "merged_duplicate_label_with_turn_overlap",
                f"phrase{phrase['original_idx']}_turns_review",
                "adjacent duplicate labels were merged, but their turn ranges overlapped",
                phrase_index=f"{previous['original_idx']}-{phrase['original_idx']}",
                value=turns_text(phrase["start"], phrase["end"]),
                expected=f"start at T{expected_start}",
            ))

        previous["end"] = max(previous["end"], phrase["end"])
        previous["original_idx"] = f"{previous['original_idx']};{phrase['original_idx']}"
        issues.append(issue(
            row,
            "info",
            "merged_adjacent_duplicate_label",
            f"phrase{phrase['original_idx']}_label_review",
            "adjacent phrases with the same label were merged",
            phrase_index=previous["original_idx"],
            value=phrase["label"],
        ))
    return merged


def validate_merged(row: dict[str, str], phrases: list[dict[str, Any]], issues: list[dict[str, str]]) -> None:
    n_user_turns = parse_int(row.get("n_user_turns"))
    if n_user_turns is None:
        issues.append(issue(row, "error", "invalid_integer", "n_user_turns", "expected an integer", value=compact(row.get("n_user_turns"))))

    previous: dict[str, Any] | None = None
    for idx, phrase in enumerate(phrases, start=1):
        if previous is None:
            if phrase["start"] != 2:
                issues.append(issue(
                    row,
                    "error",
                    "turn_start_gap_after_merge",
                    f"phrase{idx}_turns",
                    "first normalized phrase should start at the first user turn",
                    value=f"T{phrase['start']}",
                    expected="T2",
                ))
            previous = phrase
            continue

        expected_start = previous["end"] + 2
        if phrase["start"] <= previous["end"]:
            issues.append(issue(
                row,
                "error",
                "turn_overlap_or_reorder_after_merge",
                f"phrase{idx}_turns",
                "normalized phrase starts before or at the previous phrase end",
                phrase_index=idx,
                value=turns_text(phrase["start"], phrase["end"]),
                expected=f"T{expected_start}-...",
            ))
        elif phrase["start"] > expected_start:
            issues.append(issue(
                row,
                "error",
                "turn_gap_after_merge",
                f"phrase{idx}_turns",
                "gap between normalized phrase turn ranges",
                phrase_index=idx,
                value=turns_text(phrase["start"], phrase["end"]),
                expected=f"start at T{expected_start}",
            ))

        if previous["label"] == phrase["label"]:
            issues.append(issue(
                row,
                "error",
                "adjacent_duplicate_label_after_merge",
                f"phrase{idx}_label",
                "adjacent duplicate labels remain after normalization",
                phrase_index=idx,
                value=phrase["label"],
            ))
        previous = phrase

    if phrases and n_user_turns is not None:
        expected_end = n_user_turns * 2
        actual_end = phrases[-1]["end"]
        if actual_end < expected_end:
            issues.append(issue(
                row,
                "error",
                "turn_end_gap_after_merge",
                f"phrase{len(phrases)}_turns",
                "last normalized phrase ends before the final user turn",
                value=f"T{actual_end}",
                expected=f"T{expected_end}",
            ))
        elif actual_end > expected_end:
            issues.append(issue(
                row,
                "error",
                "turn_end_overrun_after_merge",
                f"phrase{len(phrases)}_turns",
                "last normalized phrase ends after the final user turn",
                value=f"T{actual_end}",
                expected=f"T{expected_end}",
            ))


def normalize_row(row: dict[str, str], indices: list[int]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    phrases, original_num_phrases = resolve_phrases(row, indices, issues)
    merged = merge_adjacent_same_label(row, phrases, issues)
    validate_merged(row, merged, issues)

    output_row: dict[str, Any] = {
        "id": compact(row.get("id")),
        "source_pool": compact(row.get("source_pool")),
        "n_user_turns": compact(row.get("n_user_turns")),
        "original_num_phrases": original_num_phrases if original_num_phrases is not None else "",
        "num_phrases": len(merged),
    }
    for idx, phrase in enumerate(merged, start=1):
        output_row[f"phrase{idx}_turns"] = turns_text(phrase["start"], phrase["end"])
        output_row[f"phrase{idx}_label"] = phrase["label"]
    return output_row, issues


def fieldnames(max_phrases: int) -> list[str]:
    names = ["id", "source_pool", "n_user_turns", "original_num_phrases", "num_phrases"]
    for idx in range(1, max_phrases + 1):
        names.extend([f"phrase{idx}_turns", f"phrase{idx}_label"])
    return names


def write_normalized(path: Path, rows: list[dict[str, Any]], max_phrases: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames(max_phrases), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_issues(path: Path, issues: list[dict[str, str]]) -> None:
    fieldnames = ["id", "source_pool", "severity", "check", "field", "phrase_index", "value", "expected", "message"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize a reviewed segmentation template and merge adjacent duplicate labels.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--issues", type=Path, default=DEFAULT_ISSUES)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, indices = load_rows(args.input)
    output_rows: list[dict[str, Any]] = []
    all_issues: list[dict[str, str]] = []

    for row in rows:
        output_row, issues = normalize_row(row, indices)
        output_rows.append(output_row)
        all_issues.extend(issues)

    max_phrases = max((int(row["num_phrases"]) for row in output_rows), default=0)
    all_issues.sort(key=sort_issue_key)
    write_normalized(args.output, output_rows, max_phrases)
    write_issues(args.issues, all_issues)

    print(f"Read {len(rows)} conversations from {args.input}")
    print(f"Wrote normalized coding to {args.output}")
    print(f"Wrote {len(all_issues)} issues to {args.issues}")
    for severity in ["error", "warning", "info"]:
        count = sum(1 for item in all_issues if item["severity"] == severity)
        print(f"{severity}s: {count}")


if __name__ == "__main__":
    main()
