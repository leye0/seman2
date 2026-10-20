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
