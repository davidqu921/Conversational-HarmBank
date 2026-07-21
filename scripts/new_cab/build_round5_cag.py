"""
Build Round 5 Conversational Attack Graphs (CAGs).

This produces two complementary graph layers:
  1. phase_cag: coarse phase-to-phase strategy graph from the phrase CAB
  2. turn_action_cag: tactical action-to-action graph from the turn-action CAB

Both are written as program-facing JSON plus edge CSVs and simple PNG figures.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import textwrap
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE_BANK = PROJECT_ROOT / "raw_cab_round5_reviewed_all" / "phrase_conversation_bank.jsonl"
DEFAULT_ACTION_BANK = PROJECT_ROOT / "raw_cab_round5_reviewed_all" / "turn_action_conversation_bank.jsonl"
DEFAULT_CAL = PROJECT_ROOT / "conversation_seg" / "conversation_action_library.md"
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab_round5_reviewed_all" / "cag"

PHASE_COLORS = {
    "Setup": "#4E79A7",
    "Trust Building": "#59A14F",
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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def display_source_path(path: Path) -> str:
    """Use a portable repo-relative path when possible, otherwise keep absolute."""
    if not path.is_absolute():
        return str(path)
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def is_success(record: dict[str, Any]) -> bool:
    return record.get("source_pool") == "success_attack"


def sequence_key(items: Iterable[str]) -> str:
    return " -> ".join(str(item) for item in items if str(item).strip())


def truncate_text(text: str, max_chars: int = 360) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def parse_action_library(path: Path) -> dict[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^##\s+([A-Z]\d+)\.\s+(.+?)\s*$\n"
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
            "node_id": action_id,
            "label": action_name,
            "phase": phase,
            "description": description,
        }
    return actions


def attempts(record: dict[str, Any]) -> list[str]:
    values = record.get("attempt_type") or []
    if isinstance(values, str):
        values = [values]
    if not values and record.get("attempt"):
        values = [record["attempt"]]
    return [str(value) for value in values if str(value).strip()] or ["Unknown"]


def severity_rank(severity: str) -> int:
    return {
        "3 - Severe": 3,
        "2 - Major": 2,
        "1 - Minor": 1,
        "0 - Safe": 0,
    }.get(str(severity), -1)


def edge_examples(
    records: list[dict[str, Any]],
    sequence_field: str,
    unit_field: str,
    max_examples: int,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    examples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    success_records = [record for record in records if is_success(record)]
    success_records.sort(
        key=lambda record: (
            -severity_rank(record.get("severity", "")),
            len(record.get(sequence_field, [])),
            str(record.get("conversation_id", "")),
        )
    )
    for record in success_records:
        conv_id = str(record.get("conversation_id", ""))
        sequence = [item for item in record.get(sequence_field, []) if item]
        units = record.get(unit_field, [])
        seen_in_record: set[tuple[str, str]] = set()
        for idx, edge in enumerate(zip(sequence, sequence[1:])):
            if edge in seen_in_record or len(examples[edge]) >= max_examples:
                continue
            seen_in_record.add(edge)
            example: dict[str, Any] = {
                "conversation_id": conv_id,
                "attempt_type": attempts(record),
                "severity": record.get("severity", ""),
                "primary_attack_vector": record.get("primary_attack_vector", ""),
            }
            if unit_field == "turns":
                matching = [turn for turn in units if turn.get("action") in edge]
                if len(matching) >= 2:
                    example.update({
                        "source_turn": matching[0].get("turn", ""),
                        "target_turn": matching[1].get("turn", ""),
                        "source_text": truncate_text(matching[0].get("text", "")),
                        "target_text": truncate_text(matching[1].get("text", "")),
                    })
            elif unit_field == "phrases":
                matching = [phrase for phrase in units if phrase.get("phase") in edge]
                if len(matching) >= 2:
                    example.update({
                        "source_phrase_index": matching[0].get("phrase_index", ""),
                        "target_phrase_index": matching[1].get("phrase_index", ""),
                        "source_turns": f"T{matching[0].get('start_turn')}-T{matching[0].get('end_turn')}",
                        "target_turns": f"T{matching[1].get('start_turn')}-T{matching[1].get('end_turn')}",
                    })
            examples[edge].append(example)
    return examples


def build_graph(
    records: list[dict[str, Any]],
    graph_id: str,
    graph_layer: str,
    sequence_field: str,
    unit_field: str,
    node_meta: dict[str, dict[str, str]],
    max_examples: int,
    top_k_next: int,
) -> dict[str, Any]:
    total_conversations = len(records)
    success_records = [record for record in records if is_success(record)]
    baseline_success_rate = len(success_records) / total_conversations if total_conversations else 0

    node_occ_total: Counter = Counter()
    node_occ_success: Counter = Counter()
    node_conv_total: dict[str, set[str]] = defaultdict(set)
    node_conv_success: dict[str, set[str]] = defaultdict(set)

    edge_occ_total: Counter = Counter()
    edge_occ_success: Counter = Counter()
    edge_conv_total: dict[tuple[str, str], set[str]] = defaultdict(set)
    edge_conv_success: dict[tuple[str, str], set[str]] = defaultdict(set)
    edge_attempts_all: dict[tuple[str, str], Counter] = defaultdict(Counter)
    edge_attempts_success: dict[tuple[str, str], Counter] = defaultdict(Counter)
    edge_next_all: dict[tuple[str, str], Counter] = defaultdict(Counter)
    edge_next_success: dict[tuple[str, str], Counter] = defaultdict(Counter)

    for record in records:
        conv_id = str(record.get("conversation_id", ""))
        sequence = [str(item).strip() for item in record.get(sequence_field, []) if str(item).strip()]
        success = is_success(record)
        unique_edges = set(zip(sequence, sequence[1:]))
        for node in sequence:
            node_occ_total[node] += 1
            node_conv_total[node].add(conv_id)
            if success:
                node_occ_success[node] += 1
                node_conv_success[node].add(conv_id)
        for idx, edge in enumerate(zip(sequence, sequence[1:])):
            edge_occ_total[edge] += 1
            edge_conv_total[edge].add(conv_id)
            if idx + 2 < len(sequence):
                edge_next_all[edge][sequence[idx + 2]] += 1
                if success:
                    edge_next_success[edge][sequence[idx + 2]] += 1
            if success:
                edge_occ_success[edge] += 1
                edge_conv_success[edge].add(conv_id)
        for edge in unique_edges:
            for attempt in attempts(record):
                edge_attempts_all[edge][attempt] += 1
                if success:
                    edge_attempts_success[edge][attempt] += 1

    examples = edge_examples(records, sequence_field, unit_field, max_examples)
    all_nodes = sorted(set(node_occ_total) | set(node_meta))
    nodes: list[dict[str, Any]] = []
    for node in all_nodes:
        total_conv = len(node_conv_total[node])
        success_conv = len(node_conv_success[node])
        success_rate = success_conv / total_conv if total_conv else 0
        meta = node_meta.get(node, {})
        nodes.append({
            "id": node,
            "label": meta.get("label", node),
            "node_type": graph_layer,
            "phase": meta.get("phase", node if graph_layer == "phase" else ""),
            "cal_id": meta.get("node_id", ""),
            "description": meta.get("description", ""),
            "count_total": node_occ_total[node],
            "count_success": node_occ_success[node],
            "conversation_count_total": total_conv,
            "conversation_count_success": success_conv,
            "success_rate": round(success_rate, 6),
            "success_lift": round(success_rate - baseline_success_rate, 6),
        })

    edges: list[dict[str, Any]] = []
    for source, target in sorted(edge_occ_total):
        edge = (source, target)
        total_conv = len(edge_conv_total[edge])
        success_conv = len(edge_conv_success[edge])
        success_rate = success_conv / total_conv if total_conv else 0
        edges.append({
            "source": source,
            "target": target,
            "transition": f"{source} -> {target}",
            "transition_count": edge_occ_total[edge],
            "success_transition_count": edge_occ_success[edge],
            "failure_transition_count": edge_occ_total[edge] - edge_occ_success[edge],
            "conversation_count": total_conv,
            "success_count": success_conv,
            "failure_count": total_conv - success_conv,
            "success_rate": round(success_rate, 6),
            "success_lift": round(success_rate - baseline_success_rate, 6),
            "attempt_targets": dict(edge_attempts_success[edge].most_common()),
            "attempt_targets_all_conversations": dict(edge_attempts_all[edge].most_common()),
            "next_nodes": dict(edge_next_all[edge].most_common(top_k_next)),
            "success_next_nodes": dict(edge_next_success[edge].most_common(top_k_next)),
            "example_conversation_ids": [example["conversation_id"] for example in examples.get(edge, [])],
            "examples": examples.get(edge, []),
        })
    edges.sort(key=lambda row: (-row["success_count"], -row["success_transition_count"], -row["transition_count"], row["source"], row["target"]))

    return {
        "graph_id": graph_id,
        "graph_layer": graph_layer,
        "metadata": {
            "total_conversations": total_conversations,
            "success_conversations": len(success_records),
            "baseline_success_rate": round(baseline_success_rate, 6),
            "sequence_field": sequence_field,
            "unit_field": unit_field,
            "node_success_rate": "conversation_count_success / conversation_count_total",
            "edge_success_rate": "success_count / conversation_count",
            "success_lift": "success_rate - baseline_success_rate",
            "counts_note": "transition_count/count_total are occurrence counts over compressed trajectories; success_count and conversation_count are conversation-level counts.",
        },
        "nodes": nodes,
        "edges": edges,
    }


def phase_meta() -> dict[str, dict[str, str]]:
    descriptions = {
        "Setup": "Establishes context before adversarial intent is explicit.",
        "Trust Building": "Builds credibility, legitimacy, or social pressure.",
        "Attack Construction": "Constructs a jailbreak path through reframing, roleplay, or transformation.",
        "Escalation": "Increases intensity or persistence after previous turns.",
        "Goal Execution": "Directly seeks restricted behavior or content.",
    }
    return {
        phase: {
            "node_id": f"P{idx}",
            "label": phase,
            "phase": phase,
            "description": descriptions.get(phase, ""),
        }
        for idx, phase in enumerate(PHASE_ORDER, start=1)
    }


def edge_csv_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "source": edge["source"],
            "target": edge["target"],
            "transition": edge["transition"],
            "transition_count": edge["transition_count"],
            "success_transition_count": edge["success_transition_count"],
            "conversation_count": edge["conversation_count"],
            "success_count": edge["success_count"],
            "success_rate": edge["success_rate"],
            "success_lift": edge["success_lift"],
            "attempt_targets": json.dumps(edge.get("attempt_targets", {}), ensure_ascii=False),
            "success_next_nodes": json.dumps(edge.get("success_next_nodes", {}), ensure_ascii=False),
            "example_conversation_ids": "; ".join(edge.get("example_conversation_ids", [])),
        }
        for edge in graph["edges"]
    ]


def scaled_width(
    count: int,
    max_count: int,
    min_width: float,
    max_width: float,
    width_scale: float,
) -> float:
    if max_count <= 0:
        return min_width
    share = max(0, count) / max_count
    return min_width + (max_width * width_scale - min_width) * (share ** 0.68)


def edge_label_text(edge_data: dict[str, Any], total_success_transitions: int, metric: str) -> str:
    success_count = int(edge_data.get("success_transition_count", 0))
    if metric == "count":
        return str(success_count)
    if metric == "success_rate":
        return f"{edge_data.get('success_rate', 0):.1%}"
    if metric == "success_lift":
        return f"{edge_data.get('success_lift', 0):+.1%}"
    percent = success_count / total_success_transitions if total_success_transitions else 0
    return f"{success_count} / {percent:.1%}"


def top_edge_labels(
    graph: Any,
    top_k: int,
    total_success_transitions: int,
    metric: str,
) -> dict[tuple[str, str], str]:
    if top_k <= 0:
        return {}
    ranked_edges = sorted(
        graph.edges,
        key=lambda edge: (
            -int(graph.edges[edge].get("success_transition_count", 0)),
            -int(graph.edges[edge].get("conversation_count", 0)),
            str(edge[0]),
            str(edge[1]),
        ),
    )
    return {
        edge: edge_label_text(graph.edges[edge], total_success_transitions, metric)
        for edge in ranked_edges[:top_k]
        if int(graph.edges[edge].get("success_transition_count", 0)) > 0
    }


def draw_graph(
    graph: dict[str, Any],
    out: Path,
    min_success_count: int,
    layout: str,
    seed: int,
    phase_x_gap: float,
    node_y_gap: float,
    canvas_phase_x_gap: float,
    canvas_node_y_gap: float,
    edge_width_scale: float,
    edge_width_min: float,
    edge_width_max: float,
    edge_label_top_k: int,
    edge_label_metric: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    g = nx.DiGraph()
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    for node in graph["nodes"]:
        g.add_node(node["id"], **node)
    for edge in graph["edges"]:
        if int(edge.get("success_transition_count", 0)) < min_success_count:
            continue
        g.add_edge(edge["source"], edge["target"], **edge, weight=edge.get("success_transition_count", 1))
    if g.number_of_edges() == 0:
        raise ValueError(f"No edges to draw for {graph['graph_id']}; lower --min-success-count.")

    if graph["graph_layer"] == "phase":
        pos = {
            phase: (idx * phase_x_gap, 0.0)
            for idx, phase in enumerate(PHASE_ORDER)
            if phase in g.nodes
        }
    elif layout == "phase":
        grouped: dict[str, list[str]] = {phase: [] for phase in PHASE_ORDER}
        grouped["Other"] = []
        for node in g.nodes:
            phase = nodes_by_id.get(node, {}).get("phase", "")
            grouped.setdefault(phase if phase in PHASE_ORDER else "Other", []).append(node)
        pos = {}
        for phase_idx, phase in enumerate(PHASE_ORDER + ["Other"]):
            phase_nodes = sorted(grouped.get(phase, []), key=lambda item: -nodes_by_id.get(item, {}).get("count_success", 0))
            if not phase_nodes:
                continue
            step = node_y_gap
            start_y = step * (len(phase_nodes) - 1) / 2
            for row_idx, node in enumerate(phase_nodes):
                pos[node] = (phase_idx * phase_x_gap, start_y - row_idx * step)
    else:
        pos = nx.spring_layout(g, seed=seed, k=4.0, iterations=250, scale=8, weight=None)

    max_count = max((nodes_by_id.get(node, {}).get("count_success", 0) for node in g.nodes), default=1)
    node_sizes = []
    node_colors = []
    labels = {}
    for node in g.nodes:
        meta = nodes_by_id.get(node, {})
        share = meta.get("count_success", 0) / max_count if max_count else 0
        node_sizes.append(1200 + 5200 * (share ** 0.65))
        node_colors.append(PHASE_COLORS.get(meta.get("phase", ""), "#BDBDBD"))
        cal_id = meta.get("cal_id", "")
        wrapped = "\n".join(textwrap.wrap(meta.get("label", node), width=16))
        labels[node] = f"{cal_id}\n{wrapped}" if cal_id else wrapped

    max_edge_count = max((int(g.edges[edge].get("success_transition_count", 0)) for edge in g.edges), default=1)
    total_success_transitions = sum(int(edge.get("success_transition_count", 0)) for edge in graph["edges"])
    edge_widths = [
        scaled_width(
            int(g.edges[edge].get("success_transition_count", 0)),
            max_edge_count,
            edge_width_min,
            edge_width_max,
            edge_width_scale,
        )
        for edge in g.edges
    ]
    edge_colors = ["#2B6CB0" if g.edges[edge].get("success_lift", 0) >= 0 else "#8E8E8E" for edge in g.edges]

    plt.figure(figsize=(14, 9) if graph["graph_layer"] == "action" else (13, 6))
    nx.draw_networkx_edges(
        g,
        pos,
        width=edge_widths,
        edge_color=edge_colors,
        alpha=0.36,
        arrows=True,
        arrowsize=15,
        min_source_margin=14,
        min_target_margin=18,
        connectionstyle="arc3,rad=0.14",
    )
    nx.draw_networkx_nodes(
        g,
        pos,
        node_size=node_sizes,
        node_color=node_colors,
        edgecolors="#333333",
        linewidths=0.8,
        alpha=0.93,
    )
    nx.draw_networkx_labels(
        g,
        pos,
        labels=labels,
        font_size=8 if graph["graph_layer"] == "phase" else 7,
        font_family="sans-serif",
        bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "none", "alpha": 0.72},
    )
    edge_labels = top_edge_labels(g, edge_label_top_k, total_success_transitions, edge_label_metric)
    if edge_labels:
        nx.draw_networkx_edge_labels(
            g,
            pos,
            edge_labels=edge_labels,
            font_size=6 if graph["graph_layer"] == "action" else 7,
            font_color="#263238",
            rotate=False,
            label_pos=0.58,
            bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "#D0D0D0", "alpha": 0.82},
        )
    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", label=phase, markerfacecolor=color, markersize=10)
        for phase, color in PHASE_COLORS.items()
    ]
    plt.legend(handles=legend_handles, loc="lower left", frameon=False)
    plt.title(f"{graph['graph_id']} ({g.number_of_nodes()} nodes, {g.number_of_edges()} success edges, min_success_count={min_success_count})")
    xs = [xy[0] for xy in pos.values()]
    ys = [xy[1] for xy in pos.values()]
    if xs and ys:
        if graph["graph_layer"] == "action" and layout == "phase":
            # Keep the display window independent from node spacing. If x/y
            # limits scale with phase_x_gap/node_y_gap, matplotlib normalizes
            # the picture and spacing changes become visually invisible.
            phase_counts = Counter(
                nodes_by_id.get(node, {}).get("phase", "Other")
                if nodes_by_id.get(node, {}).get("phase", "") in PHASE_ORDER
                else "Other"
                for node in g.nodes
            )
            max_rows = max(phase_counts.values(), default=1)
            x_left = -canvas_phase_x_gap * 1.4
            x_right = (len(PHASE_ORDER) - 1) * canvas_phase_x_gap + canvas_phase_x_gap * 1.4
            y_half = canvas_node_y_gap * (max_rows - 1) / 2 + canvas_node_y_gap * 1.8
            plt.xlim(x_left, x_right)
            plt.ylim(-y_half, y_half)
        else:
            plt.margins(0.16)
    plt.axis("off")
    plt.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=220)
    plt.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Round 5 phase and turn-action CAGs.")
    parser.add_argument("--phase-bank", type=Path, default=DEFAULT_PHASE_BANK)
    parser.add_argument("--action-bank", type=Path, default=DEFAULT_ACTION_BANK)
    parser.add_argument("--action-library", type=Path, default=DEFAULT_CAL)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--max-examples", type=int, default=5)
    parser.add_argument("--top-k-next", type=int, default=5)
    parser.add_argument("--min-success-count", type=int, default=5)
    parser.add_argument("--layout", choices=["phase", "spring"], default="phase")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--phase-x-gap", type=float, default=2.25, help="Horizontal gap between phase columns in the networkx phase layout.")
    parser.add_argument("--node-y-gap", type=float, default=1.08, help="Vertical gap between nodes within each phase column.")
    parser.add_argument("--canvas-phase-x-gap", type=float, default=1.60, help="Fixed display-window phase gap. Keep this stable while tuning --phase-x-gap.")
    parser.add_argument("--canvas-node-y-gap", type=float, default=0.80, help="Fixed display-window node gap. Keep this stable while tuning --node-y-gap.")
    parser.add_argument("--edge-width-scale", type=float, default=1.2, help="Multiplier for edge width contrast.")
    parser.add_argument("--edge-width-min", type=float, default=0.75, help="Minimum rendered edge width.")
    parser.add_argument("--edge-width-max", type=float, default=6.4, help="Maximum rendered edge width before scaling.")
    parser.add_argument("--edge-label-top-k", type=int, default=5, help="Label only the top-k displayed edges by success transition count. Use 0 to disable.")
    parser.add_argument(
        "--edge-label-metric",
        choices=["count_percent", "count", "success_rate", "success_lift"],
        default="count_percent",
        help="Metric shown on top-k edge labels.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    phrase_records = load_jsonl(args.phase_bank)
    action_records = load_jsonl(args.action_bank)

    phase_graph = build_graph(
        records=phrase_records,
        graph_id="round5_phase_cag",
        graph_layer="phase",
        sequence_field="phase_trajectory",
        unit_field="phrases",
        node_meta=phase_meta(),
        max_examples=args.max_examples,
        top_k_next=args.top_k_next,
    )
    action_graph = build_graph(
        records=action_records,
        graph_id="round5_turn_action_cag",
        graph_layer="action",
        sequence_field="action_trajectory",
        unit_field="turns",
        node_meta=parse_action_library(args.action_library),
        max_examples=args.max_examples,
        top_k_next=args.top_k_next,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "phase_conversation_attack_graph.json", phase_graph)
    write_json(args.out_dir / "turn_action_conversation_attack_graph.json", action_graph)
    write_json(args.out_dir / "conversation_attack_graph.json", {
        "graph_id": "round5_multilayer_cag",
        "metadata": {
            "source_phase_bank": display_source_path(args.phase_bank),
            "source_turn_action_bank": display_source_path(args.action_bank),
            "recommended_use": "Use phase_graph for macro attack trajectory planning and turn_action_graph for tactical action selection.",
        },
        "phase_graph": phase_graph,
        "turn_action_graph": action_graph,
    })
    write_csv(
        args.out_dir / "phase_cag_edges.csv",
        edge_csv_rows(phase_graph),
        [
            "source", "target", "transition", "transition_count", "success_transition_count",
            "conversation_count", "success_count", "success_rate", "success_lift",
            "attempt_targets", "success_next_nodes", "example_conversation_ids",
        ],
    )
    write_csv(
        args.out_dir / "turn_action_cag_edges.csv",
        edge_csv_rows(action_graph),
        [
            "source", "target", "transition", "transition_count", "success_transition_count",
            "conversation_count", "success_count", "success_rate", "success_lift",
            "attempt_targets", "success_next_nodes", "example_conversation_ids",
        ],
    )
    write_json(args.out_dir / "conversation_attack_graph_index.json", {
        "recommended_use": {
            "phase_cag": "Use as the paper-facing macro strategy graph and as high-level CAA planning states.",
            "turn_action_cag": "Use as the tactical graph for composing concrete user-turn actions inside or across phases.",
            "combined_policy": "Plan first over phase_cag, then choose phase-compatible action paths from turn_action_cag.",
        },
        "graphs": {
            "phase_cag": "phase_conversation_attack_graph.json",
            "turn_action_cag": "turn_action_conversation_attack_graph.json",
        },
        "figures": {
            "phase_cag": "phase_cag_networkx.png",
            "turn_action_cag": "turn_action_cag_networkx.png",
        },
    })

    draw_graph(
        phase_graph,
        args.out_dir / "phase_cag_networkx.png",
        args.min_success_count,
        args.layout,
        args.seed,
        phase_x_gap=args.phase_x_gap,
        node_y_gap=args.node_y_gap,
        canvas_phase_x_gap=args.canvas_phase_x_gap,
        canvas_node_y_gap=args.canvas_node_y_gap,
        edge_width_scale=args.edge_width_scale,
        edge_width_min=args.edge_width_min,
        edge_width_max=args.edge_width_max,
        edge_label_top_k=args.edge_label_top_k,
        edge_label_metric=args.edge_label_metric,
    )
    draw_graph(
        action_graph,
        args.out_dir / "turn_action_cag_networkx.png",
        args.min_success_count,
        args.layout,
        args.seed,
        phase_x_gap=args.phase_x_gap,
        node_y_gap=args.node_y_gap,
        canvas_phase_x_gap=args.canvas_phase_x_gap,
        canvas_node_y_gap=args.canvas_node_y_gap,
        edge_width_scale=args.edge_width_scale,
        edge_width_min=args.edge_width_min,
        edge_width_max=args.edge_width_max,
        edge_label_top_k=args.edge_label_top_k,
        edge_label_metric=args.edge_label_metric,
    )

    print(f"Phase CAG: {len(phase_graph['nodes'])} nodes, {len(phase_graph['edges'])} edges")
    print(f"Turn-action CAG: {len(action_graph['nodes'])} nodes, {len(action_graph['edges'])} edges")
    print(f"Wrote CAG outputs to {args.out_dir}")


if __name__ == "__main__":
    main()
