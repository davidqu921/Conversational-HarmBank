"""
Audit and repair success-attack turn-action fillback outputs.

The repair pass is intentionally scoped to success_attack fillback files. It:
  - collapses repeated attempts to one record per conversation, preferring the
    latest successful record;
  - sorts turns, removes extra non-student turns, and de-duplicates turns;
  - fills missing Student turns with a conservative phase-compatible heuristic;
  - coerces action labels so every turn action belongs to the human-reviewed
    phase span;
  - writes audit and remaining manual-review CSVs.

Outputs overwrite the canonical fillback files under conversation_seg/results_4/
success_attack and create a backup JSONL before rewriting.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.fill_back_turn_actions.fillback_success_turn_actions import (
    DEFAULT_OUT_DIR,
    DEFAULT_PHASE_CODING,
    DEFAULT_TRANSCRIPTS,
    ACTION_TO_PHASE,
    load_phase_coding,
    phrase_for_turn,
    write_turn_csv,
    write_validation_report,
)
from scripts.segmentation.segment_conversations_with_minimax import (
    get_transcript_turns,
    load_transcripts,
    normalize_action_label,
    student_turns,
)


AUDIT_FIELDS = [
    "id",
    "severity",
    "repair_type",
    "turn",
    "old_value",
    "new_value",
    "detail",
]


def compact(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def sort_id_key(conv_id: str) -> tuple[int, str]:
    return (int(conv_id), conv_id) if conv_id.isdigit() else (10**9, conv_id)


def audit_row(conv_id: str, severity: str, repair_type: str, turn: int | str, old: str, new: str, detail: str) -> dict[str, str]:
    return {
        "id": str(conv_id),
        "severity": severity,
        "repair_type": repair_type,
        "turn": str(turn),
        "old_value": old,
        "new_value": new,
        "detail": detail,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def choose_best_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    by_id: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for idx, record in enumerate(records):
        by_id[str(record.get("id"))].append((idx, record))

    chosen: list[dict[str, Any]] = []
    audit: list[dict[str, str]] = []
    for conv_id in sorted(by_id, key=sort_id_key):
        attempts = by_id[conv_id]
        successful = [(idx, record) for idx, record in attempts if record.get("error") is None and record.get("llm_output")]
        chosen_idx, chosen_record = (successful[-1] if successful else attempts[-1])
        chosen.append(chosen_record)
        if len(attempts) > 1:
            audit.append(audit_row(
                conv_id,
                "info",
                "dedupe_records",
                "",
                str(len(attempts)),
                "1",
                f"kept line {chosen_idx + 1}; preferred latest successful attempt when available",
            ))
    return chosen, audit


def action_for_phase_from_text(phase: str, text: str) -> str:
    lower = text.lower()
    if phase == "Setup":
        if re.search(r"\b(hi|hello|hey|morning|steve)\b", lower) and len(lower.split()) <= 8:
            return "Benign Opening"
        if "?" in text or re.search(r"\b(what|why|how|can you|could you|explain|mean)\b", lower):
            return "Clarification Request"
        if re.search(r"\b(class|course|assignment|academic|research|study|understand|learn|homework)\b", lower):
            return "Educational Framing"
        return "Casual Conversation"

    if phase == "Trust Building":
        if re.search(r"\b(professor|teacher|university|school|admin|administrator|official|researcher|statement|email)\b", lower):
            return "Authority Claim"
        if re.search(r"\b(permission|allowed|approved|authorized|authorize)\b", lower):
            return "Permission Claim"
        if re.search(r"\b(friend|grandma|grandfather|mother|father|family|my story|when i)\b", lower):
            return "Personal Anecdote"
        return "Emotional Pressure"

    if phase == "Attack Construction":
        if re.search(r"\b(pretend|act as|role|persona|you are|from now on)\b", lower):
            return "Roleplay Setup"
        if re.search(r"\b(story|fiction|novel|movie|game|character|scenario)\b", lower):
            return "Fictional Scenario"
        if re.search(r"\b(translate|spell|rewrite|encode|decode|base64|backward|opposite day|opposite)\b", lower):
            return "Translation / Transformation"
        if re.search(r"\b(only|format|list|example|say|answer|words|specific)\b", lower):
            return "Response Format Control"
        return "Hypothetical Framing"

    if phase == "Escalation":
        if re.search(r"\b(switching gears|different|another topic|else)\b", lower):
            return "Topic Shift"
        if re.search(r"\b(more|stronger|further|again|keep|continue|no\.|but|try)\b", lower):
            return "Persistence After Refusal"
        return "Incremental Escalation"

    if phase == "Goal Execution":
        if re.search(r"\b(system prompt|hidden|instructions|rules|policy|memory)\b", lower):
            return "System Prompt Extraction"
        if re.search(r"\b(ignore|bypass|override|disable|break safety|jailbreak)\b", lower):
            return "Safety Override Request"
        if re.search(r"\b(ai|model|tool|capability|person|human|allowed|can you see)\b", lower):
            return "Identity / Capability Probing"
        return "Restricted Content Request"

    return ""


def canonical_turn(
    conv_id: str,
    turn_num: int,
    text: str,
    phase_by_id: dict[str, list[dict[str, Any]]],
    action: str,
    audit: list[dict[str, str]],
    detail_prefix: str,
) -> dict[str, Any] | None:
    phrase = phrase_for_turn(phase_by_id[conv_id], turn_num)
    if phrase is None:
        audit.append(audit_row(conv_id, "manual", "missing_reviewed_phase", turn_num, action, "", "student turn has no reviewed phrase span"))
        return None

    normalized_action = normalize_action_label(action)
    if normalized_action not in ACTION_TO_PHASE:
        repaired = action_for_phase_from_text(phrase["phase"], text)
        audit.append(audit_row(conv_id, "warning", "invalid_action_repaired", turn_num, normalized_action, repaired, detail_prefix))
        normalized_action = repaired

    if ACTION_TO_PHASE.get(normalized_action) != phrase["phase"]:
        repaired = action_for_phase_from_text(phrase["phase"], text)
        audit.append(audit_row(
            conv_id,
            "warning",
            "action_phase_mismatch_repaired",
            turn_num,
            normalized_action,
            repaired,
            f"{detail_prefix}; fixed phase={phrase['phase']}",
        ))
        normalized_action = repaired

    return {
        "turn": turn_num,
        "text": text,
        "phase": phrase["phase"],
        "action": normalized_action,
        "phrase_index": phrase["phrase_index"],
        "phrase_turns": phrase["turns"],
    }


def repair_record(
    record: dict[str, Any],
    conv: dict[str, Any],
    phase_by_id: dict[str, list[dict[str, Any]]],
    audit: list[dict[str, str]],
) -> dict[str, Any]:
    conv_id = str(record.get("id"))
    expected_turns = [int(turn["turn"]) for turn in student_turns(get_transcript_turns(conv))]
    text_by_turn = {int(turn["turn"]): turn["text"] for turn in student_turns(get_transcript_turns(conv))}

    if record.get("error") or not record.get("llm_output"):
        audit.append(audit_row(conv_id, "manual", "api_error_unrepaired", "", str(record.get("error") or ""), "", "no successful model output to repair"))
        return record

    raw_turns = record.get("llm_output", {}).get("turns", [])
    by_turn: dict[int, dict[str, Any]] = {}
    seen_counts: Counter = Counter()
    for item in raw_turns:
        try:
            turn_num = int(item.get("turn"))
        except (TypeError, ValueError):
            audit.append(audit_row(conv_id, "warning", "dropped_invalid_turn_number", "", str(item.get("turn")), "", "turn number was not an integer"))
            continue
        if turn_num not in expected_turns:
            audit.append(audit_row(conv_id, "warning", "dropped_extra_turn", turn_num, str(item.get("action", "")), "", "turn is not an expected Student turn"))
            continue
        seen_counts[turn_num] += 1
        if turn_num in by_turn:
            audit.append(audit_row(conv_id, "warning", "dropped_duplicate_turn", turn_num, str(item.get("action", "")), str(by_turn[turn_num].get("action", "")), "kept first valid occurrence"))
            continue
        by_turn[turn_num] = item

    repaired_turns: list[dict[str, Any]] = []
    for turn_num in expected_turns:
        source_item = by_turn.get(turn_num)
        if source_item is None:
            phrase = phrase_for_turn(phase_by_id[conv_id], turn_num)
            if phrase is None:
                audit.append(audit_row(conv_id, "manual", "missing_turn_no_phase", turn_num, "", "", "missing turn and no reviewed phrase span"))
                continue
            inferred = action_for_phase_from_text(phrase["phase"], text_by_turn[turn_num])
            audit.append(audit_row(conv_id, "warning", "missing_turn_filled", turn_num, "", inferred, "filled with phase-compatible heuristic"))
            source_action = inferred
        else:
            source_action = str(source_item.get("action", ""))

        repaired = canonical_turn(
            conv_id,
            turn_num,
            text_by_turn[turn_num],
            phase_by_id,
            source_action,
            audit,
            "canonicalized from fillback output",
        )
        if repaired is not None:
            repaired_turns.append(repaired)

    old_order = [item.get("turn") for item in raw_turns]
    new_order = [item["turn"] for item in repaired_turns]
    if old_order != new_order:
        audit.append(audit_row(conv_id, "info", "turns_sorted_or_completed", "", "; ".join(map(str, old_order)), "; ".join(map(str, new_order)), "turn list rewritten in expected Student-turn order"))

    repaired_record = dict(record)
    repaired_record["error"] = None
    repaired_record["llm_output"] = {
        "conversation_id": conv_id,
        "turns": repaired_turns,
    }
    repaired_record["repaired"] = True
    return repaired_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair success-attack fillback outputs and write audit reports.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--transcripts", type=Path, default=DEFAULT_TRANSCRIPTS)
    parser.add_argument("--phase-coding", type=Path, default=DEFAULT_PHASE_CODING)
    parser.add_argument("--dry-run", action="store_true", help="Only write audit/manual reports; do not overwrite fillback jsonl/csv.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    jsonl_path = args.out_dir / "fillback_segmentations.jsonl"
    audit_path = args.out_dir / "fillback_repair_audit.csv"
    manual_path = args.out_dir / "fillback_manual_review.csv"
    backup_path = args.out_dir / "fillback_segmentations.pre_repair_backup.jsonl"

    phase_by_id = load_phase_coding(args.phase_coding)
    transcripts = load_transcripts(args.transcripts, ids=list(phase_by_id))
    transcript_by_id = {str(conv["id"]): conv for conv in transcripts}
    records = read_jsonl(jsonl_path)
    chosen_records, audit = choose_best_records(records)

    repaired_records: list[dict[str, Any]] = []
    for record in chosen_records:
        conv_id = str(record.get("id"))
        conv = transcript_by_id.get(conv_id)
        if conv is None:
            audit.append(audit_row(conv_id, "manual", "missing_transcript", "", "", "", "cannot repair without transcript"))
            repaired_records.append(record)
            continue
        repaired_records.append(repair_record(record, conv, phase_by_id, audit))

    manual_rows = [row for row in audit if row["severity"] == "manual"]
    audit.sort(key=lambda row: (sort_id_key(row["id"]), row["severity"], row["repair_type"], row["turn"]))
    manual_rows.sort(key=lambda row: (sort_id_key(row["id"]), row["repair_type"], row["turn"]))
    write_csv(audit_path, audit, AUDIT_FIELDS)
    write_csv(manual_path, manual_rows, AUDIT_FIELDS)

    if not args.dry_run:
        if jsonl_path.exists() and not backup_path.exists():
            shutil.copy2(jsonl_path, backup_path)
        repaired_records.sort(key=lambda record: sort_id_key(str(record.get("id"))))
        write_jsonl(jsonl_path, repaired_records)
        write_turn_csv(jsonl_path, args.out_dir / "fillback_turn_segments.csv")
        write_validation_report(jsonl_path, transcripts, phase_by_id, args.out_dir / "fillback_validation_report.csv")

    print(f"Read {len(records)} raw records")
    print(f"Kept {len(chosen_records)} one-per-ID records")
    print(f"Audit rows: {len(audit)} -> {audit_path}")
    print(f"Manual rows: {len(manual_rows)} -> {manual_path}")
    if args.dry_run:
        print("Dry run: fillback files were not overwritten")
    else:
        print(f"Rewrote {jsonl_path}")
        print(f"Backup: {backup_path}")


if __name__ == "__main__":
    main()
