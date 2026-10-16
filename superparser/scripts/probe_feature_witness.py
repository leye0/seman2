"""Offline bounded feature-witness search on the held-out long stress cases.

No grammar tuning, production parser changes, or runtime fallback. Failure to
find a witness is UNKNOWN, not proof that a sentence is ungrammatical.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.verbnet_lr.feature_witness import seek_feature_witness
from research.verbnet_lr.construction_guard import ConstructionGuard
from seman_parser.engine import ParserResources
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]


def run(*, wordnet_dir=None, corpus=None, max_cases=8, max_items=500_000,
        max_seconds=3.0, max_expansions=20_000, max_nodes_per_span=6):
    path = Path(corpus or ROOT / "research" / "verbnet_lr" /
                "long_sentence_stress.jsonl")
    cases = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()
             if line.strip()][:max_cases]
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    rows = []
    for case in cases:
        lattice = build_lattice(case["text"], resources.lexicon, multiword_max=1)
        guard = ConstructionGuard(modal_forms={
            c.surface.casefold() for c in lattice.candidates if c.category == "MODAL"})
        result = seek_feature_witness(
            resources.grammar, lattice, max_items=max_items,
            max_seconds=max_seconds, max_expansions=max_expansions,
            max_nodes_per_span=max_nodes_per_span,
            validate_tree=guard.validate)
        rows.append({"id": case["id"], **result})
    return {
        "schema": 1,
        "mode": "offline_feature_unification_witness_no_runtime_fallback",
        "parameters": {
            "max_seconds_per_case": max_seconds,
            "max_items": max_items,
            "max_expansions": max_expansions,
            "max_nodes_per_span": max_nodes_per_span,
        },
        "summary": {
            "found": sum(x["status"] == "FOUND" for x in rows),
            "unknown": sum(x["status"] == "UNKNOWN" for x in rows),
            "category_rejected": sum(x["status"] == "CATEGORY_REJECTED" for x in rows),
        },
        "limitations": [
            "FOUND certifies feature unification and conservative construction checks, not gold syntax.",
            "UNKNOWN is never grammatical rejection: caps, cyclic spans or incomplete candidate exploration may hide valid paths.",
            "The permissive CFG step includes every productive lexical category; its acceptance is NOT feature validity.",
            "No search path, rule, lexical candidate or constraint is injected into the L->R runtime.",
        ],
        "cases": rows,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wordnet-dir")
    p.add_argument("--corpus")
    p.add_argument("--max-cases", type=int, default=8)
    p.add_argument("--max-items", type=int, default=500_000)
    p.add_argument("--max-seconds", type=float, default=3.0)
    p.add_argument("--max-expansions", type=int, default=20_000)
    p.add_argument("--max-nodes-per-span", type=int, default=6)
    p.add_argument("--report", default=str(
        ROOT / "research" / "verbnet_lr" / "feature_witness_report.json"))
    args = p.parse_args()
    report = run(wordnet_dir=args.wordnet_dir, corpus=args.corpus,
                 max_cases=args.max_cases, max_items=args.max_items,
                 max_seconds=args.max_seconds, max_expansions=args.max_expansions,
                 max_nodes_per_span=args.max_nodes_per_span)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"summary": report["summary"],
                      "cases": [{"id": x["id"], "status": x["status"],
                                 "reason": x["reason"],
                                 "unifications": x["unifications"]}
                                for x in report["cases"]]}, indent=2))


if __name__ == "__main__":
    main()
