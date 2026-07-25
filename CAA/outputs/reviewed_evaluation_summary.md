# Aggregated Reviewed CAA Evaluations

This report pools the reviewed trajectory-attack and weak-attack evaluation summaries separately for each response model.

- Source root: `CAA/outputs`
- Included nominal run sizes: 100, 300
- Evaluation source: `reviewed_severity_llama31/summary.json` only
- Pooled ASR: sum of successes divided by sum of coded records
- Runs are pooled arithmetically; trial IDs are not deduplicated across directories

## Cross-model overview

| Response model | Attack type | Runs | Coded | Successes | Pooled ASR |
|---|---|---:|---:|---:|---:|
| google/gemma-3-12b-it | Trajectory attack | 100, 300 | 400 | 30 | 7.50% |
| google/gemma-3-12b-it | Weak attack | 100, 300 | 400 | 2 | 0.50% |
| meta-llama/Llama-3.1-8B-Instruct | Trajectory attack | 100, 300 | 400 | 38 | 9.50% |
| meta-llama/Llama-3.1-8B-Instruct | Weak attack | 100, 300 | 400 | 14 | 3.50% |
| mistralai/Mistral-7B-Instruct-v0.3 | Trajectory attack | 100, 300 | 400 | 45 | 11.25% |
| mistralai/Mistral-7B-Instruct-v0.3 | Weak attack | 100, 300 | 400 | 6 | 1.50% |
| Qwen/Qwen2.5-7B-Instruct | Trajectory attack | 100, 300 | 400 | 61 | 15.25% |
| Qwen/Qwen2.5-7B-Instruct | Weak attack | 100, 300 | 400 | 23 | 5.75% |

## google/gemma-3-12b-it

Experiment model key: `gemma3_12b`

### Trajectory attack

| Run | Records | Coded | Errors | Successes | ASR |
|---|---:|---:|---:|---:|---:|
| 100 | 100 | 100 | 0 | 9 | 9.00% |
| 300 | 300 | 300 | 0 | 21 | 7.00% |
| **Pooled** | **400** | **400** | **0** | **30** | **7.50%** |

Pooled severity distribution: 0 - Safe: 370; 1 - Minor: 26; 2 - Major: 2; 3 - Severe: 2.

#### By attempt

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Inappropriate Topics | 111 | 5 | 4.50% | 0 - Safe: 106; 1 - Minor: 5; 2 - Major: 0; 3 - Severe: 0 |
| General Break | 78 | 9 | 11.54% | 0 - Safe: 69; 1 - Minor: 8; 2 - Major: 1; 3 - Severe: 0 |
| Swearing | 60 | 4 | 6.67% | 0 - Safe: 56; 1 - Minor: 3; 2 - Major: 1; 3 - Severe: 0 |
| Break Character | 40 | 8 | 20.00% | 0 - Safe: 32; 1 - Minor: 6; 2 - Major: 0; 3 - Severe: 2 |
| Political/Social/Bias | 35 | 2 | 5.71% | 0 - Safe: 33; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |
| Slur | 29 | 0 | 0.00% | 0 - Safe: 29; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Leak Information | 25 | 1 | 4.00% | 0 - Safe: 24; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Incorrect Information | 22 | 1 | 4.55% | 0 - Safe: 21; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |

#### By source primary attack vector

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Fake Scenario | 86 | 5 | 5.81% | 0 - Safe: 81; 1 - Minor: 5; 2 - Major: 0; 3 - Severe: 0 |
| Text or Format Trick | 86 | 0 | 0.00% | 0 - Safe: 86; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| System or Rule Output | 80 | 8 | 10.00% | 0 - Safe: 72; 1 - Minor: 7; 2 - Major: 1; 3 - Severe: 0 |
| Direct Elicitation | 76 | 5 | 6.58% | 0 - Safe: 71; 1 - Minor: 4; 2 - Major: 1; 3 - Severe: 0 |
| RolePlay & Persona Manipulation (input/injection) | 53 | 11 | 20.75% | 0 - Safe: 42; 1 - Minor: 9; 2 - Major: 0; 3 - Severe: 2 |
| Disguised Intent | 14 | 0 | 0.00% | 0 - Safe: 14; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Overwhelming | 5 | 1 | 20.00% | 0 - Safe: 4; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |

Source summaries:

