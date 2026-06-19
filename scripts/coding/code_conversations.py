"""
code_conversations.py
=====================
Run the deductive coding pass over a set of conversations.

Two modes:
  --mode sync   (default) — issue requests one at a time. Slower, more expensive,
                            but useful for small batches (<100) or while iterating
                            on the prompt. Live progress + immediate failures.
  --mode batch  — submit all conversations to Anthropic's Batch API in one job.
                  ~50% cheaper, but results come back asynchronously (~minutes to hours).
                  Best for full-corpus runs.

The system prompt and few-shot examples are loaded fresh from prompts/ each run, so
prompt edits take effect immediately with no code change.

Outputs (under --out-dir, default ./coding_results/):
  codings.jsonl   — one line per conversation: {id, llm_output (parsed JSON), error}
  codings.csv     — flat CSV in the same shape as truth-label exports (one row per
                    (conversation, attack_vector) entry) for direct comparison
                    with human coding via evaluate.py.
  raw_responses/  — for sync mode, full API responses dumped as <id>.json (debug)

CLI examples:
  # Code 10 conversations sync (for iteration)
  python -m scripts.coding.code_conversations \\
      --transcripts data_prep/transcripts.jsonl \\
      --ids 1139 1192 1454 1479 1177 1317 1733 1356 1131 1189 \\
      --mode sync --out-dir coding_results/iter1

  # Code everything via batch API
  python -m scripts.coding.code_conversations \\
      --transcripts data_prep/transcripts.jsonl \\
      --mode batch --out-dir coding_results/full_run
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

# All paths are relative to the skill root (the directory that contains SKILL.md, prompts/, scripts/, references/).
SKILL_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = SKILL_ROOT / "prompts"
REFS_DIR = SKILL_ROOT / "references"

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"  # update as needed; passed via --model

# ----------------------- Prompt assembly -----------------------

def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def render_few_shots(examples: list[dict]) -> str:
    """Render few-shot examples as a compact, model-readable block.

    We use a simple textual format (rather than alternating user/assistant turns)
    because (a) it composes cleanly with the system prompt template's
    {{FEW_SHOT_EXAMPLES}} slot, and (b) it makes prompt edits easier — you can
    add/remove examples by editing prompts/few_shot_examples.json without
    threading them through API turn structures.
    """
    parts = []
    for i, ex in enumerate(examples, 1):
        parts.append(f"## Example {i} (conversation_id={ex['conversation_id']})")
        parts.append("Transcript:")
        parts.append(ex["transcript"])
        parts.append("Expected JSON output:")
        parts.append(json.dumps(ex["expected_output"], indent=2))
        parts.append("")
    return "\n".join(parts)


def build_system_prompt() -> str: # System Prompts need three components: 
                                #the system instructions, the codebook reference, 
                                #and the few-shot examples. We load these from separate 
                                #files for modularity and ease of editing.
    template = load_text(PROMPTS_DIR / "coding_system.md")
    codebook = load_text(REFS_DIR / "codebook.md")
    examples = load_json(PROMPTS_DIR / "few_shot_examples.json")
    rendered_examples = render_few_shots(examples)
    return template.replace("{{CODEBOOK}}", codebook).replace("{{FEW_SHOT_EXAMPLES}}", rendered_examples)


def build_user_prompt(conv: dict) -> str:  # The user prompt consists of a template with slots
                                           # for the conversation ID, an optional reporter note 
                                           # (the student's own description of the issue, which may be blank), 
                                           # and the transcript text. 
                                           # We load the template from prompts/coding_user_template.md 
                                           # and fill in the slots with data from the conversation record.
    template = load_text(PROMPTS_DIR / "coding_user_template.md")
    report = conv.get("report", "").strip()
    optional_report = f"Reporter note (the student's own description, may be blank): {report}\n" if report else ""
    return (
        template
        .replace("{{CONVERSATION_ID}}", str(conv["id"]))
        .replace("{{OPTIONAL_REPORT}}", optional_report)
        .replace("{{TRANSCRIPT}}", conv["transcript_text"])
    )


# ----------------------- Transcript loading -----------------------

def load_transcripts(path: Path, ids: list[str] | None = None, limit: int | None = None) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            t = json.loads(line)
            if ids is not None and str(t["id"]) not in ids:
                continue
            out.append(t)
            if limit is not None and len(out) >= limit:
                break
    return out


# ----------------------- Output flattening -----------------------

def flatten_coding(conv_id: str, llm_output: dict) -> list[dict]:
    """Convert one LLM-output dict into rows that mirror the evaluation schema."""
    rows = []
    codings = llm_output.get("codings", [])
    if not codings:
        codings = [{"attack_vector": "No Attempt", "subtypes": [{"code": "No Attempt"}], "attempts": []}]
    for c in codings:
        vec = c.get("attack_vector", "")
        subtypes = c.get("subtypes") or ([{"code": "No Attempt"}] if vec == "No Attempt" else [{"code": ""}])
        attempts = c.get("attempts") or [""]
        # Cartesian product is the most faithful flat representation: a coding
        # entry with N subtypes and M attempts becomes N*M rows. For multi-label
        # eval, evaluate.py treats per-label presence rather than tuples.
        for sub in subtypes:
            sub_code = sub.get("code", "") if isinstance(sub, dict) else str(sub)
            sub_note = sub.get("discovery_note", "") if isinstance(sub, dict) else ""
            for att in attempts:
                rows.append({
                    "id": conv_id,
                    "attack_vector": vec,
                    "subtype": sub_code,
                    "discovery_note": sub_note,
                    "attempt": att if att else "",
                    "conversational": llm_output.get("conversational", ""),
                    "success": llm_output.get("success", ""),
                    "severity": llm_output.get("severity", ""),
                    "reasoning": llm_output.get("reasoning", ""),
                })
    return rows


# ----------------------- Sync mode -----------------------

def code_one_sync(client, model: str, system_prompt: str, conv: dict, max_tokens: int = 2048) -> tuple[dict | None, str | None]:
    """Returns (parsed_output_or_None, error_string_or_None)."""
    user_prompt = build_user_prompt(conv)
    schema = load_json(REFS_DIR / "output_schema.json")
    try:
        # Use tool-use to enforce schema. The "record_coding" tool's input_schema
        # mirrors output_schema.json; the model must return one tool_use block.
        tools = [{
            "name": "record_coding",
            "description": "Record the deductive coding for this conversation.",
            "input_schema": schema["schema"],
        }]
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=tools,
            tool_choice={"type": "tool", "name": "record_coding"},
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Extract the tool_use block
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "record_coding":
                return block.input, None
        return None, f"no tool_use in response: {resp.content!r}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def run_sync(transcripts: list[dict], model: str, out_dir: Path, resume: bool):
    import anthropic
    client = anthropic.Anthropic()
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw_responses"
    raw_dir.mkdir(exist_ok=True)
    jsonl_path = out_dir / "codings.jsonl"
    csv_path = out_dir / "codings.csv"

    # Resume support: skip IDs already in jsonl_path
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
    print(f"System prompt size: {len(system_prompt)} chars / ~{len(system_prompt)//4} tokens", file=sys.stderr)

    todo = [t for t in transcripts if str(t["id"]) not in done_ids]
    print(f"Coding {len(todo)} conversations (sync, model={model})...", file=sys.stderr)

    # Collect all rows for CSV at end (re-read everything to include resumed)
    with jsonl_path.open("a", encoding="utf-8") as f_jsonl:
        for i, conv in enumerate(todo, 1):
            t0 = time.time()
            output, err = code_one_sync(client, model, system_prompt, conv)
            dt = time.time() - t0
            rec = {"id": str(conv["id"]), "llm_output": output, "error": err, "duration_s": round(dt, 2)}
            f_jsonl.write(json.dumps(rec) + "\n")
            f_jsonl.flush()
            if err:
                print(f"  [{i}/{len(todo)}] id={conv['id']} ERROR: {err}", file=sys.stderr)
            else:
                vec_summary = ",".join(c.get("attack_vector", "?") for c in output.get("codings", []))
                print(f"  [{i}/{len(todo)}] id={conv['id']} {vec_summary}  ({dt:.1f}s)", file=sys.stderr)
                # Save raw response
                with (raw_dir / f"{conv['id']}.json").open("w") as fr:
                    json.dump(output, fr, indent=2)

    # Build CSV from all jsonl records
    write_csv(jsonl_path, csv_path)
    print(f"\nDone. Results in {out_dir}", file=sys.stderr)


# ----------------------- Batch mode -----------------------

def run_batch(transcripts: list[dict], model: str, out_dir: Path):
    import anthropic
    client = anthropic.Anthropic()
    out_dir.mkdir(parents=True, exist_ok=True)
    system_prompt = build_system_prompt()
    schema = load_json(REFS_DIR / "output_schema.json")
    tools = [{
        "name": "record_coding",
        "description": "Record the deductive coding for this conversation.",
        "input_schema": schema["schema"],
    }]

    requests = []
    for conv in transcripts:
        requests.append({
            "custom_id": f"conv-{conv['id']}",
            "params": {
                "model": model,
                "max_tokens": 2048,
                "system": system_prompt,
                "tools": tools,
                "tool_choice": {"type": "tool", "name": "record_coding"},
                "messages": [{"role": "user", "content": build_user_prompt(conv)}],
            },
        })

    print(f"Submitting batch of {len(requests)} requests...", file=sys.stderr)
    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id}", file=sys.stderr)
    print(f"  Status: {batch.processing_status}", file=sys.stderr)

    # Save batch ID for later retrieval
    (out_dir / "batch_id.txt").write_text(batch.id)
    print(f"\nBatch submitted. Check status with:", file=sys.stderr)
    print(f"  python -m scripts.coding.code_conversations --retrieve-batch {batch.id} --out-dir {out_dir}", file=sys.stderr)


def retrieve_batch(batch_id: str, out_dir: Path):
    import anthropic
    client = anthropic.Anthropic()
    out_dir.mkdir(parents=True, exist_ok=True)
    batch = client.messages.batches.retrieve(batch_id)
    print(f"Batch {batch_id}: status={batch.processing_status}", file=sys.stderr)
    if batch.processing_status != "ended":
        print("  Not done yet. Try again later.", file=sys.stderr)
        return

    jsonl_path = out_dir / "codings.jsonl"
    csv_path = out_dir / "codings.csv"
    n_ok = n_err = 0
    with jsonl_path.open("w", encoding="utf-8") as f:
        for result in client.messages.batches.results(batch_id):
            cid = result.custom_id.replace("conv-", "")
            rec = {"id": cid, "llm_output": None, "error": None}
            if result.result.type == "succeeded":
                msg = result.result.message
                for block in msg.content:
                    if getattr(block, "type", None) == "tool_use" and block.name == "record_coding":
                        rec["llm_output"] = block.input
                        break
                if rec["llm_output"] is None:
                    rec["error"] = "no tool_use block"
                    n_err += 1
                else:
                    n_ok += 1
            else:
                rec["error"] = f"{result.result.type}: {result.result}"
                n_err += 1
            f.write(json.dumps(rec) + "\n")
    print(f"Wrote {n_ok} successful + {n_err} failed records to {jsonl_path}", file=sys.stderr)
    write_csv(jsonl_path, csv_path)


# ----------------------- CSV writing -----------------------

def write_csv(jsonl_path: Path, csv_path: Path):
    import csv as _csv
    rows = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("error") or not rec.get("llm_output"):
                continue
            rows.extend(flatten_coding(rec["id"], rec["llm_output"]))
    fieldnames = ["id", "attack_vector", "subtype", "discovery_note", "attempt", "conversational", "success", "severity", "reasoning"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  -> {csv_path}  ({len(rows)} rows)", file=sys.stderr)


# ----------------------- CLI -----------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcripts", type=Path, default=Path("data_prep/transcripts.jsonl"))
    ap.add_argument("--ids", nargs="*", help="Restrict to these conversation IDs")
    ap.add_argument("--limit", type=int, help="Take first N transcripts only (after --ids filter)")
    ap.add_argument("--mode", choices=["sync", "batch"], default="sync")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out-dir", type=Path, default=Path("coding_results"))
    ap.add_argument("--resume", action="store_true", help="(sync only) skip IDs already coded in --out-dir/codings.jsonl")
    ap.add_argument("--retrieve-batch", help="(batch only) retrieve completed batch by ID")
    ap.add_argument("--dry-run", action="store_true",
                    help="Build prompts and write them to <out-dir>/dry_run/ for inspection. No API calls.")
    args = ap.parse_args()

    if args.retrieve_batch:
        retrieve_batch(args.retrieve_batch, args.out_dir)
        return

    transcripts = load_transcripts(args.transcripts, ids=args.ids, limit=args.limit)
    if not transcripts:
        sys.exit("no transcripts loaded — check --transcripts / --ids")
    print(f"Loaded {len(transcripts)} transcripts", file=sys.stderr)

    if args.dry_run:
        out = args.out_dir / "dry_run"
        out.mkdir(parents=True, exist_ok=True)
        sys_prompt = build_system_prompt()
        (out / "system_prompt.md").write_text(sys_prompt)
        for conv in transcripts:
            (out / f"user_prompt_{conv['id']}.md").write_text(build_user_prompt(conv))
        # Validate schema
        schema = load_json(REFS_DIR / "output_schema.json")
        print(f"  System prompt: {len(sys_prompt)} chars / ~{len(sys_prompt)//4} tokens", file=sys.stderr)
        print(f"  Wrote {len(transcripts)} user prompts to {out}/", file=sys.stderr)
        print(f"  Output schema has {len(schema['schema']['properties'])} top-level fields", file=sys.stderr)
        # Validate few-shot examples conform to schema (quick check)
        try:
            import jsonschema  # type: ignore
            examples = load_json(PROMPTS_DIR / "few_shot_examples.json")
            for ex in examples:
                jsonschema.validate(ex["expected_output"], schema["schema"])
            print(f"  All {len(examples)} few-shot examples validate against schema", file=sys.stderr)
        except ImportError:
            print(f"  (skipping few-shot schema validation — pip install jsonschema to enable)", file=sys.stderr)
        except Exception as e:
            print(f"  WARN: few-shot example schema validation failed: {e}", file=sys.stderr)
        return

    if args.mode == "sync":
        run_sync(transcripts, args.model, args.out_dir, args.resume)
    else:
        run_batch(transcripts, args.model, args.out_dir)


if __name__ == "__main__":
    main()
