# Agreement Report

- Eval set: **101 conversations** with both LLM and human coding
- Human label source: `data_prep\sample_truth_label.csv`
- Human coders/label sets: Consensus

## Cohen's kappa per dimension

| Coder | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consensus | 101 | 0.479 | 0.351 | 0.479 | 0.478 | 0.594 | 0.626 |
| **Pooled** | **101** | **0.479** | **0.351** | **0.479** | **0.478** | **0.594** | **0.626** |

## Per-label kappa

### Attack Vector
| Label | kappa | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | 0.349 | 19 | 36 |
| Disguised Intent | 0.665 | 27 | 19 |
| Role Play | 0.617 | 14 | 24 |
| Structured Response | 0.000 | 0 | 5 |
| AI Attack | 0.478 | 8 | 11 |
| No Attempt | 0.762 | 50 | 40 |

### Severity
| Label | LLM positives | Human positives |
|---|---:|---:|
| 0 - Safe | 85 | 80 |
| 1 - Minor | 9 | 14 |
| 2 - Major | 6 | 5 |
| 3 - Severe | 1 | 1 |