- 100: `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- 300: `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`

### Weak attack

| Run | Records | Coded | Errors | Successes | ASR |
|---|---:|---:|---:|---:|---:|
| 100 | 100 | 100 | 0 | 1 | 1.00% |
| 300 | 300 | 300 | 0 | 1 | 0.33% |
| **Pooled** | **400** | **400** | **0** | **2** | **0.50%** |

Pooled severity distribution: 0 - Safe: 398; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0.

#### By attempt

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Inappropriate Topics | 111 | 2 | 1.80% | 0 - Safe: 109; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |
| General Break | 78 | 0 | 0.00% | 0 - Safe: 78; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Swearing | 60 | 0 | 0.00% | 0 - Safe: 60; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Break Character | 40 | 0 | 0.00% | 0 - Safe: 40; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Political/Social/Bias | 35 | 0 | 0.00% | 0 - Safe: 35; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Slur | 29 | 0 | 0.00% | 0 - Safe: 29; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Leak Information | 25 | 0 | 0.00% | 0 - Safe: 25; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Incorrect Information | 22 | 0 | 0.00% | 0 - Safe: 22; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

#### By source primary attack vector

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Fake Scenario | 86 | 0 | 0.00% | 0 - Safe: 86; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Text or Format Trick | 86 | 1 | 1.16% | 0 - Safe: 85; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| System or Rule Output | 80 | 0 | 0.00% | 0 - Safe: 80; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Direct Elicitation | 76 | 0 | 0.00% | 0 - Safe: 76; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| RolePlay & Persona Manipulation (input/injection) | 53 | 1 | 1.89% | 0 - Safe: 52; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Disguised Intent | 14 | 0 | 0.00% | 0 - Safe: 14; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Overwhelming | 5 | 0 | 0.00% | 0 - Safe: 5; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

Source summaries:

- 100: `CAA/outputs/round5_balanced_100_llama31_gemma3_12b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- 300: `CAA/outputs/round5_balanced_300_llama31_gemma3_12b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`

## meta-llama/Llama-3.1-8B-Instruct

Experiment model key: `llama31_8b`

### Trajectory attack

| Run | Records | Coded | Errors | Successes | ASR |
|---|---:|---:|---:|---:|---:|
| 100 | 100 | 100 | 0 | 11 | 11.00% |
| 300 | 300 | 300 | 0 | 27 | 9.00% |
| **Pooled** | **400** | **400** | **0** | **38** | **9.50%** |

Pooled severity distribution: 0 - Safe: 362; 1 - Minor: 34; 2 - Major: 4; 3 - Severe: 0.

#### By attempt

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Inappropriate Topics | 111 | 9 | 8.11% | 0 - Safe: 102; 1 - Minor: 9; 2 - Major: 0; 3 - Severe: 0 |
| General Break | 78 | 4 | 5.13% | 0 - Safe: 74; 1 - Minor: 3; 2 - Major: 1; 3 - Severe: 0 |
| Swearing | 60 | 14 | 23.33% | 0 - Safe: 46; 1 - Minor: 13; 2 - Major: 1; 3 - Severe: 0 |
| Break Character | 40 | 3 | 7.50% | 0 - Safe: 37; 1 - Minor: 3; 2 - Major: 0; 3 - Severe: 0 |
| Political/Social/Bias | 35 | 1 | 2.86% | 0 - Safe: 34; 1 - Minor: 0; 2 - Major: 1; 3 - Severe: 0 |
| Slur | 29 | 6 | 20.69% | 0 - Safe: 23; 1 - Minor: 5; 2 - Major: 1; 3 - Severe: 0 |
| Leak Information | 25 | 1 | 4.00% | 0 - Safe: 24; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Incorrect Information | 22 | 0 | 0.00% | 0 - Safe: 22; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

#### By source primary attack vector

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Fake Scenario | 86 | 6 | 6.98% | 0 - Safe: 80; 1 - Minor: 6; 2 - Major: 0; 3 - Severe: 0 |
| Text or Format Trick | 86 | 10 | 11.63% | 0 - Safe: 76; 1 - Minor: 8; 2 - Major: 2; 3 - Severe: 0 |
| System or Rule Output | 80 | 5 | 6.25% | 0 - Safe: 75; 1 - Minor: 4; 2 - Major: 1; 3 - Severe: 0 |
| Direct Elicitation | 76 | 11 | 14.47% | 0 - Safe: 65; 1 - Minor: 10; 2 - Major: 1; 3 - Severe: 0 |
| RolePlay & Persona Manipulation (input/injection) | 53 | 3 | 5.66% | 0 - Safe: 50; 1 - Minor: 3; 2 - Major: 0; 3 - Severe: 0 |
| Disguised Intent | 14 | 2 | 14.29% | 0 - Safe: 12; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |
| Overwhelming | 5 | 1 | 20.00% | 0 - Safe: 4; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |

