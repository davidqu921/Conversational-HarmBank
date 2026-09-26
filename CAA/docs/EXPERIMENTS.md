# Linux ARM64 + NVIDIA setup

English is displayed below. Expand **Chinese reference / 中文原文** at the end
to read the original version. Folding requires a Markdown renderer that
supports HTML `<details>`; other viewers may display both versions.

The production target is Ubuntu Linux on `aarch64`, using the existing Conda
environment in `environment-linux.yml`. Run commands from the repository root.

## 1. Create or update the environment

```bash
conda env create -f environment-linux.yml
conda activate caa
```

If the environment already exists, use `conda env update -n caa -f
environment-linux.yml --prune`. The YAML intentionally has no machine-specific
`prefix`.

## 2. Select the Hugging Face cache

The committed configs target:

```text
/home/david-qu/hf_cache/hub
```

and explicitly locate the attacker at:

```text
/home/david-qu/hf_cache/hub/models--meta-llama--Llama-3.1-8B-Instruct
```

`CAA_MODEL_CACHE` overrides the cache for another server without editing YAML:

```bash
export CAA_MODEL_CACHE=/home/david-qu/hf_cache/hub
```

Each configured response model must also exist in that cache. The runner is
offline-first and fails clearly if a model is absent. To use another local
checkout, add `local_path` beneath that model in the experiment YAML.

## 3. Preflight before loading weights

```bash
python -m CAA.scripts.runtime.check_runtime_env_linux \
  --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml
```

Then load tokenizer/model and generate a short sample for one model:

```bash
python -m CAA.scripts.runtime.check_hf_models \
  --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml \
  --model-id meta-llama/Llama-3.1-8B-Instruct --load-model --generate
```

## 4. Planning, smoke inference, and resume

```bash
python -m CAA.scripts.build_attempt_schedule --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml
python -m CAA.scripts.sample_strategy --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml
python -m CAA.scripts.run_caa_experiment --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml --dry-run --limit 1
python -m CAA.scripts.run_caa_experiment --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml --execute --limit 1
python -m CAA.scripts.run_caa_experiment --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml --execute --resume
```

`execution_mode: dual_resident` loads both models at once. Confirm available
VRAM before the live smoke. If the server cannot hold both models, the runner
still needs a sequential/offloaded execution mode; do not start the full batch.
Live execution requires CUDA by default; set `conversation.require_cuda: false`
only for an intentional CPU-only diagnostic.

## 5. Attack generation conditions

Run the following commands from the repository root and use the same `CONFIG`
once selected. After planning, the comparison conditions reuse the existing
`planning/strategy_assignments.jsonl`. Trajectory-seeded conditions also depend
on previously generated trajectory conversations.

| Entry point (prefix: `CAA.scripts.`) | Purpose |
| --- | --- |
| `build_attempt_schedule` | Assigns attempt types according to the configuration |
| `sample_strategy` | Samples strategies, topics, and examples, then saves the plan |
| `run_caa_experiment` | Generates a standard multi-turn conversation along the full trajectory |
| `run_weak_attack_experiment` | Selects an execution action from the plan and generates one attack and one response |
| `run_repeated_weak_attack_experiment` | Supports multiple repeated-attack modes; the response model retains context |
| `run_isolated_repeated_attack_experiment` | Generates independent short exchanges; each response sees only the current Student message |

Repeated attacks support the following `--attack-generation` values:

- `trajectory_seeded_independent` (default): copies the selected Student message
  from the trajectory for the first turn. Later variants use a fixed
  seed/plan/topic without giving the attacker previous responses. The response
  model receives accumulated conversation history.
- `trajectory_seeded`: copies the first turn from the trajectory; the attacker
  uses conversation history for subsequent turns.
- `regenerate`: generates a new attack from the conversation context each turn.
- `replay`: generates an attack once and repeats the same message.

To run the main repeated comparison condition and the supplementary isolated
condition:

```bash
CONFIG=CAA/configs/round5_balanced_100_gemma3_12b_stronger.yaml
python -m CAA.scripts.run_repeated_weak_attack_experiment \
  --config "$CONFIG" --attack-generation trajectory_seeded_independent --execute --resume
python -m CAA.scripts.run_isolated_repeated_attack_experiment \
  --config "$CONFIG" --execute --resume
```

