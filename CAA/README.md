# CAA：实验与评估入口

CAA 使用 CAB/CAG 策略生成攻击对话，比较完整 trajectory 与不同重复攻击条件下的模型表现。
当前仅保留原有 severity evaluator：普通对话使用 Round 4 衍生提示词，isolated 对话使用
output-only-v1。`unified_v2` 和 `harm-gate-v1` 的实现已移除，历史结果仍保留。

- [评估指南](docs/EVALUATION.md)：方法区别、结果来源、运行命令、resume 与人工复核。
- [实验运行指南](docs/EXPERIMENTS.md)：服务器环境、配置、攻击生成、数据结构。

## 文件分层

```text
CAA/
├── README.md
├── docs/                    # 两份集中维护的指南
├── configs/                 # 实验配置；历史配置也用于复现
├── prompts/                 # attacker / response / 普通 severity / isolated severity
├── scripts/
│   ├── build_attempt_schedule.py, sample_strategy.py  # 规划
│   ├── run_*_experiment.py                           # 攻击生成
│   ├── code_caa_severity_with_hf.py                   # 普通对话评估
│   ├── evaluate_isolated_repeated_attack.py           # isolated pair 评估
│   ├── review_severity_outputs.py                    # 人工复核导出
│   ├── caa_common.py, model_runtime.py               # 共享代码
│   ├── batch/               # shell 批处理入口
│   ├── analysis/            # 既有结果汇总、统计与策略来源审计
│   └── runtime/             # 环境检查、模型检查与下载
├── tests/
├── requirements-transformers.txt
└── outputs/                 # 实验产物；不随代码清理删除
```

核心生成、评估 Python 模块路径保留，批处理与辅助工具移入子目录。提示词路径保留，
以维持已有 output-only-v1 manifest 与 resume 的兼容性。

## 常用命令

从仓库根目录运行：

```bash
conda activate caa
CONFIG=CAA/configs/round5_balanced_100_gemma3_12b_stronger.yaml

# 普通完整轨迹、主要对比条件、isolated 补充条件：均为双层评估并 resume。
bash CAA/scripts/batch/run_severity.sh "$CONFIG" trajectory
bash CAA/scripts/batch/run_severity.sh "$CONFIG" context-independent
bash CAA/scripts/batch/run_severity.sh "$CONFIG" isolated

# 四个 response model × 100/300：仅评估已有 isolated 对话。
bash CAA/scripts/batch/run_isolated_output_only_all.sh
```

评估结果的有效性需结合 `summary.json` 的覆盖率、错误数和人工标注判断；
进程正常退出不等于所有样本均已成功评分。
