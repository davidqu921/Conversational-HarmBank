# Paired comparison: trajectory attack vs one-turn attack

This report pairs the two reviewed conditions by assignment `id`. The repository directory named `weak_attack_evaluation` is treated as the one-turn attack condition.

## Statistical definition

For each response model and run size, the paired table contains: `b` = trajectory succeeds and one-turn fails; `c` = trajectory fails and one-turn succeeds. The primary two-sided exact McNemar test uses only the `b + c` discordant pairs and tests `b ~ Binomial(b + c, 0.5)`. Success is the reviewed CSV field `success=True`, validated to be equivalent to severity > 0. The ASR denominator is the number of matched assignments, not independent condition totals.

Holm-adjusted p-values control family-wise error at alpha = 0.05 across the four response models separately within each run-size family (100, 300, and pooled). Exact p-values are primary; the continuity-corrected asymptotic values appear in the detailed sections.

## Results

| Response model | Run | N pairs | Trajectory success | One-turn success | Both success | Trajectory only (b) | One-turn only (c) | Neither | Difference (pp) | Exact p | Holm p | Holm-significant |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| google/gemma-3-12b-it | 100 | 100 | 9 (9.00%) | 1 (1.00%) | 0 | 9 | 1 | 90 | +8.00 | 0.021484 | 0.085938 | No |
| meta-llama/Llama-3.1-8B-Instruct | 100 | 100 | 11 (11.00%) | 4 (4.00%) | 0 | 11 | 4 | 85 | +7.00 | 0.118469 | 0.187500 | No |
| mistralai/Mistral-7B-Instruct-v0.3 | 100 | 100 | 6 (6.00%) | 1 (1.00%) | 1 | 5 | 0 | 94 | +5.00 | 0.062500 | 0.187500 | No |
| Qwen/Qwen2.5-7B-Instruct | 100 | 100 | 11 (11.00%) | 4 (4.00%) | 1 | 10 | 3 | 86 | +7.00 | 0.092285 | 0.187500 | No |
| google/gemma-3-12b-it | 300 | 300 | 21 (7.00%) | 1 (0.33%) | 0 | 21 | 1 | 278 | +6.67 | 0.000011 | 0.000033 | Yes |
| meta-llama/Llama-3.1-8B-Instruct | 300 | 300 | 27 (9.00%) | 10 (3.33%) | 0 | 27 | 10 | 263 | +5.67 | 0.007632 | 0.007632 | Yes |
| mistralai/Mistral-7B-Instruct-v0.3 | 300 | 300 | 39 (13.00%) | 5 (1.67%) | 1 | 38 | 4 | 257 | +11.33 | < 0.000001 | < 0.000001 | Yes |
| Qwen/Qwen2.5-7B-Instruct | 300 | 300 | 50 (16.67%) | 19 (6.33%) | 3 | 47 | 16 | 234 | +10.33 | 0.000117 | 0.000234 | Yes |
| google/gemma-3-12b-it | Pooled | 400 | 30 (7.50%) | 2 (0.50%) | 0 | 30 | 2 | 368 | +7.00 | < 0.000001 | < 0.000001 | Yes |
| meta-llama/Llama-3.1-8B-Instruct | Pooled | 400 | 38 (9.50%) | 14 (3.50%) | 0 | 38 | 14 | 348 | +6.00 | 0.001195 | 0.001195 | Yes |
| mistralai/Mistral-7B-Instruct-v0.3 | Pooled | 400 | 45 (11.25%) | 6 (1.50%) | 2 | 43 | 4 | 351 | +9.75 | < 0.000001 | < 0.000001 | Yes |
| Qwen/Qwen2.5-7B-Instruct | Pooled | 400 | 61 (15.25%) | 23 (5.75%) | 4 | 57 | 19 | 320 | +9.50 | 0.000015 | 0.000030 | Yes |

The `Difference (pp)` column is trajectory ASR minus one-turn ASR. A positive value favors the trajectory condition.

## Detailed paired tables

### google/gemma-3-12b-it — 100

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 0 | 9 | 9 |
| Failure | 1 | 90 | 91 |
| Total | 1 | 99 | 100 |

- Discordant pairs: 10 (`b=9`, `c=1`)
- Two-sided exact McNemar p: 0.021484
- Continuity-corrected McNemar chi-square: 4.900000; p: 0.026857
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 6.3333
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### meta-llama/Llama-3.1-8B-Instruct — 100

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 0 | 11 | 11 |
| Failure | 4 | 85 | 89 |
| Total | 4 | 96 | 100 |

- Discordant pairs: 15 (`b=11`, `c=4`)
- Two-sided exact McNemar p: 0.118469
- Continuity-corrected McNemar chi-square: 2.400000; p: 0.121335
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 2.5556
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### mistralai/Mistral-7B-Instruct-v0.3 — 100

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 1 | 5 | 6 |
| Failure | 0 | 94 | 94 |
| Total | 1 | 99 | 100 |

