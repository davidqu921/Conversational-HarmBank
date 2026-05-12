"""
evaluate.py
===========
Compare LLM coding to human coding and produce three artifacts:

  1. agreement_report.md  — Cohen's kappa per dimension (vector, subtype, attempt,
                            conversational, success), broken down by human coder.
                            Also reports the human-vs-human ceiling on the IRR set.
  2. confusion_matrices.xlsx  — one sheet per dimension; rows are LLM labels, cols
                                are human labels (aggregated across coders, IRR set).
  3. discrepancies.xlsx       — every conversation where the LLM disagrees with
                                the majority human label, with full transcript
                                text, both codings, and LLM reasoning, for spot-check.

Multi-label dimensions (vector, subtype, attempt) are evaluated by:
  - Treating each label in the codebook as a binary present/absent variable.
  - Computing Cohen's kappa per label, then macro-averaging (mean across labels).
  - Confusion matrix is computed by the dominant label per coder (one label per coder
    per conversation), since cross-tabulating multi-label data is non-standard.

Single-label dimensions (conversational, success) use plain Cohen's kappa.

CLI:
    python -m scripts.evaluate \\
        --llm-codings coding_results/iter1/codings.jsonl \\
        --human-coding data_prep/ground_truth.csv \\
        --transcripts data_prep/transcripts.jsonl \\
        --out-dir evaluation/iter1
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Label inventories — must match references/codebook.md
ATTACK_VECTORS = ["Brute Force", "Disguised Intent", "Role Play", "Structured Response", "AI Attack", "No Attempt"]
SUBTYPES = [
    "One Shot", "Overwhelming", "Out of Context",
    "Testing", "Joking", "Wordplay",
    "Fake Persona", "Emotional Manipulation", "Threats", "Fake Scenario",
    "Different Language", "Text Continuation", "Code/Programming", "Prompt Injection",
    "Privileges", "Re-prompting", "Appeal to Underlying AI",
]
ATTEMPTS = [
    "Swearing", "Slur", "Inappropriate Topics", "Bias", "Political/Social",
    "Incorrect Information", "Break Character", "Abnormal", "General Break",
]
CONV_LABELS = ["Single Prompt", "Multi Prompt", "Conversational"]
SUCCESS_LABELS = ["Yes - Broken", "Maybe", "No - Safe"]


def normalize(s: str | None) -> str:
    """Loose label normalization to handle minor spelling variants in human data."""
    if not s:
        return ""
    s = s.strip()
    # Common variants observed in human-coding sheets
    aliases = {
        "no attempt": "No Attempt",
        "out of context": "Out of Context",
        "appeal to ai": "Appeal to Underlying AI",
        "appeal to underlying ai": "Appeal to Underlying AI",
        "privileges": "Privileges",
        "privilages": "Privileges",
        "diff language": "Different Language",
        "inapp topic": "Inappropriate Topics",
        "incorrect info": "Incorrect Information",
        "incorrect information": "Incorrect Information",
        "general break": "General Break",
    }
    return aliases.get(s.lower(), s)


# ----------------------- Loaders -----------------------

def load_llm(jsonl_path: Path) -> dict[str, dict]:
    """Returns {conversation_id: {vectors:set, subtypes:set, attempts:set, conv:str, success:str, reasoning:str}}."""
    out = {}
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            rec = json.loads(line)
            if rec.get("error") or not rec.get("llm_output"):
                continue
            cid = str(rec["id"])
            o = rec["llm_output"]
            vecs = set()
            subs = set()
            atts = set()
            for c in o.get("codings", []):
                vec = normalize(c.get("attack_vector"))
                if vec: vecs.add(vec)
                for sub in c.get("subtypes") or []:
                    code = normalize(sub.get("code") if isinstance(sub, dict) else sub)
                    if code and code != "Other":
                        subs.add(code)
                for att in c.get("attempts") or []:
                    a = normalize(att)
                    if a and a != "Other":
                        atts.add(a)
            out[cid] = {
                "vectors": vecs,
                "subtypes": subs,
                "attempts": atts,
                "conv": normalize(o.get("conversational")),
                "success": normalize(o.get("success")),
                "reasoning": o.get("reasoning", ""),
            }
    return out


def load_human(csv_path: Path) -> dict[tuple[str, str], dict]:
    """Returns {(coder, conversation_id): {vectors:set, subtypes:set, attempts:set, conv, success}}.

    Multiple rows in the CSV for the same (coder, id) pair are merged (a coder can
    record multiple attack vectors per conversation, one row each).
    """
    out: dict[tuple[str, str], dict] = {}
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["coder"], row["id"])
            entry = out.setdefault(key, {"vectors": set(), "subtypes": set(), "attempts": set(), "conv": "", "success": ""})
            v = normalize(row["attack_vector"])
            if v: entry["vectors"].add(v)
            s = normalize(row["subtype"])
            if s and s.lower() not in ("no attempt", ""):
                entry["subtypes"].add(s)
            a = normalize(row["attempt"])
            if a and a.lower() not in ("no attempt", ""):
                entry["attempts"].add(a)
            if row["conversational"] and not entry["conv"]:
                entry["conv"] = normalize(row["conversational"])
            if row["success"] and not entry["success"]:
                entry["success"] = normalize(row["success"])
    return out


def load_transcripts(jsonl_path: Path) -> dict[str, str]:
    out = {}
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            t = json.loads(line)
            out[str(t["id"])] = t.get("transcript_text", "")
    return out


# ----------------------- Kappa -----------------------

def cohen_kappa(a: list, b: list) -> float:
    """Standard Cohen's kappa for two parallel label lists."""
    assert len(a) == len(b) and len(a) > 0
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = Counter(a); pb = Counter(b)
    pe = sum((pa[l] / n) * (pb[l] / n) for l in labels)
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def binary_kappa_per_label(label_pool: list[str], a_sets: list[set], b_sets: list[set]) -> dict[str, float]:
    """For each label in pool, treat presence/absence as binary, compute kappa."""
    out = {}
    for label in label_pool:
        a = ["Y" if label in s else "N" for s in a_sets]
        b = ["Y" if label in s else "N" for s in b_sets]
        # If neither rater ever uses this label, kappa is undefined
        if set(a) == {"N"} and set(b) == {"N"}:
            out[label] = float("nan")
            continue
        out[label] = cohen_kappa(a, b)
    return out


