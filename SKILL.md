---
name: jailbreak-coder
description: Code student-vs-virtual-Steve conversations from the breakme-steve adversarial dataset with the current jailbreak taxonomy: attack vector, attack vector type, attempt, conversational structure, success, and severity. Use this skill when labeling transcripts, running the LLM coder, comparing LLM labels to the current sample truth labels, or discovering candidate new attack types.
---

# Jailbreak Coder

This skill codes student-vs-virtual-Steve conversations from the breakme-steve adversarial dataset using the current project codebook. The present canonical human labels are in `data_prep/sample_truth_label.csv`; the older `data_prep/ground_truth.csv` was a pre-review draft and should not be used for current evaluation.

## What this skill does

1. **Codes conversations deductively.** Calls Claude with the fixed codebook, current few-shot examples, and structured-output schema.
2. **Outputs six dimensions.** Attack vector, attack vector type, attempt, conversational structure, successful jailbreak, and severity scale.
3. **Evaluates against current truth labels.** Compares LLM JSONL outputs to `data_prep/sample_truth_label.csv`, including severity, and exports agreement reports, confusion matrices, and discrepancy workbooks.
4. **Optionally discovers new candidate codes.** Clusters `Other` notes into proposed candidate types for human review. The codebook is never modified automatically.

## Current Data Sources

- `data_prep/transcripts.jsonl` - normalized transcript corpus, 1000 conversations.
- `data_prep/sample_truth_label.csv` - current post-review consensus truth labels, wide format with `X` marking labels.
- `data_prep/New_Codebook.csv` - source CSV used to update `references/codebook.md`.
- `references/codebook.md` - model-facing codebook rendered into the coding prompt.
- `references/output_schema.json` - required structured output, including `severity`.
- `prompts/few_shot_examples.json` - current few-shot examples selected from `sample_truth_label.csv`.

## Architecture

```text
jailbreak-coder/
+-- SKILL.md
+-- data_prep/
|   +-- transcripts.jsonl
|   +-- sample_truth_label.csv
|   +-- New_Codebook.csv
+-- references/
|   +-- codebook.md
|   +-- methodology.md
|   +-- output_schema.json
+-- prompts/
|   +-- coding_system.md
|   +-- coding_user_template.md
|   +-- discovery_system.md
|   +-- few_shot_examples.json
+-- scripts/
    +-- code_conversations.py
    +-- discover_codes.py
    +-- evaluate.py
    +-- prepare_data.py
```

## Standard Workflow

Run commands from the repository root.

```bash
# Dry-run prompt/schema inspection. No API calls.
python -m scripts.code_conversations \
    --transcripts data_prep/transcripts.jsonl \
    --ids 1139 1192 1177 1317 1397 1476 \
    --mode sync \
    --out-dir coding_results/smoke \
    --dry-run

# Small live LLM run for iteration.
python -m scripts.code_conversations \
    --transcripts data_prep/transcripts.jsonl \
    --ids 1139 1192 1177 1317 1397 1476 \
    --mode sync \
    --out-dir coding_results/smoke

# Evaluate a coding run against the current consensus truth labels.
python -m scripts.evaluate \
    --llm-codings coding_results/smoke/codings.jsonl \
    --human-coding data_prep/sample_truth_label.csv \
    --transcripts data_prep/transcripts.jsonl \
    --out-dir evaluation/smoke

# Full corpus via Batch API.
python -m scripts.code_conversations \
    --transcripts data_prep/transcripts.jsonl \
    --mode batch \
    --out-dir coding_results/full

# Retrieve completed batch results.
python -m scripts.code_conversations \
    --retrieve-batch BATCH_ID \
    --out-dir coding_results/full

# Evaluate full run.
python -m scripts.evaluate \
    --llm-codings coding_results/full/codings.jsonl \
    --human-coding data_prep/sample_truth_label.csv \
    --transcripts data_prep/transcripts.jsonl \
    --out-dir evaluation/full
```

## Updating The Codebook

When `data_prep/New_Codebook.csv` changes, update all three places together:

1. `references/codebook.md`
2. `references/output_schema.json`
3. label constants and normalizers in `scripts/evaluate.py`

Then regenerate or review `prompts/few_shot_examples.json` so examples reflect the current taxonomy.

## Dependencies

```bash
pip install anthropic openpyxl jsonschema
```

The Anthropic SDK reads `ANTHROPIC_API_KEY` from the environment. Dry-run mode does not require an API key.
