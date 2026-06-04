# Agreement Report

- Eval set: **97 conversations** with both LLM and human coding
- Human label source: `data_prep\sample_truth_label.csv`
- Human coders/label sets: Consensus

## Cohen's kappa per dimension

| Coder | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consensus | 97 | 0.522 | 0.361 | 0.385 | 0.500 | 0.698 | 0.640 |
| **Pooled** | **97** | **0.522** | **0.361** | **0.385** | **0.500** | **0.698** | **0.640** |

## Per-label kappa

### Attack Vector
| Label | kappa | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | 0.469 | 23 | 35 |
| Disguised Intent | 0.738 | 20 | 18 |
| Role Play | 0.707 | 20 | 24 |
| Structured Response | 0.220 | 3 | 5 |
| AI Attack | 0.327 | 5 | 11 |
| No Attempt | 0.672 | 50 | 38 |

### Severity
| Label | LLM positives | Human positives |
|---|---:|---:|
| 0 - Safe | 79 | 76 |
| 1 - Minor | 10 | 14 |
| 2 - Major | 7 | 5 |
| 3 - Severe | 1 | 1 |

## Horizontal conversation-level agreement

These metrics compare each conversation's whole label set within one dimension. They are complementary to the label-wise Cohen's kappa above.

### Multi-label dimensions

| Dimension | Hit Rate | Exact Match | Mean Jaccard | Mean Precision | Mean Recall | Mean F1 |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.794 | 0.608 | 0.693 | 0.742 | 0.723 | 0.722 |
| Type | 0.742 | 0.526 | 0.614 | 0.670 | 0.646 | 0.648 |
| Attempt | 0.732 | 0.629 | 0.675 | 0.864 | 0.716 | 0.691 |

### Single-label dimensions

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.649 |
| Success | 0.897 |
| Severity | 0.876 |