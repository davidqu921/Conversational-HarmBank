# Four-Condition CAA Evaluation Across Four Models

Each model pools the 100- and 300-conversation runs. For every individual cell, human-reviewed coding is preferred; direct `severity_llama31` coding is used only when reviewed coding is unavailable.

- ASR is recomputed as total successes / total coded records.
- Counts are pooled; run-level percentages are not averaged.
- `reviewed` means `reviewed_severity_llama31/summary.json`.
- `direct` means unreviewed `severity_llama31/summary.json`.

## Pooled comparison

| Response model | Trajectory | Weak | Repeated weak (replay) | Trajectory-seeded repeated |
|---|---:|---:|---:|---:|
| Gemma 3 12B | 30 / 400 (7.50%) | 2 / 400 (0.50%) | 10 / 400 (2.50%) | 54 / 400 (13.50%) |
| Llama 3.1 8B | 38 / 400 (9.50%) | 14 / 400 (3.50%) | 5 / 400 (1.25%) | 54 / 400 (13.50%) |
| Mistral 7B | 45 / 400 (11.25%) | 6 / 400 (1.50%) | 4 / 400 (1.00%) | 48 / 400 (12.00%) |
| Qwen 2.5 7B | 61 / 400 (15.25%) | 23 / 400 (5.75%) | 15 / 400 (3.75%) | 73 / 400 (18.25%) |
| **All models** | **174 / 1600 (10.88%)** | **45 / 1600 (2.81%)** | **34 / 1600 (2.13%)** | **229 / 1600 (14.31%)** |

## Run breakdown and coding provenance

| Response model | Attack type | 100 | 300 | Pooled | Coding source |
|---|---|---:|---:|---:|---|
| Gemma 3 12B | Trajectory | 9 / 100 (9.00%) | 21 / 300 (7.00%) | 30 / 400 (7.50%) | reviewed |
| Gemma 3 12B | Weak | 1 / 100 (1.00%) | 1 / 300 (0.33%) | 2 / 400 (0.50%) | reviewed |
| Gemma 3 12B | Repeated weak (replay) | 4 / 100 (4.00%) | 6 / 300 (2.00%) | 10 / 400 (2.50%) | direct |
| Gemma 3 12B | Trajectory-seeded repeated | 15 / 100 (15.00%) | 39 / 300 (13.00%) | 54 / 400 (13.50%) | direct |
| Llama 3.1 8B | Trajectory | 11 / 100 (11.00%) | 27 / 300 (9.00%) | 38 / 400 (9.50%) | reviewed |
| Llama 3.1 8B | Weak | 4 / 100 (4.00%) | 10 / 300 (3.33%) | 14 / 400 (3.50%) | reviewed |
| Llama 3.1 8B | Repeated weak (replay) | 0 / 100 (0.00%) | 5 / 300 (1.67%) | 5 / 400 (1.25%) | direct |
| Llama 3.1 8B | Trajectory-seeded repeated | 12 / 100 (12.00%) | 42 / 300 (14.00%) | 54 / 400 (13.50%) | direct |
| Mistral 7B | Trajectory | 6 / 100 (6.00%) | 39 / 300 (13.00%) | 45 / 400 (11.25%) | reviewed |
| Mistral 7B | Weak | 1 / 100 (1.00%) | 5 / 300 (1.67%) | 6 / 400 (1.50%) | reviewed |
| Mistral 7B | Repeated weak (replay) | 0 / 100 (0.00%) | 4 / 300 (1.33%) | 4 / 400 (1.00%) | direct |
| Mistral 7B | Trajectory-seeded repeated | 13 / 100 (13.00%) | 35 / 300 (11.67%) | 48 / 400 (12.00%) | direct |
| Qwen 2.5 7B | Trajectory | 11 / 100 (11.00%) | 50 / 300 (16.67%) | 61 / 400 (15.25%) | reviewed |
| Qwen 2.5 7B | Weak | 4 / 100 (4.00%) | 19 / 300 (6.33%) | 23 / 400 (5.75%) | reviewed |
| Qwen 2.5 7B | Repeated weak (replay) | 6 / 100 (6.00%) | 9 / 300 (3.00%) | 15 / 400 (3.75%) | direct |
| Qwen 2.5 7B | Trajectory-seeded repeated | 22 / 100 (22.00%) | 51 / 300 (17.00%) | 73 / 400 (18.25%) | direct |

## Across-model severity distribution

| Attack type | Coded | Successes | ASR | 0 - Safe | 1 - Minor | 2 - Major | 3 - Severe |
|---|---:|---:|---:|---:|---:|---:|---:|
| Trajectory | 1600 | 174 | 10.88% | 1426 | 144 | 22 | 8 |
| Weak | 1600 | 45 | 2.81% | 1555 | 42 | 3 | 0 |
| Repeated weak (replay) | 1600 | 34 | 2.13% | 1566 | 32 | 1 | 1 |
| Trajectory-seeded repeated | 1600 | 229 | 14.31% | 1371 | 186 | 38 | 5 |

## Source summaries

- Gemma 3 12B, n=100, Repeated weak (replay) (direct): `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Gemma 3 12B, n=300, Repeated weak (replay) (direct): `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Gemma 3 12B, n=100, Trajectory (reviewed): `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- Gemma 3 12B, n=300, Trajectory (reviewed): `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- Gemma 3 12B, n=100, Trajectory-seeded repeated (direct): `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/trajectory_seeded_repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Gemma 3 12B, n=300, Trajectory-seeded repeated (direct): `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/trajectory_seeded_repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Gemma 3 12B, n=100, Weak (reviewed): `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- Gemma 3 12B, n=300, Weak (reviewed): `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- Llama 3.1 8B, n=100, Repeated weak (replay) (direct): `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Llama 3.1 8B, n=300, Repeated weak (replay) (direct): `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Llama 3.1 8B, n=100, Trajectory (reviewed): `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- Llama 3.1 8B, n=300, Trajectory (reviewed): `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- Llama 3.1 8B, n=100, Trajectory-seeded repeated (direct): `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/trajectory_seeded_repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Llama 3.1 8B, n=300, Trajectory-seeded repeated (direct): `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/trajectory_seeded_repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Llama 3.1 8B, n=100, Weak (reviewed): `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- Llama 3.1 8B, n=300, Weak (reviewed): `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- Mistral 7B, n=100, Repeated weak (replay) (direct): `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Mistral 7B, n=300, Repeated weak (replay) (direct): `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Mistral 7B, n=100, Trajectory (reviewed): `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- Mistral 7B, n=300, Trajectory (reviewed): `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- Mistral 7B, n=100, Trajectory-seeded repeated (direct): `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/trajectory_seeded_repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Mistral 7B, n=300, Trajectory-seeded repeated (direct): `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/trajectory_seeded_repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Mistral 7B, n=100, Weak (reviewed): `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- Mistral 7B, n=300, Weak (reviewed): `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- Qwen 2.5 7B, n=100, Repeated weak (replay) (direct): `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Qwen 2.5 7B, n=300, Repeated weak (replay) (direct): `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Qwen 2.5 7B, n=100, Trajectory (reviewed): `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- Qwen 2.5 7B, n=300, Trajectory (reviewed): `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- Qwen 2.5 7B, n=100, Trajectory-seeded repeated (direct): `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/trajectory_seeded_repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Qwen 2.5 7B, n=300, Trajectory-seeded repeated (direct): `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/trajectory_seeded_repeated_weak_attack_evaluation/severity_llama31/summary.json`
- Qwen 2.5 7B, n=100, Weak (reviewed): `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- Qwen 2.5 7B, n=300, Weak (reviewed): `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
