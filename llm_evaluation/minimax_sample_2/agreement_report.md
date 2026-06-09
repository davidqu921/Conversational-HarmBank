# Agreement Report

- Eval set: **101 conversations** with both LLM and human coding
- Human label source: `data_prep\sample_truth_label.csv`
- Human coders/label sets: Consensus

## Cohen's kappa per dimension

| Coder | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consensus | 101 | 0.537 | 0.471 | 0.433 | 0.566 | 0.679 | 0.529 |
| **Pooled** | **101** | **0.537** | **0.471** | **0.433** | **0.566** | **0.679** | **0.529** |

## Per-label kappa

### Attack Vector
| Label | kappa | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | 0.388 | 17 | 36 |
| Disguised Intent | 0.676 | 18 | 20 |
| Role Play | 0.638 | 16 | 21 |
| Structured Response | 0.219 | 4 | 4 |
| AI Attack | 0.595 | 6 | 10 |
| No Attempt | 0.706 | 53 | 40 |

### Severity
| Label | LLM positives | Human positives |
|---|---:|---:|
| 0 - Safe | 86 | 80 |
| 1 - Minor | 4 | 14 |
| 2 - Major | 10 | 5 |
| 3 - Severe | 1 | 1 |

## Horizontal conversation-level agreement

These metrics compare each conversation's whole label set within one dimension. They are complementary to the label-wise Cohen's kappa above.

### Multi-label dimensions

| Dimension | Hit Rate | Exact Match | Mean Jaccard | Mean Precision | Mean Recall | Mean F1 |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.782 | 0.604 | 0.691 | 0.759 | 0.710 | 0.720 |
| Type | 0.772 | 0.574 | 0.656 | 0.723 | 0.678 | 0.688 |
| Attempt | 0.782 | 0.653 | 0.710 | 0.903 | 0.754 | 0.731 |

### Single-label dimensions

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.713 |
| Success | 0.901 |
| Severity | 0.851 |