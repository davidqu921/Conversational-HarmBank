# Conversational Attack Agent (CAA)

CAA is Part 2 of the CAIR Governance Jailbreak Coding project. It recombines
the reviewed Conversation Action Library (CAL), Conversation Attack Banks
(CABs), Conversation Attack Graphs (CAGs), and human-reviewed vector codings to
sample new attack trajectories, run multi-turn and one-turn attacks, evaluate
their severity, and support human-calibrated analysis.

> **Platform scope:** the environment setup, runtime commands, paths, and code
> adaptations documented in this branch are prepared for **Windows**. Linux
> users should use the **`dgx-spark` branch**, which contains the Linux-specific
> environment and runtime adaptations.

Run all commands from the repository root:

```powershell
cd projects-cair-governance-jailbreak-coding
```

> CAA intentionally generates adversarial and potentially harmful text. Use it
> only for authorized safety research in a controlled environment.

## Pipeline

```text
Reviewed CAL + human coding + phrase/turn-action CAB + phase/action CAG
  -> deterministic attempt schedule
  -> seeded strategy, trajectory, topic, and example sampling
  -> multi-turn CAA interaction + matched simple one-turn baseline
  -> local Hugging Face severity evaluation
  -> human calibration and user-defined analysis
```

## Required upstream artifacts

- `raw_cab_round5_reviewed_all/turn_action_conversation_bank.jsonl`
- `raw_cab_round5_reviewed_all/phrase_conversation_bank.jsonl`
- `raw_cab_round5_reviewed_all/cag/turn_action_conversation_attack_graph.json`
- `raw_cab_round5_reviewed_all/cag/phase_conversation_attack_graph.json`
- `data_prep/human_label_5/resolved_coding_results/round5_reviewed_completed_codings.csv`
- `conversation_seg/conversation_action_library.md`
- optionally `coding_results/minimax_round4_v2/codings.jsonl` for historical
  MiniMax source-reference analysis

Do not combine CAB, CAG, and labels from different review rounds.

## Directory and file reference

| Path | Purpose |
| --- | --- |
| `configs/` | Complete experiment definitions: seed, models, decoding, strategy ranking, stopping, input/output/cache paths, and evaluation. |
| `prompts/attacker_system.md` | Attacker behavior, adherence, novelty, and structured-output rules. |
| `prompts/attacker_turn_user_template.md` | Per-turn attempt/action/trajectory/example/topic/history template. |
| `prompts/response_system_psych_professor*.md` | Full and light psychology-professor response personas. |
| `prompts/caa_severity_*.md` | Local severity-evaluator prompts. |
| `scripts/` | Planning, model management, experiment, baseline, and evaluation entry points. |
| `outputs/<experiment_id>/` | One run’s frozen planning, conversations, transcripts, events, and evaluations. |
| `requirements-transformers.txt` | Transformers dependencies for the Windows runtime documented in this branch. |
| `requirements-vllm.txt` | Earlier optional vLLM dependency list; Linux users should follow the `dgx-spark` branch instead. |
| `DATA_CONTRACTS.md` | Config, assignment, conversation, transcript, and evaluation schemas. |
| `EXPERIMENT_CONFIG_SPEC.md` | Detailed configuration semantics. |
| `SETUP_WINDOWS_CONDA.md` | Native Windows setup details. |
| `RUN_STATUS.md` | Recorded development-machine, model, and run status. |
| `IMPLEMENTATION_PLAN.md`, `OPEN_QUESTIONS.md` | Design history; current scripts and this README describe implemented use. |
| `CAA Command.txt` | Local command notes, not the portable canonical runner. |

## Windows environment

The following setup and helper scripts are intended for Windows. For Linux,
switch to the `dgx-spark` branch rather than applying these Windows instructions.

### Transformers runner

```powershell
conda create -n caa python=3.11 -y
conda activate caa
pip install -r CAA/requirements-transformers.txt
```

