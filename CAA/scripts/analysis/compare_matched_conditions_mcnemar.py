"""Compare reviewed trajectory and one-turn attacks with paired McNemar tests.

Each experimental assignment is paired by ``id`` between these files::

    evaluation/reviewed_severity_llama31/codings.csv
    weak_attack_evaluation/reviewed_severity_llama31/codings.csv

The second path is called "weak attack" in the repository; this report calls it
"one-turn attack" to match the experimental condition name.  The primary test
is the two-sided exact McNemar test, computed from the discordant pairs only.
No third-party statistics package is required.
"""
from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:  # Support both direct execution and ``python -m CAA.scripts...``.
    from .aggregate_reviewed_evaluations import (
        DEFAULT_OUTPUTS_DIR,
        EXPERIMENT_RE,
        display_path,
        response_model_from_conversation,
    )
except ImportError:
    from aggregate_reviewed_evaluations import (
        DEFAULT_OUTPUTS_DIR,
        EXPERIMENT_RE,
        display_path,
        response_model_from_conversation,
    )


DEFAULT_REPORT = DEFAULT_OUTPUTS_DIR / "mcnemar_trajectory_vs_one_turn.md"

CODING_PATHS = {
    "trajectory": Path("evaluation/reviewed_severity_llama31/codings.csv"),
    "one_turn": Path("weak_attack_evaluation/reviewed_severity_llama31/codings.csv"),
}


@dataclass(frozen=True)
class Coding:
    assignment_id: str
    success: bool
    severity: str
    attempt: str
    attack_vector: str


@dataclass(frozen=True)
class Experiment:
    directory: Path
    run_size: int
    model_key: str
    response_model: str


@dataclass(frozen=True)
class PairedResult:
    label: str
    response_model: str
    run_size: int | None
    sources: tuple[tuple[Path, Path], ...]
    n11: int  # trajectory success, one-turn success
    n10: int  # trajectory success, one-turn failure
    n01: int  # trajectory failure, one-turn success
    n00: int  # trajectory failure, one-turn failure
    exact_p: float
    corrected_chi2: float
    corrected_p: float
    metadata_mismatches: int

    @property
    def n(self) -> int:
        return self.n11 + self.n10 + self.n01 + self.n00

    @property
    def trajectory_successes(self) -> int:
        return self.n11 + self.n10

    @property
    def one_turn_successes(self) -> int:
        return self.n11 + self.n01

    @property
    def discordant(self) -> int:
        return self.n10 + self.n01


