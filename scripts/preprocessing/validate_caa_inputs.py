"""Validate the frozen Part 1 artifacts consumed by CAA without importing CAA."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "raw_cab_round5_reviewed_all"
DEFAULT_HUMAN_CODINGS = (
    PROJECT_ROOT
    / "data_prep"
    / "human_label_5"
    / "resolved_coding_results"
    / "round5_reviewed_completed_codings.csv"
)
DEFAULT_CAL = PROJECT_ROOT / "conversation_seg" / "conversation_action_library.md"
POOLS = {"success_attack", "unsuccess_attack", "no_attack"}
SEVERITIES = {"0 - Safe", "1 - Minor", "2 - Major", "3 - Severe"}
CODING_FIELDS = {
    "id",
    "primary_attack_vector",
    "secondary_attack_vector",
    "attempt",
    "conversational",
    "severity",
}


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.counts: dict[str, Any] = {}

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def warn(self, condition: bool, message: str) -> None:
        if not condition:
            self.warnings.append(message)


def load_jsonl(path: Path, validation: Validation) -> list[dict[str, Any]]:
    if not path.is_file():
        validation.errors.append(f"Missing JSONL: {path}")
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                validation.errors.append(f"{path}:{line_number}: invalid JSON: {exc}")
                continue
            if not isinstance(value, dict):
                validation.errors.append(f"{path}:{line_number}: expected a JSON object")
                continue
            records.append(value)
    return records


def load_json(path: Path, validation: Validation) -> dict[str, Any]:
    if not path.is_file():
        validation.errors.append(f"Missing JSON: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        validation.errors.append(f"Invalid JSON {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        validation.errors.append(f"{path}: expected a JSON object")
        return {}
    return value


def record_ids(
    records: list[dict[str, Any]], label: str, validation: Validation
) -> set[str]:
    values = [str(row.get("conversation_id", "")).strip() for row in records]
    validation.require(all(values), f"{label}: every record needs conversation_id")
    duplicates = sorted(key for key, count in Counter(values).items() if key and count > 1)
    validation.require(not duplicates, f"{label}: duplicate IDs: {duplicates[:10]}")
    return {value for value in values if value}


def validate_turn_bank(records: list[dict[str, Any]], validation: Validation) -> set[str]:
    required = {
        "conversation_id", "source_pool", "primary_attack_vector", "attempt",
        "severity", "action_trajectory", "phase_trajectory", "turns",
    }
    for index, record in enumerate(records, start=1):
        record_label = f"turn bank ID {record.get('conversation_id', index)}"
        missing = required - record.keys()
        validation.require(not missing, f"{record_label}: missing {sorted(missing)}")
        validation.require(record.get("source_pool") in POOLS, f"{record_label}: invalid source_pool")
        validation.require(record.get("severity") in SEVERITIES, f"{record_label}: invalid severity")
        actions = record.get("action_trajectory")
        phases = record.get("phase_trajectory")
        turns = record.get("turns")
        validation.require(isinstance(actions, list) and bool(actions), f"{record_label}: empty action_trajectory")
        validation.require(isinstance(phases, list) and bool(phases), f"{record_label}: empty phase_trajectory")
        validation.require(isinstance(turns, list) and bool(turns), f"{record_label}: empty turns")
        validation.require(not bool(record.get("turn_coverage_issue")), f"{record_label}: unresolved turn coverage issue")
        if isinstance(turns, list):
            for turn in turns:
                validation.require(
                    isinstance(turn, dict) and all(turn.get(field) not in (None, "") for field in ("turn", "text", "phase", "action")),
                    f"{record_label}: malformed turn entry",
                )
    return record_ids(records, "turn bank", validation)


def validate_phrase_bank(records: list[dict[str, Any]], validation: Validation) -> set[str]:
    required = {
        "conversation_id", "source_pool", "primary_attack_vector", "attempt",
        "severity", "phase_trajectory", "phrases",
    }
    for index, record in enumerate(records, start=1):
        record_label = f"phrase bank ID {record.get('conversation_id', index)}"
        missing = required - record.keys()
        validation.require(not missing, f"{record_label}: missing {sorted(missing)}")
        validation.require(record.get("source_pool") in POOLS, f"{record_label}: invalid source_pool")
        validation.require(record.get("severity") in SEVERITIES, f"{record_label}: invalid severity")
        validation.require(isinstance(record.get("phase_trajectory"), list) and bool(record.get("phase_trajectory")), f"{record_label}: empty phase_trajectory")
        validation.require(isinstance(record.get("phrases"), list) and bool(record.get("phrases")), f"{record_label}: empty phrases")
    return record_ids(records, "phrase bank", validation)


def validate_graph(
    graph: dict[str, Any], expected_layer: str, path: Path, validation: Validation
) -> None:
    validation.require(graph.get("graph_layer") == expected_layer, f"{path}: expected graph_layer={expected_layer}")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    validation.require(isinstance(nodes, list) and bool(nodes), f"{path}: nodes must be a non-empty list")
    validation.require(isinstance(edges, list), f"{path}: edges must be a list")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return
    node_ids = {str(node.get("id", "")) for node in nodes if isinstance(node, dict)}
    validation.require("" not in node_ids, f"{path}: every node needs an id")
    for index, edge in enumerate(edges, start=1):
        source = str(edge.get("source", "")) if isinstance(edge, dict) else ""
        target = str(edge.get("target", "")) if isinstance(edge, dict) else ""
        validation.require(source in node_ids and target in node_ids, f"{path}: edge {index} has an unknown endpoint")


def load_coding_ids(path: Path, validation: Validation) -> set[str]:
    if not path.is_file():
        validation.errors.append(f"Missing reviewed codings: {path}")
        return set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        validation.require(CODING_FIELDS <= fields, f"{path}: missing columns {sorted(CODING_FIELDS - fields)}")
        rows = list(reader)
    ids = [str(row.get("id", "")).strip() for row in rows]
    validation.require(all(ids), f"{path}: every row needs id")
    validation.require(len(ids) == len(set(ids)), f"{path}: duplicate IDs")
    for index, row in enumerate(rows, start=2):
        validation.require(row.get("severity", "").strip() in SEVERITIES, f"{path}:{index}: invalid severity")
    validation.counts["reviewed_codings"] = len(rows)
    return set(ids)


def validate_all(artifact_dir: Path, human_codings: Path, action_library: Path) -> Validation:
    validation = Validation()
    turn_path = artifact_dir / "turn_action_conversation_bank.jsonl"
    phrase_path = artifact_dir / "phrase_conversation_bank.jsonl"
    action_graph_path = artifact_dir / "cag" / "turn_action_conversation_attack_graph.json"
    phase_graph_path = artifact_dir / "cag" / "phase_conversation_attack_graph.json"

    turn_records = load_jsonl(turn_path, validation)
    phrase_records = load_jsonl(phrase_path, validation)
    turn_ids = validate_turn_bank(turn_records, validation)
    phrase_ids = validate_phrase_bank(phrase_records, validation)
    coding_ids = load_coding_ids(human_codings, validation)
    validate_graph(load_json(action_graph_path, validation), "action", action_graph_path, validation)
    validate_graph(load_json(phase_graph_path, validation), "phase", phase_graph_path, validation)

    validation.require(action_library.is_file(), f"Missing Conversation Action Library: {action_library}")
    if action_library.is_file():
        cal_text = action_library.read_text(encoding="utf-8")
        actions = {action for record in turn_records for action in record.get("action_trajectory", [])}
        missing_actions = sorted(action for action in actions if action not in cal_text)
        validation.require(not missing_actions, f"CAL does not define actions: {missing_actions[:10]}")

    validation.require(turn_ids == phrase_ids, "turn and phrase CAB conversation IDs differ")
    validation.require(turn_ids == coding_ids, "CAB and reviewed-coding conversation IDs differ")
    validation.counts.update({
        "turn_bank_records": len(turn_records),
        "phrase_bank_records": len(phrase_records),
        "source_pools": dict(Counter(row.get("source_pool", "") for row in turn_records)),
    })
    return validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the complete Part 1 -> CAA handoff.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--human-codings", type=Path, default=DEFAULT_HUMAN_CODINGS)
    parser.add_argument("--action-library", type=Path, default=DEFAULT_CAL)
    parser.add_argument("--report", type=Path, help="Optional JSON validation report path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = validate_all(args.artifact_dir, args.human_codings, args.action_library)
    report = {
        "valid": not result.errors,
        "counts": result.counts,
        "errors": result.errors,
        "warnings": result.warnings,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if result.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
