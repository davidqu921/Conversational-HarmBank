# Round 3 Agreement Report

- Compared IDs: **10**
- A: **VirtualSteve Coding -  - Omer**
- B: **VirtualSteve Coding -  - David**

## Cohen's Kappa

| Dimension | Kappa |
|---|---:|
| Attack Vector macro | 0.588 |
| Attempt macro | 0.957 |
| Conversational | 0.000 |
| Severity | 0.365 |

## Horizontal Multi-label Agreement

| Dimension | Hit Rate | Exact Match | Mean Jaccard |
|---|---:|---:|---:|
| Attack Vector | 0.900 | 0.500 | 0.683 |
| Attempt | 1.000 | 0.900 | 0.950 |

## Single-label Hit Rate

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.900 |
| Severity | 0.600 |

## Per-label Kappa: Attack Vector

| Label | Kappa | A positives | B positives |
|---|---:|---:|---:|
| No Attempt | NA | 0 | 0 |
| Direct Elicitation | 1.000 | 2 | 2 |
| Overwhelming | 0.737 | 2 | 3 |
| Out of context/Absurd Conversation | 0.000 | 1 | 0 |
| Disguised Intent | 0.583 | 4 | 4 |
| Text or Format Trick | 0.737 | 2 | 3 |
| Different Language | NA | 0 | 0 |
| Fake Scenario | 0.615 | 2 | 1 |
| Social or Emotional Pressure | 0.615 | 2 | 1 |
| RolePlay & Persona Manipulation | 0.000 | 0 | 1 |
| System or Rule Manipulation | 1.000 | 2 | 2 |