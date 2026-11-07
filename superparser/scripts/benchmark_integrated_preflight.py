"""Paired *full Parser.parse* wall-clock comparison for opt-in fast preflight.

Unlike the earlier classifier microbenchmarks, these runs include lexical
preparation, dialogue dispatch, chart recognition, k-best and materialization.
They are independent replays of source-balanced frozen cases, not replacements
for their canonical results. Small paired timing samples are NOT evidence of
speedup. Every replay goes via parse_corpus_case -> Parser.parse.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import signal
from statistics import median
from time import perf_counter_ns
from typing import Any

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import (
    EXPECTED_500_COHORT_SHA256, SentenceDeadline, _deadline, classify, select_cases,
)
from seman_parser.engine import Parser, ParserResources


ROOT = Path(__file__).resolve().parents[1]
# 1 strict residual, 2 strict successes, 2 independently pinned marked successes.
SPECS = (
    (64, False),
    (76, False),
    (244, False),
    (463, True),
    (480, True),
)


def _med(values: list[float]) -> float | None:
    return round(median(values), 3) if values else None


def summarize(rows: list[dict[str, Any]], repeats: int) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    parity = 0
    censored = 0
    informative = 0
    for row in rows:
        if row["outcome"] == "deadline_censored":
            censored += 1
        else:
            groups["preflight_on" if row["preflight_enabled"] else "baseline"].append(
                row["full_parse_ms"])
            if row["preflight_enabled"]:
                informative += row.get("selected_tree_proven_marked_relation_count", 0)
    for index, _marked in SPECS:
        for repeat in range(repeats):
            pair = [r for r in rows if r["index"] == index and r["repeat"] == repeat]
            if len(pair) != 2:
                raise ValueError(f"Paired comparison absent for {index}/{repeat}")
            if all(row["outcome"] != "deadline_censored" for row in pair):
                if (pair[0]["outcome"] != pair[1]["outcome"]
                        or pair[0]["best_signature"] != pair[1]["best_signature"]):
                    raise AssertionError(
                        f"Opt-in preflight changed parse outcome or selected tree at {index}")
                parity += 1
    return {
        "schema": "seman2-integrated-preflight-timing-v1",
        "frozen_cohort_sha256": EXPECTED_500_COHORT_SHA256,
        "indices": [index for index, _ in SPECS],
        "repeat_count": repeats,
        "total_independent_replays": len(rows),
        "uncensored_matched_pairs": parity,
        "deadline_censored_runs": censored,
        "selected_tree_marked_proof_witnesses_in_opt_in_replays": informative,
        "full_parse_median_ms": {k: _med(v) for k, v in sorted(groups.items())},
        "warm_lattice_cache_not_cold_start": True,
        "timings_include_public_parse_and_reused_lexical_lookup": True,
        "baseline_original_500_not_replaced": True,
        "no_search_policy_change": True,
        "not_a_measured_speedup": True,
        "not_statistically_powered": True,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not 1 <= args.repeats <= 3:
        raise ValueError("Use 1..3 repeated pairs to bound CI time")
    if args.deadline_seconds <= 0 or args.max_items <= 0 or args.kbest_work_limit <= 0:
        raise ValueError("Parsing budgets must be positive")
    if sha256(args.cohort.read_bytes()).hexdigest() != EXPECTED_500_COHORT_SHA256:
        raise ValueError("Paired benchmark requires the exact frozen 500-case cohort")
    cases, _ = select_cases(500)
    if len(cases) != 500:
        raise ValueError("Frozen cohort needs 500 source cases")
    parser = Parser(
        ParserResources.from_dir(ROOT / "data", wordnet_dict=args.wordnet_dir),
        cache_size=512, max_items=args.max_items,
    )
    parser.parse("John opened the box.")  # warm initial grammar/lexical initialization
    rows: list[dict[str, Any]] = []
    handler = signal.signal(signal.SIGALRM, _deadline)
    try:
        for index, marked in SPECS:
            case = cases[index]
            case_id = str(case["book_id"]) + ":" + sha256(
                case.get("source_text", case["text"]).encode("utf8")
            ).hexdigest()[:16]
            for repeat in range(args.repeats):
                order = (False, True) if repeat % 2 == 0 else (True, False)
                for enabled in order:
                    started = perf_counter_ns()
                    timer_started = False
                    try:
                        signal.setitimer(signal.ITIMER_REAL, args.deadline_seconds)
                        timer_started = True
                        prepared, lattice, parsed = parse_corpus_case(
                            parser, case, max_items=args.max_items,
                            kbest_work_limit=args.kbest_work_limit,
                            allow_marked_deviations=marked,
                            preflight_diagnostics=enabled,
                        )
                        elapsed = (perf_counter_ns() - started) / 1e6
                        if parsed.text != prepared.analysis_text:
                            raise AssertionError("Source-balanced text was changed")
                        status = classify(parsed.completed, parsed.stats)
                        selected = parsed.best() if parsed.completed else None
                        evidence = parsed.stats.get("fast_preflight")
                        if enabled and (
                                not isinstance(evidence, dict)
                                or not evidence.get("lexical_lattice_reused")
                                or not evidence.get("first_observed_before_syntax")):
                            raise AssertionError("Opt-in integrated preflight missing")
                        if not enabled and evidence is not None:
                            raise AssertionError("Default parse unexpectedly collected preflight")
                        rows.append({
                            "index": index, "case_id": case_id,
                            "marked_opt_in": marked, "preflight_enabled": enabled,
                            "repeat": repeat, "full_parse_ms": round(elapsed, 3),
                            "outcome": status,
                            "best_signature": repr(selected.signature()) if selected else None,
                            "best_rule": selected.rule_id if selected else None,
                            "selected_tree_proven_marked_relation_count": (
                                evidence["selected_tree_proven_marked_relation_count"]
                                if evidence is not None else None),
                            "existing_lattice_probe_us": (
                                evidence["existing_lattice_probe_us"]
                                if evidence is not None else None),
                            "selected_tree_evidence_us": (
                                evidence["selected_tree_evidence_us"]
                                if evidence is not None else None),
                            "parser_result_was_not_modified": True,
                        })
                    except SentenceDeadline:
                        elapsed = (perf_counter_ns() - started) / 1e6
                        rows.append({
                            "index": index, "case_id": case_id,
                            "marked_opt_in": marked, "preflight_enabled": enabled,
                            "repeat": repeat, "full_parse_ms": round(elapsed, 3),
                            "outcome": "deadline_censored",
                            "best_signature": None,
                        })
                    finally:
                        if timer_started:
                            signal.setitimer(signal.ITIMER_REAL, 0)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)
    summary = summarize(rows, args.repeats)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "integrated_preflight_timing.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf8")
    (args.out_dir / "integrated_preflight_timing_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    report = [
        "# Full-pipeline cost of opt-in preflight", "",
        "Measured using only public Parser.parse through the quote-balanced",
        "parse_corpus_case gateway. Each pair replays the same frozen case",
        "with identical budgets, marked mode, and lexical cache state.", "",
        f"Uncensored parity pairs: {summary['uncensored_matched_pairs']}.",
        f"Deadline-censored runs: {summary['deadline_censored_runs']}.",
        f"Full parse median without preflight: "
        f"{summary['full_parse_median_ms'].get('baseline')} ms.",
        f"Full parse median with preflight: "
        f"{summary['full_parse_median_ms'].get('preflight_on')} ms.", "",
        "This is a small warm-cache paired *overhead* audit, not proof that",
        "preflight accelerates recognition: no routing or early exit is enabled.",
        "A selected-tree dependency is evidenced only by a checked explicit",
        "marked grammar rule in a completed tree; never by adjacent candidates.",
    ]
    (args.out_dir / "integrated_preflight_timing.md").write_text(
        "\n".join(report) + "\n", encoding="utf8")
    print("INTEGRATED_PREFLIGHT_TIMING", json.dumps(summary), flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", type=Path, required=True)
    ap.add_argument("--wordnet-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--max-items", type=int, default=50000)
    ap.add_argument("--kbest-work-limit", type=int, default=500000)
    ap.add_argument("--deadline-seconds", type=float, default=10.0)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
