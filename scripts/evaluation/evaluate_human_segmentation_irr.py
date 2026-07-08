"""
Evaluate human-human IRR for phrase-level segmentation labels.

Defaults:
  input dir: conversation_seg/human_coding_results
  optional LLM dir: conversation_seg/results
  output dir: conversation_seg/human_coding_results/evaluation_first15
  max conversations per coder: 15
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "conversation_seg" / "human_coding_results"
DEFAULT_LLM_RESULTS_DIR = PROJECT_ROOT / "conversation_seg" / "results"
DEFAULT_OUT_DIR = DEFAULT_INPUT_DIR / "evaluation_first15"
PHASE_LABELS = [
    "Setup",
    "Trust Building",
    "Attack Construction",
    "Escalation",
    "Goal Execution",
]


def coder_name(path: Path) -> str:
    stem = path.stem
    if " - " in stem:
        return stem.split(" - ")[-1].strip()
    return stem


def normalize_label(label: str | None) -> str:
    if not label:
        return ""
    label = " ".join(str(label).strip().split())
    aliases = {
        "trust-building": "Trust Building",
        "attack construction": "Attack Construction",
        "goal execution": "Goal Execution",
        "reconnaissance": "Goal Execution",
    }
    return aliases.get(label.lower(), label)


def phrase_indices(fieldnames: list[str] | None) -> list[int]:
    if not fieldnames:
        return []
    indices: list[int] = []
    for field in fieldnames:
        if field.startswith("phrase") and field.endswith("_label"):
            raw = field[len("phrase"):-len("_label")]
            if raw.isdigit():
                indices.append(int(raw))
    return sorted(indices)


def load_coder_file(path: Path, max_conversations: int | None) -> dict[tuple[str, int, str], str]:
    labels: dict[tuple[str, int, str], str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        indices = phrase_indices(reader.fieldnames)
        loaded_conversations = 0
        for row in reader:
            if not row.get("id"):
                continue
            if max_conversations is not None and loaded_conversations >= max_conversations:
                break
            loaded_conversations += 1
            conv_id = row["id"].strip()
            for idx in indices:
                turns = (row.get(f"phrase{idx}_turns") or "").strip()
                label = normalize_label(row.get(f"phrase{idx}_label"))
                if not turns or turns.upper() == "NA":
                    continue
                if not label or label.upper() == "NA":
                    continue
                labels[(conv_id, idx, turns)] = label
    return labels


def phase_turns(row: dict[str, str]) -> str:
    return f"T{row['start_turn'].strip()}-T{row['end_turn'].strip()}"


def load_llm_phase_segments(
    results_dir: Path,
    reference_units: list[tuple[str, int, str]],
    max_conversations: int | None,
) -> dict[tuple[str, int, str], str]:
    wanted_ids: list[str] = []
    for conv_id, _, _ in reference_units:
        if conv_id not in wanted_ids:
            wanted_ids.append(conv_id)
        if max_conversations is not None and len(wanted_ids) >= max_conversations:
            break
    wanted_id_set = set(wanted_ids)

    by_id: dict[str, list[dict[str, str]]] = {}
    for path in sorted(results_dir.glob("*/phase_segments.csv")):
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                conv_id = row.get("id", "").strip()
                if conv_id in wanted_id_set:
                    by_id.setdefault(conv_id, []).append(row)

    labels: dict[tuple[str, int, str], str] = {}
    for conv_id in wanted_ids:
        rows = sorted(by_id.get(conv_id, []), key=lambda row: int(row["start_turn"]))
        for idx, row in enumerate(rows, start=1):
            label = normalize_label(row.get("phase"))
            if not label:
                continue
            labels[(conv_id, idx, phase_turns(row))] = label
    return labels


def cohen_kappa(a: list[str], b: list[str]) -> float:
    if len(a) != len(b) or not a:
        return math.nan
    labels = sorted(set(a) | set(b))
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    ca = Counter(a)
    cb = Counter(b)
    expected = sum((ca[label] / n) * (cb[label] / n) for label in labels)
    if expected >= 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def hit_rate(a: list[str], b: list[str]) -> float:
    return sum(1 for x, y in zip(a, b) if x == y) / len(a) if a else math.nan


def fleiss_kappa(rows: list[list[str]], labels: list[str]) -> float:
    if not rows:
        return math.nan
    n_raters = len(rows[0])
    if n_raters <= 1:
        return math.nan
    n_items = len(rows)

    label_counts = Counter(label for row in rows for label in row)
    p = {label: label_counts[label] / (n_items * n_raters) for label in labels}

    p_i = []
    for row in rows:
        counts = Counter(row)
        p_i.append(
            sum(count * count for count in counts.values()) - n_raters
        )
    p_bar = sum(value / (n_raters * (n_raters - 1)) for value in p_i) / n_items
    p_e = sum(value * value for value in p.values())
    if p_e >= 1:
        return 1.0
    return (p_bar - p_e) / (1 - p_e)


def fmt(value: float) -> str:
    return "NA" if value != value else f"{value:.3f}"


def common_units(coder_labels: dict[str, dict[tuple[str, int, str], str]]) -> list[tuple[str, int, str]]:
    units: set[tuple[str, int, str]] | None = None
    for labels in coder_labels.values():
        if units is None:
            units = set(labels)
        else:
            units &= set(labels)
    if not units:
        return []
    return sorted(units, key=lambda key: (int(key[0]) if key[0].isdigit() else math.inf, key[0], key[1]))


def write_disagreements(
    path: Path,
    units: list[tuple[str, int, str]],
    coder_labels: dict[str, dict[tuple[str, int, str], str]],
) -> None:
    coders = list(coder_labels)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "phrase_index", "turns", "num_unique_labels", "labels"] + coders,
        )
        writer.writeheader()
        for unit in units:
            labels = {coder: coder_labels[coder][unit] for coder in coders}
            unique = sorted(set(labels.values()))
            if len(unique) <= 1:
                continue
            writer.writerow({
                "id": unit[0],
                "phrase_index": unit[1],
                "turns": unit[2],
                "num_unique_labels": len(unique),
                "labels": "; ".join(unique),
                **labels,
            })


def build_report(
    coder_labels: dict[str, dict[tuple[str, int, str], str]],
    units: list[tuple[str, int, str]],
    max_conversations: int | None,
    llm_results_dir: Path | None,
) -> str:
    coders = list(coder_labels)
    matrix = [[coder_labels[coder][unit] for coder in coders] for unit in units]
    labels = sorted(set(PHASE_LABELS) | {label for row in matrix for label in row})
    pair_rows: list[tuple[str, str, int, float, float]] = []
    for a, b in combinations(coders, 2):
        usable = [unit for unit in units if unit in coder_labels[a] and unit in coder_labels[b]]
        a_values = [coder_labels[a][unit] for unit in usable]
        b_values = [coder_labels[b][unit] for unit in usable]
        pair_rows.append((a, b, len(usable), cohen_kappa(a_values, b_values), hit_rate(a_values, b_values)))

    kappas = [row[3] for row in pair_rows if row[3] == row[3]]
    hits = [row[4] for row in pair_rows if row[4] == row[4]]
    all_agree = sum(1 for row in matrix if len(set(row)) == 1)

    report = [
        "# Human Segmentation IRR Report",
        "",
        f"- Coders: **{', '.join(coders)}**",
        f"- Max conversations per coder: **{max_conversations if max_conversations is not None else 'all'}**",
        f"- LLM results dir: **{llm_results_dir if llm_results_dir else 'not included'}**",
        f"- Common phrase units compared: **{len(units)}**",
        f"- All-coder exact agreement: **{fmt(all_agree / len(units) if units else math.nan)}**",
        f"- Mean pairwise Cohen's kappa: **{fmt(sum(kappas) / len(kappas) if kappas else math.nan)}**",
        f"- Mean pairwise hit rate: **{fmt(sum(hits) / len(hits) if hits else math.nan)}**",
        f"- Fleiss' kappa: **{fmt(fleiss_kappa(matrix, labels))}**",
        "",
        "## Pairwise Agreement",
        "",
        "| Coder A | Coder B | Units | Cohen's kappa | Hit rate |",
        "|---|---|---:|---:|---:|",
    ]
    for a, b, n, kappa, hit in pair_rows:
        report.append(f"| {a} | {b} | {n} | {fmt(kappa)} | {fmt(hit)} |")

    report.extend([
        "",
        "## Label Distribution",
        "",
        "| Coder | " + " | ".join(labels) + " |",
        "|---|" + "---:|" * len(labels),
    ])
    for coder in coders:
        counts = Counter(coder_labels[coder][unit] for unit in units)
        report.append("| " + coder + " | " + " | ".join(str(counts[label]) for label in labels) + " |")
    return "\n".join(report)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate phrase-level human segmentation IRR.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--llm-results-dir", type=Path, default=None, help="Optional segmentation results dir containing */phase_segments.csv.")
    parser.add_argument("--include-default-llm", action="store_true", help=f"Include default LLM results from {DEFAULT_LLM_RESULTS_DIR}.")
    parser.add_argument("--llm-name", default="LLM")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--max-conversations", type=int, default=15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = sorted(args.input_dir.glob("*.csv"))
    if not paths:
        raise SystemExit(f"no CSV files found in {args.input_dir}")

    coder_labels = {coder_name(path): load_coder_file(path, args.max_conversations) for path in paths}
    human_units = common_units(coder_labels)
    llm_results_dir = args.llm_results_dir or (DEFAULT_LLM_RESULTS_DIR if args.include_default_llm else None)
    if llm_results_dir is not None:
        coder_labels[args.llm_name] = load_llm_phase_segments(llm_results_dir, human_units, args.max_conversations)

    units = common_units(coder_labels)
    if not units:
        raise SystemExit("no common phrase units found across coders")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(coder_labels, units, args.max_conversations, llm_results_dir)
    report_path = args.out_dir / "human_segmentation_irr_report.md"
    disagreements_path = args.out_dir / "human_segmentation_disagreements.csv"
    report_path.write_text(report, encoding="utf-8")
    write_disagreements(disagreements_path, units, coder_labels)

    print(f"Wrote {report_path}")
    print(f"Wrote {disagreements_path}")


if __name__ == "__main__":
    main()
