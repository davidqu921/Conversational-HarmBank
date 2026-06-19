"""
Build a Conversation Attack Graph (CAG) from the Conversation Attack Bank.

The CAG is program-facing JSON for later Conversation Attack Automation (CAA):
nodes are actions, and directed edges are action transitions.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAB = PROJECT_ROOT / "raw_cab" / "conversation_attack_bank.jsonl"
DEFAULT_SEG_RESULTS = PROJECT_ROOT / "conversation_seg" / "results_2"
DEFAULT_CAL = PROJECT_ROOT / "conversation_seg" / "conversation_action_library.md"
DEFAULT_CAG_DIR = PROJECT_ROOT / "raw_cab" / "cag"
DEFAULT_OUT = DEFAULT_CAG_DIR / "conversation_attack_graph.json"
DEFAULT_EDGE_CSV = DEFAULT_CAG_DIR / "cag_v1_edges.csv"
DEFAULT_GRAPHML = DEFAULT_CAG_DIR / "cag_v1.graphml"
DEFAULT_GEXF = DEFAULT_CAG_DIR / "cag_v1.gexf"

PHASE_COLORS = {
    "Setup": "#4E79A7",
    "Trust Building": "#59A14F",
    "Reconnaissance": "#F28E2B",
    "Attack Construction": "#E15759",
    "Escalation": "#B07AA1",
    "Goal Execution": "#76B7B2",
}
PHASE_ORDER = list(PHASE_COLORS)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_edge_csv(path: Path, graph: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source",
        "target",
        "transition_count",
        "success_count",
        "success_rate",
        "success_lift",
        "phase_transition",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for edge in graph["edges"]:
            writer.writerow({field: edge.get(field, "") for field in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def is_success(record: dict[str, Any]) -> bool:
    return record.get("source_pool") == "success_attack"


def sequence_key(items: Iterable[str]) -> str:
    return " -> ".join(items)


def collapse_adjacent_turns(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    collapsed: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda item: int(item.get("turn") or 0)):
        action = row.get("action", "").strip()
        if not action:
            continue
        if collapsed and collapsed[-1]["action"] == action:
            continue
        collapsed.append(row)
    return collapsed


def parse_action_library(path: Path) -> dict[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^##\s+([A-F]\d+)\.\s+(.+?)\s*$\n"
        r".*?^Phase:\s*\n(.+?)\s*\n"
        r".*?^Definition:\s*\n(.+?)(?=\n\nExamples:|\n---|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    actions: dict[str, dict[str, str]] = {}
    for match in pattern.finditer(text):
        action_id = match.group(1).strip()
        action_name = match.group(2).strip()
        phase = " ".join(match.group(3).strip().split())
        description = " ".join(match.group(4).strip().split())
        actions[action_name] = {
            "action_id": action_id,
            "action_name": action_name,
            "phase": phase,
            "description": description,
        }
    return actions


def load_turn_index(seg_results_dir: Path) -> dict[str, list[dict[str, str]]]:
    by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for path in sorted(seg_results_dir.glob("*/turn_segments.csv")):
        for row in read_csv(path):
            cid = row.get("id", "").strip()
            if cid:
                by_id[cid].append({
                    "turn": row.get("turn", "").strip(),
                    "text": row.get("text", "").strip(),
                    "phase": row.get("phase", "").strip(),
                    "action": row.get("action", "").strip(),
                })
    return by_id


def truncate_text(text: str, max_chars: int = 420) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def graph_attr_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def hex_to_rgb(color: str) -> tuple[str, str, str]:
    color = color.lstrip("#")
    return str(int(color[0:2], 16)), str(int(color[2:4], 16)), str(int(color[4:6], 16))


def phase_positions(nodes: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    by_phase: dict[str, list[dict[str, Any]]] = {phase: [] for phase in PHASE_ORDER}
    by_phase["Other"] = []
    for node in nodes:
        phase = node.get("phase", "")
        by_phase.setdefault(phase if phase in PHASE_ORDER else "Other", []).append(node)

    positions: dict[str, tuple[float, float]] = {}
    for phase_index, phase in enumerate(PHASE_ORDER + ["Other"]):
        phase_nodes = sorted(by_phase.get(phase, []), key=lambda item: -item.get("count_total", 0))
        if not phase_nodes:
            continue
        step = 132.0
        start_y = step * (len(phase_nodes) - 1) / 2
        for row_index, node in enumerate(phase_nodes):
            positions[node["action_name"]] = (phase_index * 285.0, start_y - row_index * step)
    return positions


def node_size(node: dict[str, Any], max_count: int) -> str:
    share = node.get("count_total", 0) / max_count if max_count else 0
    return str(round(24.0 + 76.0 * (share ** 0.65), 3))


def edge_thickness(edge: dict[str, Any]) -> str:
    return str(round(0.8 + 0.75 * (max(0, edge.get("transition_count", 0)) ** 0.5), 3))


def edge_color(edge: dict[str, Any]) -> str:
    return "#2B6CB0" if edge.get("success_lift", 0) >= 0 else "#9E9E9E"


def graphml_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    return "string"


def gexf_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "double"
    return "string"


def write_graphml(path: Path, graph: dict[str, Any]) -> None:
    node_attrs = [
        "action_id",
        "phase",
        "count_total",
        "count_success",
        "conversation_count_total",
        "conversation_count_success",
        "success_rate",
        "success_lift",
        "description",
    ]
    edge_attrs = [
        "transition_count",
        "success_transition_count",
        "failure_transition_count",
        "conversation_count",
        "success_count",
        "failure_count",
        "success_rate",
        "success_lift",
        "phase_transition",
        "attempt_targets",
        "attempt_targets_all_conversations",
        "next_actions",
        "success_next_actions",
        "example_conversation_ids",
    ]
    node_attr_types = infer_attr_types(graph["nodes"], node_attrs)
    edge_attr_types = infer_attr_types(graph["edges"], edge_attrs)

    path.parent.mkdir(parents=True, exist_ok=True)
    ns = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}graphml")
    for attr, attr_type in node_attr_types.items():
        ET.SubElement(root, f"{{{ns}}}key", id=f"node_{attr}", **{
            "for": "node",
            "attr.name": attr,
            "attr.type": attr_type,
        })
    for attr, attr_type in edge_attr_types.items():
        ET.SubElement(root, f"{{{ns}}}key", id=f"edge_{attr}", **{
            "for": "edge",
            "attr.name": attr,
            "attr.type": attr_type,
        })

    graph_el = ET.SubElement(root, f"{{{ns}}}graph", id=graph["graph_id"], edgedefault="directed")
    for node in graph["nodes"]:
        node_el = ET.SubElement(graph_el, f"{{{ns}}}node", id=node["action_name"])
        for attr in node_attrs:
            if attr in node:
                data_el = ET.SubElement(node_el, f"{{{ns}}}data", key=f"node_{attr}")
                data_el.text = graph_attr_value(node[attr])
    for idx, edge in enumerate(graph["edges"]):
        edge_el = ET.SubElement(
            graph_el,
            f"{{{ns}}}edge",
            id=f"e{idx}",
            source=edge["source"],
            target=edge["target"],
        )
        for attr in edge_attrs:
            if attr in edge:
                data_el = ET.SubElement(edge_el, f"{{{ns}}}data", key=f"edge_{attr}")
                data_el.text = graph_attr_value(edge[attr])
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_gexf(path: Path, graph: dict[str, Any]) -> None:
    node_attrs = [
        "action_id",
        "phase",
        "count_total",
        "count_success",
        "conversation_count_total",
        "conversation_count_success",
        "success_rate",
        "success_lift",
        "description",
    ]
    edge_attrs = [
        "transition_count",
        "success_transition_count",
        "failure_transition_count",
        "conversation_count",
        "success_count",
        "failure_count",
        "success_rate",
        "success_lift",
        "phase_transition",
        "attempt_targets",
        "attempt_targets_all_conversations",
        "next_actions",
        "success_next_actions",
        "example_conversation_ids",
    ]
    node_attr_types = infer_attr_types(graph["nodes"], node_attrs, type_fn=gexf_type)
    edge_attr_types = infer_attr_types(graph["edges"], edge_attrs, type_fn=gexf_type)

    positions = phase_positions(graph["nodes"])
    max_node_count = max((node.get("count_total", 0) for node in graph["nodes"]), default=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    ns = "http://gexf.net/1.3"
    viz_ns = "http://gexf.net/1.3/viz"
    ET.register_namespace("", ns)
    ET.register_namespace("viz", viz_ns)
    root = ET.Element(f"{{{ns}}}gexf", version="1.3")
    graph_el = ET.SubElement(root, f"{{{ns}}}graph", mode="static", defaultedgetype="directed")

    node_attr_ids: dict[str, str] = {}
    node_attrs_el = ET.SubElement(graph_el, f"{{{ns}}}attributes", {"class": "node"})
    for idx, (attr, attr_type) in enumerate(node_attr_types.items()):
        attr_id = f"n{idx}"
        node_attr_ids[attr] = attr_id
        ET.SubElement(node_attrs_el, f"{{{ns}}}attribute", id=attr_id, title=attr, type=attr_type)

    edge_attr_ids: dict[str, str] = {}
    edge_attrs_el = ET.SubElement(graph_el, f"{{{ns}}}attributes", {"class": "edge"})
    for idx, (attr, attr_type) in enumerate(edge_attr_types.items()):
        attr_id = f"e{idx}"
        edge_attr_ids[attr] = attr_id
        ET.SubElement(edge_attrs_el, f"{{{ns}}}attribute", id=attr_id, title=attr, type=attr_type)

    nodes_el = ET.SubElement(graph_el, f"{{{ns}}}nodes")
    for node in graph["nodes"]:
        node_el = ET.SubElement(nodes_el, f"{{{ns}}}node", id=node["action_name"], label=node["action_name"])
        color = PHASE_COLORS.get(node.get("phase", ""), "#BDBDBD")
        r, g, b = hex_to_rgb(color)
        x, y = positions.get(node["action_name"], (0.0, 0.0))
        ET.SubElement(node_el, f"{{{viz_ns}}}color", r=r, g=g, b=b, a="0.96")
        ET.SubElement(node_el, f"{{{viz_ns}}}size", value=node_size(node, max_node_count))
        ET.SubElement(node_el, f"{{{viz_ns}}}position", x=str(x), y=str(y), z="0.0")
        attvalues_el = ET.SubElement(node_el, f"{{{ns}}}attvalues")
        for attr in node_attrs:
            if attr in node:
                ET.SubElement(attvalues_el, f"{{{ns}}}attvalue", {"for": node_attr_ids[attr], "value": graph_attr_value(node[attr])})

    edges_el = ET.SubElement(graph_el, f"{{{ns}}}edges")
    for idx, edge in enumerate(graph["edges"]):
        edge_el = ET.SubElement(
            edges_el,
            f"{{{ns}}}edge",
            id=str(idx),
            source=edge["source"],
            target=edge["target"],
            weight=str(edge.get("transition_count", 1)),
        )
        color = edge_color(edge)
        r, g, b = hex_to_rgb(color)
        ET.SubElement(edge_el, f"{{{viz_ns}}}color", r=r, g=g, b=b, a="0.42")
        ET.SubElement(edge_el, f"{{{viz_ns}}}thickness", value=edge_thickness(edge))
        attvalues_el = ET.SubElement(edge_el, f"{{{ns}}}attvalues")
        for attr in edge_attrs:
            if attr in edge:
                ET.SubElement(attvalues_el, f"{{{ns}}}attvalue", {"for": edge_attr_ids[attr], "value": graph_attr_value(edge[attr])})
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def infer_attr_types(
    rows: list[dict[str, Any]],
    attrs: list[str],
    type_fn: Any = graphml_type,
) -> dict[str, str]:
    attr_types: dict[str, str] = {}
    for attr in attrs:
        attr_types[attr] = "string"
        for row in rows:
            value = row.get(attr)
            if value not in (None, ""):
                attr_types[attr] = type_fn(value)
                break
    return attr_types


def build_examples(
    records: list[dict[str, Any]],
    turn_index: dict[str, list[dict[str, str]]],
    max_examples: int,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    examples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    success_records = [record for record in records if is_success(record)]
    severity_rank = {"3 - Severe": 3, "2 - Major": 2, "1 - Minor": 1, "0 - Safe": 0}
    success_records.sort(
        key=lambda record: (
            -severity_rank.get(str(record.get("severity", "")), -1),
            len(record.get("action_trajectory", [])),
            str(record.get("conversation_id", "")),
        )
    )

    for record in success_records:
        cid = str(record.get("conversation_id", ""))
        turns = collapse_adjacent_turns(turn_index.get(cid, []))
        used_edges: set[tuple[str, str]] = set()
        for left, right in zip(turns, turns[1:]):
            edge = (left["action"], right["action"])
            if edge in used_edges:
                continue
            if len(examples[edge]) >= max_examples:
                continue
            used_edges.add(edge)
            examples[edge].append({
                "conversation_id": cid,
                "source_turn": left.get("turn", ""),
                "target_turn": right.get("turn", ""),
                "source_text": truncate_text(left.get("text", "")),
                "target_text": truncate_text(right.get("text", "")),
                "attempt_type": record.get("attempt_type", []),
                "severity": record.get("severity", ""),
            })
    return examples


def build_graph(
    records: list[dict[str, Any]],
    action_meta: dict[str, dict[str, str]],
    turn_index: dict[str, list[dict[str, str]]],
    graph_id: str,
    max_examples: int,
    top_k_next: int,
) -> dict[str, Any]:
    total_conversations = len(records)
    success_conversations = sum(1 for record in records if is_success(record))
    baseline_success_rate = success_conversations / total_conversations if total_conversations else 0

    action_occ_total: Counter = Counter()
    action_occ_success: Counter = Counter()
    action_conv_total: dict[str, set[str]] = defaultdict(set)
    action_conv_success: dict[str, set[str]] = defaultdict(set)

    edge_occ_total: Counter = Counter()
    edge_occ_success: Counter = Counter()
    edge_conv_total: dict[tuple[str, str], set[str]] = defaultdict(set)
    edge_conv_success: dict[tuple[str, str], set[str]] = defaultdict(set)
    edge_attempt_targets_all: dict[tuple[str, str], Counter] = defaultdict(Counter)
    edge_attempt_targets_success: dict[tuple[str, str], Counter] = defaultdict(Counter)
    edge_phase_transitions: dict[tuple[str, str], Counter] = defaultdict(Counter)
    edge_next_actions: dict[tuple[str, str], Counter] = defaultdict(Counter)
    edge_next_actions_success: dict[tuple[str, str], Counter] = defaultdict(Counter)

    for record in records:
        cid = str(record.get("conversation_id", ""))
        trajectory = [item for item in record.get("action_trajectory", []) if item]
        success = is_success(record)
        attempts = record.get("attempt_type", []) or ["Unknown"]
        unique_edges = set(zip(trajectory, trajectory[1:]))

        for action in trajectory:
            action_occ_total[action] += 1
            action_conv_total[action].add(cid)
            if success:
                action_occ_success[action] += 1
                action_conv_success[action].add(cid)

        for idx, edge in enumerate(zip(trajectory, trajectory[1:])):
            source, target = edge
            edge_occ_total[edge] += 1
            edge_conv_total[edge].add(cid)
            phase_source = action_meta.get(source, {}).get("phase", "")
            phase_target = action_meta.get(target, {}).get("phase", "")
            if phase_source or phase_target:
                edge_phase_transitions[edge][f"{phase_source} -> {phase_target}"] += 1
            if idx + 2 < len(trajectory):
                edge_next_actions[edge][trajectory[idx + 2]] += 1
                if success:
                    edge_next_actions_success[edge][trajectory[idx + 2]] += 1
            if success:
                edge_occ_success[edge] += 1
                edge_conv_success[edge].add(cid)
        for edge in unique_edges:
            for attempt in attempts:
                edge_attempt_targets_all[edge][attempt] += 1
                if success:
                    edge_attempt_targets_success[edge][attempt] += 1

    example_index = build_examples(records, turn_index, max_examples)

    nodes: list[dict[str, Any]] = []
    all_actions = sorted(set(action_meta) | set(action_occ_total))
    for action in all_actions:
        total_conv_count = len(action_conv_total[action])
        success_conv_count = len(action_conv_success[action])
        success_rate = success_conv_count / total_conv_count if total_conv_count else 0
        meta = action_meta.get(action, {})
        nodes.append({
            "action_id": meta.get("action_id", ""),
            "action_name": action,
            "phase": meta.get("phase", ""),
            "count_total": action_occ_total[action],
            "count_success": action_occ_success[action],
            "conversation_count_total": total_conv_count,
            "conversation_count_success": success_conv_count,
            "success_rate": round(success_rate, 6),
            "success_lift": round(success_rate - baseline_success_rate, 6),
            "description": meta.get("description", ""),
        })

    edges: list[dict[str, Any]] = []
    for source, target in sorted(edge_occ_total):
        edge = (source, target)
        total_conv_count = len(edge_conv_total[edge])
        success_conv_count = len(edge_conv_success[edge])
        failure_conv_count = total_conv_count - success_conv_count
        success_rate = success_conv_count / total_conv_count if total_conv_count else 0
        common_phase_transition = edge_phase_transitions[edge].most_common(1)
        examples = example_index.get(edge, [])
        edges.append({
            "source": source,
            "target": target,
            "transition": f"{source} -> {target}",
            "transition_count": edge_occ_total[edge],
            "success_transition_count": edge_occ_success[edge],
            "failure_transition_count": edge_occ_total[edge] - edge_occ_success[edge],
            "conversation_count": total_conv_count,
            "success_count": success_conv_count,
            "failure_count": failure_conv_count,
            "success_rate": round(success_rate, 6),
            "success_lift": round(success_rate - baseline_success_rate, 6),
            "phase_transition": common_phase_transition[0][0] if common_phase_transition else "",
            "phase_transitions": dict(edge_phase_transitions[edge].most_common()),
            "attempt_targets": dict(edge_attempt_targets_success[edge].most_common()),
            "attempt_targets_all_conversations": dict(edge_attempt_targets_all[edge].most_common()),
            "next_actions": dict(edge_next_actions[edge].most_common(top_k_next)),
            "success_next_actions": dict(edge_next_actions_success[edge].most_common(top_k_next)),
            "example_conversation_ids": [example["conversation_id"] for example in examples],
            "examples": examples,
        })
    edges.sort(key=lambda row: (-row["success_count"], -row["transition_count"], row["source"], row["target"]))

    return {
        "graph_id": graph_id,
        "metadata": {
            "source": "raw_cab/conversation_attack_bank.jsonl",
            "segmentation_source": "conversation_seg/results_2/*/turn_segments.csv",
            "total_conversations": total_conversations,
            "success_conversations": success_conversations,
            "baseline_success_rate": round(baseline_success_rate, 6),
            "node_success_rate": "conversation_count_success / conversation_count_total",
            "edge_success_rate": "success_count / conversation_count",
            "success_lift": "success_rate - baseline_success_rate",
            "attempt_targets": "Attempt-type counts among successful conversations that use the edge.",
            "attempt_targets_all_conversations": "Attempt-type counts among all conversations that use the edge.",
            "counts_note": "transition_count/count_total are occurrence counts over compressed action trajectories; success_count and conversation_count are conversation-level counts.",
        },
        "nodes": nodes,
        "edges": edges,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cab", type=Path, default=DEFAULT_CAB)
    parser.add_argument("--seg-results-dir", type=Path, default=DEFAULT_SEG_RESULTS)
    parser.add_argument("--action-library", type=Path, default=DEFAULT_CAL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--edge-csv", type=Path, default=DEFAULT_EDGE_CSV)
    parser.add_argument("--graphml", type=Path, default=DEFAULT_GRAPHML)
    parser.add_argument("--gexf", type=Path, default=DEFAULT_GEXF)
    parser.add_argument("--graph-id", default="cag_v1")
    parser.add_argument("--max-examples", type=int, default=5)
    parser.add_argument("--top-k-next", type=int, default=5)
    args = parser.parse_args()

    records = load_jsonl(args.cab)
    action_meta = parse_action_library(args.action_library)
    turn_index = load_turn_index(args.seg_results_dir)
    graph = build_graph(
        records=records,
        action_meta=action_meta,
        turn_index=turn_index,
        graph_id=args.graph_id,
        max_examples=args.max_examples,
        top_k_next=args.top_k_next,
    )
    write_json(args.out, graph)
    write_edge_csv(args.edge_csv, graph)
    write_graphml(args.graphml, graph)
    write_gexf(args.gexf, graph)
    print(f"Loaded {len(records)} CAB records")
    print(f"Wrote {len(graph['nodes'])} nodes and {len(graph['edges'])} edges to {args.out}")
    print(f"Wrote edge list to {args.edge_csv}")
    print(f"Wrote GraphML to {args.graphml}")
    print(f"Wrote GEXF to {args.gexf}")


if __name__ == "__main__":
    main()
