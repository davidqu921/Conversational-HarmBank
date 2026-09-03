# Conversational HarmBank
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This is the official repository for "[Conversational HarmBank: Human-Grounded Attack Trajectories for Interpretable Multi-Turn Red Teaming](https://arxiv.org/abs/2307.15043)" by XXXX

## Introduction
Conversational HarmBank is an end-to-end research pipeline for studying
multi-turn adversarial conversations. It turns reviewed conversation data into
interpretable attack trajectories, then uses those trajectories to drive the
Conversational Attack Agent (CAA) against local language models.

This is the `dgx-spark` branch. Its research data and methodology match the
main branch; runtime instructions and model paths target Ubuntu Linux on NVIDIA
DGX Spark (`aarch64`). The Windows implementation is maintained on `main`.

> This repository supports authorized AI-safety research. Transcripts and model
> outputs may contain harmful or offensive content. Protect source data, use
> controlled systems, and review artifacts before sharing them.

## Project architecture

```text
Part 1: coding and reviewed knowledge construction

raw transcripts
  -> normalized and cleaned conversations
  -> conversation-level LLM coding
  -> human review and adjudication
  -> phase/action segmentation
  -> human segmentation review and turn-action fill-back
  -> phrase CAB + turn-action CAB
  -> phase CAG + action CAG
  -> executable CAA input validation

Part 2: Conversational Attack Agent

reviewed CAL/CAB/CAG + experiment YAML
  -> seeded attempt allocation and strategy sampling
  -> multi-turn CAA + matched single-turn baseline
  -> local severity coding
  -> human-reviewed evaluation and analysis
```

Human review is a required quality gate. LLM coding and segmentation output are
provisional until reviewers resolve disagreements and freeze an accepted
artifact. Only deterministic post-review stages are wrapped together.

## Repository map

| Path | Purpose |
| --- | --- |
| `preprocessing/` | Publication-facing Part 1 workflow, frozen config, contracts, and known issues. |
| `scripts/preprocessing/` | One-config CAB/CAG rebuild, validation, and SHA-256 manifest. |
| `data_prep/` | Clean transcripts, codebooks, human label rounds, review templates, and resolved labels. |
| `prompts/`, `references/` | Coding prompts, codebooks, methodology, and output schemas. |
| `coding_results/` | Whole-conversation LLM coding runs and raw responses. |
| `conversation_seg/` | CAL, numbered transcripts, segmentation results, review, and fill-back artifacts. |
| `human_irr/`, `evaluation/` | Human-human and model-human agreement reports. |
| `raw_cab_round5_reviewed_all/` | Frozen Round 5 CABs, statistics, CAGs, and CAA-facing ID pools. |
| `raw_cab/`, `raw_cab_round4/` | Earlier formats retained for experimental provenance. |
| `CAA/` | Local-model planning, attacks, baselines, severity evaluation, and outputs. |
| `environment.yml` | Portable Python 3.11 dependency specification. |
| `environment-linux.yml` | Captured DGX Spark Linux/aarch64 environment. |

## DGX Spark environment

The branch was prepared for Ubuntu Linux, NVIDIA CUDA, and `aarch64`. Run all
commands from the repository root.

For the exact captured environment:

```bash
conda env create -f environment-linux.yml
conda activate caa
```

To update an existing environment:

```bash
conda env update -n caa -f environment-linux.yml --prune
```

`environment.yml` is the less machine-specific alternative. CUDA-enabled
PyTorch must match the DGX system driver/runtime; verify the environment before
loading model weights:

```bash
python -c 'import platform, torch; print(platform.machine()); print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no CUDA")'
```

## Secrets and model cache

Keep API and Hugging Face credentials outside Git:

```bash
export MINIMAX_API_KEY='...'
export HF_TOKEN='...'
export CAA_MODEL_CACHE='/home/david-qu/hf_cache/hub'
```

Current DGX experiment YAMLs snapshot the original cache at
`/home/david-qu/hf_cache/hub`, and some also include an attacker
`local_path`. On another Linux account or server, copy the YAML, assign a new
`experiment_id`, update/remove `local_path`, and set `paths.model_cache` or
`CAA_MODEL_CACHE`. Do not reuse an existing experiment output directory after
changing models, prompts, seeds, or sampling parameters.

## Part 1: prepare reviewed artifacts

The detailed workflow and data contracts are in
[`preprocessing/README.md`](preprocessing/README.md). The main stages are:

### 1. Normalize and clean transcripts

```bash
python -m scripts.data_prep.prepare_data \
  --transcripts-csv path/to/transcripts.csv \
  --coding-xlsx path/to/human_coding.xlsx \
  --out-dir data_prep

python -m scripts.data_prep.clean_transcript \
  --input data_prep/transcripts.jsonl \
  --output data_prep/clean_transcript.jsonl
```

### 2. Code whole conversations

Inspect prompts before a live provider call:

```bash
python -m scripts.coding.code_conversations_round4_with_minimax \
  --transcripts data_prep/clean_transcript.jsonl \
  --out-dir coding_results/round4_smoke \
  --limit 2 --dry-run
```

Run or resume the full coding job only after the smoke output is reviewed:

