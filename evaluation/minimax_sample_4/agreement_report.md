# Agreement Report

- Eval set: **101 conversations** with both LLM and human coding
- Human label source: `data_prep\sample_truth_label.csv`
- Human coders/label sets: Consensus

## Cohen's kappa per dimension

| Coder | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consensus | 101 | 0.550 | 0.426 | 0.403 | 0.560 | 0.638 | 0.578 |
| **Pooled** | **101** | **0.550** | **0.426** | **0.403** | **0.560** | **0.638** | **0.578** |

## Per-label kappa

### Attack Vector
| Label | kappa | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | 0.414 | 17 | 31 |
| Disguised Intent | 0.637 | 17 | 20 |
| Role Play | 0.778 | 18 | 21 |
| Structured Response | 0.315 | 2 | 4 |
| AI Attack | 0.391 | 8 | 10 |
| No Attempt | 0.764 | 53 | 45 |

### Severity
| Label | LLM positives | Human positives |
|---|---:|---:|
| 0 - Safe | 86 | 81 |
| 1 - Minor | 6 | 14 |
| 2 - Major | 8 | 5 |
| 3 - Severe | 1 | 1 |

## Horizontal conversation-level agreement

These metrics compare each conversation's whole label set within one dimension. They are complementary to the label-wise Cohen's kappa above.

### Multi-label dimensions

| Dimension | Hit Rate | Exact Match | Mean Jaccard | Mean Precision | Mean Recall | Mean F1 |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.842 | 0.644 | 0.734 | 0.797 | 0.764 | 0.767 |
| Type | 0.792 | 0.604 | 0.673 | 0.736 | 0.695 | 0.703 |
| Attempt | 0.792 | 0.673 | 0.727 | 0.880 | 0.774 | 0.746 |

### Single-label dimensions

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.713 |
| Success | 0.891 |
| Severity | 0.871 |