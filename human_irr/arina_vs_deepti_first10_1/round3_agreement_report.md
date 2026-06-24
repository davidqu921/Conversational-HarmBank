# Round 3 Agreement Report

- Compared IDs: **10**
- A: **VirtualSteve Coding -  - Arina**
- B: **VirtualSteve Coding -  - Deepti (1)**

## Cohen's Kappa

| Dimension | Kappa |
|---|---:|
| Attack Vector macro | 0.747 |
| Attempt macro | 0.833 |
| Conversational | 1.000 |
| Severity | 0.552 |

## Horizontal Multi-label Agreement

| Dimension | Hit Rate | Exact Match | Mean Jaccard |
|---|---:|---:|---:|
| Attack Vector | 1.000 | 0.600 | 0.800 |
| Attempt | 1.000 | 0.900 | 0.950 |

## Single-label Hit Rate

| Dimension | Hit Rate |
|---|---:|
| Conversational | 1.000 |
| Severity | 0.700 |

## Per-label Kappa: Attack Vector

| Label | Kappa | A positives | B positives |
|---|---:|---:|---:|
| No Attempt | NA | 0 | 0 |
| Direct Elicitation | 1.000 | 2 | 2 |
| Overwhelming | 0.615 | 2 | 1 |
| Out of context/Absurd Conversation | NA | 0 | 0 |
| Disguised Intent | 1.000 | 5 | 5 |
| Text or Format Trick | 1.000 | 3 | 3 |
| Different Language | NA | 0 | 0 |
| Fake Scenario | NA | 0 | 0 |
| Social or Emotional Pressure | 0.000 | 0 | 2 |
| RolePlay & Persona Manipulation | 0.615 | 1 | 2 |
| System or Rule Manipulation | 1.000 | 2 | 2 |