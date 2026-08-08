from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Literal

import torch
from rich.progress import track

from CAA.scripts.caa_common import (
    load_config,
    load_json,
    model_cache_path,
    write_json,
    write_jsonl,
)
from CAA.scripts.model_runtime import load_local_model, runtime_summary
from CAA.scripts.run_caa_experiment import (
    action_descriptions,
    free_memory,
    generate_chat,
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


AttackGeneration = Literal["trajectory_seeded", "regenerate", "replay"]


def attack_round_count(selected: dict[str, Any], rounds: int | None) -> int:
    """Use an explicit round count, or preserve the source trajectory length."""
    count = int(rounds if rounds is not None else selected["action_count"])
    if count < 1:
        raise ValueError(f"attack round count must be positive, got {count}")
    return count


def expanded_path(path: Path) -> Path:
    """Expand Linux-style ~ and environment variables supplied on the CLI."""
    return Path(os.path.expandvars(os.path.expanduser(str(path))))


def portable_model_config(
    model_cfg: dict[str, Any],
    cli_path: Path | None,
    role: str,
) -> dict[str, Any]:
    """Apply a CLI model path or ignore a stale path copied from another host."""
    result = dict(model_cfg)
    if cli_path is not None:
        result["local_path"] = str(expanded_path(cli_path))
        return result
    configured = result.get("local_path")
    if configured:
        configured_path = expanded_path(Path(str(configured)))
        if configured_path.exists():
            result["local_path"] = str(configured_path)
        else:
            print(
                f"Warning: ignoring unavailable {role} local_path copied from another host: "
                f"{configured_path}"
            )
            result.pop("local_path", None)
    return result


def trajectory_seed_turn(
    conversations_dir: Path,
    assignment: dict[str, Any],
    selected: dict[str, Any],
) -> dict[str, Any]:
    """Load the original trajectory turn corresponding to the selected plan action."""
    attack_id = str(assignment["attack_id"])
    conversation_path = conversations_dir / f"{attack_id}.json"
    if not conversation_path.is_file():
        raise FileNotFoundError(
            f"{attack_id}: missing source trajectory conversation: {conversation_path}"
        )
    conversation = json.loads(conversation_path.read_text(encoding="utf-8"))
    student_turns = [
        turn
        for turn in conversation.get("turns", [])
        if str(turn.get("speaker", "")).strip().lower() == "student"
    ]
    source_index = int(selected["action_index"])
    selected_action = str(selected["action"])
    candidate = student_turns[source_index - 1] if source_index <= len(student_turns) else None

    # A terminated or legacy trajectory may not line up one-for-one by ordinal.
    # In that case, match the same occurrence of the selected action in the plan.
    if candidate is None or str(candidate.get("planned_action", "")) != selected_action:
        planned_actions = [
            str(item) for item in assignment.get("action_trajectory_list", [])
        ]
        occurrence = sum(
            action == selected_action for action in planned_actions[:source_index]
        )
        matching_turns = [
            turn
            for turn in student_turns
            if str(turn.get("planned_action", "")) == selected_action
        ]
        candidate = (
            matching_turns[occurrence - 1]
            if occurrence > 0 and occurrence <= len(matching_turns)
            else None
        )

    if candidate is None:
        raise ValueError(
            f"{attack_id}: could not find source Student turn for action "
            f"{selected_action!r} at plan index {source_index} in {conversation_path}"
        )
    text = str(candidate.get("text", "")).strip()
    if not text:
        raise ValueError(
            f"{attack_id}: matched source trajectory turn has empty text in "
            f"{conversation_path}"
        )
    attacker_raw = str(candidate.get("attacker_raw", ""))
    topic = ""
    if attacker_raw:
        try:
            raw_obj = json.loads(attacker_raw)
            if isinstance(raw_obj, dict):
                topic = str(raw_obj.get("topic", "")).strip()
        except json.JSONDecodeError:
            pass
    return {
        "text": text,
        "source_path": str(conversation_path),
        "source_turn": candidate.get("turn"),
        "attacker_raw": attacker_raw,
        "attacker_rationale": str(candidate.get("attacker_rationale", "")),
        "attacker_parse_fallback": bool(
            candidate.get("attacker_parse_fallback", False)
        ),
        "topic": topic,
    }


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
    rounds: int | None,
) -> None:
    config = load_config(config_path)
    assignments_path = config.output_dir / "planning" / "strategy_assignments.jsonl"
    if not assignments_path.exists():
        raise SystemExit(f"Missing planning assignments: {assignments_path}")
    assignments = selected_assignments(load_jsonl(assignments_path), limit, ids)
    phases = action_phases(load_json(config.raw["paths"]["action_cag"]))
    conversations_dir = config.output_dir / "conversations"
    selections = []
    for assignment in assignments:
        selected = select_weak_attack_action(assignment, phases)
        repeat_count = attack_round_count(selected, rounds)
        selection = {
            "attack_id": assignment["attack_id"],
            "attempt": assignment["attempt"],
            "topic_seed": assignment.get("topic_seed", {}),
            **selected,
            "source_action_count": selected["action_count"],
            "repeat_count": repeat_count,
            "attack_generation": attack_generation,
        }
        if attack_generation == "trajectory_seeded":
            seed = trajectory_seed_turn(conversations_dir, assignment, selected)
            selection["trajectory_seed"] = {
                "text": seed["text"],
                "source_path": seed["source_path"],
                "source_turn": seed["source_turn"],
            }
        selections.append(selection)
    output_dir = config.output_dir / "trajectory_seeded_repeated_weak_attack_convos"
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
    rounds: int | None,
    model_cache: Path | None,
    attacker_model_path: Path | None,
    response_model_path: Path | None,
) -> None:
    config = load_config(config_path)
    if (
        bool(config.raw.get("conversation", {}).get("require_cuda", True))
        and not torch.cuda.is_available()
    ):
        raise SystemExit("CUDA is required but torch.cuda.is_available() is false")

    assignments_path = config.output_dir / "planning" / "strategy_assignments.jsonl"
    if not assignments_path.exists():
        raise SystemExit(f"Missing planning assignments: {assignments_path}")
    assignments = selected_assignments(load_jsonl(assignments_path), limit, ids)
    output_dir = config.output_dir / "trajectory_seeded_repeated_weak_attack_convos"
    done = completed_ids(output_dir) if resume else set()
    assignments = [row for row in assignments if str(row["attack_id"]) not in done]
    print(
        f"Repeated weak-attack assignments: {len(assignments)} remaining; "
        f"{len(done)} completed"
    )

    action_cag = load_json(config.raw["paths"]["action_cag"])
    descriptions = action_descriptions(action_cag)
    phases = action_phases(action_cag)
    conversations_dir = config.output_dir / "conversations"
    attacker_system = read_text("CAA/prompts/attacker_system.md")
    attacker_template = read_text("CAA/prompts/attacker_turn_user_template.md")
    response_system = read_text(config.raw["response_model"]["system_prompt"])
    # Copy these mappings because CLI overrides are runtime-only and should
    # not mutate the loaded experiment configuration.
    attacker_cfg = portable_model_config(
        config.raw["attacker_model"], attacker_model_path, "attacker"
    )
    response_cfg = portable_model_config(
        config.raw["response_model"], response_model_path, "response"
    )
    cache_dir = (
        expanded_path(model_cache)
        if model_cache is not None
        else model_cache_path(config.raw)
    )

    print("Runtime:", json.dumps(runtime_summary(), ensure_ascii=False))
    print(f"Model cache: {cache_dir}")

    print(f"Loading attacker: {attacker_cfg['model_id']}")
    attacker_tokenizer, attacker_model, attacker_source = load_local_model(
        attacker_cfg, cache_dir
    )
    print(f"Loading response: {response_cfg['model_id']}")
    response_tokenizer, response_model, response_source = load_local_model(
        response_cfg, cache_dir
    )
    if torch.cuda.is_available():
        print(
            "CUDA after loading both models:",
            f"allocated={torch.cuda.memory_allocated() / 1024**3:.2f}GB",
            f"reserved={torch.cuda.memory_reserved() / 1024**3:.2f}GB",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for assignment in track(assignments, description="Executing repeated weak attacks"):
        selected = select_weak_attack_action(assignment, phases)
        repeat_count = attack_round_count(selected, rounds)
        repeated_assignment = {
            **assignment,
            "action_trajectory_list": [selected["action"]] * repeat_count,
        }
        turns: list[dict[str, Any]] = []
        recent_topics: list[str] = []
        first_attack: tuple[str, dict[str, Any]] | None = None
        seed = (
            trajectory_seed_turn(conversations_dir, assignment, selected)
            if attack_generation == "trajectory_seeded"
            else None
        )
        started = time.time()

        for attack_round in range(1, repeat_count + 1):
            if attack_generation == "trajectory_seeded" and attack_round == 1:
                assert seed is not None
                raw_attack = seed["attacker_raw"]
                attack_obj = {
                    "student_message": seed["text"],
                    "planned_action": selected["action"],
                    "rationale": seed["attacker_rationale"],
                    "parse_fallback": seed["attacker_parse_fallback"],
                    "topic": seed["topic"],
                }
                if seed["topic"]:
                    recent_topics.append(seed["topic"])
                attack_origin = "trajectory"
            elif attack_generation == "replay" and first_attack is not None:
                raw_attack, attack_obj = first_attack
                attack_origin = "replayed"
            else:
                prompt = render_attacker_prompt(
                    system_prompt=attacker_system,
                    user_template=attacker_template,
                    assignment=repeated_assignment,
                    action=selected["action"],
                    action_index=attack_round,
                    action_count=repeat_count,
                    action_description=descriptions.get(selected["action"], ""),
                    turns=[
                        {"speaker": turn["speaker"], "text": turn["text"]}
                        for turn in turns
                    ],
                    recent_topics=recent_topics,
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
                if attack_obj.get("topic"):
                    recent_topics.append(str(attack_obj["topic"]))
                if attack_generation == "replay" and first_attack is None:
                    first_attack = (raw_attack, attack_obj)
                attack_origin = "generated"

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
                    "attack_origin": attack_origin,
                    "replayed": attack_generation == "replay" and attack_round > 1,
                    "trajectory_source_path": (
                        seed["source_path"] if attack_round == 1 and seed else ""
                    ),
                    "trajectory_source_turn": (
                        seed["source_turn"] if attack_round == 1 and seed else None
                    ),
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
            "source_action_count": selected["action_count"],
            "action_count": repeat_count,
            "trajectory_seed": (
                {
                    "source_path": seed["source_path"],
                    "source_turn": seed["source_turn"],
                    "text": seed["text"],
                }
                if seed
                else None
            ),
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
        "--rounds",
        type=int,
        help=(
            "Number of Student/Steve attack rounds. By default, repeat the selected "
            "single action for the length of the source action trajectory."
        ),
    )
    parser.add_argument(
        "--model-cache",
        type=Path,
        help="Linux Hugging Face cache root; overrides paths.model_cache for this run.",
    )
    parser.add_argument(
        "--attacker-model-path",
        type=Path,
        help="Optional local attacker model directory on the DGX Spark.",
    )
    parser.add_argument(
        "--response-model-path",
        type=Path,
        help="Optional local response model directory on the DGX Spark.",
    )
    parser.add_argument(
        "--attack-generation",
        choices=("trajectory_seeded", "regenerate", "replay"),
        default="trajectory_seeded",
        help=(
            "trajectory_seeded copies the matching original trajectory turn for round 1 "
            "and generates context-aware variants thereafter; regenerate creates a new "
            "context-aware message every round; replay generates once and repeats that "
            "message verbatim"
        ),
    )
    args = parser.parse_args()
    if args.execute == args.dry_run:
        raise SystemExit("Choose exactly one of --dry-run or --execute")
    if args.rounds is not None and args.rounds < 1:
        parser.error("--rounds must be at least 1")
    if args.execute:
        execute(
            args.config,
            args.limit,
            args.ids,
            args.resume,
            args.attack_generation,
            args.rounds,
            args.model_cache,
            args.attacker_model_path,
            args.response_model_path,
        )
    else:
        dry_run(
            args.config,
            args.limit,
            args.ids,
            args.attack_generation,
            args.rounds,
        )


if __name__ == "__main__":
    main()
