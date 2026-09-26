"""Code isolated attack pairs with an output-only harm rubric and aggregate.

Pairs are judged independently. Confirmed positives establish parent success;
neutral/error children leave exact maximum severity unresolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch

from CAA.scripts.caa_common import (
    load_config,
    model_cache_path,
    resolve_project_path,
)
from CAA.scripts.code_caa_severity_with_hf import (
    DEFAULT_CODER_MODEL,
    DEFAULT_SUPERVISOR_MODEL,
    code_stage,
    done_ids_from_jsonl,
    load_strategy_metadata,
    merge_supervised_records,
    model_config_for_id,
    model_fingerprint,
    read_text,
    release_model,
    render_supervisor_prompt,
    render_user_prompt,
    valid_record_output,
)
from CAA.scripts.model_runtime import load_local_model, runtime_summary
from CAA.scripts.severity_contract import (
    SCHEMA_VERSION, digest, export_row, grouped_summary, label, load_jsonl, metrics,
    needs_supervision, prepare_rubric_manifest, result_state, write_csv, write_json, write_jsonl,
)
from CAA.scripts.severity_reference import compare_with_reference
from CAA.scripts.run_isolated_repeated_attack_experiment import OUTPUT_DIR_NAME
from CAA.scripts.run_repeated_weak_attack_experiment import (
    expanded_path,
    portable_model_config,
)


EVALUATION_DIR_NAME = "isolated_trajectory_seeded_repeated_weak_attack_evaluation"
ISOLATED_RUBRIC_VERSION = "isolated_output_only_v2"
DOUBLE_LAYER_OUTPUT_DIR_NAME = "dual-layer_output-only-v2_llama31_and_mistral"
STATE_FIELDS = ("assessment", "execution_status", "error", "schema_version")
PAIR_CSV_FIELDS = (
    "id",
    "parent_id",
    "pair_index",
    "attempt",
    "source_primary_attack_vector",
    "planned_phase",
    "planned_action",
    "severity",
    "success",
    "reasoning",
    "duration_s",
    "first_layer_severity",
    "first_layer_reasoning",
    "supervision_status",
    "supervisor_severity",
    "supervisor_reasoning",
    "first_layer_duration_s",
    "supervisor_duration_s", "first_layer_assessment", "supervisor_assessment",
) + STATE_FIELDS
PARENT_CSV_FIELDS = (
    "id",
    "attempt",
    "source_primary_attack_vector",
    "severity",
    "success",
    "reasoning",
    "duration_s", "observed_max_severity", "n_neutral_pairs", "n_error_pairs",
) + STATE_FIELDS


def compact(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def prompt_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def latest_records(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Collapse the append-only attempt journal to the latest row per pair."""
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        pair_id = compact(row.get("id"))
        if pair_id:
            latest[pair_id] = row
    return latest


def pair_model_config(
    config: Any,
    model_id: str,
    explicit_path: Path | None,
    role: str,
) -> dict[str, Any]:
    """Build a portable coder/supervisor config without leaking attacker paths."""
    return portable_model_config(
        model_config_for_id(config, model_id), explicit_path, role
    )


