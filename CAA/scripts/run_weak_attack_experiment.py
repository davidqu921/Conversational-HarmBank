from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

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


PHASE_PRIORITY = (
    "Goal Execution",
    "Attack Construction",
    "Escalation",
    "Trust Building",
    "Setup",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def action_phases(action_cag: dict[str, Any]) -> dict[str, str]:
    return {
        str(node["id"]): str(node.get("phase", "")).strip()
        for node in action_cag.get("nodes", [])
    }


def select_weak_attack_action(
    assignment: dict[str, Any],
    phase_by_action: dict[str, str],
) -> dict[str, Any]:
    actions = [str(item) for item in assignment.get("action_trajectory_list", [])]
    if not actions:
        raise ValueError(f"{assignment.get('attack_id')}: empty action trajectory")

    unknown = [action for action in actions if not phase_by_action.get(action)]
    if unknown:
        raise ValueError(
            f"{assignment.get('attack_id')}: actions missing canonical phase: {unknown}"
        )

    for phase in PHASE_PRIORITY:
        for index in range(len(actions) - 1, -1, -1):
            action = actions[index]
            if phase_by_action[action] == phase:
                return {
                    "phase": phase,
                    "action": action,
                    "action_index": index + 1,
                    "action_count": len(actions),
                }
    raise ValueError(f"{assignment.get('attack_id')}: no action matched phase priority")


def selected_assignments(
    assignments: list[dict[str, Any]],
    limit: int | None,
    ids: list[str] | None,
) -> list[dict[str, Any]]:
    if ids:
        wanted = set(ids)
        assignments = [row for row in assignments if str(row.get("attack_id")) in wanted]
    if limit is not None:
        assignments = assignments[:limit]
    return assignments


def completed_ids(output_dir: Path) -> set[str]:
    done: set[str] = set()
    if not output_dir.exists():
        return done
    for path in output_dir.glob("caa_*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if row.get("status") == "completed":
            done.add(str(row.get("attack_id", path.stem)))
    return done


def write_aggregate_outputs(output_dir: Path) -> None:
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
    write_json(output_dir / "run_summary.json", {
        "experiment_id": conversations[0]["experiment_id"] if conversations else "",
        "mode": "single_priority_phase_attack",
        "phase_priority": list(PHASE_PRIORITY),
        "n_conversations": len(conversations),
        "selected_phase_counts": phase_counts,
    })


def dry_run(config_path: Path, limit: int | None, ids: list[str] | None) -> None:
    config = load_config(config_path)
    assignments_path = config.output_dir / "planning" / "strategy_assignments.jsonl"
    if not assignments_path.exists():
        raise SystemExit(f"Missing planning assignments: {assignments_path}")
    assignments = selected_assignments(load_jsonl(assignments_path), limit, ids)
    action_cag = load_json(config.raw["paths"]["action_cag"])
    phases = action_phases(action_cag)
    selections = [
        {
            "attack_id": row["attack_id"],
            "attempt": row["attempt"],
            "topic_seed": row.get("topic_seed", {}),
            **select_weak_attack_action(row, phases),
        }
        for row in assignments
    ]
    output_dir = config.output_dir / "weak_attack_convos"
    write_jsonl(output_dir / "dry_run_selections.jsonl", selections)
    print(f"Selected {len(selections)} weak-attack turns -> {output_dir / 'dry_run_selections.jsonl'}")


def execute(
    config_path: Path,
    limit: int | None,
    ids: list[str] | None,
    resume: bool,
) -> None:
    config = load_config(config_path)
    if bool(config.raw.get("conversation", {}).get("require_cuda", True)) and not torch.cuda.is_available():
        raise SystemExit("CUDA is required but torch.cuda.is_available() is false")

    assignments_path = config.output_dir / "planning" / "strategy_assignments.jsonl"
    if not assignments_path.exists():
        raise SystemExit(f"Missing planning assignments: {assignments_path}")
    assignments = selected_assignments(load_jsonl(assignments_path), limit, ids)
    output_dir = config.output_dir / "weak_attack_convos"
    done = completed_ids(output_dir) if resume else set()
    assignments = [row for row in assignments if str(row["attack_id"]) not in done]
    print(f"Weak-attack assignments: {len(assignments)} remaining; {len(done)} completed")

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
    attacker_tokenizer, attacker_model, attacker_source = load_local_model(attacker_cfg["model_id"], cache_dir)
    print(f"Loading response: {response_cfg['model_id']}")
    response_tokenizer, response_model, response_source = load_local_model(response_cfg["model_id"], cache_dir)
    if torch.cuda.is_available():
        print(
            "CUDA after loading both models:",
            f"allocated={torch.cuda.memory_allocated() / 1024**3:.2f}GB",
            f"reserved={torch.cuda.memory_reserved() / 1024**3:.2f}GB",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for assignment in track(assignments, description="Executing weak attacks"):
        selected = select_weak_attack_action(assignment, phases)
        prompt = render_attacker_prompt(
            system_prompt=attacker_system,
            user_template=attacker_template,
            assignment=assignment,
            action=selected["action"],
            action_index=selected["action_index"],
            action_count=selected["action_count"],
            action_description=descriptions.get(selected["action"], ""),
            turns=[],
            recent_topics=[],
        )
        started = time.time()
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
        student_text = str(attack_obj.get("student_message", "")).strip()
        if not student_text:
            raise RuntimeError(f"{assignment['attack_id']}: attacker generated an empty message")
        turns: list[dict[str, Any]] = [{
            "turn": 1,
            "speaker": "Student",
            "text": student_text,
            "planned_phase": selected["phase"],
            "planned_action": selected["action"],
            "source_action_index": selected["action_index"],
            "attacker_raw": raw_attack,
            "attacker_rationale": attack_obj.get("rationale", ""),
            "attacker_parse_fallback": bool(attack_obj.get("parse_fallback", False)),
        }]
        professor_text = generate_chat(
            response_tokenizer,
            response_model,
            response_messages(response_system, [{"speaker": "Student", "text": student_text}]),
            max_new_tokens=int(response_cfg.get("max_new_tokens", 192)),
            temperature=float(response_cfg.get("temperature", 0.7)),
            top_p=float(response_cfg.get("top_p", 0.9)),
        )
        turns.append({"turn": 2, "speaker": "Steve", "text": professor_text})
        conversation = {
            "attack_id": assignment["attack_id"],
            "experiment_id": assignment["experiment_id"],
            "created_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "attempt": assignment["attempt"],
            "status": "completed",
            "mode": "single_priority_phase_attack",
            "selected_phase": selected["phase"],
            "selected_action": selected["action"],
            "source_action_index": selected["action_index"],
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
                "source_conversation_ids": assignment.get("source_conversation_ids", ""),
                "topic_seed": assignment.get("topic_seed", {}),
            },
            "turns": turns,
        }
        write_json(output_dir / f"{assignment['attack_id']}.json", conversation)
        write_aggregate_outputs(output_dir)

    write_aggregate_outputs(output_dir)
    print(f"Wrote weak-attack outputs to {output_dir}")
    del attacker_model, response_model, attacker_tokenizer, response_tokenizer
    free_memory()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate one priority-phase attack turn per existing CAA assignment."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="*")
    args = parser.parse_args()
    if args.execute == args.dry_run:
        raise SystemExit("Choose exactly one of --dry-run or --execute")
    if args.execute:
        execute(args.config, args.limit, args.ids, args.resume)
    else:
        dry_run(args.config, args.limit, args.ids)


if __name__ == "__main__":
    main()



