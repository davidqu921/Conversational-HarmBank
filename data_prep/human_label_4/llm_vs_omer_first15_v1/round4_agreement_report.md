# Round 4 Agreement Report

- Compared IDs: **15**
- A: **Omer**
- B: **MiniMax-Round4**

## Cohen's Kappa

| Dimension | Kappa |
|---|---:|
| Attack Vector macro binary | 0.370 |
| Attempt macro binary | 0.220 |
| Conversational | 0.022 |
| Severity | 0.286 |

## Relaxed Attack-Vector Agreement

Primary and secondary attack vectors are treated as an unordered set.
The overlap-adjusted value is chance-corrected but is not classic Cohen's kappa.

| Metric | Value |
|---|---:|
| Any-overlap hit rate | 0.800 |
| Exact unordered set match | 0.267 |
| Mean Jaccard | 0.467 |
| Overlap-adjusted kappa-like | 0.559 |

## Multi-label Agreement

| Dimension | Hit Rate | Exact Match | Mean Jaccard |
|---|---:|---:|---:|
| Attack Vector | 0.800 | 0.267 | 0.467 |
| Attempt | 0.467 | 0.400 | 0.433 |

## Single-label Hit Rate

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.200 |
| Severity | 0.467 |

## Per-label Kappa: Attack Vector

| Label | Kappa | A positives | B positives |
|---|---:|---:|---:|
| No Attempt | NA | 0 | 0 |
| System or Rule Output | 0.815 | 4 | 3 |
| Text or Format Trick | -0.154 | 2 | 2 |
| Disguised Intent | 0.000 | 10 | 9 |
| Fake Scenario | 0.194 | 1 | 6 |
| RolePlay & Persona Manipulation (input/injection) | 0.815 | 4 | 3 |
| Social or Emotional Pressure | 0.328 | 1 | 4 |
| Direct Elicitation | 0.595 | 4 | 2 |
| Out of Context/Absurd Conversation | NA | 0 | 0 |
| Overwhelming | NA | 0 | 0 |