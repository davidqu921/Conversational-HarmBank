from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import torch
import transformers

from CAA.scripts.caa_common import load_config, model_cache_path
from CAA.scripts.model_runtime import resolve_model_source, runtime_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight CAA on Linux/ARM64/NVIDIA.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--allow-cpu", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    report = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "transformers": transformers.__version__,
        **runtime_summary(),
        "models": {},
    }
    cache = model_cache_path(config.raw)
    errors: list[str] = []
    if platform.system() != "Linux":
        errors.append("production inference target must be Linux")
    if platform.machine().lower() not in {"aarch64", "arm64"}:
        errors.append(f"expected ARM64/aarch64, found {platform.machine()}")
    if not torch.cuda.is_available() and not args.allow_cpu:
        errors.append("PyTorch cannot access CUDA")
    for role in ("attacker_model", "response_model"):
        try:
            source, local = resolve_model_source(config.raw[role], cache)
            report["models"][role] = {"source": source, "local": local, "exists": Path(source).exists()}
        except Exception as exc:
            report["models"][role] = {"error": f"{type(exc).__name__}: {exc}"}
            errors.append(f"{role}: {exc}")
    report["errors"] = errors
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
