---
name: jailbreak-coder
description: Code student-vs-virtual-Steve conversations from the Virtual Steve / breakme-steve adversarial dataset along the project's jailbreak codebook (attack vectors, subtypes, attempt types, conversational style, success). Two-pass workflow — deductive coding against the fixed codebook, then optional inductive discovery of new candidate codes from "Other" notes — plus a Cohen's-κ + confusion-matrix + discrepancy-XLSX evaluation against human coders. Use this skill whenever the user wants to label, classify, code, or analyze the breakme-steve transcripts; whenever they mention attack vectors, jailbreak coding, the virtual Steve study, or comparing LLM coding to human coding; even when they describe the work without using those words ("can you go through these student conversations and tag what kind of attack each one is?"). Skill is modular — every label lives in references/codebook.md and every prompt lives in prompts/, both editable without touching code.
---

# Jailbreak Coder

This skill codes student-vs-virtual-Steve conversations from the breakme-steve adversarial dataset using the project's jailbreak codebook. It is built around a deductive-then-inductive workflow validated against multiple human coders.

## What this skill does

1. **Prepares data.** Reads raw transcripts (CSV) and the human-coding spreadsheet (XLSX); writes normalized JSONL/CSV for the rest of the pipeline. Identifies the IRR set (conversations coded by 3+ humans) used for validation.
2. **Codes conversations deductively.** For each conversation, calls Claude with the fixed codebook + few-shot examples + structured-output schema, producing one coding per conversation along five dimensions: attack vector, subtypes, attempt types, conversational style, success.
3. **Discovers new candidate codes inductively.** Clusters all `Other` notes into proposed new subtypes for human review. The codebook is never auto-modified.
4. **Evaluates against human coding.** Computes Cohen's κ per dimension and per label vs each human coder, generates confusion matrices, exports a discrepancy XLSX with full transcripts so a researcher can spot-check disagreements. Reports the human-vs-human IRR ceiling so the LLM's score has a reference point.

## When this skill triggers

- "Code these conversations / tag the attack vectors / classify these jailbreaks"
- "Run the LLM coder on the breakme transcripts"
- "Compare the LLM coding to the human coding / compute kappa / make confusion matrices"
- "Find any new attack patterns in the Other notes / discover new codes"
- Any request that names the dataset, the codebook, or the validation goal even if not in those exact words.

## Architecture (what to read when)

```
jailbreak-coder/
├── SKILL.md                       (this file — overview + how to run)
├── references/
│   ├── codebook.md                Single source of truth for all labels.
│   │                              Edit this to add/remove codes; no code change needed.
│   ├── methodology.md             Background and design rationale. Read when the user
│   │                              asks "why is the skill set up this way" or
│   │                              when considering structural changes.
│   └── output_schema.json         JSON Schema constraining the coding LLM's output.
│                                  Mirrors codebook.md.
├── prompts/                       The LLM-facing prompts. Edit freely; the scripts
│   ├── coding_system.md           reload them on every run.
│   ├── coding_user_template.md
│   ├── discovery_system.md
│   └── few_shot_examples.json     Hand-curated examples drawn from human-consensus IRR
│                                  conversations. The IDs here are also written to
│                                  evals/reserved_ids.json so they are excluded from
│                                  validation (no train/test leakage).
├── scripts/
│   ├── prepare_data.py            Loads transcripts + human coding -> normalized files.
│   ├── code_conversations.py      The coding pass. Sync mode for iteration, batch mode
│   │                              (50% cheaper) for full corpus runs.
│   ├── discover_codes.py          The discovery pass over 'Other' notes.
│   └── evaluate.py                κ, confusion matrices, discrepancy XLSX.
└── evals/
    └── reserved_ids.json          Conversation IDs reserved for few-shot. Held out
                                   from validation in evaluate.py.
```

## Standard end-to-end workflow

The user has supplied paths to the raw transcripts (`breakme-steve_transcripts.csv`) and the human-coding XLSX (`VirtualSteve Coding - Round 2.xlsx`). Run scripts from the skill root.

```bash
# 1) Prepare data (one-time per dataset version).
python -m scripts.prepare_data \
    --transcripts-csv "/path/to/breakme-steve_transcripts.csv" \
    --coding-xlsx     "/path/to/VirtualSteve Coding - Round 2.xlsx" \
    --out-dir         data_prep

# 2) Quick smoke test on a small slice (sync mode, fast iteration).
python -m scripts.code_conversations \
    --transcripts data_prep/transcripts.jsonl \
    --ids 1139 1192 1454 1479 1177 1317 1733 1356 1131 1189 \
    --mode sync --out-dir coding_results/smoke

# 3) Evaluate the smoke run vs human coders.
python -m scripts.evaluate \
    --llm-codings coding_results/smoke/codings.jsonl \
    --human-coding data_prep/ground_truth.csv \
    --transcripts data_prep/transcripts.jsonl \
    --out-dir evaluation/smoke

# 4) (Optional) Run the discovery pass to surface new candidate codes.
python -m scripts.discover_codes \
    --codings coding_results/smoke/codings.jsonl \
    --out coding_results/smoke/discovery_proposal.json

# 5) Once the agreement report looks good, run the full corpus via the Batch API.
python -m scripts.code_conversations \
    --transcripts data_prep/transcripts.jsonl \
    --mode batch --out-dir coding_results/full

# Wait for the batch to finish (status check):
python -m scripts.code_conversations --retrieve-batch BATCH_ID --out-dir coding_results/full

# Re-evaluate on the full set:
python -m scripts.evaluate \
    --llm-codings coding_results/full/codings.jsonl \
    --human-coding data_prep/ground_truth.csv \
    --transcripts data_prep/transcripts.jsonl \
    --out-dir evaluation/full
```

## How to extend the codebook

1. Add the new code under the right dimension in `references/codebook.md` with a 1-sentence definition.
2. Add it to the appropriate enum/list in `references/output_schema.json` AND the matching constant in `scripts/evaluate.py` (`ATTACK_VECTORS`, `SUBTYPES`, etc.).
3. Re-run the coding pass. No prompt rewrite needed — the prompts render the codebook at runtime.
4. (Optional) Add 1–2 new few-shot examples to `prompts/few_shot_examples.json` covering the new code if it's subtle.

## How to revise the prompt without breaking validation

Edit `prompts/coding_system.md` or `prompts/coding_user_template.md`. Re-run `code_conversations.py` and `evaluate.py`. Compare the new agreement report side-by-side with the previous one — if κ moves significantly in either direction, the prompt change had real effect. If you change few-shot examples, also update `evals/reserved_ids.json` so the new example IDs are held out from validation.

## What "good enough" looks like

Recent literature on LLM-assisted thematic analysis (LATA 2025; multi-LLM reliability work, 2025) reports Cohen's κ in the **0.7–0.9 range** for deductive coding by frontier models against human raters — comparable to the human–human ceiling on the same data. Inspect the IRR section of the agreement report to see what the human ceiling is on this dataset; the LLM should approach but won't exceed it. If your κ is below ~0.5 on a dimension, that dimension's labels are probably either ambiguous in the codebook (clarify definitions or add examples) or genuinely hard to disambiguate from transcripts alone.

## Cost / time expectations

At Sonnet pricing with the Batch API (50% off): coding all ~1000 breakme transcripts is in the low-single-digit dollars and finishes within an hour. Sync mode for a 10-conversation smoke test takes about a minute and costs cents.

## Dependencies

```bash
pip install anthropic openpyxl
```

The Anthropic SDK reads `ANTHROPIC_API_KEY` from the environment.
