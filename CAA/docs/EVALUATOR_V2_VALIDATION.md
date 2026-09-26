# Evaluator v2 implementation and validation — 2026-09-20

The ordinary conversation and isolated output evaluators have been replaced in
place with the approved integer/null contract. Positive and neutral first-layer
judgments enter an independent supervisor; valid supervisor null is final.
Runtime/parser failures are distinct from neutral and never fall back to a
confirmed first-layer positive. Historical experiment outputs and human labels
were not rewritten.

## Implemented and checked

- Exact two-field validation; duplicate/extra/missing keys, invalid types,
  ambiguous multiple objects, empty/overlong reasoning and incomplete JSON fail.
- One corrective format retry per stage invocation; native greedy decoding,
  bounded budget increase and context-length preflight. No LLM JSON repair.
- Transcript-only supervision without candidate label/rationale, with consistent
  first-layer and supervisor rubric wording. Structured speaker preparation
  prevents quoted speaker names from becoming turn metadata.
- Separate semantic and execution states in JSONL/CSV; neutral/error-aware ASR,
  coverage and full-set bounds; parent success preserved when a confirmed
  positive coexists with unresolved child pairs, without inventing exact severity.
- Append-only attempt journals, unique raw diagnostics, atomic derived files,
  conservative interrupted-tail recovery, and input/prompt/schema/model/runtime
  checks on resume. Supervisor reruns archive old results.
- Current human-reference comparison with numeric-prefix CSV normalization,
  neutral/error counts and operational recall. Legacy binary report/review
  commands reject the new schema rather than silently coercing it.
- Updated launchers use new v2 output directories. Active old evaluator code
  and prompts are replaced; historical outputs remain available for comparison.

`python3 -m unittest discover -s CAA/tests -v` passed **47 tests** after the
implementation. This includes an exhaustive 36-combination parent aggregation
fixture and both real command entry-point control flows with simulated model
responses, supervision failure, resume and completed-neutral skipping.
Syntax compilation, shell syntax and whitespace checks also passed. Both actual
CLI dry runs passed in the installed environment: the two ordinary regression
conversations and all seven pairs of one isolated parent, including both layers’
rendered prompts.

All **5,223 historical source files** in the existing audit hash inventory were
rechecked: no missing files and no changed hashes. This covers the audited
human references and historical prediction sources. New validation artifacts
are confined to a separate directory.

## Installed-runtime compatibility

The local environment reports PyTorch `2.13.0+cu130`, Transformers `5.13.0`,
CUDA 13.0 and NVIDIA GB10. Both configured local model snapshots were found.
The installed environment has no `lmformatenforcer`; grammar-constrained
inference was therefore not enabled or claimed. Strict validation plus the
bounded corrective retry is the active format fallback.

Both real tokenizers/chat templates successfully encoded **28 combinations**
(14 selected inputs × the appropriate first-layer/supervisor model). The longest
input was **4,756 tokens**. All fitted their model context with the maximum
512-token retry budget used by this pilot. This verifies tokenizer/template
compatibility, not model-generation correctness.

## Real generation pilot: interrupted by resource pressure

A fixed 14-case smoke/calibration set was prepared:

| Cases | Count | Purpose |
| --- | ---: | --- |
| Previously observed isolated false positives | 6 | Harmless substitute/phrase, category label, anatomy, masked profanity, contextual slur mention |
| Human-positive isolated pairs | 4 | Contrastive checks, one from each response model |
| Human-Safe isolated controls | 2 | Check preservation of benign judgments |
| Known ordinary supervisor false negatives | 2 | Mistral trajectory `caa_0061` and `caa_0062` |

Llama weights loaded, but the runtime reported CPU/disk offloading. At inspection,
shared system memory was approximately **111/121 GiB used**, with nearly all
**15 GiB swap used**. The first judgment had not completed. Only the pilot
process started for this task was terminated; other workloads were left running.
The first-stage journal is empty and **no accepted real-model judgment exists**.
The absence of results is not a measured JSON failure or semantic neutral.

Accordingly, this change has **no measured FP reduction, positive recall or
accuracy improvement yet**. In particular, no claim is made that the 55 false
positives are fixed or that all 89 isolated positives / 57 positive parents are
preserved. Prompt changes encode cautious boundaries; their effect remains to
be measured against the unchanged human references.

Pilot inputs, exact human-reference copies, case selection, model/prompt
provenance, runtime log and tokenizer results are in
[`outputs/evaluator_v2_validation/20260920_pilot/`](../outputs/evaluator_v2_validation/20260920_pilot/).
IDs are namespaced by response model **only inside this mixed-model pilot** to
avoid collisions; original IDs and paths are recorded in `selection.json`.
Production evaluators preserve source IDs unchanged.

When enough memory is available, from the repository root:

```bash
conda activate caa
PYTHONPATH=. python CAA/outputs/evaluator_v2_validation/20260920_pilot/run_pilot.py
```

The pilot reuses the active evaluator functions and verifies its saved manifest
before resuming. It is not an old evaluator implementation. Use `--out-dir` for
a fresh pilot if input, prompt or model fingerprints change. The selected cases
are calibration examples already examined, not a held-out test set.

## Remaining validation

1. Complete this small real-generation pilot when resources allow; inspect any
   false-negative or ungraded human-positive results before scaling.
2. Run the revised evaluators against the existing 100-parent/model human
   references, reporting true FP-to-Safe corrections separately from neutral
   abstentions and execution failures, at pair and parent levels.
3. Confirm any accuracy improvement on new or separately reviewed examples.

The current usage and export conventions are documented in
[EVALUATION.md](EVALUATION.md). The approved rationale remains in
[EVALUATOR_IMPROVEMENT_PLAN.md](EVALUATOR_IMPROVEMENT_PLAN.md).
