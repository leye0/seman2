"""Offline structural-coverage bound for Seman2's long stress corpus.

If even a permissive CFG recognizer cannot derive the full sentence, more
backtracking in the L->R runtime cannot repair its missing grammar coverage.
A derived upper bound does not certify morphological or semantic correctness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.verbnet_lr.upper_bound import recognize_upper_bound
from seman_parser.engine import ParserResources
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]


def run(*, wordnet_dir=None, corpus=None, max_items=500_000, max_seconds=2.5):
    path = Path(corpus or ROOT / "research" / "verbnet_lr" / "long_sentence_stress.jsonl")
    cases = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()
             if line.strip()]
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    productions = [(rule.lhs.category, tuple(s.category for s in rule.rhs))
                   for rule in resources.grammar.rules]
    report = []
    for case in cases:
        lattice = build_lattice(case["text"], resources.lexicon, multiword_max=1)
        tokens = list(lattice.tokens)
        if tokens and tokens[-1].text in (".", "!"):
            tokens.pop()  # Same optional sentence-ending punctuation as runtime.
        by_span = {}
        for cand in lattice.candidates:
            by_span.setdefault((cand.span_start, cand.span_end), set()).add(cand.category)
        categories = [by_span.get((t.start, t.end), set()) for t in tokens]
        outcome = recognize_upper_bound(
            productions, categories, max_items=max_items, max_seconds=max_seconds)
        report.append({
            "id": case["id"],
            "tokens": len(tokens),
            "lexical_gap": [{"at": i, "word": tok.text} for i, tok in enumerate(tokens)
                            if not categories[i]],
            **outcome,
        })
    return {
        "schema": 1, "mode": "feature_agnostic_CFG_upper_bound",
        "limitations": [
            "An ACCEPTED upper bound may fail all feature unifications.",
            "A REJECTED upper bound establishes missing structural/lexical coverage only "
            "with the current token-only lattice and entire grammar.",
            "UNKNOWN is a budget/time limit, not grammatical rejection.",
            "This offline recognizer has no effect on the runtime or parse rankings.",
        ],
        "summary": {
            "accepted": sum(x["status"] == "ACCEPTED" for x in report),
            "rejected": sum(x["status"] == "REJECTED" for x in report),
            "unknown": sum(x["status"] == "UNKNOWN" for x in report),
        },
        "cases": report,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wordnet-dir")
    parser.add_argument("--corpus")
    parser.add_argument("--max-items", type=int, default=500000)
    parser.add_argument("--max-seconds", type=float, default=2.5)
    parser.add_argument("--report", default=str(
        ROOT / "research" / "verbnet_lr" / "grammar_upper_bound.json"))
    args = parser.parse_args()
    if args.max_items < 1 or args.max_seconds <= 0:
        parser.error("positive budgets required")
    report = run(wordnet_dir=args.wordnet_dir, corpus=args.corpus,
                 max_items=args.max_items, max_seconds=args.max_seconds)
    Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"summary": report["summary"], "cases": [
        {key: val for key, val in case.items()
         if key in ("id", "status", "reason", "items", "elapsed_ms", "furthest_goal_prefix")}
        for case in report["cases"]]}, indent=2))


if __name__ == "__main__":
    main()
