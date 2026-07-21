"""Rebuild and validate frozen Part 1 artifacts from one explicit config."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.preprocessing.validate_caa_inputs import validate_all


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "preprocessing" / "configs" / "round5_reviewed_all.json"


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def run(command: list[str], dry_run: bool) -> None:
    print("+ " + subprocess.list2cmdline(command), flush=True)
    if not dry_run:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def git_commit() -> str:
    command = [
        "git", "-c", f"safe.directory={PROJECT_ROOT.as_posix()}",
        "rev-parse", "HEAD",
    ]
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def write_manifest(
    config_path: Path,
    config: dict[str, Any],
    inputs: dict[str, Path],
    output_dir: Path,
) -> None:
    output_files = [
        output_dir / "category_assignments.csv",
        output_dir / "phrase_conversation_bank.jsonl",
        output_dir / "turn_action_conversation_bank.jsonl",
        output_dir / "cag" / "phase_conversation_attack_graph.json",
        output_dir / "cag" / "turn_action_conversation_attack_graph.json",
    ]
    manifest = {
        "schema_version": 1,
        "release_id": config["release_id"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "config": {"path": display_path(config_path), "sha256": sha256(config_path)},
        "inputs": {name: {"path": display_path(path), "sha256": sha256(path)} for name, path in inputs.items()},
        "outputs": {str(path.relative_to(output_dir)): sha256(path) for path in output_files},
    }
    (output_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the deterministic post-review CAB/CAG release and validate its CAA contract."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--build", action="store_true", help="Rebuild outputs before validation")
    mode.add_argument("--validate-only", action="store_true", help="Only validate existing outputs (default)")
    parser.add_argument("--out-dir", type=Path, help="Override the configured artifact directory")
    parser.add_argument("--dry-run", action="store_true", help="Print build commands without running them")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    paths = {name: resolve_path(value) for name, value in config["paths"].items()}
    output_dir = args.out_dir.resolve() if args.out_dir else paths["artifact_dir"]
    inputs = {
        "clean_transcripts": paths["clean_transcripts"],
        "reviewed_codings": paths["reviewed_codings"],
        "reviewed_success_phrases": paths["reviewed_success_phrases"],
        "success_turn_segments": paths["success_turn_segments"],
        "success_validation": paths["success_validation"],
        "unsuccess_turn_segments": paths["segmentation_results_dir"] / "unsuccess_attack" / "turn_segments.csv",
        "unsuccess_phase_segments": paths["segmentation_results_dir"] / "unsuccess_attack" / "phase_segments.csv",
        "no_attack_turn_segments": paths["segmentation_results_dir"] / "no_attack" / "turn_segments.csv",
        "no_attack_phase_segments": paths["segmentation_results_dir"] / "no_attack" / "phase_segments.csv",
        "action_library": paths["action_library"],
    }
    missing = [f"{name}: {path}" for name, path in inputs.items() if not path.is_file()]
    if missing:
        raise SystemExit("Missing frozen input(s):\n- " + "\n- ".join(missing))

    if args.build:
        py = sys.executable
        top_k = str(config.get("statistics", {}).get("top_k", 20))
        commands = [
            [py, "-m", "scripts.preprocessing.build_category_assignments", "--codings", str(paths["reviewed_codings"]), "--clean-transcripts", str(paths["clean_transcripts"]), "--out-dir", str(output_dir)],
            [py, "-m", "scripts.new_cab.build_phase_phrase_bank", "--assignments", str(output_dir / "category_assignments.csv"), "--reviewed-success", str(paths["reviewed_success_phrases"]), "--seg-results-dir", str(paths["segmentation_results_dir"]), "--out-dir", str(output_dir)],
            [py, "-m", "scripts.new_cab.compute_phase_phrase_stats", "--bank", str(output_dir / "phrase_conversation_bank.jsonl"), "--out-dir", str(output_dir / "stats"), "--top-k", top_k],
            [py, "-m", "scripts.new_cab.build_turn_action_bank", "--assignments", str(output_dir / "category_assignments.csv"), "--seg-results-dir", str(paths["segmentation_results_dir"]), "--success-turns", str(paths["success_turn_segments"]), "--success-validation", str(paths["success_validation"]), "--out-dir", str(output_dir)],
            [py, "-m", "scripts.new_cab.compute_turn_action_stats", "--bank", str(output_dir / "turn_action_conversation_bank.jsonl"), "--out-dir", str(output_dir / "turn_action_stats"), "--top-k", top_k],
            [py, "-m", "scripts.new_cab.build_round5_cag", "--phase-bank", str(output_dir / "phrase_conversation_bank.jsonl"), "--action-bank", str(output_dir / "turn_action_conversation_bank.jsonl"), "--action-library", str(paths["action_library"]), "--out-dir", str(output_dir / "cag"), "--seed", str(config.get("graph", {}).get("seed", 7))],
        ]
        for command in commands:
            run(command, args.dry_run)
        if args.dry_run:
            return

    result = validate_all(output_dir, paths["reviewed_codings"], paths["action_library"])
    if result.errors:
        print("CAA handoff validation failed:", file=sys.stderr)
        for error in result.errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"valid": True, "counts": result.counts, "warnings": result.warnings}, indent=2))
    if args.build:
        write_manifest(config_path, config, inputs, output_dir)
        print(f"Wrote provenance manifest: {output_dir / 'artifact_manifest.json'}")


if __name__ == "__main__":
    main()
