# Conversational HarmBank
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This is the official repository for "Conversational HarmBank: Human-Grounded Attack Trajectories for Interpretable Multi-Turn Red Teaming" by  Shizhuo Qu，Brian Harrington，Arina Azmi， Deepti Gorrepati and Omer Yilmaz.

## Introduction
This repository is an end-to-end research pipeline for studying adversarial
conversations with a virtual psychology professor (“Steve”). It has two parts:

1. **Coding and knowledge-base construction**: prepare transcripts, label
   conversation-level attack vector/attempt/structure/severity, conduct human
   review, segment Student turns into phases/actions, and build the Conversation
   Attack Bank (CAB) and Conversation Attack Graph (CAG).
2. **Conversational Attack Agent (CAA)**: recombine the reviewed CAL, CAB, CAG,
   and vector codings into new attack trajectories; run multi-turn and one-turn
   baseline attacks; evaluate and analyze the results. See
   [`CAA/README.md`](CAA/README.md).

> This project is for authorized AI-safety research. Outputs can contain harmful
> or offensive text. Use controlled systems, protect participant data, and
> review all artifacts before sharing them.

## End-to-end workflow

```text
Raw transcripts + human coding
  -> normalized/clean JSONL
  -> whole-conversation LLM coding
  -> human review and agreement checks
  -> turn numbering and LLM segmentation
  -> human segmentation review
  -> reviewed phrase/turn-action CABs and statistics
  -> phase/action CAGs
  -> CAA trajectory generation, attacks, evaluation, and analysis
```

The publication-facing Part 1 entry point is
[`preprocessing/README.md`](preprocessing/README.md). It separates the human
quality gates from a deterministic, one-config post-review build and provides an
executable validator for every artifact consumed by CAA.

Human review is a required quality gate. Raw LLM coding and unreviewed
segmentation are not final research labels. For this reason, Part 1 is
intentionally documented as a staged workflow rather than an unattended
one-command pipeline: multiple points require independent review, disagreement
resolution, adjudication, and an explicit decision to freeze the accepted
artifact before the next stage. Automating across those gates would silently
turn provisional model output into research ground truth. CAA can be wrapped
end to end after those reviewed upstream artifacts have been frozen.

## Repository map

| Path | Purpose |
| --- | --- |
| `preprocessing/` | Canonical Round 5 configuration, Part 1 data contracts, reproducible post-review build, and CAA handoff validation. |
| `data_prep/` | Normalized transcripts, tabular codebooks, five rounds of human labels, and review templates/results. |
| `prompts/` | Whole-conversation coding prompts and few-shot examples. |
| `references/` | Model-facing codebooks, methodology, and round-specific output schemas. |
| `coding_results/` | LLM coding runs and raw provider responses. |
| `human_irr/`, `evaluation/` | Human–human and LLM–human agreement outputs. |
| `conversation_seg/` | Conversation Action Library (CAL), segmentation prompts/schema, numbered transcripts, results, and review artifacts. |
| `raw_cab_round5_reviewed_all/` | Canonical reviewed phrase/turn-action CABs, statistics, CAGs, and ID pools used by CAA. |
| `scripts/` | Executable modules, grouped by pipeline stage. |
| `CAA/` | Independent local-model attack generation, baseline, evaluation, and analysis pipeline. |
| `environment.yml` | Main Conda environment for Part 1. |

## Installation

Run commands from the repository root:

```powershell
cd projects-cair-governance-jailbreak-coding
conda env create -f environment.yml
conda activate caa
```

The main stack uses packages including `openai`, `anthropic`, `pandas`,
`openpyxl`, `jsonschema`, `scikit-learn`, `networkx`, and `matplotlib`. CAA has
separate local-model requirements; follow `CAA/README.md` rather than combining
both environments blindly.

## API keys and `.env`

Create `.env` in the repository root. It is ignored by Git:

