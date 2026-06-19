# Scripts

Project scripts are grouped by task:

- `data_prep/`: raw transcript preparation and cleaning.
- `coding/`: whole-conversation jailbreak coding with LLMs.
- `segmentation/`: turn-level conversation segmentation and review helpers.
- `cab/`: Conversation Attack Bank construction and CAB statistics.
- `cag/`: Conversation Attack Graph construction for downstream CAA.
- `evaluation/`: human/LLM coding agreement and report comparison.

Run scripts from the repository root with `python -m`, for example:

```bash
python -m scripts.segmentation.segment_conversations_with_minimax --seg-success-attack
python -m scripts.cab.build_conversation_attack_bank
python -m scripts.cab.compute_cab_stats
python -m scripts.cag.build_conversation_attack_graph
python -m scripts.cag.visualize_cag_networkx --min-count 8 --out raw_cab/cag/cag_v1_networkx_phase.png --no-show
```

The CAG builder writes:

- `raw_cab/cag/conversation_attack_graph.json`: canonical program-facing graph.
- `raw_cab/cag/cag_v1_edges.csv`: flat edge list for inspection and graph tooling.
- `raw_cab/cag/cag_v1.graphml`: visualization/network-analysis graph file.
- `raw_cab/cag/cag_v1.gexf`: Gephi-friendly visualization graph file.

The quick NetworkX viewer defaults to a phase-column layout to reduce overlap.
Use `--layout spring` for a force-directed view, `--min-count` to filter weak
edges, and `--success-only` to weight/filter edges by successful transitions.
