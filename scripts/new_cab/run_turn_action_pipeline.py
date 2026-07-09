"""Run the Round 5 turn-action CAB pipeline end to end."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab_round5_reviewed_all"


def run(command: list[str]) -> None:
    print("+ " + " ".join(str(part) for part in command))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build turn-action CAB and stats for Round 5 reviewed data.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--top-k", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run([
        sys.executable,
        "scripts/new_cab/build_turn_action_bank.py",
        "--out-dir",
        str(args.out_dir),
    ])
    run([
        sys.executable,
        "scripts/new_cab/compute_turn_action_stats.py",
        "--bank",
        str(args.out_dir / "turn_action_conversation_bank.jsonl"),
        "--out-dir",
        str(args.out_dir / "turn_action_stats"),
        "--top-k",
        str(args.top_k),
    ])


if __name__ == "__main__":
    main()