```dotenv
MINIMAX_API_KEY=replace_with_your_key
MINIMAX_BASE_URL=https://api.minimax.chat/v1
MINIMAX_MODEL=MiniMax-Text-01

# Optional OpenAI-compatible fallback
OPENAI_API_KEY=replace_with_your_key
OPENAI_BASE_URL=https://your-provider.example/v1
OPENAI_MODEL=your-model

# Legacy Anthropic workflow only
ANTHROPIC_API_KEY=replace_with_your_key

# CAA gated Hugging Face models
HF_TOKEN=hf_replace_with_your_token
```

MiniMax scripts resolve key as `MINIMAX_API_KEY` then `OPENAI_API_KEY`; base URL
as CLI `--base-url`, `MINIMAX_BASE_URL`, `OPENAI_BASE_URL`, then the default;
and model as CLI `--model`, `MINIMAX_MODEL`, `OPENAI_MODEL`, then the default.
The simple loader expects plain `KEY=value` lines. Never commit `.env` or tokens.

## Canonical inputs

- `data_prep/transcripts.jsonl`: normalized corpus.
- `data_prep/clean_transcript.jsonl`: cleaned current corpus.
- `references/codebook_round4.md` and `output_schema_round4.json`: current
  whole-conversation taxonomy/schema.
- `conversation_seg/conversation_action_library.md`: canonical CAL.
- `conversation_seg/numbered_transcripts.jsonl`: segmentation input.
- `/conversation_seg/human_coding_template/normalized_seg_coding.csv`: human reviewed sgmentation coding results.
- `data_prep/human_label_5/resolved_coding_results/`: resolved Round 5 labels.
- `raw_cab_round5_reviewed_all/`: final reviewed CAB/CAG artifacts.

Earlier rounds are retained for provenance. Do not mix rounds without an
explicit taxonomy mapping.

## Part 1: canonical run order

For paper reproduction, use the staged instructions below for data creation and
human review, then use the configured publication runner in step 8. Detailed
contracts and the legacy/current boundary are in
[`preprocessing/README.md`](preprocessing/README.md).

### 1. Prepare and clean data

```powershell
python -m scripts.data_prep.prepare_data `
  --transcripts-csv path/to/transcripts.csv `
  --coding-xlsx path/to/human_coding.xlsx `
  --out-dir data_prep

python -m scripts.data_prep.clean_transcript `
  --input data_prep/transcripts.jsonl `
  --output data_prep/clean_transcript.jsonl

python -m scripts.data_prep.turn_count_stats
```

### 2. Whole-conversation coding

Round 4 produces primary/secondary attack vectors and single-label attempt,
conversational structure, and severity. Success is derived downstream from
severity.

```powershell
# Inspect prompts; no API call
python -m scripts.coding.code_conversations_round4_with_minimax `
  --transcripts data_prep/clean_transcript.jsonl `
  --limit 2 --out-dir coding_results/round4_smoke --dry-run

# Small live test
python -m scripts.coding.code_conversations_round4_with_minimax `
  --transcripts data_prep/clean_transcript.jsonl `
  --limit 10 --out-dir coding_results/round4_smoke

# Full/resumed run
python -m scripts.coding.code_conversations_round4_with_minimax `
  --transcripts data_prep/clean_transcript.jsonl `
  --out-dir coding_results/minimax_round4_v2 --resume
```

Outputs include canonical nested `codings.jsonl`, CSV exports,
`raw_responses/`, and dry-run prompts.

> **Notice:** this module imports helpers from
> `scripts/coding/code_conversations_with_minimax.py`

### 3. Human review and agreement

Use `scripts.evaluation.evaluate_round4` for
the matching taxonomy. Resolve disagreements manually; statistics do not replace
adjudication.

```powershell
python -m scripts.evaluation.evaluate_round4 --help `
  --llm-codings coding_results/minimax_round4_v2/codings.jsonl `
  --human-coding data_prep/sample_truth_label.csv `
  --transcripts data_prep/transcripts.jsonl `
  --out-dir evaluation/round4
```

Freeze/version resolved human labels before rebuilding downstream artifacts.

### 4. Number turns and create segmentation pools

```powershell
python -m scripts.segmentation.prepare_numbered_transcripts `
  --input data_prep/clean_transcript.jsonl `
  --output conversation_seg/numbered_transcripts.jsonl