The isolated runner uses dedicated standalone prompts for subsequent attacks,
and each response has an independent context. It does not simply split the
existing context-independent transcript into separate exchanges, so generation
differences also affect the experimental comparison. `standalone_validation`
only issues warnings: if a message contains a reference to history such as
`last time`, it records the failed check and matching phrases without stopping
generation. The copied seed turn incurs no attacker-query tokens; its length
is stored separately in `seed_text_tokens`.

To generate isolated attacks for all four models and both the 100/300 sample
runs:

```bash
nohup bash CAA/scripts/batch/run_isolated_repeated_attack_all.sh \
  > isolated_repeated_launcher.log 2>&1 &
```

Each job uses resume and, by default, retries once after failure. If the retry
also fails, the batch continues to the next job and ultimately exits with a
nonzero code. Logs and `status.tsv` are stored under
`CAA/outputs/isolated_repeated_batch_logs/<UTC timestamp>/`.
See [EVALUATION.md](EVALUATION.md) for evaluation instructions.

## 6. Configuration and data layout

`configs/*.yaml` contains the actual experiment configurations; a filename does
not necessarily match its `experiment_id`. The output directory is determined
by `paths.output_root / experiment_id`. Configurations for 40/100/300 samples
and other run sizes are retained for reproducibility. Smaller runs and
configurations for different models should not be deleted as duplicates.

| Configuration field | Current purpose |
| --- | --- |
| `experiment_id`, `seed`, `num_attacks`, `max_attacker_turns` | Experiment identifier, planning random seed, attack count, and turn limit |
| `attacker_model`, `response_model` | Transformers models, generation parameters, and optional local paths |
| `sampling` | CAB strategy sampling, attempt assignment, topic/example selection, and short-path extension |
| `conversation` | Runtime CUDA requirements, execution mode, and stopping/retry policies |
| `paths` | CAB/CAG data, human/historical annotations, output root, and model cache |
| `evaluation` | Configuration for auditing historical source labels; does not automatically launch severity evaluation of generated conversations |

Production configurations generally disable `randomize_action_count` and use
the sampled path as the basis for progression up to the turn limit. Very short
paths can be extended using `short_path_extension_threshold` /
`short_path_extension_min_turns`. Prompt paths in configurations are relative
to the repository root. Environment variables `CAA_MODEL_CACHE` / `HF_HUB_CACHE`
can override the model cache without editing individual YAML files.

Canonical data sources include:

- `raw_cab_round5_reviewed_all/turn_action_conversation_bank.jsonl`
- `raw_cab_round5_reviewed_all/phrase_conversation_bank.jsonl`
- Action/phase graphs under `raw_cab_round5_reviewed_all/cag/`
- `data_prep/human_label_5/resolved_coding_results/round5_reviewed_completed_codings.csv`
- `references/codebook_round4.md`

Main output layout:

```text
outputs/<experiment_id>/
├── planning/strategy_assignments.jsonl
├── conversations/                         # raw trajectory conversations
├── transcripts.jsonl                      # trajectory evaluation input
├── weak_attack_convos/
├── context_independent_trajectory_seeded_repeated_weak_attack_convos/
├── isolated_trajectory_seeded_repeated_weak_attack_convos/
│   ├── caa_0001/pair_XX.json, manifest.json
│   ├── pair_transcripts.jsonl
│   └── parent_index.jsonl
├── evaluation/                            # trajectory codings
├── weak_attack_evaluation/
├── context_independent_trajectory_seeded_repeated_weak_attack_evaluation/
└── isolated_trajectory_seeded_repeated_weak_attack_evaluation/
```

Each line in a standard transcript JSONL contains fields such as `id`,
`transcript_text`, and `transcript_turns`. Structured turns contain `turn`,
`speaker`, and `text`; Student is the attacker and Steve is the response model.
Isolated pair IDs have the form `caa_0001__pair_01` and link to their parent
through `parent_attack_id`. The parent index's `n_conversations` field is used
to check completeness. On resume, the isolated generation runner can migrate
legacy `conversation_XX.json` files to canonical pair files without regenerating
existing responses.

