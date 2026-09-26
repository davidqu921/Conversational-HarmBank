from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path
from typing import Any

import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer

from CAA.scripts.caa_common import model_cache_path, resolve_project_path
from CAA.scripts.model_runtime import load_local_model, resolve_model_source, runtime_summary


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_manifest(cache_dir: Path) -> dict[str, str]:
    manifest_path = cache_dir / "caa_model_manifest.json"
    out = scan_model_cache(cache_dir)
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        out.update({item["model_id"]: item["local_path"] for item in data.get("models", [])})
    return out


def scan_model_cache(cache_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not cache_dir.exists():
        return out
    for model_dir in cache_dir.glob("models--*--*"):
        snapshots = model_dir / "snapshots"
        if not snapshots.exists():
            continue
        snapshot_dirs = sorted(
            [path for path in snapshots.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not snapshot_dirs:
            continue
        parts = model_dir.name.split("--", 2)
        if len(parts) == 3:
            out[f"{parts[1]}/{parts[2]}"] = str(snapshot_dirs[0])
    return out


def free_memory() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def first_real_device(model) -> torch.device:
    for parameter in model.parameters():
        if not getattr(parameter, "is_meta", False):
            return parameter.device
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def move_inputs(inputs: Any, device: torch.device) -> Any:
    if hasattr(inputs, "to"):
        return inputs.to(device)
    if isinstance(inputs, dict):
        return {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}
    return inputs


def check_one(
    model_id: str,
    local_path: str | None,
    model_cfg: dict[str, Any],
    load_model: bool,
    generate: bool,
    max_new_tokens: int,
) -> dict[str, Any]:
    cfg = dict(model_cfg)
    cfg["model_id"] = model_id
    if local_path:
        cfg["local_path"] = local_path
    source = local_path or model_id
    result: dict[str, Any] = {
        "model_id": model_id,
        "source": source,
        "tokenizer_ok": False,
        "model_ok": False,
        "generate_ok": False,
        "error": None,
    }
    try:
        source, is_local = resolve_model_source(cfg, Path(cfg.pop("_cache_path")))
        result["source"] = source
        tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=is_local, trust_remote_code=True)
        result["tokenizer_ok"] = True
        result["vocab_size"] = len(tokenizer)
        if not load_model:
            return result

        start = time.time()
        tokenizer, model, source = load_local_model(cfg, Path(model_cfg["_cache_path"]))
        result["source"] = source
        result["model_ok"] = True
        result["load_s"] = round(time.time() - start, 2)
        result["device_map"] = getattr(model, "hf_device_map", None)
        if torch.cuda.is_available():
            result["cuda_allocated_gb"] = round(torch.cuda.memory_allocated() / 1024**3, 3)
            result["cuda_reserved_gb"] = round(torch.cuda.memory_reserved() / 1024**3, 3)

        if generate:
            prompt = "You are a psychology professor. Briefly introduce classical conditioning in one sentence."
            messages = [{"role": "user", "content": prompt}]
            input_device = first_real_device(model)
            if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
                try:
                    inputs = tokenizer.apply_chat_template(
                        messages,
                        add_generation_prompt=True,
                        tokenize=True,
                        return_tensors="pt",
                        return_dict=True,
                    )
                except TypeError:
                    encoded = tokenizer.apply_chat_template(
                        messages,
                        add_generation_prompt=True,
                        tokenize=True,
                        return_tensors="pt",
                    )
                    inputs = {"input_ids": encoded}
            else:
                inputs = tokenizer(prompt, return_tensors="pt")
            inputs = move_inputs(inputs, input_device)
            with torch.inference_mode():
                output = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            decoded = tokenizer.decode(output[0], skip_special_tokens=True)
            result["generate_ok"] = True
            result["sample_output"] = decoded[-500:]

        del model
        del tokenizer
        free_memory()
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        free_memory()
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Check locally downloaded CAA Hugging Face models.")
    parser.add_argument("--config", type=Path, default=Path("CAA/configs/round5_balanced_40.yaml"))
    parser.add_argument("--model-id", help="Check only one model id from the config/manifest.")
    parser.add_argument("--load-model", action="store_true", help="Actually load each model one at a time.")
    parser.add_argument("--generate", action="store_true", help="Run a tiny generation smoke test after loading.")
    parser.add_argument("--max-new-tokens", type=int, default=24)
    args = parser.parse_args()

    config = load_yaml(resolve_project_path(args.config))
    cache_dir = model_cache_path(config)
    manifest = load_manifest(cache_dir)
    models = [
        config["attacker_model"]["model_id"],
        config["response_model"]["model_id"],
    ]
    if args.model_id:
        models = [args.model_id]

    print(json.dumps(runtime_summary(), ensure_ascii=False))
    results = []
    for model_id in models:
        print(f"Checking {model_id}")
        result = check_one(
            model_id=model_id,
            local_path=manifest.get(model_id),
            model_cfg={
                **next((config[key] for key in ("attacker_model", "response_model") if config[key]["model_id"] == model_id), {}),
                "_cache_path": str(cache_dir),
            },
            load_model=args.load_model,
            generate=args.generate,
            max_new_tokens=args.max_new_tokens,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        results.append(result)
    if not all(row["tokenizer_ok"] and (row["model_ok"] or not args.load_model) for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
