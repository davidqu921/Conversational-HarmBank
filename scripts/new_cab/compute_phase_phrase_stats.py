"""
Compute phase/phrase-only CAB statistics for Round 5 reviewed data.

The script reads raw_cab_round5_reviewed_all/phrase_conversation_bank.jsonl and
writes only phrase-related stats:
  - all_phrase_topk.csv
  - success_phase_action_topk.csv
  - success_phase_trajectory_topk.csv
  - success_phase_transition_topk.csv
  - cab_stats_summary.json
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BANK = PROJECT_ROOT / "raw_cab_round5_reviewed_all" / "phrase_conversation_bank.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab_round5_reviewed_all" / "stats"


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
    return " -> ".join(items)


def selected_records(records: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    if scope == "all":
        return records
    return [record for record in records if record.get("source_pool") == scope]


def phrase_counter(records: list[dict[str, Any]]) -> tuple[Counter, dict[str, set[str]], int]:
    counter: Counter = Counter()
    conversation_sets: dict[str, set[str]] = defaultdict(set)
    total = 0
    for record in records:
        conv_id = str(record.get("conversation_id", ""))
        for phrase in record.get("phrases", []):
            phase = phrase.get("phase", "")
            if not phase:
                continue
            counter[phase] += 1
            conversation_sets[phase].add(conv_id)
            total += 1
    return counter, conversation_sets, total


def compute_all_phrase_topk(records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total_conversations_by_scope = {
        scope: len(selected_records(records, scope))
        for scope in ["all", "success_attack", "unsuccess_attack", "no_attack"]
    }
    for scope in ["all", "success_attack", "unsuccess_attack", "no_attack"]:
        scoped = selected_records(records, scope)
        counter, conversation_sets, total_phrases = phrase_counter(scoped)
        for rank, (phase, count) in enumerate(counter.most_common(top_k), 1):
            conversation_count = len(conversation_sets[phase])
            rows.append({
                "scope": scope,
                "rank": rank,
                "phase": phase,
                "phrase_count": count,
                "proportion_of_phrases": round(count / total_phrases, 6) if total_phrases else 0,
                "conversation_count": conversation_count,
                "proportion_of_conversations": round(conversation_count / total_conversations_by_scope[scope], 6) if total_conversations_by_scope[scope] else 0,
            })
    return rows


def compute_success_phase_action_topk(records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    success_records = [record for record in records if is_success(record)]
    success_ids = {record["conversation_id"] for record in success_records}
    all_counter, all_conversation_sets, _ = phrase_counter(records)
    counter, conversation_sets, total_success_phrases = phrase_counter(success_records)

    rows: list[dict[str, Any]] = []
    for rank, (phase, count) in enumerate(counter.most_common(top_k), 1):
        conversation_count = len(conversation_sets[phase])
        all_conversation_count = len(all_conversation_sets[phase])
        rows.append({
            "scope": "success_attack",
            "rank": rank,
            "phase": phase,
            "action": phase,
            "phrase_count": count,
            "proportion_of_success_phrases": round(count / total_success_phrases, 6) if total_success_phrases else 0,
            "conversation_count": conversation_count,
            "proportion_of_success_conversations": round(conversation_count / len(success_ids), 6) if success_ids else 0,
            "all_phrase_count": all_counter[phase],
            "all_conversation_count": all_conversation_count,
            "success_rate_among_conversations_with_phase": round(conversation_count / all_conversation_count, 6) if all_conversation_count else 0,
        })
    return rows


def compute_phase_trajectory_topk(records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    success_records = [record for record in records if is_success(record)]
    success_ids = {record["conversation_id"] for record in success_records}
    all_conversation_sets: dict[str, set[str]] = defaultdict(set)
    success_conversation_sets: dict[str, set[str]] = defaultdict(set)

    for record in records:
        trajectory = sequence_key(record.get("phase_trajectory", []))
        if not trajectory:
            continue
        conv_id = str(record.get("conversation_id", ""))
        all_conversation_sets[trajectory].add(conv_id)
        if is_success(record):
            success_conversation_sets[trajectory].add(conv_id)

    counter = Counter(sequence_key(record.get("phase_trajectory", [])) for record in success_records)
    counter.pop("", None)
    rows: list[dict[str, Any]] = []
    for rank, (trajectory, count) in enumerate(counter.most_common(top_k), 1):
        all_conversation_count = len(all_conversation_sets[trajectory])
        success_conversation_count = len(success_conversation_sets[trajectory])
        rows.append({
            "scope": "success_attack",
            "rank": rank,
            "phase_trajectory": trajectory,
            "count": count,
            "proportion_of_success_trajectories": round(count / len(success_records), 6) if success_records else 0,
            "conversation_count": count,
            "proportion_of_success_conversations": round(count / len(success_ids), 6) if success_ids else 0,
            "all_conversation_count": all_conversation_count,
            "success_rate_among_conversations_with_pattern": round(success_conversation_count / all_conversation_count, 6) if all_conversation_count else 0,
        })
    return rows


def transition_counts(records: list[dict[str, Any]]) -> tuple[Counter, Counter, dict[tuple[str, str], set[str]], int]:
    counter: Counter = Counter()
    outgoing: Counter = Counter()
    conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    total = 0
    for record in records:
        conv_id = str(record.get("conversation_id", ""))
        trajectory = record.get("phase_trajectory", [])
        for source, target in zip(trajectory, trajectory[1:]):
            counter[(source, target)] += 1
            outgoing[source] += 1
            conversation_sets[(source, target)].add(conv_id)
            total += 1
    return counter, outgoing, conversation_sets, total


def compute_phase_transition_topk(records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    success_records = [record for record in records if is_success(record)]
    success_ids = {record["conversation_id"] for record in success_records}
    all_counter, _, all_conversation_sets, all_total = transition_counts(records)
    counter, outgoing, conversation_sets, success_total = transition_counts(success_records)

    rows: list[dict[str, Any]] = []
    for rank, ((source, target), count) in enumerate(counter.most_common(top_k), 1):
        all_conversation_count = len(all_conversation_sets[(source, target)])
        success_conversation_count = len(conversation_sets[(source, target)])
        rows.append({
            "scope": "success_attack",
            "rank": rank,
            "source": source,
            "target": target,
            "transition": f"{source} -> {target}",
            "count": count,
            "proportion_of_all_transitions": round(count / all_total, 6) if all_total else 0,
            "proportion_of_success_transitions": round(count / success_total, 6) if success_total else 0,
            "conditional_probability": round(count / outgoing[source], 6) if outgoing[source] else 0,
            "conversation_count": success_conversation_count,
            "proportion_of_success_conversations": round(success_conversation_count / len(success_ids), 6) if success_ids else 0,
            "all_transition_count": all_counter[(source, target)],
            "all_conversation_count": all_conversation_count,
            "success_rate_among_conversations_with_pattern": round(success_conversation_count / all_conversation_count, 6) if all_conversation_count else 0,
        })
    return rows


def compute_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts = Counter(record.get("source_pool", "") for record in records)
    severity_counts = Counter(record.get("severity", "") for record in records)
    phrase_counts_by_source = Counter()
    phase_counts_by_source: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        source = record.get("source_pool", "")
        phrase_counts_by_source[source] += len(record.get("phrases", []))
        for phrase in record.get("phrases", []):
            phase_counts_by_source[source][phrase.get("phase", "")] += 1
    mean_phrase_count = round(sum(record.get("phrase_count", 0) for record in records) / len(records), 3) if records else 0
    return {
        "n_conversations": len(records),
        "source_pool_counts": dict(source_counts),
        "severity_counts": dict(severity_counts),
        "phrase_counts_by_source_pool": dict(phrase_counts_by_source),
        "phase_counts_by_source_pool": {
            source: dict(counter)
            for source, counter in sorted(phase_counts_by_source.items())
        },
        "mean_phrase_trajectory_length": mean_phrase_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute phase/phrase-only CAB statistics.")
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--top-k", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_bank(args.bank)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(
        args.out_dir / "all_phrase_topk.csv",
        compute_all_phrase_topk(records, args.top_k),
        ["scope", "rank", "phase", "phrase_count", "proportion_of_phrases", "conversation_count", "proportion_of_conversations"],
    )
    write_csv(
        args.out_dir / "success_phase_action_topk.csv",
        compute_success_phase_action_topk(records, args.top_k),
        [
            "scope", "rank", "phase", "action", "phrase_count", "proportion_of_success_phrases",
            "conversation_count", "proportion_of_success_conversations", "all_phrase_count",
            "all_conversation_count", "success_rate_among_conversations_with_phase",
        ],
    )
    write_csv(
        args.out_dir / "success_phase_trajectory_topk.csv",
        compute_phase_trajectory_topk(records, args.top_k),
        [
            "scope", "rank", "phase_trajectory", "count", "proportion_of_success_trajectories",
            "conversation_count", "proportion_of_success_conversations", "all_conversation_count",
            "success_rate_among_conversations_with_pattern",
        ],
    )
    write_csv(
        args.out_dir / "success_phase_transition_topk.csv",
        compute_phase_transition_topk(records, args.top_k),
        [
            "scope", "rank", "source", "target", "transition", "count",
            "proportion_of_all_transitions", "proportion_of_success_transitions",
            "conditional_probability", "conversation_count", "proportion_of_success_conversations",
            "all_transition_count", "all_conversation_count", "success_rate_among_conversations_with_pattern",
        ],
    )
    write_json(args.out_dir / "cab_stats_summary.json", compute_summary(records))

    print(f"Loaded {len(records)} phrase CAB records from {args.bank}")
    print(f"Wrote phase/phrase stats to {args.out_dir}")


if __name__ == "__main__":
    main()