python -m scripts.cab.prepare_round4_segmentation_pools
```

Verify counts in `success_attack`, `unsuccess_attack`, `no_attack`, and
`unclassified` before continuing.

### 5. Segment phase and turn action

The model returns each Student turn’s action. The script backfills text, maps
action to phase from the CAL, derives contiguous phase segments, and validates
structure.

```powershell
python -m scripts.segmentation.segment_conversations_with_minimax `
  --ids 1131 1132 --out-dir conversation_seg/results/smoke --dry-run

python -m scripts.segmentation.segment_conversations_with_minimax --seg-success-attack
python -m scripts.segmentation.segment_conversations_with_minimax --seg-unsuccess-attack
python -m scripts.segmentation.segment_conversations_with_minimax --seg-no-attack
```

Use `--resume` for API failures and `--repair-existing` to regenerate derived
files without a model call. Review `segmentations.jsonl`, `turn_segments.csv`,
`phase_segments.csv`, `validation_report.csv`, and `raw_responses/`.
`needs_review` is not automatically retried or safe to include.

### 6. Human segmentation review

The review cycle is: build templates, assign reviewers, normalize edits, run
checks, adjudicate conflicts, resolve Round 5 labels, and freeze the reviewed
files.

```powershell
python -m scripts.data_prep.build_seg_review_template --help
python -m scripts.data_prep.normalize_seg_review_template --help
python -m scripts.data_prep.check_seg_review_template --help
python -m scripts.data_prep.build_round5_llm_review_templates --help
python -m scripts.data_prep.resolve_round5_llm_reviews --help
python -m scripts.evaluation.evaluate_human_segmentation_irr --help
```

### 7. Fill back successful turn actions

```powershell
python -m scripts.fill_back_turn_actions.fillback_success_turn_actions --dry-run
python -m scripts.fill_back_turn_actions.fillback_success_turn_actions --resume
python -m scripts.fill_back_turn_actions.repair_success_fillback_outputs --dry-run
```

Review audit/manual reports before using repaired records.

### 8. Build final CAB, statistics, and CAG

```powershell
# Read-only check of the artifacts currently handed to CAA
python -m scripts.preprocessing.run_publication_pipeline --validate-only

# Inspect, then run, the deterministic post-review rebuild
python -m scripts.preprocessing.run_publication_pipeline --build --dry-run
python -m scripts.preprocessing.run_publication_pipeline --build
```

The final folder contains `phrase_conversation_bank.jsonl`,
`turn_action_conversation_bank.jsonl`, statistics, and canonical
`cag/phase_conversation_attack_graph.json` and
`cag/turn_action_conversation_attack_graph.json`. A successful build also writes
`artifact_manifest.json` with the Git commit and input/output SHA-256 hashes.
The runner exits nonzero rather than publishing unresolved turn coverage,
schema errors, or cross-file ID mismatches. Rebuild all downstream artifacts
after any human-review correction.

## Complete script reference

Invoke modules with `python -m` from the repository root.

