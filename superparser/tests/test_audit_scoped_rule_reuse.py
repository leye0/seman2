"""The audit groups shapes and observed scope use without merging grammar."""
import unittest

from scripts.audit_scoped_rule_reuse import summarize_grammar, summarize_replay


def rule(name, plan, category, *rhs):
    return {"id": name, "provenance": {"source_plan": plan},
            "lhs": {"category": category},
            "rhs": [{"category": child} for child in rhs]}


class ScopedRuleReuseAudit(unittest.TestCase):
    def test_shapes_across_scopes_are_candidates_not_semantic_duplicates(self):
        rules = [
            rule("r1", "a", "NP", "NP", "REL-CLAUSE-OBJ"),
            rule("r2", "b", "NP", "NP", "REL-CLAUSE-OBJ"),
            rule("r3", "a", "CLAUSE", "NP", "VP"),
            rule("r4", "a", "CLAUSE", "NP", "VP"),
            rule("r5", None, "NP", "NP", "REL-CLAUSE-OBJ"),
        ]
        report = summarize_grammar(rules, {
            "r1": [{"compose": {"links": [{"relation": "RELATIVE_ANTECEDENT"}]}}],
            "r2": [{"compose": {"links": [{"relation": "COMPLEMENT"}]}}],
            "r3": [{"link": {"role": "CONJUNCT"}}],
        })
        self.assertEqual(report["scoped_productions"], 4)
        self.assertEqual(report["source_plans"], 2)
        self.assertEqual(report["cross_scope_category_shapes"], 1)
        self.assertEqual(report["productions_in_cross_scope_category_shapes"], 2)
        self.assertEqual(report["direct_recipe_relations"]["RELATIVE_ANTECEDENT"],
                         {"productions": 1, "plans": 1})
        self.assertEqual(report["direct_recipe_relations"]["CONJUNCT"],
                         {"productions": 1, "plans": 1})

    def test_only_completed_selected_roots_contribute_to_reuse(self):
        report = summarize_replay([
            {"status": "complete", "root_rule": "r1"},
            {"status": "complete", "root_rule": "r2"},
            {"status": "complete", "root_rule": "r3"},
            {"status": "complete", "root_rule": "generic"},
            {"status": "no_structural_root", "root_rule": None},
        ], {"r1": "a", "r2": "a", "r3": "b"})
        self.assertEqual((report["sources"], report["complete"]), (5, 4))
        self.assertEqual(report["complete_with_scoped_root"], 3)
        self.assertEqual(report["selected_plan_counts"], {"a": 2, "b": 1})
        self.assertEqual(report["plans_selected_once"], 1)


if __name__ == "__main__":
    unittest.main()
