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

## Horizontal conversation-level agreement

These metrics compare each conversation's whole label set within one dimension. They are complementary to the label-wise Cohen's kappa above.

### Multi-label dimensions

| Dimension | Hit Rate | Exact Match | Mean Jaccard | Mean Precision | Mean Recall | Mean F1 |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.812 | 0.564 | 0.679 | 0.762 | 0.718 | 0.720 |
| Type | 0.772 | 0.495 | 0.620 | 0.708 | 0.658 | 0.663 |
| Attempt | 0.782 | 0.663 | 0.716 | 0.881 | 0.748 | 0.735 |

### Single-label dimensions

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.653 |
| Success | 0.871 |
| Severity | 0.881 |