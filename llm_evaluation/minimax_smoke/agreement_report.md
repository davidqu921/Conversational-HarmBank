# Agreement Report

- Eval set: **3 conversations** with both LLM and human coding
- Human label source: `data_prep\sample_truth_label.csv`
- Human coders/label sets: Consensus

## Cohen's kappa per dimension

| Coder | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consensus | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| **Pooled** | **3** | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** |

## Per-label kappa

### Attack Vector
| Label | kappa | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | nan | 0 | 0 |
| Disguised Intent | 1.000 | 1 | 1 |
| Role Play | 1.000 | 1 | 1 |
| Structured Response | nan | 0 | 0 |
| AI Attack | nan | 0 | 0 |
| No Attempt | 1.000 | 1 | 1 |

### Severity
| Label | LLM positives | Human positives |
|---|---:|---:|
| 0 - Safe | 2 | 2 |
| 1 - Minor | 0 | 0 |
| 2 - Major | 1 | 1 |
| 3 - Severe | 0 | 0 |