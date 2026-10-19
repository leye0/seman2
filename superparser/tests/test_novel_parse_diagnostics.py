"""Fast, data-independent tests for the 50-sentence diagnostic labels."""
import unittest

from scripts.diagnose_novel_parses import classify, compact_stats, tally, lexical_diagnostics


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

    def test_failed_sentence_lexical_categories_and_origins(self):
        from seman_parser.features import FeatureStructure
        from seman_parser.segmentation import (
            LexicalCandidate, LexicalInterpretation, LexicalLattice, tokenize,
        )
        item = LexicalCandidate(
            span_start=0, span_end=3, surface="Run", lemma="run",
            category="V", source="wordnet",
            features=FeatureStructure.build({"subcat": "intransitive", "vform": "base"}),
            interpretations=(LexicalInterpretation(
                sense_id="run.v.01", lemma="run", score=1.0,
                provenance={"source": "wordnet"},
            ),),
        )
        lattice = LexicalLattice(
            text="Run now.", tokens=tokenize("Run now."), candidates=(item,),
        )
        result = lexical_diagnostics(lattice)
        self.assertEqual([r["surface"] for r in result["tokens"]], ["Run", "now", "."])
        self.assertEqual(result["tokens"][0]["categories"], ["V"])
        self.assertEqual(result["tokens"][0]["candidates"][0]["sense_ids"], ["run.v.01"])
        self.assertEqual(result["tokens"][0]["candidates"][0]["features"]["subcat"], "intransitive")
        self.assertEqual(result["words_without_any_candidate"], ["now"])
        self.assertFalse(result["tokens"][2]["no_candidate_or_cover"])

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
