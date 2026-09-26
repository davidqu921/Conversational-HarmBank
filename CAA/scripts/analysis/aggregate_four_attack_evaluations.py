"""Aggregate four CAA attack conditions across response models.

For every model, run size, and attack condition, prefer the human-reviewed
summary and fall back to the direct Llama-3.1 severity coding when a reviewed
summary is unavailable. Counts are pooled; percentages are never averaged.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "CAA" / "outputs"
DEFAULT_REPORT = DEFAULT_OUTPUTS_DIR / "four_attack_evaluation_summary.md"

EXPERIMENT_RE = re.compile(
    r"^round5_balanced_(?P<size>\d+)_llama31_(?P<model>.+?)"
    r"_stronger(?:_v\d+_topic_conditional)?$"
)

ATTACK_DIRS = {
    "trajectory": "evaluation",
    "weak": "weak_attack_evaluation",
    "repeated_weak": "repeated_weak_attack_evaluation",
    "trajectory_seeded_repeated": "trajectory_seeded_repeated_weak_attack_evaluation",
}

ATTACK_TITLES = {
    "trajectory": "Trajectory",
    "weak": "Weak",
    "repeated_weak": "Repeated weak (replay)",
    "trajectory_seeded_repeated": "Trajectory-seeded repeated",
}

ATTACK_ORDER = tuple(ATTACK_DIRS)

MODEL_TITLES = {
    "gemma3_12b": "Gemma 3 12B",
    "llama31_8b": "Llama 3.1 8B",
    "mistral_7b": "Mistral 7B",
    "qwen25_7b": "Qwen 2.5 7B",
}

SEVERITY_ORDER = ("0 - Safe", "1 - Minor", "2 - Major", "3 - Severe")


@dataclass(frozen=True)
class Summary:
    experiment_dir: Path
    run_size: int
    model_key: str
    attack_kind: str
    coding_source: str
    path: Path
    data: dict[str, Any]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def require_count(data: dict[str, Any], field: str, path: Path) -> int:
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path}: {field} must be a nonnegative integer")
    return value


def validate_summary(data: dict[str, Any], path: Path) -> None:
    if data.get("schema_version"):
        raise ValueError(f"{path}: this historical binary report does not accept versioned neutral-aware outputs; use the evaluator summary/reference comparison")
    n_records = require_count(data, "n_records", path)
    n_coded = require_count(data, "n_coded", path)
    n_success = require_count(data, "n_success", path)
    require_count(data, "n_errors", path)
    if n_coded > n_records or n_success > n_coded:
        raise ValueError(f"{path}: inconsistent record/coded/success counts")
    severity_counts = data.get("severity_counts")
    if not isinstance(severity_counts, dict):
        raise ValueError(f"{path}: severity_counts must be an object")
    if sum(int(value) for value in severity_counts.values()) != n_coded:
        raise ValueError(f"{path}: severity_counts do not sum to n_coded")


def preferred_summary(evaluation_dir: Path) -> tuple[Path, str] | None:
    candidates = (
        (evaluation_dir / "reviewed_severity_llama31" / "summary.json", "reviewed"),
        (evaluation_dir / "severity_llama31" / "summary.json", "direct"),
    )
    return next(((path, source) for path, source in candidates if path.is_file()), None)


def discover(
    outputs_dir: Path,
    sizes: set[int],
    model_keys: set[str],
) -> tuple[list[Summary], list[str]]:
    rows: list[Summary] = []
    missing: list[str] = []
    for experiment_dir in sorted(path for path in outputs_dir.iterdir() if path.is_dir()):
        match = EXPERIMENT_RE.match(experiment_dir.name)
        if not match:
            continue
        run_size = int(match.group("size"))
        model_key = match.group("model")
        if run_size not in sizes or model_key not in model_keys:
            continue
        for attack_kind, relative_dir in ATTACK_DIRS.items():
            selected = preferred_summary(experiment_dir / relative_dir)
            if selected is None:
                missing.append(f"{experiment_dir.name}: {relative_dir}")
                continue
            path, coding_source = selected
            data = load_json(path)
            validate_summary(data, path)
            rows.append(
                Summary(
                    experiment_dir=experiment_dir,
                    run_size=run_size,
                    model_key=model_key,
                    attack_kind=attack_kind,
                    coding_source=coding_source,
                    path=path,
                    data=data,
                )
            )
    return rows, missing


def pooled(rows: Iterable[Summary]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "n_records": 0,
        "n_coded": 0,
        "n_errors": 0,
        "n_success": 0,
        "severity_counts": Counter(),
    }
    for row in rows:
        for field in ("n_records", "n_coded", "n_errors", "n_success"):
            result[field] += int(row.data[field])
        result["severity_counts"].update(
            {key: int(value) for key, value in row.data["severity_counts"].items()}
        )
    return result


def pct(successes: int, coded: int) -> str:
    if not coded:
        return "n/a"
    value = (Decimal(successes) * 100 / Decimal(coded)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return f"{value}%"


def result_cell(data: dict[str, Any]) -> str:
    successes = int(data["n_success"])
    coded = int(data["n_coded"])
    return f"{successes} / {coded} ({pct(successes, coded)})"


def source_text(rows: Iterable[Summary]) -> str:
    sources = {row.coding_source for row in rows}
    if sources == {"reviewed"}:
        return "reviewed"
    if sources == {"direct"}:
        return "direct"
    return "mixed"


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def render_report(rows: list[Summary], sizes: list[int], model_keys: list[str]) -> str:
    by_cell = {
        (row.model_key, row.run_size, row.attack_kind): row for row in rows
    }
    lines = [
        "# Four-Condition CAA Evaluation Across Four Models",
        "",
        "Each model pools the 100- and 300-conversation runs. For every individual "
        "cell, human-reviewed coding is preferred; direct `severity_llama31` coding "
        "is used only when reviewed coding is unavailable.",
        "",
        "- ASR is recomputed as total successes / total coded records.",
        "- Counts are pooled; run-level percentages are not averaged.",
        "- `reviewed` means `reviewed_severity_llama31/summary.json`.",
        "- `direct` means unreviewed `severity_llama31/summary.json`.",
        "",
        "## Pooled comparison",
        "",
        "| Response model | "
        + " | ".join(ATTACK_TITLES[kind] for kind in ATTACK_ORDER)
        + " |",
        "|---|" + "---:|" * len(ATTACK_ORDER),
    ]

    for model_key in model_keys:
        cells = []
        for attack_kind in ATTACK_ORDER:
            selected = [
                by_cell[(model_key, size, attack_kind)] for size in sizes
            ]
            cells.append(result_cell(pooled(selected)))
        lines.append(f"| {MODEL_TITLES.get(model_key, model_key)} | " + " | ".join(cells) + " |")

    all_cells = []
    for attack_kind in ATTACK_ORDER:
        selected = [row for row in rows if row.attack_kind == attack_kind]
        all_cells.append(f"**{result_cell(pooled(selected))}**")
    lines.append("| **All models** | " + " | ".join(all_cells) + " |")

    lines.extend(
        [
            "",
            "## Run breakdown and coding provenance",
            "",
            "| Response model | Attack type | "
            + " | ".join(str(size) for size in sizes)
            + " | Pooled | Coding source |",
            "|---|---|" + "---:|" * len(sizes) + "---:|---|",
        ]
    )
    for model_key in model_keys:
        for attack_kind in ATTACK_ORDER:
            selected = [by_cell[(model_key, size, attack_kind)] for size in sizes]
            run_cells = [result_cell(row.data) for row in selected]
            lines.append(
                f"| {MODEL_TITLES.get(model_key, model_key)} | "
                f"{ATTACK_TITLES[attack_kind]} | "
                + " | ".join(run_cells)
                + f" | {result_cell(pooled(selected))} | {source_text(selected)} |"
            )

    lines.extend(
        [
            "",
            "## Across-model severity distribution",
            "",
            "| Attack type | Coded | Successes | ASR | "
            + " | ".join(SEVERITY_ORDER)
            + " |",
            "|---|---:|---:|---:|" + "---:|" * len(SEVERITY_ORDER),
        ]
    )
    for attack_kind in ATTACK_ORDER:
        aggregate = pooled(row for row in rows if row.attack_kind == attack_kind)
        counts = aggregate["severity_counts"]
        lines.append(
            f"| {ATTACK_TITLES[attack_kind]} | {aggregate['n_coded']} | "
            f"{aggregate['n_success']} | "
            f"{pct(aggregate['n_success'], aggregate['n_coded'])} | "
            + " | ".join(str(int(counts.get(label, 0))) for label in SEVERITY_ORDER)
            + " |"
        )

    lines.extend(["", "## Source summaries", ""])
    for row in sorted(
        rows,
        key=lambda item: (item.model_key, item.attack_kind, item.run_size),
    ):
        lines.append(
            f"- {MODEL_TITLES.get(row.model_key, row.model_key)}, n={row.run_size}, "
            f"{ATTACK_TITLES[row.attack_kind]} ({row.coding_source}): "
            f"`{display_path(row.path)}`"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate trajectory, weak, repeated, and trajectory-seeded attacks."
    )
    parser.add_argument("--outputs-dir", type=Path, default=DEFAULT_OUTPUTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 300])
    parser.add_argument(
        "--models", nargs="+", default=list(MODEL_TITLES), choices=tuple(MODEL_TITLES)
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs_dir = args.outputs_dir.resolve()
    sizes = sorted(set(args.sizes))
    model_keys = list(dict.fromkeys(args.models))
    rows, missing = discover(outputs_dir, set(sizes), set(model_keys))
    if missing:
        raise SystemExit("Missing evaluation summaries:\n- " + "\n- ".join(missing))
    expected = len(sizes) * len(model_keys) * len(ATTACK_ORDER)
    if len(rows) != expected:
        raise SystemExit(f"Expected {expected} summaries, discovered {len(rows)}")
    report_path = args.output.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(rows, sizes, model_keys), encoding="utf-8"
    )
    source_counts = Counter(row.coding_source for row in rows)
    print(
        f"Wrote {report_path} from {len(rows)} summaries "
        f"({source_counts['reviewed']} reviewed, {source_counts['direct']} direct)."
    )


if __name__ == "__main__":
    main()
