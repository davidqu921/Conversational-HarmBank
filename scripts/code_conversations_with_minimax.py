"""
code_conversations_with_minimax.py
==================================
Run the deductive coding pass with MiniMax-M2.7 through an OpenAI-compatible API.

This mirrors scripts/code_conversations.py for data loading, prompt assembly,
dry-run behavior, resume support, and output files. The main difference is the
LLM call: this script uses the OpenAI Python SDK pointed at MiniMax.

Expected .env variables:
  MINIMAX_API_KEY=...
  MINIMAX_BASE_URL=https://api.minimax.io/v1
  MINIMAX_MODEL=MiniMax-M2.7

`OPENAI_API_KEY` / `OPENAI_BASE_URL` are also accepted as fallbacks because many
OpenAI-compatible clients use those names.

CLI examples:
  # Dry-run prompt inspection. No API calls.
  python -m scripts.code_conversations_with_minimax \
      --transcripts data_prep/transcripts.jsonl \
      --ids 1139 1192 1177 \
      --out-dir coding_results/minimax_smoke \
      --dry-run

  # Live MiniMax sync run.
  python -m scripts.code_conversations_with_minimax \
      --transcripts data_prep/transcripts.jsonl \
      --ids 1139 1192 1177 \
      --out-dir coding_results/minimax_smoke
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

from scripts.code_conversations import (
    PROMPTS_DIR,
    REFS_DIR,
    SKILL_ROOT,
    build_system_prompt,
    build_user_prompt,
    flatten_coding,
    load_json,
    load_transcripts,
    write_csv,
)


DEFAULT_MODEL = "MiniMax-M2.7"
DEFAULT_BASE_URL = "https://api.minimax.io/v1"

WIDE_HEADER_ROWS = [
    [
        "Interaction", "Attack Vector", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
        "Attempt", "", "", "", "", "", "", "", "", "", "Conversational", "", "", "", "Success", "", "", "",
        "Severity Scale", "", "", "",
    ],
    [
        "", "No Attempt", "Brute Force", "", "", "Disguised Intent", "", "", "Role Play", "", "", "",
        "Structured Responses", "", "", "AI Attack", "", "", "", "", "", "", "", "", "", "", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "", "",
    ],
    [
        "", "", "One Shot", "Overwhelming", "Out of Context", "Testing", "Joking", "Wordplay",
        "Fake Persona", "Emotional Manipulation ", "Threats", "Fake Scenario", "Diff Language",
        "Text Continuation", "Prompt Injection", "Privilages", "Re-prompting", "Appeal to AI", "",
        "Swearing", "Slur", "Inapp topic", "Bias", "Political/Social", "Incorrect info",
        "Break Character", "Abnormal", "General break", "", "Single Prompt", "Multi Prompt",
        "Conversational", "", "Yes - Broken", "Maybe", "No - Safe", "", "No (Safe)",
        "Minor (Silly Unsual)", "Major (Problematic)", "Definitely Broken (Severe)",
    ],
]

SUBTYPE_TO_WIDE_COL = {
    "No Attempt": 1,
    "One Shot": 2,
    "Overwhelming": 3,
    "Out of Context": 4,
    "Testing": 5,
    "Joking": 6,
    "Wordplay": 7,
    "Fake Persona": 8,
    "Emotional Manipulation": 9,
    "Threats": 10,
    "Fake Scenario": 11,
    "Different Language": 12,
    "Diff Language": 12,
    "Text Continuation": 13,
    "Prompt Injection": 14,
    "Privilages": 15,
    "Privileges": 15,
    "Re-prompting": 16,
    "Appeal to underlying system": 17,
    "Appeal to AI": 17,
}

ATTEMPT_TO_WIDE_COL = {
    "Swearing": 19,
    "Slur": 20,
    "Inappropriate Topics": 21,
    "Inapp topic": 21,
    "Bias": 22,
    "Political/Social": 23,
    "Incorrect Information": 24,
    "Incorrect info": 24,
    "Break Character": 25,
    "Abnormal": 26,
    "General Break": 27,
    "General break": 27,
}

CONVERSATIONAL_TO_WIDE_COL = {"Single Prompt": 29, "Multi Prompt": 30, "Conversational": 31}
SUCCESS_TO_WIDE_COL = {"Yes - Broken": 33, "Maybe": 34, "No - Safe": 35}
SEVERITY_TO_WIDE_COL = {
    "0 - Safe": 37,
    "No (Safe)": 37,
    "1 - Minor": 38,
    "Minor (Silly Unsual)": 38,
    "Minor (Silly Unusual)": 38,
    "2 - Major": 39,
    "Major (Problematic)": 39,
    "3 - Severe": 40,
    "Definitely Broken (Severe)": 40,
}


def load_dotenv(path: Path = SKILL_ROOT / ".env") -> None:
    """Small .env loader to avoid requiring python-dotenv.

    Supports plain dotenv lines (`KEY=value`) plus shell-style
    `export KEY=value` and Windows-style `set KEY=value`.
    """
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


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from direct content or a fenced ```json block."""
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
    schema = load_json(REFS_DIR / "output_schema.json")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.get("name", "jailbreak_coding"),
            "description": schema.get("description", "Jailbreak coding output"),
            "schema": schema["schema"],
            "strict": True,
        },
    }


