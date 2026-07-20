#!/usr/bin/env bash
#
# Run the complete Windows CAA workflow from one experiment YAML.
#
# Intended shell: Git Bash on Windows.
# Run from anywhere:
#   bash CAA/scripts/run_full_pipeline.sh --config CAA/configs/my_experiment.yaml

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

CONFIG=""
LIMIT=""
SKIP_DOWNLOAD=0
DRY_RUN=0
SOURCE_REFERENCE=1
CURRENT_STAGE="initialization"
PIPELINE_START=$SECONDS

if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'
  C_BOLD=$'\033[1m'
  C_BLUE=$'\033[34m'
  C_GREEN=$'\033[32m'
  C_RED=$'\033[31m'
  C_YELLOW=$'\033[33m'
else
  C_RESET=""
  C_BOLD=""
  C_BLUE=""
  C_GREEN=""
  C_RED=""
  C_YELLOW=""
fi

usage() {
  cat <<'EOF'
Usage:
  bash CAA/scripts/run_full_pipeline.sh --config PATH [options]

Required:
  --config PATH          Experiment YAML file.

Options:
  --limit N              Run only the first N assigned attacks (smoke test).
  --skip-download        Do not download/refresh Hugging Face model snapshots.
  --dry-run              Build planning and render multi-turn/simple prompts;
                         do not run models or evaluations.
  --skip-source-reference
                         Skip the optional source-strategy reference summary.
  -h, --help             Show this help.

The default full run performs:
  model download/check -> attempt schedule -> strategy sampling
  -> multi-turn attack -> multi-turn severity evaluation
  -> source-reference summary -> simple one-turn attack
  -> simple-attack severity evaluation

Completed conversations and evaluations are resumed automatically.
EOF
}

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

format_seconds() {
  local total="$1"
  printf '%02d:%02d:%02d' "$((total / 3600))" "$(((total % 3600) / 60))" "$((total % 60))"
}

info() {
  printf '%s[%s] INFO%s  %s\n' "$C_BLUE" "$(timestamp)" "$C_RESET" "$*"
}

warn() {
  printf '%s[%s] WARN%s  %s\n' "$C_YELLOW" "$(timestamp)" "$C_RESET" "$*"
}

die() {
  printf '%s[%s] ERROR%s %s\n' "$C_RED" "$(timestamp)" "$C_RESET" "$*" >&2
  exit 1
}

run_stage() {
  local number="$1"
  local total="$2"
  local label="$3"
  shift 3

  CURRENT_STAGE="$label"
  local started=$SECONDS
  printf '\n%s%s[%s/%s] START%s %s\n' \
    "$C_BOLD" "$C_BLUE" "$number" "$total" "$C_RESET" "$label"
  printf 'Command:'
  printf ' %q' "$@"
  printf '\n'

  "$@"

  printf '%s%s[%s/%s] DONE%s  %s (%s)\n' \
    "$C_BOLD" "$C_GREEN" "$number" "$total" "$C_RESET" "$label" \
    "$(format_seconds "$((SECONDS - started))")"
}

