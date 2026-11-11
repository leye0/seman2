"""Static grammar risk inventory must never be confused with proof of a bug."""
from __future__ import annotations

import unittest

from scripts.audit_fragment_grammar_rules import analyze, classify_rule, render_markdown


class FragmentRuleAuditTests(unittest.TestCase):
    def test_tentative_root_without_overt_predicate_is_flagged(self):
        sample = {
            "id": "clause_elided_contextual_predicate",
            "lhs": {"category": "CLAUSE"},
            "rhs": [{"category": "COORD"}, {"category": "NP"}],
        }
        flags = classify_rule(sample)
        self.assertIn("clause_without_overt_predicate", flags)
        self.assertIn("ellipsis_or_fragment_license", flags)
        self.assertIn("root_started_by_coordinator", flags)

    def test_legitimate_matrix_and_imperative_not_declared_bad(self):
        for rhs in (["NP", "VP"], ["VP-NP"]):
            rule = {
                "id": "fully_licensed_clause",
                "lhs": {"category": "CLAUSE"},
                "rhs": [{"category": c} for c in rhs],
            }
            flags = classify_rule(rule)
            self.assertNotIn("clause_without_overt_predicate", flags)
        # A candidate flag is not a false-positive diagnosis or deletion.
        candidate = {"id": "nominal_utterance", "lhs": {"category": "CLAUSE"},
                     "rhs": [{"category": "NP"}]}
        self.assertIn("clause_without_overt_predicate", classify_rule(candidate))

    def test_report_distinguishes_added_candidates_and_no_deletion(self):
        rules = [
            {"id": "regular_clause", "lhs": {"category": "CLAUSE"},
             "rhs": [{"category": "NP"}, {"category": "VP"}]},
            {"id": "ellipsis_unit", "lhs": {"category": "CLAUSE"},
             "rhs": [{"category": "NP"}]},
        ]
        original = [dict(x) for x in rules]
        result = analyze(rules, {"regular_clause", "old_rule"},
                         prior_commit="abc123")
        self.assertEqual(result["baseline_count"], 2)
        self.assertEqual(result["rules_added_since_baseline"], 1)
        self.assertEqual(result["rules_removed_since_baseline"], 1)
        self.assertEqual(result["review_candidate_count"], 1)
        self.assertTrue(result["candidates"][0]["introduced_after_baseline"])
        self.assertTrue(result["requires_ranking_tree_ablation_before_deletion"])
        self.assertEqual(rules, original)
        self.assertIn("Aucune règle n'est supprimée automatiquement",
                      render_markdown(result))

    def test_duplicate_rule_ids_fail_closed(self):
        rule = {"id": "same", "lhs": {"category": "CLAUSE"},
                "rhs": [{"category": "VP"}]}
        with self.assertRaises(ValueError):
            analyze([rule, rule], set(), prior_commit="snapshot")


if __name__ == "__main__":
    unittest.main()
