from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Literal

import torch
from rich.progress import track

from CAA.scripts.caa_common import (
    load_config,
    load_json,
    resolve_project_path,
    write_json,
    write_jsonl,
)
from CAA.scripts.run_caa_experiment import (
    action_descriptions,
    free_memory,
    generate_chat,
    load_local_model,
    parse_attacker_json,
    read_text,
    render_attacker_prompt,
    response_messages,
    transcript_record_from_conversation,
)
from CAA.scripts.run_weak_attack_experiment import (
    action_phases,
    completed_ids,
    load_jsonl,
    select_weak_attack_action,
    selected_assignments,
)


AttackGeneration = Literal["regenerate", "replay"]


def write_aggregate_outputs(output_dir: Path, attack_generation: AttackGeneration) -> None:
    conversations: list[dict[str, Any]] = []
    for path in sorted(output_dir.glob("caa_*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if row.get("status") == "completed":
            conversations.append(row)

    write_jsonl(
        output_dir / "transcripts.jsonl",
        [transcript_record_from_conversation(row) for row in conversations],
    )
    phase_counts: dict[str, int] = {}
    for row in conversations:
        phase = str(row.get("selected_phase", ""))
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
    write_json(
        output_dir / "run_summary.json",
        {
            "experiment_id": conversations[0]["experiment_id"] if conversations else "",
            "mode": "repeated_single_priority_phase_attack",
            "attack_generation": attack_generation,
            "n_conversations": len(conversations),
            "selected_phase_counts": phase_counts,
        },
    )


def dry_run(
    config_path: Path,
    limit: int | None,
    ids: list[str] | None,
    attack_generation: AttackGeneration,
) -> None:
    config = load_config(config_path)
    assignments_path = config.output_dir / "planning" / "strategy_assignments.jsonl"
    if not assignments_path.exists():
        raise SystemExit(f"Missing planning assignments: {assignments_path}")
    assignments = selected_assignments(load_jsonl(assignments_path), limit, ids)
    phases = action_phases(load_json(config.raw["paths"]["action_cag"]))
    selections = []
    for assignment in assignments:
        selected = select_weak_attack_action(assignment, phases)
        selections.append(
            {
                "attack_id": assignment["attack_id"],
                "attempt": assignment["attempt"],
                "topic_seed": assignment.get("topic_seed", {}),
                **selected,
                "repeat_count": selected["action_count"],
                "attack_generation": attack_generation,
            }
        )
    output_dir = config.output_dir / "repeated_weak_attack_convos"
    write_jsonl(output_dir / "dry_run_selections.jsonl", selections)
    print(
        f"Selected {len(selections)} repeated weak attacks "
        f"-> {output_dir / 'dry_run_selections.jsonl'}"
    )


def execute(
    config_path: Path,
    limit: int | None,
    ids: list[str] | None,
    resume: bool,
    attack_generation: AttackGeneration,
) -> None:
    config = load_config(config_path)
    if bool(config.raw.get("conversation", {}).get("require_cuda", True)) and not torch.cuda.is_available():
        raise SystemExit("CUDA is required but torch.cuda.is_available() is false")

    assignments_path = config.output_dir / "planning" / "strategy_assignments.jsonl"
    if not assignments_path.exists():
        raise SystemExit(f"Missing planning assignments: {assignments_path}")
    assignments = selected_assignments(load_jsonl(assignments_path), limit, ids)
    output_dir = config.output_dir / "repeated_weak_attack_convos"
    done = completed_ids(output_dir) if resume else set()
    assignments = [row for row in assignments if str(row["attack_id"]) not in done]
    print(f"Repeated weak-attack assignments: {len(assignments)} remaining; {len(done)} completed")

    action_cag = load_json(config.raw["paths"]["action_cag"])
    descriptions = action_descriptions(action_cag)
    phases = action_phases(action_cag)
    attacker_system = read_text("CAA/prompts/attacker_system.md")
    attacker_template = read_text("CAA/prompts/attacker_turn_user_template.md")
    response_system = read_text(config.raw["response_model"]["system_prompt"])
    attacker_cfg = config.raw["attacker_model"]
    response_cfg = config.raw["response_model"]
    cache_dir = resolve_project_path(config.raw["paths"]["model_cache"])

    print(f"Loading attacker: {attacker_cfg['model_id']}")
    attacker_tokenizer, attacker_model, attacker_source = load_local_model(
        attacker_cfg["model_id"], cache_dir
    )
    print(f"Loading response: {response_cfg['model_id']}")
    response_tokenizer, response_model, response_source = load_local_model(
        response_cfg["model_id"], cache_dir
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    for assignment in track(assignments, description="Executing repeated weak attacks"):
        selected = select_weak_attack_action(assignment, phases)
        repeat_count = selected["action_count"]
        repeated_assignment = {
            **assignment,
            "action_trajectory_list": [selected["action"]] * repeat_count,
        }
        turns: list[dict[str, Any]] = []
        first_attack: tuple[str, dict[str, Any]] | None = None
        started = time.time()

        for attack_round in range(1, repeat_count + 1):
            if attack_generation == "regenerate" or first_attack is None:
                prompt = render_attacker_prompt(
                    system_prompt=attacker_system,
                    user_template=attacker_template,
                    assignment=repeated_assignment,
                    action=selected["action"],
                    action_index=attack_round,
                    action_count=repeat_count,
                    action_description=descriptions.get(selected["action"], ""),
                    turns=[{"speaker": turn["speaker"], "text": turn["text"]} for turn in turns],
                    recent_topics=[],
                )
                raw_attack = generate_chat(
                    attacker_tokenizer,
                    attacker_model,
                    [
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    max_new_tokens=int(attacker_cfg.get("max_new_tokens", 192)),
                    temperature=float(attacker_cfg.get("temperature", 0.7)),
                    top_p=float(attacker_cfg.get("top_p", 0.9)),
                )
                attack_obj = parse_attacker_json(raw_attack, selected["action"])
                if first_attack is None:
                    first_attack = (raw_attack, attack_obj)
            else:
                raw_attack, attack_obj = first_attack

            student_text = str(attack_obj.get("student_message", "")).strip()
            if not student_text:
                raise RuntimeError(f"{assignment['attack_id']}: attacker generated an empty message")
            turns.append(
                {
                    "turn": len(turns) + 1,
                    "speaker": "Student",
                    "text": student_text,
                    "planned_phase": selected["phase"],
                    "planned_action": selected["action"],
                    "attack_round": attack_round,
                    "source_action_index": selected["action_index"],
                    "attacker_raw": raw_attack,
                    "attacker_rationale": attack_obj.get("rationale", ""),
                    "attacker_parse_fallback": bool(attack_obj.get("parse_fallback", False)),
                    "replayed": attack_generation == "replay" and attack_round > 1,
                }
            )
            professor_text = generate_chat(
                response_tokenizer,
                response_model,
                response_messages(
                    response_system,
                    [{"speaker": turn["speaker"], "text": turn["text"]} for turn in turns],
                ),
                max_new_tokens=int(response_cfg.get("max_new_tokens", 192)),
                temperature=float(response_cfg.get("temperature", 0.7)),
                top_p=float(response_cfg.get("top_p", 0.9)),
            )
            turns.append(
                {"turn": len(turns) + 1, "speaker": "Steve", "text": professor_text}
            )

        conversation = {
            "attack_id": assignment["attack_id"],
            "experiment_id": assignment["experiment_id"],
            "created_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "attempt": assignment["attempt"],
            "status": "completed",
            "mode": "repeated_single_priority_phase_attack",
            "attack_generation": attack_generation,
            "selected_phase": selected["phase"],
            "selected_action": selected["action"],
            "source_action_index": selected["action_index"],
            "action_count": repeat_count,
            "duration_s": round(time.time() - started, 2),
            "models": {
                "attacker": attacker_cfg["model_id"],
                "attacker_source": attacker_source,
                "response": response_cfg["model_id"],
                "response_source": response_source,
            },
            "strategy": {
                "phase_trajectory": assignment.get("phase_trajectory_list", []),
                "action_trajectory": assignment.get("action_trajectory_list", []),
                "repeated_action_trajectory": [selected["action"]] * repeat_count,
                "source_conversation_ids": assignment.get("source_conversation_ids", ""),
                "topic_seed": assignment.get("topic_seed", {}),
            },
            "turns": turns,
        }
        write_json(output_dir / f"{assignment['attack_id']}.json", conversation)
        write_aggregate_outputs(output_dir, attack_generation)

    write_aggregate_outputs(output_dir, attack_generation)
    print(f"Wrote repeated weak-attack outputs to {output_dir}")
    del attacker_model, response_model, attacker_tokenizer, response_tokenizer
    free_memory()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Repeat one priority-selected attack action for the same number of rounds "
            "as the source trajectory."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="*")
    parser.add_argument(
        "--attack-generation",
        choices=("regenerate", "replay"),
        default="regenerate",
        help=(
            "regenerate creates a context-aware message each round while keeping the action fixed; "
            "replay repeats the first generated message verbatim"
        ),
    )
    args = parser.parse_args()
    if args.execute == args.dry_run:
        raise SystemExit("Choose exactly one of --dry-run or --execute")
    if args.execute:
        execute(args.config, args.limit, args.ids, args.resume, args.attack_generation)
    else:
        dry_run(args.config, args.limit, args.ids, args.attack_generation)


if __name__ == "__main__":
    main()
