# Part 1: reviewed-data pipeline

This directory is the publication-facing entry point for everything before
`CAA/`. It keeps historical experiment folders in place while giving the active
Round 5 release one explicit configuration, one deterministic post-review build,
and one executable CAA handoff contract.

Run commands from the repository root. Configuration paths are repository
relative and Python resolves them with `pathlib`; no developer-specific absolute
path is required for Part 1.

## Workflow and human quality gates

```text
raw transcript export
  -> normalize and clean
  -> whole-conversation LLM coding
  -> [HUMAN GATE] review, disagreement resolution, freeze labels
  -> number turns and segment phases/actions
  -> [HUMAN GATE] review segmentation and freeze spans
  -> fill back successful-attack turn actions
  -> [HUMAN GATE] resolve every coverage issue
  -> deterministic publication build
       assignments and ID pools
       phrase CAB + statistics
       turn-action CAB + statistics
       phase CAG + action CAG
       CAA contract validation + SHA-256 manifest
  -> CAA experiments
```

Human gates are deliberately not hidden inside an unattended command. Raw LLM
output is provisional until reviewers resolve disagreements and freeze it.

## Frozen Round 5 inputs

`configs/round5_reviewed_all.json` names every input:

| Input | Purpose |
| --- | --- |
| `data_prep/clean_transcript.jsonl` | Clean population and ID boundary. |
| `data_prep/human_label_5/resolved_coding_results/round5_reviewed_completed_codings.csv` | Frozen conversation labels. |
| `conversation_seg/human_coding_template/normalized_seg_coding.csv` | Reviewed successful-attack phase spans. |
| `conversation_seg/results_4/{unsuccess_attack,no_attack}/` | Frozen direct LLM segmentations for other pools. |
| `conversation_seg/results_4/success_attack/fillback_turn_segments.csv` | Actions aligned to reviewed successful-attack phases. |
| `conversation_seg/results_4/success_attack/fillback_validation_report.csv` | Fill-back coverage audit. |
| `conversation_seg/conversation_action_library.md` | Frozen phase/action vocabulary. |

See [DATA_CONTRACTS.md](DATA_CONTRACTS.md) for required fields and invariants.

## Validate or rebuild

Read-only validation:

```bash
python -m scripts.preprocessing.run_publication_pipeline --validate-only
```

Write a machine-readable report:

```bash
python -m scripts.preprocessing.validate_caa_inputs \
  --report preprocessing/validation_report.json
```

Inspect the complete rebuild without writing, then run it after all human gates
are resolved:

```bash
python -m scripts.preprocessing.run_publication_pipeline --build --dry-run
python -m scripts.preprocessing.run_publication_pipeline --build
```

For a clean-room comparison outside the repository:

```bash
python -m scripts.preprocessing.run_publication_pipeline --build \
  --out-dir /tmp/harmbank-round5-reproduction
```

After validation passes, the build writes `artifact_manifest.json` with the Git
commit and SHA-256 hashes of the config, frozen inputs, and CAA-facing outputs.
The current checkout has two pre-existing unresolved fill-back records; see
[KNOWN_DATA_ISSUES.md](KNOWN_DATA_ISSUES.md).

## Earlier research stages

The API and human-review stages remain individual modules:

1. `scripts.data_prep.prepare_data` and `clean_transcript`
2. `scripts.coding.code_conversations_round4_with_minimax`
3. `scripts.evaluation.evaluate_round4` and human adjudication
4. `scripts.segmentation.prepare_numbered_transcripts`
5. `scripts.segmentation.segment_conversations_with_minimax`
6. review template build, normalization, audit, and adjudication
7. `scripts.fill_back_turn_actions.*` and manual resolution
8. the deterministic publication build above

Use `python -m <module> --help` for stage-specific arguments. Preserve model,
provider, prompt/schema versions, decoding parameters, reviewer assignments,
and adjudication decisions with every run.

## Historical material

Earlier label rounds, `raw_cab/`, `raw_cab_round4/`, old CAB/CAG builders,
prior segmentation result directories, raw responses, and evaluation reports
are provenance. They remain where they were created so historical experiments
can be audited, but they are not inputs to the configured Round 5 release.

