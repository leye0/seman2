"""Evidence-gated dialogue composition through the one public Parser.parse.

A quoted speech sequence can be counted complete only if each source clause
has its own accepted finite subject-predicate tree AND the source-delimiter
assembly grammar produces a full-span root. A provisional source annotation
by itself never provides a successful grammatical analysis.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts.diagnose_novel_parses import select_cases
from seman_parser.dialogue_clause_plans import PARENTHETICAL_MODAL
from seman_parser.engine import Parser
from seman_parser.structural_preanalysis import analyze_paragraph

DATA = Path(__file__).resolve().parents[1] / "data"


class QuotedStructuralCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def _parse_case(self, source: str):
        rows, _ = extract(
            Book(999, "Grammar", "Test", "train"),
            source, length_min=1, length_max=120,
        )
        self.assertEqual(len(rows), 1, source)
        return parse_corpus_case(
            self.parser, rows[0], max_items=50_000,
            kbest_work_limit=500_000,
        )

    def test_two_full_quoted_clauses_are_really_parsed_and_assembled(self):
        source = '"John walks. Mary walks."'
        prepared, lattice, result = self._parse_case(source)
        self.assertEqual(prepared.analysis_text, source)
        self.assertEqual(result.text, source)
        self.assertEqual(lattice.text, source)
        self.assertTrue(result.completed, result.stats)
        self.assertTrue(result.stats.get("structural_composition"), result.stats)
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_two_finite_clauses")
        self.assertEqual(prepared.source_component("qc0_0"), "John walks.")
        self.assertEqual(prepared.source_component("qc0_1"), "Mary walks.")
        self.assertEqual(result.stats["structural_segment_count"], 2)
        self.assertEqual(result.stats["structural_segment_rule_ids"],
                         ["clause_np_vp", "clause_np_vp"])
        self.assertEqual(
            [source[a:b] for a, b in result.stats["structural_segment_spans"]],
            ["John walks", "Mary walks"],
        )
        self.assertEqual(
            [source[a:b] for a, b in result.stats["source_punctuation_spans"]],
            [".", "."],
        )
        root = result.best()
        self.assertEqual(root.category, "CLAUSE")
        self.assertEqual(root.start, 0)
        self.assertEqual(root.end, len(source))
        self.assertEqual(len(root.children), 6)
        self.assertEqual(
            [child.category for child in root.children],
            ["OPEN-QUOTE", "CLAUSE", "SPEECH-STOP",
             "CLAUSE", "SPEECH-STOP", "CLOSE-QUOTE"],
        )
        for child in (root.children[1], root.children[3]):
            self.assertEqual(child.rule_id, "segment_interface")
            self.assertEqual(child.children[0].rule_id, "clause_np_vp")

    def test_three_full_quoted_clauses_use_three_proven_interfaces(self):
        source = '"John walks. Mary walks. Jane walks."'
        prepared, _, result = self._parse_case(source)
        self.assertTrue(result.completed, result.stats)
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_three_finite_clauses")
        self.assertEqual(result.stats["structural_segment_count"], 3)
        self.assertEqual(len(result.best().children), 8)
        self.assertEqual(prepared.source_component("qc0_2"), "Jane walks.")

    def test_composed_dialogue_preserves_reported_content_and_speech_links(self):
        source = '"John walks," said Mary, "Jane walks."'
        rows, _ = extract(
            Book(999, "Grammar", "Test", "train"),
            source, length_min=1, length_max=120,
        )
        self.assertEqual(len(rows), 1)
        report = self.parser.parse(
            source,
            structural_constituents=rows[0]["structural_constituents"],
            max_items=50_000,
            kbest_work_limit=500_000,
        )
        self.assertTrue(report.result.completed, report.result.stats)
        self.assertEqual(report.result.best().rule_id,
                         "dialogue_structural_intercalated_two_finite_clauses")
        relations = [r.as_dict()["relation"]
                     for r in report.interpret().graph.relations]
        self.assertIn("AGENT", relations)
        self.assertIn("REPORTED_CONTENT", relations)
        self.assertIn("CONTINUED_SPEECH", relations)

    def test_no_composition_when_one_part_is_not_a_finite_clause(self):
        source = '"John walks. Very quickly."'
        prepared, _, result = self._parse_case(source)
        self.assertTrue(prepared.structural_constituents)
        self.assertFalse(result.stats.get("structural_composition", False),
                         "A sentence fragment may not be promoted to a finite clause")
        self.assertEqual(result.text, source)

    def test_split_dialogue_composes_real_clauses_and_reporting_tag(self):
        source = '"John walks," said Mary, "Jane walks."'
        prepared, _, result = self._parse_case(source)
        self.assertTrue(result.completed, result.stats)
        self.assertTrue(result.stats.get("structural_composition"), result.stats)
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_intercalated_two_finite_clauses")
        self.assertEqual(result.text, source)
        self.assertEqual(result.stats["structural_composition_kind"],
                         "intercalated_reporting_clause")
        self.assertEqual(result.stats["structural_clause_count"], 2)
        self.assertEqual(prepared.source_component("r0"), "said Mary")
        self.assertEqual(
            [source[a:b] for a, b in result.stats["structural_segment_spans"]],
            ["John walks", "said Mary", "Jane walks"],
        )
        self.assertEqual(len(result.best().children), 10)
        self.assertEqual(
            [node.category for node in result.best().children],
            ["OPEN-QUOTE", "CLAUSE", "COMMA", "CLOSE-QUOTE",
             "SPEECH-TAG", "COMMA", "OPEN-QUOTE",
             "CLAUSE", "SPEECH-STOP", "CLOSE-QUOTE"],
        )
        self.assertEqual(
            [node.rule_id for node in result.best().children
             if node.category in ("CLAUSE", "SPEECH-TAG")],
            ["segment_interface"] * 3,
        )
        self.assertTrue(result.stats["structural_segment_rule_ids"][2]
                        .startswith("dialogue_speech_tag_"))

    def test_split_subject_and_predicate_cannot_fake_two_finite_clauses(self):
        source = '"John," said Mary, "walks."'
        _, _, result = self._parse_case(source)
        self.assertFalse(result.stats.get("structural_composition", False))
        self.assertEqual(result.text, source)

    def test_unattributed_adjacent_quotes_are_two_independent_utterances(self):
        source = '"John walks." "Mary walks."'
        units = analyze_paragraph(source)
        self.assertEqual([u.text for u in units],
                         ['"John walks."', '"Mary walks."'])
        self.assertTrue(all(u.eligible_for_parse for u in units))
        self.assertTrue(all(
            not any(p.function == "split_direct_speech_turn"
                    for p in u.constituents)
            for u in units
        ))

    def test_attested_minor_dialogue_answer_is_composed_without_a_verb(self):
        source = '‘Perfectly, sir.’'
        prepared, _, result = self._parse_case(source)
        self.assertTrue(result.completed, result.stats)
        self.assertTrue(result.stats.get("structural_composition"), result.stats)
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_minor_adv_vocative")
        self.assertEqual(result.best().features.as_dict()["minor_utterance"],
                         "true")
        self.assertEqual(result.stats["structural_clause_count"], 0)
        self.assertEqual(result.stats["structural_composition_kind"],
                         "adverbial_answer_with_vocative")
        self.assertEqual(
            [source[a:b] for a, b in result.stats["structural_segment_spans"]],
            ["Perfectly", "sir"],
        )
        self.assertEqual(
            [node.category for node in result.best().children],
            ["OPEN-QUOTE", "ADV", "COMMA", "NP", "SPEECH-STOP", "CLOSE-QUOTE"],
        )
        self.assertEqual(prepared.source_text, source)
        self.assertEqual(result.text, source)
        self.assertTrue(all(
            n.category not in ("V", "VP", "COPULA")
            for n in result.best().children
        ), "Verbless minor utterance must not fabricate a predicate")

    def test_minor_dialogue_must_be_classified_and_parse_both_components(self):
        for source in ('‘Perfectly, very.’', '‘Slowly, perhaps.’'):
            with self.subTest(source=source):
                prepared, _, result = self._parse_case(source)
                self.assertFalse(result.stats.get("structural_composition", False))
                self.assertEqual(prepared.source_text, source)

    def test_direct_parse_without_source_graph_retains_original_route(self):
        source = '"John walks. Mary walks."'
        raw = self.parser.parse(
            source, max_items=50_000, kbest_work_limit=500_000,
        )
        self.assertFalse(raw.result.stats.get("structural_composition", False))
        self.assertEqual(raw.result.text, source)

    def test_broken_quote_is_never_synthetically_closed_to_force_success(self):
        source = '"John walks. Mary walks.'
        unit, = analyze_paragraph(source)
        self.assertFalse(unit.eligible_for_parse)
        rows, counts = extract(
            Book(999, "Grammar", "Test", "train"),
            source, length_min=1, length_max=120,
        )
        self.assertEqual(rows, [])
        self.assertEqual(counts["requires_source_context"], 1)


class SourceParentheticalModalTests(unittest.TestCase):
    CONTROL = (
        "We could stay in the room (she knew with a smile) "
        "and watch the door when we met them at dawn."
    )

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(
            Path(__file__).resolve().parents[1] / "data", cache_size=0,
        )

    def parse(self, case):
        return parse_corpus_case(self.parser, case, max_items=50_000,
                                 kbest_work_limit=500_000)

    def control(self, text):
        rows, _ = extract(Book(999, "Synthetic", "Test", "train"), text,
                          length_min=1, length_max=100)
        self.assertEqual([row["source_text"] for row in rows], [text])
        return self.parse(rows[0])[2]

    def spans(self, nodes, text):
        return [(n.category, text[n.start:n.end]) for n in nodes]

    def test_case_493_preserves_shared_modal_and_nested_attachment(self):
        case = select_cases(500)[0][493]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "f02fcc4a918d02fc")
        prepared, lattice, result = self.parse(case)
        self.assertEqual(prepared.analysis_text, text)
        self.assertEqual(lattice.text, text)
        self.assertTrue(result.completed, result.stats)
        best = result.best()
        self.assertEqual(best.rule_id, PARENTHETICAL_MODAL)
        self.assertEqual((best.start, best.end), (0, len(text)))
        self.assertEqual(self.spans(best.children, text), [
            ("NP", "I"), ("MODAL", "should"), ("VP-NP", "lie down in my own place"),
            ("PARENTHETICAL", "(I thought with a silent chuckle)"), ("COORD", "and"),
            ("VP-NP", "enjoy their faces when they found me in the morning"),
            ("SPEECH-STOP", "."),
        ])
        _, _, first, aside, _, second, _ = best.children
        self.assertEqual(first.children[0].rule_id, "vpnp_bare_prepositional_pp")
        self.assertEqual(self.spans(aside.children, text), [
            ("OPEN-PAREN", "("), ("NP", "I"), ("V", "thought"),
            ("PP", "with a silent chuckle"), ("CLOSE-PAREN", ")"),
        ])
        self.assertEqual(prepared.source_component(f"p{aside.start}"),
                         "(I thought with a silent chuckle)")
        action, temporal = second.children
        self.assertEqual(action.children[0].rule_id, "vp_bare_trans")
        self.assertEqual(self.spans(temporal.children, text), [
            ("CONJ", "when"), ("CLAUSE", "they found me"), ("PP", "in the morning"),
        ])
        self.assertEqual(temporal.children[1].children[0].children[1].rule_id,
                         "vp_transitive")
        self.assertFalse(result.stats.get("budget_exceeded"))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))

    def test_independent_parenthetical_with_optional_temporal_pp(self):
        for text in (self.CONTROL, self.CONTROL.replace(" at dawn", "")):
            with self.subTest(text=text):
                result = self.control(text)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, PARENTHETICAL_MODAL)
                self.assertEqual(result.best().children[3].category, "PARENTHETICAL")
                self.assertEqual(result.best().children[5].rule_id,
                                 "structural_source_bare_predicate_with_when")

    def test_does_not_admit_nonclausal_incise_or_finite_second_predicate(self):
        for old, new in (("she knew", "she laughed"), ("and watch", "and watches"),
                         ("(she knew with a smile)", "with a smile")):
            with self.subTest(new=new):
                result = self.control(self.CONTROL.replace(old, new))
                self.assertNotEqual(result.stats.get("structural_composition_kind"),
                                    PARENTHETICAL_MODAL)

    def test_preanalysis_records_parentheses_not_quoted_or_unmatched_marks(self):
        source = 'He stayed (she knew) and waited. He said "I stayed (she knew)."'
        first, quoted = analyze_paragraph(source)
        candidates = [c for c in first.constituents if c.function == "parenthetical_candidate"]
        self.assertEqual([(first.text[c.start:c.end], c.governor) for c in candidates],
                         [("(she knew)", "s0")])
        self.assertFalse(any(c.function == "parenthetical_candidate" for c in quoted.constituents))
        for sentence in analyze_paragraph("He stayed (she knew and waited."):
            self.assertFalse(any(c.function == "parenthetical_candidate"
                                 for c in sentence.constituents))


if __name__ == "__main__":
    unittest.main()
