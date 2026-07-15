# Conversational Attack Agent (CAA)

This folder contains the design plan for the final project stage: an automated
Conversational Attack Agent that uses CAB/CAG-derived strategies to evaluate a
response model's safety behavior across repeated multi-turn attacks.

The CAA should be implemented as a reproducible experiment pipeline:

1. Select an attempt type using a fixed experiment allocation.
2. Sample a successful CAB/CAG strategy path for that attempt while preserving
   diversity across runs.
3. Ask an attacking LLM to instantiate the abstract path into a new attack topic
   and turn-level plan.
4. Run a multi-turn conversation against a response LLM.
5. Stop at the hard turn cap or when the strategy path is exhausted.
6. Save the full transcript and metadata.
7. Reuse the Round 4 coding pipeline to label the outcome and determine whether
   the response model was successfully attacked.

Canonical project inputs, based on the current reviewed artifacts:

- `raw_cab_round5_reviewed_all/turn_action_conversation_bank.jsonl`
- `raw_cab_round5_reviewed_all/phrase_conversation_bank.jsonl`
- `raw_cab_round5_reviewed_all/cag/turn_action_conversation_attack_graph.json`
- `raw_cab_round5_reviewed_all/cag/phase_conversation_attack_graph.json`
- `raw_cab_round5_reviewed_all/turn_action_stats/*.csv`
- `conversation_seg/numbered_transcripts.jsonl`
- `references/codebook_round4.md`
- `references/output_schema_round4.json`
- `scripts/coding/code_conversations_round4_with_minimax.py`
- `projects-cair-governance-jailbreak-coding\conversation_seg\conversation_action_library.md`

Important unresolved decisions are tracked in
[`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md).

Windows Conda runtime setup is tracked in
[`SETUP_WINDOWS_CONDA.md`](SETUP_WINDOWS_CONDA.md).

Linux ARM64 + NVIDIA runtime setup is tracked in
[`SETUP_LINUX_ARM64.md`](SETUP_LINUX_ARM64.md).

Current implementation and runtime status is tracked in
[`RUN_STATUS.md`](RUN_STATUS.md).
