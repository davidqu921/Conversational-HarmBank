# Linux ARM64 + NVIDIA setup

The production target is Ubuntu Linux on `aarch64`, using the existing Conda
environment in `environment-linux.yml`. Run commands from the repository root.

## 1. Create or update the environment

```bash
conda env create -f environment-linux.yml
conda activate caa
```

If the environment already exists, use `conda env update -n caa -f
environment-linux.yml --prune`. The YAML intentionally has no machine-specific
`prefix`.

## 2. Select the Hugging Face cache

The committed configs target:

```text
/home/david-qu/hf_cache/hub
```

and explicitly locate the attacker at:

```text
/home/david-qu/hf_cache/hub/models--meta-llama--Llama-3.1-8B-Instruct
```

`CAA_MODEL_CACHE` overrides the cache for another server without editing YAML:

```bash
export CAA_MODEL_CACHE=/home/david-qu/hf_cache/hub
```

Each configured response model must also exist in that cache. The runner is
offline-first and fails clearly if a model is absent. To use another local
checkout, add `local_path` beneath that model in the experiment YAML.

## 3. Preflight before loading weights

```bash
python -m CAA.scripts.check_runtime_env_linux \
  --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml
```

Then load tokenizer/model and generate a short sample for one model:

```bash
python -m CAA.scripts.check_hf_models \
  --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml \
  --model-id meta-llama/Llama-3.1-8B-Instruct --load-model --generate
```

## 4. Planning, smoke inference, and resume

```bash
python -m CAA.scripts.build_attempt_schedule --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml
python -m CAA.scripts.sample_strategy --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml
python -m CAA.scripts.run_caa_experiment --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml --dry-run --limit 1
python -m CAA.scripts.run_caa_experiment --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml --execute --limit 1
python -m CAA.scripts.run_caa_experiment --config CAA/configs/round5_balanced_40_llama32_3b_stronger.yaml --execute --resume
```

`execution_mode: dual_resident` loads both models at once. Confirm available
VRAM before the live smoke. If the server cannot hold both models, the runner
still needs a sequential/offloaded execution mode; do not start the full batch.
Live execution requires CUDA by default; set `conversation.require_cuda: false`
only for an intentional CPU-only diagnostic.
