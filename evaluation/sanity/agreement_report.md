# Agreement Report

- Eval set: **100 conversations** with both LLM and human coding
- Human coders: Anson Kwok, David, Jailbreak-Anushree, Jania, Taylor

## Cohen's κ per dimension, LLM vs each human coder

| Coder | n | Vector (macro) | Subtype (macro) | Attempt (macro) | Conversational | Success |
|---|---:|---:|---:|---:|---:|---:|
| Anson Kwok | 100 | 1.000 | 1.000 | 1.000 | 0.504 | 0.289 |
| David | 22 | 0.460 | 0.075 | 0.376 | 0.183 | 0.136 |
| Jailbreak-Anushree | 21 | 0.481 | 0.293 | 0.193 | 0.362 | 0.171 |
| Jania | 100 | 0.540 | 0.294 | 0.502 | 0.287 | 0.183 |
| Taylor | 35 | 0.358 | 0.163 | 0.342 | 0.473 | 0.361 |
| **Pooled** | **278** | **0.606** | **0.435** | **0.668** | **0.386** | **0.229** |

## Per-label κ (pooled across coders)

### Attack Vector
| Label | κ | LLM positives | Human positives |
|---|---:|---:|---:|
| Brute Force | 0.676 | 70 | 58 |
| Disguised Intent | 0.753 | 52 | 53 |
| Role Play | 0.777 | 48 | 43 |
| Structured Response | 0.000 | 0 | 8 |
| AI Attack | 0.560 | 7 | 7 |
| No Attempt | 0.870 | 101 | 110 |

### Subtype (top by human frequency)
| Label | κ | LLM positives | Human positives |
|---|---:|---:|---:|
| Wordplay | 0.806 | 47 | 46 |
| One Shot | 0.690 | 59 | 43 |
| Fake Scenario | 0.604 | 26 | 24 |
| Overwhelming | 0.393 | 2 | 8 |
| Out of Context | 0.211 | 9 | 8 |
| Fake Persona | 0.438 | 2 | 7 |
| Threats | 0.931 | 8 | 7 |
| Emotional Manipulation | 0.542 | 12 | 6 |
| Testing | 0.240 | 3 | 5 |
| Different Language | 0.000 | 0 | 5 |
| Prompt Injection | 0.000 | 0 | 3 |
| Re-prompting | 0.566 | 4 | 3 |

## Human-vs-human ceiling (IRR set, n=35)

Pairwise mean κ across all coder pairs on the IRR conversations.

- **Attack Vector (macro)**: mean pairwise κ = 0.440  (over 10 pairs)
- **Subtype (macro)**: mean pairwise κ = 0.226  (over 10 pairs)
- **Attempt (macro)**: mean pairwise κ = 0.343  (over 10 pairs)
- **Conversational**: mean pairwise κ = 0.484  (over 10 pairs)
- **Success**: mean pairwise κ = 0.295  (over 10 pairs)