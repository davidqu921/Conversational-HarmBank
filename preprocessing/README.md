# Part 1: reviewed-data pipeline

This directory is the publication-facing entry point for everything before
`CAA/`. It does not move or rewrite the historical experiment folders. Instead,
it gives the current Round 5 release one explicit configuration, one
deterministic post-review build command, and one CAA handoff validator.

Run every command from the repository root. Paths in the JSON configuration are
repository-relative and are resolved with `pathlib`, so the Python entry points
work with native Windows paths and do not depend on the current shell separator.

## Workflow and quality gates

```text
raw transcript export
  -> normalize and clean
  -> whole-conversation LLM coding
  -> [HUMAN GATE] review, disagreement resolution, freeze labels
  -> number turns and segment
  -> [HUMAN GATE] review segmentation, resolve spans/actions, freeze labels
  -> fill back turn actions and audit coverage
  -> [HUMAN GATE] resolve every needs_review record
  -> deterministic publication build
       category assignments + ID pools
       phrase CAB + statistics
       turn-action CAB + statistics
       phase CAG + action CAG
       CAA contract validation + SHA-256 manifest
  -> CAA
```

The human gates are intentionally not hidden inside an unattended runner. A
reviewer must explicitly freeze accepted files before the deterministic build.

## Canonical frozen inputs

The active release is defined in
`preprocessing/configs/round5_reviewed_all.json`:

| Input | Role |
| --- | --- |
| `data_prep/clean_transcript.jsonl` | Clean transcript population and ID boundary. |
| `data_prep/human_label_5/resolved_coding_results/round5_reviewed_completed_codings.csv` | Frozen conversation-level human labels. |
| `conversation_seg/human_coding_template/normalized_seg_coding.csv` | Frozen reviewed phase spans for successful attacks. |
| `conversation_seg/results_4/{unsuccess_attack,no_attack}/` | Validated direct LLM phase/action segmentation for the other pools. |
| `conversation_seg/results_4/success_attack/fillback_turn_segments.csv` | Turn actions aligned to reviewed successful-attack phases. |
| `conversation_seg/results_4/success_attack/fillback_validation_report.csv` | Coverage and action/phase audit for fill-back output. |
| `conversation_seg/conversation_action_library.md` | Frozen phase/action vocabulary (CAL). |

See [DATA_CONTRACTS.md](DATA_CONTRACTS.md) for required columns and output
invariants.

## Validate the current CAA handoff

Validation is read-only:

```powershell
python -m scripts.preprocessing.run_publication_pipeline --validate-only
```

For a standalone machine-readable report:

```powershell
python -m scripts.preprocessing.validate_caa_inputs `
  --report preprocessing/validation_report.json
```

The command exits nonzero on missing files, schema errors, mismatched IDs,
unknown graph endpoints/actions, or unresolved turn coverage. Warnings and
record counts are printed separately.

The current checkout has two pre-existing unresolved fill-back records, so the
strict validator correctly blocks publication until they are adjudicated. See
[`KNOWN_DATA_ISSUES.md`](KNOWN_DATA_ISSUES.md).

## Rebuild the frozen release

Inspect all commands without writing:

```powershell
python -m scripts.preprocessing.run_publication_pipeline --build --dry-run
```

After every human gate is resolved, rebuild in place:

```powershell
python -m scripts.preprocessing.run_publication_pipeline --build
```

For a clean-room comparison, build into another directory:

```powershell
python -m scripts.preprocessing.run_publication_pipeline --build `
  --out-dir reproduction/round5_reviewed_all
```

The build writes `artifact_manifest.json` only after contract validation passes.
It records the Git commit plus SHA-256 hashes of the configuration, frozen
inputs, and CAA-facing outputs.

## Before the frozen inputs

The earlier research stages remain individual, inspectable commands because
they include API calls and human decisions. The canonical order is:

1. `scripts.data_prep.prepare_data` and `clean_transcript`
2. `scripts.coding.code_conversations_round4_with_minimax`
3. `scripts.evaluation.evaluate_round4` plus human adjudication
4. `scripts.segmentation.prepare_numbered_transcripts`
5. `scripts.segmentation.segment_conversations_with_minimax`
6. review-template build, normalization, checks, and adjudication
7. `scripts.fill_back_turn_actions.fillback_success_turn_actions` and repair audit
8. the deterministic publication build above

Use `python -m <module> --help` for stage-specific arguments. Record provider,
model ID, prompt/schema versions, decoding parameters, reviewer assignments,
and adjudication decisions alongside each run.

## Historical material

Earlier label rounds, `raw_cab/`, earlier CAB/CAG builders, old evaluation
reports, raw model responses, and prior segmentation result directories are
provenance—not inputs to the active release. They remain in place to preserve
the experimental audit trail. New reproduction instructions should not point to
them unless explicitly reproducing that historical round.
