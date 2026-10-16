"""Quality gate must report nondeterministic repeat outcomes."""
import unittest
from scripts.assess_verbnet_grammar_quality import assess
from scripts.benchmark_verbnet_negatives import MODES


class QualityGateConsistencyTests(unittest.TestCase):
    def test_new_modes_and_unstable_repeats_are_reported(self):
        positive = {
            "cases": 2, "repetitions": 2,
            "summary": {name: {
                "explicit_gold_assertion_passed": 4, "complete": 4,
                "complete_but_nonconforming": 0,
                "total_ms": {"p50": 4.9, "p95": 8.0}
            } for name, _ in MODES},
            "per_split": {name: {"dev": {"complete": 2,
                                        "explicit_gold_passed": 2}}
                          for name, _ in MODES},
            "repeat_stability": {name: {
                "first_pass_gold": 2, "stable_gold": 2,
                "unstable_gold_ids": [], "unstable_completion_ids": [],
                "unstable_trace_ids": []
            } for name, _ in MODES},
            "diffs": {}
        }
        negative = {"summary": {name: {
            "negative_cases": 24, "negative_false_accepts": 1,
            "new_false_accepts_vs_baseline": []
        } for name, _ in MODES}}
        positive["repeat_stability"]["AR_reachable_guard3"] = {
            "first_pass_gold": 2, "stable_gold": 1,
            "unstable_gold_ids": ["synthetic_case"],
            "unstable_completion_ids": [],
            "unstable_trace_ids": ["synthetic_case"]
        }
        result = assess(positive, negative)
        stable = result["comparisons"]["AQ_reachable_guard1"]
        variable = result["comparisons"]["AR_reachable_guard3"]
        self.assertEqual(stable["gold_passed_cases"], 2)
        self.assertTrue(stable["quality_gate"])
        self.assertEqual(variable["gold_passed_cases"], 1)
        self.assertEqual(variable["gold_passed_first_repetition"], 2)
        self.assertEqual(variable["unstable_positive_cases"], ["synthetic_case"])
        self.assertFalse(variable["quality_gate"])


if __name__ == "__main__":
    unittest.main()