- Discordant pairs: 5 (`b=5`, `c=0`)
- Two-sided exact McNemar p: 0.062500
- Continuity-corrected McNemar chi-square: 3.200000; p: 0.073638
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 11.0000
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### Qwen/Qwen2.5-7B-Instruct — 100

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 1 | 10 | 11 |
| Failure | 3 | 86 | 89 |
| Total | 4 | 96 | 100 |

- Discordant pairs: 13 (`b=10`, `c=3`)
- Two-sided exact McNemar p: 0.092285
- Continuity-corrected McNemar chi-square: 2.769231; p: 0.096092
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 3.0000
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### google/gemma-3-12b-it — 300

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 0 | 21 | 21 |
| Failure | 1 | 278 | 279 |
| Total | 1 | 299 | 300 |

- Discordant pairs: 22 (`b=21`, `c=1`)
- Two-sided exact McNemar p: 0.000011
- Continuity-corrected McNemar chi-square: 16.409091; p: 0.000051
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 14.3333
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### meta-llama/Llama-3.1-8B-Instruct — 300

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 0 | 27 | 27 |
| Failure | 10 | 263 | 273 |
| Total | 10 | 290 | 300 |

- Discordant pairs: 37 (`b=27`, `c=10`)
- Two-sided exact McNemar p: 0.007632
- Continuity-corrected McNemar chi-square: 6.918919; p: 0.008529
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 2.6190
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### mistralai/Mistral-7B-Instruct-v0.3 — 300

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 1 | 38 | 39 |
| Failure | 4 | 257 | 261 |
| Total | 5 | 295 | 300 |

- Discordant pairs: 42 (`b=38`, `c=4`)
- Two-sided exact McNemar p: < 0.000001
- Continuity-corrected McNemar chi-square: 25.928571; p: < 0.000001
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 8.5556
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### Qwen/Qwen2.5-7B-Instruct — 300

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 3 | 47 | 50 |
| Failure | 16 | 234 | 250 |
| Total | 19 | 281 | 300 |

- Discordant pairs: 63 (`b=47`, `c=16`)
- Two-sided exact McNemar p: 0.000117
- Continuity-corrected McNemar chi-square: 14.285714; p: 0.000157
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 2.8788
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### google/gemma-3-12b-it — Pooled 100 + 300

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 0 | 30 | 30 |
| Failure | 2 | 368 | 370 |
| Total | 2 | 398 | 400 |

- Discordant pairs: 32 (`b=30`, `c=2`)
- Two-sided exact McNemar p: < 0.000001
- Continuity-corrected McNemar chi-square: 22.781250; p: 0.000002
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 12.2000
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`
  - trajectory: `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### meta-llama/Llama-3.1-8B-Instruct — Pooled 100 + 300

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 0 | 38 | 38 |
| Failure | 14 | 348 | 362 |
| Total | 14 | 386 | 400 |

- Discordant pairs: 52 (`b=38`, `c=14`)
- Two-sided exact McNemar p: 0.001195
- Continuity-corrected McNemar chi-square: 10.173077; p: 0.001425
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 2.6552
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`
  - trajectory: `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### mistralai/Mistral-7B-Instruct-v0.3 — Pooled 100 + 300

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 2 | 43 | 45 |
| Failure | 4 | 351 | 355 |
| Total | 6 | 394 | 400 |

- Discordant pairs: 47 (`b=43`, `c=4`)
- Two-sided exact McNemar p: < 0.000001
- Continuity-corrected McNemar chi-square: 30.723404; p: < 0.000001
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 9.6667
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`
  - trajectory: `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

### Qwen/Qwen2.5-7B-Instruct — Pooled 100 + 300

| Trajectory \ One-turn | Success | Failure | Total |
|---|---:|---:|---:|
| Success | 4 | 57 | 61 |
| Failure | 19 | 320 | 339 |
| Total | 23 | 377 | 400 |

- Discordant pairs: 76 (`b=57`, `c=19`)
- Two-sided exact McNemar p: 0.000015
- Continuity-corrected McNemar chi-square: 18.013158; p: 0.000022
- Discordant-pair odds ratio `(b + 0.5) / (c + 0.5)`: 2.9487
- Attempt/vector metadata mismatches among paired IDs: 0
- Sources:
  - trajectory: `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`
  - trajectory: `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/codings.csv`; one-turn: `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/codings.csv`

## Pooling caveat

The per-run-size tests are the least assumption-dependent results. The pooled rows concatenate the 100- and 300-assignment directories using `(experiment directory, id)` as the pair key. They are valid only if those directories contain distinct experimental assignments. If the 100-run assignments are a subset or rerun of the 300-run assignments, do not use the pooled p-value; use the 300-run result or deduplicate with a stable cross-run assignment identifier.