```bash
python -m scripts.coding.code_conversations_round4_with_minimax \
  --transcripts data_prep/clean_transcript.jsonl \
  --out-dir coding_results/minimax_round4_v2 --resume
```

### 3. Review, adjudicate, and segment

Use the round-matched evaluator and review utilities:

```bash
python -m scripts.evaluation.evaluate_round4 --help
python -m scripts.segmentation.prepare_numbered_transcripts \
  --input data_prep/clean_transcript.jsonl \
  --output conversation_seg/numbered_transcripts.jsonl
python -m scripts.segmentation.segment_conversations_with_minimax --help
python -m scripts.data_prep.build_seg_review_template --help
python -m scripts.data_prep.normalize_seg_review_template --help
python -m scripts.data_prep.check_seg_review_template --help
python -m scripts.fill_back_turn_actions.fillback_success_turn_actions --help
```

Freeze reviewed labels and resolve every fill-back coverage issue before the
publication build.

### 4. Validate or rebuild the CAA handoff

```bash
# Read-only validation of current artifacts
python -m scripts.preprocessing.run_publication_pipeline --validate-only

# Show every deterministic build command
python -m scripts.preprocessing.run_publication_pipeline --build --dry-run

# Rebuild after human review is frozen
python -m scripts.preprocessing.run_publication_pipeline --build
```

The final output is `raw_cab_round5_reviewed_all/`. A passing build adds
`artifact_manifest.json` containing the Git commit and hashes of all frozen
inputs and CAA-facing outputs. The current branch has two documented unresolved
fill-back records; see
[`preprocessing/KNOWN_DATA_ISSUES.md`](preprocessing/KNOWN_DATA_ISSUES.md).

## Part 2: run CAA on DGX Spark

Detailed runtime notes are in
[`CAA/SETUP_LINUX_ARM64.md`](CAA/SETUP_LINUX_ARM64.md), with schemas in
[`CAA/DATA_CONTRACTS.md`](CAA/DATA_CONTRACTS.md) and configuration semantics in
[`CAA/EXPERIMENT_CONFIG_SPEC.md`](CAA/EXPERIMENT_CONFIG_SPEC.md).

Select a config, then run preflight and planning:

```bash
CONFIG=CAA/configs/round5_balanced_300_qwen25_7b_stronger.yaml

python -m CAA.scripts.check_runtime_env_linux --config "$CONFIG"
python -m CAA.scripts.build_attempt_schedule --config "$CONFIG"
python -m CAA.scripts.sample_strategy --config "$CONFIG"
```

Render a prompt-only smoke test, execute a small GPU smoke test, then resume the
full multi-turn run:

```bash
python -m CAA.scripts.run_caa_experiment \
  --config "$CONFIG" --dry-run --limit 1
python -m CAA.scripts.run_caa_experiment \
  --config "$CONFIG" --execute --limit 1
python -m CAA.scripts.run_caa_experiment \
  --config "$CONFIG" --execute --resume
```

Run the matched single-turn baseline and local severity evaluation:

```bash
python -m CAA.scripts.run_weak_attack_experiment \
  --config "$CONFIG" --execute --resume
python -m CAA.scripts.code_caa_severity_with_hf \
  --config "$CONFIG" --double-layer --resume
```

With `--double-layer`, Llama 3.1 performs the first pass and Mistral 7B Instruct
v0.3 independently adjudicates only positive results. The final files keep the
same names, while first-layer and supervisor journals are retained for audit and
resume. Omit `--double-layer` to reproduce the original single-model evaluator.

CAA stores each experiment beneath `CAA/outputs/<experiment_id>/`, including
frozen planning assignments, per-conversation JSON, transcript JSONL, events,
run summaries, baseline output, and evaluation output. Seeds reproduce planning;
GPU generation may remain nondeterministic.

## Human-reviewed severity export

After manually editing the `severity` column in an evaluator `codings.csv`, use
the reviewed exporter rather than changing derived fields by hand:

```bash
python -m CAA.scripts.review_severity_outputs \
  --source-dir CAA/outputs/<experiment_id>/evaluation/severity_llama31
```

It creates the sibling `reviewed_severity_llama31/`, recalculates `success`,
synchronizes `codings.jsonl`, rebuilds all summary aggregations, verifies the
result, and refuses to overwrite an existing reviewed directory.

## Reproducibility checklist

- Run from the repository root and record the Git commit and active branch.
- Record `uname -a`, architecture, GPU, driver, CUDA, Python, PyTorch, and model IDs.
- Use a new experiment ID for every config, prompt, model, or sampling change.
- Keep raw responses and provisional labels separate from human-reviewed labels.
- Do not continue from frozen outputs after changing their upstream inputs.
- Resolve or explicitly exclude all `needs_review` records before publication.
- Never commit `.env`, tokens, model weights, restricted transcripts, or machine logs.
- Add final authors, citation, dataset access terms, and contact information before release.

## Legacy and provenance policy

Historical scripts and generated files are intentionally retained when they
help reproduce earlier experimental decisions. The active publication route is
the configured Round 5 pipeline under `scripts.preprocessing`; older CAB/CAG
entry points should only be used when explicitly reproducing those earlier
formats.
