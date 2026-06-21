# Round 3 Agreement Report

- Compared IDs: **10**
- A: **VirtualSteve Coding -  - Arina**
- B: **VirtualSteve Coding -  - Deepti**

## Cohen's Kappa

| Dimension | Kappa |
|---|---:|
| Attack Vector macro | 0.551 |
| Attempt macro | 0.833 |
| Conversational | 1.000 |
| Severity | 0.254 |

## Horizontal Multi-label Agreement

| Dimension | Hit Rate | Exact Match | Mean Jaccard |
|---|---:|---:|---:|
| Attack Vector | 1.000 | 0.400 | 0.667 |
| Attempt | 1.000 | 0.900 | 0.950 |

## Single-label Hit Rate

| Dimension | Hit Rate |
|---|---:|
| Conversational | 1.000 |
| Severity | 0.500 |

## Per-label Kappa: Attack Vector

| Label | Kappa | A positives | B positives |
|---|---:|---:|---:|
| No Attempt | NA | 0 | 0 |
| Direct Elicitation | 0.375 | 2 | 2 |
| Overwhelming | 0.615 | 2 | 1 |
| Out of context/Absurd Conversation | 0.000 | 0 | 1 |
| Disguised Intent | 0.800 | 5 | 6 |
| Text or Format Trick | 1.000 | 3 | 3 |
| Different Language | NA | 0 | 0 |
| Fake Scenario | NA | 0 | 0 |
| Social or Emotional Pressure | 0.000 | 0 | 2 |
| RolePlay & Persona Manipulation | 0.615 | 1 | 2 |
| System or Rule Manipulation | 1.000 | 2 | 2 |