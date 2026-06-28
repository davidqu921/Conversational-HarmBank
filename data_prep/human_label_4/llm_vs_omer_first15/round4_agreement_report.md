# Round 4 Agreement Report

- Compared IDs: **15**
- A: **Omer**
- B: **MiniMax-Round4**

## Cohen's Kappa

| Dimension | Kappa |
|---|---:|
| Attack Vector macro binary | 0.261 |
| Attempt macro binary | 0.290 |
| Conversational | 0.010 |
| Severity | 0.762 |

## Relaxed Attack-Vector Agreement

Primary and secondary attack vectors are treated as an unordered set.
The overlap-adjusted value is chance-corrected but is not classic Cohen's kappa.

| Metric | Value |
|---|---:|
| Any-overlap hit rate | 0.733 |
| Exact unordered set match | 0.200 |
| Mean Jaccard | 0.411 |
| Overlap-adjusted kappa-like | 0.429 |

## Multi-label Agreement

| Dimension | Hit Rate | Exact Match | Mean Jaccard |
|---|---:|---:|---:|
| Attack Vector | 0.733 | 0.200 | 0.411 |
| Attempt | 0.600 | 0.533 | 0.567 |

## Single-label Hit Rate

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.133 |
| Severity | 0.867 |

## Per-label Kappa: Attack Vector

| Label | Kappa | A positives | B positives |
|---|---:|---:|---:|
| No Attempt | 0.000 | 0 | 1 |
| System or Rule Output | 0.595 | 4 | 2 |
| Text or Format Trick | -0.098 | 2 | 1 |
| Disguised Intent | 0.286 | 10 | 9 |
| Fake Scenario | -0.129 | 1 | 6 |
| RolePlay & Persona Manipulation (input/injection) | 0.659 | 4 | 4 |
| Social or Emotional Pressure | 0.444 | 1 | 3 |
| Direct Elicitation | 0.328 | 4 | 1 |
| Out of Context/Absurd Conversation | NA | 0 | 0 |
| Overwhelming | NA | 0 | 0 |