"""One public parse, one lexical lattice, opt-in preflight with verified tree links."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser, ParserResources


DATA = Path(__file__).resolve().parents[1] / "data"


class IntegratedFastPreflightTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(DATA), cache_size=8)

    def test_option_does_not_change_default_cache_or_selected_tree(self):
        text = "John opened the box."
        canonical = self.parser.parse(text)
        self.assertNotIn("fast_preflight", canonical.result.stats)
        with patch.object(
            self.parser, "_lattice_for_text",
            wraps=self.parser._lattice_for_text,
        ) as prepare:
            observed = self.parser.parse(text, preflight_diagnostics=True)
        prepare.assert_called_once_with(text)
        self.assertIs(observed.lattice, canonical.lattice)
        self.assertEqual(observed.result.completed, canonical.result.completed)
        self.assertEqual(
            observed.result.best().as_dict(), canonical.result.best().as_dict())
        probe = observed.result.stats["fast_preflight"]
        self.assertEqual(probe["phase"], "existing_lattice")
        self.assertTrue(probe["lexical_lattice_reused"])
        self.assertTrue(probe["first_observed_before_syntax"])
        self.assertTrue(probe["selected_tree_checked"])
        self.assertEqual(probe["selected_tree_proven_marked_relations"], [])
        self.assertFalse(probe["grammatical_fault_established"])
        self.assertFalse(probe["can_skip_full_parse"])
        self.assertGreaterEqual(probe["existing_lattice_probe_us"], 0.0)
        self.assertGreaterEqual(probe["selected_tree_evidence_us"], 0.0)
        # Enabled debug requests must not mutate the cached baseline.
        later = self.parser.parse(text)
        self.assertNotIn("fast_preflight", later.result.stats)

    def test_incomplete_clause_has_only_hypotheses_never_links(self):
        text = '"They says."'
        observed = self.parser.parse(text, preflight_diagnostics=True)
        probe = observed.result.stats["fast_preflight"]
        if not observed.result.completed:
            self.assertFalse(probe["selected_tree_checked"])
        self.assertEqual(probe["selected_tree_proven_marked_relation_count"], 0)
        self.assertFalse(probe["grammatical_fault_established"])

    def test_quote_scoped_incomplete_reuses_original_lattice(self):
        text = '"The strange winds was blowing," she said.'
        with patch.object(
            self.parser, "_lattice_for_text",
            wraps=self.parser._lattice_for_text,
        ) as lattice_for_text:
            observed = self.parser.parse(
                text, max_items=50000,
                kbest_work_limit=500000,
                preflight_diagnostics=True,
            )
        lattice_for_text.assert_called_once_with(text)
        self.assertEqual(observed.lattice.text, text)
        self.assertIn("fast_preflight", observed.result.stats)

    def test_pinned_marked_463_has_selected_tree_licensed_subject_relation(self):
        case = select_cases(500)[0][463]
        prepared, original_lattice, strict = parse_corpus_case(
            self.parser, case,
            max_items=50000, kbest_work_limit=500000,
            preflight_diagnostics=True,
        )
        assert not strict.completed
        strict_probe = strict.stats["fast_preflight"]
        self.assertFalse(strict_probe["selected_tree_checked"])
        self.assertEqual(strict_probe["selected_tree_proven_marked_relations"], [])
        self.assertFalse(strict_probe["grammatical_fault_established"])
        prepared, marked_lattice, marked = parse_corpus_case(
            self.parser, case,
            max_items=50000, kbest_work_limit=500000,
            allow_marked_deviations=True,
            preflight_diagnostics=True,
        )
        self.assertIs(marked_lattice, original_lattice)
        self.assertTrue(marked.completed)
        deviation = marked.usage_deviations()
        self.assertEqual(len(deviation), 1)
        probe = marked.stats["fast_preflight"]
        self.assertEqual(probe["selected_tree_proven_marked_relation_count"], 1)
        proof = probe["selected_tree_proven_marked_relations"][0]
        self.assertEqual(proof["licensing_rule_id"], deviation[0].rule_id)
        self.assertEqual(proof["subject_analysis_span"], list(deviation[0].subject_span))
        self.assertEqual(proof["predicate_analysis_span"], list(deviation[0].predicate_span))
        self.assertEqual(proof["evidence_basis"],
                         "explicit_marked_rule_selected_complete_tree")
        self.assertEqual(proof["scope"], "selected_tree_only_not_sentence_error")
        self.assertFalse(probe["grammatical_fault_established"])


if __name__ == "__main__":
    import unittest
    unittest.main()
