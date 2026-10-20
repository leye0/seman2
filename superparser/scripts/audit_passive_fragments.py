"""Structural audit of a finite passive auxiliary with shared participles.

Use only Parser.parse with explicit goal categories; preserve each category,
valency feature and syntax tree. This diagnostic never edits the corpus.
"""
from __future__ import annotations

import os
from pathlib import Path

from seman_parser.engine import Parser

DATA = Path(__file__).resolve().parents[1] / "data"

SAMPLES = (
    ("PASSIVE-PART", "seized immediately"),
    ("PASSIVE-PART", "charged with murder"),
    ("PASSIVE-PART", "thrown, by some surprising accident"),
    ("PASSIVE-PART", "thrown, by some surprising accident, on this shore"),
    ("NP", "this shore, renowned for its hospitality"),
    ("PP", "on this shore, renowned for its hospitality"),
    ("PASSIVE-PART", "thrown, by some surprising accident, on this shore, renowned for its hospitality"),
    ("PASSIVE-SEQ", "seized immediately, and charged with murder"),
    ("PASSIVE-SEQ", "thrown, by some surprising accident, on this shore, renowned for its hospitality, seized immediately, and charged with murder"),
    ("CLAUSE", "The doors were opened, and closed."),
    ("CLAUSE", "You were thrown, by some surprising accident, on this shore, renowned for its hospitality, seized immediately, and charged with murder."),
)