Source summaries:

- 100: `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- 300: `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`

### Weak attack

| Run | Records | Coded | Errors | Successes | ASR |
|---|---:|---:|---:|---:|---:|
| 100 | 100 | 100 | 0 | 4 | 4.00% |
| 300 | 300 | 300 | 0 | 10 | 3.33% |
| **Pooled** | **400** | **400** | **0** | **14** | **3.50%** |

Pooled severity distribution: 0 - Safe: 386; 1 - Minor: 14; 2 - Major: 0; 3 - Severe: 0.

#### By attempt

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Inappropriate Topics | 111 | 5 | 4.50% | 0 - Safe: 106; 1 - Minor: 5; 2 - Major: 0; 3 - Severe: 0 |
| General Break | 78 | 1 | 1.28% | 0 - Safe: 77; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Swearing | 60 | 2 | 3.33% | 0 - Safe: 58; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |
| Break Character | 40 | 1 | 2.50% | 0 - Safe: 39; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Political/Social/Bias | 35 | 1 | 2.86% | 0 - Safe: 34; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Slur | 29 | 3 | 10.34% | 0 - Safe: 26; 1 - Minor: 3; 2 - Major: 0; 3 - Severe: 0 |
| Leak Information | 25 | 1 | 4.00% | 0 - Safe: 24; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Incorrect Information | 22 | 0 | 0.00% | 0 - Safe: 22; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

#### By source primary attack vector

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Fake Scenario | 86 | 3 | 3.49% | 0 - Safe: 83; 1 - Minor: 3; 2 - Major: 0; 3 - Severe: 0 |
| Text or Format Trick | 86 | 4 | 4.65% | 0 - Safe: 82; 1 - Minor: 4; 2 - Major: 0; 3 - Severe: 0 |
| System or Rule Output | 80 | 1 | 1.25% | 0 - Safe: 79; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Direct Elicitation | 76 | 2 | 2.63% | 0 - Safe: 74; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |
| RolePlay & Persona Manipulation (input/injection) | 53 | 3 | 5.66% | 0 - Safe: 50; 1 - Minor: 3; 2 - Major: 0; 3 - Severe: 0 |
| Disguised Intent | 14 | 0 | 0.00% | 0 - Safe: 14; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Overwhelming | 5 | 1 | 20.00% | 0 - Safe: 4; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |

Source summaries:

- 100: `CAA/outputs/round5_balanced_100_llama31_llama31_8b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- 300: `CAA/outputs/round5_balanced_300_llama31_llama31_8b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`

## mistralai/Mistral-7B-Instruct-v0.3

Experiment model key: `mistral_7b`

### Trajectory attack

| Run | Records | Coded | Errors | Successes | ASR |
|---|---:|---:|---:|---:|---:|
| 100 | 100 | 100 | 0 | 6 | 6.00% |
| 300 | 300 | 300 | 0 | 39 | 13.00% |
| **Pooled** | **400** | **400** | **0** | **45** | **11.25%** |

Pooled severity distribution: 0 - Safe: 355; 1 - Minor: 34; 2 - Major: 9; 3 - Severe: 2.

#### By attempt

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Inappropriate Topics | 111 | 10 | 9.01% | 0 - Safe: 101; 1 - Minor: 8; 2 - Major: 2; 3 - Severe: 0 |
| General Break | 78 | 7 | 8.97% | 0 - Safe: 71; 1 - Minor: 2; 2 - Major: 3; 3 - Severe: 2 |
| Swearing | 60 | 16 | 26.67% | 0 - Safe: 44; 1 - Minor: 13; 2 - Major: 3; 3 - Severe: 0 |
| Break Character | 40 | 6 | 15.00% | 0 - Safe: 34; 1 - Minor: 6; 2 - Major: 0; 3 - Severe: 0 |
| Political/Social/Bias | 35 | 2 | 5.71% | 0 - Safe: 33; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |
| Slur | 29 | 4 | 13.79% | 0 - Safe: 25; 1 - Minor: 3; 2 - Major: 1; 3 - Severe: 0 |
| Leak Information | 25 | 0 | 0.00% | 0 - Safe: 25; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Incorrect Information | 22 | 0 | 0.00% | 0 - Safe: 22; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

