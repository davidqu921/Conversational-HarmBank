# Scripts

Run Python entry points as modules from the repository root. The canonical
publication workflow is documented in
[`../preprocessing/README.md`](../preprocessing/README.md).

## Active Round 5 packages

| Package | Purpose |
| --- | --- |
| `preprocessing/` | Configured post-review build, CAA contract validation, and provenance manifest. |
| `data_prep/` | Transcript preparation and human-review template tools. |
| `coding/` | Whole-conversation LLM coding. |
| `segmentation/` | Turn numbering and phase/action segmentation. |
| `fill_back_turn_actions/` | Successful-attack action fill-back and audit. |
| `new_cab/` | Round 5 CAB/statistics/CAG implementation used by the publication runner. |
| `evaluation/` | Agreement, discrepancy, and inter-rater reports. |

```bash
python -m scripts.preprocessing.run_publication_pipeline --validate-only
python -m scripts.preprocessing.run_publication_pipeline --build --dry-run
python -m scripts.preprocessing.run_publication_pipeline --build
```

## Historical implementations

`cab/` and `cag/` implement earlier artifact formats. Earlier label rounds,
result directories, and reports remain for provenance and are not consumed by
the configured Round 5 publication build or current CAA configs.
