# Trajectory Attack vs Weak Attack vs Repeated Weak Attack

This report combines the 100- and 300-round summaries for each response model. Trajectory and weak attack use the human-reviewed `reviewed_severity_llama31/summary.json`; repeated weak attack temporarily uses the unreviewed `severity_llama31/summary.json` because no reviewed version is available yet.

- Pooled ASR = total successes / total coded records.
- Each pooled cell contains **successes / coded (ASR)**.
- All 24 source summaries report `n_errors = 0`.
- Evaluation status: trajectory = reviewed; weak = reviewed; repeated weak = unreviewed.

## Pooled comparison (100 + 300)

| Response model | Trajectory attack | Weak attack | Repeated weak attack |
|---|---:|---:|---:|
| Gemma 3 12B | **30 / 400 (7.50%)** | 2 / 400 (0.50%) | 10 / 400 (2.50%) |
| Llama 3.1 8B | **38 / 400 (9.50%)** | 14 / 400 (3.50%) | 5 / 400 (1.25%) |
| Mistral 7B | **45 / 400 (11.25%)** | 6 / 400 (1.50%) | 4 / 400 (1.00%) |
| Qwen 2.5 7B | **61 / 400 (15.25%)** | 23 / 400 (5.75%) | 15 / 400 (3.75%) |
| **All models** | **174 / 1600 (10.88%)** | **45 / 1600 (2.81%)** | **34 / 1600 (2.13%)** |

## Run breakdown

| Response model | Attack type | 100 rounds | 300 rounds | Pooled |
|---|---|---:|---:|---:|
| Gemma 3 12B | Trajectory | 9 / 100 (9.00%) | 21 / 300 (7.00%) | 30 / 400 (7.50%) |
|  | Weak | 1 / 100 (1.00%) | 1 / 300 (0.33%) | 2 / 400 (0.50%) |
|  | Repeated weak | 4 / 100 (4.00%) | 6 / 300 (2.00%) | 10 / 400 (2.50%) |
| Llama 3.1 8B | Trajectory | 11 / 100 (11.00%) | 27 / 300 (9.00%) | 38 / 400 (9.50%) |
|  | Weak | 4 / 100 (4.00%) | 10 / 300 (3.33%) | 14 / 400 (3.50%) |
|  | Repeated weak | 0 / 100 (0.00%) | 5 / 300 (1.67%) | 5 / 400 (1.25%) |
| Mistral 7B | Trajectory | 6 / 100 (6.00%) | 39 / 300 (13.00%) | 45 / 400 (11.25%) |
|  | Weak | 1 / 100 (1.00%) | 5 / 300 (1.67%) | 6 / 400 (1.50%) |
|  | Repeated weak | 0 / 100 (0.00%) | 4 / 300 (1.33%) | 4 / 400 (1.00%) |
| Qwen 2.5 7B | Trajectory | 11 / 100 (11.00%) | 50 / 300 (16.67%) | 61 / 400 (15.25%) |
|  | Weak | 4 / 100 (4.00%) | 19 / 300 (6.33%) | 23 / 400 (5.75%) |
|  | Repeated weak | 6 / 100 (6.00%) | 9 / 300 (3.00%) | 15 / 400 (3.75%) |

## Takeaway

- Trajectory attack has the highest pooled ASR for every model.
- Repeated weak attack exceeds weak attack only for Gemma 3 12B (2.50% vs 0.50%).
- Across all models, the ASR ordering is trajectory (10.88%) > weak (2.81%) > repeated weak (2.13%).

The lower repeated-weak ASR is plausible because these runs use `attack_generation = replay`: the same first attack message is repeated verbatim for 3--15 rounds (about 9 rounds on average), without adapting to Steve's replies. Repetition can make the attack look like spam and give Steve repeated opportunities to refuse or redirect. Also, the first repeated-weak message was generated independently from the one-turn weak message, so this is not a controlled test in which identical attack text is shown once versus multiple times. The success cases confirm this mismatch: across the four pooled model comparisons, only 2 assignments succeeded under both weak conditions.

Note: ASRs were recomputed from `n_success / n_coded`. The repeated-weak results should be treated as provisional until they receive the same human-review procedure as the other two conditions.
