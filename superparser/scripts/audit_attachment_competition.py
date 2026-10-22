"""Cost-bounded lexical/structural ablations for literary attachment regressions.

Every trial uses Parser.parse through parse_corpus_case at the same official
50,000-item and 500,000-work limits. Ablations are diagnostics only, never
alternate headline coverage or a reason to relax the canonical budget.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import classify, select_cases
from seman_parser.engine import Parser, ParserResources
from seman_parser.grammar import Grammar

DATA = Path(__file__).resolve().parents[1] / "data"
MAX_ITEMS = 50_000
KBEST_WORK = 500_000


def nodes(node):
    yield node
    for child in node.children:
        yield from nodes(child)


def parser_variant(base, removed=(), goal="CLAUSE"):
    rules = tuple(rule for rule in base.grammar.rules
                  if rule.rule_id not in removed)
    return Parser(ParserResources(
        grammar=Grammar(rules), lexicon=base.lexicon,
        types=base.types, metadata=base.metadata,
    ), goal_category=goal, cache_size=0, max_items=MAX_ITEMS)


def diagnose_original_359(resources, case):
    variants = {
        "current": (),
        "without_nominal_absolute_attachment": ("np_with_absolute_modifier",),
        "without_modal_perfects": (
            "vpnp_base_perfect_transitive", "vpnp_base_perfect_intransitive",
        ),
        "without_both_families": (
            "np_with_absolute_modifier",
            "vpnp_base_perfect_transitive", "vpnp_base_perfect_intransitive",
        ),
        "without_typed_absolute_projection": (
            "pp_absolute_from_typed_with_predicate",
        ),
    }
    for name, excluded in variants.items():
        parser = parser_variant(resources, excluded)
        prepared, _, result = parse_corpus_case(
            parser, case, max_items=MAX_ITEMS,
            kbest_work_limit=KBEST_WORK,
        )
        stats = result.stats
        print("ATTACHMENT_ABLATION_359", json.dumps({
            "variant": name,
            "removed": excluded,
            "source": prepared.source_text,
            "completed": result.completed,
            "status": classify(result.completed, stats),
            "best_rule": result.best().rule_id if result.best() else None,
            "forest_nodes": stats.get("forest_nodes"),
            "partial_states": stats.get("partial_states"),
            "dialogue_budget_exceeded": (
                stats.get("dialogue_attempt") or {}
            ).get("budget_exceeded"),
            "dialogue_partial_states": (
                stats.get("dialogue_attempt") or {}
            ).get("partial_states"),
        }, ensure_ascii=False), flush=True)


def diagnose_427(resources, case):
    parser = parser_variant(resources)
    prepared, _, result = parse_corpus_case(
        parser, case, max_items=MAX_ITEMS,
        kbest_work_limit=KBEST_WORK,
    )
    target = "a bottle with some brandy left"
    names = {"np_with_absolute_modifier", "pp_absolute_with_np_adjp"}
    ranks = []
    for rank, root in enumerate(result.alternatives(limit=128), start=1):
        spans = {
            (node.rule_id, prepared.analysis_text[node.start:node.end])
            for node in nodes(root)
        }
        matched = {
            key for key, span in spans
            if key in names and (span == target or span == "with some brandy left")
        }
        if matched or rank <= 3:
            ranks.append({
                "rank": rank, "score": root.score,
                "root_rule": root.rule_id,
                "matched": sorted(matched),
                "has_wrong_vp": (
                    "vp_adv", "found a bottle with some brandy left"
                ) in spans,
                "has_prep_ditransitive": (
                    "vp_prep_ditransitive", "found a bottle with some brandy"
                ) in spans,
            })
    print("ATTACHMENT_ALTERNATIVES_427", json.dumps({
        "source": prepared.source_text,
        "completed": result.completed,
        "forest_nodes": result.stats.get("forest_nodes"),
        "alternatives_checked": min(128, len(result.alternatives(limit=128))),
        "candidate_ranks": ranks,
    }, ensure_ascii=False), flush=True)
    nominal = parser_variant(resources, goal="NP")
    for phrase in (
        "a bottle with some brandy left",
        "a man with his eyes open",
        "a bottle with a label",
    ):
        result = nominal.parse(
            phrase, kbest_work_limit=KBEST_WORK,
            diagnostic_k=32,
        ).result
        best = result.best()
        print("ATTACHMENT_NP", json.dumps({
            "phrase": phrase,
            "completed": result.completed,
            "best_rule": best.rule_id if best else None,
            "best_score": best.score if best else None,
            "rules": sorted({str(n.rule_id) for n in nodes(best)})
            if best else [],
        }), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wordnet-dir", required=True)
    args = ap.parse_args()
    resources = ParserResources.from_dir(DATA, wordnet_dict=args.wordnet_dir)
    cohort, _ = select_cases(500)
    diagnose_original_359(resources, cohort[359])
    diagnose_427(resources, cohort[427])


if __name__ == "__main__":
    main()