def parse_bool(value: str, *, path: Path, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{path}:{row_number}: invalid success value {value!r}")


def severity_is_success(value: str, *, path: Path, row_number: int) -> bool:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{path}:{row_number}: empty severity")
    prefix = normalized.split("-", 1)[0].strip()
    try:
        level = int(prefix)
    except ValueError as exc:
        raise ValueError(
            f"{path}:{row_number}: severity must start with an integer, got {value!r}"
        ) from exc
    return level > 0


def load_codings(path: Path) -> dict[str, Coding]:
    required = {
        "id",
        "attempt",
        "source_primary_attack_vector",
        "severity",
        "success",
    }
    rows: dict[str, Coding] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")
        for row_number, row in enumerate(reader, start=2):
            if row.get("schema_version"):
                raise ValueError(f"{path}: binary matched-condition analysis requires fully reviewed historical exports; v2 needs explicit neutral handling")
            assignment_id = (row.get("id") or "").strip()
            if not assignment_id:
                raise ValueError(f"{path}:{row_number}: empty id")
            if assignment_id in rows:
                raise ValueError(f"{path}:{row_number}: duplicate id {assignment_id!r}")
            success = parse_bool(row.get("success") or "", path=path, row_number=row_number)
            severity = (row.get("severity") or "").strip()
            severity_success = severity_is_success(
                severity, path=path, row_number=row_number
            )
            if success != severity_success:
                raise ValueError(
                    f"{path}:{row_number}: success={success} conflicts with "
                    f"severity={severity!r}"
                )
            rows[assignment_id] = Coding(
                assignment_id=assignment_id,
                success=success,
                severity=severity,
                attempt=(row.get("attempt") or "").strip(),
                attack_vector=(row.get("source_primary_attack_vector") or "").strip(),
            )
    return rows


def discover_experiments(outputs_dir: Path, sizes: set[int]) -> list[Experiment]:
    experiments: list[Experiment] = []
    for directory in sorted(path for path in outputs_dir.iterdir() if path.is_dir()):
        match = EXPERIMENT_RE.fullmatch(directory.name)
        if not match:
            continue
        run_size = int(match.group("size"))
        if run_size not in sizes:
            continue
        if not all((directory / relative).is_file() for relative in CODING_PATHS.values()):
            continue
        model_key = match.group("model")
        experiments.append(
            Experiment(
                directory=directory,
                run_size=run_size,
                model_key=model_key,
                response_model=response_model_from_conversation(directory, model_key),
            )
        )
    return experiments


def exact_mcnemar_p(n10: int, n01: int) -> float:
    """Two-sided exact binomial McNemar p-value under p=0.5."""
    discordant = n10 + n01
    if discordant == 0:
        return 1.0
    tail_end = min(n10, n01)
    tail = sum(math.comb(discordant, k) for k in range(tail_end + 1)) / (2**discordant)
    return min(1.0, 2.0 * tail)


def corrected_asymptotic_mcnemar(n10: int, n01: int) -> tuple[float, float]:
    """Continuity-corrected chi-square statistic and df=1 survival probability."""
    discordant = n10 + n01
    if discordant == 0:
        return 0.0, 1.0
    statistic = (abs(n10 - n01) - 1.0) ** 2 / discordant
    p_value = math.erfc(math.sqrt(statistic / 2.0))
    return statistic, p_value


def compare_pairs(
    label: str,
    response_model: str,
    run_size: int | None,
    sources: Iterable[tuple[Path, Path]],
    *,
    allow_unmatched: bool,
) -> PairedResult:
    n11 = n10 = n01 = n00 = metadata_mismatches = 0
    source_tuple = tuple(sources)
    for trajectory_path, one_turn_path in source_tuple:
        trajectory = load_codings(trajectory_path)
        one_turn = load_codings(one_turn_path)
        trajectory_ids = set(trajectory)
        one_turn_ids = set(one_turn)
        if trajectory_ids != one_turn_ids and not allow_unmatched:
            trajectory_only = sorted(trajectory_ids - one_turn_ids)
            one_turn_only = sorted(one_turn_ids - trajectory_ids)
            raise ValueError(
                f"Unmatched assignment ids in {trajectory_path.parent.parent.parent}: "
                f"trajectory-only={trajectory_only[:10]!r}; "
                f"one-turn-only={one_turn_only[:10]!r}. "
                "Use --allow-unmatched to analyze only the intersection."
            )
        for assignment_id in sorted(trajectory_ids & one_turn_ids):
            trajectory_row = trajectory[assignment_id]
            one_turn_row = one_turn[assignment_id]
            if (
                trajectory_row.attempt != one_turn_row.attempt
                or trajectory_row.attack_vector != one_turn_row.attack_vector
            ):
                metadata_mismatches += 1
            pair = (trajectory_row.success, one_turn_row.success)
            if pair == (True, True):
                n11 += 1
            elif pair == (True, False):
                n10 += 1
            elif pair == (False, True):
                n01 += 1
            else:
                n00 += 1
    exact_p = exact_mcnemar_p(n10, n01)
    corrected_chi2, corrected_p = corrected_asymptotic_mcnemar(n10, n01)
    return PairedResult(
        label=label,
        response_model=response_model,
        run_size=run_size,
        sources=source_tuple,
        n11=n11,
        n10=n10,
        n01=n01,
        n00=n00,
        exact_p=exact_p,
        corrected_chi2=corrected_chi2,
        corrected_p=corrected_p,
        metadata_mismatches=metadata_mismatches,
    )


def holm_adjust(p_values: list[float]) -> list[float]:
    """Return Holm family-wise-error-adjusted p-values in original order."""
    count = len(p_values)
    adjusted = [1.0] * count
    running_max = 0.0
    for rank, index in enumerate(sorted(range(count), key=p_values.__getitem__)):
        candidate = min(1.0, (count - rank) * p_values[index])
        running_max = max(running_max, candidate)
        adjusted[index] = running_max
    return adjusted


def pct(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.2%}" if denominator else "NA"


def p_text(value: float) -> str:
    return "< 0.000001" if value < 0.000001 else f"{value:.6f}"


def escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def result_table(
    results: list[PairedResult], holm_values: dict[tuple[str, str], float], alpha: float
) -> list[str]:
    lines = [
        "| Response model | Run | N pairs | Trajectory success | One-turn success | Both success | Trajectory only (b) | One-turn only (c) | Neither | Difference (pp) | Exact p | Holm p | Holm-significant |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for result in results:
        run = str(result.run_size) if result.run_size is not None else "Pooled"
        difference = 100.0 * (result.n10 - result.n01) / result.n if result.n else 0.0
        holm_p = holm_values[(result.label, result.response_model)]
        lines.append(
            f"| {escape_cell(result.response_model)} | {run} | {result.n} | "
            f"{result.trajectory_successes} ({pct(result.trajectory_successes, result.n)}) | "
            f"{result.one_turn_successes} ({pct(result.one_turn_successes, result.n)}) | "
            f"{result.n11} | {result.n10} | {result.n01} | {result.n00} | "
            f"{difference:+.2f} | {p_text(result.exact_p)} | {p_text(holm_p)} | "
            f"{'Yes' if holm_p < alpha else 'No'} |"
        )
    return lines


def build_report(results: list[PairedResult], alpha: float) -> str:
    by_label: dict[str, list[PairedResult]] = {}
    for result in results:
        by_label.setdefault(result.label, []).append(result)

    holm_values: dict[tuple[str, str], float] = {}
    for label, group in by_label.items():
        adjusted = holm_adjust([item.exact_p for item in group])
        for item, adjusted_p in zip(group, adjusted):
            holm_values[(label, item.response_model)] = adjusted_p

    ordered = sorted(
        results,
        key=lambda item: (
            item.run_size is None,
            item.run_size if item.run_size is not None else 10**9,
            item.response_model.lower(),
        ),
    )
    lines = [
        "# Paired comparison: trajectory attack vs one-turn attack",
        "",
        "This report pairs the two reviewed conditions by assignment `id`. "
        "The repository directory named `weak_attack_evaluation` is treated as "
        "the one-turn attack condition.",
        "",
        "## Statistical definition",
        "",
        "For each response model and run size, the paired table contains: "
        "`b` = trajectory succeeds and one-turn fails; `c` = trajectory fails "
        "and one-turn succeeds. The primary two-sided exact McNemar test uses "
        "only the `b + c` discordant pairs and tests `b ~ Binomial(b + c, 0.5)`. "
        "Success is the reviewed CSV field `success=True`, validated to be "
        "equivalent to severity > 0. The ASR denominator is the number of "
        "matched assignments, not independent condition totals.",
        "",
        f"Holm-adjusted p-values control family-wise error at alpha = {alpha:g} "
        "across the four response models separately within each run-size "
        "family (100, 300, and pooled). Exact p-values are primary; the "
        "continuity-corrected asymptotic values appear in the detailed sections.",
        "",
        "## Results",
        "",
        *result_table(ordered, holm_values, alpha),
        "",
        "The `Difference (pp)` column is trajectory ASR minus one-turn ASR. "
        "A positive value favors the trajectory condition.",
        "",
        "## Detailed paired tables",
        "",
    ]

    for result in ordered:
        run = str(result.run_size) if result.run_size is not None else "Pooled 100 + 300"
        corrected_or = (result.n10 + 0.5) / (result.n01 + 0.5)
        lines.extend(
            [
                f"### {result.response_model} — {run}",
                "",
                "| Trajectory \\ One-turn | Success | Failure | Total |",
                "|---|---:|---:|---:|",
                f"| Success | {result.n11} | {result.n10} | {result.trajectory_successes} |",
                f"| Failure | {result.n01} | {result.n00} | {result.n01 + result.n00} |",
                f"| Total | {result.one_turn_successes} | {result.n10 + result.n00} | {result.n} |",
                "",
                f"- Discordant pairs: {result.discordant} (`b={result.n10}`, `c={result.n01}`)",
                f"- Two-sided exact McNemar p: {p_text(result.exact_p)}",
                f"- Continuity-corrected McNemar chi-square: {result.corrected_chi2:.6f}; p: {p_text(result.corrected_p)}",
                f"- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: {corrected_or:.4f}",
                f"- Attempt/vector metadata mismatches among paired IDs: {result.metadata_mismatches}",
                "- Sources:",
            ]
        )
        for trajectory_path, one_turn_path in result.sources:
            lines.append(
                f"  - trajectory: `{display_path(trajectory_path)}`; "
                f"one-turn: `{display_path(one_turn_path)}`"
            )
        lines.append("")

    lines.extend(
        [
            "## Pooling caveat",
            "",
            "The per-run-size tests are the least assumption-dependent results. "
            "The pooled rows concatenate the 100- and 300-assignment directories "
            "using `(experiment directory, id)` as the pair key. They are valid "
            "only if those directories contain distinct experimental assignments. "
            "If the 100-run assignments are a subset or rerun of the 300-run "
            "assignments, do not use the pooled p-value; use the 300-run result or "
            "deduplicate with a stable cross-run assignment identifier.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs-dir", type=Path, default=DEFAULT_OUTPUTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 300])
    parser.add_argument("--expected-models", type=int, default=4)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument(
        "--allow-unmatched",
        action="store_true",
        help="Analyze only ID intersections instead of failing on unmatched IDs.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Do not fail if a requested size lacks the expected model count.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sizes = set(args.sizes)
    if not sizes:
        raise ValueError("At least one run size is required")
    if not 0.0 < args.alpha < 1.0:
        raise ValueError("--alpha must be between 0 and 1")

    experiments = discover_experiments(args.outputs_dir, sizes)
    if not experiments:
        raise FileNotFoundError(
            f"No complete paired experiments found under {args.outputs_dir}"
        )

    for size in sorted(sizes):
        model_count = len({item.response_model for item in experiments if item.run_size == size})
        if model_count != args.expected_models and not args.allow_missing:
            raise ValueError(
                f"Run size {size}: found {model_count} complete response models; "
                f"expected {args.expected_models}. Use --allow-missing to continue."
            )

    results: list[PairedResult] = []
    for experiment in experiments:
        source_pair = tuple(
            experiment.directory / CODING_PATHS[kind]
            for kind in ("trajectory", "one_turn")
        )
        results.append(
            compare_pairs(
                label=str(experiment.run_size),
                response_model=experiment.response_model,
                run_size=experiment.run_size,
                sources=[source_pair],
                allow_unmatched=args.allow_unmatched,
            )
        )

    by_model: dict[str, list[Experiment]] = {}
    for experiment in experiments:
        by_model.setdefault(experiment.response_model, []).append(experiment)
    if len(sizes) > 1:
        for response_model, model_experiments in sorted(by_model.items()):
            source_pairs = [
                (
                    experiment.directory / CODING_PATHS["trajectory"],
                    experiment.directory / CODING_PATHS["one_turn"],
                )
                for experiment in sorted(model_experiments, key=lambda item: item.run_size)
            ]
            results.append(
                compare_pairs(
                    label="pooled",
                    response_model=response_model,
                    run_size=None,
                    sources=source_pairs,
                    allow_unmatched=args.allow_unmatched,
                )
            )

    report = build_report(results, args.alpha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {display_path(args.output)}")


if __name__ == "__main__":
    main()
