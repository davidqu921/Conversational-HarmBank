"""
Compute turn-action-level CAB statistics for Round 5 reviewed data.

The input bank is produced by scripts/new_cab/build_turn_action_bank.py. Outputs
are written to raw_cab_round5_reviewed_all/turn_action_stats by default so they
do not overwrite the phase-only reviewed stats.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BANK = PROJECT_ROOT / "raw_cab_round5_reviewed_all" / "turn_action_conversation_bank.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab_round5_reviewed_all" / "turn_action_stats"


def load_bank(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_success(record: dict[str, Any]) -> bool:
    return record.get("source_pool") == "success_attack"


def sequence_key(items: Iterable[str]) -> str:
    return " -> ".join(str(item) for item in items if str(item).strip())


def selected_records(records: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    if scope == "all":
        return records
    return [record for record in records if record.get("source_pool") == scope]


def ngrams(items: list[str], n: int) -> Iterable[tuple[str, ...]]:
    if n <= 0:
        return
    for idx in range(0, max(0, len(items) - n + 1)):
        yield tuple(items[idx:idx + n])


def top_counter_rows(
    counter: Counter,
    denominator: int,
    label_field: str,
    top_k: int,
    proportion_field: str = "proportion",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, (label, count) in enumerate(counter.most_common(top_k), 1):
        rows.append({
            "rank": rank,
            label_field: label,
            "count": count,
            proportion_field: round(count / denominator, 6) if denominator else 0,
        })
    return rows


def action_counter(records: list[dict[str, Any]]) -> tuple[Counter, dict[str, set[str]], int]:
    counter: Counter = Counter()
    conversation_sets: dict[str, set[str]] = defaultdict(set)
    total = 0
    for record in records:
        conv_id = str(record.get("conversation_id", ""))
        for action in record.get("action_sequence", []):
            if not action:
                continue
            counter[action] += 1
            conversation_sets[action].add(conv_id)
            total += 1
    return counter, conversation_sets, total


def compute_all_action_topk(records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scopes = ["all", "success_attack", "unsuccess_attack", "no_attack"]
    total_conversations = {scope: len(selected_records(records, scope)) for scope in scopes}
    for scope in scopes:
        scoped = selected_records(records, scope)
        counter, conversation_sets, total_actions = action_counter(scoped)
        for rank, (action, count) in enumerate(counter.most_common(top_k), 1):
            conversation_count = len(conversation_sets[action])
            rows.append({
                "scope": scope,
                "rank": rank,
                "action": action,
                "turn_count": count,
                "proportion_of_turns": round(count / total_actions, 6) if total_actions else 0,
                "conversation_count": conversation_count,
                "proportion_of_conversations": round(conversation_count / total_conversations[scope], 6) if total_conversations[scope] else 0,
            })
    return rows


def compute_success_phase_action_topk(records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    success_records = [record for record in records if is_success(record)]
    success_ids = {record["conversation_id"] for record in success_records}
    counters: dict[str, Counter] = defaultdict(Counter)
    phase_totals: Counter = Counter()
    conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    all_conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    success_conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)

    for record in records:
        conv_id = str(record.get("conversation_id", ""))
        for turn in record.get("turns", []):
            phase = str(turn.get("phase", "")).strip()
            action = str(turn.get("action", "")).strip()
            if phase and action:
                all_conversation_sets[(phase, action)].add(conv_id)
                if is_success(record):
                    success_conversation_sets[(phase, action)].add(conv_id)

    for record in success_records:
        conv_id = str(record.get("conversation_id", ""))
        for turn in record.get("turns", []):
            phase = str(turn.get("phase", "")).strip()
            action = str(turn.get("action", "")).strip()
            if not phase or not action:
                continue
            counters[phase][action] += 1
            phase_totals[phase] += 1
            conversation_sets[(phase, action)].add(conv_id)

    rows: list[dict[str, Any]] = []
    for phase in sorted(counters):
        for row in top_counter_rows(counters[phase], phase_totals[phase], "action", top_k):
            action = row["action"]
            conversation_count = len(conversation_sets[(phase, action)])
            all_conversation_count = len(all_conversation_sets[(phase, action)])
            success_conversation_count = len(success_conversation_sets[(phase, action)])
            rows.append({
                "phase": phase,
                "phase_turn_count": phase_totals[phase],
                **row,
                "conversation_count": conversation_count,
                "proportion_of_success_conversations": round(conversation_count / len(success_ids), 6) if success_ids else 0,
                "all_conversation_count": all_conversation_count,
                "success_rate_among_conversations_with_pattern": round(success_conversation_count / all_conversation_count, 6) if all_conversation_count else 0,
            })
    return rows


def compute_trajectory_topk(records: list[dict[str, Any]], top_k: int, field: str, success_only: bool) -> list[dict[str, Any]]:
    selected = [record for record in records if is_success(record) or not success_only]
    success_records = [record for record in records if is_success(record)]
    all_conversation_sets: dict[str, set[str]] = defaultdict(set)
    success_conversation_sets: dict[str, set[str]] = defaultdict(set)
    for record in records:
        key = sequence_key(record.get(field, []))
        if not key:
            continue
        conv_id = str(record.get("conversation_id", ""))
        all_conversation_sets[key].add(conv_id)
        if is_success(record):
            success_conversation_sets[key].add(conv_id)

    counter = Counter(sequence_key(record.get(field, [])) for record in selected)
    counter.pop("", None)
    label = "action_trajectory" if "action" in field else "phase_trajectory"
    rows = top_counter_rows(
        counter,
        len(selected),
        label,
        top_k,
        "proportion_of_success_trajectories" if success_only else "proportion",
    )
    for row in rows:
        row["scope"] = "success_attack" if success_only else "all"
        if success_only:
            key = row[label]
            all_count = len(all_conversation_sets[key])
            success_count = len(success_conversation_sets[key])
            row["conversation_count"] = row["count"]
            row["proportion_of_success_conversations"] = round(row["count"] / len(success_records), 6) if success_records else 0
            row["all_conversation_count"] = all_count
            row["success_rate_among_conversations_with_pattern"] = round(success_count / all_count, 6) if all_count else 0
    return rows


def compute_ngram_topk(records: list[dict[str, Any]], ngram_sizes: list[int], top_k: int, success_only: bool) -> list[dict[str, Any]]:
    selected = [record for record in records if is_success(record) or not success_only]
    success_records = [record for record in records if is_success(record)]
    rows: list[dict[str, Any]] = []
    for n in ngram_sizes:
        counter: Counter = Counter()
        conversation_sets: dict[str, set[str]] = defaultdict(set)
        all_conversation_sets: dict[str, set[str]] = defaultdict(set)
        success_conversation_sets: dict[str, set[str]] = defaultdict(set)
        for record in records:
            conv_id = str(record.get("conversation_id", ""))
            for gram in ngrams(record.get("action_trajectory", []), n):
                key = sequence_key(gram)
                all_conversation_sets[key].add(conv_id)
                if is_success(record):
                    success_conversation_sets[key].add(conv_id)
        total = 0
        for record in selected:
            conv_id = str(record.get("conversation_id", ""))
            for gram in ngrams(record.get("action_trajectory", []), n):
                key = sequence_key(gram)
                counter[key] += 1
                conversation_sets[key].add(conv_id)
                total += 1
        for row in top_counter_rows(
            counter,
            total,
            "action_ngram",
            top_k,
            "proportion_of_success_ngrams" if success_only else "proportion",
        ):
            out = {"scope": "success_attack" if success_only else "all", "n": n, **row}
            if success_only:
                key = row["action_ngram"]
                conversation_count = len(conversation_sets[key])
                all_count = len(all_conversation_sets[key])
                success_count = len(success_conversation_sets[key])
                out["conversation_count"] = conversation_count
                out["proportion_of_success_conversations"] = round(conversation_count / len(success_records), 6) if success_records else 0
                out["all_conversation_count"] = all_count
                out["success_rate_among_conversations_with_pattern"] = round(success_count / all_count, 6) if all_count else 0
            rows.append(out)
    return rows


def compute_transition_topk(records: list[dict[str, Any]], top_k: int, field: str, success_only: bool) -> list[dict[str, Any]]:
    selected = [record for record in records if is_success(record) or not success_only]
    success_records = [record for record in records if is_success(record)]
    counter: Counter = Counter()
    outgoing: Counter = Counter()
    conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    all_conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    success_conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)

    for record in records:
        conv_id = str(record.get("conversation_id", ""))
        trajectory = record.get(field, [])
        for source, target in zip(trajectory, trajectory[1:]):
            all_conversation_sets[(source, target)].add(conv_id)
            if is_success(record):
                success_conversation_sets[(source, target)].add(conv_id)

    selected_total = 0
    for record in selected:
        conv_id = str(record.get("conversation_id", ""))
        trajectory = record.get(field, [])
        for source, target in zip(trajectory, trajectory[1:]):
            counter[(source, target)] += 1
            outgoing[source] += 1
            conversation_sets[(source, target)].add(conv_id)
            selected_total += 1

    all_total = sum(max(0, len(record.get(field, [])) - 1) for record in records)
    rows: list[dict[str, Any]] = []
    for rank, ((source, target), count) in enumerate(counter.most_common(top_k), 1):
        row = {
            "scope": "success_attack" if success_only else "all",
            "rank": rank,
            "source": source,
            "target": target,
            "transition": f"{source} -> {target}",
            "count": count,
            "proportion_of_all_transitions": round(count / all_total, 6) if all_total else 0,
            "proportion_of_success_transitions": round(count / selected_total, 6) if success_only and selected_total else "",
            "conditional_probability": round(count / outgoing[source], 6) if outgoing[source] else 0,
        }
        if success_only:
            conversation_count = len(conversation_sets[(source, target)])
            all_count = len(all_conversation_sets[(source, target)])
            success_count = len(success_conversation_sets[(source, target)])
            row["conversation_count"] = conversation_count
            row["proportion_of_success_conversations"] = round(conversation_count / len(success_records), 6) if success_records else 0
            row["all_conversation_count"] = all_count
            row["success_rate_among_conversations_with_pattern"] = round(success_count / all_count, 6) if all_count else 0
        rows.append(row)
    return rows


def compute_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts = Counter(record.get("source_pool", "") for record in records)
    severity_counts = Counter(record.get("severity", "") for record in records)
    validation_counts = Counter(record.get("validation_status", "") for record in records if is_success(record))
    issue_count = sum(1 for record in records if is_success(record) and record.get("turn_coverage_issue"))
    action_counts_by_source: dict[str, Counter] = defaultdict(Counter)
    phase_action_counts_by_source: dict[str, Counter] = defaultdict(Counter)
    attempt_counts: Counter = Counter()
    for record in records:
        source = record.get("source_pool", "")
        for action in record.get("action_sequence", []):
            action_counts_by_source[source][action] += 1
        for turn in record.get("turns", []):
            phase = str(turn.get("phase", "")).strip()
            action = str(turn.get("action", "")).strip()
            if phase and action:
                phase_action_counts_by_source[source][f"{phase} :: {action}"] += 1
        for attempt in record.get("attempt_type", []):
            attempt_counts[attempt] += 1

    return {
        "n_conversations": len(records),
        "source_pool_counts": dict(source_counts),
        "severity_counts": dict(severity_counts),
        "attempt_type_counts": dict(attempt_counts),
        "success_fillback_validation_status_counts": dict(validation_counts),
        "success_turn_coverage_issue_count": issue_count,
        "turn_counts_by_source_pool": {
            source: sum(counter.values())
            for source, counter in sorted(action_counts_by_source.items())
        },
        "mean_raw_action_trajectory_length": round(sum(record.get("raw_action_trajectory_length", 0) for record in records) / len(records), 3) if records else 0,
        "mean_action_trajectory_length": round(sum(record.get("action_trajectory_length", 0) for record in records) / len(records), 3) if records else 0,
        "top_actions_by_source_pool": {
            source: dict(counter.most_common(20))
            for source, counter in sorted(action_counts_by_source.items())
        },
        "top_phase_actions_by_source_pool": {
            source: dict(counter.most_common(20))
            for source, counter in sorted(phase_action_counts_by_source.items())
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute turn-action-level CAB statistics.")
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--ngram-sizes", nargs="+", type=int, default=[2, 3, 4])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_bank(args.bank)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, tuple[list[dict[str, Any]], list[str]]] = {
        "all_action_topk.csv": (
            compute_all_action_topk(records, args.top_k),
            ["scope", "rank", "action", "turn_count", "proportion_of_turns", "conversation_count", "proportion_of_conversations"],
        ),
        "success_phase_action_topk.csv": (
            compute_success_phase_action_topk(records, args.top_k),
            [
                "phase", "phase_turn_count", "rank", "action", "count", "proportion",
                "conversation_count", "proportion_of_success_conversations",
                "all_conversation_count", "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_action_trajectory_topk.csv": (
            compute_trajectory_topk(records, args.top_k, "action_trajectory", success_only=True),
            [
                "scope", "rank", "action_trajectory", "count",
                "proportion_of_success_trajectories", "conversation_count",
                "proportion_of_success_conversations", "all_conversation_count",
                "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_action_ngram_topk.csv": (
            compute_ngram_topk(records, args.ngram_sizes, args.top_k, success_only=True),
            [
                "scope", "n", "rank", "action_ngram", "count",
                "proportion_of_success_ngrams", "conversation_count",
                "proportion_of_success_conversations", "all_conversation_count",
                "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_action_transition_topk.csv": (
            compute_transition_topk(records, args.top_k, "action_trajectory", success_only=True),
            [
                "scope", "rank", "source", "target", "transition", "count",
                "proportion_of_all_transitions", "proportion_of_success_transitions",
                "conditional_probability", "conversation_count", "proportion_of_success_conversations",
                "all_conversation_count", "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_raw_action_transition_topk.csv": (
            compute_transition_topk(records, args.top_k, "action_sequence", success_only=True),
            [
                "scope", "rank", "source", "target", "transition", "count",
                "proportion_of_all_transitions", "proportion_of_success_transitions",
                "conditional_probability", "conversation_count", "proportion_of_success_conversations",
                "all_conversation_count", "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_phase_trajectory_topk.csv": (
            compute_trajectory_topk(records, args.top_k, "phase_trajectory", success_only=True),
            [
                "scope", "rank", "phase_trajectory", "count",
                "proportion_of_success_trajectories", "conversation_count",
                "proportion_of_success_conversations", "all_conversation_count",
                "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_phase_transition_topk.csv": (
            compute_transition_topk(records, args.top_k, "phase_trajectory", success_only=True),
            [
                "scope", "rank", "source", "target", "transition", "count",
                "proportion_of_all_transitions", "proportion_of_success_transitions",
                "conditional_probability", "conversation_count", "proportion_of_success_conversations",
                "all_conversation_count", "success_rate_among_conversations_with_pattern",
            ],
        ),
        "all_action_transition_topk.csv": (
            compute_transition_topk(records, args.top_k, "action_trajectory", success_only=False),
            ["scope", "rank", "source", "target", "transition", "count", "proportion_of_all_transitions", "conditional_probability"],
        ),
        "all_raw_action_transition_topk.csv": (
            compute_transition_topk(records, args.top_k, "action_sequence", success_only=False),
            ["scope", "rank", "source", "target", "transition", "count", "proportion_of_all_transitions", "conditional_probability"],
        ),
    }
    for filename, (rows, fieldnames) in outputs.items():
        write_csv(args.out_dir / filename, rows, fieldnames)

    write_json(args.out_dir / "turn_action_stats_summary.json", compute_summary(records))

    print(f"Loaded {len(records)} turn-action CAB records from {args.bank}")
    print(f"Wrote turn-action stats to {args.out_dir}")


if __name__ == "__main__":
    main()
