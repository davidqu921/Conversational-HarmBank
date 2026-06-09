# Agreement Report

- Eval set: **101 conversations** with both LLM and human coding
- Human label source: `data_prep\sample_truth_label.csv`
- Human coders/label sets: Consensus

## Cohen's kappa per dimension

| Coder | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consensus | 101 | 0.566 | 0.483 | 0.454 | 0.621 | 0.703 | 0.548 |
| **Pooled** | **101** | **0.566** | **0.483** | **0.454** | **0.621** | **0.703** | **0.548** |

## Per-label kappa

### Attack Vector
| Label | kappa | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | 0.468 | 17 | 31 |
| Disguised Intent | 0.676 | 18 | 20 |
| Role Play | 0.638 | 16 | 21 |
| Structured Response | 0.219 | 4 | 4 |
| AI Attack | 0.595 | 6 | 10 |
| No Attempt | 0.803 | 53 | 45 |

### Severity
| Label | LLM positives | Human positives |
|---|---:|---:|
| 0 - Safe | 86 | 81 |
| 1 - Minor | 4 | 14 |
| 2 - Major | 10 | 5 |
| 3 - Severe | 1 | 1 |

## Horizontal conversation-level agreement

These metrics compare each conversation's whole label set within one dimension. They are complementary to the label-wise Cohen's kappa above.

### Multi-label dimensions

| Dimension | Hit Rate | Exact Match | Mean Jaccard | Mean Precision | Mean Recall | Mean F1 |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.832 | 0.653 | 0.740 | 0.809 | 0.759 | 0.769 |
| Type | 0.822 | 0.624 | 0.706 | 0.772 | 0.728 | 0.738 |
| Attempt | 0.832 | 0.703 | 0.760 | 0.903 | 0.804 | 0.781 |

### Single-label dimensions

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.752 |
| Success | 0.911 |
| Severity | 0.861 |