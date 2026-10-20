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


if __name__ == "__main__":
    main()
