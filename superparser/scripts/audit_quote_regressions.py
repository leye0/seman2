"""Reproduce and ablate residual quote regressions without changing corpus or parser code.

Runs the public corpus parsing API on selected pinned Gutenberg indices with the
current grammar and two controlled variants:
- the old, nonlexical NP coordinator+adverb construction;
- the removal of selected *new* generic grammar families.
A comparison is evidence about causes, never a license to loosen grammar merely
to raise the recognition counter.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases, classify
from seman_parser.engine import Parser, ParserResources
from seman_parser.grammar import Grammar, parse_rule

DATA = Path(__file__).resolve().parents[1] / "data"
NEW_RULES = frozenset({
    "np_prenominal_degree_adjective_indefinite_noun",
    "vp_perfect_clausal_zero_complement",
    "vp_perfect_clausal_that_complement",
    "vp_finite_clausal_not_that",
    "clause_initial_coordinator_discourse_adverb",
    "pp_absolute_with_np_adjp",
})
VARIANTS = ("current", "old_nominal_coordination", "without_six_rules", "both")
OLD_NP_COORD_ADV = parse_rule({
    "id": "np_coord_adv",
    "rhs": [
        {"category": "COORD", "features": {"nominal_coordination": "true"},
         "requires": ["nominal_coordination"]},
        {"category": "ADV"},
        {"category": "NP", "exports": {"referent": "right"}},
    ],
    "lhs": {"category": "NP"},
    "score": 1.05,
})


def variant_rules(resources: ParserResources, variant: str) -> Grammar:
    if variant not in VARIANTS and not variant.startswith("without_rule:"):
        raise ValueError(f"Unknown variant: {variant}")
    rules = list(resources.grammar.rules)
    if variant.startswith("without_rule:"):
        dropped = variant.partition(":")[2]
        if dropped not in NEW_RULES:
            raise ValueError(f"Unknown new rule for ablation: {dropped}")
        rules = [r for r in rules if r.rule_id != dropped]
    if variant in ("without_six_rules", "both"):
        rules = [r for r in rules if r.rule_id not in NEW_RULES]
    if variant in ("old_nominal_coordination", "both"):
        rules = [OLD_NP_COORD_ADV if r.rule_id == "np_coord_adv" else r
                 for r in rules]
    return Grammar(rules)


def root_rules(node):
    yield node.rule_id
    for child in node.children:
        yield from root_rules(child)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wordnet-dir", required=True)
    ap.add_argument("--indices", default="359,414")
    ap.add_argument("--budget", type=int, default=50000)
    ap.add_argument("--raised-budget", type=int, default=60000)
    ap.add_argument("--isolate-new-rules", action="store_true")
    args = ap.parse_args()
    indices = tuple(int(v) for v in args.indices.split(","))
    cases, _ = select_cases(500)
    resources = ParserResources.from_dir(DATA, wordnet_dict=args.wordnet_dir)
    variants = (*VARIANTS, *(f"without_rule:{rule}" for rule in sorted(NEW_RULES))) if args.isolate_new_rules else VARIANTS
    for variant in variants:
        grammar = variant_rules(resources, variant)
        p = Parser(ParserResources(
            grammar=grammar, lexicon=resources.lexicon,
            types=resources.types, metadata=resources.metadata,
        ), cache_size=0, max_items=args.budget)
        for idx in indices:
            if variant.startswith("without_rule:") and idx != 359:
                continue
            for budget in (args.budget, args.raised_budget) if idx == 359 and variant == "current" else (args.budget,):
                start = perf_counter()
                prepared, lattice, result = parse_corpus_case(
                    p, cases[idx], max_items=budget,
                    kbest_work_limit=500000,
                )
                best = result.best()
                row = {
                    "index": idx,
                    "variant": variant,
                    "budget": budget,
                    "completed": result.completed,
                    "status": classify(result.completed, result.stats),
                    "root_rule": best.rule_id if best else None,
                    "root_rules": sorted({
                        str(name) for name in root_rules(best)
                        if name and ("coord" in name or "clause" in name)
                    }) if best else [],
                    "forest_budget": bool(result.stats.get("budget_exceeded")),
                    "dialogue_attempt": result.stats.get("dialogue_attempt"),
                    "elapsed_ms": round(1000 * (perf_counter() - start), 2),
                    "text": prepared.analysis_text,
                }
                print("QUOTE_REGRESSION_ABLATION", json.dumps(
                    row, ensure_ascii=False), flush=True)
                if best and idx == 414 and variant in ("current", "old_nominal_coordination"):
                    from scripts.audit_novel_tree_quality import display_tree
                    print("QUOTE_REGRESSION_TREE_BEGIN", variant, idx, flush=True)
                    print("\\n".join(display_tree(best, result.text)), flush=True)
                    print("QUOTE_REGRESSION_TREE_END", variant, idx, flush=True)
                if best and idx == 359 and budget > args.budget:
                    from scripts.audit_novel_tree_quality import display_tree
                    print("QUOTE_REGRESSION_TREE_BEGIN", variant, idx, flush=True)
                    print("\\n".join(display_tree(best, result.text)), flush=True)
                    print("QUOTE_REGRESSION_TREE_END", variant, idx, flush=True)


if __name__ == "__main__":
    main()
