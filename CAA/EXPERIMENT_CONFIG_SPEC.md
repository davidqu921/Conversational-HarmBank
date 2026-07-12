# Experiment Configuration Spec

## Model Selection

The first implementation should support local Hugging Face models. Keep
attacker and response model adapters symmetric so either side can later be
replaced by an OpenAI-compatible endpoint or vLLM server.

Recommended config fields:

```yaml
attacker_model:
  provider: huggingface
  backend: transformers
  model_id: meta-llama/Llama-3.1-8B-Instruct
  device_map: auto
  torch_dtype: auto
  max_new_tokens: 512
  temperature: 0.8
  top_p: 0.9
  repetition_penalty: 1.05

response_model:
  provider: huggingface
  backend: transformers
  model_id: google/gemma-2-9b
  device_map: auto
  torch_dtype: auto
  max_new_tokens: 512
  temperature: 0.7
  top_p: 0.9
  system_prompt: CAA/prompts/response_system_psych_professor.md
```

The first target machine has an RTX 5090 with about 32GB VRAM available. That is
enough for initial 8B/9B experimentation, especially with bf16/fp16 and careful
context sizes. Running both models at the same time may still require vLLM
serving, quantization, or sequential load/unload depending on actual memory
pressure.

## Backend Preference

Prefer vLLM for the production experiment because it is better suited for
serving and repeated generation. However, official vLLM GPU support is Linux
first and does not support native Windows. On this Windows machine, use one of
these paths:

1. Recommended: install WSL2 Ubuntu and run vLLM inside Linux.
2. Fallback: use native Windows Transformers for smoke tests and possibly for
   sequential single-model generation.

## Sampling Parameters

```yaml
sampling:
  attempt_allocation: cab_proportional
  min_per_attempt: 2
  strategy_scope: success_attack
  prefer_attempt_exact_match: true
  prefer_nonzero_severity: true
  top_k_trajectories: 20
  trajectory_temperature: 0.7
  diversity_window: 8
  allow_cag_walk_fallback: true
  randomize_action_count: false
  min_sampled_action_count: 4
  short_path_extension_threshold: 2
  short_path_extension_min_turns: 6
```

Formal experiments should usually keep `randomize_action_count: false`: once a
CAB strategy path is sampled, the CAA follows that path as-is up to
`max_attacker_turns`. Randomness should come from which CAB path is sampled, not
from truncating the sampled path. Very short paths, defined by
`short_path_extension_threshold`, are extended to
`short_path_extension_min_turns` using same-action repetition and
attempt-appropriate Goal Execution pressure actions.

## Stopping Parameters

```yaml
conversation:
  max_attacker_turns: 15
  stop_when_strategy_exhausted: true
  allow_adaptive_turns_after_path: false
  max_retries_per_turn: 2
  response_system_prompt: CAA/prompts/response_system_psych_professor.md
```

## Output Paths

```yaml
paths:
  turn_action_bank: raw_cab_round5_reviewed_all/turn_action_conversation_bank.jsonl
  phrase_bank: raw_cab_round5_reviewed_all/phrase_conversation_bank.jsonl
  action_cag: raw_cab_round5_reviewed_all/cag/turn_action_conversation_attack_graph.json
  phase_cag: raw_cab_round5_reviewed_all/cag/phase_conversation_attack_graph.json
  round5_human_codings: data_prep/human_label_5/resolved_coding_results/round5_reviewed_completed_codings.csv
  historical_codings: coding_results/minimax_round4_v2/codings.jsonl
  output_root: CAA/outputs
  model_cache: D:/Summer_Project_2026/hf_cache
```

## Evaluation Parameters

```yaml
evaluation:
  enabled: true
  mode: source_reference
  default_reference: round5_human
  round5_human_codings: data_prep/human_label_5/resolved_coding_results/round5_reviewed_completed_codings.csv
  success_severities:
    - "1 - Minor"
    - "2 - Major"
    - "3 - Severe"
```
