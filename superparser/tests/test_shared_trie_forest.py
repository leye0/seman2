"""Real online trie recognizer: canonical forest + top-k parity controls."""
import os
from pathlib import Path
import unittest

from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice
from seman_parser.vector_chart import VectorGrammar

DATA=Path(__file__).resolve().parents[1]/"data"
SHORT=(
    "John opened the box.",
    "John gave Mary the box.",
    "The box was opened by John.",
    "I saw the man with the telescope.",
)


class SharedTrieForestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources=ParserResources.from_dir(
            DATA,wordnet_dict=os.environ.get("WORDNET_DICT"))
        cls.parser=Parser(cls.resources,cache_size=0,max_items=20000)
        cls.canonical=cls.parser._vector_grammar
        cls.lazy=VectorGrammar(cls.canonical.grammar,lazy_trie_recognition=True)

    def test_category_trie_is_precompiled_and_shares_paths(self):
        count=sum(len(rule.rhs_ids) for rule in self.canonical.rules)
        self.assertGreater(count,len(self.lazy.trie_nodes))
        self.assertGreater(len(self.lazy.trie_nodes),200)

    def test_lazy_rule_projection_retains_all_canonical_trees(self):
        for text in SHORT:
            with self.subTest(text=text):
                lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
                original=self.canonical.parse_lattice(
                    lattice,beam=80,max_items=20000,goal_category="CLAUSE",
                    kbest_work_limit=100000)
                lazy=self.lazy.parse_lattice(
                    lattice,beam=80,max_items=20000,goal_category="CLAUSE",
                    kbest_work_limit=100000)
                self.assertFalse(original.stats["budget_exceeded"])
                self.assertFalse(lazy.stats["budget_exceeded"])
                self.assertEqual(original.completed,lazy.completed)
                for key in ("forest_nodes","partial_states",
                            "partial_derivations","structural_derivations"):
                    self.assertEqual(original.stats[key],lazy.stats[key],key)
                self.assertEqual(
                    original.best().as_dict() if original.best() else None,
                    lazy.best().as_dict() if lazy.best() else None)
                self.assertEqual(
                    [x.as_dict() for x in original.alternatives(limit=3)],
                    [x.as_dict() for x in lazy.alternatives(limit=3)])
                def normalized(forest):
                    result={}
                    for p in forest.partials:
                        key=(p.rule_index,p.dot,p.start,p.end)
                        result[key]={
                            (None if d.previous_id is None else (
                                forest.partials[d.previous_id].rule_index,
                                forest.partials[d.previous_id].dot,
                                forest.partials[d.previous_id].start,
                                forest.partials[d.previous_id].end),
                             forest.nodes[d.child_id].category_id,
                             forest.nodes[d.child_id].start,
                             forest.nodes[d.child_id].end)
                            for d in p.derivations}
                    return result
                self.assertTrue(lazy.stats["lazy_trie_recognition"])
                # The parser completed without allocating eager rule partials.
                # The full-edge oracle walk below *intentionally* forces
                # every virtual partial to be materialized for comparison.
                self.assertLess(
                    len(lazy.shared_forest.partials.cached),
                    len(lazy.shared_forest.partials))
                self.assertEqual(normalized(original.shared_forest),
                                 normalized(lazy.shared_forest))
                self.assertEqual(
                    len(lazy.shared_forest.partials.cached),
                    len(lazy.shared_forest.partials))



if __name__=="__main__":
    unittest.main()
