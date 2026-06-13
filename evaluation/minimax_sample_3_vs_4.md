# Agreement Report Comparison

- Old report: `evaluation\minimax_sample_3\agreement_report.md`
- New report: `evaluation\minimax_sample_4\agreement_report.md`
- Eval set: 101 -> 101 (0)

> Positive deltas mean the new report improved on that metric. Check eval-set changes before interpreting differences.

## Cohen's Kappa

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Vector (macro) | 0.561 | 0.550 | -0.011 |
| Type (macro) | 0.459 | 0.426 | -0.033 |
| Attempt (macro) | 0.451 | 0.403 | -0.048 |
| Conversational | 0.511 | 0.560 | +0.049 |
| Success | 0.723 | 0.638 | -0.085 |
| Severity | 0.643 | 0.578 | -0.065 |

## Attack Vector Per-label Kappa

| Label | Old kappa | New kappa | Delta | Old LLM+ | New LLM+ | Human+ old->new |
|---|---:|---:|---:|---:|---:|---:|
| AI Attack | 0.500 | 0.391 | -0.109 | 5 | 8 | 10->10 |
| Brute Force | 0.458 | 0.414 | -0.044 | 20 | 17 | 31->31 |
| Disguised Intent | 0.616 | 0.637 | +0.021 | 23 | 17 | 20->20 |
| No Attempt | 0.763 | 0.764 | +0.001 | 51 | 53 | 45->45 |
| Role Play | 0.714 | 0.778 | +0.064 | 18 | 18 | 21->21 |
| Structured Response | 0.315 | 0.315 | 0.000 | 2 | 2 | 4->4 |

## Horizontal Multi-label Agreement

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Vector Hit Rate | 0.822 | 0.842 | +0.020 |
| Vector Exact Match | 0.663 | 0.644 | -0.019 |
| Vector Mean Jaccard | 0.737 | 0.734 | -0.003 |
| Vector Mean Precision | 0.789 | 0.797 | +0.008 |
| Vector Mean Recall | 0.759 | 0.764 | +0.005 |
| Vector Mean F1 | 0.763 | 0.767 | +0.004 |
| Type Hit Rate | 0.782 | 0.792 | +0.010 |
| Type Exact Match | 0.614 | 0.604 | -0.010 |
| Type Mean Jaccard | 0.689 | 0.673 | -0.016 |
| Type Mean Precision | 0.732 | 0.736 | +0.004 |
| Type Mean Recall | 0.719 | 0.695 | -0.024 |
| Type Mean F1 | 0.716 | 0.703 | -0.013 |
| Attempt Hit Rate | 0.812 | 0.792 | -0.020 |
| Attempt Exact Match | 0.693 | 0.673 | -0.020 |
| Attempt Mean Jaccard | 0.745 | 0.727 | -0.018 |
| Attempt Mean Precision | 0.889 | 0.880 | -0.009 |
| Attempt Mean Recall | 0.799 | 0.774 | -0.025 |
| Attempt Mean F1 | 0.764 | 0.746 | -0.018 |

## Horizontal Single-label Agreement

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Conversational Hit Rate | 0.683 | 0.713 | +0.030 |
| Success Hit Rate | 0.911 | 0.891 | -0.020 |
| Severity Hit Rate | 0.881 | 0.871 | -0.010 |

## Severity Label Counts

| Label | Old LLM+ | New LLM+ | Delta LLM+ | Human+ old->new |
|---|---:|---:|---:|---:|
| 0 - Safe | 82 | 86 | +4 | 81->81 |
| 1 - Minor | 8 | 6 | -2 | 14->14 |
| 2 - Major | 10 | 8 | -2 | 5->5 |
| 3 - Severe | 1 | 1 | 0 | 1->1 |
