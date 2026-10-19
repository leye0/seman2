"""Fast, data-independent tests for the 50-sentence diagnostic labels."""
import unittest

from scripts.diagnose_novel_parses import classify, compact_stats, tally


class NovelDiagnosticsTests(unittest.TestCase):
    def test_exclusive_headlines(self):
        cases = (
            (False, {"budget_exceeded": True, "kbest_budget_exceeded": True}, "both_budgets_exceeded"),
            (False, {"budget_exceeded": True, "structural_root_nodes": 0}, "forest_budget_exceeded"),
            (False, {"kbest_budget_exceeded": True, "structural_root_nodes": 2}, "kbest_budget_exceeded"),
            (False, {"structural_root_nodes": 0}, "no_structural_root"),
            (False, {"structural_root_nodes": 3}, "roots_without_valid_analysis"),
            (True, {"budget_exceeded": True, "structural_root_nodes": 1}, "complete"),
        )
        for completed, stats, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify(completed, stats), expected)

    def test_keep_counters(self):
        stats = {
            "structural_root_nodes": 3, "combinations_visited_total": 17,
            "kbest_work_units": 25, "unification_rejections": 2,
        }
        exported = compact_stats(stats)
        for key, value in stats.items():
            self.assertEqual(exported[key], value)

    def test_exclusive_statuses_and_overlapping_flags(self):
        rows = [
            {"status": "complete", "forest_budget_exceeded": True,
             "kbest_budget_exceeded": False, "structural_root_nodes": 2},
            {"status": "both_budgets_exceeded", "forest_budget_exceeded": True,
             "kbest_budget_exceeded": True, "structural_root_nodes": 1},
            {"status": "no_structural_root", "structural_root_nodes": 0},
            {"status": "timeout"},
        ]
        result = tally(rows)
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["forest_budget_flag"], 2)
        self.assertEqual(result["kbest_budget_flag"], 1)
        self.assertEqual(result["complete_with_forest_saturation"], 1)
        self.assertEqual(sum(result["statuses"].values()), 4)


if __name__ == "__main__":
    unittest.main()
