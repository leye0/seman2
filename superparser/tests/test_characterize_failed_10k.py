"""Unit tests for the 10,000-sentence grammatical failure corpus."""
from __future__ import annotations
import unittest

from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from scripts.characterize_failed_10k import (
    ABLATIONS, relax_grammar, label_case, choose_probes,
)


def symbol(category, features=None, requires=()):
    return RuleSymbol(
        category,
        FeatureStructure.build(features or {}),
        requires=requires,
    )


class CharacterizeFailed10kTests(unittest.TestCase):
    def setUp(self):
        self.sample=Grammar((
            GrammarRule(
                "clause_restricted",
                (symbol("NP",{"number":"?n","person":"?p","subcat":"?s"},
                        requires=("subcat","wh")),
                 symbol("VP",{"number":"?n","person":"?p","vform":"finite"})),
                symbol("CLAUSE",{"number":"?n","person":"?p","voice":"active"}),
                2.0,
            ),
        ))

    def test_counterfactual_ablation_keeps_categories_rule_order_and_score(self):
        for name in ABLATIONS:
            with self.subTest(name=name):
                altered,changed=relax_grammar(self.sample,name)
                prior=self.sample.rules[0]
                new=altered.rules[0]
                self.assertEqual(prior.rule_id,new.rule_id)
                self.assertEqual(prior.score,new.score)
                self.assertEqual(
                    tuple(x.category for x in prior.rhs),
                    tuple(x.category for x in new.rhs))
                self.assertEqual(prior.lhs.category,new.lhs.category)
                self.assertEqual(len(new.rhs),len(prior.rhs))
                if name=="requires_any":
                    self.assertEqual(new.rhs[0].requires,())
                if name=="requires_subcat":
                    self.assertEqual(new.rhs[0].requires,("wh",))
                if name=="feature_number":
                    for sym in (new.lhs,)+new.rhs:
                        self.assertFalse(sym.features.has("number"))
                    self.assertIn("clause_restricted",changed)

    def test_failure_taxonomy_distinguishes_unproven_from_rejected(self):
        case={"completed":False,
              "kbest_budget_exceeded":False,
              "forest_budget_exceeded":False,
              "lexical_missing_tokens":[],
              "root_recognized":False}
        self.assertEqual(label_case(case),"no_root_under_current_grammar")
        self.assertEqual(label_case(dict(case,root_recognized=True)),
                         "root_without_feature_valid_witness")
        self.assertEqual(label_case(dict(case,forest_budget_exceeded=True)),
                         "forest_budget_no_root")
        self.assertEqual(label_case(dict(case,forest_budget_exceeded=True,
                                         root_recognized=True)),
                         "forest_budget_root_present")
        self.assertEqual(label_case(dict(case,kbest_budget_exceeded=True)),
                         "kbest_budget_unproven")
        self.assertEqual(label_case(dict(case,lexical_missing_tokens=["x"])),
                         "lexical_gap")
        self.assertEqual(label_case(dict(case,completed=True)),"complete")

    def test_probes_sample_each_failure_family_deterministically(self):
        cases=[{
            "index":i,"failure_family":"complete" if i%2 else "no_root_under_current_grammar",
            "full_ms":float(i+1),"length_band":"04-08" if i<10 else "17-24",
            "completed":bool(i%2),"tokens":5,
        } for i in range(30)]
        cache={i:(None,None) for i in range(30)}
        a=choose_probes(cases,cache,5)
        self.assertLessEqual(len(a),10)
        self.assertGreater(len(a),4)
        self.assertEqual([r["index"] for r in a],
                         [r["index"] for r in choose_probes(cases,cache,5)])
        self.assertEqual(
            set(r["failure_family"] for r in a),
            {"complete","no_root_under_current_grammar"})


if __name__=="__main__":
    unittest.main()
