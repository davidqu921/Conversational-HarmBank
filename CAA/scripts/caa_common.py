from __future__ import annotations

import csv
import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ATTEMPTS = [
    "Swearing",
    "Slur",
    "Inappropriate Topics",
    "Political/Social/Bias",
    "Incorrect Information",
    "Break Character",
    "General Break",
    "Leak Information",
]

SEVERITY_RANK = {
    "0 - Safe": 0,
    "1 - Minor": 1,
    "2 - Major": 2,
    "3 - Severe": 3,
}


@dataclass(frozen=True)
class CaaConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])

    @property
    def seed(self) -> int:
        return int(self.raw.get("seed", 0))

    @property
    def num_attacks(self) -> int:
        return int(self.raw.get("num_attacks", 40))

    @property
    def output_dir(self) -> Path:
        output_root = resolve_project_path(self.raw["paths"]["output_root"])
        return output_root / self.experiment_id


def resolve_project_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(path: str | Path) -> CaaConfig:
    resolved = resolve_project_path(path)
    return CaaConfig(raw=load_yaml(resolved), path=resolved)


def load_json(path: str | Path) -> Any:
    return json.loads(resolve_project_path(path).read_text(encoding="utf-8"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with resolve_project_path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def attempts_for_record(record: dict[str, Any]) -> list[str]:
    values = record.get("attempt_type") or []
    if isinstance(values, str):
        values = [values]
    if not values and record.get("attempt"):
        values = [record["attempt"]]
    return [str(value).strip() for value in values if str(value).strip()]


def severity_rank(record: dict[str, Any]) -> int:
    return SEVERITY_RANK.get(str(record.get("severity", "")), -1)


def count_attempts(records: list[dict[str, Any]], include_no_attempt: bool = False) -> Counter:
    counts: Counter = Counter()
    for record in records:
        for attempt in attempts_for_record(record):
            if attempt == "No Attempt" and not include_no_attempt:
                continue
            if attempt in ATTEMPTS:
                counts[attempt] += 1
    return counts


def allocate_attempts(
    counts: Counter,
    num_attacks: int,
    min_per_attempt: int,
    rng: random.Random,
) -> dict[str, int]:
    available = [attempt for attempt in ATTEMPTS if counts.get(attempt, 0) > 0]
    if num_attacks <= 0 or not available:
        return {}

    if num_attacks < len(available) * min_per_attempt:
        ranked = sorted(available, key=lambda item: (-counts[item], item))
        selected = ranked[:num_attacks]
        return {attempt: 1 for attempt in selected}

    allocation = {attempt: min_per_attempt for attempt in available}
    remaining = num_attacks - sum(allocation.values())
    total = sum(counts[attempt] for attempt in available)
    if remaining <= 0 or total <= 0:
        return allocation

    shares = {
        attempt: remaining * counts[attempt] / total
        for attempt in available
    }
    for attempt, share in shares.items():
        whole = int(share)
        allocation[attempt] += whole
        remaining -= whole

    ranked_remainders = sorted(
        available,
        key=lambda item: (-(shares[item] - int(shares[item])), -counts[item], item),
    )
    if remaining > 0:
        # Shuffle equal-ish tail deterministically so repeated experiments do
        # not always give the same low-count attempt the final slot.
        tail = ranked_remainders[:]
        rng.shuffle(tail)
        ranked_remainders = sorted(
            tail,
            key=lambda item: (-(shares[item] - int(shares[item])), -counts[item], item),
        )
    for attempt in ranked_remainders[:remaining]:
        allocation[attempt] += 1
    return {attempt: allocation[attempt] for attempt in ATTEMPTS if allocation.get(attempt, 0)}


def expanded_schedule(allocation: dict[str, int], rng: random.Random) -> list[str]:
    schedule: list[str] = []
    for attempt in ATTEMPTS:
        schedule.extend([attempt] * allocation.get(attempt, 0))
    rng.shuffle(schedule)
    return schedule


def sequence_key(items: list[str]) -> str:
    return " -> ".join(str(item).strip() for item in items if str(item).strip())

