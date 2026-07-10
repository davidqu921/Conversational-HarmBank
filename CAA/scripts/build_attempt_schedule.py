from __future__ import annotations

import argparse
import random
from collections import Counter
from pathlib import Path

from CAA.scripts.caa_common import (
    ATTEMPTS,
    allocate_attempts,
    count_attempts,
    expanded_schedule,
    load_config,
    load_jsonl,
    resolve_project_path,
    write_csv,
    write_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deterministic CAA attempt schedule.")
    parser.add_argument("--config", type=Path, default=Path("CAA/configs/round5_balanced_40.yaml"))
    args = parser.parse_args()

    config = load_config(args.config)
    rng = random.Random(config.seed)
    records = load_jsonl(config.raw["paths"]["turn_action_bank"])
    counts: Counter = count_attempts(records)
    min_per_attempt = int(config.raw.get("sampling", {}).get("min_per_attempt", 2))
    allocation = allocate_attempts(counts, config.num_attacks, min_per_attempt, rng)
    schedule = expanded_schedule(allocation, rng)

    out_dir = config.output_dir / "planning"
    rows = [
        {
            "attack_index": idx,
            "attack_id": f"caa_{idx:04d}",
            "attempt": attempt,
            "attempt_quota_index": sum(1 for prev in schedule[:idx - 1] if prev == attempt) + 1,
        }
        for idx, attempt in enumerate(schedule, 1)
    ]

    write_json(out_dir / "attempt_schedule.json", {
        "experiment_id": config.experiment_id,
        "seed": config.seed,
        "num_attacks": config.num_attacks,
        "min_per_attempt": min_per_attempt,
        "source_counts": {attempt: counts.get(attempt, 0) for attempt in ATTEMPTS},
        "allocation": allocation,
        "schedule": rows,
        "config": str(resolve_project_path(args.config)),
    })
    write_csv(
        out_dir / "attempt_schedule.csv",
        rows,
        ["attack_index", "attack_id", "attempt", "attempt_quota_index"],
    )
    print(f"Wrote {len(rows)} scheduled attacks to {out_dir}")
    print("Allocation:", allocation)


if __name__ == "__main__":
    main()

