#!/usr/bin/env bash
# Sequential launcher; no attack generation. Use --dry-run before a live run.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/../.."
if [[ $# -lt 1 || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: bash CAA/scripts/run_unified_severity.sh CONFIG [trajectory|context-independent|isolated|weak|all] [evaluator arguments]
Default condition: context-independent. Default interpreter: python.
Examples:
  bash CAA/scripts/run_unified_severity.sh CAA/configs/round5_balanced_300_mistral_7b_stronger.yaml all --dry-run --limit 2
  bash CAA/scripts/run_unified_severity.sh CAA/configs/round5_balanced_300_mistral_7b_stronger.yaml context-independent
For repeated JSON/evidence failures, add --repair-failed to retry pending units
with focused source checks and a larger recovery output budget.
Every task uses --resume and the new versioned output directory. --limit counts
conversations for ordinary conditions and parents for isolated. The launcher
stops on failures/pending results; inspect review_queue.csv before resuming.
Do not pass a shared --out-dir with 'all'. Set PYTHON_BIN to select Python.
EOF
  exit 0
fi
config="$1"
shift
condition="context-independent"
if [[ $# -gt 0 && "$1" != --* ]]; then condition="$1"; shift; fi
PYTHON_BIN="${PYTHON_BIN:-python}"
if [[ "$condition" == all ]]; then
  for arg in "$@"; do
    if [[ "$arg" == --out-dir || "$arg" == --out-dir=* || "$arg" == --transcripts || "$arg" == --transcripts=* || "$arg" == --parent-index || "$arg" == --parent-index=* || "$arg" == --reference-codings || "$arg" == --reference-codings=* ]]; then
      echo "Use condition-specific inputs, output or references outside 'all'." >&2
      exit 2
    fi
  done
  conditions=(trajectory context-independent weak isolated)
else
  conditions=("$condition")
fi
experiment_dir="$("$PYTHON_BIN" -c 'import sys; from pathlib import Path; from CAA.scripts.caa_common import load_config; print(load_config(Path(sys.argv[1])).output_dir)' "$config")"
for current in "${conditions[@]}"; do
  case "$current" in
    trajectory) input="$experiment_dir/transcripts.jsonl" ;;
    context-independent) input="$experiment_dir/context_independent_trajectory_seeded_repeated_weak_attack_convos/transcripts.jsonl" ;;
    weak) input="$experiment_dir/weak_attack_convos/transcripts.jsonl" ;;
    isolated)
      "$PYTHON_BIN" -u -m CAA.scripts.evaluate_isolated_repeated_attack --config "$config" --double-layer --resume "$@"
      continue ;;
    *) echo "Unknown condition: $current" >&2; exit 2 ;;
  esac
  "$PYTHON_BIN" -u -m CAA.scripts.code_caa_severity_with_hf --config "$config" --transcripts "$input" --double-layer --resume "$@"
done
