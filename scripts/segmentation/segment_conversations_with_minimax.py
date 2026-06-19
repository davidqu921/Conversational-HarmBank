"""
segment_conversations_with_minimax.py
=====================================
Segment student-vs-virtual-Steve conversations into user-turn actions with
MiniMax-M2.7 through an OpenAI-compatible API. Phase labels and phase spans are
derived deterministically from the model's per-user-turn action labels.

This is intentionally separate from the whole-conversation jailbreak coder so
the phase/action segmentation prompt can evolve without disturbing the earlier
coding pipeline.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEG_DIR = PROJECT_ROOT / "conversation_seg"
RAW_CAB_DIR = PROJECT_ROOT / "raw_cab"
DEFAULT_TRANSCRIPTS = SEG_DIR / "numbered_transcripts.jsonl"
DEFAULT_MODEL = "MiniMax-M2.7"
DEFAULT_BASE_URL = "https://api.minimax.io/v1"
VALID_PHASES = {
    "Setup",
    "Trust Building",
    "Reconnaissance",
    "Attack Construction",
    "Escalation",
    "Goal Execution",
}


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        elif line.lower().startswith("set "):
            line = line[len("set "):].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_transcripts(path: Path, ids: list[str] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    id_set = set(ids) if ids is not None else None
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if id_set is not None and str(rec["id"]) not in id_set:
                continue
            out.append(rec)
            if limit is not None and len(out) >= limit:
                break
    return out


def load_ids_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"missing ID list: {path}")
    ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        conv_id = line.strip()
        if conv_id:
            ids.append(conv_id)
    if not ids:
        raise ValueError(f"ID list is empty: {path}")
    return ids


def resolve_segmentation_pool(args: argparse.Namespace) -> tuple[list[str] | None, Path | None, str | None]:
    """Resolve one of the raw_cab segmentation-pool shortcuts."""
    pools = [
        (
            args.seg_success_attack,
            "success_attack",
            RAW_CAB_DIR / "success_attack" / "ids.txt",
            SEG_DIR / "results_2" / "success_attack",
        ),
        (
            args.seg_unsuccess_attack,
            "unsuccess_attack",
            RAW_CAB_DIR / "unsuccess_attack" / "ids.txt",
            SEG_DIR / "results_2" / "unsuccess_attack",
        ),
        (
            args.seg_no_attack,
            "no_attack",
            RAW_CAB_DIR / "no_attack" / "ids.txt",
            SEG_DIR / "results_2" / "no_attack",
        ),
    ]
    selected = [(name, ids_path, out_dir) for enabled, name, ids_path, out_dir in pools if enabled]
    if not selected:
        return None, None, None
    name, ids_path, out_dir = selected[0]
    return load_ids_file(ids_path), out_dir, name


TURN_RE = re.compile(r"^(Steve|Student):\s*(.*)$")

ACTION_CODE_TO_NAME = {
    "A1": "Benign Opening",
    "A2": "Course-related Question",
    "A3": "Casual Conversation",
    "A4": "Clarification Request",
    "B1": "Authority Claim",
    "B2": "Permission Claim",
    "B3": "Educational Framing",
    "B4": "Emotional Pressure",
    "B5": "Personal Anecdote",
    "C1": "Boundary Probing",
    "C2": "Identity / Capability Probing",
    "D1": "Roleplay Setup",
    "D2": "Hypothetical Framing",
    "D3": "Fictional Scenario",
    "D4": "Translation / Transformation",
    "D5": "Response Format Control",
    "E1": "Incremental Escalation",
    "E2": "Persistence After Refusal",
    "E3": "Topic Shift",
    "F1": "System Prompt Extraction",
    "F2": "Restricted Content Request",
    "F3": "Safety Override Request",
}

ACTION_TO_PHASE = {
    "Benign Opening": "Setup",
    "Course-related Question": "Setup",
    "Casual Conversation": "Setup",
    "Clarification Request": "Setup",
    "Authority Claim": "Trust Building",
    "Permission Claim": "Trust Building",
    "Educational Framing": "Trust Building",
    "Emotional Pressure": "Trust Building",
    "Personal Anecdote": "Trust Building",
    "Boundary Probing": "Reconnaissance",
    "Identity / Capability Probing": "Reconnaissance",
    "Roleplay Setup": "Attack Construction",
    "Hypothetical Framing": "Attack Construction",
    "Fictional Scenario": "Attack Construction",
    "Translation / Transformation": "Attack Construction",
    "Response Format Control": "Attack Construction",
    "Incremental Escalation": "Escalation",
    "Persistence After Refusal": "Escalation",
    "Topic Shift": "Escalation",
    "System Prompt Extraction": "Goal Execution",
    "Restricted Content Request": "Goal Execution",
    "Safety Override Request": "Goal Execution",
}
VALID_ACTIONS = set(ACTION_TO_PHASE)


def normalize_action_label(label: Any) -> str:
    label_text = str(label or "").strip()
    if not label_text:
        return ""
    if label_text in VALID_ACTIONS:
        return label_text
    if label_text in ACTION_CODE_TO_NAME:
        return ACTION_CODE_TO_NAME[label_text]
    code_match = re.match(r"^([A-F][1-5])\.\s*(.+)$", label_text)
    if code_match:
        code, name = code_match.groups()
        return ACTION_CODE_TO_NAME.get(code, name.strip())
    return label_text


def parse_transcript_turns(transcript_text: str) -> list[dict[str, Any]]:
    """Parse transcript text into numbered speaker turns.

    The normalized corpus stores conversations as lines beginning with
    `Steve:` or `Student:`. Continuation lines, if any, are appended to the
    previous speaker turn.
    """
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


def get_transcript_turns(conv: dict[str, Any]) -> list[dict[str, Any]]:
    turns = conv.get("transcript_turns")
    if isinstance(turns, list):
        normalized: list[dict[str, Any]] = []
        for item in turns:
            if not isinstance(item, dict):
                continue
            try:
                turn_num = int(item["turn"])
            except (KeyError, TypeError, ValueError):
                continue
            speaker = str(item.get("speaker", "")).strip()
            text = str(item.get("text", "")).strip()
            if speaker in {"Steve", "Student"}:
                normalized.append({"turn": turn_num, "speaker": speaker, "text": text})
        if normalized:
            return normalized
    return parse_transcript_turns(conv.get("transcript_text", ""))


def render_parsed_turns(turns: list[dict[str, Any]]) -> str:
    if not turns:
        return "(empty transcript)"
    return "\n".join(f'{t["turn"]}. {t["speaker"]}: {t["text"]}' for t in turns)


def student_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in turns if t["speaker"] == "Student"]


def get_student_turn_numbers(conv: dict[str, Any], turns: list[dict[str, Any]]) -> list[int]:
    raw_numbers = conv.get("student_turn_numbers")
    if isinstance(raw_numbers, list):
        out: list[int] = []
        for value in raw_numbers:
            try:
                out.append(int(value))
            except (TypeError, ValueError):
                pass
        if out:
            return out
    return [turn["turn"] for turn in student_turns(turns)]


def get_output_turns(output: dict[str, Any]) -> list[dict[str, Any]]:
    turns = output.get("turns")
    if isinstance(turns, list):
        return [turn for turn in turns if isinstance(turn, dict)]
    return []


def canonicalize_turn_labels(output: dict[str, Any]) -> None:
    canonical_turns: list[dict[str, Any]] = []
    for item in get_output_turns(output):
        action = normalize_action_label(item.get("action", ""))
        canonical = {
            "turn": item.get("turn"),
            "action": action,
            "phase": ACTION_TO_PHASE.get(action, ""),
        }
        canonical_turns.append(canonical)
    output["turns"] = canonical_turns


def backfill_user_turn_text(output: dict[str, Any], conv: dict[str, Any]) -> None:
    text_by_turn = {
        turn["turn"]: turn["text"]
        for turn in student_turns(get_transcript_turns(conv))
    }
    for item in get_output_turns(output):
        turn = item.get("turn")
        if turn in text_by_turn:
            item["text"] = text_by_turn[turn]


def unique_actions_for_turns(turns: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for turn in turns:
        action = normalize_action_label(turn.get("action", ""))
        if action and action not in seen:
            actions.append(action)
            seen.add(action)
    return actions


def derive_phase_segments(output: dict[str, Any]) -> list[dict[str, Any]]:
    """Build clean, non-overlapping phase spans from per-user-turn labels."""
    turns = get_output_turns(output)
    if not turns:
        return []

    spans: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_phase: str | None = None

    for turn in turns:
        phase = str(turn.get("phase", ""))
        if current and phase != current_phase:
            spans.append(current)
            current = []
        current.append(turn)
        current_phase = phase
    if current:
        spans.append(current)

    derived: list[dict[str, Any]] = []
    for span in spans:
        phase = str(span[0].get("phase", ""))
        start_turn = int(span[0].get("turn"))
        end_turn = int(span[-1].get("turn"))
        derived.append({
            "phase": phase,
            "start_turn": start_turn,
            "end_turn": end_turn,
            "actions": unique_actions_for_turns(span),
            "summary": f"User turns {start_turn}-{end_turn} are labeled as {phase}.",
        })
    return derived


def repair_segmentation_output(output: dict[str, Any], conv: dict[str, Any] | None = None) -> None:
    canonicalize_turn_labels(output)
    if conv is not None:
        output["conversation_id"] = str(conv["id"])
        backfill_user_turn_text(output, conv)
    output["phase_segments"] = derive_phase_segments(output)


def build_system_prompt() -> str:
    template = load_text(SEG_DIR / "segmentation_system.md")
    action_library = load_text(SEG_DIR / "conversation_action_library.md")
    return template.replace("{{ACTION_LIBRARY}}", action_library)


def build_user_prompt(conv: dict[str, Any]) -> str:
    template = load_text(SEG_DIR / "segmentation_user_template.md")
    turns = get_transcript_turns(conv)
    student_turn_numbers = get_student_turn_numbers(conv, turns)
    return (
        template
        .replace("{{PARSED_TURNS}}", render_parsed_turns(turns))
        .replace("{{STUDENT_TURN_NUMBERS}}", ", ".join(str(turn) for turn in student_turn_numbers))
    )


def get_openai_client(base_url: str | None):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Missing dependency: pip install openai") from exc

    load_dotenv()
    api_key = os.getenv("MINIMAX_API_KEY") or os.getenv("OPENAI_API_KEY")
    resolved_base_url = base_url or os.getenv("MINIMAX_BASE_URL") or os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL
    if not api_key:
        raise RuntimeError("Missing MINIMAX_API_KEY or OPENAI_API_KEY. Put it in .env or your environment.")
    return OpenAI(api_key=api_key, base_url=resolved_base_url), resolved_base_url


def build_json_schema_response_format() -> dict[str, Any]:
    schema = load_json(SEG_DIR / "segmentation_output_schema.json")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.get("name", "conversation_segmentation"),
            "description": schema.get("description", "Conversation segmentation output"),
            "schema": schema["schema"],
            "strict": True,
        },
    }


def build_tool_spec() -> list[dict[str, Any]]:
    schema = load_json(SEG_DIR / "segmentation_output_schema.json")
    return [{
        "type": "function",
        "function": {
            "name": "record_conversation_segmentation",
            "description": "Record user-turn action labels for this conversation.",
            "parameters": schema["schema"],
        },
    }]


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    candidates = [text]
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.append(fenced.group(1).strip())
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and first < last:
        candidates.append(text[first:last + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise ValueError(f"response did not contain a valid JSON object: {text[:500]!r}")


def parse_chat_completion(resp, structured_mode: str) -> dict[str, Any]:
    message = resp.choices[0].message
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        args = tool_calls[0].function.arguments
        return json.loads(args)
    content = message.content or ""
    if structured_mode in {"json_schema", "json_object"}:
        return extract_json_object(content)
    raise ValueError(f"no tool call in response: {message!r}")


def validation_summary(conv: dict[str, Any], rec: dict[str, Any]) -> dict[str, str]:
    output = rec.get("llm_output") or {}
    expected = student_turns(get_transcript_turns(conv))
    observed = get_output_turns(output)

    expected_turns = [t["turn"] for t in expected]
    observed_turns = [t.get("turn") for t in observed]

    missing_turns = [turn for turn in expected_turns if turn not in observed_turns]
    extra_turns = [turn for turn in observed_turns if turn not in expected_turns]
    duplicate_turns = sorted({turn for turn in observed_turns if observed_turns.count(turn) > 1}, key=str)
    out_of_order = observed_turns != expected_turns

    missing_backfilled_text_turns: list[Any] = []
    invalid_phase_turns: list[Any] = []
    invalid_action_turns: list[Any] = []
    empty_field_turns: list[Any] = []

    for item in observed:
        turn = item.get("turn")
        if turn in expected_turns and not item.get("text"):
            missing_backfilled_text_turns.append(turn)
        if item.get("phase") not in VALID_PHASES:
            invalid_phase_turns.append(turn)
        if normalize_action_label(item.get("action", "")) not in VALID_ACTIONS:
            invalid_action_turns.append(turn)
        required_fields = ["turn", "action"]
        if any(item.get(field) in (None, "") for field in required_fields):
            empty_field_turns.append(turn)

    api_error = rec.get("error") or ""
    issue_fields = [
        missing_turns,
        extra_turns,
        duplicate_turns,
        missing_backfilled_text_turns,
        invalid_phase_turns,
        invalid_action_turns,
        empty_field_turns,
    ]
    status = "ok"
    if api_error:
        status = "api_error"
    elif out_of_order or any(issue_fields):
        status = "needs_review"

    return {
        "id": str(rec.get("id", conv.get("id", ""))),
        "status": status,
        "api_error": str(api_error),
        "expected_user_turns": "; ".join(str(t) for t in expected_turns),
        "observed_user_turns": "; ".join(str(t) for t in observed_turns),
        "missing_turns": "; ".join(str(t) for t in missing_turns),
        "extra_turns": "; ".join(str(t) for t in extra_turns),
        "duplicate_turns": "; ".join(str(t) for t in duplicate_turns),
        "out_of_order": str(out_of_order),
        "missing_backfilled_text_turns": "; ".join(str(t) for t in missing_backfilled_text_turns),
        "invalid_phase_turns": "; ".join(str(t) for t in invalid_phase_turns),
        "invalid_action_turns": "; ".join(str(t) for t in invalid_action_turns),
        "empty_field_turns": "; ".join(str(t) for t in empty_field_turns),
    }


def write_validation_report(jsonl_path: Path, transcripts: list[dict[str, Any]], csv_path: Path) -> None:
    transcript_by_id = {str(conv["id"]): conv for conv in transcripts}
    fieldnames = [
        "id",
        "status",
        "api_error",
        "expected_user_turns",
        "observed_user_turns",
        "missing_turns",
        "extra_turns",
        "duplicate_turns",
        "out_of_order",
        "missing_backfilled_text_turns",
        "invalid_phase_turns",
        "invalid_action_turns",
        "empty_field_turns",
    ]
    rows: list[dict[str, str]] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            conv = transcript_by_id.get(str(rec.get("id")), {"id": rec.get("id"), "transcript_text": ""})
            rows.append(validation_summary(conv, rec))

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    needs_review = sum(1 for row in rows if row["status"] != "ok")
    print(f"  -> {csv_path} ({len(rows)} conversations, {needs_review} need review)", file=sys.stderr)


def segment_one_sync(
    client,
    model: str,
    system_prompt: str,
    conv: dict[str, Any],
    structured_mode: str,
    max_tokens: int,
    request_timeout: float,
) -> tuple[dict[str, Any] | None, str | None, Any | None]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_user_prompt(conv)},
    ]
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "timeout": request_timeout,
    }
    if structured_mode == "json_schema":
        kwargs["response_format"] = build_json_schema_response_format()
    elif structured_mode == "json_object":
        kwargs["response_format"] = {"type": "json_object"}
    elif structured_mode == "tools":
        kwargs["tools"] = build_tool_spec()
        kwargs["tool_choice"] = {"type": "function", "function": {"name": "record_conversation_segmentation"}}
    else:
        return None, f"unknown structured_mode={structured_mode!r}", None

    try:
        resp = client.chat.completions.create(**kwargs)
        output = parse_chat_completion(resp, structured_mode)
        repair_segmentation_output(output, conv)
        return output, None, resp
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}", None


def dump_raw_response(path: Path, raw_response: Any, parsed_output: dict[str, Any] | None) -> None:
    if raw_response is None:
        path.write_text(json.dumps(parsed_output, indent=2, ensure_ascii=False), encoding="utf-8")
        return
    try:
        path.write_text(raw_response.model_dump_json(indent=2), encoding="utf-8")
    except Exception:
        path.write_text(json.dumps(parsed_output, indent=2, ensure_ascii=False), encoding="utf-8")


def write_turn_csv(jsonl_path: Path, csv_path: Path) -> None:
    fieldnames = [
        "id",
        "turn",
        "text",
        "phase",
        "action",
    ]
    rows: list[dict[str, str]] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("error") or not rec.get("llm_output"):
                continue
            for turn in get_output_turns(rec["llm_output"]):
                rows.append({
                    "id": str(rec["id"]),
                    "turn": str(turn.get("turn", "")),
                    "text": turn.get("text", ""),
                    "phase": turn.get("phase", ""),
                    "action": turn.get("action", ""),
                })
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  -> {csv_path} ({len(rows)} user-turn rows)", file=sys.stderr)


def write_phase_csv(jsonl_path: Path, csv_path: Path) -> None:
    fieldnames = ["id", "phase", "start_turn", "end_turn", "actions", "summary"]
    rows: list[dict[str, str]] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("error") or not rec.get("llm_output"):
                continue
            for seg in rec["llm_output"].get("phase_segments", []):
                rows.append({
                    "id": str(rec["id"]),
                    "phase": seg.get("phase", ""),
                    "start_turn": str(seg.get("start_turn", "")),
                    "end_turn": str(seg.get("end_turn", "")),
                    "actions": "; ".join(seg.get("actions") or []),
                    "summary": seg.get("summary", ""),
                })
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  -> {csv_path} ({len(rows)} phase rows)", file=sys.stderr)


def repair_existing_outputs(out_dir: Path, transcripts: list[dict[str, Any]]) -> None:
    jsonl_path = out_dir / "segmentations.jsonl"
    if not jsonl_path.exists():
        raise FileNotFoundError(f"missing {jsonl_path}")

    transcript_by_id = {str(conv["id"]): conv for conv in transcripts}
    repaired_records: list[dict[str, Any]] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("llm_output"):
                conv = transcript_by_id.get(str(rec.get("id")))
                repair_segmentation_output(rec["llm_output"], conv)
            repaired_records.append(rec)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for rec in repaired_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    write_turn_csv(jsonl_path, out_dir / "turn_segments.csv")
    write_phase_csv(jsonl_path, out_dir / "phase_segments.csv")
    write_validation_report(jsonl_path, transcripts, out_dir / "validation_report.csv")
    print(f"Repaired {len(repaired_records)} records in {out_dir}", file=sys.stderr)


def run_sync(
    transcripts: list[dict[str, Any]],
    model: str,
    base_url: str | None,
    out_dir: Path,
    resume: bool,
    structured_mode: str,
    max_tokens: int,
    request_timeout: float,
) -> None:
    client, resolved_base_url = get_openai_client(base_url)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw_responses"
    raw_dir.mkdir(exist_ok=True)
    jsonl_path = out_dir / "segmentations.jsonl"

    done_ids: set[str] = set()
    if resume and jsonl_path.exists():
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("error") is None:
                        done_ids.add(str(rec["id"]))
                except Exception:
                    pass
        print(f"Resume: skipping {len(done_ids)} already-segmented conversations", file=sys.stderr)

    system_prompt = build_system_prompt()
    todo = [t for t in transcripts if str(t["id"]) not in done_ids]
    print(f"System prompt size: {len(system_prompt)} chars / ~{len(system_prompt)//4} tokens", file=sys.stderr)
    print(
        f"Segmenting {len(todo)} conversations (model={model}, base_url={resolved_base_url}, structured_mode={structured_mode})...",
        file=sys.stderr,
    )

    with jsonl_path.open("a", encoding="utf-8") as f_jsonl:
        for i, conv in enumerate(todo, 1):
            t0 = time.time()
            output, err, raw_response = segment_one_sync(
                client,
                model,
                system_prompt,
                conv,
                structured_mode,
                max_tokens,
                request_timeout,
            )
            dt = time.time() - t0
            rec = {"id": str(conv["id"]), "llm_output": output, "error": err, "duration_s": round(dt, 2)}
            f_jsonl.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f_jsonl.flush()
            if err:
                print(f"  [{i}/{len(todo)}] id={conv['id']} ERROR: {err}", file=sys.stderr)
            else:
                n_turns = len(get_output_turns(output)) if output else 0
                n_phases = len(output.get("phase_segments", [])) if output else 0
                print(f"  [{i}/{len(todo)}] id={conv['id']} {n_turns} user turns, {n_phases} phases ({dt:.1f}s)", file=sys.stderr)
            dump_raw_response(raw_dir / f"{conv['id']}.json", raw_response, output)

    write_turn_csv(jsonl_path, out_dir / "turn_segments.csv")
    write_phase_csv(jsonl_path, out_dir / "phase_segments.csv")
    write_validation_report(jsonl_path, transcripts, out_dir / "validation_report.csv")
    print(f"\nDone. Results in {out_dir}", file=sys.stderr)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcripts", type=Path, default=DEFAULT_TRANSCRIPTS)
    parser.add_argument("--ids", nargs="*", help="Restrict to these conversation IDs")
    parser.add_argument("--limit", type=int, help="Take first N transcripts only after --ids filter")
    parser.add_argument("--model", default=os.getenv("MINIMAX_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL)
    parser.add_argument("--base-url", default=os.getenv("MINIMAX_BASE_URL") or os.getenv("OPENAI_BASE_URL") or None)
    parser.add_argument("--out-dir", type=Path, help="Output directory. Defaults to conversation_seg/results/minimax, or the selected pool directory.")
    parser.add_argument("--resume", action="store_true", help="Skip IDs already segmented in --out-dir/segmentations.jsonl")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=180.0,
        help="Per-conversation API request timeout in seconds. Timed-out records are written as errors and can be retried with --resume.",
    )
    pool_group = parser.add_mutually_exclusive_group()
    pool_group.add_argument(
        "--seg-success-attack",
        action="store_true",
        help="Segment all IDs listed in raw_cab/success_attack/ids.txt and save under conversation_seg/results/success_attack.",
    )
    pool_group.add_argument(
        "--seg-unsuccess-attack",
        action="store_true",
        help="Segment all IDs listed in raw_cab/unsuccess_attack/ids.txt and save under conversation_seg/results/unsuccess_attack.",
    )
    pool_group.add_argument(
        "--seg-no-attack",
        action="store_true",
        help="Segment all IDs listed in raw_cab/no_attack/ids.txt and save under conversation_seg/results/no_attack.",
    )
    parser.add_argument(
        "--structured-mode",
        choices=["json_schema", "tools", "json_object"],
        default="json_schema",
        help="How to request structured output from the OpenAI-compatible endpoint.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build prompts and write them to <out-dir>/dry_run. No API calls.")
    parser.add_argument(
        "--repair-existing",
        action="store_true",
        help="Normalize an existing <out-dir>/segmentations.jsonl and regenerate CSV exports. No API calls.",
    )
    args = parser.parse_args()

    pool_ids, pool_out_dir, pool_name = resolve_segmentation_pool(args)
    if pool_ids is not None:
        if args.ids:
            sys.exit("Do not combine --ids with --seg-success-attack / --seg-unsuccess-attack / --seg-no-attack.")
        args.ids = pool_ids
        if args.out_dir is None:
            args.out_dir = pool_out_dir
        print(f"Loaded {len(args.ids)} IDs from raw_cab/{pool_name}/ids.txt", file=sys.stderr)
    elif args.out_dir is None:
        args.out_dir = Path("conversation_seg/results/minimax")

    transcripts = load_transcripts(args.transcripts, ids=args.ids, limit=args.limit)
    if not transcripts:
        sys.exit("no transcripts loaded - check --transcripts / --ids")
    print(f"Loaded {len(transcripts)} transcripts", file=sys.stderr)

    if args.repair_existing:
        repair_existing_outputs(args.out_dir, transcripts)
        return

    if args.dry_run:
        out = args.out_dir / "dry_run"
        out.mkdir(parents=True, exist_ok=True)
        system_prompt = build_system_prompt()
        (out / "system_prompt.md").write_text(system_prompt, encoding="utf-8")
        for conv in transcripts:
            (out / f"user_prompt_{conv['id']}.md").write_text(build_user_prompt(conv), encoding="utf-8")
        schema = load_json(SEG_DIR / "segmentation_output_schema.json")
        print(f"  System prompt: {len(system_prompt)} chars / ~{len(system_prompt)//4} tokens", file=sys.stderr)
        print(f"  Wrote {len(transcripts)} user prompts to {out}/", file=sys.stderr)
        print(f"  Output schema has {len(schema['schema']['properties'])} top-level fields", file=sys.stderr)
        print(f"  MiniMax model: {args.model}", file=sys.stderr)
        print(f"  Base URL: {args.base_url or os.getenv('MINIMAX_BASE_URL') or os.getenv('OPENAI_BASE_URL') or DEFAULT_BASE_URL}", file=sys.stderr)
        return

    run_sync(
        transcripts=transcripts,
        model=args.model,
        base_url=args.base_url,
        out_dir=args.out_dir,
        resume=args.resume,
        structured_mode=args.structured_mode,
        max_tokens=args.max_tokens,
        request_timeout=args.request_timeout,
    )


if __name__ == "__main__":
    main()
