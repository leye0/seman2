"""Fast, data-independent tests for the 500-sentence diagnostic corpus."""
import unittest

from scripts.diagnose_novel_parses import (
    classify, compact_stats, tally, lexical_diagnostics, recurring_issues,
    select_cases, word_category_sequence, contrast_category_patterns,
)


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

    def test_pattern_contrasts_use_both_successes_and_failures(self):
        rows = []
        for number in range(5):
            rows.append({
                "case_id": f"bad:{number}", "status": "no_structural_root",
                "lexical_category_sequence": ["N", "PREP", "N"],
            })
        for number in range(4):
            rows.append({
                "case_id": f"good:{number}", "status": "complete",
                "lexical_category_sequence": ["N", "V", "N"],
            })
        rows.append({
            "case_id": "timeout:0", "status": "timeout",
            "lexical_category_sequence": ["N", "PREP", "N"],
        })
        result = contrast_category_patterns(rows, min_support=5)
        self.assertEqual(result["counts"], {
            "usable": 9, "grammatical_failures": 5,
            "completed": 4, "excluded_inconclusive": 1,
        })
        first = next(
            x for x in result["patterns"]
            if x["gram_length"] == 2 and x["pattern"] == "N + PREP"
        )
        self.assertEqual(first["failed_sentence_count"], 5)
        self.assertEqual(first["successful_sentence_count"], 0)
        self.assertGreater(first["enrichment_ratio"], 1)

    def test_possessive_tokens_are_covered_by_two_lexical_edges(self):
        from seman_parser.features import FeatureStructure
        from seman_parser.segmentation import (
            LexicalCandidate, LexicalLattice, tokenize,
        )
        sentence = "John's house."
        def edge(left, right, category):
            return LexicalCandidate(
                span_start=left, span_end=right,
                surface=sentence[left:right], lemma=sentence[left:right],
                category=category, features=FeatureStructure.empty(),
            )
        lattice = LexicalLattice(
            text=sentence, tokens=tokenize(sentence),
            candidates=(
                edge(0, 4, "PROPER-NOUN"), edge(4, 6, "POSS"),
                edge(7, 12, "N"),
            ),
        )
        lexical = lexical_diagnostics(lattice)
        token = lexical["tokens"][0]
        self.assertTrue(token["no_exact_candidate"])
        self.assertTrue(token["has_split_candidate_path"])
        self.assertFalse(token["no_candidate_or_cover"])
        self.assertEqual(token["split_candidate_count"], 2)
        self.assertEqual(lexical["words_without_any_candidate"], [])
        self.assertEqual(
            word_category_sequence(lattice)[0], "SPLIT_LEXICAL_CANDIDATES"
        )

    def test_recurring_patterns_count_distinct_failed_sentences(self):
        lex = lambda surface: {
            "tokens": [
                {"surface": surface, "is_word": True, "categories": [],
                 "no_candidate_or_cover": True, "no_exact_candidate": True},
                {"surface": surface, "is_word": True, "categories": [],
                 "no_candidate_or_cover": True, "no_exact_candidate": True},
            ]
        }
        rows = [
            {"case_id": f"test:{i}", "status": "no_structural_root",
             "lexical_diagnostic": lex("Missing")}
            for i in range(4)
        ]
        rows.append({
            "case_id": "test:ok", "status": "complete",
            "lexical_diagnostic": lex("Missing"),
        })
        report = recurring_issues(rows, minimum_cases=3)
        self.assertEqual(report["denominator"]["sampled"], 5)
        self.assertEqual(report["denominator"]["failed"], 4)
        self.assertEqual(report["word_without_candidate"][0]["pattern"], "missing")
        self.assertEqual(
            report["word_without_candidate"][0]["failed_sentence_count"], 4
        )
        self.assertEqual(
            report["category_bigram"][0]["failed_sentence_count"], 4
        )
        self.assertEqual(len(report["word_without_candidate"][0]["example_case_ids"]), 3)

    def test_select_exactly_500_from_stratified_pool(self):
        from unittest.mock import patch
        pool = [{"book_id": i // 128, "band": str((i % 128) // 32),
                 "text": f"Case {i}", "tokens": 8} for i in range(512)]
        with patch("scripts.diagnose_novel_parses.choose_cases",
                   return_value=(pool, [])) as choose:
            cases, sources = select_cases(500)
        self.assertEqual(choose.call_args.args, (32,))
        self.assertEqual(len(cases), 500)
        self.assertEqual(len(set(row["text"] for row in cases)), 500)
        self.assertEqual(sources, [])

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
