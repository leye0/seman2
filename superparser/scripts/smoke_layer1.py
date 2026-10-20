"""Runnable, offline smoke test of Seman2's ONLY current Layer 1 routes.

Requires WORDNET_DICT containing WordNet 3.0 dict files. No benchmark
threshold is silently enabled in production: the alternate path below
is explicitly requested for this smoke test.
"""
from __future__ import annotations
import os
from pathlib import Path

from seman_parser.engine import Parser, ParserResources
from seman_parser.complexity_routing import ComplexityPolicy
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]
SHORT="John opened the box."
LONG=("John opened the box, and Mary gave the book to Robert while the other "
      "children waited near the doorway for their parents to arrive.")
DIALOGUE='"Hello," said Mary.'


def main():
    resources=ParserResources.from_dir(
        ROOT/"data",wordnet_dict=os.environ.get("WORDNET_DICT"))
    canonical=Parser(resources,cache_size=0,max_items=20000)
    routed=Parser(resources,cache_size=0,max_items=20000,
                  complexity_policy=ComplexityPolicy(1,min_tokens=17))
    for text,expected in ((SHORT,"canonical"),(LONG,"trie"),
                          (DIALOGUE,"canonical")):
        lattice=build_lattice(text,resources.lexicon)
        result=routed.parse(
            text,max_items=20000,kbest_work_limit=100000).result
        assert result.stats["complexity_route"]==expected,(
            text,result.stats.get("complexity_route"))
        assert result.text==text
        assert result.lattice.text==text
        assert bool(result.stats["lazy_trie_recognition"])==(expected=="trie")
        ordinary=canonical.parse(
            text,max_items=20000,kbest_work_limit=100000).result
        assert result.completed==ordinary.completed
        assert ([x.as_dict() for x in result.alternatives(limit=2)]==
                [x.as_dict() for x in ordinary.alternatives(limit=2)])
        print(f"OK route={expected} tokens={len(lattice.tokens)} "
              f"completed={result.completed} original_text_preserved=yes")
    print("Seman2 canonical + adaptive lazy-trie + dialogue smoke: PASS")


if __name__=="__main__":
    main()
