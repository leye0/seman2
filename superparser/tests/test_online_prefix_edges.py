"""Online shared grammar-prefix edges must preserve the canonical forest.

No new accepted syntax, lexical candidate deletion, rule coalescing or budget
discounting is permitted. Test the *entire* packed derivation history, not
only the selected best tree.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice
from seman_parser.vector_chart import VectorGrammar

DATA=Path(__file__).resolve().parents[1]/"data"
CASES=(
    "John opened the box.",
    "John gave Mary the box.",
    "The box was opened by John.",
    "I saw the man with the telescope.",
    '"Hello," said Mary.',
    "She walked slowly, and John opened the door.",
)


class OnlinePrefixParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources=ParserResources.from_dir(
            DATA,wordnet_dict=os.environ.get("WORDNET_DICT"))
        cls.reference=Parser(cls.resources,cache_size=0,max_items=20000)
        cls.online=Parser(cls.resources,cache_size=0,max_items=20000)
        original=cls.online._vector_grammar
        cls.online._vector_grammar=VectorGrammar(
            original.grammar,online_prefix_edges=True)
        dialog=cls.online._dialogue_vector_grammar
        if dialog is not None:
            cls.online._dialogue_vector_grammar=VectorGrammar(
                dialog.grammar,online_prefix_edges=True,
                preserve_quote_delimiters=True)

    def test_complete_canonical_forests_and_kbest_identical(self):
        hits=0
        for sentence in CASES:
            with self.subTest(sentence=sentence):
                lattice=build_lattice(sentence,self.resources.lexicon,multiword_max=1)
                a=self.reference.parse_grammar_lattice(
                    lattice,max_items=20000,kbest_work_limit=100000)
                b=self.online.parse_grammar_lattice(
                    lattice,max_items=20000,kbest_work_limit=100000)
                for key in (
                    "completed","budget_exceeded","kbest_budget_exceeded",
                    "forest_nodes","partial_states","partial_derivations",
                    "structural_derivations","partial_proposals",
                    "duplicate_partial_proposals","recognition_operations",
                ):
                    self.assertEqual(
                        a.completed if key=="completed" else a.stats.get(key),
                        b.completed if key=="completed" else b.stats.get(key),
                        key)
                self.assertEqual(a.best().as_dict() if a.best() else None,
                                 b.best().as_dict() if b.best() else None)
                self.assertEqual(
                    [x.as_dict() for x in a.alternatives(limit=3)],
                    [x.as_dict() for x in b.alternatives(limit=3)])
                self.assertEqual(len(a.shared_forest.partials),
                                 len(b.shared_forest.partials))
                for original,new in zip(a.shared_forest.partials,
                                        b.shared_forest.partials):
                    self.assertEqual(
                        (original.rule_index,original.dot,original.start,
                         original.end),
                        (new.rule_index,new.dot,new.start,new.end))
                    self.assertEqual(
                        [(d.previous_id,d.child_id) for d in original.derivations],
                        [(d.previous_id,d.child_id) for d in new.derivations])
                self.assertFalse(a.stats["online_prefix_edges_enabled"])
                self.assertTrue(b.stats["online_prefix_edges_enabled"])
                hits+=b.stats["online_prefix_shared_edge_hits"]
        self.assertGreater(hits,0)

    def test_online_compact_membership_is_also_accessible_to_lazy_materializer(self):
        lattice=build_lattice("John opened the box.",self.resources.lexicon,
                              multiword_max=1)
        result=self.online.parse_grammar_lattice(
            lattice,max_items=20000,kbest_work_limit=100000)
        forest=result.shared_forest
        store=forest.prefix_store
        self.assertIsNotNone(store)
        self.assertEqual(store.diagnostics()["online_prefix_member_count"],
                         len(forest.partials))
        for partial in forest.partials:
            self.assertIsNone(partial.seen)
            self.assertIs(partial.derivations.store,store)
            if partial.derivations:
                self.assertEqual(partial.derivations[-1],
                                 tuple(partial.derivations)[-1])


if __name__=="__main__":
    unittest.main()
