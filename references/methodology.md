# Methodology Notes

Background reading and design choices behind this skill. Not loaded into the per-conversation prompt — read this when you need to understand *why* the skill is shaped the way it is, or when you're considering changes to the prompt or evaluation strategy.

## Why deductive + inductive in two passes

Recent work on LLM-assisted thematic analysis (LATA, 2025; multi-LLM dual-reliability work, 2025; GPT-4 deductive coding studies, 2024) consistently finds:

- **Deductive (codebook-given) coding** with detailed definitions and a few examples reaches Cohen's κ in the 0.7–0.9 range against humans — comparable to the human–human ceiling.
- **Fully autonomous inductive coding** (zero-shot "find the themes") drifts and produces unstable taxonomies.

We therefore split the work:
1. **Pass 1 — Deductive coding.** The LLM is given the full codebook and assigns existing codes to each conversation. When nothing fits, it writes `Other` plus a free-text note. The codebook stays frozen.
2. **Pass 2 — Discovery.** A separate prompt clusters the `Other` notes across all conversations and proposes new candidate codes for human review. A human decides whether to add them to the codebook.

This keeps the taxonomy under human control, makes IRR meaningful (you're comparing apples to apples), and makes the system reproducible — re-running the deductive pass on a stable codebook yields stable results.

## Why few-shot examples matter

Multi-label classification with ambiguous categories (e.g., "is this Wordplay or Out of Context?") benefits substantially from 3–5 worked examples in the prompt. We curate these from human-coded conversations the LLM will *not* be evaluated on, so we don't leak the test set into the prompt. See `prompts/few_shot_examples.json`.

## Why structured output

The Anthropic API supports JSON-schema-constrained generation. We use it because:
- It eliminates parse failures (no need for retry-on-malformed-JSON).
- It lets us enforce that subtypes belong to assigned vectors (validated post-hoc).
- It ships well with the Batch API at 50% cost.

## Why Cohen's κ over raw accuracy

Most conversations in this dataset are `No Attempt` (≈40%) and most attempts use a small set of common subtypes. Raw agreement is inflated by base rates. Cohen's κ corrects for chance agreement and is the standard in IRR literature. We report:
- **κ per dimension** (vector, subtype, attempt, conversational, success) against each human coder.
- **Confusion matrices** so we can see *which* labels the LLM confuses (often more diagnostic than the κ number).
- **The human–human IRR** on the 100 IRR conversations as a ceiling — the LLM should approach but won't exceed this.

For multi-label dimensions (vector, subtype, attempt) we treat each label as a binary present/absent and average per-label κ ("macro κ"). For single-label dimensions (conversational, success) we use standard κ.

## Why not mock-test on the full coded set

We never include the IRR-validation conversations in the few-shot examples. The held-out approach guards against the prompt being over-fit to specific cases. If the user asks "why does the LLM disagree with the human on conversation X", we want that signal to be honest.

## Where the user's transcripts come from

- `breakme-steve_transcripts.csv` (~1000 rows, IDs 1131–2495) — adversarial transcripts from a class assignment incentivizing students to break the agent. **This is the dataset this skill targets.**
- `virtual-steve_2025-09-01_2025-12-31.csv` (~4000 rows) — general office-hours conversations. Out of scope for this skill (different codebook — visitation reasons / goals).

## Cost expectations

At Sonnet pricing with Batch API (50% off): coding all 1000 breakme conversations end-to-end is in the low-single-digit dollars. Discovery pass adds pennies. Re-running iteratively while tuning the prompt is cheap.
