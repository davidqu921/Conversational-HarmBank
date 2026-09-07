#!/usr/bin/env bash
# Sequentially run the isolated repeated attack for all 4 models x 2 run sizes.
#
# Run this script inside the CUDA-enabled `caa` environment. Every task uses
# --resume, writes a separate log, and is retried after an unexpected failure.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  bash CAA/scripts/run_isolated_repeated_all.sh [runner arguments]

Runs all eight 100/300 x Gemma/Llama/Mistral/Qwen isolated repeated attacks in
sequence. Additional arguments are forwarded to every runner invocation; for
example, `--rounds 6` or `--limit 1`.

Environment variables:
  PYTHON_BIN                  Python executable (default: python)
  CAA_MODEL_CACHE             Hugging Face cache
                              (default: /home/david-qu/hf_cache/hub)
  MAX_RETRIES                 Retries after the first attempt (default: 1)
  INTER_TASK_DELAY_SECONDS    Delay after each task (default: 10)
  BATCH_LOG_ROOT              Parent log directory
                              (default: CAA/outputs/isolated_repeated_batch_logs)

Recommended background launch after `conda activate caa`:
  nohup bash CAA/scripts/run_isolated_repeated_all.sh \
    > isolated_repeated_launcher.log 2>&1 &

Monitor:
  tail -f isolated_repeated_launcher.log
EOF
  exit 0
fi

PYTHON_BIN="${PYTHON_BIN:-python}"
CAA_MODEL_CACHE="${CAA_MODEL_CACHE:-/home/david-qu/hf_cache/hub}"
MAX_RETRIES="${MAX_RETRIES:-1}"
INTER_TASK_DELAY_SECONDS="${INTER_TASK_DELAY_SECONDS:-10}"
BATCH_LOG_ROOT="${BATCH_LOG_ROOT:-CAA/outputs/isolated_repeated_batch_logs}"

if ! [[ "${MAX_RETRIES}" =~ ^[0-9]+$ ]]; then
  echo "MAX_RETRIES must be a non-negative integer: ${MAX_RETRIES}" >&2
  exit 2
fi
if ! [[ "${INTER_TASK_DELAY_SECONDS}" =~ ^[0-9]+$ ]]; then
  echo "INTER_TASK_DELAY_SECONDS must be a non-negative integer: ${INTER_TASK_DELAY_SECONDS}" >&2
  exit 2
fi

mkdir -p "${BATCH_LOG_ROOT}"
if command -v flock >/dev/null 2>&1; then
  exec 9>"${BATCH_LOG_ROOT}/.isolated_repeated_batch.lock"
  if ! flock -n 9; then
    echo "Another isolated repeated batch appears to be running." >&2
    exit 3
  fi
else
  echo "Warning: flock is unavailable; duplicate-launch protection is disabled." >&2
fi

RUN_STAMP="$(date -u +'%Y%m%dT%H%M%SZ')"
RUN_LOG_DIR="${BATCH_LOG_ROOT}/${RUN_STAMP}"
STATUS_FILE="${RUN_LOG_DIR}/status.tsv"
mkdir -p "${RUN_LOG_DIR}"
printf 'task\tconfig\tstatus\tattempts\texit_code\tstarted_utc\tfinished_utc\tlog\n' > "${STATUS_FILE}"

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
    exit 4
  fi
done

export CAA_MODEL_CACHE
export PYTHONUNBUFFERED=1

echo "Repository: ${REPO_ROOT}"
echo "Python: ${PYTHON_BIN}"
echo "Model cache: ${CAA_MODEL_CACHE}"
echo "Batch logs: ${RUN_LOG_DIR}"
echo "Tasks: ${#CONFIGS[@]} (strictly sequential)"

"${PYTHON_BIN}" -c '
import platform
import torch
print(f"Architecture: {platform.machine()}")
print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable")
print(f"GPU: {torch.cuda.get_device_name(0)}")
'

failures=()
total="${#CONFIGS[@]}"

for index in "${!CONFIGS[@]}"; do
  task="${TASK_NAMES[$index]}"
  config="${CONFIGS[$index]}"
  task_number="$((index + 1))"
  task_log="${RUN_LOG_DIR}/${task}.log"
  started_utc="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  max_attempts="$((MAX_RETRIES + 1))"
  attempt=0
  exit_code=1

  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Starting ${task_number}/${total}: ${task}"
  echo "Config: ${config}"

  while (( attempt < max_attempts )); do
    attempt="$((attempt + 1))"
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] ${task} attempt ${attempt}/${max_attempts}" \
      | tee -a "${task_log}"

    command=(
      "${PYTHON_BIN}"
      -m CAA.scripts.run_isolated_repeated_attack_experiment
      --config "${config}"
      --execute
      --resume
      --model-cache "${CAA_MODEL_CACHE}"
      "$@"
    )

    if "${command[@]}" 2>&1 | tee -a "${task_log}"; then
      exit_code=0
      break
    else
      exit_code="${PIPESTATUS[0]}"
      echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] ${task} failed with exit ${exit_code}" \
        | tee -a "${task_log}"
      if (( attempt < max_attempts )); then
        echo "Retrying ${task} with --resume after ${INTER_TASK_DELAY_SECONDS}s" \
          | tee -a "${task_log}"
        sleep "${INTER_TASK_DELAY_SECONDS}"
      fi
    fi
  done

  finished_utc="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  if (( exit_code == 0 )); then
    status="completed"
    echo "[${finished_utc}] Completed ${task_number}/${total}: ${task}"
  else
    status="failed"
    failures+=("${task}")
    echo "[${finished_utc}] FAILED ${task_number}/${total}: ${task}; continuing." >&2
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${task}" "${config}" "${status}" "${attempt}" "${exit_code}" \
    "${started_utc}" "${finished_utc}" "${task_log}" >> "${STATUS_FILE}"

  if (( task_number < total && INTER_TASK_DELAY_SECONDS > 0 )); then
    sleep "${INTER_TASK_DELAY_SECONDS}"
  fi
done

echo "Batch status: ${STATUS_FILE}"
if (( ${#failures[@]} > 0 )); then
  echo "Batch finished with ${#failures[@]} failed task(s): ${failures[*]}" >&2
  exit 1
fi

echo "<==All ${total} isolated repeated attack tasks completed successfully.==>"
