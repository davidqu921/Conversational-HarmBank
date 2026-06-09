# Agreement Report

- Eval set: **101 conversations** with both LLM and human coding
- Human label source: `data_prep\sample_truth_label.csv`
- Human coders/label sets: Consensus

## Cohen's kappa per dimension

| Coder | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consensus | 101 | 0.561 | 0.459 | 0.451 | 0.511 | 0.723 | 0.643 |
| **Pooled** | **101** | **0.561** | **0.459** | **0.451** | **0.511** | **0.723** | **0.643** |

## Per-label kappa

### Attack Vector
| Label | kappa | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | 0.458 | 20 | 31 |
| Disguised Intent | 0.616 | 23 | 20 |
| Role Play | 0.714 | 18 | 21 |
| Structured Response | 0.315 | 2 | 4 |
| AI Attack | 0.500 | 5 | 10 |
| No Attempt | 0.763 | 51 | 45 |

### Severity
| Label | LLM positives | Human positives |
|---|---:|---:|
| 0 - Safe | 82 | 81 |
| 1 - Minor | 8 | 14 |
| 2 - Major | 10 | 5 |
| 3 - Severe | 1 | 1 |

## Horizontal conversation-level agreement

These metrics compare each conversation's whole label set within one dimension. They are complementary to the label-wise Cohen's kappa above.

### Multi-label dimensions

| Dimension | Hit Rate | Exact Match | Mean Jaccard | Mean Precision | Mean Recall | Mean F1 |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.822 | 0.663 | 0.737 | 0.789 | 0.759 | 0.763 |
| Type | 0.782 | 0.614 | 0.689 | 0.732 | 0.719 | 0.716 |
| Attempt | 0.812 | 0.693 | 0.745 | 0.889 | 0.799 | 0.764 |

### Single-label dimensions

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.683 |
| Success | 0.911 |
| Severity | 0.881 |