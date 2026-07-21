# Scripts

Run Python entry points as modules from the repository root. The canonical
publication flow is documented in [`../preprocessing/README.md`](../preprocessing/README.md).

## Active Round 5 pipeline

| Package | Purpose |
| --- | --- |
| `preprocessing/` | One-config post-review build, category assignment, CAA contract validation, and provenance manifest. |
| `data_prep/` | Transcript normalization plus human-review template preparation, normalization, and checks. |
| `coding/` | Current whole-conversation Round 4 LLM coding. |
| `segmentation/` | Turn numbering and phase/action segmentation. |
| `fill_back_turn_actions/` | Successful-attack action fill-back and coverage repair audit. |
| `new_cab/` | Round 5 phrase/turn CAB, statistics, and phase/action CAG implementation called by the publication runner. |
| `evaluation/` | Human/LLM agreement and discrepancy reports. |

Canonical read-only handoff check:

```powershell
python -m scripts.preprocessing.run_publication_pipeline --validate-only
```

Canonical deterministic rebuild after human review is frozen:

```powershell
python -m scripts.preprocessing.run_publication_pipeline --build --dry-run
python -m scripts.preprocessing.run_publication_pipeline --build
```

## Historical implementations

`cab/` and `cag/` implement the earlier CAB/CAG format. Earlier label rounds,
earlier result directories, and their reports remain for provenance. They are
not used by the Round 5 publication runner or by current CAA configurations.
Do not combine artifacts from different rounds without an explicit taxonomy and
review mapping.