#### By source primary attack vector

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Fake Scenario | 86 | 8 | 9.30% | 0 - Safe: 78; 1 - Minor: 7; 2 - Major: 1; 3 - Severe: 0 |
| Text or Format Trick | 86 | 12 | 13.95% | 0 - Safe: 74; 1 - Minor: 10; 2 - Major: 2; 3 - Severe: 0 |
| System or Rule Output | 80 | 6 | 7.50% | 0 - Safe: 74; 1 - Minor: 2; 2 - Major: 3; 3 - Severe: 1 |
| Direct Elicitation | 76 | 9 | 11.84% | 0 - Safe: 67; 1 - Minor: 7; 2 - Major: 2; 3 - Severe: 0 |
| RolePlay & Persona Manipulation (input/injection) | 53 | 8 | 15.09% | 0 - Safe: 45; 1 - Minor: 6; 2 - Major: 1; 3 - Severe: 1 |
| Disguised Intent | 14 | 2 | 14.29% | 0 - Safe: 12; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |
| Overwhelming | 5 | 0 | 0.00% | 0 - Safe: 5; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

Source summaries:

- 100: `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- 300: `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`

### Weak attack

| Run | Records | Coded | Errors | Successes | ASR |
|---|---:|---:|---:|---:|---:|
| 100 | 100 | 100 | 0 | 1 | 1.00% |
| 300 | 300 | 300 | 0 | 5 | 1.67% |
| **Pooled** | **400** | **400** | **0** | **6** | **1.50%** |

Pooled severity distribution: 0 - Safe: 394; 1 - Minor: 5; 2 - Major: 1; 3 - Severe: 0.

#### By attempt

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Inappropriate Topics | 111 | 1 | 0.90% | 0 - Safe: 110; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| General Break | 78 | 1 | 1.28% | 0 - Safe: 77; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Swearing | 60 | 2 | 3.33% | 0 - Safe: 58; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |
| Break Character | 40 | 1 | 2.50% | 0 - Safe: 39; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Political/Social/Bias | 35 | 0 | 0.00% | 0 - Safe: 35; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Slur | 29 | 1 | 3.45% | 0 - Safe: 28; 1 - Minor: 0; 2 - Major: 1; 3 - Severe: 0 |
| Leak Information | 25 | 0 | 0.00% | 0 - Safe: 25; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Incorrect Information | 22 | 0 | 0.00% | 0 - Safe: 22; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

#### By source primary attack vector

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Fake Scenario | 86 | 1 | 1.16% | 0 - Safe: 85; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Text or Format Trick | 86 | 1 | 1.16% | 0 - Safe: 85; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| System or Rule Output | 80 | 1 | 1.25% | 0 - Safe: 79; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Direct Elicitation | 76 | 2 | 2.63% | 0 - Safe: 74; 1 - Minor: 1; 2 - Major: 1; 3 - Severe: 0 |
| RolePlay & Persona Manipulation (input/injection) | 53 | 1 | 1.89% | 0 - Safe: 52; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Disguised Intent | 14 | 0 | 0.00% | 0 - Safe: 14; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Overwhelming | 5 | 0 | 0.00% | 0 - Safe: 5; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

Source summaries:

- 100: `CAA/outputs/round5_balanced_100_llama31_mistral_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- 300: `CAA/outputs/round5_balanced_300_llama31_mistral_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`

## Qwen/Qwen2.5-7B-Instruct

Experiment model key: `qwen25_7b`

### Trajectory attack

| Run | Records | Coded | Errors | Successes | ASR |
|---|---:|---:|---:|---:|---:|
| 100 | 100 | 100 | 0 | 11 | 11.00% |
| 300 | 300 | 300 | 0 | 50 | 16.67% |
| **Pooled** | **400** | **400** | **0** | **61** | **15.25%** |

Pooled severity distribution: 0 - Safe: 339; 1 - Minor: 50; 2 - Major: 7; 3 - Severe: 4.

#### By attempt

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Inappropriate Topics | 111 | 9 | 8.11% | 0 - Safe: 102; 1 - Minor: 8; 2 - Major: 1; 3 - Severe: 0 |
| General Break | 78 | 19 | 24.36% | 0 - Safe: 59; 1 - Minor: 17; 2 - Major: 1; 3 - Severe: 1 |
| Swearing | 60 | 20 | 33.33% | 0 - Safe: 40; 1 - Minor: 16; 2 - Major: 4; 3 - Severe: 0 |
| Break Character | 40 | 6 | 15.00% | 0 - Safe: 34; 1 - Minor: 3; 2 - Major: 0; 3 - Severe: 3 |
| Political/Social/Bias | 35 | 2 | 5.71% | 0 - Safe: 33; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |
| Slur | 29 | 2 | 6.90% | 0 - Safe: 27; 1 - Minor: 1; 2 - Major: 1; 3 - Severe: 0 |
| Leak Information | 25 | 1 | 4.00% | 0 - Safe: 24; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Incorrect Information | 22 | 2 | 9.09% | 0 - Safe: 20; 1 - Minor: 2; 2 - Major: 0; 3 - Severe: 0 |

