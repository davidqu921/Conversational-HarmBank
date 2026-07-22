# Part 1 / CAA handoff contracts

`scripts.preprocessing.validate_caa_inputs` is the executable form of these
contracts. CSV is UTF-8 with an optional BOM. JSONL contains one UTF-8 JSON
object per non-empty line. Conversation IDs are compared as strings.

## Reviewed coding CSV

Required columns:

```text
id,primary_attack_vector,secondary_attack_vector,attempt,conversational,severity
```

IDs are non-empty and unique. Severity is `0 - Safe`, `1 - Minor`,
`2 - Major`, or `3 - Severe`.

## Category assignments

The deterministic classifier emits:

```text
id,category,reason,primary_attack_vector,secondary_attack_vector,attempt,conversational,severity
```

`severity >= 1` becomes `success_attack`. Safe records whose primary vector is
`No Attempt` become `no_attack`; other safe attacks become `unsuccess_attack`.
Unknown values become `unclassified` and are never silently added to a CAB.

## Phrase and turn-action CABs

Phrase records require `conversation_id`, `source_pool`, coding fields,
`phase_trajectory`, and non-empty `phrases`.

Turn-action records require `conversation_id`, `source_pool`, coding fields,
non-empty `action_trajectory`, `phase_trajectory`, and `turns`. Each turn has
`turn`, `text`, `phase`, and `action`. A publication release cannot contain
`turn_coverage_issue=true`.

## CAGs and cross-file invariants

Action and phase graphs contain `graph_layer`, non-empty `nodes`, and `edges`
whose endpoints exist in the same graph. Every action is defined by the frozen
Conversation Action Library.

- Reviewed codings, phrase CAB, and turn-action CAB have the same unique IDs.
- `source_pool` is `success_attack`, `unsuccess_attack`, or `no_attack`.
- CAB, CAG, reviewed labels, and CAL belong to the same frozen release.
- The CAA-facing filenames remain those referenced by `CAA/configs/*.yaml`.

