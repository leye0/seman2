"""Positive local-witness sampling contract, independent of WordNet."""
from __future__ import annotations

import unittest

from seman_parser.local_constituent_proofs import BoundedLocalConstituentProofs


def record(pool, *, category="VP", start=1, end=15, rule="vp_transitive",
           child_count=2, requested=(), witnessed=(), ref=None):
    pool.record(
        category=category, analysis_span=(start, end), rule_id=rule,
        children=[{"category": "NP", "analysis_span": (start + i, start + i + 1),
                   "rule_id": "np_bare"} for i in range(child_count)],
        verified_features={"vform": "finite"},
        required_context_features={"number": "plural"},
        required_positive_features=requested,
        witnessed_positive_features=witnessed,
        materialized_analysis=ref,
    )


class LocalConstituentProofTests(unittest.TestCase):
    def test_only_accepted_rule_compositions_are_reported_as_local(self):
        pool = BoundedLocalConstituentProofs(4)
        record(pool, requested=("number",), witnessed=("number", "vform"))
        result = pool.as_dict()
        self.assertEqual(result["observed_materialized_rule_analyses"], 1)
        witness = result["witnesses"][0]
        self.assertEqual(witness["rule_id"], "vp_transitive")
        self.assertEqual(witness["analysis_span"], [1, 15])
        self.assertEqual(len(witness["children"]), 2)
        self.assertEqual(witness["required_positive_features"], ["number"])
        self.assertEqual(witness["verified_features"]["vform"], "finite")
        self.assertFalse(result["global_tree_proven"])
        self.assertFalse(witness["whole_sentence_grammaticality_proven"])
        self.assertFalse(result["sentence_grammatical_fault_established"])

    def test_missing_positive_feature_does_not_become_a_proof(self):
        pool = BoundedLocalConstituentProofs(3)
        with self.assertRaisesRegex(ValueError, "missing positive"):
            record(pool, requested=("number",), witnessed=("person",))
        self.assertEqual(pool.as_dict()["observed_materialized_rule_analyses"], 0)

    def test_bounded_diverse_samples_prefer_long_spans(self):
        pool = BoundedLocalConstituentProofs(3)
        for i in range(15):
            record(pool, category="NP", start=i, end=i+2, rule=f"np_{i}")
        record(pool, category="VP", start=2, end=24, rule="vp_full")
        record(pool, category="PP", start=5, end=28, rule="pp_full")
        result = pool.as_dict()
        self.assertEqual(result["observed_materialized_rule_analyses"], 17)
        self.assertEqual(result["sampled_local_constituents"], 3)
        self.assertTrue(result["truncated"])
        self.assertEqual({w["rule_id"] for w in result["witnesses"]} &
                         {"vp_full", "pp_full"}, {"vp_full", "pp_full"})

    def test_same_span_does_not_monopolize_sample(self):
        pool = BoundedLocalConstituentProofs(4)
        for i in range(20):
            record(pool, category="NP", start=0, end=9, rule=f"np_variant_{i}")
        result = pool.as_dict()
        self.assertLessEqual(result["sampled_local_constituents"], 2)
        self.assertEqual(result["observed_materialized_rule_analyses"], 20)

    def test_private_materialized_references_follow_bounded_replacement(self):
        pool = BoundedLocalConstituentProofs(1)
        first, second = object(), object()
        record(pool, category="NP", start=0, end=2, ref=first)
        record(pool, category="NP", start=0, end=11, ref=second)
        retained = pool.retained_analyses()
        self.assertEqual(len(retained), 1)
        self.assertIs(retained[0][1], second)
        self.assertEqual(retained[0][0]["analysis_span"], [0, 11])
        self.assertNotIn("materialized_analysis", str(pool.as_dict()))


if __name__ == "__main__":
    unittest.main()
