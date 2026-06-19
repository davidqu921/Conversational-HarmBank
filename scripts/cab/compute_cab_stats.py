"""
Compute descriptive statistics from the Conversation Attack Bank (CAB).

The script is designed to support Conversation Attack Graph (CAG) design by
summarizing common actions, trajectories, and transitions.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAB = PROJECT_ROOT / "raw_cab" / "conversation_attack_bank.jsonl"
DEFAULT_SEG_RESULTS = PROJECT_ROOT / "conversation_seg" / "results_2"
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab" / "stats"


def load_cab(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_success_attack(record: dict[str, Any]) -> bool:
    return record.get("source_pool") == "success_attack"


def sequence_key(items: Iterable[str]) -> str:
    return " -> ".join(items)


def ngrams(items: list[str], n: int) -> Iterable[tuple[str, ...]]:
    if n <= 0:
        return
    for i in range(0, max(0, len(items) - n + 1)):
        yield tuple(items[i:i + n])


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


def load_turn_rows(seg_results_dir: Path, keep_ids: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(seg_results_dir.glob("*/turn_segments.csv")):
        source_pool = path.parent.name
        for row in read_csv(path):
            cid = row.get("id", "").strip()
            if cid not in keep_ids:
                continue
            rows.append({
                "id": cid,
                "source_pool": source_pool,
                "turn": row.get("turn", ""),
                "phase": row.get("phase", "").strip(),
                "action": row.get("action", "").strip(),
            })
    return rows


def compute_success_phase_action_topk(records: list[dict[str, Any]], seg_results_dir: Path, top_k: int) -> list[dict[str, Any]]:
    success_ids = {record["conversation_id"] for record in records if is_success_attack(record)}
    all_ids = {record["conversation_id"] for record in records}
    turn_rows = load_turn_rows(seg_results_dir, success_ids)
    all_turn_rows = load_turn_rows(seg_results_dir, all_ids)

    counters: dict[str, Counter] = defaultdict(Counter)
    conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    all_conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    success_conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    totals: Counter = Counter()
    for row in turn_rows:
        phase = row["phase"]
        action = row["action"]
        if not phase or not action:
            continue
        counters[phase][action] += 1
        conversation_sets[(phase, action)].add(row["id"])
        success_conversation_sets[(phase, action)].add(row["id"])
        totals[phase] += 1
    for row in all_turn_rows:
        phase = row["phase"]
        action = row["action"]
        if phase and action:
            all_conversation_sets[(phase, action)].add(row["id"])

    out: list[dict[str, Any]] = []
    for phase in sorted(counters):
        for row in top_counter_rows(counters[phase], totals[phase], "action", top_k):
            conversation_count = len(conversation_sets[(phase, row["action"])])
            all_conversation_count = len(all_conversation_sets[(phase, row["action"])])
            success_conversation_count = len(success_conversation_sets[(phase, row["action"])])
            out.append({
                "phase": phase,
                "phase_turn_count": totals[phase],
                **row,
                "conversation_count": conversation_count,
                "proportion_of_success_conversations": round(conversation_count / len(success_ids), 6) if success_ids else 0,
                "all_conversation_count": all_conversation_count,
                "success_rate_among_conversations_with_pattern": round(success_conversation_count / all_conversation_count, 6) if all_conversation_count else 0,
            })
    return out


def compute_full_trajectory_topk(records: list[dict[str, Any]], top_k: int, success_attack_only: bool) -> list[dict[str, Any]]:
    selected = [record for record in records if is_success_attack(record) or not success_attack_only]
    success_ids = {record["conversation_id"] for record in records if is_success_attack(record)}
    all_conversation_sets: dict[str, set[str]] = defaultdict(set)
    success_conversation_sets: dict[str, set[str]] = defaultdict(set)
    for record in records:
        key = sequence_key(record.get("action_trajectory", []))
        if not key:
            continue
        conversation_id = str(record.get("conversation_id", ""))
        all_conversation_sets[key].add(conversation_id)
        if is_success_attack(record):
            success_conversation_sets[key].add(conversation_id)
    counter = Counter(sequence_key(record.get("action_trajectory", [])) for record in selected)
    counter.pop("", None)
    rows = top_counter_rows(
        counter,
        len(selected),
        "action_trajectory",
        top_k,
        proportion_field="proportion_of_success_trajectories" if success_attack_only else "proportion",
    )
    for row in rows:
        row["scope"] = "success_attack" if success_attack_only else "all"
        if success_attack_only:
            row["conversation_count"] = row["count"]
            row["proportion_of_success_conversations"] = row["proportion_of_success_trajectories"]
            all_conversation_count = len(all_conversation_sets[row["action_trajectory"]])
            success_conversation_count = len(success_conversation_sets[row["action_trajectory"]])
            row["all_conversation_count"] = all_conversation_count
            row["success_rate_among_conversations_with_pattern"] = round(success_conversation_count / all_conversation_count, 6) if all_conversation_count else 0
    return rows


def compute_action_ngram_topk(records: list[dict[str, Any]], ngram_sizes: list[int], top_k: int, success_attack_only: bool) -> list[dict[str, Any]]:
    selected = [record for record in records if is_success_attack(record) or not success_attack_only]
    rows: list[dict[str, Any]] = []
    for n in ngram_sizes:
        counter: Counter = Counter()
        conversation_sets: dict[str, set[str]] = defaultdict(set)
        all_conversation_sets: dict[str, set[str]] = defaultdict(set)
        success_conversation_sets: dict[str, set[str]] = defaultdict(set)
        for record in records:
            conversation_id = str(record.get("conversation_id", ""))
            for gram in ngrams(record.get("action_trajectory", []), n):
                key = sequence_key(gram)
                all_conversation_sets[key].add(conversation_id)
                if is_success_attack(record):
                    success_conversation_sets[key].add(conversation_id)
        total = 0
        for record in selected:
            conversation_id = str(record.get("conversation_id", ""))
            for gram in ngrams(record.get("action_trajectory", []), n):
                key = sequence_key(gram)
                counter[key] += 1
                conversation_sets[key].add(conversation_id)
                total += 1
        for row in top_counter_rows(
            counter,
            total,
            "action_ngram",
            top_k,
            proportion_field="proportion_of_success_ngrams" if success_attack_only else "proportion",
        ):
            out_row = {"scope": "success_attack" if success_attack_only else "all", "n": n, **row}
            if success_attack_only:
                conversation_count = len(conversation_sets[row["action_ngram"]])
                out_row["conversation_count"] = conversation_count
                out_row["proportion_of_success_conversations"] = round(conversation_count / len(selected), 6) if selected else 0
                all_conversation_count = len(all_conversation_sets[row["action_ngram"]])
                success_conversation_count = len(success_conversation_sets[row["action_ngram"]])
                out_row["all_conversation_count"] = all_conversation_count
                out_row["success_rate_among_conversations_with_pattern"] = round(success_conversation_count / all_conversation_count, 6) if all_conversation_count else 0
            rows.append(out_row)
    return rows


def compute_transition_topk(records: list[dict[str, Any]], top_k: int, field: str, success_attack_only: bool) -> list[dict[str, Any]]:
    selected = [record for record in records if is_success_attack(record) or not success_attack_only]
    counter: Counter = Counter()
    outgoing: Counter = Counter()
    conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    all_conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    success_conversation_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    selected_total = 0
    for record in records:
        conversation_id = str(record.get("conversation_id", ""))
        trajectory = record.get(field, [])
        for source, target in zip(trajectory, trajectory[1:]):
            all_conversation_sets[(source, target)].add(conversation_id)
            if is_success_attack(record):
                success_conversation_sets[(source, target)].add(conversation_id)
    for record in selected:
        conversation_id = str(record.get("conversation_id", ""))
        trajectory = record.get(field, [])
        for source, target in zip(trajectory, trajectory[1:]):
            counter[(source, target)] += 1
            conversation_sets[(source, target)].add(conversation_id)
            outgoing[source] += 1
            selected_total += 1

    all_total = 0
    for record in records:
        trajectory = record.get(field, [])
        all_total += max(0, len(trajectory) - 1)

    rows: list[dict[str, Any]] = []
    for rank, ((source, target), count) in enumerate(counter.most_common(top_k), 1):
        row = {
            "scope": "success_attack" if success_attack_only else "all",
            "rank": rank,
            "source": source,
            "target": target,
            "transition": f"{source} -> {target}",
            "count": count,
            "proportion_of_all_transitions": round(count / all_total, 6) if all_total else 0,
            "proportion_of_success_transition": round(count / selected_total, 6) if success_attack_only and selected_total else "",
            "conditional_probability": round(count / outgoing[source], 6) if outgoing[source] else 0,
        }
        if success_attack_only:
            conversation_count = len(conversation_sets[(source, target)])
            all_conversation_count = len(all_conversation_sets[(source, target)])
            success_conversation_count = len(success_conversation_sets[(source, target)])
            row["conversation_count"] = conversation_count
            row["proportion_of_success_conversations"] = round(conversation_count / len(selected), 6) if selected else 0
            row["all_conversation_count"] = all_conversation_count
            row["success_rate_among_conversations_with_pattern"] = round(success_conversation_count / all_conversation_count, 6) if all_conversation_count else 0
        rows.append(row)
    return rows


def compute_phase_trajectory_topk(records: list[dict[str, Any]], top_k: int, success_attack_only: bool) -> list[dict[str, Any]]:
    selected = [record for record in records if is_success_attack(record) or not success_attack_only]
    all_conversation_sets: dict[str, set[str]] = defaultdict(set)
    success_conversation_sets: dict[str, set[str]] = defaultdict(set)
    for record in records:
        key = sequence_key(record.get("phase_trajectory", []))
        if not key:
            continue
        conversation_id = str(record.get("conversation_id", ""))
        all_conversation_sets[key].add(conversation_id)
        if is_success_attack(record):
            success_conversation_sets[key].add(conversation_id)
    counter = Counter(sequence_key(record.get("phase_trajectory", [])) for record in selected)
    counter.pop("", None)
    rows = top_counter_rows(
        counter,
        len(selected),
        "phase_trajectory",
        top_k,
        proportion_field="proportion_of_success_trajectories" if success_attack_only else "proportion",
    )
    for row in rows:
        row["scope"] = "success_attack" if success_attack_only else "all"
        if success_attack_only:
            row["conversation_count"] = row["count"]
            row["proportion_of_success_conversations"] = row["proportion_of_success_trajectories"]
            all_conversation_count = len(all_conversation_sets[row["phase_trajectory"]])
            success_conversation_count = len(success_conversation_sets[row["phase_trajectory"]])
            row["all_conversation_count"] = all_conversation_count
            row["success_rate_among_conversations_with_pattern"] = round(success_conversation_count / all_conversation_count, 6) if all_conversation_count else 0
    return rows


def compute_dataset_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_source = Counter(record.get("source_pool", "") for record in records)
    by_severity = Counter(record.get("severity", "") for record in records)
    by_attempt: Counter = Counter()
    attempts_by_severity: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        severity = record.get("severity", "")
        for attempt_type in record.get("attempt_type", []):
            by_attempt[attempt_type] += 1
            attempts_by_severity[severity][attempt_type] += 1
    return {
        "n_conversations": len(records),
        "source_pool_counts": dict(by_source),
        "severity_counts": dict(by_severity),
        "attempt_type_counts": dict(by_attempt),
        "attempt_type_counts_by_severity": {
            severity: dict(counter)
            for severity, counter in sorted(attempts_by_severity.items())
        },
        "mean_action_trajectory_length": round(sum(record.get("action_trajectory_length", 0) for record in records) / len(records), 3) if records else 0,
        "mean_phase_trajectory_length": round(sum(record.get("phase_trajectory_length", 0) for record in records) / len(records), 3) if records else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cab", type=Path, default=DEFAULT_CAB)
    parser.add_argument("--seg-results-dir", type=Path, default=DEFAULT_SEG_RESULTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--ngram-sizes", nargs="+", type=int, default=[2, 3, 4])
    args = parser.parse_args()

    records = load_cab(args.cab)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "success_phase_action_topk.csv": (
            compute_success_phase_action_topk(records, args.seg_results_dir, args.top_k),
            [
                "phase", "phase_turn_count", "rank", "action", "count", "proportion",
                "conversation_count", "proportion_of_success_conversations",
                "all_conversation_count", "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_action_trajectory_topk.csv": (
            compute_full_trajectory_topk(records, args.top_k, success_attack_only=True),
            [
                "scope", "rank", "action_trajectory", "count",
                "proportion_of_success_trajectories", "conversation_count",
                "proportion_of_success_conversations", "all_conversation_count",
                "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_action_ngram_topk.csv": (
            compute_action_ngram_topk(records, args.ngram_sizes, args.top_k, success_attack_only=True),
            [
                "scope", "n", "rank", "action_ngram", "count",
                "proportion_of_success_ngrams", "conversation_count",
                "proportion_of_success_conversations", "all_conversation_count",
                "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_action_transition_topk.csv": (
            compute_transition_topk(records, args.top_k, "action_trajectory", success_attack_only=True),
            [
                "scope", "rank", "source", "target", "transition", "count",
                "proportion_of_all_transitions", "proportion_of_success_transition",
                "conditional_probability", "conversation_count",
                "proportion_of_success_conversations", "all_conversation_count",
                "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_phase_trajectory_topk.csv": (
            compute_phase_trajectory_topk(records, args.top_k, success_attack_only=True),
            [
                "scope", "rank", "phase_trajectory", "count",
                "proportion_of_success_trajectories", "conversation_count",
                "proportion_of_success_conversations", "all_conversation_count",
                "success_rate_among_conversations_with_pattern",
            ],
        ),
        "success_phase_transition_topk.csv": (
            compute_transition_topk(records, args.top_k, "phase_trajectory", success_attack_only=True),
            [
                "scope", "rank", "source", "target", "transition", "count",
                "proportion_of_all_transitions", "proportion_of_success_transition",
                "conditional_probability", "conversation_count",
                "proportion_of_success_conversations", "all_conversation_count",
                "success_rate_among_conversations_with_pattern",
            ],
        ),
        "all_action_transition_topk.csv": (
            compute_transition_topk(records, args.top_k, "action_trajectory", success_attack_only=False),
            ["scope", "rank", "source", "target", "transition", "count", "proportion_of_all_transitions", "conditional_probability"],
        ),
        "all_phase_transition_topk.csv": (
            compute_transition_topk(records, args.top_k, "phase_trajectory", success_attack_only=False),
            ["scope", "rank", "source", "target", "transition", "count", "proportion_of_all_transitions", "conditional_probability"],
        ),
    }

    for filename, (rows, fieldnames) in outputs.items():
        write_csv(args.out_dir / filename, rows, fieldnames)

    summary = compute_dataset_summary(records)
    write_json(args.out_dir / "cab_stats_summary.json", summary)

    print(f"Loaded {len(records)} CAB records")
    print(f"Wrote stats to {args.out_dir}")


if __name__ == "__main__":
    main()
