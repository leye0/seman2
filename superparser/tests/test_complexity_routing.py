"""Adaptive routing must protect easy sentences and all grammatical evidence.

Research only: explicit thresholds are not a calibrated production policy.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from seman_parser.complexity_routing import ComplexityPolicy, StructuralRiskRouter
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice
from research.verbnet_lr.continuation_probe import ContinuationIndex

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
                rule_start_threshold=1,min_tokens=17,
                difficult_strategy="flat"))
        cls.always_canonical=Parser(cls.resources,cache_size=0,max_items=20000,
            complexity_policy=ComplexityPolicy(
                rule_start_threshold=10**12,min_tokens=17,
                difficult_strategy="flat"))

    def test_score_is_identical_to_original_compiled_continuation_probe(self):
        indexed=ContinuationIndex(self.reference._vector_grammar.grammar)
        router=self.adaptive._complexity_router
        for text in (*EASY,*HARD):
            lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
            self.assertEqual(router.score(lattice),
                             indexed.fast_signal(lattice)["fast_start_sum"])

    def test_fast_sentences_do_not_even_probe_or_use_special_parser(self):
        router=self.adaptive._complexity_router
        original=router.score
        def forbidden(_):
            raise AssertionError("Risk scoring must be bypassed for short text")
        router.score=forbidden
        try:
            for text in EASY:
                lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
                result=self.adaptive.parse_grammar_lattice(
                    lattice,max_items=20000,kbest_work_limit=100000)
                base=self.reference.parse_grammar_lattice(
                    lattice,max_items=20000,kbest_work_limit=100000)
                self.assertEqual(result.stats["complexity_route"],"canonical")
                self.assertEqual(result.stats["complexity_probe_ms"],0.0)
                self.assertEqual(result.stats["complexity_score"],None)
                self.assertFalse(result.stats["online_prefix_edges_enabled"])
                self.assertEqual(
                    result.best().as_dict() if result.best() else None,
                    base.best().as_dict() if base.best() else None)
        finally:
            router.score=original

    def test_hard_sentences_route_and_preserve_complete_forest_and_kbest(self):
        for text in HARD:
            with self.subTest(text=text):
                lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
                original=self.reference.parse_grammar_lattice(
                    lattice,max_items=20000,kbest_work_limit=100000)
                routed=self.adaptive.parse_grammar_lattice(
                    lattice,max_items=20000,kbest_work_limit=100000)
                self.assertEqual(routed.stats["complexity_route"],"flat")
                self.assertTrue(routed.stats["online_prefix_edges_enabled"])
                self.assertTrue(routed.stats["online_prefix_flat_enabled"])
                for field in (
                    "forest_nodes","partial_states","partial_derivations",
                    "structural_derivations","budget_exceeded",
                    "kbest_budget_exceeded","recognition_operations",
                ):
                    self.assertEqual(original.stats[field],
                                     routed.stats[field],field)
                self.assertEqual(
                    [t.as_dict() for t in original.alternatives(limit=3)],
                    [t.as_dict() for t in routed.alternatives(limit=3)])
                self.assertEqual(original.completed,routed.completed)
                for a,b in zip(original.shared_forest.partials,
                               routed.shared_forest.partials):
                    self.assertEqual(
                        [(d.previous_id,d.child_id) for d in a.derivations],
                        [(d.previous_id,d.child_id) for d in b.derivations])

    def test_low_risk_long_sentence_can_stay_canonical(self):
        lattice=build_lattice(HARD[0],self.resources.lexicon,multiword_max=1)
        result=self.always_canonical.parse_grammar_lattice(
            lattice,max_items=20000,kbest_work_limit=100000)
        self.assertEqual(result.stats["complexity_route"],"canonical")
        self.assertEqual(result.stats["complexity_reason"],"risk_below_threshold")
        self.assertFalse(result.stats["online_prefix_edges_enabled"])
        self.assertIsInstance(result.stats["complexity_score"],int)

    def test_dialogue_never_enters_unvalidated_special_grammar(self):
        text='"Hello," said Mary.'
        lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
        router=StructuralRiskRouter(self.reference._vector_grammar.grammar,
                                    ComplexityPolicy(1,min_tokens=1))
        decision=router.choose(lattice,dialogue=True)
        self.assertEqual(decision.strategy,"canonical")
        self.assertEqual(decision.measured_ms,0)
        self.assertIsNone(decision.score)
        result=self.adaptive.parse_grammar_lattice(
            lattice,max_items=20000,kbest_work_limit=100000)
        self.assertFalse(result.stats["online_prefix_edges_enabled"])

    def test_explicit_length_band_thresholds_are_enforced(self):
        long_text=HARD[0]
        lattice=build_lattice(long_text,self.resources.lexicon,multiword_max=1)
        n=len(lattice.tokens)
        self.assertGreaterEqual(n,17)
        high=ComplexityPolicy(
            rule_start_threshold=1,min_tokens=17,
            band_thresholds=((17,100,10**12),))
        self.assertEqual(high.threshold_for(n),10**12)
        self.assertEqual(high.threshold_for(101),1)
        decision=StructuralRiskRouter(
            self.reference._vector_grammar.grammar,high).choose(lattice)
        self.assertEqual(decision.strategy,"canonical")
        self.assertEqual(decision.reason,"risk_below_threshold")
        low=ComplexityPolicy(
            rule_start_threshold=10**12,min_tokens=17,
            band_thresholds=((17,100,1),))
        self.assertEqual(
            StructuralRiskRouter(self.reference._vector_grammar.grammar,low
            ).choose(lattice).strategy,"flat")

    def test_banded_policy_rejects_overlap_or_under_min_tokens(self):
        with self.assertRaises(ValueError):
            ComplexityPolicy(1,band_thresholds=((17,24,20),(24,32,30)))
        with self.assertRaises(ValueError):
            ComplexityPolicy(1,band_thresholds=((8,16,20),))
        with self.assertRaises(ValueError):
            ComplexityPolicy(1,band_thresholds=((17,20,0),))

    def test_indexed_recognition_preserves_all_rule_paths_on_difficult_prose(self):
        fast=Parser(self.resources,cache_size=0,max_items=20000,
            complexity_policy=ComplexityPolicy(
                rule_start_threshold=1,min_tokens=17,
                difficult_strategy="indexed"))
        for text in HARD:
            with self.subTest(text=text):
                lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
                canonical=self.reference.parse_grammar_lattice(
                    lattice,max_items=20000,kbest_work_limit=100000)
                indexed=fast.parse_grammar_lattice(
                    lattice,max_items=20000,kbest_work_limit=100000)
                self.assertEqual(indexed.stats["complexity_route"],"indexed")
                self.assertTrue(indexed.stats["indexed_recognition_enabled"])
                self.assertFalse(indexed.stats["online_prefix_edges_enabled"])
                for field in ("forest_nodes","partial_states",
                              "partial_derivations","structural_derivations",
                              "partial_proposals","duplicate_partial_proposals",
                              "recognition_operations","budget_exceeded",
                              "kbest_budget_exceeded"):
                    self.assertEqual(canonical.stats[field],indexed.stats[field],field)
                self.assertEqual(canonical.completed,indexed.completed)
                self.assertEqual(
                    [x.as_dict() for x in canonical.alternatives(limit=3)],
                    [x.as_dict() for x in indexed.alternatives(limit=3)])
                self.assertEqual(len(canonical.shared_forest.partials),
                                 len(indexed.shared_forest.partials))
                for old,new in zip(canonical.shared_forest.partials,
                                   indexed.shared_forest.partials):
                    self.assertEqual(
                        (old.rule_index,old.dot,old.start,old.end),
                        (new.rule_index,new.dot,new.start,new.end))
                    self.assertEqual(
                        [(d.previous_id,d.child_id) for d in old.derivations],
                        [(d.previous_id,d.child_id) for d in new.derivations])

    def test_indexed_recognition_never_processes_easy_or_dialogue_sentences(self):
        indexed=Parser(self.resources,cache_size=0,max_items=20000,
            complexity_policy=ComplexityPolicy(
                rule_start_threshold=1,min_tokens=17,
                difficult_strategy="indexed"))
        for text in (*EASY, '"Hello," said Mary.'):
            lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
            result=indexed.parse_grammar_lattice(
                lattice,max_items=20000,kbest_work_limit=100000)
            self.assertFalse(result.stats["indexed_recognition_enabled"])
            self.assertEqual(result.stats["complexity_route"],"canonical")

    def test_no_invented_default_threshold_or_bad_policy(self):
        self.assertIsNone(self.reference._complexity_router)
        for cutoff in (0,-1):
            with self.assertRaises(ValueError):
                ComplexityPolicy(cutoff)
        with self.assertRaises(ValueError):
            ComplexityPolicy(1,difficult_strategy="unvalidated")


if __name__=="__main__":
    unittest.main()