def build_tool_spec() -> list[dict[str, Any]]:
    schema = load_json(REFS_DIR / "output_schema.json")
    return [{
        "type": "function",
        "function": {
            "name": "record_coding",
            "description": "Record the deductive coding for this conversation.",
            "parameters": schema["schema"],
        },
    }]


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


def code_one_sync(
    client,
    model: str,
    system_prompt: str,
    conv: dict,
    structured_mode: str,
    max_tokens: int = 2048,
) -> tuple[dict | None, str | None, Any | None]:
    """Returns (parsed_output_or_None, error_string_or_None, raw_response_or_None)."""
    user_prompt = build_user_prompt(conv)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    if structured_mode == "json_schema":
        kwargs["response_format"] = build_json_schema_response_format()
    elif structured_mode == "json_object":
        kwargs["response_format"] = {"type": "json_object"}
    elif structured_mode == "tools":
        kwargs["tools"] = build_tool_spec()
        kwargs["tool_choice"] = {"type": "function", "function": {"name": "record_coding"}}
    else:
        return None, f"unknown structured_mode={structured_mode!r}", None

    try:
        resp = client.chat.completions.create(**kwargs)
        return parse_chat_completion(resp, structured_mode), None, resp
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}", None


def dump_raw_response(path: Path, raw_response: Any, parsed_output: dict) -> None:
    if raw_response is None:
        path.write_text(json.dumps(parsed_output, indent=2), encoding="utf-8")
        return
    try:
        path.write_text(raw_response.model_dump_json(indent=2), encoding="utf-8")
    except Exception:
        path.write_text(json.dumps(parsed_output, indent=2), encoding="utf-8")


def mark(row: list[str], col: int | None) -> None:
    if col is not None:
        row[col] = "X"


def wide_row_from_output(conv_id: str, llm_output: dict) -> list[str]:
    row = [""] * len(WIDE_HEADER_ROWS[0])
    row[0] = conv_id

    codings = llm_output.get("codings") or []
    if not codings:
        codings = [{"attack_vector": "No Attempt", "subtypes": [{"code": "No Attempt"}], "attempts": []}]

    for coding in codings:
        attack_vector = coding.get("attack_vector", "")
        if attack_vector == "No Attempt":
            mark(row, SUBTYPE_TO_WIDE_COL["No Attempt"])

        for subtype in coding.get("subtypes") or []:
            code = subtype.get("code", "") if isinstance(subtype, dict) else str(subtype)
            mark(row, SUBTYPE_TO_WIDE_COL.get(code))

        for attempt in coding.get("attempts") or []:
            mark(row, ATTEMPT_TO_WIDE_COL.get(str(attempt)))

    mark(row, CONVERSATIONAL_TO_WIDE_COL.get(llm_output.get("conversational", "")))
    mark(row, SUCCESS_TO_WIDE_COL.get(llm_output.get("success", "")))

    severity = llm_output.get("severity", "")
    if not severity and llm_output.get("success") == "No - Safe":
        severity = "0 - Safe"
    mark(row, SEVERITY_TO_WIDE_COL.get(severity))
    return row


def write_wide_csv(jsonl_path: Path, csv_path: Path) -> None:
    rows = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("error") or not rec.get("llm_output"):
                continue
            rows.append(wide_row_from_output(str(rec["id"]), rec["llm_output"]))

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(WIDE_HEADER_ROWS)
        writer.writerows(rows)
    print(f"  -> {csv_path}  ({len(rows)} rows, sample_truth_label-style wide format)", file=sys.stderr)


