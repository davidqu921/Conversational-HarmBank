#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv-caa
source .venv-caa/bin/activate
python -m pip install --upgrade pip
pip install -r CAA/requirements-vllm.txt

python -m CAA.scripts.download_hf_models \
  --config CAA/configs/round5_balanced_40.yaml

