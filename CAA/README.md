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

## Single-turn weak attacks from existing planning

`run_weak_attack_experiment.py` reuses an experiment's existing
`planning/strategy_assignments.jsonl`; it does not resample attempts, topics, or
trajectories. For each assignment it selects the last action from the first
available phase in this order: Goal Execution, Attack Construction, Escalation,
Trust Building, Setup. It generates that single Student attack and one response
model reply.

```bash
python -m CAA.scripts.run_weak_attack_experiment \
  --config CAA/configs/round5_balanced_40_gemma3_12b_stronger.yaml \
  --dry-run

python -m CAA.scripts.run_weak_attack_experiment \
  --config CAA/configs/round5_balanced_40_gemma3_12b_stronger.yaml \
  --execute --resume
```

Outputs are written under the experiment directory in `weak_attack_convos/`,
next to `conversations/`.

## Isolated trajectory-seeded repeated attacks

`run_isolated_repeated_attack_experiment.py` repeats the priority-selected
trajectory execution turn using isolated one-Student/one-Steve conversations.
The first conversation copies the matched trajectory turn. Every later
attacker call uses the same fixed seed, objective, plan, examples, topic, and
standalone pressure guidance. Every response-model call receives only the
current Student message.

```bash
python -m CAA.scripts.run_isolated_repeated_attack_experiment \
  --config CAA/configs/round5_balanced_100_gemma3_12b_stronger.yaml \
  --dry-run --limit 1

python -m CAA.scripts.run_isolated_repeated_attack_experiment \
  --config CAA/configs/round5_balanced_100_gemma3_12b_stronger.yaml \
  --execute --resume
```

Outputs are written to
`isolated_trajectory_seeded_repeated_weak_attack_convos/`. Each `caa_*` ID is a
folder containing `conversation_XX.json` files and a `manifest.json`.
`pair_transcripts.jsonl` flattens the isolated conversations for later coding;
parent-level evaluation aggregation is deliberately handled separately. Token
usage records actual attacker and response queries. Because the first attack is
copied rather than generated in this run, it records zero attacker-query tokens
and reports the copied seed length separately as `seed_text_tokens`.

The older `trajectory_seeded_independent` mode in
`run_repeated_weak_attack_experiment.py` does not pass actual Steve responses to
the attacker, but it uses the legacy context-oriented attacker instructions and
keeps all Steve replies in one accumulated response-model conversation. The
isolated runner uses dedicated standalone prompts and fresh response context for
the stricter independent condition.

To run the 100- and 300-conversation configs for all four response models
strictly sequentially on the DGX Spark, activate the `caa` environment and
launch the batch wrapper once:

```bash
nohup bash CAA/scripts/run_isolated_repeated_all.sh \
  > isolated_repeated_launcher.log 2>&1 &

tail -f isolated_repeated_launcher.log
```

The wrapper always passes `--resume`, retries each failed task once, continues
to later tasks after a persistent failure, and writes per-task logs plus a
`status.tsv` under `CAA/outputs/isolated_repeated_batch_logs/<UTC timestamp>/`.
It exits nonzero if any of the eight tasks remains failed.

## Export manually reviewed severity labels

After manually editing the `severity` column in an evaluator `codings.csv`,
create a synchronized reviewed export without overwriting the model output. The
leading severity number is authoritative, so changing only that number also
normalizes the label text (for example, `0 - Major` becomes `0 - Safe`). A
manually renamed `severity_reviewed` column is also accepted and exported under
the canonical `severity` name:

```powershell
python -m CAA.scripts.review_severity_outputs `
  --source-dir CAA/outputs/<experiment_id>/evaluation/severity_llama31
```

The default output is the sibling directory `reviewed_severity_llama31/`. The
script derives `success` from severity (`0 - Safe` is false; 1/2/3 are true),
synchronizes `codings.jsonl`, rebuilds every `summary.json` aggregation, verifies
the three files, and refuses to overwrite an existing reviewed directory.
