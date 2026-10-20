"""Fast, data-independent tests for the 500-sentence diagnostic corpus."""
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import ast

from research.verbnet_lr.corpus_pipeline import (
    CorpusParseMode, prepare_corpus_input, parse_corpus_case,
)

from scripts.diagnose_novel_parses import (
    classify, compact_stats, tally, lexical_diagnostics, recurring_issues,
    select_cases, word_category_sequence, contrast_category_patterns,
    canonical_residual_audit, construction_cluster_audit,
)


class NovelDiagnosticsTests(unittest.TestCase):

    def test_construction_clusters_compare_successes_and_censor_limits(self):
        def case(index, text, status):
            return {
                "index": index, "book_id": 84,
                "sentence": text, "canonical_analysis_text": text,
                "status": status,
            }
        rows = [
            case(0, "The book, to which the child replied, fell.", "no_structural_root"),
            case(1, "The sea, on which the moon shone, was calm.",
                 "roots_without_valid_analysis"),
            case(2, "The house, in which Mary lived, was old.", "complete"),
            case(3, "I am sure you will return.", "roots_without_valid_analysis"),
            case(4, "Are you quite sure that they left?", "complete"),
            case(5, "It is certain that he will go.", "timeout"),
            case(6, "John, however, opened the box.", "no_structural_root"),
            case(7, "John opened the box.", "complete"),
        ]
        report = construction_cluster_audit(rows)
        self.assertEqual(report["cohort_size"], 8)
        groups = {g["construction"]: g for g in report["groups"]}
        relatives = groups["relative_preposition_pied_piping"]
        self.assertEqual(relatives["matched"], 3)
        self.assertEqual(relatives["conclusive_failures"], 2)
        self.assertEqual(relatives["successful"], 1)
        self.assertEqual(relatives["successful_control_indices"], [2])
        self.assertEqual(relatives["conclusive_failure_percent"], 66.67)
        adjectives = groups["copular_adjective_finite_complement"]
        self.assertEqual(adjectives["conclusive_failures"], 1)
        self.assertEqual(adjectives["successful"], 1)
        self.assertEqual(adjectives["inconclusive"], 1)
        self.assertEqual(adjectives["conclusive_failure_percent"], 50.0)
        self.assertEqual(
            groups["parenthetical_between_commas"]["failing_case_indices"],
            [6],
        )
        self.assertEqual(report["total_inconclusive"], 1)
        self.assertEqual(report["total_conclusive_failures"], 4)

    def test_clusters_do_not_conflate_ordinary_pp_or_bare_adjective(self):
        texts = [
            "John spoke to Mary, and his sister listened.",
            "The school to which John walked was closed.",
            "I am certain of this result.",
        ]
        rows = [{
            "index": i, "book_id": 120,
            "sentence": text, "status": "complete",
        } for i, text in enumerate(texts)]
        report = construction_cluster_audit(rows)
        groups = {g["construction"]: g for g in report["groups"]}
        self.assertEqual(groups["relative_preposition_pied_piping"]["matched"], 0)
        self.assertEqual(groups["copular_adjective_finite_complement"]["matched"], 0)
        self.assertEqual(groups["comma_followed_by_coordinator"]["matched"], 1)

    def test_canonical_residual_audit_uses_actual_parser_statuses(self):
        rows = [
            {"case_id":"a","index":0,"book_id":766,"band":"04-08",
             "sentence":"I can go.","source_text":"I can go.","status":"complete"},
            {"case_id":"b","index":1,"book_id":84,"band":"09-16",
             "sentence":"John walked, and Mary ran.",
             "source_text":"John walked, and Mary ran.",
             "status":"roots_without_valid_analysis"},
            {"case_id":"c","index":2,"book_id":120,"band":"09-16",
             "sentence":"The girl who laughed was here.",
             "source_text":"The girl who laughed was here.",
             "status":"no_structural_root"},
        ]
        audit, residuals = canonical_residual_audit(rows)
        self.assertEqual(audit["completed"], 1)
        self.assertEqual(audit["remaining"], 2)
        self.assertEqual(audit["statuses"]["no_structural_root"], 1)
        self.assertEqual(audit["statuses"]["roots_without_valid_analysis"], 1)
        self.assertEqual([r["case_id"] for r in residuals], ["b","c"])
        self.assertIn("coordination_surface", residuals[0]["surface_tags"])
        self.assertIn("relative_or_wh_surface", residuals[1]["surface_tags"])
        self.assertEqual(residuals[0]["canonical_status"],
                         "roots_without_valid_analysis")
        self.assertEqual(audit["coverage_percent"], 33.33)

    def test_default_corpus_entrypoint_transfers_quotes_not_raw(self):
        # The source opens a quotation which continues across a sentence.
        case = {
            "text": "I saw.”", "source_text": "I saw.”",
            "balanced_analysis_text": "“I saw.”",
            "balanced_synthetic_prefix": "“",
            "balanced_synthetic_suffix": "",
            "balanced_synthetic_terminal": False,
        }
        input_ = prepare_corpus_input(case)
        self.assertEqual(input_.analysis_text, "“I saw.”")
        self.assertEqual(input_.source_text, "I saw.”")
        self.assertEqual(input_.synthetic_prefix, "“")
        self.assertEqual(input_.mode, CorpusParseMode.QUOTE_BALANCED)
        self.assertEqual(
            prepare_corpus_input(
                case, mode=CorpusParseMode.HISTORICAL_REFERENCE,
            ).analysis_text,
            "I saw.”",
        )
        parser = MagicMock()
        parser.parse.return_value.lattice.text = "“I saw.”"
        parser.parse.return_value.result.text = "“I saw.”"
        parsed, lattice, result = parse_corpus_case(parser, case)
        self.assertEqual(parsed.analysis_text, "“I saw.”")
        self.assertIs(lattice, parser.parse.return_value.lattice)
        self.assertIs(result, parser.parse.return_value.result)
        parser.parse.assert_called_once_with(
            "“I saw.”", max_items=None, kbest_work_limit=None,
        )

    def test_missing_quote_provenance_fails_closed(self):
        sample = {"text": "I saw.”", "source_text": "I saw.”"}
        for mode in CorpusParseMode:
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, "quote-transfer provenance"):
                    prepare_corpus_input(sample, mode=mode)
        with self.assertRaisesRegex(ValueError, "CorpusParseMode"):
            prepare_corpus_input({
                **sample, "balanced_analysis_text": "“I saw.”",
                "balanced_synthetic_prefix": "“",
                "balanced_synthetic_suffix": "",
                "balanced_synthetic_terminal": False,
            }, mode="historical_reference")

    def test_reference_sample_has_same_source_and_prepared_candidate(self):
        from research.verbnet_lr.gutenberg_novels import Book, extract
        paragraph = "“I came. I saw.”"
        rows, _ = extract(
            Book(999, "Test", "Test", "train"), paragraph,
            length_min=1, length_max=99,
        )
        self.assertEqual([x["text"] for x in rows], ["“I came.", "I saw.”"])
        self.assertEqual(
            [prepare_corpus_input(x).analysis_text for x in rows],
            ["“I came.”", "“I saw.”"],
        )
        self.assertEqual(
            [prepare_corpus_input(
                x, mode=CorpusParseMode.HISTORICAL_REFERENCE,
            ).analysis_text for x in rows],
            ["“I came.", "I saw.”"],
        )
        self.assertEqual(
            [x["source_text"] for x in rows], ["“I came.", "I saw.”"],
        )

    def test_diagnostic_must_not_bypass_corpus_quote_gateway(self):
        """Static architecture guard: a future raw parse fails CI."""
        source = (
            Path(__file__).resolve().parents[1]
            / "scripts" / "diagnose_novel_parses.py"
        ).read_text(encoding="utf8")
        parsed = ast.parse(source)
        called = {
            n.func.id
            for n in ast.walk(parsed)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        self.assertIn("parse_corpus_case", called)
        self.assertIn("prepare_corpus_input", called)
        forbidden = [
            n.func.attr
            for n in ast.walk(parsed)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in {"parse_grammar_lattice", "_parse_dialogue_text"}
        ]
        self.assertEqual(forbidden, [],
            "The 500-case diagnostic must parse through corpus_pipeline only")

    def test_diagnostic_counts_canonical_input_and_has_no_legacy_trial(self):
        source = (Path(__file__).resolve().parents[1]
                  / "scripts" / "diagnose_novel_parses.py").read_text(
                      encoding="utf8")
        tree = ast.parse(source)
        self.assertNotIn("HISTORICAL_REFERENCE", source)
        self.assertNotIn("quote_boundary_trial", source)
        self.assertIn("parse_corpus_case", source)
        self.assertNotIn("parse_grammar_lattice", source)

    def test_real_corpus_and_direct_call_share_coordination_route(self):
        """Measure the actual production route, not a second lattice API."""
        from seman_parser.engine import Parser
        parser = Parser.from_dir(
            Path(__file__).resolve().parents[1] / "data",
            cache_size=0, max_items=20000,
        )
        self.assertFalse(hasattr(parser, "parse_grammar_lattice"))
        text = "John opened the box, but Mary closed the door."
        case = {
            "text": text, "source_text": text,
            "balanced_analysis_text": text,
            "balanced_synthetic_prefix": "",
            "balanced_synthetic_suffix": "",
            "balanced_synthetic_terminal": False,
        }
        direct = parser.parse(
            text, max_items=20000, kbest_work_limit=100000,
        )
        prepared, lattice, result = parse_corpus_case(
            parser, case, max_items=20000, kbest_work_limit=100000,
        )
        self.assertEqual(prepared.analysis_text, text)
        self.assertEqual(lattice.text, direct.lattice.text)
        self.assertEqual(result.completed, direct.result.completed)
        self.assertEqual(result.stats.get("segmented"),
                         direct.result.stats.get("segmented"))
        self.assertEqual(
            result.best().as_dict() if result.best() else None,
            direct.result.best().as_dict() if direct.result.best() else None,
        )

    def test_novel_dialogue_audit_uses_gateway_and_fails_on_errors(self):
        source = (Path(__file__).resolve().parents[1]
                  / "scripts" / "smoke_cleaned_novel_dialogues.py").read_text(
                      encoding="utf8")
        self.assertIn("parse_corpus_case(", source)
        self.assertNotIn("parse_grammar_lattice", source)
        self.assertIn("raise RuntimeError(", source)

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

    def test_nonauxiliary_negative_clitic_is_not_false_lexical_coverage(self):
        from seman_parser.features import FeatureStructure
        from seman_parser.segmentation import (
            LexicalCandidate, LexicalLattice, tokenize,
        )
        def case(word, first_category, first_surface):
            base_end = 2
            candidates = (
                LexicalCandidate(
                    span_start=0, span_end=base_end, surface=first_surface,
                    lemma=first_surface, category=first_category,
                    features=FeatureStructure.empty(),
                    source="contraction-base",
                ),
                LexicalCandidate(
                    span_start=base_end, span_end=len(word),
                    surface="n't", lemma="not", category="NEG",
                    features=FeatureStructure.empty(),
                    source="contraction-clitic",
                ),
            )
            return LexicalLattice(
                text=word, tokens=tokenize(word), candidates=candidates,
            )
        bogus = case("ain't", "N", "ai")
        missing = lexical_diagnostics(bogus)
        self.assertFalse(missing["tokens"][0]["has_split_candidate_path"])
        self.assertEqual(missing["words_without_any_candidate"], ["ain't"])
        self.assertEqual(
            word_category_sequence(bogus)[0], "NO_EXACT_LEXICAL_CANDIDATE"
        )
        genuine = case("don't", "AUX", "do")
        real = lexical_diagnostics(genuine)
        self.assertTrue(real["tokens"][0]["has_split_candidate_path"])
        self.assertFalse(real["tokens"][0]["no_candidate_or_cover"])
        self.assertEqual(
            word_category_sequence(genuine)[0], "SPLIT_LEXICAL_CANDIDATES"
        )
        mismatched = case("don't", "AUX", "du")
        self.assertFalse(
            lexical_diagnostics(mismatched)["tokens"][0]["has_split_candidate_path"]
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
