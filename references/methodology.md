# Methodology Notes

Background reading and design choices behind this pipeline. This file is not loaded into the per-conversation prompt.

## Deductive + Inductive Workflow

The main pass is deductive: the LLM receives the fixed codebook and assigns only existing labels. If an attack pattern does not fit the current types, it may use `Other` with a short discovery note.

The optional discovery pass clusters those `Other` notes and proposes candidate codes for human review. It does not edit the codebook automatically.

## Current Truth Labels

The current evaluation source is `data_prep/sample_truth_label.csv`, a post-review consensus label sheet in wide format. The older `data_prep/ground_truth.csv` came from an earlier draft round and should not be used for current model evaluation.

The old IRR/reserved-ID workflow has been removed from the active pipeline. Few-shot examples are selected from the current sample truth labels and should be regenerated or reviewed whenever the codebook changes.

## Few-Shot Examples

Few-shot examples should cover:

- Normal/no-attempt conversations.
- Common attack vectors and types.
- Multi-label conversations.
- Borderline success cases.
- The full Severity Scale when possible.

They live in `prompts/few_shot_examples.json` and are rendered into the system prompt at runtime.

## Structured Output

The Anthropic API tool schema in `references/output_schema.json` requires the LLM to return:

- `reasoning`
- `codings`
- `conversational`
- `success`
- `severity`

This avoids free-form parsing and keeps outputs aligned with the current codebook.

## Evaluation

`scripts/evaluate.py` treats attack vector, attack vector type, and attempt as multi-label dimensions. It computes binary Cohen's kappa per label and macro-averages across labels.

Conversational, success, and severity are single-label dimensions and use standard Cohen's kappa.
