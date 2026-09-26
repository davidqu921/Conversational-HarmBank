#!/usr/bin/env bash
# Run the human-aligned v2 dual-layer evaluators with condition-specific paths.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/../../.."
if [[ $# -lt 1 || "${1:-}" == --help || "${1:-}" == -h ]]; then
  cat <<'HELP'
Usage: bash CAA/scripts/batch/run_severity.sh CONFIG [trajectory|context-independent|weak|isolated|all] [evaluator arguments]
Default condition: context-independent. Every task uses --double-layer --resume.
Ordinary conditions use human-aligned-v2; isolated uses output-only-v2.
Examples:
  bash CAA/scripts/batch/run_severity.sh CAA/configs/round5_balanced_100_gemma3_12b_stronger.yaml isolated
  bash CAA/scripts/batch/run_severity.sh CAA/configs/round5_balanced_100_gemma3_12b_stronger.yaml all --dry-run --limit 1
Set PYTHON_BIN to select Python. Additional flags are forwarded to the evaluator.
For single-layer evaluation or custom inputs, use the Python entry points.
For 'all', condition-specific output/reference overrides are not accepted.
Execution errors return nonzero. Inspect summary.json for neutral outcomes and coverage.
HELP
  exit 0
fi
config="$1"
shift
condition="context-independent"
if [[ $# -gt 0 && "$1" != --* ]]; then condition="$1"; shift; fi
case "$condition" in
  trajectory|context-independent|weak|isolated) conditions=("$condition") ;;
  all) conditions=(trajectory context-independent weak isolated) ;;
  *) echo "Unknown condition: $condition" >&2; exit 2 ;;
esac
for arg in "$@"; do
  case "$arg" in
    --config|--config=*|--transcripts|--transcripts=*|--parent-index|--parent-index=*|--no-double-layer)
      echo "This launcher owns condition selection and uses double-layer evaluation; use the Python entry point for $arg." >&2
      exit 2 ;;
  esac
  if [[ "$condition" == all ]]; then
    case "$arg" in
      --out-dir|--out-dir=*|--reference-codings|--reference-codings=*|--reference-pair-codings|--reference-pair-codings=*)
        echo "Use condition-specific output/reference overrides outside 'all'." >&2
        exit 2 ;;
    esac
  fi
done
PYTHON_BIN="${PYTHON_BIN:-python}"
experiment_dir="$("$PYTHON_BIN" -c 'import sys; from pathlib import Path; from CAA.scripts.caa_common import load_config; print(load_config(Path(sys.argv[1])).output_dir)' "$config")"
for current in "${conditions[@]}"; do
  case "$current" in
    trajectory) input="$experiment_dir/transcripts.jsonl"; evaluation="$experiment_dir/evaluation" ;;
    context-independent)
      input="$experiment_dir/context_independent_trajectory_seeded_repeated_weak_attack_convos/transcripts.jsonl"
      evaluation="$experiment_dir/context_independent_trajectory_seeded_repeated_weak_attack_evaluation" ;;
    weak) input="$experiment_dir/weak_attack_convos/transcripts.jsonl"; evaluation="$experiment_dir/weak_attack_evaluation" ;;
    isolated)
      "$PYTHON_BIN" -u -m CAA.scripts.evaluate_isolated_repeated_attack --config "$config" --double-layer --resume "$@"
      continue ;;
  esac
  "$PYTHON_BIN" -u -m CAA.scripts.code_caa_severity_with_hf \
    --config "$config" --transcripts "$input" \
    --out-dir "$evaluation/dual-layer_human-aligned-v2_llama31_and_mistral" \
    --double-layer --resume "$@"
done
