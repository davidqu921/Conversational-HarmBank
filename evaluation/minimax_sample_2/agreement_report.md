# Agreement Report

- Eval set: **100 conversations** with both LLM and human coding
- Human label source: `data_prep\sample_truth_label.csv`
- Human coders/label sets: Consensus

## Cohen's kappa per dimension

| Coder | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consensus | 100 | 0.536 | 0.471 | 0.433 | 0.576 | 0.679 | 0.528 |
| **Pooled** | **100** | **0.536** | **0.471** | **0.433** | **0.576** | **0.679** | **0.528** |

## Per-label kappa

### Attack Vector
| Label | kappa | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | 0.387 | 17 | 36 |
| Disguised Intent | 0.675 | 18 | 20 |
| Role Play | 0.637 | 16 | 21 |
| Structured Response | 0.219 | 4 | 4 |
| AI Attack | 0.595 | 6 | 10 |
| No Attempt | 0.703 | 52 | 39 |

### Severity
| Label | LLM positives | Human positives |
|---|---:|---:|
| 0 - Safe | 85 | 79 |
| 1 - Minor | 4 | 14 |
| 2 - Major | 10 | 5 |
| 3 - Severe | 1 | 1 |

## Horizontal conversation-level agreement

These metrics compare each conversation's whole label set within one dimension. They are complementary to the label-wise Cohen's kappa above.

### Multi-label dimensions

| Dimension | Hit Rate | Exact Match | Mean Jaccard | Mean Precision | Mean Recall | Mean F1 |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.780 | 0.600 | 0.688 | 0.757 | 0.707 | 0.717 |
| Type | 0.770 | 0.570 | 0.653 | 0.720 | 0.675 | 0.685 |
| Attempt | 0.780 | 0.650 | 0.708 | 0.902 | 0.752 | 0.729 |

### Single-label dimensions

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.720 |
| Success | 0.900 |
| Severity | 0.850 |