"""
compare_agreement_reports.py
============================
Compare two evaluation agreement_report.md files and summarize metric changes.

Example:
  python -m scripts.compare_agreement_reports \
      --old evaluation/minimax_sample_0/agreement_report.md \
      --new evaluation/minimax_sample_1/agreement_report.md \
      --out evaluation/minimax_sample_comparison.md
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def clean_cell(cell: str) -> str:
    return cell.strip().strip("*").strip()


def parse_float(cell: str) -> float | None:
    cell = clean_cell(cell)
    if not cell:
        return None
    try:
        return float(cell)
    except ValueError:
        return None


def parse_int(cell: str) -> int | None:
    cell = clean_cell(cell)
    if not cell:
        return None
    try:
        return int(cell)
    except ValueError:
        return None


def parse_markdown_row(line: str) -> list[str]:
    return [clean_cell(part) for part in line.strip().strip("|").split("|")]


def is_separator_row(line: str) -> bool:
    cells = parse_markdown_row(line)
    return bool(cells) and all(set(cell) <= {"-", ":"} for cell in cells)


def parse_eval_set(text: str) -> int | None:
    match = re.search(r"Eval set:\s+\*\*(\d+)\s+conversations\*\*", text)
    return int(match.group(1)) if match else None


def parse_tables(text: str) -> dict[str, dict]:
    """Parse the specific tables produced by scripts/evaluate.py."""
    lines = text.splitlines()
    parsed: dict[str, dict] = {
        "kappa": {},
        "attack_vector": {},
        "severity_counts": {},
        "horizontal_multi": {},
        "horizontal_single": {},
    }

    current_heading = ""
    current_subheading = ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## "):
            current_heading = line[3:].strip()
            current_subheading = ""
        elif line.startswith("### "):
            current_subheading = line[4:].strip()

        if line.startswith("|") and i + 1 < len(lines) and is_separator_row(lines[i + 1]):
            header = parse_markdown_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(parse_markdown_row(lines[i]))
                i += 1

            if header[:2] == ["Coder", "n"]:
                for row in rows:
                    if row and row[0] == "Pooled":
                        metrics = dict(zip(header[1:], row[1:]))
                        parsed["kappa"] = {
                            "n": parse_int(metrics.get("n", "")),
                            "Vector (macro)": parse_float(metrics.get("Vector (macro)", "")),
                            "Type (macro)": parse_float(metrics.get("Type (macro)", "")),
                            "Attempt (macro)": parse_float(metrics.get("Attempt (macro)", "")),
                            "Conversational": parse_float(metrics.get("Conversational", "")),
                            "Success": parse_float(metrics.get("Success", "")),
                            "Severity": parse_float(metrics.get("Severity", "")),
                        }
            elif current_subheading == "Attack Vector" and header[:2] == ["Label", "kappa"]:
                for row in rows:
                    if len(row) >= 4:
                        parsed["attack_vector"][row[0]] = {
                            "kappa": parse_float(row[1]),
                            "LLM positives": parse_int(row[2]),
                            "Human positives": parse_int(row[3]),
                        }
            elif current_subheading == "Severity" and header[:2] == ["Label", "LLM positives"]:
                for row in rows:
                    if len(row) >= 3:
                        parsed["severity_counts"][row[0]] = {
                            "LLM positives": parse_int(row[1]),
                            "Human positives": parse_int(row[2]),
                        }
            elif current_subheading == "Multi-label dimensions" and header[:2] == ["Dimension", "Hit Rate"]:
                for row in rows:
                    if len(row) >= 7:
                        parsed["horizontal_multi"][row[0]] = {
                            "Hit Rate": parse_float(row[1]),
                            "Exact Match": parse_float(row[2]),
                            "Mean Jaccard": parse_float(row[3]),
                            "Mean Precision": parse_float(row[4]),
                            "Mean Recall": parse_float(row[5]),
                            "Mean F1": parse_float(row[6]),
                        }
            elif current_subheading == "Single-label dimensions" and header[:2] == ["Dimension", "Hit Rate"]:
                for row in rows:
                    if len(row) >= 2:
                        parsed["horizontal_single"][row[0]] = {"Hit Rate": parse_float(row[1])}
            continue

        i += 1

    parsed["eval_set"] = parse_eval_set(text)
    return parsed


def fmt(value: float | int | None, digits: int = 3) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def fmt_delta(old: float | int | None, new: float | int | None, digits: int = 3) -> str:
    if old is None or new is None:
        return ""
    delta = new - old
    sign = "+" if delta > 0 else ""
    if isinstance(old, int) and isinstance(new, int):
        return f"{sign}{delta}"
    return f"{sign}{delta:.{digits}f}"


def metric_table(title: str, rows: list[tuple[str, float | int | None, float | int | None]]) -> list[str]:
    out = [f"## {title}", "", "| Metric | Old | New | Delta |", "|---|---:|---:|---:|"]
    for name, old, new in rows:
        out.append(f"| {name} | {fmt(old)} | {fmt(new)} | {fmt_delta(old, new)} |")
    out.append("")
    return out


def compare_reports(old_path: Path, new_path: Path) -> str:
    old = parse_tables(old_path.read_text(encoding="utf-8"))
    new = parse_tables(new_path.read_text(encoding="utf-8"))

    lines = [
        "# Agreement Report Comparison",
        "",
        f"- Old report: `{old_path}`",
        f"- New report: `{new_path}`",
        f"- Eval set: {old.get('eval_set')} -> {new.get('eval_set')} ({fmt_delta(old.get('eval_set'), new.get('eval_set'), 0)})",
        "",
        "> Positive deltas mean the new report improved on that metric. Check eval-set changes before interpreting differences.",
        "",
    ]

    kappa_names = ["Vector (macro)", "Type (macro)", "Attempt (macro)", "Conversational", "Success", "Severity"]
    lines.extend(metric_table("Cohen's Kappa", [(name, old["kappa"].get(name), new["kappa"].get(name)) for name in kappa_names]))

    vector_labels = sorted(set(old["attack_vector"]) | set(new["attack_vector"]))
    lines.extend(["## Attack Vector Per-label Kappa", "", "| Label | Old kappa | New kappa | Delta | Old LLM+ | New LLM+ | Human+ old->new |", "|---|---:|---:|---:|---:|---:|---:|"])
    for label in vector_labels:
        old_rec = old["attack_vector"].get(label, {})
        new_rec = new["attack_vector"].get(label, {})
        human_old = old_rec.get("Human positives")
        human_new = new_rec.get("Human positives")
        lines.append(
            f"| {label} | {fmt(old_rec.get('kappa'))} | {fmt(new_rec.get('kappa'))} | "
            f"{fmt_delta(old_rec.get('kappa'), new_rec.get('kappa'))} | "
            f"{fmt(old_rec.get('LLM positives'))} | {fmt(new_rec.get('LLM positives'))} | "
            f"{fmt(human_old)}->{fmt(human_new)} |"
        )
    lines.append("")

    horizontal_rows = []
    for dim in ["Vector", "Type", "Attempt"]:
        for metric in ["Hit Rate", "Exact Match", "Mean Jaccard", "Mean Precision", "Mean Recall", "Mean F1"]:
            horizontal_rows.append((f"{dim} {metric}", old["horizontal_multi"].get(dim, {}).get(metric), new["horizontal_multi"].get(dim, {}).get(metric)))
    lines.extend(metric_table("Horizontal Multi-label Agreement", horizontal_rows))

    single_rows = []
    for dim in ["Conversational", "Success", "Severity"]:
        single_rows.append((f"{dim} Hit Rate", old["horizontal_single"].get(dim, {}).get("Hit Rate"), new["horizontal_single"].get(dim, {}).get("Hit Rate")))
    lines.extend(metric_table("Horizontal Single-label Agreement", single_rows))

    severity_labels = sorted(set(old["severity_counts"]) | set(new["severity_counts"]))
    lines.extend(["## Severity Label Counts", "", "| Label | Old LLM+ | New LLM+ | Delta LLM+ | Human+ old->new |", "|---|---:|---:|---:|---:|"])
    for label in severity_labels:
        old_rec = old["severity_counts"].get(label, {})
        new_rec = new["severity_counts"].get(label, {})
        lines.append(
            f"| {label} | {fmt(old_rec.get('LLM positives'))} | {fmt(new_rec.get('LLM positives'))} | "
            f"{fmt_delta(old_rec.get('LLM positives'), new_rec.get('LLM positives'))} | "
            f"{fmt(old_rec.get('Human positives'))}->{fmt(new_rec.get('Human positives'))} |"
        )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", required=True, type=Path, help="Path to the old agreement_report.md")
    parser.add_argument("--new", required=True, type=Path, help="Path to the new agreement_report.md")
    parser.add_argument("--out", type=Path, help="Optional output markdown path")
    args = parser.parse_args()

    text = compare_reports(args.old, args.new)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
