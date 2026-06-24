# Round 3 Agreement Report

- Compared IDs: **10**
- A: **VirtualSteve Coding -  - Arina**
- B: **VirtualSteve Coding -  - Omer (1)**

## Cohen's Kappa

| Dimension | Kappa |
|---|---:|
| Attack Vector macro | 0.615 |
| Attempt macro | 0.833 |
| Conversational | 1.000 |
| Severity | 1.000 |

## Horizontal Multi-label Agreement

| Dimension | Hit Rate | Exact Match | Mean Jaccard |
|---|---:|---:|---:|
| Attack Vector | 0.900 | 0.500 | 0.700 |
| Attempt | 1.000 | 0.900 | 0.950 |

## Single-label Hit Rate

| Dimension | Hit Rate |
|---|---:|
| Conversational | 1.000 |
| Severity | 1.000 |

## Per-label Kappa: Attack Vector

| Label | Kappa | A positives | B positives |
|---|---:|---:|---:|
| No Attempt | NA | 0 | 0 |
| Direct Elicitation | 1.000 | 2 | 2 |
| Overwhelming | 0.737 | 2 | 3 |
| Out of context/Absurd Conversation | 0.000 | 0 | 1 |
| Disguised Intent | 0.800 | 5 | 4 |
| Text or Format Trick | 1.000 | 3 | 3 |
| Different Language | NA | 0 | 0 |
| Fake Scenario | 0.000 | 0 | 1 |
| Social or Emotional Pressure | 0.000 | 0 | 2 |
| RolePlay & Persona Manipulation | 1.000 | 1 | 1 |
| System or Rule Manipulation | 1.000 | 2 | 2 |