"""Eligibility and noncausal output checks; independent of WordNet."""
from __future__ import annotations

import unittest

from scripts.probe_unscoped_residuals import (
    eligible_unscoped_residuals, summary_for, render,
)


class UnscopedLocalProbeTests(unittest.TestCase):
    def test_only_unsaturated_cases_without_dialogue_roots_are_replayed(self):
        rows = [
            {"index": 8, "status": "no_structural_root"},
            {"index": 116, "status": "roots_without_valid_analysis",
             "dialogue_attempt": {"structural_root_nodes": 0}},
            {"index": 64, "status": "roots_without_valid_analysis",
             "dialogue_attempt": {"structural_root_nodes": 3}},
            {"index": 235, "status": "forest_budget_exceeded"},
            {"index": 312, "status": "timeout"},
            {"index": 56, "status": "complete"},
        ]
        self.assertEqual([r["index"] for r in eligible_unscoped_residuals(rows)],
                         [8, 116])
        self.assertEqual(rows[2]["dialogue_attempt"]["structural_root_nodes"], 3)

    def test_only_proven_subtrees_count_and_censored_replays_stay_visible(self):
        rows = [
            {"index": 8, "case_id": "c:8", "source_text": "which I did",
             "canonical_status": "no_structural_root",
             "replay_outcome": "no_structural_root",
             "rejection_trace": {"independent_local_probe": {
                 "sampled_local_constituents": 2,
                 "witnesses": [{"category": "NP", "rule_id": "np_pronoun",
                                "analysis_span": [0, 5], "reference_span": [0, 5],
                                "children": [{"category": "PRON"}]}]}}},
            {"index": 116, "case_id": "c:116", "source_text": "another",
             "canonical_status": "roots_without_valid_analysis",
             "replay_outcome": "deadline_censored", "rejection_trace": None},
        ]
        summary = summary_for(rows)
        self.assertEqual(summary["cases"], 2)
        self.assertEqual(summary["independent_witnesses"], 2)
        self.assertEqual(summary["cases_with_independent_witnesses"], 1)
        self.assertTrue(summary["resource_censored_baseline_excluded"])
        report = render(rows, summary)
        self.assertIn("deadline_censored", report)
        self.assertIn("No sampled subtree proves", report)


if __name__ == "__main__":
    unittest.main()
