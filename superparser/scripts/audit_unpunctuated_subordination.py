"""Structural trial: unpunctuated preposed subordination needs an overt
finite subject/predicate matrix, not an arbitrary full CLAUSE neighbor.

Research variant only: main grammar is untouched. Every analysis still uses
the public Parser.parse gateway; the experiment substitutes two declarative
rules while preserving all lexical senses and subordinate constituent rules.
"""
from __future__ import annotations
import argparse
import json
from dataclasses import replace
from pathlib import Path
import signal
from time import perf_counter

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import classify, select_cases
from seman_parser.engine import Parser, ParserResources
from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar, RuleSymbol

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (58, 62, 64, 90, 93, 95, 98, 104, 108, 173, 191, 203,
           223, 227, 231, 243, 248, 353, 362, 367, 447, 478, 485, 496, 499)
UNPUNCTUATED = frozenset({"clause_sub_front", "clause_when"})


class Deadline(Exception): pass


def _alarm(_s, _f): raise Deadline()


def variant(resources):
    changed = set()
    grammar = []
    subject = RuleSymbol(
        "NP", FeatureStructure.build({"number": "?np", "person": "?person"}),
        {"referent": "subject"},
    )
    predicate = RuleSymbol(
        "VP", FeatureStructure.build({
            "number": "?np", "person": "?person",
            "voice": "active", "vform": "finite",
        }), {"event": "main"}, ("vform",),
    )
    for rule in resources.grammar:
        if rule.rule_id not in UNPUNCTUATED:
            grammar.append(rule)
            continue
        # Only the permissive CLAUSE slot *after* an already identified
        # subordinate clause is replaced by an overt agreeing NP + finite VP.
        assert [s.category for s in rule.rhs] == ["CONJ", "CLAUSE", "CLAUSE"]
        grammar.append(replace(rule, rhs=(*rule.rhs[:2], subject, predicate)))
        changed.add(rule.rule_id)
    assert changed == UNPUNCTUATED
    return ParserResources(
        grammar=Grammar(grammar), lexicon=resources.lexicon,
        types=resources.types, metadata=resources.metadata,
    )


def tree(item):
    if item is None: return None
    return {
        "cat": item.category, "rule": item.rule_id,
        "span": [item.start, item.end],
        "children": [tree(child) for child in item.children],
    }


def parse(parser, case):
    start = perf_counter()
    signal.setitimer(signal.ITIMER_REAL, 9)
    try:
        prepared, _lattice, parsed = parse_corpus_case(
            parser, case, max_items=50000, kbest_work_limit=500000,
        )
        stats = parsed.stats
        result = {
            "status": classify(parsed.completed, stats),
            "root": parsed.best().rule_id if parsed.best() else None,
            "tree": tree(parsed.best()),
            "forest_budget": bool(stats.get("budget_exceeded")),
            "dialogue_budget": bool((stats.get("dialogue_attempt") or {})
                                   .get("budget_exceeded")),
            "partial_states": int(stats.get("partial_states", 0)),
            "analysis": prepared.analysis_text,
        }
    except Deadline:
        result = {"status": "timeout", "root": None}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    result["wall_ms"] = round((perf_counter() - start) * 1000, 2)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--wordnet-dir", required=True)
    p.add_argument("--out", type=Path, required=True)
    options = p.parse_args()
    resources = ParserResources.from_dir(ROOT / "data",
                                         wordnet_dict=options.wordnet_dir)
    baseline = Parser(resources, cache_size=256,
                      lexical_left_corner_pruning=True)
    experimental = Parser(variant(resources), cache_size=256,
                          lexical_left_corner_pruning=True)
    experimental._lattice_cache = baseline._lattice_cache
    old = signal.signal(signal.SIGALRM, _alarm)
    cases, _ = select_cases(500)
    rows = []
    try:
        for index in TARGETS:
            case = cases[index]
            a = parse(baseline, case)
            b = parse(experimental, case)
            row = {
                "index": index, "source": case["text"],
                "baseline": a, "constrained": b,
            }
            rows.append(row)
            print("SUBORDINATION_BOUNDARY_CASE", json.dumps({
                "index": index,
                "baseline": {k: v for k, v in a.items()
                             if k not in ("tree", "analysis")},
                "constrained": {k: v for k, v in b.items()
                                if k not in ("tree", "analysis")},
                "tree_changed": a["tree"] != b["tree"],
            }, ensure_ascii=False), flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    summary = {
        "cases": len(rows),
        "baseline_complete": sum(r["baseline"]["status"] == "complete"
                                 for r in rows),
        "constrained_complete": sum(r["constrained"]["status"] == "complete"
                                    for r in rows),
        "recovered": [r["index"] for r in rows
                      if r["baseline"]["status"] != "complete"
                      and r["constrained"]["status"] == "complete"],
        "no_longer_completed": [r["index"] for r in rows
                                if r["baseline"]["status"] == "complete"
                                and r["constrained"]["status"] != "complete"],
        "changed_trees": [r["index"] for r in rows
                          if r["baseline"]["tree"] != r["constrained"]["tree"]],
    }
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(
        json.dumps({"summary": summary, "rows": rows},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    print("SUBORDINATION_BOUNDARY_SUMMARY", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
