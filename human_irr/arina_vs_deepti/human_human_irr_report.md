# Human-Human IRR Report

- Eval set: **100 conversations** coded by both human coders
- Coder A: **Arina** from `data_prep\human_label_2\Coding - Jailbreak (H-H) Arina.csv`
- Coder B: **Deepti** from `data_prep\human_label_2\Coding - Jailbreak (H-H) Deepti.csv`

## Cohen's kappa per dimension

| Comparison | n | Vector (macro) | Type (macro) | Attempt (macro) | Conversational | Success | Severity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Arina vs Deepti | 100 | 0.497 | 0.341 | 0.466 | 0.820 | 0.743 | 0.691 |

## Per-label kappa

### Attack Vector
| Label | kappa | Arina positives | Deepti positives |
|---|---:|---:|---:|
| Brute Force | 0.711 | 25 | 33 |
| Disguised Intent | 0.519 | 5 | 6 |
| Role Play | 0.463 | 11 | 5 |
| Structured Response | 0.000 | 3 | 0 |
| AI Attack | 0.390 | 10 | 8 |
| No Attempt | 0.896 | 60 | 59 |

### Severity
| Label | Arina positives | Deepti positives |
|---|---:|---:|
| 0 - Safe | 28 | 33 |
| 1 - Minor | 7 | 8 |
| 2 - Major | 0 | 0 |
| 3 - Severe | 0 | 0 |

## Horizontal conversation-level agreement

These metrics compare each conversation's whole label set within one dimension. This is the closest human-human counterpart to the LLM-vs-human success-rate style metrics.

### Multi-label dimensions

| Dimension | Hit Rate | Exact Match | Mean Jaccard | Mean Precision | Mean Recall | Mean F1 |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.900 | 0.740 | 0.810 | 0.850 | 0.858 | 0.836 |
| Type | 0.850 | 0.640 | 0.728 | 0.767 | 0.792 | 0.762 |
| Attempt | 0.840 | 0.750 | 0.792 | 0.820 | 0.842 | 0.806 |

### Single-label dimensions

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.900 |
| Success | 0.860 |
| Severity | 0.840 |