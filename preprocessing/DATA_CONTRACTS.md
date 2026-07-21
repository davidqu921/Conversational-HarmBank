# Part 1 / CAA handoff contracts

The validator in `scripts.preprocessing.validate_caa_inputs` is the executable
form of these contracts. CSV is read as UTF-8 (optionally with BOM); JSONL is one
UTF-8 JSON object per non-empty line. Conversation IDs are compared as strings.

## Frozen reviewed codings

Required CSV columns:

```text
id,primary_attack_vector,secondary_attack_vector,attempt,conversational,severity
```

`id` must be non-empty and unique. Severity is one of `0 - Safe`, `1 - Minor`,
`2 - Major`, or `3 - Severe`.

## Category assignments

The deterministic classifier emits:

```text
id,category,reason,primary_attack_vector,secondary_attack_vector,attempt,conversational,severity
```

The rule is `severity >= 1 -> success_attack`; safe records with primary vector
`No Attempt` become `no_attack`; the remaining safe attacks become
`unsuccess_attack`. Unknown/missing values become `unclassified` and must not be
silently included in a CAB.

## Phrase CAB

Every JSONL record needs:

```text
conversation_id,source_pool,primary_attack_vector,attempt,severity,
phase_trajectory,phrases
```

`phase_trajectory` and `phrases` are non-empty lists. Successful attacks use
human-reviewed phrase spans; other pools use their frozen validated LLM phase
segments.

## Turn-action CAB

Every JSONL record needs:

```text
conversation_id,source_pool,primary_attack_vector,attempt,severity,
action_trajectory,phase_trajectory,turns
```

Trajectories and `turns` are non-empty lists. Each turn has `turn`, `text`,
`phase`, and `action`. A publication release cannot contain
`turn_coverage_issue=true`; resolve or explicitly exclude the source record and
rebuild all downstream artifacts.

## CAGs

The action and phase graph JSON objects contain `graph_layer`, `nodes`, and
`edges`. Node IDs are non-empty. Every edge `source` and `target` must reference
a node in the same graph. Every action trajectory label must be defined by the
frozen Conversation Action Library.

## Cross-file invariants

- Reviewed codings, phrase CAB, and turn-action CAB have the same unique ID set.
- `source_pool` is `success_attack`, `unsuccess_attack`, or `no_attack`.
- CAB, CAG, human labels, and CAL all belong to the same frozen review release.
- The two CAA-facing graph paths and two bank paths retain the names configured
  by `CAA/configs/*.yaml`.