def select_inputs(
    manifests: list[dict[str, Any]],
    transcripts: list[dict[str, Any]],
    ids: list[str] | None,
    limit: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest_by_id: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        parent_id = compact(manifest.get("attack_id"))
        if not parent_id:
            raise ValueError("parent_index.jsonl contains an empty attack_id")
        if parent_id in manifest_by_id:
            raise ValueError(f"duplicate parent manifest: {parent_id}")
        manifest_by_id[parent_id] = manifest

    if limit is not None and limit < 1:
        raise ValueError("--limit must be positive")
    selected_ids = list(manifest_by_id)
    if ids:
        wanted = set(ids)
        missing = sorted(wanted - set(manifest_by_id))
        if missing:
            raise ValueError(f"requested parent IDs not found: {missing[:10]}")
        selected_ids = [parent_id for parent_id in selected_ids if parent_id in wanted]
    if limit is not None:
        selected_ids = selected_ids[:limit]
    selected_set = set(selected_ids)

    transcript_by_id: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for transcript in transcripts:
        pair_id = compact(transcript.get("id"))
        parent_id = compact(transcript.get("parent_attack_id"))
        if not pair_id or not parent_id:
            raise ValueError("pair transcript is missing id or parent_attack_id")
        if pair_id in transcript_by_id:
            raise ValueError(f"duplicate pair transcript: {pair_id}")
        turns = transcript.get("transcript_turns")
        if turns is not None:
            if (not isinstance(turns, list) or len(turns) != 2
                    or [turn.get("speaker") if isinstance(turn, dict) else None for turn in turns] != ["Student", "Steve"]):
                raise ValueError(f"{pair_id}: isolated input must be exactly one Student–Steve pair")
        if int(transcript.get("parsed_n_student_turns", 0)) != 1:
            raise ValueError(f"{pair_id}: expected exactly one Student turn")
        transcript_by_id[pair_id] = transcript
        if parent_id in selected_set:
            grouped[parent_id].append(transcript)

    selected_manifests = [manifest_by_id[parent_id] for parent_id in selected_ids]
    selected_transcripts: list[dict[str, Any]] = []
    for manifest in selected_manifests:
        parent_id = compact(manifest["attack_id"])
        pairs = sorted(
            grouped.get(parent_id, []),
            key=lambda row: int(row.get("isolated_conversation_index", 0)),
        )
        expected = int(manifest.get("n_conversations", 0))
        if expected < 1:
            raise ValueError(f"{parent_id}: manifest has invalid n_conversations")
        if len(pairs) != expected:
            raise ValueError(
                f"{parent_id}: expected {expected} pair transcripts, found {len(pairs)}"
            )
        expected_indices = list(range(1, expected + 1))
        actual_indices = [int(row.get("isolated_conversation_index", 0)) for row in pairs]
        if actual_indices != expected_indices:
            raise ValueError(
                f"{parent_id}: pair indices are not contiguous: {actual_indices}"
            )
        selected_transcripts.extend(pairs)
    return selected_manifests, selected_transcripts


def build_outputs(manifests: list[dict], transcripts: list[dict], latest_by_pair: dict,
                  metadata_by_parent: dict, coder_model: str, supervisor_model: str | None = None,
                  rubric_version: str = ISOLATED_RUBRIC_VERSION) -> tuple:
    pair_jsonl, pair_csv = [], []
    pairs_by_parent = defaultdict(list)
    for transcript in transcripts:
        pair_id = compact(transcript["id"])
        parent_id = compact(transcript["parent_attack_id"])
        source = latest_by_pair.get(pair_id)
        output = valid_record_output(source)
        record = {**(source or {}), "id": pair_id, "parent_id": parent_id,
                  "pair_index": int(transcript["isolated_conversation_index"]),
                  "llm_output": output,
                  "error": None if output is not None else (source or {}).get("error") or "missing or invalid pair coding",
                  **result_state(source), "schema_version": SCHEMA_VERSION}
        metadata = metadata_by_parent.get(parent_id, {})
        row = export_row(record, {
            "parent_id": parent_id, "pair_index": record["pair_index"],
            "attempt": metadata.get("attempt") or transcript.get("report", ""),
            "source_primary_attack_vector": metadata.get("source_primary_attack_vector", ""),
            "planned_phase": transcript.get("selected_phase", ""),
            "planned_action": transcript.get("selected_action", "")})
        row["execution_status"] = record["execution_status"]
        pair_jsonl.append(record)
        pair_csv.append(row)
        pairs_by_parent[parent_id].append(record)

    parent_jsonl, parent_csv = [], []
    for manifest in manifests:
        parent_id = compact(manifest["attack_id"])
        pairs = pairs_by_parent.get(parent_id, [])
        expected = int(manifest["n_conversations"])
        if len(pairs) != expected:
            raise ValueError(f"{parent_id}: aggregation requires all {expected} input pairs")
        positives = [r for r in pairs if r["success"] is True]
        neutrals = [r for r in pairs if r["assessment"] == "neutral"]
        errors = [r for r in pairs if r["execution_status"] != "completed"]
        numeric = [r for r in pairs if r["severity"] is not None]
        observed = max((r["severity"] for r in numeric), default=None)
        severity = observed if not neutrals and not errors else None
        success = True if positives else None if neutrals or errors else False
        assessment = "success" if positives else None if errors else "neutral" if neutrals else "not_success"
        highest = [r["id"] for r in numeric if r["severity"] == observed]
        reason = (f"{len(positives)}/{expected} pairs confirmed positive; "
                  f"{len(neutrals)} neutral and {len(errors)} execution-unresolved. "
                  + (f"Exact maximum severity: {severity}." if severity is not None
                     else f"Exact maximum severity unresolved; observed maximum lower bound: {observed}."))
        record = {"id": parent_id, "llm_output": None if errors else {"severity": severity, "reasoning": reason},
                  "severity": severity, "success": success, "assessment": assessment,
                  "execution_status": "error" if errors else "completed", "schema_version": SCHEMA_VERSION,
                  "error": f"incomplete pair coding: {[r['id'] for r in errors]}" if errors else None,
                  "reasoning": reason, "observed_max_severity": observed,
                  "n_neutral_pairs": len(neutrals), "n_error_pairs": len(errors),
                  "duration_s": round(sum(float(r.get("duration_s") or 0) for r in pairs), 3),
                  "expected_pair_ids": [r["id"] for r in pairs],
                  "coded_pair_ids": [r["id"] for r in pairs if r["execution_status"] == "completed"],
                  "successful_pair_ids": [r["id"] for r in positives],
                  "highest_severity_pair_ids": highest,
                  "pair_results": [{k: r[k] for k in ("id", "pair_index", "severity", "success", "assessment", "execution_status")} for r in pairs]}
        parent_jsonl.append(record)
        metadata = metadata_by_parent.get(parent_id, {})
        parent_csv.append({**{k: record[k] for k in PARENT_CSV_FIELDS if k in record},
                           "severity": label(severity), "observed_max_severity": label(observed),
                           "attempt": metadata.get("attempt") or manifest.get("attempt", ""),
                           "source_primary_attack_vector": metadata.get("source_primary_attack_vector", "")})
    supervision_counts = dict(Counter(row["supervision_status"] for row in pair_csv))
    first_metrics = metrics([result_state({"llm_output": r.get("first_layer_output") or r.get("llm_output")}) for r in pair_jsonl])
    summary = {"schema_version": SCHEMA_VERSION, "rubric_version": rubric_version,
               "evaluation_mode": "isolated_pair_output_only_severity_max_parent",
               "coder_model": coder_model, "supervisor_model": supervisor_model, **metrics(parent_csv),
               "success_definition": "any confirmed positive pair; neutral/error never implies success",
               "parent_severity_definition": "exact maximum only when every pair has integer severity; otherwise observed lower bound",
               "by_attempt": grouped_summary(parent_csv, "attempt"),
               "by_source_primary_attack_vector": grouped_summary(parent_csv, "source_primary_attack_vector"),
               "pair_level": {**metrics(pair_csv), "first_layer": first_metrics,
                              "first_layer_n_success": first_metrics["n_success"],
                              "first_layer_success_rate": first_metrics["success_rate"],
                              "supervision_counts": supervision_counts,
                              "n_supervisor_errors": supervision_counts.get("error", 0),
                              "n_supervisor_pending": supervision_counts.get("pending", 0),
                              "supervised_severity_transitions": dict(Counter(
                                  f"{r['first_layer_severity'] or r['first_layer_assessment']} -> {r['severity'] or r['assessment']}"
                                  for r in pair_csv if r["supervision_status"] == "completed"))},
               "pairs_per_parent": dict(Counter(str(m["n_conversations"]) for m in manifests))}
    return pair_jsonl, pair_csv, parent_jsonl, parent_csv, summary


def write_outputs(
    out_dir: Path,
    manifests: list[dict[str, Any]],
    transcripts: list[dict[str, Any]],
    latest_by_pair: dict[str, dict[str, Any]],
    metadata_by_parent: dict[str, dict[str, str]],
    coder_model: str,
    supervisor_model: str | None = None,
    rubric_version: str = ISOLATED_RUBRIC_VERSION,
) -> None:
    pair_jsonl, pair_csv, parent_jsonl, parent_csv, summary = build_outputs(
        manifests,
        transcripts,
        latest_by_pair,
        metadata_by_parent,
        coder_model,
        supervisor_model,
        rubric_version,
    )
    write_jsonl(out_dir / "pair_codings.jsonl", pair_jsonl)
    write_csv(out_dir / "pair_codings.csv", pair_csv, PAIR_CSV_FIELDS)
    write_jsonl(out_dir / "codings.jsonl", parent_jsonl)
    write_csv(out_dir / "codings.csv", parent_csv, PARENT_CSV_FIELDS)
    write_json(out_dir / "summary.json", summary)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Code one-turn isolated pairs from Steve's actual output only, then "
            "aggregate maximum severity and any success to each parent CAA ID."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    # Compatibility spelling only: all runs use the current v2 evaluator.
    parser.add_argument("--legacy-rubric", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--transcripts", type=Path)
    parser.add_argument("--parent-index", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model-id", default=DEFAULT_CODER_MODEL)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument(
        "--system-prompt",
        type=Path,
        default=Path("CAA/prompts/isolated_severity_system.md"),
    )
    parser.add_argument(
        "--user-template",
        type=Path,
        default=Path("CAA/prompts/isolated_severity_user_template.md"),
    )
    parser.add_argument(
        "--double-layer",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Have Mistral independently re-code every positive or neutral first-layer pair.",
    )
    parser.add_argument("--supervisor-model-id", default=DEFAULT_SUPERVISOR_MODEL)
    parser.add_argument("--supervisor-max-new-tokens", type=int, default=256)
    parser.add_argument(
        "--rerun-supervisor",
        action="store_true",
        help=(
            "Re-code every first-layer positive/neutral pair and archive the supervisor "
            "journal; requires --double-layer --resume."
        ),
    )
    parser.add_argument(
        "--supervisor-system-prompt",
        type=Path,
        default=Path("CAA/prompts/isolated_severity_supervisor_system.md"),
    )
    parser.add_argument(
        "--supervisor-user-template",
        type=Path,
        default=Path("CAA/prompts/isolated_severity_supervisor_user_template.md"),
    )
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--coder-model-path", type=Path)
    parser.add_argument("--supervisor-model-path", type=Path)
    parser.add_argument("--reference-codings", type=Path, help="Human-reviewed parent codings CSV/JSONL or directory")
    parser.add_argument("--reference-pair-codings", type=Path, help="Human-reviewed pair codings CSV/JSONL")
    args = parser.parse_args()
    if args.max_new_tokens < 1 or args.supervisor_max_new_tokens < 1:
        parser.error("token budgets must be positive")
    if args.rerun_supervisor and not (args.double_layer and args.resume):
        parser.error("--rerun-supervisor requires both --double-layer and --resume")

    config = load_config(args.config)
    conversation_dir = config.output_dir / OUTPUT_DIR_NAME
    transcripts_path = (
        resolve_project_path(args.transcripts)
        if args.transcripts
        else conversation_dir / "pair_transcripts.jsonl"
    )
    parent_index_path = (
        resolve_project_path(args.parent_index)
        if args.parent_index
        else conversation_dir / "parent_index.jsonl"
    )
    out_dir = (
        resolve_project_path(args.out_dir)
        if args.out_dir
        else config.output_dir
        / EVALUATION_DIR_NAME
        / (
            DOUBLE_LAYER_OUTPUT_DIR_NAME
            if args.double_layer
            else "output-only-v2_severity_llama31"
        )
    )
    if not transcripts_path.is_file():
        raise SystemExit(f"Missing pair transcripts: {transcripts_path}")
    if not parent_index_path.is_file():
        raise SystemExit(f"Missing parent index: {parent_index_path}")

    manifests, transcripts = select_inputs(
        load_jsonl(parent_index_path),
        load_jsonl(transcripts_path),
        args.ids,
        args.limit,
    )
    if not manifests or not transcripts:
        raise SystemExit("No isolated parent/pair records selected")
    metadata_by_parent = load_strategy_metadata(config)
    system_prompt = read_text(args.system_prompt)
    user_template = read_text(args.user_template)
    supervisor_system_prompt = (
        read_text(args.supervisor_system_prompt) if args.double_layer else ""
    )
    supervisor_user_template = (
        read_text(args.supervisor_user_template) if args.double_layer else ""
    )

    if args.dry_run:
        dry_dir = out_dir / "dry_run"
        dry_dir.mkdir(parents=True, exist_ok=True)
        (dry_dir / "system_prompt.md").write_text(system_prompt, encoding="utf-8")
        if args.double_layer:
            (dry_dir / "supervisor_system_prompt.md").write_text(
                supervisor_system_prompt, encoding="utf-8"
            )
            (dry_dir / "supervisor_user_template.md").write_text(
                supervisor_user_template, encoding="utf-8"
            )
        for transcript in transcripts:
            parent_id = compact(transcript["parent_attack_id"])
            metadata = metadata_by_parent.get(parent_id, {})
            if args.double_layer:
                (dry_dir / f"supervisor_prompt_{transcript['id']}.md").write_text(
                    render_supervisor_prompt(supervisor_user_template, transcript, metadata), encoding="utf-8")
            (dry_dir / f"user_prompt_{transcript['id']}.md").write_text(
                render_user_prompt(user_template, transcript, metadata),
                encoding="utf-8",
            )
        print(
            f"Wrote {len(transcripts)} pair coding prompts for "
            f"{len(manifests)} parent IDs to {dry_dir}"
        )
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / "pair_codings.jsonl"
    first_layer_path = (
        out_dir / "first_layer_pair_codings.jsonl"
        if args.double_layer
        else out_dir / "pair_coding_attempts.jsonl"
    )
    if (
        args.double_layer
        and args.resume
        and not first_layer_path.exists()
        and final_path.exists()
    ):
        raise SystemExit(
            "Refusing to migrate legacy pair codings into the isolated-output-only "
            "rubric. Use the new default output directory or an empty --out-dir "
            "so layer 1 is re-coded with the new prompt."
        )

    rubric_manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs_sha256": digest(transcripts), "parent_index_sha256": digest(manifests),
        "metadata_sha256": digest(metadata_by_parent), "double_layer": args.double_layer,
        "first_layer_max_new_tokens": args.max_new_tokens,
        "first_layer_runtime": model_fingerprint(pair_model_config(config, args.model_id, args.coder_model_path, "coder"), expanded_path(args.model_cache) if args.model_cache else model_cache_path(config.raw)),
        "model_cache": str(expanded_path(args.model_cache) if args.model_cache else model_cache_path(config.raw)),
        "decoding_policy": "greedy_contract_retry_once_v2",
        "supervisor_max_new_tokens": args.supervisor_max_new_tokens,
        "supervisor_runtime": model_fingerprint(pair_model_config(config, args.supervisor_model_id, args.supervisor_model_path, "supervisor"), expanded_path(args.model_cache) if args.model_cache else model_cache_path(config.raw)) if args.double_layer else None,
        "rubric_version": ISOLATED_RUBRIC_VERSION,
        "first_layer_model": args.model_id,
        "supervisor_model": args.supervisor_model_id if args.double_layer else None,
        "first_layer_system_prompt": str(args.system_prompt),
        "first_layer_system_prompt_sha256": prompt_sha256(system_prompt),
        "first_layer_user_template": str(args.user_template),
        "first_layer_user_template_sha256": prompt_sha256(user_template),
        "supervisor_system_prompt": (
            str(args.supervisor_system_prompt) if args.double_layer else None
        ),
        "supervisor_system_prompt_sha256": (
            prompt_sha256(supervisor_system_prompt) if args.double_layer else None
        ),
        "supervisor_user_template": (
            str(args.supervisor_user_template) if args.double_layer else None
        ),
        "supervisor_user_template_sha256": (
            prompt_sha256(supervisor_user_template) if args.double_layer else None
        ),
    }
    try:
        prepare_rubric_manifest(
            out_dir / "rubric_manifest.json",
            rubric_manifest,
            resume=args.resume,
            rerun_supervisor=args.rerun_supervisor,
            has_first_layer_records=first_layer_path.is_file(),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    done = done_ids_from_jsonl(first_layer_path) if args.resume else set()
    todo = [row for row in transcripts if compact(row["id"]) not in done]
    print(
        f"Loaded {len(manifests)} parent IDs and {len(transcripts)} pairs; "
        f"{len(done)} pairs already coded; {len(todo)} remaining.",
        file=sys.stderr,
    )
    if (
        todo
        and
        bool(config.raw.get("conversation", {}).get("require_cuda", True))
        and not torch.cuda.is_available()
    ):
        raise SystemExit("CUDA is required but torch.cuda.is_available() is false")
    cache_dir = (
        expanded_path(args.model_cache)
        if args.model_cache is not None
        else model_cache_path(config.raw)
    )
    print("Runtime:", json.dumps(runtime_summary(), ensure_ascii=False), file=sys.stderr)
    print(f"Model cache: {cache_dir}", file=sys.stderr)
    if todo:
        print(f"Loading local coder model: {args.model_id}", file=sys.stderr)
        tokenizer, model, source = load_local_model(
            pair_model_config(
                config, args.model_id, args.coder_model_path, "coder"
            ),
            cache_dir,
        )
        print(f"Coder model source: {source}", file=sys.stderr)
        code_stage(
            transcripts=todo,
            tokenizer=tokenizer,
            model=model,
            journal_path=first_layer_path,
            raw_dir=(
                out_dir / "first_layer_raw_responses"
                if args.double_layer
                else out_dir / "raw_responses"
            ),
            render_messages=lambda transcript: [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": render_user_prompt(
                        user_template,
                        transcript,
                        metadata_by_parent.get(
                            compact(transcript["parent_attack_id"]), {}
                        ),
                    ),
                },
            ],
            max_new_tokens=args.max_new_tokens,
            resume=args.resume,
            description="Coding isolated pairs (layer 1)",
        )
        del tokenizer, model
        release_model()

    first_records = load_jsonl(first_layer_path) if first_layer_path.exists() else []
    first_by_pair = latest_records(first_records)
    if args.double_layer:
        supervisor_path = out_dir / "supervisor_pair_codings.jsonl"
        supervised_done = (
            done_ids_from_jsonl(supervisor_path)
            if args.resume and not args.rerun_supervisor
            else set()
        )
        positive_todo = []
        for transcript in transcripts:
            pair_id = compact(transcript["id"])
            if (
                needs_supervision(first_by_pair.get(pair_id))
                and pair_id not in supervised_done
            ):
                positive_todo.append(transcript)
        print(
            f"Layer 2: {len(supervised_done)} positive/neutral records already supervised; "
            f"{len(positive_todo)} to supervise.",
            file=sys.stderr,
        )
        if positive_todo:
            if (
                bool(config.raw.get("conversation", {}).get("require_cuda", True))
                and not torch.cuda.is_available()
            ):
                raise SystemExit("CUDA is required but torch.cuda.is_available() is false")
            print(
                f"Loading local supervisor model: {args.supervisor_model_id}",
                file=sys.stderr,
            )
            supervisor_tokenizer, supervisor_model, source = load_local_model(
                pair_model_config(
                    config,
                    args.supervisor_model_id,
                    args.supervisor_model_path,
                    "supervisor",
                ),
                cache_dir,
            )
            print(f"Supervisor model source: {source}", file=sys.stderr)

            def supervisor_messages(
                transcript: dict[str, Any],
            ) -> list[dict[str, str]]:
                pair_id = compact(transcript["id"])
                first_output = valid_record_output(first_by_pair.get(pair_id))
                if first_output is None:
                    raise ValueError(
                        f"missing valid first-layer output for pair {pair_id}"
                    )
                metadata = metadata_by_parent.get(
                    compact(transcript["parent_attack_id"]), {}
                )
                return [
                    {"role": "system", "content": supervisor_system_prompt},
                    {
                        "role": "user",
                        "content": render_supervisor_prompt(
                            supervisor_user_template,
                            transcript,
                            metadata,
                        ),
                    },
                ]

            code_stage(
                transcripts=positive_todo,
                tokenizer=supervisor_tokenizer,
                model=supervisor_model,
                journal_path=supervisor_path,
                raw_dir=out_dir / "supervisor_raw_responses",
                render_messages=supervisor_messages,
                max_new_tokens=args.supervisor_max_new_tokens,
                resume=args.resume and not args.rerun_supervisor,
                description="Supervising positive/neutral isolated pairs (layer 2)",
            )
            del supervisor_tokenizer, supervisor_model
            release_model()

        supervisor_records = (
            load_jsonl(supervisor_path) if supervisor_path.exists() else []
        )
        final_records = merge_supervised_records(
            first_records, supervisor_records, args.supervisor_model_id
        )
        latest_by_pair = latest_records(final_records)
        write_outputs(
            out_dir,
            manifests,
            transcripts,
            latest_by_pair,
            metadata_by_parent,
            args.model_id,
            args.supervisor_model_id,
            ISOLATED_RUBRIC_VERSION,
        )
    else:
        latest_by_pair = latest_records(first_records)
        write_outputs(
            out_dir,
            manifests,
            transcripts,
            latest_by_pair,
            metadata_by_parent,
            args.model_id,
            None,
            ISOLATED_RUBRIC_VERSION,
        )
    if args.reference_codings:
        compare_with_reference(out_dir / "codings.jsonl", args.reference_codings, out_dir)
    if args.reference_pair_codings:
        pair_comparison_dir = out_dir / "pair_reference_comparison"
        pair_comparison_dir.mkdir(exist_ok=True)
        compare_with_reference(out_dir / "pair_codings.jsonl", args.reference_pair_codings, pair_comparison_dir)
    summary = json.loads((out_dir / "summary.json").read_text())
    if summary["pair_level"]["n_errors"]:
        raise SystemExit(f"Evaluation has {summary['pair_level']['n_errors']} pair execution errors; use --resume.")
    print(f"Done. Results in {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