| Module | Purpose |
| --- | --- |
| `scripts.preprocessing.run_publication_pipeline` | Canonical configured Round 5 rebuild, validation, and provenance manifest. |
| `scripts.preprocessing.validate_caa_inputs` | Read-only executable contract for the Part 1 -> CAA handoff. |
| `scripts.preprocessing.build_category_assignments` | Build reviewed source pools from frozen labels and cleaned transcript IDs. |
| `scripts.data_prep.prepare_data` | Convert original transcript CSV and coding XLSX into normalized project inputs. |
| `scripts.data_prep.clean_transcript` | Remove conversations with `n_turns <= 1`. |
| `scripts.data_prep.turn_count_stats` | Report transcript/segmentation turn distributions. |
| `scripts.data_prep.filter_success_attack_ids_by_user_turns` | Filter successful IDs by maximum Student-turn count. |
| `scripts.data_prep.build_seg_review_template` | Create human phase-segmentation review templates. |
| `scripts.data_prep.normalize_seg_review_template` | Normalize edited review sheets. |
| `scripts.data_prep.check_seg_review_template` | Audit IDs, phases/actions, spans, turns, and missing values. |
| `scripts.data_prep.build_human_phrase_seg_template` | Join human labels and phase outputs into phrase-review templates. |
| `scripts.data_prep.build_round5_llm_review_templates` | Build Round 5 LLM/human comparison templates. |
| `scripts.data_prep.resolve_round5_llm_reviews` | Resolve completed reviews and report conflicts/unresolved rows. |
| `scripts.coding.code_conversations_round4_with_minimax` | Current OpenAI-compatible/MiniMax Round 4 coder with dry-run/raw/resume support. |
| `scripts.coding.discover_codes` | Propose candidate taxonomy additions from “Other” notes; never edits the codebook. |
| `scripts.evaluation.evaluate` | General LLM–human/human–human agreement and discrepancy reports. |
| `scripts.evaluation.evaluate_round3`, `evaluate_round4` | Round-specific agreement evaluators. |
| `scripts.evaluation.evaluate_human_segmentation_irr` | Human segmentation inter-rater reliability. |
| `scripts.evaluation.compare_agreement_reports` | Compare two Markdown agreement reports. |
| `scripts.segmentation.prepare_numbered_transcripts` | Parse deterministic turns and Student turn numbers. |
| `scripts.segmentation.segment_conversations_with_minimax` | Label actions, derive phases/spans, validate, and export segmentation. |
| `scripts.segmentation.extract_action_code_turns` | Extract code-like action values for targeted cleanup. |
| `scripts.cab.prepare_round4_segmentation_pools` | Build Round 4 category ID pools. |
| `scripts.cab.build_conversation_attack_bank` | Join nested coding and validated segmentation into the earlier CAB. |
| `scripts.cab.compute_cab_stats` | Compute earlier CAB distributions, transitions, n-grams, and success stats. |
| `scripts.cag.build_conversation_attack_graph` | Build earlier CAG JSON/CSV/GraphML/GEXF exports. |
| `scripts.cag.visualize_cag_networkx` | Render earlier CAG with phase/spring layouts and filters. |
| `scripts.fill_back_turn_actions.fillback_success_turn_actions` | Add missing turn actions to reviewed successful phase records. |
| `scripts.fill_back_turn_actions.repair_success_fillback_outputs` | Audit/reconstruct fill-back outputs without model calls. |
| `scripts.new_cab.build_phase_phrase_bank` | Build reviewed phase/phrase CAB. |
| `scripts.new_cab.compute_phase_phrase_stats` | Analyze phase/phrase trajectories and patterns. |
| `scripts.new_cab.run_phase_phrase_pipeline` | Run the preceding build and stats stages. |
| `scripts.new_cab.build_turn_action_bank` | Build reviewed turn-action CAB. |
| `scripts.new_cab.compute_turn_action_stats` | Analyze action/phase/attempt/severity, transitions, trajectories, and n-grams. |
| `scripts.new_cab.run_turn_action_pipeline` | Run turn-action build and stats stages. |
| `scripts.new_cab.build_round5_cag` | Build final phase/action CAGs, index, network exports, and figures. |

Earlier `scripts.cab`/`scripts.cag` builders, old label rounds, and earlier
segmentation outputs are retained for provenance. They are not inputs to the
configured Round 5 publication build. The active Round 4 coder imports shared
helpers from `scripts.coding.code_conversations_with_minimax`; that helper is
therefore active support code even though its standalone workflow is legacy.

## Reproducibility and publication checklist

- Run dry tests before every model/provider/config change.
- Use a new output directory for every taxonomy or experiment version.
- Resume only when inputs, prompt, schema, model, and config are unchanged.
- Preserve raw responses until adjudication is complete.
- Exclude `needs_review` records unless manually resolved.
- Version CAL, codebook, schema, normalizers, and evaluator labels together.
- Freeze reviewed files before CAB/CAG; rebuild after corrections.
- Record model IDs, provider/endpoint, parameters, seed, and Git commit.
- Do not commit `.env`, tokens, HF caches, PID/log files, restricted transcripts,
  or harmful outputs without explicit review.
- Inspect Git status before release. This checkout contains many pre-existing
  deletions of historical generated results.
- Add the final license, citation, dataset access terms, and contact details
  before public release; a code license does not grant transcript/model rights.

