"""
discover_codes.py
=================
Inductive discovery pass.

Reads a coding run (codings.jsonl) and pulls every subtype where code='Other'
(plus its discovery_note and the conversation it came from). Sends the bundle
to a single Claude call with prompts/discovery_system.md and asks the model
to cluster the notes into candidate new codes for human review.

The codebook is NEVER modified automatically — output is a JSON proposal.

CLI:
    python -m scripts.coding.discover_codes \\
        --codings coding_results/full_run/codings.jsonl \\
        --transcripts data_prep/transcripts.jsonl \\
        --out coding_results/full_run/discovery_proposal.json
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = SKILL_ROOT / "prompts"
REFS_DIR = SKILL_ROOT / "references"

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def collect_other_notes(codings_jsonl: Path) -> list[dict]:
    """Returns [{id, parent_vector, note}] for every subtype where code=='Other'."""
    out = []
    with codings_jsonl.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("error") or not rec.get("llm_output"):
                continue
            cid = rec["id"]
            for c in rec["llm_output"].get("codings", []):
                vec = c.get("attack_vector", "")
                for sub in c.get("subtypes") or []:
                    if isinstance(sub, dict) and sub.get("code") == "Other":
                        out.append({
                            "id": cid,
                            "parent_vector": vec,
                            "note": sub.get("discovery_note", ""),
                        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codings", required=True, type=Path)
    ap.add_argument("--transcripts", type=Path, help="(optional) transcripts.jsonl, used to enrich examples")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    notes = collect_other_notes(args.codings)
    print(f"Collected {len(notes)} 'Other' notes from {args.codings}", file=sys.stderr)
    if not notes:
        print("No 'Other' notes found — nothing to discover. Existing codebook covers all observed cases.", file=sys.stderr)
        args.out.write_text(json.dumps({"clusters": [], "summary": "No Other notes; codebook covers all observed cases."}, indent=2))
        return

    # Build the input bundle for the discovery prompt
    bundle_lines = ["# Other notes from the coding run\n"]
    for n in notes:
        bundle_lines.append(f"- conversation_id={n['id']} parent_vector={n['parent_vector']!r}: {n['note']}")
    bundle = "\n".join(bundle_lines)

    # Assemble system prompt
    system_template = (PROMPTS_DIR / "discovery_system.md").read_text(encoding="utf-8")
    codebook = (REFS_DIR / "codebook.md").read_text(encoding="utf-8")
    system_prompt = system_template.replace("{{CODEBOOK}}", codebook)

    import anthropic
    client = anthropic.Anthropic()
    print(f"Calling {args.model} for discovery (input {len(notes)} notes)...", file=sys.stderr)
    resp = client.messages.create(
        model=args.model,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": bundle}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")

    # Try to parse JSON from the response (model may wrap in ```json ... ```)
    parsed = None
    for candidate in (text, text.strip().removeprefix("```json").removesuffix("```").strip(),
                      text.strip().removeprefix("```").removesuffix("```").strip()):
        try:
            parsed = json.loads(candidate)
            break
        except Exception:
            pass

    if parsed is None:
        print("WARN: discovery response was not valid JSON; saving raw text", file=sys.stderr)
        args.out.write_text(text)
        return

    args.out.write_text(json.dumps(parsed, indent=2))
    print(f"Wrote {args.out}", file=sys.stderr)
    summary = parsed.get("summary", "")
    n_clusters = len(parsed.get("clusters", []))
    print(f"\n{n_clusters} candidate clusters proposed.", file=sys.stderr)
    if summary:
        print(f"Summary: {summary}", file=sys.stderr)


if __name__ == "__main__":
    main()