Evaluation `codings.csv` / `codings.jsonl` files contain derived codings;
human-reviewed results reside in reviewed subdirectories. `summary.json`
aggregates coverage, success rates, and errors. Interpret each evaluator's
subdirectory separately.

---

<details>
<summary>Chinese reference / 中文原文（点击展开）</summary>

# Linux ARM64 + NVIDIA setup

The production target is Ubuntu Linux on `aarch64`, using the existing Conda
environment in `environment-linux.yml`. Run commands from the repository root.

## 1. Create or update the environment

```bash
conda env create -f environment-linux.yml
conda activate caa
```

If the environment already exists, use `conda env update -n caa -f
environment-linux.yml --prune`. The YAML intentionally has no machine-specific
`prefix`.

## 2. Select the Hugging Face cache

The committed configs target:

```text
/home/david-qu/hf_cache/hub
```

and explicitly locate the attacker at:

```text
/home/david-qu/hf_cache/hub/models--meta-llama--Llama-3.1-8B-Instruct
```

`CAA_MODEL_CACHE` overrides the cache for another server without editing YAML:

```bash
export CAA_MODEL_CACHE=/home/david-qu/hf_cache/hub
```

Each configured response model must also exist in that cache. The runner is
offline-first and fails clearly if a model is absent. To use another local
checkout, add `local_path` beneath that model in the experiment YAML.

## 3. Preflight before loading weights

```bash
python -m CAA.scripts.runtime.check_runtime_env_linux \
  --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml
```

Then load tokenizer/model and generate a short sample for one model:

```bash
python -m CAA.scripts.runtime.check_hf_models \
  --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml \
  --model-id meta-llama/Llama-3.1-8B-Instruct --load-model --generate
```

## 4. Planning, smoke inference, and resume

```bash
python -m CAA.scripts.build_attempt_schedule --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml
python -m CAA.scripts.sample_strategy --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml
python -m CAA.scripts.run_caa_experiment --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml --dry-run --limit 1
python -m CAA.scripts.run_caa_experiment --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml --execute --limit 1
python -m CAA.scripts.run_caa_experiment --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml --execute --resume
```

`execution_mode: dual_resident` loads both models at once. Confirm available
VRAM before the live smoke. If the server cannot hold both models, the runner
still needs a sequential/offloaded execution mode; do not start the full batch.
Live execution requires CUDA by default; set `conversation.require_cuda: false`
only for an intentional CPU-only diagnostic.

## 5. 攻击生成条件

以下命令均在仓库根目录运行，配置选定后使用同一 `CONFIG`。规划完成后，各对照条件复用已有
`planning/strategy_assignments.jsonl`，trajectory-seeded 条件还依赖已生成的 trajectory 对话。

| 入口（前缀 `CAA.scripts.`） | 作用 |
| --- | --- |
| `build_attempt_schedule` | 按配置分配 attempt 类型 |
| `sample_strategy` | 采样策略、topic 与示例，保存规划 |
| `run_caa_experiment` | 沿完整轨迹推进的普通多轮对话 |
| `run_weak_attack_experiment` | 从规划选择执行动作，生成一次攻击和一次回应 |
| `run_repeated_weak_attack_experiment` | 多种重复攻击模式；response 保留上下文 |
| `run_isolated_repeated_attack_experiment` | 每次 response 只看当前 Student 消息，独立短对话 |

重复攻击的 `--attack-generation`：

- `trajectory_seeded_independent`（默认）：第一轮复制 trajectory 中选定的 Student 消息，
  后续使用固定 seed/plan/topic 生成变化，不向 attacker 提供先前回应；response 累积上下文。
- `trajectory_seeded`：第一轮复制 trajectory，后续 attacker 使用对话上下文。
- `regenerate`：每轮根据上下文重新生成攻击。
- `replay`：生成一次后重复相同消息。

主要对比条件和 isolated 补充条件：

```bash
CONFIG=CAA/configs/round5_balanced_100_gemma3_12b_stronger.yaml
python -m CAA.scripts.run_repeated_weak_attack_experiment \
  --config "$CONFIG" --attack-generation trajectory_seeded_independent --execute --resume
python -m CAA.scripts.run_isolated_repeated_attack_experiment \
  --config "$CONFIG" --execute --resume
```

