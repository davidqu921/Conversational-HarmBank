from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit("Missing dependency: pip install pyyaml") from exc

try:
    from huggingface_hub import HfApi, get_token, snapshot_download
except ImportError as exc:
    raise SystemExit("Missing dependency: pip install huggingface-hub") from exc


DEFAULT_MODELS = [
    "meta-llama/Llama-3.1-8B-Instruct",
    "google/gemma-2-9b",
]


def load_config_models(path: Path) -> tuple[list[str], Path | None]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    models: list[str] = []
    for key in ("attacker_model", "response_model"):
        model_id = (data.get(key) or {}).get("model_id")
        if model_id:
            models.append(str(model_id))
    cache = ((data.get("paths") or {}).get("model_cache"))
    return models, Path(cache) if cache else None


def token_from_env_or_arg(token: str | None) -> str | None:
    return token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or get_token()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download CAA Hugging Face models into the local cache.")
    parser.add_argument("--config", type=Path, default=Path("CAA/configs/round5_balanced_40.yaml"))
    parser.add_argument("--model", action="append", dest="models", help="Model id to download. Can be repeated.")
    parser.add_argument("--cache-dir", type=Path, help="Hugging Face cache directory.")
    parser.add_argument("--token", help="Hugging Face token. Prefer HF_TOKEN env var instead of passing this.")
    parser.add_argument("--revision", default=None)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    config_models: list[str] = []
    config_cache: Path | None = None
    if args.config.exists():
        config_models, config_cache = load_config_models(args.config)

    models = args.models or config_models or DEFAULT_MODELS
    cache_dir = args.cache_dir or config_cache or Path("D:/Summer_Project_2026/hf_cache")
    token = token_from_env_or_arg(args.token)

    if not token and not args.local_files_only:
        raise SystemExit(
            "No Hugging Face token found. Set HF_TOKEN/HUGGINGFACE_HUB_TOKEN or run huggingface-cli login."
        )

    cache_dir.mkdir(parents=True, exist_ok=True)
    api = HfApi(token=token)
    manifest = {
        "cache_dir": str(cache_dir),
        "models": [],
    }

    for model_id in models:
        print(f"Checking access: {model_id}")
        if not args.local_files_only:
            api.model_info(model_id, token=token)
        print(f"Downloading: {model_id}")
        local_path = snapshot_download(
            repo_id=model_id,
            revision=args.revision,
            cache_dir=str(cache_dir),
            token=token,
            local_files_only=args.local_files_only,
        )
        manifest["models"].append({"model_id": model_id, "local_path": local_path})
        print(f"Downloaded {model_id} -> {local_path}")

    manifest_path = cache_dir / "caa_model_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
