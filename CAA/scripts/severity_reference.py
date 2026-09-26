"""Human-reference comparison that preserves abstentions and execution failures."""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from CAA.scripts.caa_common import resolve_project_path
from CAA.scripts.severity_contract import SCHEMA_VERSION, LABELS, load_jsonl, rate, write_csv, write_json


def resolve_codings_file(path: Path) -> Path:
    path = resolve_project_path(path)
    if path.is_dir():
        # Human edits to CSV are authoritative, even if a stale JSONL coexists.
        for name in ("codings.csv", "codings.jsonl"):
            if (path / name).is_file():
                return path / name
        raise FileNotFoundError(f"No codings.csv or codings.jsonl in {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Missing codings: {path}")
    return path


def reference_severity(value):
    if value is None or value == "":
        return None
    if type(value) is int and value in range(4):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-3](?:\s*-\s*.*)?", value.strip()):
        return int(value.strip()[0])
    raise ValueError(f"Invalid reference/export severity: {value!r}")


def load_coding_map(path: Path) -> dict:
    if path.suffix.lower() == ".jsonl":
        records = load_jsonl(path)
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            records = list(csv.DictReader(handle))
    else:
        raise ValueError(f"Unsupported coding file: {path}")
    results = {}
    for row in records:
        rid = str(row.get("id", "")).strip()
        if not rid:
            raise ValueError(f"Missing ID in {path}")
        version = row.get("schema_version")
        if version and version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema: {version}")
        output = row.get("llm_output") or row
        severity = reference_severity(output.get("severity"))
        missing_judgment = "llm_output" in row and row["llm_output"] is None
        status = row.get("execution_status") or ("error" if row.get("error") or missing_judgment else "completed")
        success = None if severity is None else severity > 0
        if status != "completed":
            severity, success = None, None
        # A parent can have a confirmed positive while its exact max is unresolved.
        if version == SCHEMA_VERSION and row.get("assessment") == "success":
            success = True
        if rid in results and path.suffix.lower() == ".csv":
            raise ValueError(f"Duplicate coding ID {rid!r} in {path}")
        results[rid] = {"severity": severity, "success": success, "execution_status": status,
                        "assessment": row.get("assessment") or ("neutral" if severity is None and status == "completed" else None),
                        "reasoning": output.get("reasoning", "")}
    return results


def compare_with_reference(current_path: Path, reference_path: Path, out_dir: Path) -> dict:
    reference_file = resolve_codings_file(reference_path)
    current = load_coding_map(current_path)
    reference = load_coding_map(reference_file)
    graded_reference = {rid: row for rid, row in reference.items() if row["severity"] is not None and row["execution_status"] == "completed"}
    counts = Counter()
    confusion = defaultdict(Counter)
    rows = []
    for rid, human in sorted(graded_reference.items()):
        predicted = current.get(rid, {"severity": None, "success": None, "execution_status": "pending", "assessment": None, "reasoning": ""})
        p, h = predicted["severity"], human["severity"]
        ps, hs = predicted["success"], h > 0
        counts["reference_positive" if hs else "reference_safe"] += 1
        bucket = "resolved" if ps is not None else "neutral" if predicted["execution_status"] == "completed" else "execution_unresolved"
        counts[bucket] += 1
        counts[f"{bucket}_on_human_{'positive' if hs else 'safe'}"] += 1
        exact = p is not None and p == h
        binary = ps is not None and ps == hs
        counts["exact"] += exact
        counts["binary"] += binary
        counts["positive_exact"] += bool(exact and hs)
        if p is not None:
            counts["numeric"] += 1
            counts["distance"] += abs(p - h)
        if ps is not None:
            counts["tp" if ps and hs else "fp" if ps else "fn" if hs else "tn"] += 1
        confusion[LABELS[h]][LABELS[p] if p is not None else bucket] += 1
        rows.append({"id": rid, "predicted_severity": LABELS[p] if p is not None else "",
                     "reference_severity": LABELS[h], "exact_match": exact,
                     "predicted_success": ps, "reference_success": hs, "binary_match": binary,
                     "prediction_bucket": bucket, "execution_status": predicted["execution_status"],
                     "predicted_reasoning": predicted["reasoning"], "reference_reasoning": human["reasoning"]})
    n = len(graded_reference)
    tp, fp, fn, tn = (counts[k] for k in ("tp", "fp", "fn", "tn"))
    precision, recall, specificity = rate(tp, tp + fp), rate(tp, tp + fn), rate(tn, tn + fp)
    summary = {"schema_version": SCHEMA_VERSION, "reference_path": str(reference_file),
               "n_current": len(current), "n_reference": len(reference), "n_reference_graded": n,
               "n_reference_ungraded": len(reference) - n,
               "n_overlap": len(set(current) & set(graded_reference)),
               "n_missing_predictions": len(set(graded_reference) - set(current)),
               "n_predictions_without_reference": len(set(current) - set(graded_reference)),
               "n_resolved": counts["resolved"], "n_neutral": counts["neutral"],
               "n_execution_unresolved": counts["execution_unresolved"],
               "binary_coverage": rate(counts["resolved"], n), "numeric_severity_coverage": rate(counts["numeric"], n),
               "exact_severity_matches": counts["exact"], "exact_severity_agreement": rate(counts["exact"], n),
               "binary_success_matches": counts["binary"], "binary_success_agreement": rate(counts["binary"], n),
               "resolved_binary_success_agreement": rate(counts["binary"], counts["resolved"]),
               "severity_mae": rate(counts["distance"], counts["numeric"]),
               "reference_n_success": counts["reference_positive"], "predicted_n_success": tp + fp,
               "reference_positive_exact_severity_matches": counts["positive_exact"],
               "reference_positive_exact_severity_agreement": rate(counts["positive_exact"], counts["reference_positive"]),
               "true_positive": tp, "true_negative": tn, "false_positive": fp, "false_negative": fn,
               "positive_precision": precision, "positive_recall": recall,
               "operational_positive_recall": rate(tp, counts["reference_positive"]),
               "positive_f1": rate(2 * tp, 2 * tp + fp + fn), "safe_specificity": specificity,
               "binary_balanced_accuracy": round((recall + specificity) / 2, 6) if recall is not None and specificity is not None else None,
               "neutral_on_human_safe": counts["neutral_on_human_safe"],
               "neutral_on_human_positive": counts["neutral_on_human_positive"],
               "execution_unresolved_on_human_safe": counts["execution_unresolved_on_human_safe"],
               "execution_unresolved_on_human_positive": counts["execution_unresolved_on_human_positive"],
               "severity_confusion_matrix": {expected: dict(confusion[expected]) for expected in LABELS}}
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "reference_comparison.json", summary)
    write_csv(out_dir / "reference_comparison.csv", rows,
              tuple(rows[0]) if rows else ("id", "predicted_severity", "reference_severity", "prediction_bucket"))
    return summary