Install a CUDA-compatible PyTorch build for your hardware. The development
machine recorded Python 3.11, PyTorch `2.11.0+cu128`, CUDA, and an RTX 5090;
these exact versions are not universal.

Environment helpers:

```powershell
powershell -ExecutionPolicy Bypass -File CAA/scripts/setup_windows_conda.ps1
powershell -ExecutionPolicy Bypass -File CAA/scripts/check_runtime_env.ps1
```

`run_caa_experiment.py` in this branch uses local Transformers. Linux and DGX
Spark setup/runtime instructions are maintained in the `dgx-spark` branch.

## Hugging Face authentication and model location

Create `.env` at the repository root if using the wider project:

```dotenv
HF_TOKEN=hf_replace_with_your_token
# Alternative recognized name:
# HUGGINGFACE_HUB_TOKEN=hf_replace_with_your_token
```

The HF scripts do not explicitly load that `.env`; also export the token in the
active process or log in:

```powershell
$env:HF_TOKEN = "hf_replace_with_your_token"
huggingface-cli login
```

Accept gated-model licenses (notably Meta Llama) with the same HF account.

Model files are stored in a dedicated `hf_cache/` folder **outside the Git
repository and alongside the repository folder**. The intended layout is:

```text
Summer_Project_2026/
├── hf_cache/                                  # Hugging Face model files
└── projects-cair-governance-jailbreak-coding/ # this Git repository
```

On the original development machine, that sibling folder resolves to
`D:/Summer_Project_2026/hf_cache`; this is only a machine-specific example, not
a required universal path. On another Windows machine, create `hf_cache/` next
to the cloned repository and set `paths.model_cache` in your copied experiment
YAML to that folder's absolute path. Keeping the model cache outside the
repository prevents large model files from being mistaken for project source or
committed to Git.

```powershell
# Download the attacker and response model in the config
python -m CAA.scripts.download_hf_models `
  --config CAA/configs/round5_balanced_40_gemma2_2b_stronger.yaml

# Explicit model/cache example
python -m CAA.scripts.download_hf_models `
  --model meta-llama/Llama-3.1-8B-Instruct `
  --model google/gemma-2-2b-it `
  --cache-dir D:/Summer_Project_2026/hf_cache  # sibling of the repository

# Verify; the second command actually loads and generates
python -m CAA.scripts.check_hf_models `
  --config CAA/configs/round5_balanced_40_gemma2_2b_stronger.yaml
python -m CAA.scripts.check_hf_models `
  --config CAA/configs/round5_balanced_40_gemma2_2b_stronger.yaml `
  --load-model --generate
