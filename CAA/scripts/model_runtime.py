from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def _model_id_from_cache_dir(path: Path) -> str | None:
    if not path.name.startswith("models--"):
        return None
    parts = path.name.split("--", 2)
    return f"{parts[1]}/{parts[2]}" if len(parts) == 3 else None


def _latest_snapshot(model_dir: Path) -> Path | None:
    snapshots = model_dir / "snapshots"
    if not snapshots.is_dir():
        return model_dir if (model_dir / "config.json").is_file() else None
    candidates = [p for p in snapshots.iterdir() if p.is_dir()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def scan_model_cache(cache_path: Path) -> dict[str, str]:
    """Scan an HF cache root, its hub directory, or one models--org--name dir."""
    cache_path = cache_path.expanduser()
    roots = [cache_path]
    if (cache_path / "hub").is_dir():
        roots.insert(0, cache_path / "hub")
    direct_id = _model_id_from_cache_dir(cache_path)
    if direct_id:
        snapshot = _latest_snapshot(cache_path)
        return {direct_id: str(snapshot)} if snapshot else {}
    out: dict[str, str] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for model_dir in root.glob("models--*--*"):
            model_id = _model_id_from_cache_dir(model_dir)
            snapshot = _latest_snapshot(model_dir)
            if model_id and snapshot:
                out[model_id] = str(snapshot)
    return out


def load_manifest(cache_path: Path) -> dict[str, str]:
    out = scan_model_cache(cache_path)
    for manifest_path in (cache_path / "caa_model_manifest.json", cache_path.parent / "caa_model_manifest.json"):
        if manifest_path.is_file():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            for item in data.get("models", []):
                local = Path(str(item.get("local_path", ""))).expanduser()
                if local.exists():
                    out[str(item["model_id"])] = str(local)
    return out


def resolve_model_source(model_cfg: dict[str, Any], cache_path: Path) -> tuple[str, bool]:
    model_id = str(model_cfg["model_id"])
    explicit = model_cfg.get("local_path") or os.getenv("CAA_MODEL_PATH")
    if explicit:
        path = Path(os.path.expandvars(os.path.expanduser(str(explicit))))
        if not path.exists():
            raise FileNotFoundError(f"Configured local model path does not exist: {path}")
        snapshot = _latest_snapshot(path) or path
        return str(snapshot), True
    cached = load_manifest(cache_path).get(model_id)
    if cached:
        return cached, True
    if bool(model_cfg.get("local_files_only", True)):
        raise FileNotFoundError(f"{model_id} was not found under {cache_path}")
    return model_id, False


def load_local_model(model_cfg: dict[str, Any], cache_path: Path):
    source, is_local = resolve_model_source(model_cfg, cache_path)
    common = {
        "local_files_only": is_local,
        "trust_remote_code": bool(model_cfg.get("trust_remote_code", True)),
    }
    tokenizer = AutoTokenizer.from_pretrained(source, **common)
    model_kwargs = dict(common)
    model_kwargs["device_map"] = model_cfg.get("device_map", "auto")
    # Transformers 5 uses dtype; Transformers 4 accepts torch_dtype.
    dtype = model_cfg.get("dtype", model_cfg.get("torch_dtype", "auto"))
    model_kwargs["dtype"] = dtype
    try:
        model = AutoModelForCausalLM.from_pretrained(source, **model_kwargs)
    except TypeError as exc:
        if "dtype" not in str(exc):
            raise
        model_kwargs["torch_dtype"] = model_kwargs.pop("dtype")
        model = AutoModelForCausalLM.from_pretrained(source, **model_kwargs)
    model.eval()
    return tokenizer, model, source


def runtime_summary() -> dict[str, Any]:
    return {
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "device_count": torch.cuda.device_count(),
        "devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
    }
