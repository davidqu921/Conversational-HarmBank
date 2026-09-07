#!/usr/bin/env bash
# Run the isolated-output-only v1 dual-layer evaluator for all four round5
# response models at both balanced-100 and balanced-300, strictly sequentially.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  bash CAA/scripts/run_isolated_output_only_all.sh [extra evaluator arguments]

Runs balanced-100 and balanced-300 isolated evaluations for Gemma, Llama,
Mistral, and Qwen. For each response model, the 100 configuration runs before
the 300 configuration. Each task uses the isolated-output-only v1 prompts,
Llama layer 1, Mistral layer 2, --double-layer, and --resume. The launcher stops
if a Python process exits unsuccessfully; re-running the same command resumes
completed pair codings.

Environment variables:
  PYTHON_BIN       Python executable (default: python)
  CAA_MODEL_CACHE  Optional Hugging Face cache override
EOF
  exit 0
fi

PYTHON_BIN="${PYTHON_BIN:-python}"

TASK_NAMES=(
  "gemma3_12b_100"
  "gemma3_12b_300"
  "llama31_8b_100"
  "llama31_8b_300"
  "mistral_7b_100"
  "mistral_7b_300"
  "qwen25_7b_100"
  "qwen25_7b_300"
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

echo "All ${total} isolated-output-only evaluations completed successfully."