def main() -> None:
    for goal, sentence in SAMPLES:
        parser = Parser.from_dir(DATA, goal_category=goal, cache_size=0,
                                 max_items=50_000)
        result = parser.parse(sentence, kbest_work_limit=500_000).result
        best = result.best()
        print("PASSIVE_FRAGMENT",
              repr(goal), repr(sentence), "complete=", result.completed,
              "best=", best.rule_id if best else None,
              "structural_roots=", result.stats.get("structural_root_nodes"),
              "forest=", result.stats.get("forest_nodes"), flush=True)

    sample = SAMPLES[-1][1]
    parser = Parser.from_dir(DATA, goal_category="CLAUSE", cache_size=0,
                             max_items=50_000)
    result = parser.parse(sample, diagnostic_k=128,
                          kbest_work_limit=500_000).result

    def nodes(item):
        yield item
        for child in item.children:
            yield from nodes(child)

    for goal, frag in (
        ("VP", sample[sample.index("were "):].rstrip(".")),
        ("CLAUSE", "You were thrown, seized immediately, and charged with murder."),
        ("VP", "were opened, and closed"),
        ("CLAUSE", "The doors were opened, and closed."),
    ):
        p = Parser.from_dir(DATA, goal_category=goal, cache_size=0)
        rr = p.parse(frag, diagnostic_k=64,
                     kbest_work_limit=500_000).result
        alt = rr.alternatives(limit=64)
        valid = [
            rank for rank, item in enumerate(alt, start=1)
            if any(n.rule_id == "vp_passive_shared_aux_sequence"
                   for n in nodes(item))
        ]
        print("PASSIVE_COMPOSITION", repr(goal), repr(frag),
              "complete=", rr.completed,
              "shared_aux_ranks=", valid[:8],
              "best_rule=", rr.best().rule_id if rr.best() else None,
              "root_candidates=", len(alt), flush=True)

    for sentence in (
        "You were captured.",
        "You were captured, and released.",
        "They were captured, and released.",
        "John was captured, and released.",
        "The men were captured, and released.",
    ):
        p = Parser.from_dir(DATA, cache_size=0)
        rr = p.parse(sentence, diagnostic_k=64,
                     kbest_work_limit=500_000).result
        alts = rr.alternatives(limit=64)
        print("PASSIVE_SUBJECT_RANK", repr(sentence),
              "completed=", rr.completed,
              "best=", rr.best().rule_id if rr.best() else None,
              "passive_clause_ranks=", [
                  i for i, a in enumerate(alts, 1)
                  if a.rule_id == "clause_passive"
              ][:20],
              "shared_seq_ranks=", [
                  i for i, a in enumerate(alts, 1)
                  if any(n.rule_id == "vp_passive_shared_aux_sequence"
                         for n in nodes(a))
              ][:20], flush=True)

    from collections import Counter
    from seman_parser.vector_chart import RuleDerivation

    forest = result.shared_forest
    def rule_counts(category: str, start: int):
        nodes_at_start = [
            n for n in forest.nodes
            if n.category == category and n.start == start
            and not sample[n.end:].strip(' .!?;:"')
        ]
        counts = Counter()
        for n in nodes_at_start:
            for d in n.derivations:
                if isinstance(d, RuleDerivation):
                    counts[forest.compiled.rules[d.rule_index].rule.rule_id] += 1
        return dict(counts)

    print("PASSIVE_FOREST_ROOTS",
          "CLAUSE=", rule_counts("CLAUSE", 0),
          "VP=", rule_counts("VP", sample.index("were")),
          "PASSIVE-SEQ=", rule_counts("PASSIVE-SEQ", sample.index("thrown")),
          flush=True)

    # Diagnostic-only restriction of competing root schemas. The public
    # Parser.parse entry point remains exactly the same; this experiment
    # tests whether the packed clause_passive derivation can unify at all.
    from seman_parser.engine import ParserResources
    from seman_parser.grammar import Grammar
    resources = ParserResources.from_dir(DATA)
    restricted_rules = [
        r for r in resources.grammar
        if r.lhs.category != "CLAUSE" or r.rule_id == "clause_passive"
    ]
    resources.grammar = Grammar(tuple(restricted_rules))
    restricted_parser = Parser(resources, goal_category="CLAUSE", cache_size=0,
                               max_items=50_000)
    restricted = restricted_parser.parse(
        sample, diagnostic_k=32, kbest_work_limit=500_000,
    ).result
    print("PASSIVE_ROOT_UNIFICATION",
          "complete=", restricted.completed,
          "root=", restricted.best().rule_id if restricted.best() else None,
          "restricted_score=", restricted.best().score if restricted.best() else None,
          "unrestricted_best_score=", result.best().score if result.best() else None,
          "stats=", {
              k: restricted.stats.get(k) for k in
              ("structural_root_nodes", "forest_nodes", "budget_exceeded",
               "roots_without_valid_analysis", "kbest_work_units")
          }, flush=True)

    for beam in (160, 320):
        pp = Parser.from_dir(DATA, goal_category="CLAUSE", cache_size=0,
                             max_items=50_000, beam=beam)
        wide = pp.parse(sample, diagnostic_k=128, beam=beam,
                        kbest_work_limit=500_000).result
        alts = wide.alternatives(limit=128)
        matches = [
            k for k, tree in enumerate(alts, start=1)
            if any(n.rule_id == "vp_passive_shared_aux_sequence"
                   for n in nodes(tree))
        ]
        print("PASSIVE_BEAM_AUDIT", beam,
              "complete=", wide.completed,
              "correct_ranks=", matches[:10],
              "forest=", wide.stats.get("forest_nodes"),
              "forest_budget=", wide.stats.get("budget_exceeded"),
              "kbest_budget=", wide.stats.get("kbest_budget_exceeded"),
              "roots=", wide.stats.get("structural_root_nodes"),
              flush=True)

    for rank, tree in enumerate(result.alternatives(limit=128), start=1):
        all_nodes = list(nodes(tree))
        if any(n.rule_id == "vp_passive_shared_aux_sequence" for n in all_nodes):
            print("PASSIVE_CORRECT_PATH_RANK", rank,
                  "score=", tree.score,
                  "has_supplementary_np=", any(
                      n.rule_id == "np_postposed_supplementary_adjp"
                      for n in all_nodes),
                  "root=", tree.rule_id,
                  "voice=", tree.features.as_dict().get("voice"), flush=True)
            break
    else:
        print("PASSIVE_CORRECT_PATH_MISSING",
              "checked=", len(result.alternatives(limit=128)),
              "forest=", result.stats.get("forest_nodes"),
              "kbest_budget=", result.stats.get("kbest_budget_exceeded"),
              flush=True)


if __name__ == "__main__":
    main()
