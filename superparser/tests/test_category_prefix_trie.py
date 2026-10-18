"""Can an RHS category-prefix trie replace duplicated recognition work?

This is a research *oracle replay* over canonical forest nodes, not yet a
standalone parser or a replacement for feature-aware tree materialization.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from research.verbnet_lr.category_prefix_trie import CategoryPrefixTrie
from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice

DATA=Path(__file__).resolve().parents[1]/"data"


class CategoryTrieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources=ParserResources.from_dir(
            DATA,wordnet_dict=os.environ.get("WORDNET_DICT"))
        cls.parser=Parser(cls.resources,cache_size=0,max_items=20000)
        cls.trie=CategoryPrefixTrie(cls.parser._vector_grammar)

    def test_prefixes_project_back_to_all_rule_specific_dotted_states(self):
        for text in (
            "John opened the box.",
            "John gave Mary the box.",
            "The box was opened by John.",
            "I saw the man with the telescope.",
        ):
            with self.subTest(sentence=text):
                lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
                parsed=self.parser._vector_grammar.parse_lattice(
                    lattice,beam=80,max_items=20000,
                    goal_category="CLAUSE",kbest_work_limit=100000)
                forest=parsed.shared_forest
                self.assertFalse(forest.budget_exceeded)
                replay=self.trie.replay(forest)
                self.assertEqual(replay["projection_failures"],[])
                self.assertEqual(replay["projected_rule_states"],
                                 replay["canonical_partial_states"])
                self.assertGreater(replay["verified_edges"],0)
                self.assertGreater(
                    replay["canonical_partial_states"],
                    replay["shared_prefix_states"])

    def test_trie_preserves_distinct_rule_variants_for_same_category_prefix(self):
        variants=[
            tuple(node.variants) for node in self.trie.nodes
            if len(node.variants)>1]
        self.assertTrue(variants)
        self.assertTrue(any(len(v)>3 for v in variants))
        total=sum(len(rule.rhs_ids)
                  for rule in self.parser._vector_grammar.rules)
        self.assertEqual(sum(len(n.variants) for n in self.trie.nodes),total)
        self.assertLess(len(self.trie.nodes),total+1)


if __name__=="__main__":
    unittest.main()
