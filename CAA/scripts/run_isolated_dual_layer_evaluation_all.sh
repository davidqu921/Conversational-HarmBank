#!/usr/bin/env bash
# Run the fixed Llama -> Mistral isolated-pair evaluator for all four
# round5 balanced-100 response-model experiments, strictly sequentially.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  bash CAA/scripts/run_isolated_dual_layer_evaluation_all.sh [extra evaluator arguments]

Runs the Gemma, Llama, Mistral, and Qwen balanced-100 isolated evaluations in
that order. Every invocation uses the fixed Llama first layer, Mistral
supervisor, --double-layer, and --resume. The launcher stops if a task fails.

Examples:
  bash CAA/scripts/run_isolated_dual_layer_evaluation_all.sh
  bash CAA/scripts/run_isolated_dual_layer_evaluation_all.sh --rerun-supervisor

Environment variables:
  PYTHON_BIN       Python executable (default: python)
  CAA_MODEL_CACHE  Optional Hugging Face cache override
EOF
  exit 0
fi

PYTHON_BIN="${PYTHON_BIN:-python}"

TASK_NAMES=(
  "gemma3_12b"
  "llama31_8b"
  "mistral_7b"
  "qwen25_7b"
)

CONFIGS=(
  "CAA/configs/round5_balanced_100_gemma3_12b_stronger.yaml"
  "CAA/configs/round5_balanced_300_gemma3_12b_stronger.yaml"
  "CAA/configs/round5_balanced_100_llama31_8b_stronger.yaml"
  "CAA/configs/round5_balanced_300_llama31_8b_stronger.yaml"
  "CAA/configs/round5_balanced_100_mistral_7b_stronger.yaml"
  "CAA/configs/round5_balanced_300_mistral_7b_stronger.yaml"
  "CAA/configs/round5_balanced_100_qwen25_7b_stronger.yaml"
  "CAA/configs/round5_balanced_300_qwen25_7b_stronger.yaml"
)

for config in "${CONFIGS[@]}"; do
  if [[ ! -f "${config}" ]]; then
    echo "Missing config: ${config}" >&2
    exit 2
  fi
done

total="${#CONFIGS[@]}"
for index in "${!CONFIGS[@]}"; do
  task="${TASK_NAMES[$index]}"
  config="${CONFIGS[$index]}"
  task_number="$((index + 1))"

  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Starting ${task_number}/${total}: ${task}"
  "${PYTHON_BIN}" -u -m CAA.scripts.evaluate_isolated_repeated_attack \
    --config "${config}" \
    --model-id "meta-llama/Llama-3.1-8B-Instruct" \
    --supervisor-model-id "mistralai/Mistral-7B-Instruct-v0.3" \
    --double-layer \
    --resume \
    "$@"
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Completed ${task_number}/${total}: ${task}"
done

echo "All ${total} isolated dual-layer evaluations completed successfully."