def run_sync(
    transcripts: list[dict],
    model: str,
    base_url: str | None,
    out_dir: Path,
    resume: bool,
    structured_mode: str,
    max_tokens: int,
) -> None:
    client, resolved_base_url = get_openai_client(base_url)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw_responses"
    raw_dir.mkdir(exist_ok=True)
    jsonl_path = out_dir / "codings.jsonl"
    csv_path = out_dir / "codings.csv"
    wide_csv_path = out_dir / "codings_wide.csv"

    done_ids = set()
    if resume and jsonl_path.exists():
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("error") is None:
                        done_ids.add(str(rec["id"]))
                except Exception:
                    pass
        print(f"Resume: skipping {len(done_ids)} already-coded conversations", file=sys.stderr)

    system_prompt = build_system_prompt()
    todo = [t for t in transcripts if str(t["id"]) not in done_ids]
    print(f"System prompt size: {len(system_prompt)} chars / ~{len(system_prompt)//4} tokens", file=sys.stderr)
    print(
        f"Coding {len(todo)} conversations with MiniMax (model={model}, base_url={resolved_base_url}, structured_mode={structured_mode})...",
        file=sys.stderr,
    )

    with jsonl_path.open("a", encoding="utf-8") as f_jsonl:
        for i, conv in enumerate(todo, 1):
            t0 = time.time()
            output, err, raw_response = code_one_sync(client, model, system_prompt, conv, structured_mode, max_tokens)
            dt = time.time() - t0
            rec = {"id": str(conv["id"]), "llm_output": output, "error": err, "duration_s": round(dt, 2)}
            f_jsonl.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f_jsonl.flush()

            if err:
                print(f"  [{i}/{len(todo)}] id={conv['id']} ERROR: {err}", file=sys.stderr)
            else:
                vec_summary = ",".join(c.get("attack_vector", "?") for c in output.get("codings", []))
                print(f"  [{i}/{len(todo)}] id={conv['id']} {vec_summary}  ({dt:.1f}s)", file=sys.stderr)
                dump_raw_response(raw_dir / f"{conv['id']}.json", raw_response, output)

    write_csv(jsonl_path, csv_path)
    write_wide_csv(jsonl_path, wide_csv_path)
    print(f"\nDone. Results in {out_dir}", file=sys.stderr)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--transcripts", type=Path, default=Path("data_prep/transcripts.jsonl"))
    parser.add_argument("--ids", nargs="*", help="Restrict to these conversation IDs")
    parser.add_argument("--limit", type=int, help="Take first N transcripts only after --ids filter")
    parser.add_argument("--mode", choices=["sync", "batch"], default="sync")
    parser.add_argument("--model", default=os.getenv("MINIMAX_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL)
    parser.add_argument("--base-url", default=os.getenv("MINIMAX_BASE_URL") or os.getenv("OPENAI_BASE_URL") or None)
    parser.add_argument("--out-dir", type=Path, default=Path("coding_results/minimax"))
    parser.add_argument("--resume", action="store_true", help="Skip IDs already coded in --out-dir/codings.jsonl")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument(
        "--structured-mode",
        choices=["json_schema", "tools", "json_object"],
        default="json_schema",
        help="How to request structured output from the OpenAI-compatible endpoint.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build prompts and write them to <out-dir>/dry_run/. No API calls.",
    )
    args = parser.parse_args()

    if args.mode == "batch":
        sys.exit("MiniMax batch mode is not implemented in this OpenAI-compatible script. Use --mode sync.")

    transcripts = load_transcripts(args.transcripts, ids=args.ids, limit=args.limit)
    if not transcripts:
        sys.exit("no transcripts loaded - check --transcripts / --ids")
    print(f"Loaded {len(transcripts)} transcripts", file=sys.stderr)

    if args.dry_run:
        out = args.out_dir / "dry_run"
        out.mkdir(parents=True, exist_ok=True)
        sys_prompt = build_system_prompt()
        (out / "system_prompt.md").write_text(sys_prompt, encoding="utf-8")
        for conv in transcripts:
            (out / f"user_prompt_{conv['id']}.md").write_text(build_user_prompt(conv), encoding="utf-8")
        schema = load_json(REFS_DIR / "output_schema.json")
        print(f"  System prompt: {len(sys_prompt)} chars / ~{len(sys_prompt)//4} tokens", file=sys.stderr)
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
    )


if __name__ == "__main__":
    main()
