"""Run the Round 5 phase/phrase CAB build and stats pipeline."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.new_cab import build_phase_phrase_bank, compute_phase_phrase_stats


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = PROJECT_ROOT / "raw_cab_round5_reviewed_all"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the phase phrase CAB and compute phrase-only stats.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--top-k", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_args = argparse.Namespace(
        assignments=args.out_dir / "category_assignments.csv",
        reviewed_success=build_phase_phrase_bank.DEFAULT_REVIEWED_SUCCESS,
        seg_results_dir=build_phase_phrase_bank.DEFAULT_SEG_RESULTS_DIR,
        out_dir=args.out_dir,
    )
    assignments = build_phase_phrase_bank.load_assignments(build_args.assignments)
    reviewed_success = build_phase_phrase_bank.load_reviewed_success(build_args.reviewed_success)
    llm_by_pool = {
        "unsuccess_attack": build_phase_phrase_bank.load_llm_phase_segments(build_args.seg_results_dir, "unsuccess_attack"),
        "no_attack": build_phase_phrase_bank.load_llm_phase_segments(build_args.seg_results_dir, "no_attack"),
    }
    records, issues = build_phase_phrase_bank.build_records(assignments, reviewed_success, llm_by_pool)
    build_phase_phrase_bank.write_jsonl(args.out_dir / "phrase_conversation_bank.jsonl", records)
    build_phase_phrase_bank.write_csv(
        args.out_dir / "phrase_conversation_bank.csv",
        build_phase_phrase_bank.flatten_records(records),
        [
            "conversation_id",
            "source_pool",
            "primary_attack_vector",
            "secondary_attack_vector",
            "attempt",
            "conversational",
            "severity",
            "phrase_count",
            "phase_trajectory",
        ],
    )
    build_phase_phrase_bank.write_csv(
        args.out_dir / "phrase_conversation_bank_issues.csv",
        issues,
        ["id", "source_pool", "severity", "issue", "detail"],
    )

    stats_out_dir = args.out_dir / "stats"
    stats_records = compute_phase_phrase_stats.load_bank(args.out_dir / "phrase_conversation_bank.jsonl")
    stats_out_dir.mkdir(parents=True, exist_ok=True)
    compute_phase_phrase_stats.write_csv(
        stats_out_dir / "all_phrase_topk.csv",
        compute_phase_phrase_stats.compute_all_phrase_topk(stats_records, args.top_k),
        ["scope", "rank", "phase", "phrase_count", "proportion_of_phrases", "conversation_count", "proportion_of_conversations"],
    )
    compute_phase_phrase_stats.write_csv(
        stats_out_dir / "success_phase_action_topk.csv",
        compute_phase_phrase_stats.compute_success_phase_action_topk(stats_records, args.top_k),
        [
            "scope", "rank", "phase", "action", "phrase_count", "proportion_of_success_phrases",
            "conversation_count", "proportion_of_success_conversations", "all_phrase_count",
            "all_conversation_count", "success_rate_among_conversations_with_phase",
        ],
    )
    compute_phase_phrase_stats.write_csv(
        stats_out_dir / "success_phase_trajectory_topk.csv",
        compute_phase_phrase_stats.compute_phase_trajectory_topk(stats_records, args.top_k),
        [
            "scope", "rank", "phase_trajectory", "count", "proportion_of_success_trajectories",
            "conversation_count", "proportion_of_success_conversations", "all_conversation_count",
            "success_rate_among_conversations_with_pattern",
        ],
    )
    compute_phase_phrase_stats.write_csv(
        stats_out_dir / "success_phase_transition_topk.csv",
        compute_phase_phrase_stats.compute_phase_transition_topk(stats_records, args.top_k),
        [
            "scope", "rank", "source", "target", "transition", "count",
            "proportion_of_all_transitions", "proportion_of_success_transitions",
            "conditional_probability", "conversation_count", "proportion_of_success_conversations",
            "all_transition_count", "all_conversation_count", "success_rate_among_conversations_with_pattern",
        ],
    )
    compute_phase_phrase_stats.write_json(stats_out_dir / "cab_stats_summary.json", compute_phase_phrase_stats.compute_summary(stats_records))

    print(f"Wrote {len(records)} phrase CAB records to {args.out_dir}")
    print(f"Bank issues: {len(issues)}")
    print(f"Wrote phrase-only stats to {stats_out_dir}")


if __name__ == "__main__":
    main()
