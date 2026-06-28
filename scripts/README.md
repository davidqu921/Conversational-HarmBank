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
python -m scripts.coding.code_conversations_round3_with_minimax --ids-from-round3 "data_prep/human_label_3/Round 3 - Jailbreak (new) - Arina.csv" --limit 10 --out-dir coding_results/minimax_round3
python -m scripts.coding.code_conversations_round4_with_minimax --transcripts data_prep/clean_transcript.jsonl --out-dir coding_results/minimax_round4_clean_transcript
python -m scripts.evaluation.evaluate_round3 --human-a "data_prep/human_label_3/VirtualSteve Coding - Round 3 - Jailbreak (new) - Arina.csv" --human-b "data_prep/human_label_3/VirtualSteve Coding - Round 3 - Jailbreak (new) - David.csv" --max-conversations 10 --out-dir human_irr/arina_vs_david_first10
```

Round 3 coding uses the simplified codebook with no subtype hierarchy. It writes
new outputs under `coding_results/minimax_round3/` by default and does not modify
the earlier coding results.

Round 4 coding uses primary/secondary attack-vector fields, single-label
attempt/conversational/severity fields, and no success field. To inspect prompts
before making API calls:

```bash
python -m scripts.coding.code_conversations_round4_with_minimax --transcripts data_prep/clean_transcript.jsonl --limit 2 --out-dir coding_results/minimax_round4_clean_transcript --dry-run
```

To code all 777 conversations in `data_prep/clean_transcript.jsonl`:

```bash
python -m scripts.coding.code_conversations_round4_with_minimax --transcripts data_prep/clean_transcript.jsonl --out-dir coding_results/minimax_round4_clean_transcript
```

If the full run is interrupted, resume without re-coding completed successful
rows:

```bash
python -m scripts.coding.code_conversations_round4_with_minimax --transcripts data_prep/clean_transcript.jsonl --out-dir coding_results/minimax_round4_clean_transcript --resume
```

The CAG builder writes:

- `raw_cab/cag/conversation_attack_graph.json`: canonical program-facing graph.
- `raw_cab/cag/cag_v1_edges.csv`: flat edge list for inspection and graph tooling.
- `raw_cab/cag/cag_v1.graphml`: visualization/network-analysis graph file.
- `raw_cab/cag/cag_v1.gexf`: Gephi-friendly visualization graph file.

The quick NetworkX viewer defaults to a phase-column layout to reduce overlap.
Use `--layout spring` for a force-directed view, `--min-count` to filter weak
edges, and `--success-only` to weight/filter edges by successful transitions.
