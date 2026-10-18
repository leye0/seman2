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
        cls.shared=VectorGrammar(cls.canonical.grammar,shared_trie_recognition=True)

    def test_category_trie_is_precompiled_and_shares_paths(self):
        count=sum(len(rule.rhs_ids) for rule in self.canonical.rules)
        self.assertGreater(count,len(self.shared.trie_nodes))
        self.assertGreater(len(self.shared.trie_nodes),200)

    def test_independent_trie_recognition_retains_rule_specific_forests(self):
        for text in SHORT:
            with self.subTest(text=text):
                lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
                baseline=self.canonical.parse_lattice(
                    lattice,beam=80,max_items=20000,goal_category="CLAUSE",
                    kbest_work_limit=100000)
                experiment=self.shared.parse_lattice(
                    lattice,beam=80,max_items=20000,goal_category="CLAUSE",
                    kbest_work_limit=100000)
                self.assertFalse(baseline.stats["budget_exceeded"])
                self.assertFalse(experiment.stats["budget_exceeded"])
                self.assertEqual(baseline.completed,experiment.completed)
                for field in ("forest_nodes","partial_states",
                              "partial_derivations","structural_derivations"):
                    self.assertEqual(baseline.stats[field],
                                     experiment.stats[field],field)
                expected={
                    (p.rule_index,p.dot,p.start,p.end):
                    {(d.previous_id,d.child_id) for d in p.derivations}
                    for p in baseline.shared_forest.partials}
                received={
                    (p.rule_index,p.dot,p.start,p.end):
                    {(d.previous_id,d.child_id) for d in p.derivations}
                    for p in experiment.shared_forest.partials}
                # IDs and traversal orders can differ between algorithms;
                # match predecessor rule/slot/span, not raw integer ID.
                expected2={}
                received2={}
                for target,forest in ((expected2,baseline.shared_forest),
                                      (received2,experiment.shared_forest)):
                    for p in forest.partials:
                        k=(p.rule_index,p.dot,p.start,p.end)
                        target[k]={
                            (None if d.previous_id is None else (
                                forest.partials[d.previous_id].rule_index,
                                forest.partials[d.previous_id].dot,
                                forest.partials[d.previous_id].start,
                                forest.partials[d.previous_id].end),
                             forest.nodes[d.child_id].start,
                             forest.nodes[d.child_id].end,
                             forest.nodes[d.child_id].category_id)
                            for d in p.derivations}
                self.assertEqual(expected2,received2)
                self.assertEqual(
                    baseline.best().as_dict() if baseline.best() else None,
                    experiment.best().as_dict() if experiment.best() else None)
                self.assertEqual(
                    [t.as_dict() for t in baseline.alternatives(limit=3)],
                    [t.as_dict() for t in experiment.alternatives(limit=3)])


if __name__=="__main__":
    unittest.main()
