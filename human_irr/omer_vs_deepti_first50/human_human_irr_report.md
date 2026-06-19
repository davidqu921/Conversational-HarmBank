# Human-Human IRR Report

- Eval set: **50 conversations** coded by both human coders
- Coder A: **Omer** from `data_prep\human_label_1\Coding - Jailbreak (balanced) - Omer.csv`
- Coder B: **Deepti** from `data_prep\human_label_1\Coding - Jailbreak (balanced) - Deepti.csv`
- Max conversations loaded per coder file: **50**

## Cohen's kappa per dimension

| Comparison | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Omer vs Deepti | 50 | 0.435 | 0.331 | 0.403 | 0.532 | 0.188 | 0.136 |

## Per-label kappa

### Attack Vector
| Label | kappa | Omer positives | Deepti positives |
|---|---:|---:|---:|
| Brute Force | 0.636 | 16 | 9 |
| Disguised Intent | 0.747 | 12 | 15 |
| Role Play | 0.511 | 13 | 7 |
| Structured Response | -0.027 | 2 | 1 |
| AI Attack | 0.169 | 11 | 4 |
| No Attempt | 0.576 | 8 | 16 |

### Severity
| Label | Omer positives | Deepti positives |
|---|---:|---:|
| 0 - Safe | 37 | 19 |
| 1 - Minor | 8 | 7 |
| 2 - Major | 4 | 1 |
| 3 - Severe | 1 | 1 |

## Horizontal conversation-level agreement

These metrics compare each conversation's whole label set within one dimension. This is the closest human-human counterpart to the LLM-vs-human success-rate style metrics.

### Multi-label dimensions

| Dimension | Hit Rate | Exact Match | Mean Jaccard | Mean Precision | Mean Recall | Mean F1 |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.680 | 0.420 | 0.548 | 0.750 | 0.630 | 0.591 |
| Type | 0.580 | 0.320 | 0.443 | 0.630 | 0.537 | 0.485 |
| Attempt | 0.600 | 0.420 | 0.502 | 0.803 | 0.530 | 0.530 |

### Single-label dimensions

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.660 |
| Success | 0.440 |
| Severity | 0.400 |