on_error() {
  local exit_code=$?
  printf '\n%s%sPIPELINE FAILED%s during: %s\n' \
    "$C_BOLD" "$C_RED" "$C_RESET" "$CURRENT_STAGE" >&2
  printf 'Exit code: %s | elapsed: %s\n' \
    "$exit_code" "$(format_seconds "$((SECONDS - PIPELINE_START))")" >&2
  printf 'Fix the reported error, then rerun the same command; completed work uses --resume.\n' >&2
  exit "$exit_code"
}
trap on_error ERR

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      [[ $# -ge 2 ]] || die "--config requires a path"
      CONFIG="$2"
      shift 2
      ;;
    --limit)
      [[ $# -ge 2 ]] || die "--limit requires a positive integer"
      LIMIT="$2"
      [[ "$LIMIT" =~ ^[1-9][0-9]*$ ]] || die "--limit must be a positive integer"
      shift 2
      ;;
    --skip-download)
      SKIP_DOWNLOAD=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --skip-source-reference)
      SOURCE_REFERENCE=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1 (use --help)"
      ;;
  esac
done

[[ -n "$CONFIG" ]] || {
  usage
  die "--config is required"
}

cd "$REPO_ROOT"
command -v python >/dev/null 2>&1 || die "python is not available in PATH; activate the CAA Conda environment"
[[ -f "$CONFIG" ]] || die "config file not found: $CONFIG"

# Ask the project config loader for canonical values rather than duplicating
# YAML parsing in Bash. Each value is emitted on its own line for mapfile.
mapfile -t CONFIG_VALUES < <(
  python -c \
    'import sys; from CAA.scripts.caa_common import load_config; c=load_config(sys.argv[1]); print(c.experiment_id); print(c.output_dir); print(c.raw.get("evaluation", {}).get("default_reference", "round5_human"))' \
    "$CONFIG"
)
[[ ${#CONFIG_VALUES[@]} -eq 3 ]] || die "could not resolve experiment metadata from config"

# Windows Python may emit CRLF even when called from Git Bash.
EXPERIMENT_ID="${CONFIG_VALUES[0]%$'\r'}"
OUTPUT_DIR="${CONFIG_VALUES[1]%$'\r'}"
REFERENCE="${CONFIG_VALUES[2]%$'\r'}"
WEAK_TRANSCRIPTS="${OUTPUT_DIR}/weak_attack_convos/transcripts.jsonl"
WEAK_EVALUATION="${OUTPUT_DIR}/weak_attack_evaluation/severity_llama31"

LIMIT_ARGS=()
if [[ -n "$LIMIT" ]]; then
  LIMIT_ARGS=(--limit "$LIMIT")
fi

printf '%s%sCAA FULL PIPELINE%s\n' "$C_BOLD" "$C_BLUE" "$C_RESET"
info "Windows Git Bash workflow"
info "Repository: ${REPO_ROOT}"
info "Config: ${CONFIG}"
info "Experiment: ${EXPERIMENT_ID}"
info "Output: ${OUTPUT_DIR}"
[[ -n "$LIMIT" ]] && warn "Smoke-test limit enabled: ${LIMIT}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  TOTAL_STAGES=4
  run_stage 1 "$TOTAL_STAGES" "Check Hugging Face model cache" \
    python -u -m CAA.scripts.check_hf_models --config "$CONFIG"
  run_stage 2 "$TOTAL_STAGES" "Build attempt schedule" \
    python -u -m CAA.scripts.build_attempt_schedule --config "$CONFIG"
  run_stage 3 "$TOTAL_STAGES" "Sample strategy assignments" \
    python -u -m CAA.scripts.sample_strategy --config "$CONFIG"
  run_stage 4 "$TOTAL_STAGES" "Render multi-turn dry run" \
    python -u -m CAA.scripts.run_caa_experiment --config "$CONFIG" --dry-run "${LIMIT_ARGS[@]}"

  warn "Simple-attack dry-run selection follows the frozen assignments:"
  python -u -m CAA.scripts.run_weak_attack_experiment \
    --config "$CONFIG" --dry-run "${LIMIT_ARGS[@]}"
else
  TOTAL_STAGES=9
  STAGE=1

  if [[ "$SKIP_DOWNLOAD" -eq 0 ]]; then
    run_stage "$STAGE" "$TOTAL_STAGES" "Download/refresh Hugging Face models" \
      python -u -m CAA.scripts.download_hf_models --config "$CONFIG"
  else
    warn "Skipping model download by request"
  fi
  STAGE=$((STAGE + 1))

  run_stage "$STAGE" "$TOTAL_STAGES" "Check Hugging Face model cache" \
    python -u -m CAA.scripts.check_hf_models --config "$CONFIG"
  STAGE=$((STAGE + 1))

  run_stage "$STAGE" "$TOTAL_STAGES" "Build attempt schedule" \
    python -u -m CAA.scripts.build_attempt_schedule --config "$CONFIG"
  STAGE=$((STAGE + 1))

  run_stage "$STAGE" "$TOTAL_STAGES" "Sample strategy assignments" \
    python -u -m CAA.scripts.sample_strategy --config "$CONFIG"
  STAGE=$((STAGE + 1))

  run_stage "$STAGE" "$TOTAL_STAGES" "Run multi-turn CAA attacks" \
    python -u -m CAA.scripts.run_caa_experiment \
      --config "$CONFIG" --execute --resume "${LIMIT_ARGS[@]}"
  STAGE=$((STAGE + 1))

  run_stage "$STAGE" "$TOTAL_STAGES" "Evaluate multi-turn attack severity" \
    python -u -m CAA.scripts.code_caa_severity_with_hf \
      --config "$CONFIG" --resume "${LIMIT_ARGS[@]}"
  STAGE=$((STAGE + 1))

  if [[ "$SOURCE_REFERENCE" -eq 1 ]]; then
    run_stage "$STAGE" "$TOTAL_STAGES" "Summarize source-strategy reference" \
      python -u -m CAA.scripts.evaluate_caa_outputs \
        --config "$CONFIG" --reference "$REFERENCE"
  else
    warn "Skipping source-strategy reference summary by request"
  fi
  STAGE=$((STAGE + 1))

  run_stage "$STAGE" "$TOTAL_STAGES" "Run simple one-turn attacks" \
    python -u -m CAA.scripts.run_weak_attack_experiment \
      --config "$CONFIG" --execute --resume "${LIMIT_ARGS[@]}"
  STAGE=$((STAGE + 1))

  run_stage "$STAGE" "$TOTAL_STAGES" "Evaluate simple-attack severity" \
    python -u -m CAA.scripts.code_caa_severity_with_hf \
      --config "$CONFIG" \
      --transcripts "$WEAK_TRANSCRIPTS" \
      --out-dir "$WEAK_EVALUATION" \
      --resume "${LIMIT_ARGS[@]}"
fi

printf '\n%s%sPIPELINE COMPLETE%s\n' "$C_BOLD" "$C_GREEN" "$C_RESET"
info "Experiment: ${EXPERIMENT_ID}"
info "Outputs: ${OUTPUT_DIR}"
info "Total elapsed: $(format_seconds "$((SECONDS - PIPELINE_START))")"
info "LLM evaluations are provisional; complete human calibration before publication."
