#!/usr/bin/env bash
# Run V2 or V3 dual-layer evaluators with condition-specific paths.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/../../.."
if [[ $# -lt 1 || "${1:-}" == --help || "${1:-}" == -h ]]; then
  cat <<'HELP'
Usage: bash CAA/scripts/batch/run_severity.sh CONFIG [trajectory|context-independent|weak|isolated|all] [evaluator arguments]
Default condition: context-independent. Every task uses --double-layer --resume.
Default: preserved V2. Pass --evaluator-version v3 for restored Round 4 in both layers.
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
    --config|--config=*|--transcripts|--transcripts=*|--parent-index|--parent-index=*|--condition|--condition=*|--no-double-layer)
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
for current in "${conditions[@]}"; do
  if [[ "$current" == isolated ]]; then
    "$PYTHON_BIN" -u -m CAA.scripts.evaluate_isolated_repeated_attack \
      --config "$config" --double-layer --resume "$@"
  else
    "$PYTHON_BIN" -u -m CAA.scripts.code_caa_severity_with_hf \
      --config "$config" --condition "$current" --double-layer --resume "$@"
  fi
done
