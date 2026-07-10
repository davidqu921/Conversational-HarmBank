from __future__ import annotations

import argparse
import csv
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from CAA.scripts.caa_common import (
    ATTEMPTS,
    attempts_for_record,
    load_config,
    load_json,
    load_jsonl,
    resolve_project_path,
    sequence_key,
    severity_rank,
    write_csv,
    write_json,
    write_jsonl,
)


def load_schedule(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    return data["schedule"]


def transition_lookup(action_cag: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {edge["transition"]: edge for edge in action_cag.get("edges", [])}


def node_lookup(action_cag: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in action_cag.get("nodes", [])}


def record_matches_attempt(record: dict[str, Any], attempt: str) -> bool:
    return attempt in attempts_for_record(record)


def candidate_score(
    record: dict[str, Any],
    edge_by_transition: dict[str, dict[str, Any]],
    used_trajectories: Counter,
    max_turns: int,
) -> float:
    actions = [str(item) for item in record.get("action_trajectory", []) if str(item).strip()]
    if not actions:
        return -999.0

    edge_score = 0.0
    edge_count = 0
    for source, target in zip(actions, actions[1:]):
        edge = edge_by_transition.get(f"{source} -> {target}")
        if not edge:
            continue
        edge_score += float(edge.get("success_lift", 0)) + float(edge.get("success_rate", 0))
        edge_score += math.log1p(float(edge.get("success_count", 0))) * 0.2
        edge_count += 1
    if edge_count:
        edge_score /= edge_count

    severity_bonus = severity_rank(record) * 0.35
    length_penalty = abs(len(actions) - min(max_turns, len(actions))) * 0.03
    diversity_penalty = used_trajectories[sequence_key(actions)] * 0.75
    source_bonus = 0.25 if record.get("source_pool") == "success_attack" else 0.0
    return edge_score + severity_bonus + source_bonus - length_penalty - diversity_penalty


def pick_weighted(candidates: list[tuple[dict[str, Any], float]], rng: random.Random, temperature: float) -> dict[str, Any]:
    if not candidates:
        raise ValueError("no candidates")
    max_score = max(score for _, score in candidates)
    temp = max(temperature, 0.05)
    weights = [math.exp((score - max_score) / temp) for _, score in candidates]
    total = sum(weights)
    point = rng.random() * total
    seen = 0.0
    for (record, _), weight in zip(candidates, weights):
        seen += weight
        if seen >= point:
            return record
    return candidates[-1][0]


def best_cag_walk(
    attempt: str,
    action_cag: dict[str, Any],
    rng: random.Random,
    max_turns: int,
) -> list[str]:
    edges = [
        edge for edge in action_cag.get("edges", [])
        if attempt in (edge.get("attempt_targets") or {})
        and int(edge.get("success_count", 0)) > 0
    ]
    edges.sort(key=lambda edge: (-float(edge.get("success_lift", 0)), -int(edge.get("success_count", 0)), edge["transition"]))
    if not edges:
        return []
    start = rng.choice(edges[: min(8, len(edges))])
    path = [start["source"], start["target"]]
    current = start["target"]
    while len(path) < max_turns:
        next_edges = [
            edge for edge in edges
            if edge["source"] == current and edge["target"] not in path[-2:]
        ]
        if not next_edges:
            break
        next_edges.sort(key=lambda edge: (-float(edge.get("success_lift", 0)), -int(edge.get("success_count", 0)), edge["transition"]))
        edge = rng.choice(next_edges[: min(3, len(next_edges))])
        path.append(edge["target"])
        current = edge["target"]
    return path


def action_phase_trajectory(actions: list[str], nodes: dict[str, dict[str, Any]]) -> list[str]:
    phases: list[str] = []
    for action in actions:
        phase = str(nodes.get(action, {}).get("phase", "")).strip()
        if phase and (not phases or phases[-1] != phase):
            phases.append(phase)
    return phases


def extension_action_pool(attempt: str, last_action: str) -> list[str]:
    if attempt in {"General Break", "Leak Information"}:
        goal_actions = ["System Prompt Extraction", "Safety Override Request", "Persistence After Refusal"]
    elif attempt == "Break Character":
        goal_actions = ["Roleplay Setup", "Safety Override Request", "Persistence After Refusal"]
    else:
        goal_actions = ["Restricted Content Request", "Persistence After Refusal", "Response Format Control"]

    pool = [last_action] if last_action else []
    for action in goal_actions:
        if action not in pool:
            pool.append(action)
    return pool


def extend_short_path(actions: list[str], attempt: str, target_turns: int) -> list[str]:
    if not actions:
        return actions
    extended = actions[:]
    pool = extension_action_pool(attempt, extended[-1])
    pool_index = 0
    while len(extended) < target_turns:
        extended.append(pool[pool_index % len(pool)])
        pool_index += 1
    return extended


def finalize_action_path(
    actions: list[str],
    attempt: str,
    rng: random.Random,
    max_turns: int,
    sampling_cfg: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    original_count = len(actions)
    actions = actions[:max_turns]
    randomized = False

    if bool(sampling_cfg.get("randomize_action_count", False)):
        min_count = int(sampling_cfg.get("min_sampled_action_count", 3))
        if len(actions) > min_count:
            target_count = rng.randint(min_count, len(actions))
            actions = actions[:target_count]
            randomized = True

    short_threshold = int(sampling_cfg.get("short_path_extension_threshold", 0))
    extension_min_turns = int(sampling_cfg.get("short_path_extension_min_turns", 0))
    extension_applied = False
    extension_target = len(actions)
    if short_threshold > 0 and extension_min_turns > 0 and 0 < len(actions) <= short_threshold:
        extension_target = min(max_turns, extension_min_turns)
        if len(actions) < extension_target:
            actions = extend_short_path(actions, attempt, extension_target)
            extension_applied = True

    metadata = {
        "source_action_count": original_count,
        "randomized_action_count": randomized,
        "path_extension_applied": extension_applied,
        "path_extension_target_turns": extension_target if extension_applied else "",
    }
    return actions, metadata


def source_examples(record: dict[str, Any], max_examples: int = 10) -> list[dict[str, Any]]:
    """Select examples that preserve tactic strength, not just early setup.

    Earlier versions used the first N CAB turns, which overrepresented benign
    setup. This keeps first examples for each planned action and also includes
    tail turns, where successful CAB conversations often become more concrete.
    """
    turns = list(record.get("turns", []))
    if not turns:
        return []

    selected: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    action_trajectory = [str(action) for action in record.get("action_trajectory", []) if str(action).strip()]
    for planned_action in action_trajectory:
        if planned_action in seen_actions:
            continue
        match = next((turn for turn in turns if str(turn.get("action", "")) == planned_action), None)
        if match:
            selected.append(match)
            seen_actions.add(planned_action)

    for turn in turns[-max_examples:]:
        if turn not in selected:
            selected.append(turn)
        if len(selected) >= max_examples:
            break

    selected.sort(key=lambda turn: int(turn.get("turn", 0)) if str(turn.get("turn", "")).isdigit() else 9999)
    examples = []
    for turn in selected[:max_examples]:
        examples.append({
            "turn": turn.get("turn"),
            "phase": turn.get("phase", ""),
            "action": turn.get("action", ""),
            "text": turn.get("text", ""),
        })
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample CAB/CAG strategy assignments for a CAA experiment.")
    parser.add_argument("--config", type=Path, default=Path("CAA/configs/round5_balanced_40.yaml"))
    parser.add_argument("--schedule", type=Path, help="attempt_schedule.json. Defaults to experiment output.")
    args = parser.parse_args()

    config = load_config(args.config)
    rng = random.Random(config.seed + 101)
    out_dir = config.output_dir / "planning"
    schedule_path = args.schedule or out_dir / "attempt_schedule.json"
    schedule = load_schedule(schedule_path)

    records = load_jsonl(config.raw["paths"]["turn_action_bank"])
    success_records = [record for record in records if record.get("source_pool") == "success_attack"]
    action_cag = load_json(config.raw["paths"]["action_cag"])
    edge_by_transition = transition_lookup(action_cag)
    nodes = node_lookup(action_cag)
    max_turns = int(config.raw.get("conversation", {}).get("max_attacker_turns", config.raw.get("max_attacker_turns", 15)))
    top_k = int(config.raw.get("sampling", {}).get("top_k_trajectories", 20))
    temperature = float(config.raw.get("sampling", {}).get("trajectory_temperature", 0.7))
    prefer_nonzero = bool(config.raw.get("sampling", {}).get("prefer_nonzero_severity", True))
    sampling_cfg = config.raw.get("sampling", {})

    by_attempt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in success_records:
        for attempt in attempts_for_record(record):
            if attempt in ATTEMPTS:
                by_attempt[attempt].append(record)

    used_trajectories: Counter = Counter()
    assignments: list[dict[str, Any]] = []
    assignment_jsonl: list[dict[str, Any]] = []
    for row in schedule:
        attempt = row["attempt"]
        pool = by_attempt.get(attempt, [])
        if prefer_nonzero:
            nonzero = [record for record in pool if severity_rank(record) > 0]
            if nonzero:
                pool = nonzero

        candidates = [
            (record, candidate_score(record, edge_by_transition, used_trajectories, max_turns))
            for record in pool
            if record.get("action_trajectory")
        ]
        candidates.sort(key=lambda item: (-item[1], str(item[0].get("conversation_id", ""))))
        selected: dict[str, Any] | None = None
        fallback = False
        if candidates:
            selected = pick_weighted(candidates[:top_k], rng, temperature)
            action_trajectory = [str(item) for item in selected.get("action_trajectory", []) if str(item).strip()]
            action_trajectory, path_metadata = finalize_action_path(
                actions=action_trajectory,
                attempt=attempt,
                rng=rng,
                max_turns=max_turns,
                sampling_cfg=sampling_cfg,
            )
            phase_trajectory = action_phase_trajectory(action_trajectory, nodes)
            source_ids = [str(selected.get("conversation_id", ""))]
            examples = source_examples(selected)
            source_severity = selected.get("severity", "")
            source_primary = selected.get("primary_attack_vector", "")
        else:
            fallback = True
            action_trajectory = best_cag_walk(attempt, action_cag, rng, max_turns)
            action_trajectory, path_metadata = finalize_action_path(
                actions=action_trajectory,
                attempt=attempt,
                rng=rng,
                max_turns=max_turns,
                sampling_cfg=sampling_cfg,
            )
            phase_trajectory = action_phase_trajectory(action_trajectory, nodes)
            source_ids = []
            examples = []
            source_severity = ""
            source_primary = ""

        used_trajectories[sequence_key(action_trajectory)] += 1
        assignment = {
            "attack_index": row["attack_index"],
            "attack_id": row["attack_id"],
            "experiment_id": config.experiment_id,
            "seed": config.seed,
            "attempt": attempt,
            "attempt_quota_index": row["attempt_quota_index"],
            "phase_trajectory": sequence_key(phase_trajectory),
            "action_trajectory": sequence_key(action_trajectory),
            "action_count": len(action_trajectory),
            "source_action_count": path_metadata["source_action_count"],
            "randomized_action_count": path_metadata["randomized_action_count"],
            "path_extension_applied": path_metadata["path_extension_applied"],
            "path_extension_target_turns": path_metadata["path_extension_target_turns"],
            "source_conversation_ids": ";".join(source_ids),
            "source_severity": source_severity,
            "source_primary_attack_vector": source_primary,
            "fallback_cag_walk": fallback,
            "attacker_model": config.raw["attacker_model"]["model_id"],
            "response_model": config.raw["response_model"]["model_id"],
            "max_attacker_turns": max_turns,
            "status": "planned",
            "stop_reason": "",
        }
        assignments.append(assignment)
        assignment_jsonl.append({
            **assignment,
            "phase_trajectory_list": phase_trajectory,
            "action_trajectory_list": action_trajectory,
            "source_examples": examples,
        })

    write_csv(
        out_dir / "strategy_assignments.csv",
        assignments,
        [
            "attack_index", "attack_id", "experiment_id", "seed", "attempt",
            "attempt_quota_index", "phase_trajectory", "action_trajectory",
            "action_count", "source_conversation_ids", "source_severity",
            "source_action_count", "randomized_action_count",
            "path_extension_applied", "path_extension_target_turns",
            "source_primary_attack_vector", "fallback_cag_walk",
            "attacker_model", "response_model", "max_attacker_turns",
            "status", "stop_reason",
        ],
    )
    write_jsonl(out_dir / "strategy_assignments.jsonl", assignment_jsonl)
    write_json(out_dir / "strategy_sampling_summary.json", {
        "experiment_id": config.experiment_id,
        "n_assignments": len(assignments),
        "fallback_count": sum(1 for row in assignments if row["fallback_cag_walk"]),
        "attempt_counts": dict(Counter(row["attempt"] for row in assignments)),
        "unique_action_trajectories": len(set(row["action_trajectory"] for row in assignments)),
    })
    print(f"Wrote {len(assignments)} strategy assignments to {out_dir}")


if __name__ == "__main__":
    main()
