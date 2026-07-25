"""Aggregate reviewed CAA trajectory and weak-attack evaluation summaries.

The expected input layout is::

    CAA/outputs/<experiment>/evaluation/reviewed_severity_llama31/summary.json
    CAA/outputs/<experiment>/weak_attack_evaluation/reviewed_severity_llama31/summary.json

Experiments are discovered from ``round5_balanced_<N>_llama31_*`` directories.
Counts are pooled across the requested run sizes and all rates are recomputed
from the pooled numerator and denominator; rates are never averaged directly.
No attempt is made to deduplicate trials across experiment directories.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "CAA" / "outputs"
DEFAULT_REPORT = DEFAULT_OUTPUTS_DIR / "reviewed_evaluation_summary.md"

EXPERIMENT_RE = re.compile(
    r"^round5_balanced_(?P<size>\d+)_llama31_(?P<model>.+?)"
    r"_stronger(?:_v\d+_topic_conditional)?$"
)

SUMMARY_PATHS = {
    "trajectory": Path("evaluation/reviewed_severity_llama31/summary.json"),
    "weak": Path("weak_attack_evaluation/reviewed_severity_llama31/summary.json"),
}

ATTACK_TITLES = {
    "trajectory": "Trajectory attack",
    "weak": "Weak attack",
}

SEVERITY_ORDER = (
    "0 - Safe",
    "1 - Minor",
    "2 - Major",
    "3 - Severe",
)


@dataclass(frozen=True)
class ReviewedSummary:
    experiment_dir: Path
    run_size: int
    model_key: str
    response_model: str
    attack_kind: str
    path: Path
    data: dict[str, Any]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def response_model_from_conversation(experiment_dir: Path, fallback: str) -> str:
    conversation_dir = experiment_dir / "conversations"
    for path in sorted(conversation_dir.glob("caa_*.json")):
        try:
            row = load_json(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        model_id = str((row.get("models") or {}).get("response", "")).strip()
        if model_id:
            return model_id
    return fallback


def require_int(data: dict[str, Any], field: str, path: Path) -> int:
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path}: {field} must be an integer, got {value!r}")
    if value < 0:
        raise ValueError(f"{path}: {field} must be nonnegative")
    return value


def validate_summary(data: dict[str, Any], path: Path) -> None:
    n_records = require_int(data, "n_records", path)
    n_coded = require_int(data, "n_coded", path)
    n_errors = require_int(data, "n_errors", path)
    n_success = require_int(data, "n_success", path)
    if n_coded > n_records:
        raise ValueError(f"{path}: n_coded exceeds n_records")
    if n_success > n_coded:
        raise ValueError(f"{path}: n_success exceeds n_coded")
    if n_errors > n_records:
        raise ValueError(f"{path}: n_errors exceeds n_records")

    severity_counts = data.get("severity_counts")
    if not isinstance(severity_counts, dict):
        raise ValueError(f"{path}: severity_counts must be an object")
    if sum(int(value) for value in severity_counts.values()) != n_coded:
        raise ValueError(f"{path}: severity_counts do not sum to n_coded")

    for field in ("by_attempt", "by_source_primary_attack_vector"):
        groups = data.get(field)
        if not isinstance(groups, dict):
            raise ValueError(f"{path}: {field} must be an object")
        group_total = 0
        for label, group in groups.items():
            if not isinstance(group, dict):
                raise ValueError(f"{path}: {field}[{label!r}] must be an object")
            group_n = require_int(group, "n", path)
            group_successes = require_int(group, "successes", path)
            if group_successes > group_n:
                raise ValueError(f"{path}: {field}[{label!r}] successes exceed n")
            group_total += group_n
        if group_total != n_coded:
            raise ValueError(f"{path}: {field} counts do not sum to n_coded")


def discover_summaries(
    outputs_dir: Path,
    sizes: set[int],
) -> tuple[list[ReviewedSummary], list[str]]:
    summaries: list[ReviewedSummary] = []
    missing: list[str] = []

    for experiment_dir in sorted(path for path in outputs_dir.iterdir() if path.is_dir()):
        match = EXPERIMENT_RE.match(experiment_dir.name)
        if not match:
            continue
        run_size = int(match.group("size"))
        if run_size not in sizes:
            continue
        model_key = match.group("model")
        response_model = response_model_from_conversation(experiment_dir, model_key)

        for attack_kind, relative_path in SUMMARY_PATHS.items():
            summary_path = experiment_dir / relative_path
            if not summary_path.is_file():
                missing.append(
                    f"{experiment_dir.name}: missing {relative_path.as_posix()}"
                )
                continue
            data = load_json(summary_path)
            validate_summary(data, summary_path)
            summaries.append(
                ReviewedSummary(
                    experiment_dir=experiment_dir,
                    run_size=run_size,
                    model_key=model_key,
                    response_model=response_model,
                    attack_kind=attack_kind,
                    path=summary_path,
                    data=data,
                )
            )
    return summaries, missing


def empty_aggregate() -> dict[str, Any]:
    return {
        "n_records": 0,
        "n_coded": 0,
        "n_errors": 0,
        "n_success": 0,
        "severity_counts": Counter(),
        "by_attempt": defaultdict(lambda: {"n": 0, "successes": 0, "severity_counts": Counter()}),
        "by_source_primary_attack_vector": defaultdict(
            lambda: {"n": 0, "successes": 0, "severity_counts": Counter()}
        ),
    }


def aggregate_summaries(rows: Iterable[ReviewedSummary]) -> dict[str, Any]:
    aggregate = empty_aggregate()
    for row in rows:
        data = row.data
        for field in ("n_records", "n_coded", "n_errors", "n_success"):
            aggregate[field] += int(data[field])
        aggregate["severity_counts"].update(
            {label: int(count) for label, count in data["severity_counts"].items()}
        )
        for field in ("by_attempt", "by_source_primary_attack_vector"):
            for label, group in data[field].items():
                target = aggregate[field][label]
                target["n"] += int(group["n"])
                target["successes"] += int(group["successes"])
                target["severity_counts"].update(
                    {
                        severity: int(count)
                        for severity, count in (group.get("severity_counts") or {}).items()
                    }
                )
    return aggregate


def rate(successes: int, denominator: int) -> float:
    return successes / denominator if denominator else 0.0


def pct(value: float) -> str:
    return f"{value:.2%}"


def escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def severity_text(counts: dict[str, int] | Counter) -> str:
    known = [f"{label}: {int(counts.get(label, 0))}" for label in SEVERITY_ORDER]
    extras = sorted(set(counts) - set(SEVERITY_ORDER))
    known.extend(f"{label}: {int(counts[label])}" for label in extras)
    return "; ".join(known)


def overall_table(rows: list[ReviewedSummary], pooled: dict[str, Any]) -> list[str]:
    lines = [
        "| Run | Records | Coded | Errors | Successes | ASR |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(rows, key=lambda item: item.run_size):
        data = row.data
        lines.append(
            f"| {row.run_size} | {data['n_records']} | {data['n_coded']} | "
            f"{data['n_errors']} | {data['n_success']} | "
            f"{pct(rate(int(data['n_success']), int(data['n_coded'])))} |"
        )
    lines.append(
        f"| **Pooled** | **{pooled['n_records']}** | **{pooled['n_coded']}** | "
        f"**{pooled['n_errors']}** | **{pooled['n_success']}** | "
        f"**{pct(rate(pooled['n_success'], pooled['n_coded']))}** |"
    )
    return lines


def grouped_table(groups: dict[str, dict[str, Any]]) -> list[str]:
    lines = [
        "| Group | N | Successes | ASR | Severity distribution |",
        "|---|---:|---:|---:|---|",
    ]
    ordered = sorted(
        groups.items(),
        key=lambda item: (-int(item[1]["n"]), str(item[0]).lower()),
    )
    for label, group in ordered:
        lines.append(
            f"| {escape_cell(label)} | {group['n']} | {group['successes']} | "
            f"{pct(rate(group['successes'], group['n']))} | "
            f"{escape_cell(severity_text(group['severity_counts']))} |"
        )
    return lines


def render_report(
    summaries: list[ReviewedSummary],
    outputs_dir: Path,
    sizes: list[int],
) -> str:
    by_model: dict[str, dict[str, list[ReviewedSummary]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in summaries:
        by_model[row.response_model][row.attack_kind].append(row)

    lines = [
        "# Aggregated Reviewed CAA Evaluations",
        "",
        "This report pools the reviewed trajectory-attack and weak-attack evaluation "
        "summaries separately for each response model.",
        "",
        f"- Source root: `{display_path(outputs_dir)}`",
        f"- Included nominal run sizes: {', '.join(str(size) for size in sizes)}",
        "- Evaluation source: `reviewed_severity_llama31/summary.json` only",
        "- Pooled ASR: sum of successes divided by sum of coded records",
        "- Runs are pooled arithmetically; trial IDs are not deduplicated across directories",
        "",
        "## Cross-model overview",
        "",
        "| Response model | Attack type | Runs | Coded | Successes | Pooled ASR |",
        "|---|---|---:|---:|---:|---:|",
    ]

    for model in sorted(by_model, key=str.lower):
        for attack_kind in ("trajectory", "weak"):
            rows = by_model[model].get(attack_kind, [])
            if not rows:
                continue
            pooled = aggregate_summaries(rows)
            run_labels = ", ".join(str(row.run_size) for row in sorted(rows, key=lambda item: item.run_size))
            lines.append(
                f"| {escape_cell(model)} | {ATTACK_TITLES[attack_kind]} | "
                f"{run_labels} | {pooled['n_coded']} | {pooled['n_success']} | "
                f"{pct(rate(pooled['n_success'], pooled['n_coded']))} |"
            )

    for model in sorted(by_model, key=str.lower):
        model_rows = [row for rows in by_model[model].values() for row in rows]
        keys = sorted({row.model_key for row in model_rows})
        lines.extend(["", f"## {model}", ""])
        if keys:
            lines.append(f"Experiment model key: `{', '.join(keys)}`")

        for attack_kind in ("trajectory", "weak"):
            rows = by_model[model].get(attack_kind, [])
            if not rows:
                continue
            pooled = aggregate_summaries(rows)
            lines.extend(["", f"### {ATTACK_TITLES[attack_kind]}", ""])
            lines.extend(overall_table(rows, pooled))
            lines.extend(
                [
                    "",
                    f"Pooled severity distribution: {severity_text(pooled['severity_counts'])}.",
                    "",
                    "#### By attempt",
                    "",
                ]
            )
            lines.extend(grouped_table(pooled["by_attempt"]))
            lines.extend(["", "#### By source primary attack vector", ""])
            lines.extend(grouped_table(pooled["by_source_primary_attack_vector"]))
            lines.extend(["", "Source summaries:", ""])
            for row in sorted(rows, key=lambda item: item.run_size):
                lines.append(f"- {row.run_size}: `{display_path(row.path)}`")

    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pool reviewed trajectory and weak-attack evaluation summaries by response model."
        )
    )
    parser.add_argument("--outputs-dir", type=Path, default=DEFAULT_OUTPUTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 300])
    parser.add_argument(
        "--expected-models",
        type=int,
        default=4,
        help="Fail unless this many response models are discovered; use 0 to disable.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Generate a partial report when an expected summary is missing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs_dir = args.outputs_dir.resolve()
    output_path = args.output.resolve()
    sizes = sorted(set(args.sizes))
    if not outputs_dir.is_dir():
        raise SystemExit(f"Outputs directory does not exist: {outputs_dir}")

    summaries, missing = discover_summaries(outputs_dir, set(sizes))
    if missing and not args.allow_missing:
        raise SystemExit("Missing reviewed summaries:\n- " + "\n- ".join(missing))
    if not summaries:
        raise SystemExit("No reviewed evaluation summaries were discovered.")

    models = {row.response_model for row in summaries}
    if args.expected_models > 0 and len(models) != args.expected_models:
        raise SystemExit(
            f"Expected {args.expected_models} response models, discovered {len(models)}: "
            + ", ".join(sorted(models))
        )

    expected_pairs = {
        (model, size, attack_kind)
        for model in models
        for size in sizes
        for attack_kind in SUMMARY_PATHS
    }
    observed_pairs = {
        (row.response_model, row.run_size, row.attack_kind) for row in summaries
    }
    absent_pairs = sorted(expected_pairs - observed_pairs)
    if absent_pairs and not args.allow_missing:
        formatted = [f"{model}, n={size}, {kind}" for model, size, kind in absent_pairs]
        raise SystemExit("Incomplete model/size/attack matrix:\n- " + "\n- ".join(formatted))

    report = render_report(summaries, outputs_dir, sizes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(
        f"Wrote {output_path} from {len(summaries)} reviewed summaries "
        f"across {len(models)} response models."
    )
    if missing:
        print(f"Skipped {len(missing)} missing summary files because --allow-missing was set.")


if __name__ == "__main__":
    main()
