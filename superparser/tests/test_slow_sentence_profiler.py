"""Regression tests for real-novel parser tail characterization."""
from __future__ import annotations

import unittest
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import Token, LexicalCandidate, LexicalLattice
from scripts.profile_gutenberg_slow_sentences import (
    quantile,distribution,token_band,characterization,characterize_tail,
    NUMERIC_FACTORS,BOOLEAN_FACTORS
)


def fake_record(index,ms):
    x={key:1 for key in NUMERIC_FACTORS}
    x.update({key:0 for key in BOOLEAN_FACTORS})
    x.update({
        "index":index,"book_ordinal":index,"sentence_sha256":str(index),
        "preview":"sample sentence for characterization",
        "tokens":5,"length_band":"04-08","characters":50,
        "lexical_candidates":12,"ambiguous_positions":3,
        "cross_token_or_split_spans":0,"completed":True,"indexed":True,
        "phase_dominant":"forest",
        "lexing_ms":1.0,"recognition_ms":ms-2.0,"kbest_ms":1.0,
        "full_ms":ms,"forest_nodes":10,"structural_derivations":15,
        "partial_states":20,"partial_derivations":22,
        "combinations_visited_for_best":4,"kbest_work_units":18,
        "forest_budget_exceeded":False,
        "kbest_budget_exceeded":False,
    })
    return x


class SlowSentenceProfilerTests(unittest.TestCase):
    def test_exact_quantiles_include_single_element(self):
        self.assertEqual(quantile([42.0],.95),42.0)
        self.assertEqual(quantile([1.,2.,3.],.5),2.0)
        self.assertEqual(distribution([1.0])["p50"],1.0)
        self.assertIsNone(quantile([],.5))

    def test_characterize_pos_ambiguity_without_assuming_parse(self):
        tokens=(Token(0,0,4,"that"),Token(1,5,9,"runs"))
        candidate=lambda start,end,surface,category:LexicalCandidate(
            start,end,surface,surface,category,FeatureStructure.empty())
        lattice=LexicalLattice("that runs",tokens,(
            candidate(0,4,"that","DET"),candidate(0,4,"that","PRONOUN"),
            candidate(5,9,"runs","V"),candidate(5,9,"runs","N")))
        traits=characterization(lattice.text,lattice)
        self.assertEqual(traits["tokens"],2)
        self.assertEqual(traits["ambiguous_positions"],2)
        self.assertEqual(traits["lexical_candidates"],4)
        self.assertEqual(traits["cross_token_or_split_spans"],0)
        self.assertTrue(traits["has_pronoun_reading"])
        self.assertEqual(token_band(8),"04-08")
        self.assertEqual(token_band(16),"09-16")
        self.assertEqual(token_band(24),"17-24")
        self.assertEqual(token_band(32),"25-32")

    def test_concentrated_tail_and_stratified_counters(self):
        cases=[fake_record(i,10.0) for i in range(99)]
        cases.append(fake_record(99,10000.0))
        result=characterize_tail(cases)
        self.assertEqual(result["n"],100)
        self.assertEqual(result["outlier_cohorts"]["over_5x_median"]["count"],1)
        self.assertEqual(result["outlier_cohorts"]["over_10x_median"]["count"],1)
        self.assertEqual(result["outlier_cohorts"]["over_1000ms"]["count"],1)
        self.assertGreater(result["runtime_concentration"]["top_1pct_share_pct"],90)
        self.assertEqual(result["top_40_slowest"][0]["index"],99)
        self.assertEqual(result["by_token_length"]["04-08"]["count"],100)
        self.assertEqual(result["outlier_cohorts"]["top_5pct_p95"]["count"],100
                         if result["outlier_threshold_ms"]["top_5pct_p95"]==10 else 1)

    def test_true_kbest_exhaustion_is_not_conflated_with_no_parse(self):
        cases=[fake_record(i,20.0+i) for i in range(20)]
        cases[-1]["completed"]=False
        cases[-1]["kbest_budget_exceeded"]=True
        result=characterize_tail(cases)
        self.assertEqual(result["completion"]["complete"],19)
        self.assertEqual(result["completion"]["kbest_work_limit_reached"],1)
        self.assertEqual(result["completion"]["no_full_analysis"],1)


if __name__=="__main__":
    unittest.main()