Isolated runner 后续攻击使用 dedicated standalone prompts，response 的上下文独立。
它并非把现有 context-independent transcript 原封不动拆分，所以生成差异也会影响实验比较。
`standalone_validation` 只做告警：如出现 `last time` 等引用历史的表达，保存失败标记和命中短语，
不会因此停止生成。复制 seed 的首轮不计 attacker 查询 tokens，另存 `seed_text_tokens`。

四模型 × 100/300 isolated 生成批处理：

```bash
nohup bash CAA/scripts/batch/run_isolated_repeated_attack_all.sh \
  > isolated_repeated_launcher.log 2>&1 &
```

每项使用 resume，默认失败重试一次，仍失败则继续下一项并最终返回非零；日志与 `status.tsv`
存于 `CAA/outputs/isolated_repeated_batch_logs/<UTC timestamp>/`。
评估另见 [EVALUATION.md](EVALUATION.md)。

## 6. 配置与数据结构

`configs/*.yaml` 是各实验的实际配置，文件名不一定等于 `experiment_id`。
输出目录由 `paths.output_root / experiment_id` 决定。保留 40/100/300 等配置用于复现，
不把较小规模或不同模型配置当成重复版本删除。

| 配置字段 | 当前用途 |
| --- | --- |
| `experiment_id`, `seed`, `num_attacks`, `max_attacker_turns` | 实验标识、规划随机种子、数量与轮次上限 |
| `attacker_model`, `response_model` | Transformers 模型、生成参数和可选本地路径 |
| `sampling` | CAB 策略采样、attempt 分配、topic/example 选择与短路径扩展 |
| `conversation` | 运行时 CUDA、执行方式、停止与重试策略 |
| `paths` | CAB/CAG、人工/历史标注、输出根目录、模型 cache |
| `evaluation` | 历史来源标签审计的配置；不自动启动生成对话的 severity evaluator |

正式配置通常关闭 `randomize_action_count`，以采样出的路径为基础推进到轮次上限；
极短路径可依据 `short_path_extension_threshold` / `short_path_extension_min_turns` 扩展。
配置中的 prompt 路径相对于仓库根目录。环境变量 `CAA_MODEL_CACHE` / `HF_HUB_CACHE`
可覆盖模型缓存，不必逐个修改 YAML。

Canonical 数据源包括：

- `raw_cab_round5_reviewed_all/turn_action_conversation_bank.jsonl`
- `raw_cab_round5_reviewed_all/phrase_conversation_bank.jsonl`
- `raw_cab_round5_reviewed_all/cag/` 下的 action/phase 图
- `data_prep/human_label_5/resolved_coding_results/round5_reviewed_completed_codings.csv`
- `references/codebook_round4.md`

主要产物结构：

```text
outputs/<experiment_id>/
├── planning/strategy_assignments.jsonl
├── conversations/                         # trajectory 原始对话
├── transcripts.jsonl                      # trajectory 评估输入
├── weak_attack_convos/
├── context_independent_trajectory_seeded_repeated_weak_attack_convos/
├── isolated_trajectory_seeded_repeated_weak_attack_convos/
│   ├── caa_0001/pair_XX.json, manifest.json
│   ├── pair_transcripts.jsonl
│   └── parent_index.jsonl
├── evaluation/                            # trajectory 评分
├── weak_attack_evaluation/
├── context_independent_trajectory_seeded_repeated_weak_attack_evaluation/
└── isolated_trajectory_seeded_repeated_weak_attack_evaluation/
```

普通 transcript JSONL 每行有 `id`、`transcript_text`、`transcript_turns` 等字段；
结构化 turn 包含 `turn`、`speaker`、`text`，Student 为 attacker，Steve 为 response。
Isolated pair ID 形如 `caa_0001__pair_01`，通过 `parent_attack_id` 对应 parent；
parent index 的 `n_conversations` 用于检查完整性。旧 `conversation_XX.json` 格式可由 isolated
生成 runner 在 resume 时迁移到 canonical pair 文件，不重新生成已有回应。

评估 `codings.csv` / `codings.jsonl` 是派生评分，人工结果位于 reviewed 子目录；
`summary.json` 汇总覆盖率、成功率与错误。不同 evaluator 的子目录必须分开解释。

</details>
