# Round 4 Agreement Report

- Compared IDs: **15**
- A: **David**
- B: **MiniMax-Round4**

## Cohen's Kappa

| Dimension | Kappa |
|---|---:|
| Attack Vector macro binary | 0.373 |
| Attempt macro binary | 0.222 |
| Conversational | 0.022 |
| Severity | 0.762 |

## Relaxed Attack-Vector Agreement

Primary and secondary attack vectors are treated as an unordered set.
The overlap-adjusted value is chance-corrected but is not classic Cohen's kappa.

| Metric | Value |
|---|---:|
| Any-overlap hit rate | 0.800 |
| Exact unordered set match | 0.267 |
| Mean Jaccard | 0.500 |
| Overlap-adjusted kappa-like | 0.563 |

## Multi-label Agreement

| Dimension | Hit Rate | Exact Match | Mean Jaccard |
|---|---:|---:|---:|
| Attack Vector | 0.800 | 0.267 | 0.500 |
| Attempt | 0.467 | 0.467 | 0.467 |

## Single-label Hit Rate

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.200 |
| Severity | 0.867 |

## Per-label Kappa: Attack Vector

| Label | Kappa | A positives | B positives |
|---|---:|---:|---:|
| No Attempt | 0.000 | 0 | 1 |
| System or Rule Output | 0.595 | 4 | 2 |
| Text or Format Trick | -0.098 | 2 | 1 |
| Disguised Intent | 0.412 | 11 | 9 |
| Fake Scenario | -0.129 | 1 | 6 |
| RolePlay & Persona Manipulation (input/injection) | 0.815 | 3 | 4 |
| Social or Emotional Pressure | 0.762 | 2 | 3 |
| Direct Elicitation | 1.000 | 1 | 1 |
| Out of Context/Absurd Conversation | NA | 0 | 0 |
| Overwhelming | 0.000 | 1 | 0 |