```

Prefer `HF_TOKEN` over CLI `--token` to avoid shell-history leakage. Downloads
are indexed by `model_manifest.json`.

## Experiment configurations

Each YAML snapshots experiment ID, seed, attack count, turn cap, attacker and
response model parameters, trajectory/topic sampling, stopping/retry behavior,
reviewed source paths, output root, cache, and evaluation policy.

Current configs use Llama 3.1 8B Instruct as attacker:

| Config | Response model | Runs |
| --- | --- | ---: |
| `round5_balanced_100_llama31_8b_stronger.yaml` | Llama 3.1 8B Instruct | 100 |
| `round5_balanced_300_llama31_8b_stronger.yaml` | Llama 3.1 8B Instruct | 300 |
| `round5_balanced_40_deepseek_r1_qwen_1_5b_stronger.yaml` | DeepSeek R1 Distill Qwen 1.5B | 40 |
| `round5_balanced_40_gemma2_2b_stronger.yaml` | Gemma 2 2B IT | 40 |
| `round5_balanced_40_llama32_3b_stronger.yaml` | Llama 3.2 3B Instruct | 40 |

Copy a YAML and assign a new `experiment_id` whenever changing model, prompt,
seed, sampling, or run size. Never reuse an old output directory.

## Canonical run order

```powershell
$CONFIG = "CAA/configs/round5_balanced_40_gemma2_2b_stronger.yaml"
```

### 1. Build the attempt schedule

```powershell
python -m CAA.scripts.build_attempt_schedule --config $CONFIG
```

This counts reviewed CAB attempts, applies seeded proportional allocation and
minimum quotas, and writes `planning/attempt_schedule.json` and `.csv`. Inspect
the total and each attempt quota.

### 2. Sample and freeze strategies

```powershell
python -m CAA.scripts.sample_strategy --config $CONFIG
```

The sampler prefers exact-attempt successful CAB paths, scores trajectory
strength, compatibility, and diversity, optionally selects topic seeds and
extra examples, extends short paths as configured, and can use a CAG walk
fallback. It writes:

```text
planning/strategy_assignments.csv
planning/strategy_assignments.jsonl
planning/strategy_sampling_summary.json
```

Freeze these assignments before execution. Multi-turn and simple attacks use
the same assignments for a matched comparison.

### 3. Dry-run and execute multi-turn attacks

```powershell
python -m CAA.scripts.run_caa_experiment --config $CONFIG --dry-run --limit 2
python -m CAA.scripts.run_caa_experiment --config $CONFIG --execute --limit 2
```

Inspect prompt rendering, action adherence, topic, persona, turns, errors, and
stop reasons before the full run:

```powershell
python -m CAA.scripts.run_caa_experiment --config $CONFIG --execute --resume
```

`--resume` skips completed `conversations/<attack_id>.json` and rebuilds
aggregate outputs. Never resume after changing config, prompts, models, or plan.

### 4. Run the matched simple one-turn baseline

```powershell
python -m CAA.scripts.run_weak_attack_experiment `
  --config $CONFIG --dry-run --limit 2
python -m CAA.scripts.run_weak_attack_experiment `
  --config $CONFIG --execute --resume
```

The script normally selects a Goal Execution action from each assignment, with
phase/path fallbacks, and sends it without the earlier trajectory to the same
response model. Outputs remain in `weak_attack_convos/`.

### 5. Evaluate generated conversations

The local evaluator defaults to Llama 3.1 8B and returns `0 - Safe`,
`1 - Minor`, `2 - Major`, or `3 - Severe`.

```powershell
# Multi-turn
python -m CAA.scripts.code_caa_severity_with_hf --config $CONFIG --resume

# Simple baseline
python -m CAA.scripts.code_caa_severity_with_hf `
  --config $CONFIG `
  --transcripts CAA/outputs/<experiment_id>/weak_attack_convos/transcripts.jsonl `
  --out-dir CAA/outputs/<experiment_id>/weak_attack_evaluation/severity_llama31 `
  --resume
```

Use `--dry-run --limit 2` to inspect evaluator prompts. Current configs treat
any non-safe severity as success, while retaining exact severity. Human-review
and calibrate **all** multi-turn and simple evaluations before publication.
Store calibrated labels separately; never overwrite raw LLM output.

### 6. Optional source-reference analysis

```powershell
python -m CAA.scripts.evaluate_caa_outputs `
  --config $CONFIG --reference round5_human
```

This joins sampled source IDs to Round 5 human (or historical MiniMax) codings.
It characterizes the source strategies; it does not freshly judge generated
responses. Use the local severity coder for actual generated text.

### 7. Downstream analysis

Join by `attack_id` across strategy assignments, conversations, multi-turn
evaluation, simple conversations/evaluation, and the separate human-calibrated
file. Analyze response model, attempt, severity, attack vector, phase/action
trajectory, topic, path length, stop reason, and multi-turn versus simple
condition. State whether each result uses raw LLM or calibrated labels.

## Output structure

