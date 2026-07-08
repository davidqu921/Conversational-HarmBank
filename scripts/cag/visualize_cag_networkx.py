"""
Quick NetworkX visualization for the Conversation Attack Graph.

This is intentionally simple and exploratory: use it to sanity-check whether
the CAG structure matches intuition before building a richer visualization.
"""
from __future__ import annotations

import argparse
import json
import math
import textwrap
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GRAPH = PROJECT_ROOT / "raw_cab" / "cag" / "conversation_attack_graph.json"

PHASE_COLORS = {
    "Setup": "#4E79A7",
    "Trust Building": "#59A14F",
    "Attack Construction": "#E15759",
    "Escalation": "#B07AA1",
    "Goal Execution": "#76B7B2",
}

PHASE_ORDER = list(PHASE_COLORS)


def load_graph_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def scaled_edge_width(count: int) -> float:
    return 0.4 + math.log1p(max(count, 0)) * 0.55


def build_networkx_graph(graph_json: dict[str, Any], min_count: int, success_only: bool) -> Any:
    import networkx as nx

    graph = nx.DiGraph()
    for node in graph_json["nodes"]:
        graph.add_node(
            node["action_name"],
            phase=node.get("phase", ""),
            action_id=node.get("action_id", ""),
            success_rate=node.get("success_rate", 0),
            count_total=node.get("count_total", 0),
        )

    for edge in graph_json["edges"]:
        count_field = "success_transition_count" if success_only else "transition_count"
        count = int(edge.get(count_field, 0))
        if count < min_count:
            continue
        graph.add_edge(
            edge["source"],
            edge["target"],
            weight=count,
            transition_count=edge.get("transition_count", 0),
            success_transition_count=edge.get("success_transition_count", 0),
            success_rate=edge.get("success_rate", 0),
            success_lift=edge.get("success_lift", 0),
            phase_transition=edge.get("phase_transition", ""),
        )
    return graph


def phase_layout(graph: Any) -> dict[str, tuple[float, float]]:
    by_phase: dict[str, list[str]] = {phase: [] for phase in PHASE_ORDER}
    by_phase["Other"] = []
    for node in graph.nodes:
        phase = graph.nodes[node].get("phase", "")
        by_phase.setdefault(phase if phase in PHASE_ORDER else "Other", []).append(node)

    pos: dict[str, tuple[float, float]] = {}
    for phase_index, phase in enumerate(PHASE_ORDER + ["Other"]):
        nodes = sorted(by_phase.get(phase, []), key=lambda item: -graph.nodes[item].get("count_total", 0))
        if not nodes:
            continue
        step = 1.65
        start_y = step * (len(nodes) - 1) / 2
        for row_index, node in enumerate(nodes):
            pos[node] = (phase_index * 3.35, start_y - row_index * step)
    return pos


def wrapped_labels(graph: Any) -> dict[str, str]:
    labels: dict[str, str] = {}
    for node in graph.nodes:
        action_id = graph.nodes[node].get("action_id", "")
        label = "\n".join(textwrap.wrap(node, width=16))
        labels[node] = f"{action_id}\n{label}" if action_id else label
    return labels


def draw_graph(graph: Any, title: str, out: Path | None, seed: int, layout: str, show: bool) -> None:
    if not show:
        import matplotlib

        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    if graph.number_of_edges() == 0:
        raise ValueError("No edges to draw. Lower --min-count or disable --success-only.")

    if layout == "spring":
        pos = nx.spring_layout(graph, seed=seed, k=4.5, iterations=300, scale=8, weight=None)
    else:
        pos = phase_layout(graph)
    max_count = max((graph.nodes[node].get("count_total", 0) for node in graph.nodes), default=1)
    node_sizes = []
    for node in graph.nodes:
        count = graph.nodes[node].get("count_total", 0)
        share = count / max_count if max_count else 0
        node_sizes.append(1500 + 6200 * (share ** 0.65))
    node_colors = [
        PHASE_COLORS.get(graph.nodes[node].get("phase", ""), "#bdbdbd")
        for node in graph.nodes
    ]
    edge_widths = [
        scaled_edge_width(graph.edges[edge].get("weight", 1))
        for edge in graph.edges
    ]
    edge_colors = [
        "#2B6CB0" if graph.edges[edge].get("success_lift", 0) >= 0 else "#9E9E9E"
        for edge in graph.edges
    ]

    plt.figure(figsize=(24, 14))
    nx.draw_networkx_edges(
        graph,
        pos,
        width=edge_widths,
        edge_color=edge_colors,
        alpha=0.34,
        arrows=True,
        arrowsize=13,
        min_source_margin=14,
        min_target_margin=18,
        connectionstyle="arc3,rad=0.14",
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        node_size=node_sizes,
        node_color=node_colors,
        edgecolors="#333333",
        linewidths=0.8,
        alpha=0.92,
    )
    nx.draw_networkx_labels(
        graph,
        pos,
        labels=wrapped_labels(graph),
        font_size=7,
        font_family="sans-serif",
        bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "none", "alpha": 0.72},
    )

    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", label=phase, markerfacecolor=color, markersize=10)
        for phase, color in PHASE_COLORS.items()
    ]
    plt.legend(handles=legend_handles, loc="lower left", frameon=False)
    plt.title(title)
    plt.axis("off")
    plt.tight_layout()

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(out, dpi=220, bbox_inches="tight")
        print(f"Saved visualization to {out}")
    if show:
        plt.show()
    else:
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--min-count", type=int, default=5, help="Minimum transition count to draw.")
    parser.add_argument("--success-only", action="store_true", help="Filter/weight edges by success_transition_count.")
    parser.add_argument("--out", type=Path, default=None, help="Optional PNG output path.")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--layout", choices=["phase", "spring"], default="phase")
    parser.add_argument("--no-show", action="store_true", help="Save without opening a GUI window.")
    args = parser.parse_args()

    graph_json = load_graph_json(args.graph)
    graph = build_networkx_graph(graph_json, min_count=args.min_count, success_only=args.success_only)
    title = (
        f"{graph_json.get('graph_id', 'CAG')} "
        f"({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges, min_count={args.min_count})"
    )
    draw_graph(graph, title=title, out=args.out, seed=args.seed, layout=args.layout, show=not args.no_show)


if __name__ == "__main__":
    main()
