# Round 3 Agreement Report

- Compared IDs: **10**
- A: **VirtualSteve Coding -  - Arina**
- B: **VirtualSteve Coding -  - David**

## Cohen's Kappa

| Dimension | Kappa |
|---|---:|
| Attack Vector macro | 0.569 |
| Attempt macro | 0.797 |
| Conversational | 0.000 |
| Severity | 0.688 |

## Horizontal Multi-label Agreement

| Dimension | Hit Rate | Exact Match | Mean Jaccard |
|---|---:|---:|---:|
| Attack Vector | 0.700 | 0.600 | 0.650 |
| Attempt | 1.000 | 0.900 | 0.933 |

## Single-label Hit Rate

| Dimension | Hit Rate |
|---|---:|
| Conversational | 0.900 |
| Severity | 0.800 |

## Per-label Kappa: Attack Vector

| Label | Kappa | A positives | B positives |
|---|---:|---:|---:|
| No Attempt | NA | 0 | 0 |
| Direct Elicitation | 0.615 | 2 | 1 |
| Overwhelming | 0.400 | 2 | 5 |
| Out of context/Absurd Conversation | NA | 0 | 0 |
| Disguised Intent | 0.800 | 5 | 4 |
| Text or Format Trick | 0.737 | 3 | 2 |
| Different Language | NA | 0 | 0 |
| Fake Scenario | 0.000 | 0 | 1 |
| Social or Emotional Pressure | 0.000 | 0 | 1 |
| RolePlay & Persona Manipulation | 1.000 | 1 | 1 |
| System or Rule Manipulation | 1.000 | 2 | 2 |