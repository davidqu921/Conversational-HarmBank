# Agreement Report Comparison

- Old report: `evaluation\minimax_sample_0\agreement_report.md`
- New report: `evaluation\minimax_sample_1\agreement_report.md`
- Eval set: 101 -> 97 (-4)

> Positive deltas mean the new report improved on that metric. Check eval-set changes before interpreting differences.

## Cohen's Kappa

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Vector (macro) | 0.479 | 0.522 | +0.043 |
| Type (macro) | 0.351 | 0.361 | +0.010 |
| Attempt (macro) | 0.479 | 0.385 | -0.094 |
| Conversational | 0.478 | 0.500 | +0.022 |
| Success | 0.594 | 0.698 | +0.104 |
| Severity | 0.626 | 0.640 | +0.014 |

## Attack Vector Per-label Kappa

| Label | Old kappa | New kappa | Delta | Old LLM+ | New LLM+ | Human+ old->new |
|---|---:|---:|---:|---:|---:|---:|
| AI Attack | 0.478 | 0.327 | -0.151 | 8 | 5 | 11->11 |
| Brute Force | 0.349 | 0.469 | +0.120 | 19 | 23 | 36->35 |
| Disguised Intent | 0.665 | 0.738 | +0.073 | 27 | 20 | 19->18 |
| No Attempt | 0.762 | 0.672 | -0.090 | 50 | 50 | 40->38 |
| Role Play | 0.617 | 0.707 | +0.090 | 14 | 20 | 24->24 |
| Structured Response | 0.000 | 0.220 | +0.220 | 0 | 3 | 5->5 |

## Horizontal Multi-label Agreement

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Vector Hit Rate | 0.812 | 0.794 | -0.018 |
| Vector Exact Match | 0.564 | 0.608 | +0.044 |
| Vector Mean Jaccard | 0.679 | 0.693 | +0.014 |
| Vector Mean Precision | 0.762 | 0.742 | -0.020 |
| Vector Mean Recall | 0.718 | 0.723 | +0.005 |
| Vector Mean F1 | 0.720 | 0.722 | +0.002 |
| Type Hit Rate | 0.772 | 0.742 | -0.030 |
| Type Exact Match | 0.495 | 0.526 | +0.031 |
| Type Mean Jaccard | 0.620 | 0.614 | -0.006 |
| Type Mean Precision | 0.708 | 0.670 | -0.038 |
| Type Mean Recall | 0.658 | 0.646 | -0.012 |
| Type Mean F1 | 0.663 | 0.648 | -0.015 |
| Attempt Hit Rate | 0.782 | 0.732 | -0.050 |
| Attempt Exact Match | 0.663 | 0.629 | -0.034 |
| Attempt Mean Jaccard | 0.716 | 0.675 | -0.041 |
| Attempt Mean Precision | 0.881 | 0.864 | -0.017 |
| Attempt Mean Recall | 0.748 | 0.716 | -0.032 |
| Attempt Mean F1 | 0.735 | 0.691 | -0.044 |

## Horizontal Single-label Agreement

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Conversational Hit Rate | 0.653 | 0.649 | -0.004 |
| Success Hit Rate | 0.871 | 0.897 | +0.026 |
| Severity Hit Rate | 0.881 | 0.876 | -0.005 |

## Severity Label Counts

| Label | Old LLM+ | New LLM+ | Delta LLM+ | Human+ old->new |
|---|---:|---:|---:|---:|
| 0 - Safe | 85 | 79 | -6 | 80->76 |
| 1 - Minor | 9 | 10 | +1 | 14->14 |
| 2 - Major | 6 | 7 | +1 | 5->5 |
| 3 - Severe | 1 | 1 | 0 | 1->1 |
