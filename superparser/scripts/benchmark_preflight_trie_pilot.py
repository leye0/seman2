"""Frozen-cohort pilot: compare actual whole-parser latency for preflight trie routing.

Only source-balanced parse_corpus_case -> public Parser.parse is used. The
normal 500-case canonical pass runs separately before this experiment. This
pilot never trains thresholds or enables routing for ordinary Parser users.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import signal
from statistics import median
from time import perf_counter_ns
from typing import Any

from research.verbnet_lr.corpus_pipeline import parse_corpus_case, prepare_corpus_input
from scripts.diagnose_novel_parses import (
    EXPECTED_500_COHORT_SHA256, SentenceDeadline, _deadline, classify, select_cases,
)
from seman_parser.engine import Parser, ParserResources
from seman_parser.fast_preflight import PreflightTriePolicy, fast_preflight

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "seman2-preflight-trie-pilot-v1"


def _take_evenly(indices: list[int], count: int) -> list[int]:
    if count < 0 or count > len(indices):
        raise ValueError("Invalid sample count for eligible cases")
    return [indices[(2 * n + 1) * len(indices) // (2 * count)]
            for n in range(count)] if count else []


def select_pilot(
    cases: list[dict[str, Any]], *,
    minimum_tokens: int = 17,
    routed_count: int = 12,
    control_count: int = 6,
) -> list[dict[str, Any]]:
    """Choose on *surface inputs alone*, never canonical completion labels."""
    policy = PreflightTriePolicy(minimum_tokens=minimum_tokens)
    routed = []
    not_routed = []
    for i, case in enumerate(cases):
        prepared = prepare_corpus_input(case)
        probe = fast_preflight(prepared.analysis_text)
        accepted = (
            probe.token_count >= policy.minimum_tokens
            and "dialogue_or_quote_surface" not in probe.signals
            and any(signal in probe.signals for signal in policy.route_on)
        )
        (routed if accepted else not_routed).append(i)
    # Two independently pinned quote controls must never be routed. They
    # are not used to set thresholds and are both strict-mode residuals.
    protected = [i for i in (463, 480) if i < len(cases)]
    if any(i not in not_routed for i in protected):
        raise AssertionError("A pinned quote/marked case entered trie route")
    if control_count < len(protected):
        raise ValueError("Not enough control slots for protected quote cases")
    controls_available = [i for i in not_routed if i not in protected]
    sampled = _take_evenly(routed, routed_count)
    control_sample = protected + _take_evenly(
        controls_available, control_count - len(protected))
    selected = sorted(set(sampled + control_sample))
    if len(selected) != routed_count + control_count:
        raise AssertionError("Duplicate pilot samples")
    return [{
        "index": i,
        "expected_route": "trie" if i in sampled else "canonical",
        "selection": "preflight_surface_only_without_outcome_labels",
    } for i in selected]


def summarize(rows: list[dict[str, Any]],
              pilot: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for record in rows:
        grouped.setdefault((record["index"], record["repeat"]), []).append(record)
    if len(grouped) != len(pilot) * (len(rows) // (len(pilot) * 2)):
        raise ValueError("Uneven pair coverage")
    pairs = []
    for (index, repeat), pair in sorted(grouped.items()):
        if len(pair) != 2 or {r["policy"] for r in pair} != {"canonical", "preflight"}:
            raise ValueError(f"Missing paired public parse at {index}/{repeat}")
        base = next(x for x in pair if x["policy"] == "canonical")
        exp = next(x for x in pair if x["policy"] == "preflight")
        comparable = (base["status"] != "deadline_censored"
                      and exp["status"] != "deadline_censored")
        no_saturation = (comparable
                         and not base["forest_or_kbest_budget_exceeded"]
                         and not exp["forest_or_kbest_budget_exceeded"])
        pairs.append({
            "index": index, "repeat": repeat,
            "expected_route": exp["expected_route"],
            "actual_route": exp.get("complexity_route"),
            "comparable": comparable,
            "both_searches_unsaturated": no_saturation,
            "canonical_status": base["status"],
            "experimental_status": exp["status"],
            "status_equal": (base["status"] == exp["status"]) if comparable else None,
            "selected_tree_equal": (
                base["selected_signature"] == exp["selected_signature"]
                if comparable else None),
            "canonical_ms": base["full_parse_ms"],
            "experimental_ms": exp["full_parse_ms"],
            "ratio": (round(exp["full_parse_ms"] / base["full_parse_ms"], 4)
                      if comparable and base["full_parse_ms"] > 0 else None),
        })
    applicable = [x for x in pairs if x["comparable"]]
    actual = [x for x in applicable if x["actual_route"] == "trie"]
    controls = [x for x in applicable if x["actual_route"] != "trie"]
    def med(values):
        return round(median(values), 4) if values else None
    def timing(group):
        return {
            "matched_pairs": len(group),
            "canonical_median_ms": med([x["canonical_ms"] for x in group]),
            "experimental_median_ms": med([x["experimental_ms"] for x in group]),
            "median_paired_ratio": med([x["ratio"] for x in group
                                       if x["ratio"] is not None]),
        }
    changed = [x for x in applicable if not x["selected_tree_equal"]]
    downgraded = [x for x in applicable if x["canonical_status"] == "complete"
                  and x["experimental_status"] != "complete"]
    unsaturated_changes = [
        x for x in changed if x["both_searches_unsaturated"]
    ]
    return {
        "schema": SCHEMA,
        "cohort_sha256": EXPECTED_500_COHORT_SHA256,
        "pilot_indices": [x["index"] for x in pilot],
        "intended_trie_indices": [
            x["index"] for x in pilot if x["expected_route"] == "trie"],
        "pairs": len(pairs),
        "uncensored_pairs": len(applicable),
        "deadline_censored_pairs": len(pairs) - len(applicable),
        "actually_trie_routed_pairs": len(actual),
        "no_trie_controls": len(controls),
        "timing_trie_routed": timing(actual),
        "timing_nonrouted_control": timing(controls),
        "completed_canonical_lost_indices": sorted({x["index"] for x in downgraded}),
        "changed_selected_tree_indices": sorted({x["index"] for x in changed}),
        "unsaturated_tree_change_indices": sorted({
            x["index"] for x in unsaturated_changes}),
        "status_changes": [
            {"index": x["index"], "baseline": x["canonical_status"],
             "experiment": x["experimental_status"]}
            for x in applicable if not x["status_equal"]
        ],
        "no_default_routing_enabled": True,
        "small_sample_pilot_not_a_population_speedup_claim": True,
        "does_not_justify_early_grammar_rejection": True,
        "grammatical_error_gold_labels_unavailable": True,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.repeats < 1 or args.repeats > 2:
        raise ValueError("Limit repeats to 1..2 to bound CI")
    if args.deadline_seconds <= 0 or args.max_items <= 0 or args.kbest_work_limit <= 0:
        raise ValueError("Budgets must be positive")
    if sha256(args.cohort.read_bytes()).hexdigest() != EXPECTED_500_COHORT_SHA256:
        raise ValueError("Fixed-cohort checksum mismatch")
    cases, _ = select_cases(500)
    pilot = select_pilot(
        cases, minimum_tokens=args.minimum_tokens,
        routed_count=args.routed_count, control_count=args.control_count)
    resources = ParserResources.from_dir(
        ROOT / "data", wordnet_dict=args.wordnet_dir)
    baseline = Parser(resources, cache_size=512, max_items=args.max_items)
    experiment = Parser(
        resources, cache_size=512, max_items=args.max_items,
        preflight_route_policy=PreflightTriePolicy(
            minimum_tokens=args.minimum_tokens),
    )
    for p in (baseline, experiment):
        p.parse("John opened the box.")  # warm shared WordNet/grammar objects
    rows: list[dict[str, Any]] = []
    old_handler = signal.signal(signal.SIGALRM, _deadline)
    try:
        for selected in pilot:
            index = selected["index"]
            case = cases[index]
            case_id = str(case["book_id"]) + ":" + sha256(
                case["source_text"].encode("utf8")).hexdigest()[:16]
            for rep in range(args.repeats):
                # Counterbalanced orders reduce systematic first-run bias.
                order = (
                    (("canonical", baseline), ("preflight", experiment))
                    if rep % 2 == 0 else
                    (("preflight", experiment), ("canonical", baseline))
                )
                for policy, parser in order:
                    start = perf_counter_ns()
                    signal.setitimer(signal.ITIMER_REAL, args.deadline_seconds)
                    try:
                        prepared, lattice, result = parse_corpus_case(
                            parser, case, max_items=args.max_items,
                            kbest_work_limit=args.kbest_work_limit,
                        )
                        elapsed = (perf_counter_ns() - start) / 1e6
                        best = result.best() if result.completed else None
                        stats = result.stats
                        if result.text != prepared.analysis_text or lattice.text != result.text:
                            raise AssertionError("Canonical corpus text or lattice changed")
                        rows.append({
                            "index": index, "case_id": case_id,
                            "policy": policy, "repeat": rep,
                            "expected_route": selected["expected_route"],
                            "status": classify(result.completed, stats),
                            "selected_signature": repr(best.signature()) if best else None,
                            "selected_rule": best.rule_id if best else None,
                            "complexity_route": stats.get("complexity_route"),
                            "complexity_reason": stats.get("complexity_reason"),
                            "lazy_trie_recognition": bool(
                                stats.get("lazy_trie_recognition")),
                            "forest_or_kbest_budget_exceeded": bool(
                                stats.get("budget_exceeded")
                                or stats.get("kbest_budget_exceeded")
                                or (stats.get("dialogue_attempt") or {}).get("budget_exceeded")
                                or (stats.get("dialogue_attempt") or {}).get("kbest_budget_exceeded")),
                            "full_parse_ms": round(elapsed, 3),
                            "same_canonical_budgets": True,
                        })
                    except SentenceDeadline:
                        rows.append({
                            "index": index, "case_id": case_id,
                            "policy": policy, "repeat": rep,
                            "expected_route": selected["expected_route"],
                            "status": "deadline_censored",
                            "selected_signature": None,
                            "forest_or_kbest_budget_exceeded": True,
                            "complexity_route": None,
                            "full_parse_ms": round((perf_counter_ns() - start) / 1e6, 3),
                        })
                    finally:
                        signal.setitimer(signal.ITIMER_REAL, 0)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    summary = summarize(rows, pilot)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "preflight_trie_pilot.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows),
        encoding="utf8")
    (args.out_dir / "preflight_trie_pilot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8")
    lines = [
        "# Opt-in preflight search routing: whole-parser paired pilot", "",
        "Selection is based ONLY on quote-balanced text, token count, commas",
        "and quote presence. No canonical outcomes or grammatical annotations",
        "are used for routing. Both analyses always use the public Parser.parse",
        "through the standard corpus gateway; same forest/kbest/time budgets.", "",
        f"Total pairs: {summary['pairs']}, comparable: "
        f"{summary['uncensored_pairs']}, actually routed: "
        f"{summary['actually_trie_routed_pairs']}.", "",
        f"Trie routed: {summary['timing_trie_routed']}.",
        f"Nonrouted controls: {summary['timing_nonrouted_control']}.", "",
        f"Previously completed cases lost: "
        f"{summary['completed_canonical_lost_indices']}.",
        f"Different selected trees: {summary['changed_selected_tree_indices']}.",
        f"Unsaturated tree differences: "
        f"{summary['unsaturated_tree_change_indices']}.", "",
        "A faster median is NOT sufficient to deploy a route. In particular,",
        "loss of completion or a changed selected tree needs examination.",
        "No early grammatical rejection is licensed by these surface hints.",
    ]
    (args.out_dir / "preflight_trie_pilot_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf8")
    print("PREFLIGHT_TRIE_PILOT", json.dumps(summary), flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", type=Path, required=True)
    ap.add_argument("--wordnet-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--minimum-tokens", type=int, default=17)
    ap.add_argument("--routed-count", type=int, default=12)
    ap.add_argument("--control-count", type=int, default=6)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--max-items", type=int, default=50000)
    ap.add_argument("--kbest-work-limit", type=int, default=500000)
    ap.add_argument("--deadline-seconds", type=float, default=10.0)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