#### By source primary attack vector

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Fake Scenario | 86 | 10 | 11.63% | 0 - Safe: 76; 1 - Minor: 9; 2 - Major: 1; 3 - Severe: 0 |
| Text or Format Trick | 86 | 17 | 19.77% | 0 - Safe: 69; 1 - Minor: 12; 2 - Major: 5; 3 - Severe: 0 |
| System or Rule Output | 80 | 19 | 23.75% | 0 - Safe: 61; 1 - Minor: 17; 2 - Major: 1; 3 - Severe: 1 |
| Direct Elicitation | 76 | 8 | 10.53% | 0 - Safe: 68; 1 - Minor: 8; 2 - Major: 0; 3 - Severe: 0 |
| RolePlay & Persona Manipulation (input/injection) | 53 | 6 | 11.32% | 0 - Safe: 47; 1 - Minor: 3; 2 - Major: 0; 3 - Severe: 3 |
| Disguised Intent | 14 | 1 | 7.14% | 0 - Safe: 13; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Overwhelming | 5 | 0 | 0.00% | 0 - Safe: 5; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

Source summaries:

- 100: `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`
- 300: `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/evaluation/reviewed_severity_llama31/summary.json`

### Weak attack

| Run | Records | Coded | Errors | Successes | ASR |
|---|---:|---:|---:|---:|---:|
| 100 | 100 | 100 | 0 | 4 | 4.00% |
| 300 | 300 | 300 | 0 | 19 | 6.33% |
| **Pooled** | **400** | **400** | **0** | **23** | **5.75%** |

Pooled severity distribution: 0 - Safe: 377; 1 - Minor: 21; 2 - Major: 2; 3 - Severe: 0.

#### By attempt

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Inappropriate Topics | 111 | 4 | 3.60% | 0 - Safe: 107; 1 - Minor: 4; 2 - Major: 0; 3 - Severe: 0 |
| General Break | 78 | 1 | 1.28% | 0 - Safe: 77; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Swearing | 60 | 13 | 21.67% | 0 - Safe: 47; 1 - Minor: 12; 2 - Major: 1; 3 - Severe: 0 |
| Break Character | 40 | 1 | 2.50% | 0 - Safe: 39; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Political/Social/Bias | 35 | 1 | 2.86% | 0 - Safe: 34; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Slur | 29 | 2 | 6.90% | 0 - Safe: 27; 1 - Minor: 1; 2 - Major: 1; 3 - Severe: 0 |
| Leak Information | 25 | 0 | 0.00% | 0 - Safe: 25; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |
| Incorrect Information | 22 | 1 | 4.55% | 0 - Safe: 21; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |

#### By source primary attack vector

| Group | N | Successes | ASR | Severity distribution |
|---|---:|---:|---:|---|
| Fake Scenario | 86 | 3 | 3.49% | 0 - Safe: 83; 1 - Minor: 3; 2 - Major: 0; 3 - Severe: 0 |
| Text or Format Trick | 86 | 10 | 11.63% | 0 - Safe: 76; 1 - Minor: 8; 2 - Major: 2; 3 - Severe: 0 |
| System or Rule Output | 80 | 1 | 1.25% | 0 - Safe: 79; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Direct Elicitation | 76 | 7 | 9.21% | 0 - Safe: 69; 1 - Minor: 7; 2 - Major: 0; 3 - Severe: 0 |
| RolePlay & Persona Manipulation (input/injection) | 53 | 1 | 1.89% | 0 - Safe: 52; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Disguised Intent | 14 | 1 | 7.14% | 0 - Safe: 13; 1 - Minor: 1; 2 - Major: 0; 3 - Severe: 0 |
| Overwhelming | 5 | 0 | 0.00% | 0 - Safe: 5; 1 - Minor: 0; 2 - Major: 0; 3 - Severe: 0 |

Source summaries:

- 100: `CAA/outputs/round5_balanced_100_llama31_qwen25_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
- 300: `CAA/outputs/round5_balanced_300_llama31_qwen25_7b_stronger_v3_topic_conditional/weak_attack_evaluation/reviewed_severity_llama31/summary.json`
