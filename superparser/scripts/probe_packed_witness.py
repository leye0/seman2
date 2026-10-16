"""Offline feature-checking of packed Earley proof paths, stress corpus only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.verbnet_lr.packed_witness import seek_packed_witness
from research.verbnet_lr.construction_guard import ConstructionGuard
from seman_parser.engine import ParserResources
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]


def run(*, wordnet_dir=None, corpus=None, max_cases=8, max_items=500_000,
        max_seconds=3.0, max_expansions=100_000,
        max_paths_per_item=6, max_backpointers=6):
    path = Path(corpus or ROOT / "research" / "verbnet_lr" /
                "long_sentence_stress.jsonl")
    cases = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()
             if line.strip()][:max_cases]
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    results = []
    for case in cases:
        lattice = build_lattice(case["text"], resources.lexicon, multiword_max=1)
        guard = ConstructionGuard(modal_forms={
            c.surface.casefold() for c in lattice.candidates if c.category == "MODAL"})
        result = seek_packed_witness(
            resources.grammar, lattice,
            max_items=max_items, max_seconds=max_seconds,
            max_expansions=max_expansions,
            max_paths_per_item=max_paths_per_item,
            max_backpointers=max_backpointers,
            validate_tree=guard.validate)
        results.append({"id": case["id"], **result})
    return {
        "schema": 1,
        "mode": "offline_packed_earley_unification_witness",
        "parameters": {
            "max_seconds_per_case": max_seconds,
            "max_items": max_items,
            "max_expansions": max_expansions,
            "max_paths_per_item": max_paths_per_item,
            "max_backpointers": max_backpointers,
        },
        "summary": {
            "found": sum(r["status"] == "FOUND" for r in results),
            "unknown": sum(r["status"] == "UNKNOWN" for r in results),
            "category_rejected": sum(r["status"] == "CATEGORY_REJECTED" for r in results),
        },
        "limitations": [
            "A feature-unified packed proof is not a gold linguistic tree.",
            "The Earley backpointer cap and time/item budgets can hide valid derivations.",
            "UNKNOWN never establishes agrammaticality.",
            "No runtime parser decision or production grammar has been changed.",
        ],
        "cases": results,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wordnet-dir")
    p.add_argument("--corpus")
    p.add_argument("--max-cases", type=int, default=8)
    p.add_argument("--max-items", type=int, default=500_000)
    p.add_argument("--max-seconds", type=float, default=3.0)
    p.add_argument("--max-expansions", type=int, default=100_000)
    p.add_argument("--max-paths-per-item", type=int, default=6)
    p.add_argument("--max-backpointers", type=int, default=6)
    p.add_argument("--report", default=str(ROOT / "research" / "verbnet_lr" /
                                        "packed_witness_report.json"))
    args = p.parse_args()
    report = run(wordnet_dir=args.wordnet_dir, corpus=args.corpus,
                 max_cases=args.max_cases, max_items=args.max_items,
                 max_seconds=args.max_seconds,
                 max_expansions=args.max_expansions,
                 max_paths_per_item=args.max_paths_per_item,
                 max_backpointers=args.max_backpointers)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"summary": report["summary"],
                      "cases": [{"id": r["id"], "status": r["status"],
                                 "reason": r["reason"],
                                 "unifications": r["unifications"]}
                                for r in report["cases"]]}, indent=2))


if __name__ == "__main__":
    main()
