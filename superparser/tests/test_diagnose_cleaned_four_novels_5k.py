"""Checks for cleaned 5000-sentence failure diagnoses."""
from __future__ import annotations
from collections import Counter
from types import SimpleNamespace
import unittest

from scripts.diagnose_cleaned_four_novels_5k import (
    failure_status, lexical_diagnostics, forest_diagnostics, summary,
)
from seman_parser.segmentation import LexicalLattice, LexicalCandidate, Token
from seman_parser.features import FeatureStructure


class CleanedFourNovelDiagnosisTests(unittest.TestCase):
    def test_budget_status_is_never_misclassified_as_no_rule(self):
        self.assertEqual(failure_status(True,False,True,True),"complete")
        self.assertEqual(failure_status(False,False,True,False),"forest_budget_no_root")
        self.assertEqual(failure_status(False,True,True,False),"forest_budget_root_present")
        self.assertEqual(failure_status(False,True,False,True),"kbest_budget_unproven")
        self.assertEqual(failure_status(False,False,False,True),"kbest_budget_unproven")
        self.assertEqual(failure_status(False,False,False,False),"no_root_under_current_grammar")
        self.assertEqual(failure_status(False,True,False,False),"root_without_feature_valid_witness")

    def test_punctuation_is_not_treated_as_missing_word(self):
        tokens=(Token(0,0,1,"'"),Token(1,2,6,"don't"),
                Token(2,7,8,"."))
        lattice=LexicalLattice("' don't.",tokens,(
            LexicalCandidate(2,4,"do","do","V",FeatureStructure.empty()),
            LexicalCandidate(4,6,"n't","not","NEG",FeatureStructure.empty()),
        ))
        d=lexical_diagnostics(lattice)
        self.assertEqual(d["uncovered_punctuation_token_count"],2)
        self.assertEqual(d["uncovered_wordlike_token_count"],1)
        self.assertEqual(d["tokens_without_one_covering_candidate"],["'","don't","."])

    def test_structural_root_witness_distinction(self):
        class Forest:
            def __init__(self):
                self.nodes=[SimpleNamespace(start=0,end=7,category="CLAUSE",
                                            derivations=[1,2])]
                self.partials=[]
            def _root_span(self,start,end):
                return start==0 and end==7
        forest=Forest()
        result=forest_diagnostics(forest,"CLAUSE")
        self.assertTrue(result["root_recognized"])
        self.assertEqual(result["root_derivation_count"],2)
        self.assertEqual(result["top_rules_by_partial_states"],[])

    def test_aggregate_uses_author_labels_and_preserves_budget(self):
        common={
            "full_ms":10.0,"lexing_ms":1.0,"recognition_ms":6.0,
            "kbest_ms":3.0,"tokens":6,"lexical_candidates":10,
            "ambiguous_positions":2,"partial_states":40,"partial_rule_counts":[["r",4]],
            "completed":False,"forest_budget_exceeded":True,
            "kbest_budget_exceeded":False,
            "failure_family":"forest_budget_no_root",
        }
        rows=[dict(common,book_id=766),dict(common,book_id=1342,full_ms=40.0)]
        books=[{"id":766,"title":"David Copperfield","author":"Charles Dickens",
                "sha256":"testhash","selected":1},
               {"id":1342,"title":"Pride and Prejudice","author":"Jane Austen",
                "sha256":"testhash2","selected":1}]
        s=summary(rows,books)
        self.assertEqual(s["overall"]["n"],2)
        self.assertEqual(s["overall"]["forest_budget"],2)
        self.assertEqual(s["overall"]["total_ms"]["p50"],25)
        self.assertEqual(s["by_book"]["1342"]["data"]["n"],1)
        self.assertEqual(s["partial_rule_cohorts"]["forest_saturated"]["top_partial_producers"],[("r",8)])


if __name__=="__main__":
    unittest.main()
