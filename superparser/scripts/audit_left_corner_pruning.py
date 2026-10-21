"""Paired proof-of-preservation for lexical left-corner partial-state pruning.

Both variants use the SAME public Parser.parse and the immutable 500-sentence
cohort. This tests structural forest preservation, best-tree stability and
resource effects. A saturated baseline does NOT certify equivalence and is
reported separately; it must never be counted as a guaranteed recovery.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import signal
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import classify, select_cases
from seman_parser.engine import Parser, ParserResources

ROOT = Path(__file__).resolve().parents[1]
# Deliberately includes successful controls, failed ordinary clauses,
# dialogue, and the known scoped-dialogue saturation case 367.
INDICES = (58, 62, 75, 98, 104, 96, 100, 115, 194, 209, 232, 237,
           347, 349, 367, 439, 473)


class Deadline(Exception):
    pass


def _timeout(_signal, _frame):
    raise Deadline("left-corner paired corpus parse timed out")


def _tree(item):
    if item is None:
        return None
    return (
        item.start, item.end, item.category, item.rule_id,
        tuple(_tree(child) for child in item.children),
    )


def _node_signature(result):
    forest = result.shared_forest
    if not hasattr(forest, "nodes"):
        # Hierarchical results have interfaces rather than one ordinary
        # shared forest; their root trees and completion are still compared.
        return None
    return sorted((n.start, n.end, n.category, len(n.derivations))
                  for n in forest.nodes)


def _candidate_signature(lattice):
    return sha256(repr(tuple((
        c.span_start, c.span_end, c.category,
        c.lemma, c.sense_ids, c.features.as_dict(),
    ) for c in lattice.candidates)).encode("utf-8")).hexdigest()


def _run(parser, case, seconds):
    began = perf_counter()
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        _prepared, lattice, result = parse_corpus_case(
            parser, case, max_items=50000, kbest_work_limit=500000,
        )
        stats = result.stats
        dialogue = stats.get("dialogue_attempt") or {}
        data = {
            "completed": result.completed,
            "status": classify(result.completed, stats),
            "rule": result.best().rule_id if result.best() else None,
            "tree": _tree(result.best()),
            "nodes": _node_signature(result),
            "candidates": _candidate_signature(lattice),
            "partial_states": stats.get("partial_states"),
            "forest_nodes": stats.get("forest_nodes"),
            "derivations": stats.get("structural_derivations"),
            "root_nodes": stats.get("structural_root_nodes"),
            "budget": bool(stats.get("budget_exceeded")),
            "dialogue_budget": bool(dialogue.get("budget_exceeded")),
            "dialogue_partials": dialogue.get("partial_states"),
            "dialogue_nodes": dialogue.get("forest_nodes"),
            "unreachable_prefix_proposals": stats.get(
                "unreachable_prefix_proposals", 0),
            "dialogue_unreachable_prefix_proposals": dialogue.get(
                "unreachable_prefix_proposals", 0),
        }
    except Deadline:
        data = {"completed": False, "status": "timeout"}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    data["wall_ms"] = round(1000 * (perf_counter() - began), 2)
    return data


def audit(wordnet_dir: str, indices=INDICES, seconds=9.0, output=None):
    cases, _ = select_cases(500)
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    baseline = Parser(resources, cache_size=0)
    candidate = Parser(
        resources, cache_size=0, lexical_left_corner_pruning=True,
    )
    old_handler = signal.signal(signal.SIGALRM, _timeout)
    rows = []
    try:
        for index in indices:
            if not 0 <= index < len(cases):
                raise ValueError(f"Invalid pinned corpus index: {index}")
            case = cases[index]
            base = _run(baseline, case, seconds)
            opt = _run(candidate, case, seconds)
            baseline_censored = (
                base["status"] == "timeout"
                or base.get("budget")
                or base.get("dialogue_budget")
                or base["status"] in (
                    "forest_budget_exceeded", "kbest_budget_exceeded",
                    "both_budgets_exceeded",
                )
            )
            # Only a completed baseline recognition can certify full-forest
            # preservation. Inconclusive cases are observations, not proofs.
            comparable = not baseline_censored and opt["status"] != "timeout"
            if comparable:
                assert opt["candidates"] == base["candidates"], index
                assert opt["completed"] == base["completed"], (index, base, opt)
                assert opt["tree"] == base["tree"], (index, base["tree"], opt["tree"])
                assert opt["nodes"] == base["nodes"], (index, "forest changed")
                assert opt["derivations"] == base["derivations"], index
                assert opt["root_nodes"] == base["root_nodes"], index
                assert not opt["budget"] and not opt["dialogue_budget"], index
                assert opt["partial_states"] <= base["partial_states"], index
            row = {
                "index": index,
                "book_id": case["book_id"],
                "baseline_censored": baseline_censored,
                "comparable": comparable,
                "baseline": {key: value for key, value in base.items()
                            if key not in ("tree", "nodes", "candidates")},
                "optimized": {key: value for key, value in opt.items()
                              if key not in ("tree", "nodes", "candidates")},
            }
            rows.append(row)
            print("LEFT_CORNER_CASE", json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    summary = {
        "n": len(rows),
        "equivalent_unsaturated": sum(r["comparable"] for r in rows),
        "inconclusive_baselines": sum(r["baseline_censored"] for r in rows),
        "optimized_complete": sum(r["optimized"]["completed"] for r in rows),
        "baseline_complete": sum(r["baseline"]["completed"] for r in rows),
        "baseline_partial_states": sum(
            r["baseline"].get("partial_states") or 0 for r in rows
        ),
        "optimized_partial_states": sum(
            r["optimized"].get("partial_states") or 0 for r in rows
        ),
        "skipped_prefix_proposals": sum(
            r["optimized"].get("unreachable_prefix_proposals") or 0 for r in rows
        ),
        "dialogue_skipped_prefix_proposals": sum(
            r["optimized"].get("dialogue_unreachable_prefix_proposals") or 0
            for r in rows
        ),
        "caveat": "Saturated trials cannot certify forest/tree equivalence",
    }
    print("LEFT_CORNER_SUMMARY", json.dumps(summary), flush=True)
    if output:
        Path(output).write_text(
            json.dumps({"summary": summary, "rows": rows},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir", required=True)
    ap.add_argument("--indices", default=",".join(map(str, INDICES)))
    ap.add_argument("--seconds", type=float, default=9.0)
    ap.add_argument("--output", default=None)
    options = ap.parse_args()
    audit(options.wordnet_dir, tuple(
        int(part) for part in options.indices.split(",") if part.strip()
    ), options.seconds, options.output)


if __name__ == "__main__":
    main()
