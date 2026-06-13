"""
Filter low-information transcript records before segmentation.

Keeps only conversations whose original `n_turns` is greater than 1.
By default:

  input:  data_prep/transcripts.jsonl
  output: data_prep/clean_transcript.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data_prep" / "transcripts.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data_prep" / "clean_transcript.jsonl"


def keep_record(record: dict[str, Any]) -> bool:
    try:
        return int(record.get("n_turns", 0)) > 1
    except (TypeError, ValueError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    kept = 0
    dropped = 0

    with args.input.open(encoding="utf-8") as f_in, args.output.open("w", encoding="utf-8") as f_out:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            total += 1
            record = json.loads(line)
            if keep_record(record):
                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                kept += 1
            else:
                dropped += 1

    print(f"Read {total} records from {args.input}")
    print(f"Kept {kept} records with n_turns > 1")
    print(f"Dropped {dropped} records with n_turns <= 1 or invalid n_turns")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