```text
CAA/outputs/<experiment_id>/
├── planning/
│   ├── attempt_schedule.{json,csv}
│   ├── strategy_assignments.{jsonl,csv}
│   └── strategy_sampling_summary.json
├── conversations/caa_0001.json
├── transcripts.jsonl
├── events.jsonl
├── run_summary.json
├── evaluation/severity_llama31/
├── weak_attack_convos/
│   ├── caa_0001.json
│   ├── transcripts.jsonl
│   └── run_summary.json
└── weak_attack_evaluation/severity_llama31/
```

`transcripts.jsonl` matches the Round 4 transcript shape. Full JSON also stores
models, strategy, planned action per Student turn, timing, stop reason, and
errors. See `DATA_CONTRACTS.md`.

## Complete script reference

| Script | Purpose |
| --- | --- |
| `caa_common.py` | Shared config/path/I/O, attempt/severity, allocation, and sequence helpers; imported rather than run. |
| `download_hf_models.py` | Download config/explicit models and maintain the cache manifest. |
| `check_hf_models.py` | Scan cache; optionally load models sequentially and generate a smoke sample. |
| `build_attempt_schedule.py` | Write seeded proportional/minimum-quota JSON/CSV schedules. |
| `sample_strategy.py` | Sample CAB paths, topic seeds/examples, extend short paths, use CAG fallback, and write frozen assignments. |
| `run_caa_experiment.py` | Render dry prompts or run local multi-turn attacker/response interaction with resumable outputs. |
| `run_weak_attack_experiment.py` | Run matched one-turn baselines with dry-run, ID/limit filtering, and resume. |
| `code_caa_severity_with_hf.py` | Severity-code compatible transcript JSONL with local HF; supports dry-run, IDs/limit, resume, and summaries. |
| `evaluate_caa_outputs.py` | Report Round 5 human or historical MiniMax source-strategy labels; not generated-text evaluation. |
| `setup_windows_conda.ps1` | Build/configure the Windows Conda Transformers environment. |
| `check_runtime_env.ps1` | Print Python, PyTorch, CUDA, GPU, and HF-environment diagnostics. |
| `setup_wsl_vllm.sh` | Earlier WSL/vLLM helper retained here; use the `dgx-spark` branch for the supported Linux workflow. |

## Operating notes

- Required order is schedule -> sampling -> dry run -> smoke -> formal
  multi-turn -> simple baseline -> evaluation -> human calibration -> analysis.
- `dual_resident` can exceed VRAM for two large models. Use a smaller response
  model or add quantization, serving, or sequential loading. `device_map: auto`
  may CPU-offload and become slow.
- GPT-2 Large is not instruction-tuned; disclose this in comparisons.
- Seeds reproduce planning, but GPU generation can remain nondeterministic.
- Check `error` and `stop_reason`; do not silently count incomplete records.
- Do not commit `.env`, tokens, HF weights, restricted/harmful outputs, PID
  files, or machine logs without deliberate review.

## Troubleshooting

- **HF 401/403:** accept the license and use a token from the approved account.
- **Cache mismatch:** align the downloader and YAML `paths.model_cache`; inspect
  `model_manifest.json`.
- **CUDA OOM:** reduce model/context/generation size, close GPU processes, or
  add quantization/vLLM/sequential loading.
- **Missing planning:** run schedule then sampler using the same YAML.
- **Output collision:** create a new YAML and `experiment_id`.
- **Missing baseline/evaluation rows:** inspect summaries and per-record errors,
  then resume unchanged inputs.
- **Reference/local evaluation disagree:** they measure the source trajectory’s
  historical label versus the newly generated response.

Related documentation: [`../README.md`](../README.md),
[`DATA_CONTRACTS.md`](DATA_CONTRACTS.md),
[`EXPERIMENT_CONFIG_SPEC.md`](EXPERIMENT_CONFIG_SPEC.md),
[`SETUP_WINDOWS_CONDA.md`](SETUP_WINDOWS_CONDA.md), and
[`RUN_STATUS.md`](RUN_STATUS.md).
