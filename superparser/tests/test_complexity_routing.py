"""Contract of the TWO supported Layer 1 recognizers.

The canonical engine is the default. The lazy shared trie is selected only
for explicitly configured high-risk nonquoted ordinary prose. Short text
never invokes a predictor or the trie.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from seman_parser.complexity_routing import ComplexityPolicy, StructuralRiskRouter
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

DATA=Path(__file__).resolve().parents[1]/"data"
EASY=("John opened the box.","John gave Mary the box.",
      "The box was opened by John.")
HARD=(
    "John opened the box, and Mary gave the book to Robert while the other "
    "children waited near the doorway for their parents to arrive.",
    "The doctor opened the door, and the old man stood beside the table "
    "while the younger children waited quietly in the hallway.",
)


class AdaptiveRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources=ParserResources.from_dir(
            DATA,wordnet_dict=os.environ.get("WORDNET_DICT"))
        cls.reference=Parser(cls.resources,cache_size=0,max_items=20000)
        cls.adaptive=Parser(cls.resources,cache_size=0,max_items=20000,
            complexity_policy=ComplexityPolicy(
                rule_start_threshold=1,min_tokens=17))
        cls.canonical_long=Parser(cls.resources,cache_size=0,max_items=20000,
            complexity_policy=ComplexityPolicy(
                rule_start_threshold=10**12,min_tokens=17))

    def lattice(self,text):
        return build_lattice(text,self.resources.lexicon,multiword_max=1)

    def test_default_is_only_canonical_and_policy_allows_only_trie(self):
        self.assertIsNone(self.reference._complexity_router)
        self.assertFalse(self.reference._vector_grammar.lazy_trie_recognition)
        self.assertTrue(self.adaptive._difficult_vector_grammar.lazy_trie_recognition)
        for value in (0,-1):
            with self.assertRaises(ValueError):
                ComplexityPolicy(value)
        with self.assertRaises(ValueError):
            ComplexityPolicy(1,difficult_strategy="flat")
        with self.assertRaises(ValueError):
            ComplexityPolicy(1,difficult_strategy="online")

    def test_easy_short_circuits_before_any_lexical_risk_score(self):
        router=self.adaptive._complexity_router
        original=router.score
        def forbidden(_):
            raise AssertionError("Fast path must NEVER evaluate risk")
        router.score=forbidden
        try:
            for sentence in EASY:
                with self.subTest(sentence=sentence):
                    lattice=self.lattice(sentence)
                    observed=self.adaptive.parse(
                        lattice.text,max_items=20000,kbest_work_limit=100000).result
                    baseline=self.reference.parse(
                        lattice.text,max_items=20000,kbest_work_limit=100000).result
                    self.assertEqual(observed.stats["complexity_route"],"canonical")
                    self.assertEqual(observed.stats["complexity_probe_ms"],0.0)
                    self.assertIsNone(observed.stats["complexity_score"])
                    self.assertFalse(observed.stats["lazy_trie_recognition"])
                    self.assertEqual(
                        observed.best().as_dict() if observed.best() else None,
                        baseline.best().as_dict() if baseline.best() else None)
        finally:
            router.score=original

    def test_long_complex_sentences_use_shared_trie_with_kbest_parity(self):
        for sentence in HARD:
            with self.subTest(sentence=sentence):
                lattice=self.lattice(sentence)
                base=self.reference.parse(
                    lattice.text,max_items=20000,kbest_work_limit=100000).result
                fast=self.adaptive.parse(
                    lattice.text,max_items=20000,kbest_work_limit=100000).result
                self.assertEqual(fast.stats["complexity_route"],"trie")
                self.assertTrue(fast.stats["lazy_trie_recognition"])
                self.assertEqual(base.completed,fast.completed)
                # A hard max-items cutoff interrupts the two agendas at
                # different points; the resulting partial forests cannot
                # certify identical best rankings. Parity is mandatory only
                # when both recognitions finished without saturation.
                if (base.stats.get("budget_exceeded")
                        or fast.stats.get("budget_exceeded")):
                    continue
                self.assertEqual(
                    [x.as_dict() for x in base.alternatives(limit=2)],
                    [x.as_dict() for x in fast.alternatives(limit=2)])

    def test_long_below_threshold_remains_canonical(self):
        result=self.canonical_long.parse(
            HARD[0],max_items=20000,kbest_work_limit=100000).result
        self.assertEqual(result.stats["complexity_reason"],"risk_below_threshold")
        self.assertFalse(result.stats["lazy_trie_recognition"])
        self.assertIsInstance(result.stats["complexity_score"],int)

    def test_quotes_and_dialogue_never_enter_unverified_trie(self):
        for sentence in ('"Hello," said Mary.',
                         '"I am tired," said Mary, "and John opened the door."'):
            lattice=self.lattice(sentence)
            result=self.adaptive.parse(
                lattice.text,max_items=20000,kbest_work_limit=100000).result
            self.assertFalse(result.stats["lazy_trie_recognition"])
        router=StructuralRiskRouter(self.reference._vector_grammar.grammar,
                                    ComplexityPolicy(1,min_tokens=1))
        decision=router.choose(self.lattice('"Hello," said Mary.'),dialogue=True)
        self.assertEqual(decision.strategy,"canonical")
        self.assertIsNone(decision.score)

    def test_explicit_nonoverlapping_length_thresholds(self):
        size=len(self.lattice(HARD[0]).tokens)
        p=ComplexityPolicy(1,band_thresholds=((17,100,10**12),))
        self.assertEqual(p.threshold_for(size),10**12)
        self.assertEqual(p.threshold_for(101),1)
        for bands in (((17,24,20),(24,32,30)),((8,16,20),),((17,20,0),)):
            with self.assertRaises(ValueError):
                ComplexityPolicy(1,band_thresholds=bands)


if __name__=="__main__":
    unittest.main()