def macro_kappa(per_label: dict[str, float]) -> float:
    vals = [v for v in per_label.values() if v == v]  # filter NaN
    return sum(vals) / len(vals) if vals else float("nan")


# ----------------------- Confusion matrix -----------------------

def confusion_matrix(rows_a: list[str], rows_b: list[str], labels: list[str]) -> list[list[int]]:
    idx = {l: i for i, l in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for x, y in zip(rows_a, rows_b):
        if x in idx and y in idx:
            matrix[idx[x]][idx[y]] += 1
    return matrix


# ----------------------- Main -----------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-codings", required=True, type=Path)
    ap.add_argument("--human-coding", required=True, type=Path)
    ap.add_argument("--transcripts", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading LLM codings...", file=sys.stderr)
    llm = load_llm(args.llm_codings)
    print(f"  {len(llm)} LLM-coded conversations", file=sys.stderr)

    print("Loading human coding...", file=sys.stderr)
    human = load_human(args.human_coding)
    coders = sorted({k[0] for k in human.keys()})
    coded_ids = sorted({k[1] for k in human.keys()})
    print(f"  {len(human)} (coder, conv) entries from {len(coders)} coders covering {len(coded_ids)} conversations", file=sys.stderr)

    transcripts = load_transcripts(args.transcripts)

    # Eval set: conversations that are in BOTH human coding and LLM coding
    eval_ids = sorted(set(coded_ids) & set(llm.keys()))
    print(f"  {len(eval_ids)} conversations have both LLM and human coding (eval set)", file=sys.stderr)
    if not eval_ids:
        sys.exit("no overlap between LLM coding and human coding — cannot evaluate")

    # ---------- Agreement: LLM vs each coder ----------
    report_lines = ["# Agreement Report", ""]
    report_lines.append(f"- Eval set: **{len(eval_ids)} conversations** with both LLM and human coding")
    report_lines.append(f"- Human coders: {', '.join(coders)}")
    report_lines.append("")

    def gather_aligned(coder: str, ids: list[str]):
        """Return aligned (human_records, llm_records) for conversations the coder coded."""
        h_recs, l_recs = [], []
        for cid in ids:
            if (coder, cid) in human and cid in llm:
                h_recs.append(human[(coder, cid)])
                l_recs.append(llm[cid])
        return h_recs, l_recs

    # Vector kappa per coder
    report_lines.append("## Cohen's κ per dimension, LLM vs each human coder")
    report_lines.append("")
    report_lines.append("| Coder | n | Vector (macro) | Subtype (macro) | Attempt (macro) | Conversational | Success |")
    report_lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for coder in coders:
        h, l = gather_aligned(coder, eval_ids)
        if not h: continue
        kv = macro_kappa(binary_kappa_per_label(ATTACK_VECTORS, [r["vectors"] for r in h], [r["vectors"] for r in l]))
        ks = macro_kappa(binary_kappa_per_label(SUBTYPES, [r["subtypes"] for r in h], [r["subtypes"] for r in l]))
        ka = macro_kappa(binary_kappa_per_label(ATTEMPTS, [r["attempts"] for r in h], [r["attempts"] for r in l]))
        kc = cohen_kappa([r["conv"] or "<blank>" for r in h], [r["conv"] or "<blank>" for r in l])
        ksu = cohen_kappa([r["success"] or "<blank>" for r in h], [r["success"] or "<blank>" for r in l])
        report_lines.append(f"| {coder} | {len(h)} | {kv:.3f} | {ks:.3f} | {ka:.3f} | {kc:.3f} | {ksu:.3f} |")

    # Pooled (all human entries, treating each (coder, conv) as a row)
    h_all, l_all = [], []
    for coder in coders:
        for cid in eval_ids:
            if (coder, cid) in human:
                h_all.append(human[(coder, cid)])
                l_all.append(llm[cid])
    kv = macro_kappa(binary_kappa_per_label(ATTACK_VECTORS, [r["vectors"] for r in h_all], [r["vectors"] for r in l_all]))
    ks = macro_kappa(binary_kappa_per_label(SUBTYPES, [r["subtypes"] for r in h_all], [r["subtypes"] for r in l_all]))
    ka = macro_kappa(binary_kappa_per_label(ATTEMPTS, [r["attempts"] for r in h_all], [r["attempts"] for r in l_all]))
    kc = cohen_kappa([r["conv"] or "<blank>" for r in h_all], [r["conv"] or "<blank>" for r in l_all])
    ksu = cohen_kappa([r["success"] or "<blank>" for r in h_all], [r["success"] or "<blank>" for r in l_all])
    report_lines.append(f"| **Pooled** | **{len(h_all)}** | **{kv:.3f}** | **{ks:.3f}** | **{ka:.3f}** | **{kc:.3f}** | **{ksu:.3f}** |")
    report_lines.append("")

    # ---------- Per-label kappa (vector & success — most actionable) ----------
    report_lines.append("## Per-label κ (pooled across coders)")
    report_lines.append("")
    report_lines.append("### Attack Vector")
    pl = binary_kappa_per_label(ATTACK_VECTORS, [r["vectors"] for r in h_all], [r["vectors"] for r in l_all])
    report_lines.append("| Label | κ | LLM positives | Human positives |")
    report_lines.append("|---|---:|---:|---:|")
    for lab in ATTACK_VECTORS:
        n_llm = sum(1 for r in l_all if lab in r["vectors"])
        n_hum = sum(1 for r in h_all if lab in r["vectors"])
        k = pl[lab]
        report_lines.append(f"| {lab} | {k:.3f} | {n_llm} | {n_hum} |")
    report_lines.append("")

    report_lines.append("### Subtype (top by human frequency)")
    pl = binary_kappa_per_label(SUBTYPES, [r["subtypes"] for r in h_all], [r["subtypes"] for r in l_all])
    sub_freq = sorted(SUBTYPES, key=lambda l: -sum(1 for r in h_all if l in r["subtypes"]))
    report_lines.append("| Label | κ | LLM positives | Human positives |")
    report_lines.append("|---|---:|---:|---:|")
    for lab in sub_freq[:12]:
        n_llm = sum(1 for r in l_all if lab in r["subtypes"])
        n_hum = sum(1 for r in h_all if lab in r["subtypes"])
        k = pl[lab]
        report_lines.append(f"| {lab} | {k:.3f} | {n_llm} | {n_hum} |")
    report_lines.append("")

    # ---------- Human ceiling on IRR set ----------
    irr_ids = sorted([cid for cid in eval_ids if sum(1 for c in coders if (c, cid) in human) >= 3])
    if irr_ids:
        report_lines.append(f"## Human-vs-human ceiling (IRR set, n={len(irr_ids)})")
        report_lines.append("")
        report_lines.append("Pairwise mean κ across all coder pairs on the IRR conversations.")
        report_lines.append("")
        for dim_name, getter, pool in [
            ("Attack Vector (macro)", lambda r: r["vectors"], ATTACK_VECTORS),
            ("Subtype (macro)", lambda r: r["subtypes"], SUBTYPES),
            ("Attempt (macro)", lambda r: r["attempts"], ATTEMPTS),
        ]:
            pair_ks = []
            for i, ca in enumerate(coders):
                for cb in coders[i+1:]:
                    a_sets, b_sets = [], []
                    for cid in irr_ids:
                        if (ca, cid) in human and (cb, cid) in human:
                            a_sets.append(getter(human[(ca, cid)]))
                            b_sets.append(getter(human[(cb, cid)]))
                    if a_sets:
                        pair_ks.append(macro_kappa(binary_kappa_per_label(pool, a_sets, b_sets)))
            mean_k = sum(pair_ks) / len(pair_ks) if pair_ks else float("nan")
            report_lines.append(f"- **{dim_name}**: mean pairwise κ = {mean_k:.3f}  (over {len(pair_ks)} pairs)")

        for dim_name, field in [("Conversational", "conv"), ("Success", "success")]:
            pair_ks = []
            for i, ca in enumerate(coders):
                for cb in coders[i+1:]:
                    a, b = [], []
                    for cid in irr_ids:
                        if (ca, cid) in human and (cb, cid) in human:
                            va = human[(ca, cid)][field] or "<blank>"
                            vb = human[(cb, cid)][field] or "<blank>"
                            a.append(va); b.append(vb)
                    if a:
                        pair_ks.append(cohen_kappa(a, b))
            mean_k = sum(pair_ks) / len(pair_ks) if pair_ks else float("nan")
            report_lines.append(f"- **{dim_name}**: mean pairwise κ = {mean_k:.3f}  (over {len(pair_ks)} pairs)")

    (args.out_dir / "agreement_report.md").write_text("\n".join(report_lines))
    print(f"  -> {args.out_dir / 'agreement_report.md'}", file=sys.stderr)

    # ---------- Confusion matrices (XLSX) ----------
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        def write_matrix(sheet_name, labels, llm_rows, human_rows):
            ws = wb.create_sheet(sheet_name)
            ws.cell(1, 1, f"{sheet_name}: rows=LLM, cols=human (any coder)")
            for j, lab in enumerate(labels, 2):
                ws.cell(2, j, lab)
            for i, lab in enumerate(labels, 3):
                ws.cell(i, 1, lab)
            mat = confusion_matrix(llm_rows, human_rows, labels)
            for i, row in enumerate(mat, 3):
                for j, v in enumerate(row, 2):
                    ws.cell(i, j, v)

        # For multi-label dims: we pick the *first* label per record (deterministic order: codebook order)
        def first_label(s: set, pool: list[str]) -> str:
            for lab in pool:
                if lab in s:
                    return lab
            return ""

        write_matrix("vector", ATTACK_VECTORS,
                     [first_label(r["vectors"], ATTACK_VECTORS) for r in l_all],
                     [first_label(r["vectors"], ATTACK_VECTORS) for r in h_all])
        write_matrix("subtype", SUBTYPES,
                     [first_label(r["subtypes"], SUBTYPES) for r in l_all],
                     [first_label(r["subtypes"], SUBTYPES) for r in h_all])
        write_matrix("attempt", ATTEMPTS,
                     [first_label(r["attempts"], ATTEMPTS) for r in l_all],
                     [first_label(r["attempts"], ATTEMPTS) for r in h_all])
        write_matrix("conversational", CONV_LABELS,
                     [r["conv"] for r in l_all], [r["conv"] for r in h_all])
        write_matrix("success", SUCCESS_LABELS,
                     [r["success"] for r in l_all], [r["success"] for r in h_all])

        wb.save(args.out_dir / "confusion_matrices.xlsx")
        print(f"  -> {args.out_dir / 'confusion_matrices.xlsx'}", file=sys.stderr)
    except ImportError:
        print("  (skipping confusion matrices — install openpyxl)", file=sys.stderr)

    # ---------- Discrepancies (XLSX) ----------
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Discrepancies"
        headers = ["conversation_id", "coder", "human_vectors", "llm_vectors", "human_subtypes", "llm_subtypes",
                   "human_attempts", "llm_attempts", "human_conv", "llm_conv", "human_success", "llm_success",
                   "agree_vector", "agree_subtype", "agree_success", "llm_reasoning", "transcript"]
        for j, h in enumerate(headers, 1):
            ws.cell(1, j, h)
        row = 2
        for coder in coders:
            for cid in eval_ids:
                if (coder, cid) not in human: continue
                h = human[(coder, cid)]; l = llm[cid]
                # Agreement: do they share at least one common label per dim?
                agree_vec = bool(h["vectors"] & l["vectors"])
                agree_sub = (not h["subtypes"] and not l["subtypes"]) or bool(h["subtypes"] & l["subtypes"])
                agree_suc = h["success"] == l["success"]
                if agree_vec and agree_sub and agree_suc:
                    continue  # only export disagreements
                values = [
                    cid, coder,
                    "; ".join(sorted(h["vectors"])), "; ".join(sorted(l["vectors"])),
                    "; ".join(sorted(h["subtypes"])), "; ".join(sorted(l["subtypes"])),
                    "; ".join(sorted(h["attempts"])), "; ".join(sorted(l["attempts"])),
                    h["conv"], l["conv"], h["success"], l["success"],
                    agree_vec, agree_sub, agree_suc,
                    l["reasoning"][:600],
                    transcripts.get(cid, "")[:3000],
                ]
                for j, v in enumerate(values, 1):
                    ws.cell(row, j, v)
                row += 1
        wb.save(args.out_dir / "discrepancies.xlsx")
        print(f"  -> {args.out_dir / 'discrepancies.xlsx'}  ({row-2} disagreements)", file=sys.stderr)
    except ImportError:
        print("  (skipping discrepancies xlsx — install openpyxl)", file=sys.stderr)


if __name__ == "__main__":
    main()
