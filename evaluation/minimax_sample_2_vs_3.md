# Agreement Report Comparison

- Old report: `evaluation\minimax_sample_2\agreement_report.md`
- New report: `evaluation\minimax_sample_3\agreement_report.md`
- Eval set: 101 -> 101 (0)

> Positive deltas mean the new report improved on that metric. Check eval-set changes before interpreting differences.

## Cohen's Kappa

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Vector (macro) | 0.537 | 0.561 | +0.024 |
| Type (macro) | 0.471 | 0.459 | -0.012 |
| Attempt (macro) | 0.433 | 0.451 | +0.018 |
| Conversational | 0.566 | 0.511 | -0.055 |
| Success | 0.679 | 0.723 | +0.044 |
| Severity | 0.529 | 0.643 | +0.114 |

## Attack Vector Per-label Kappa

| Label | Old kappa | New kappa | Delta | Old LLM+ | New LLM+ | Human+ old->new |
|---|---:|---:|---:|---:|---:|---:|
| AI Attack | 0.595 | 0.500 | -0.095 | 6 | 5 | 10->10 |
| Brute Force | 0.388 | 0.458 | +0.070 | 17 | 20 | 36->31 |
| Disguised Intent | 0.676 | 0.616 | -0.060 | 18 | 23 | 20->20 |
| No Attempt | 0.706 | 0.763 | +0.057 | 53 | 51 | 40->45 |
| Role Play | 0.638 | 0.714 | +0.076 | 16 | 18 | 21->21 |
| Structured Response | 0.219 | 0.315 | +0.096 | 4 | 2 | 4->4 |

## Horizontal Multi-label Agreement

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Vector Hit Rate | 0.782 | 0.822 | +0.040 |
| Vector Exact Match | 0.604 | 0.663 | +0.059 |
| Vector Mean Jaccard | 0.691 | 0.737 | +0.046 |
| Vector Mean Precision | 0.759 | 0.789 | +0.030 |
| Vector Mean Recall | 0.710 | 0.759 | +0.049 |
| Vector Mean F1 | 0.720 | 0.763 | +0.043 |
| Type Hit Rate | 0.772 | 0.782 | +0.010 |
| Type Exact Match | 0.574 | 0.614 | +0.040 |
| Type Mean Jaccard | 0.656 | 0.689 | +0.033 |
| Type Mean Precision | 0.723 | 0.732 | +0.009 |
| Type Mean Recall | 0.678 | 0.719 | +0.041 |
| Type Mean F1 | 0.688 | 0.716 | +0.028 |
| Attempt Hit Rate | 0.782 | 0.812 | +0.030 |
| Attempt Exact Match | 0.653 | 0.693 | +0.040 |
| Attempt Mean Jaccard | 0.710 | 0.745 | +0.035 |
| Attempt Mean Precision | 0.903 | 0.889 | -0.014 |
| Attempt Mean Recall | 0.754 | 0.799 | +0.045 |
| Attempt Mean F1 | 0.731 | 0.764 | +0.033 |

## Horizontal Single-label Agreement

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Conversational Hit Rate | 0.713 | 0.683 | -0.030 |
| Success Hit Rate | 0.901 | 0.911 | +0.010 |
| Severity Hit Rate | 0.851 | 0.881 | +0.030 |

## Severity Label Counts

| Label | Old LLM+ | New LLM+ | Delta LLM+ | Human+ old->new |
|---|---:|---:|---:|---:|
| 0 - Safe | 86 | 82 | -4 | 80->81 |
| 1 - Minor | 4 | 8 | +4 | 14->14 |
| 2 - Major | 10 | 10 | 0 | 5->5 |
| 3 - Severe | 1 | 1 | 0 | 1->1 |
