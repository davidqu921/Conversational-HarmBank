"""
Check a reviewed LLM segmentation template and write a CSV issue report.

Review semantics:
  - V/v/check/ok means keep the LLM value.
  - A non-empty review value replaces the LLM value.
  - A blank review value is reported as missing_review, but the LLM value is
    still used as a temporary fallback so structural checks can continue.

Defaults:
  input:  conversation_seg/human_coding_template/VirtualSteve Coding - Round 3 - seg_review_template .csv
  output: conversation_seg/human_coding_template/seg_review_template_normalization_issues.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "conversation_seg"
    / "human_coding_template"
    / "VirtualSteve Coding - Round 3 - seg_review_template .csv"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "conversation_seg" / "human_coding_template" / "seg_review_template_normalization_issues.csv"

PHASE_LABELS = [
    "Setup",
    "Trust Building",
    "Attack Construction",
    "Escalation",
    "Goal Execution",
]
LABEL_ALIASES = {
    "setup": "Setup",
    "trust building": "Trust Building",
    "trust-building": "Trust Building",
    "attack construction": "Attack Construction",
    "escalation": "Escalation",
    "goal execution": "Goal Execution",
    "reconnaissance": "Goal Execution",
}
AGREE_VALUES = {"v", "check", "checked", "ok", "okay", "yes", "y", "correct"}
TURN_RE = re.compile(r"^T?\s*(\d+)\s*[-–]\s*T?\s*(\d+)$", re.IGNORECASE)


def compact(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def key(value: str | None) -> str:
    return compact(value).lower()


def is_agree(value: str | None) -> bool:
    return key(value) in AGREE_VALUES


def phrase_indices(fieldnames: list[str] | None) -> list[int]:
    if not fieldnames:
        return []
    indices: set[int] = set()
    for field in fieldnames:
        match = re.fullmatch(r"phrase(\d+)_(?:turns|turns_review|label|label_review)", field)
        if match:
            indices.add(int(match.group(1)))
    return sorted(indices)


def issue(
    row: dict[str, str],
    severity: str,
    check: str,
    field: str,
    message: str,
    *,
    phrase_index: int | str = "",
    value: str = "",
    expected: str = "",
) -> dict[str, str]:
    return {
        "id": compact(row.get("id")),
        "source_pool": compact(row.get("source_pool")),
        "severity": severity,
        "check": check,
        "field": field,
        "phrase_index": str(phrase_index),
        "value": value,
        "expected": expected,
        "message": message,
    }


def parse_int(value: str | None) -> int | None:
    text = compact(value)
    if not text:
        return None
    return int(text) if text.isdigit() else None


def parse_reviewed_int(
    row: dict[str, str],
    base_field: str,
    review_field: str,
    issues: list[dict[str, str]],
    *,
    required_review: bool,
) -> int | None:
    base = compact(row.get(base_field))
    review = compact(row.get(review_field))
    raw = base if is_agree(review) or not review else review

    if required_review and not review:
        issues.append(issue(row, "error", "missing_review", review_field, "review value is blank", value=review))

    parsed = parse_int(raw)
    if parsed is None:
        issues.append(issue(row, "error", "invalid_integer", review_field, "expected an integer", value=raw))
    return parsed


def parse_turn_range(value: str) -> tuple[int, int] | None:
    text = compact(value)
    match = TURN_RE.fullmatch(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def reviewed_value(
    row: dict[str, str],
    base_field: str,
    review_field: str,
    issues: list[dict[str, str]],
    *,
    phrase_index: int,
    required_review: bool,
) -> str:
    base = compact(row.get(base_field))
    review = compact(row.get(review_field))
    if required_review and not review:
        issues.append(issue(
            row,
            "error",
            "missing_review",
            review_field,
            "review value is blank",
            phrase_index=phrase_index,
            value=review,
        ))
    if is_agree(review) or not review:
        return base
    return review


def normalize_label(label: str) -> str | None:
    return LABEL_ALIASES.get(key(label))


def check_label(
    row: dict[str, str],
    phrase_index: int,
    field: str,
    raw_label: str,
    issues: list[dict[str, str]],
) -> str:
    if not raw_label:
        issues.append(issue(
            row,
            "error",
            "missing_label",
            field,
            "resolved phrase label is blank",
            phrase_index=phrase_index,
            expected="; ".join(PHASE_LABELS),
        ))
        return ""

    normalized = normalize_label(raw_label)
    if normalized is None:
        issues.append(issue(
            row,
            "error",
            "invalid_label",
            field,
            "label is not one of the active phase labels",
            phrase_index=phrase_index,
            value=raw_label,
            expected="; ".join(PHASE_LABELS),
        ))
        return raw_label

    if compact(raw_label) != normalized:
        issues.append(issue(
            row,
            "warning",
            "label_normalized",
            field,
            "label can be normalized but should be written in canonical form",
            phrase_index=phrase_index,
            value=raw_label,
            expected=normalized,
        ))
    return normalized


def check_turns(
    row: dict[str, str],
    phrase_index: int,
    field: str,
    raw_turns: str,
    issues: list[dict[str, str]],
) -> tuple[int, int] | None:
    if not raw_turns:
        issues.append(issue(row, "error", "missing_turns", field, "resolved phrase turns are blank", phrase_index=phrase_index))
        return None

    parsed = parse_turn_range(raw_turns)
    if parsed is None:
        issues.append(issue(
            row,
            "error",
            "invalid_turn_range",
            field,
            "turn range should look like T2-T6",
            phrase_index=phrase_index,
            value=raw_turns,
        ))
        return None

    start, end = parsed
    if start > end:
        issues.append(issue(
            row,
            "error",
            "turn_range_reversed",
            field,
            "turn range start is greater than end",
            phrase_index=phrase_index,
            value=raw_turns,
        ))
    if start % 2 or end % 2:
        issues.append(issue(
            row,
            "warning",
            "odd_turn_number",
            field,
            "user turns are expected to use even transcript turn numbers",
            phrase_index=phrase_index,
            value=raw_turns,
        ))
    return start, end


def has_any_review_or_base(row: dict[str, str], idx: int) -> bool:
    fields = [
        f"phrase{idx}_turns",
        f"phrase{idx}_turns_review",
        f"phrase{idx}_label",
        f"phrase{idx}_label_review",
    ]
    return any(compact(row.get(field)) for field in fields)


def check_row(row: dict[str, str], indices: list[int]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    n_user_turns = parse_int(row.get("n_user_turns"))
    if n_user_turns is None:
        issues.append(issue(row, "error", "invalid_integer", "n_user_turns", "expected an integer", value=compact(row.get("n_user_turns"))))

    num_phrases = parse_reviewed_int(
        row,
        "num_phrases",
        "num_phrases_review",
        issues,
        required_review=True,
    )
    if num_phrases is None:
        return issues

    if num_phrases < 1:
        issues.append(issue(row, "error", "invalid_num_phrases", "num_phrases_review", "num_phrases must be at least 1", value=str(num_phrases)))

    effective_phrases: list[dict[str, Any]] = []
    for idx in indices:
        if idx > num_phrases:
            if compact(row.get(f"phrase{idx}_turns_review")) or compact(row.get(f"phrase{idx}_label_review")):
                issues.append(issue(
                    row,
                    "warning",
                    "review_beyond_num_phrases",
                    f"phrase{idx}_turns_review/phrase{idx}_label_review",
                    "reviewed phrase exists after resolved num_phrases and will be ignored",
                    phrase_index=idx,
                    expected=f"only phrases 1-{num_phrases}",
                ))
            continue

        turns_field = f"phrase{idx}_turns_review"
        label_field = f"phrase{idx}_label_review"
        turns = reviewed_value(
            row,
            f"phrase{idx}_turns",
            turns_field,
            issues,
            phrase_index=idx,
            required_review=True,
        )
        label = reviewed_value(
            row,
            f"phrase{idx}_label",
            label_field,
            issues,
            phrase_index=idx,
            required_review=True,
        )
        parsed_turns = check_turns(row, idx, turns_field, turns, issues)
        normalized_label = check_label(row, idx, label_field, label, issues)
        effective_phrases.append({
            "idx": idx,
            "turns": parsed_turns,
            "label": normalized_label,
            "raw_turns": turns,
            "raw_label": label,
        })

    actual_nonempty_count = sum(1 for idx in indices if idx <= num_phrases and has_any_review_or_base(row, idx))
    if actual_nonempty_count != num_phrases:
        issues.append(issue(
            row,
            "error",
            "num_phrases_mismatch",
            "num_phrases_review",
            "resolved num_phrases does not match the number of populated phrase slots",
            value=str(num_phrases),
            expected=str(actual_nonempty_count),
        ))

    previous: dict[str, Any] | None = None
    for current in effective_phrases:
        if previous is None:
            previous = current
            continue

        if previous["label"] and current["label"] and previous["label"] == current["label"]:
            issues.append(issue(
                row,
                "warning",
                "adjacent_duplicate_label",
                f"phrase{previous['idx']}_label_review/phrase{current['idx']}_label_review",
                "adjacent phrases have the same resolved label and may need to be merged",
                phrase_index=f"{previous['idx']}-{current['idx']}",
                value=current["label"],
            ))

        prev_turns = previous["turns"]
        cur_turns = current["turns"]
        if prev_turns and cur_turns:
            prev_start, prev_end = prev_turns
            cur_start, cur_end = cur_turns
            expected_start = prev_end + 2
            if cur_start <= prev_end:
                issues.append(issue(
                    row,
                    "error",
                    "turn_overlap_or_reorder",
                    f"phrase{current['idx']}_turns_review",
                    "current phrase starts before or at the previous phrase end",
                    phrase_index=current["idx"],
                    value=current["raw_turns"],
                    expected=f"T{expected_start}-...",
                ))
            elif cur_start > expected_start:
                issues.append(issue(
                    row,
                    "error",
                    "turn_gap",
                    f"phrase{current['idx']}_turns_review",
                    "gap between adjacent phrase turn ranges",
                    phrase_index=current["idx"],
                    value=current["raw_turns"],
                    expected=f"start at T{expected_start}",
                ))
        previous = current

    valid_turns = [phrase["turns"] for phrase in effective_phrases if phrase["turns"]]
    if valid_turns:
        first_start = valid_turns[0][0]
        last_end = valid_turns[-1][1]
        if first_start != 2:
            issues.append(issue(
                row,
                "error",
                "turn_start_gap",
                "phrase1_turns_review",
                "first phrase should start at the first user turn",
                value=f"T{first_start}",
                expected="T2",
            ))
        if n_user_turns is not None:
            expected_last_end = n_user_turns * 2
            if last_end < expected_last_end:
                issues.append(issue(
                    row,
                    "error",
                    "turn_end_gap",
                    f"phrase{num_phrases}_turns_review",
                    "last phrase ends before the final user turn",
                    value=f"T{last_end}",
                    expected=f"T{expected_last_end}",
                ))
            elif last_end > expected_last_end:
                issues.append(issue(
                    row,
                    "error",
                    "turn_end_overrun",
                    f"phrase{num_phrases}_turns_review",
                    "last phrase ends after the final user turn",
                    value=f"T{last_end}",
                    expected=f"T{expected_last_end}",
                ))

    return issues


def write_issues(path: Path, issues: list[dict[str, str]]) -> None:
    fieldnames = ["id", "source_pool", "severity", "check", "field", "phrase_index", "value", "expected", "message"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a reviewed segmentation template and write CSV issues.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    all_issues: list[dict[str, str]] = []
    with args.input.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        indices = phrase_indices(reader.fieldnames)
        if not indices:
            raise SystemExit(f"No phrase columns found in {args.input}")
        rows = [row for row in reader if compact(row.get("id"))]

    for row in rows:
        all_issues.extend(check_row(row, indices))

    all_issues.sort(key=lambda item: (
        int(item["id"]) if item["id"].isdigit() else sys.maxsize,
        item["id"],
        item["severity"],
        item["check"],
        item["phrase_index"],
    ))
    write_issues(args.output, all_issues)

    errors = sum(1 for item in all_issues if item["severity"] == "error")
    warnings = sum(1 for item in all_issues if item["severity"] == "warning")
    print(f"Read {len(rows)} conversations from {args.input}")
    print(f"Wrote {len(all_issues)} issues to {args.output}")
    print(f"errors: {errors}")
    print(f"warnings: {warnings}")


if __name__ == "__main__":
    main()
