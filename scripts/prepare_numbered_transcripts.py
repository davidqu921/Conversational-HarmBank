"""
Prepare numbered transcripts for conversation segmentation.

Reads data_prep/transcripts.jsonl and writes a JSONL file where each record
contains deterministic turn numbers for every Steve/Student utterance plus the
complete list of Student turn numbers.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data_prep" / "clean_transcripts.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "conversation_seg" / "numbered_transcripts.jsonl"
TURN_RE = re.compile(r"^(Steve|Student):\s*(.*)$")


def parse_transcript_turns(transcript_text: str) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for raw_line in transcript_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = TURN_RE.match(line)
        if match:
            turns.append({
                "turn": len(turns) + 1,
                "speaker": match.group(1),
                "text": match.group(2).strip(),
            })
        elif turns:
            turns[-1]["text"] = f"{turns[-1]['text']} {line}".strip()
    return turns


def prepare_record(record: dict[str, Any]) -> dict[str, Any]:
    turns = parse_transcript_turns(record.get("transcript_text", ""))
    student_turn_numbers = [
        turn["turn"]
        for turn in turns
        if turn["speaker"] == "Student"
    ]
    out = dict(record)
    out["transcript_turns"] = turns
    out["student_turn_numbers"] = student_turn_numbers
    out["parsed_n_turns"] = len(turns)
    out["parsed_n_student_turns"] = len(student_turn_numbers)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    n_records = 0
    n_empty = 0
    with args.input.open(encoding="utf-8") as f_in, args.output.open("w", encoding="utf-8") as f_out:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            prepared = prepare_record(record)
            if not prepared["transcript_turns"]:
                n_empty += 1
            f_out.write(json.dumps(prepared, ensure_ascii=False) + "\n")
            n_records += 1

    print(f"Wrote {n_records} numbered transcripts to {args.output}")
    print(f"Empty parsed transcripts: {n_empty}")


if __name__ == "__main__":
    main()
