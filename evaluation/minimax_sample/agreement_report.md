# Agreement Report

- Eval set: **99 conversations** with both LLM and human coding
- Human label source: `data_prep\sample_truth_label.csv`
- Human coders/label sets: Consensus

## Cohen's kappa per dimension

| Coder | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consensus | 99 | 0.485 | 0.355 | 0.490 | 0.469 | 0.573 | 0.608 |
| **Pooled** | **99** | **0.485** | **0.355** | **0.490** | **0.469** | **0.573** | **0.608** |

## Per-label kappa

### Attack Vector
| Label | kappa | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | 0.344 | 19 | 36 |
| Disguised Intent | 0.653 | 26 | 18 |
| Role Play | 0.642 | 13 | 24 |
| Structured Response | 0.000 | 0 | 4 |
| AI Attack | 0.512 | 8 | 10 |
| No Attempt | 0.757 | 49 | 39 |

### Severity
| Label | LLM positives | Human positives |
|---|---:|---:|
| 0 - Safe | 84 | 79 |
| 1 - Minor | 8 | 13 |
| 2 - Major | 6 | 5 |
| 3 - Severe | 1 | 1 |