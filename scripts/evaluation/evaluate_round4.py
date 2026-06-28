"""
Evaluate Round 4 jailbreak coding.

Round 4 keeps the same attempt/conversational/severity layout as Round 3, but
attack vectors are no longer wide X-mark columns. Each row has:
  - Primary Attack Vector
  - Secondary Attack Vector (optional)

For attack-vector agreement this script treats primary/secondary as an unordered
set. It reports both standard multi-label binary kappa and relaxed overlap
metrics where any shared vector counts as agreement.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ATTACK_VECTORS = [
    "No Attempt",
    "System or Rule Output",
    "Text or Format Trick",
    "Disguised Intent",
    "Fake Scenario",
    "RolePlay & Persona Manipulation (input/injection)",
    "Social or Emotional Pressure",
    "Direct Elicitation",
    "Out of Context/Absurd Conversation",
    "Overwhelming",
]
ATTEMPTS = [
    "Swearing",
    "Slur",
    "Inappropriate Topics",
    "Political/Social/Bias",
    "Incorrect Information",
    "Break Character",
    "General Break",
    "Leak Information",
]
CONVERSATIONAL = ["Single Prompt", "Multi Prompt", "Conversational"]
SEVERITY = ["0 - Safe", "1 - Minor", "2 - Major", "3 - Severe"]


def normalize(label: str | None) -> str:
    if not label:
        return ""
    label = " ".join(str(label).strip().split())
    aliases = {
        "no attempt": "No Attempt",
        "out of context/absurd conversation": "Out of Context/Absurd Conversation",
        "out of context": "Out of Context/Absurd Conversation",
        "different language": "Different Language",
        "inapp topic": "Inappropriate Topics",
        "inappropriate topics": "Inappropriate Topics",
        "incorrect info": "Incorrect Information",
        "incorrect information": "Incorrect Information",
        "general break": "General Break",
        "system or rule output": "System or Rule Output",
        "system or rule manipulation": "System or Rule Output",
        "roleplay & persona manipulation": "RolePlay & Persona Manipulation (input/injection)",
        "roleplay & persona manipulation (input/injection)": "RolePlay & Persona Manipulation (input/injection)",
        "political/social/bias": "Political/Social/Bias",
        "no (safe)": "0 - Safe",
        "0 - safe": "0 - Safe",
        "minor (silly unsual)": "1 - Minor",
        "minor (silly unusual)": "1 - Minor",
        "1- minor": "1 - Minor",
        "1 - minor": "1 - Minor",
        "major (problematic)": "2 - Major",
        "2 - major": "2 - Major",
        "definitely broken (severe)": "3 - Severe",
        "3 - severe": "3 - Severe",
    }
    return aliases.get(label.lower(), label)


def empty_record() -> dict[str, Any]:
    return {
        "vectors": set(),
        "primary_vector": "",
        "secondary_vector": "",
        "attempts": set(),
        "conversational": "",
        "severity": "",
        "reasoning": "",
    }


def find_column(labels: list[str], candidates: tuple[str, ...]) -> int | None:
    normalized = [normalize(label).lower() for label in labels]
    for candidate in candidates:
        candidate_norm = normalize(candidate).lower()
        for idx, label in enumerate(normalized):
            if label == candidate_norm:
                return idx
    return None


def load_round4_human(path: Path, max_conversations: int | None = None) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) < 4 or not rows[0] or rows[0][0] != "Interaction":
        raise ValueError(f"{path} does not look like a Round 4 CSV")

    labels = [normalize(value) for value in rows[2]]
    primary_idx = find_column(labels, ("Primary Attack Vector",))
    secondary_idx = find_column(labels, ("Secondary Attack Vector (optional)", "Secodary Attack Vector (optional)"))
    if primary_idx is None:
        raise ValueError(f"{path} is missing Primary Attack Vector column")

    out: dict[str, dict[str, Any]] = {}
    loaded = 0
    for row in rows[3:]:
        if not row or not row[0].strip():
            continue
        if max_conversations is not None and loaded >= max_conversations:
            break

        cid = row[0].strip()
        rec = empty_record()
        primary = normalize(row[primary_idx] if primary_idx < len(row) else "")
        secondary = normalize(row[secondary_idx] if secondary_idx is not None and secondary_idx < len(row) else "")
        rec["primary_vector"] = primary
        rec["secondary_vector"] = secondary
        rec["vectors"] = {value for value in (primary, secondary) if value}

        for idx, raw in enumerate(row):
            if raw.strip().upper() != "X":
                continue
            label = labels[idx] if idx < len(labels) else ""
            if label in ATTEMPTS:
                rec["attempts"].add(label)
            elif label in CONVERSATIONAL:
                rec["conversational"] = label
            elif label in SEVERITY:
                rec["severity"] = label

        if "No Attempt" in rec["vectors"]:
            rec["vectors"] = {"No Attempt"}
            rec["attempts"] = set()
        out[cid] = rec
        loaded += 1
    return out


def load_llm(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("error") or not row.get("llm_output"):
                continue
            output = row["llm_output"]
            rec = empty_record()

            if "primary_attack_vector" in output or "secondary_attack_vector" in output:
                primary = normalize(output.get("primary_attack_vector"))
                secondary = normalize(output.get("secondary_attack_vector"))
                rec["primary_vector"] = primary
                rec["secondary_vector"] = secondary
                rec["vectors"] = {value for value in (primary, secondary) if value}
                attempt = normalize(output.get("attempt"))
                rec["attempts"] = {attempt} if attempt else set()
            else:
                rec["vectors"] = {normalize(v) for v in output.get("attack_vectors", []) if normalize(v)}
                rec["attempts"] = {normalize(a) for a in output.get("attempts", []) if normalize(a)}

            if "No Attempt" in rec["vectors"]:
                rec["vectors"] = {"No Attempt"}
                rec["primary_vector"] = "No Attempt"
                rec["secondary_vector"] = ""
                rec["attempts"] = set()
            rec["conversational"] = normalize(output.get("conversational"))
            rec["severity"] = normalize(output.get("severity"))
            rec["reasoning"] = output.get("reasoning", "")
            out[str(row["id"])] = rec
    return out


def cohen_kappa(a: list[str], b: list[str]) -> float:
    if len(a) != len(b) or not a:
        return math.nan
    labels = sorted(set(a) | set(b))
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    ca = Counter(a)
    cb = Counter(b)
    expected = sum((ca[label] / n) * (cb[label] / n) for label in labels)
    if expected >= 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def single_label_kappa(a: list[str], b: list[str]) -> float:
    if set(a) == {""} and set(b) == {""}:
        return math.nan
    return cohen_kappa([value or "<blank>" for value in a], [value or "<blank>" for value in b])


def overlap_kappa_like(a_sets: list[set[str]], b_sets: list[set[str]]) -> float:
    """Chance-corrected overlap agreement for unordered multi-label sets.

    This is not classic Cohen's kappa. Observed agreement is true when two sets
    are both empty or share at least one label. Expected agreement uses the
    empirical marginal distributions over each rater's full label sets.
    """
    if len(a_sets) != len(b_sets) or not a_sets:
        return math.nan
    n = len(a_sets)
    a_keys = [tuple(sorted(values)) for values in a_sets]
    b_keys = [tuple(sorted(values)) for values in b_sets]
    ca = Counter(a_keys)
    cb = Counter(b_keys)

    def agrees(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
        return (not left and not right) or bool(set(left) & set(right))

    observed = sum(1 for left, right in zip(a_keys, b_keys) if agrees(left, right)) / n
    expected = 0.0
    for left, left_count in ca.items():
        for right, right_count in cb.items():
            if agrees(left, right):
                expected += (left_count / n) * (right_count / n)
    if expected >= 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def binary_kappas(labels: list[str], a_sets: list[set[str]], b_sets: list[set[str]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for label in labels:
        a = ["Y" if label in labels_a else "N" for labels_a in a_sets]
        b = ["Y" if label in labels_b else "N" for labels_b in b_sets]
        out[label] = math.nan if set(a) == {"N"} and set(b) == {"N"} else cohen_kappa(a, b)
    return out


def macro(values: dict[str, float]) -> float:
    usable = [value for value in values.values() if value == value]
    return sum(usable) / len(usable) if usable else math.nan


def set_metrics(a_sets: list[set[str]], b_sets: list[set[str]]) -> dict[str, float]:
    exact = []
    jaccard = []
    hit = []
    for a, b in zip(a_sets, b_sets):
        union = a | b
        inter = a & b
        exact.append(1.0 if a == b else 0.0)
        jaccard.append(1.0 if not union else len(inter) / len(union))
        hit.append(1.0 if (not union or inter) else 0.0)
    n = len(a_sets)
    return {
        "exact": sum(exact) / n if n else math.nan,
        "jaccard": sum(jaccard) / n if n else math.nan,
        "hit_rate": sum(hit) / n if n else math.nan,
    }


def single_hit(a: list[str], b: list[str]) -> float:
    if set(a) == {""} and set(b) == {""}:
        return math.nan
    return sum(1 for x, y in zip(a, b) if x == y) / len(a) if a else math.nan


def fmt(value: float) -> str:
    return "NA" if value != value else f"{value:.3f}"


def compare(a: dict[str, dict[str, Any]], b: dict[str, dict[str, Any]], name_a: str, name_b: str, out_dir: Path) -> None:
    ids = sorted(set(a) & set(b), key=lambda item: int(item) if item.isdigit() else item)
    if not ids:
        sys.exit("no overlapping IDs to evaluate")
    rows_a = [a[cid] for cid in ids]
    rows_b = [b[cid] for cid in ids]

    a_vectors = [r["vectors"] for r in rows_a]
    b_vectors = [r["vectors"] for r in rows_b]
    vector_k = binary_kappas(ATTACK_VECTORS, a_vectors, b_vectors)
    attempt_k = binary_kappas(ATTEMPTS, [r["attempts"] for r in rows_a], [r["attempts"] for r in rows_b])
    conv_k = single_label_kappa([r["conversational"] for r in rows_a], [r["conversational"] for r in rows_b])
    severity_k = single_label_kappa([r["severity"] for r in rows_a], [r["severity"] for r in rows_b])

    vector_metrics = set_metrics(a_vectors, b_vectors)
    attempt_metrics = set_metrics([r["attempts"] for r in rows_a], [r["attempts"] for r in rows_b])
    vector_overlap_k = overlap_kappa_like(a_vectors, b_vectors)

    report = [
        "# Round 4 Agreement Report",
        "",
        f"- Compared IDs: **{len(ids)}**",
        f"- A: **{name_a}**",
        f"- B: **{name_b}**",
        "",
        "## Cohen's Kappa",
        "",
        "| Dimension | Kappa |",
        "|---|---:|",
        f"| Attack Vector macro binary | {fmt(macro(vector_k))} |",
        f"| Attempt macro binary | {fmt(macro(attempt_k))} |",
        f"| Conversational | {fmt(conv_k)} |",
        f"| Severity | {fmt(severity_k)} |",
        "",
        "## Relaxed Attack-Vector Agreement",
        "",
        "Primary and secondary attack vectors are treated as an unordered set.",
        "The overlap-adjusted value is chance-corrected but is not classic Cohen's kappa.",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Any-overlap hit rate | {fmt(vector_metrics['hit_rate'])} |",
        f"| Exact unordered set match | {fmt(vector_metrics['exact'])} |",
        f"| Mean Jaccard | {fmt(vector_metrics['jaccard'])} |",
        f"| Overlap-adjusted kappa-like | {fmt(vector_overlap_k)} |",
        "",
        "## Multi-label Agreement",
        "",
        "| Dimension | Hit Rate | Exact Match | Mean Jaccard |",
        "|---|---:|---:|---:|",
        f"| Attack Vector | {fmt(vector_metrics['hit_rate'])} | {fmt(vector_metrics['exact'])} | {fmt(vector_metrics['jaccard'])} |",
        f"| Attempt | {fmt(attempt_metrics['hit_rate'])} | {fmt(attempt_metrics['exact'])} | {fmt(attempt_metrics['jaccard'])} |",
        "",
        "## Single-label Hit Rate",
        "",
        "| Dimension | Hit Rate |",
        "|---|---:|",
        f"| Conversational | {fmt(single_hit([r['conversational'] for r in rows_a], [r['conversational'] for r in rows_b]))} |",
        f"| Severity | {fmt(single_hit([r['severity'] for r in rows_a], [r['severity'] for r in rows_b]))} |",
        "",
        "## Per-label Kappa: Attack Vector",
        "",
        "| Label | Kappa | A positives | B positives |",
        "|---|---:|---:|---:|",
    ]
    for label in ATTACK_VECTORS:
        report.append(f"| {label} | {fmt(vector_k[label])} | {sum(1 for r in rows_a if label in r['vectors'])} | {sum(1 for r in rows_b if label in r['vectors'])} |")

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "round4_agreement_report.md"
    disagreements_path = out_dir / "round4_disagreements.csv"
    report_path.write_text("\n".join(report), encoding="utf-8")

    with disagreements_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "a_primary_vector", "a_secondary_vector", "b_primary_vector", "b_secondary_vector",
            "a_vectors", "b_vectors", "vector_overlap", "a_attempts", "b_attempts",
            "a_conversational", "b_conversational", "a_severity", "b_severity",
        ])
        writer.writeheader()
        for cid, rec_a, rec_b in zip(ids, rows_a, rows_b):
            vector_overlap = bool(rec_a["vectors"] & rec_b["vectors"]) or (not rec_a["vectors"] and not rec_b["vectors"])
            if (
                vector_overlap
                and rec_a["attempts"] == rec_b["attempts"]
                and rec_a["conversational"] == rec_b["conversational"]
                and rec_a["severity"] == rec_b["severity"]
            ):
                continue
            writer.writerow({
                "id": cid,
                "a_primary_vector": rec_a["primary_vector"],
                "a_secondary_vector": rec_a["secondary_vector"],
                "b_primary_vector": rec_b["primary_vector"],
                "b_secondary_vector": rec_b["secondary_vector"],
                "a_vectors": "; ".join(sorted(rec_a["vectors"])),
                "b_vectors": "; ".join(sorted(rec_b["vectors"])),
                "vector_overlap": "Y" if vector_overlap else "N",
                "a_attempts": "; ".join(sorted(rec_a["attempts"])),
                "b_attempts": "; ".join(sorted(rec_b["attempts"])),
                "a_conversational": rec_a["conversational"],
                "b_conversational": rec_b["conversational"],
                "a_severity": rec_a["severity"],
                "b_severity": rec_b["severity"],
            })
    print(f"Wrote {report_path}")
    print(f"Wrote {disagreements_path}")


def default_name(path: Path) -> str:
    return path.stem.replace("Round 3 - Jailbreak (newest)", "").strip(" -_") or path.stem


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--human-a", type=Path)
    parser.add_argument("--human-b", type=Path)
    parser.add_argument("--llm-codings", type=Path)
    parser.add_argument("--human", type=Path)
    parser.add_argument("--name-a")
    parser.add_argument("--name-b")
    parser.add_argument("--max-conversations", type=int, default=15)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.human_a or args.human_b:
        if not args.human_a or not args.human_b:
            parser.error("--human-a and --human-b must be provided together")
        a = load_round4_human(args.human_a, args.max_conversations)
        b = load_round4_human(args.human_b, args.max_conversations)
        compare(a, b, args.name_a or default_name(args.human_a), args.name_b or default_name(args.human_b), args.out_dir)
        return

    if not args.llm_codings or not args.human:
        parser.error("provide either --human-a/--human-b or --llm-codings/--human")
    llm = load_llm(args.llm_codings)
    human = load_round4_human(args.human, args.max_conversations)
    compare(human, llm, args.name_a or default_name(args.human), args.name_b or "LLM", args.out_dir)


if __name__ == "__main__":
    main()
