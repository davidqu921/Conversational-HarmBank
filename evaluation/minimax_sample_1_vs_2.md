# Agreement Report Comparison

- Old report: `evaluation\minimax_sample_1\agreement_report.md`
- New report: `evaluation\minimax_sample_2\agreement_report.md`
- Eval set: 97 -> 100 (+3)

> Positive deltas mean the new report improved on that metric. Check eval-set changes before interpreting differences.

## Cohen's Kappa

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Vector (macro) | 0.522 | 0.536 | +0.014 |
| Type (macro) | 0.361 | 0.471 | +0.110 |
| Attempt (macro) | 0.385 | 0.433 | +0.048 |
| Conversational | 0.500 | 0.576 | +0.076 |
| Success | 0.698 | 0.679 | -0.019 |
| Severity | 0.640 | 0.528 | -0.112 |

## Attack Vector Per-label Kappa

| Label | Old kappa | New kappa | Delta | Old LLM+ | New LLM+ | Human+ old->new |
|---|---:|---:|---:|---:|---:|---:|
| AI Attack | 0.327 | 0.595 | +0.268 | 5 | 6 | 11->10 |
| Brute Force | 0.469 | 0.387 | -0.082 | 23 | 17 | 35->36 |
| Disguised Intent | 0.738 | 0.675 | -0.063 | 20 | 18 | 18->20 |
| No Attempt | 0.672 | 0.703 | +0.031 | 50 | 52 | 38->39 |
| Role Play | 0.707 | 0.637 | -0.070 | 20 | 16 | 24->21 |
| Structured Response | 0.220 | 0.219 | -0.001 | 3 | 4 | 5->4 |

## Horizontal Multi-label Agreement

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Vector Hit Rate | 0.794 | 0.780 | -0.014 |
| Vector Exact Match | 0.608 | 0.600 | -0.008 |
| Vector Mean Jaccard | 0.693 | 0.688 | -0.005 |
| Vector Mean Precision | 0.742 | 0.757 | +0.015 |
| Vector Mean Recall | 0.723 | 0.707 | -0.016 |
| Vector Mean F1 | 0.722 | 0.717 | -0.005 |
| Type Hit Rate | 0.742 | 0.770 | +0.028 |
| Type Exact Match | 0.526 | 0.570 | +0.044 |
| Type Mean Jaccard | 0.614 | 0.653 | +0.039 |
| Type Mean Precision | 0.670 | 0.720 | +0.050 |
| Type Mean Recall | 0.646 | 0.675 | +0.029 |
| Type Mean F1 | 0.648 | 0.685 | +0.037 |
| Attempt Hit Rate | 0.732 | 0.780 | +0.048 |
| Attempt Exact Match | 0.629 | 0.650 | +0.021 |
| Attempt Mean Jaccard | 0.675 | 0.708 | +0.033 |
| Attempt Mean Precision | 0.864 | 0.902 | +0.038 |
| Attempt Mean Recall | 0.716 | 0.752 | +0.036 |
| Attempt Mean F1 | 0.691 | 0.729 | +0.038 |

## Horizontal Single-label Agreement

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| Conversational Hit Rate | 0.649 | 0.720 | +0.071 |
| Success Hit Rate | 0.897 | 0.900 | +0.003 |
| Severity Hit Rate | 0.876 | 0.850 | -0.026 |

## Severity Label Counts

| Label | Old LLM+ | New LLM+ | Delta LLM+ | Human+ old->new |
|---|---:|---:|---:|---:|
| 0 - Safe | 79 | 85 | +6 | 76->79 |
| 1 - Minor | 10 | 4 | -6 | 14->14 |
| 2 - Major | 7 | 10 | +3 | 5->5 |
| 3 - Severe | 1 | 1 | 0 | 1->1 |
