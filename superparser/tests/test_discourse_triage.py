"""Discourse-level controls: distinguish non-prose from legitimate minor clauses."""
from __future__ import annotations

import unittest
from research.verbnet_lr.gutenberg_novels import Book, analysis_units, extract
from seman_parser.discourse_roles import classify_discourse
from seman_parser.structural_preanalysis import analyze_paragraph


class DiscourseTriageTests(unittest.TestCase):
    def test_only_upon_us_is_source_linked_not_invented_matrix(self):
        text = ("He pushed me hastily into the open air, and closed the "
                "door upon us. Only upon us two.")
        first, second = analyze_paragraph(text)
        self.assertTrue(first.eligible_for_parse)
        self.assertFalse(second.eligible_for_parse)
        self.assertEqual(second.discourse_function, "elliptical_supplement")
        self.assertEqual(second.discourse_relation, "anaphoric_afterthought")
        self.assertEqual(second.structural_status, "requires_source_context")
        self.assertEqual(next(c for c in second.constituents
                              if c.id == "s0").function,
                         "elliptical_supplement")
        units = list(analysis_units(text))
        self.assertEqual(len(units), 2)
        self.assertEqual(units[1].discourse_governor_core_span,
                         (units[0].core_start, units[0].core_end))
        self.assertEqual(
            text[slice(*units[1].discourse_governor_core_span)],
            first.text,
        )
        rows, stats = extract(Book(999, "Mock", "No", "train"), text,
                              length_min=1)
        self.assertEqual([x["source_text"] for x in rows], [first.text])
        self.assertEqual(stats["contextual_discourse_supplements"], 1)

    def test_contextual_afterthought_must_have_real_prior_governor(self):
        source = "Only upon us two."
        unit, = analyze_paragraph(source)
        self.assertEqual(unit.discourse_function, "clausal_utterance_candidate")
        self.assertTrue(unit.eligible_for_parse)
        self.assertIsNone(unit.discourse_governor_core_span)

    def test_quote_dash_mid_predicate_requires_source_governor(self):
        paragraph = (
            "‘--was induced and persuaded by me,’ I went on, swallowing "
            "that colder designation, ‘to consent to this concealment, "
            "and I bitterly regret it.’"
        )
        unit, = analyze_paragraph(paragraph)
        self.assertEqual(unit.quotation_status, "balanced")
        self.assertFalse(unit.eligible_for_parse)
        self.assertEqual(unit.discourse_function, "reported_speech_continuation")
        self.assertEqual(unit.structural_status, "requires_source_context")
        self.assertEqual(unit.text, paragraph)
        self.assertFalse(unit.synthetic_prefix)
        previous = "I told my aunt what had happened.\n\n" + paragraph
        units = list(analysis_units(previous))
        self.assertEqual(len(units), 2)
        self.assertEqual(units[1].discourse_governor_paragraph_index, 0)
        self.assertEqual(units[1].discourse_governor_core_span,
                         (units[0].core_start, units[0].core_end))

    def test_map_bearings_not_misrepresented_as_main_clause(self):
        bearing = "Tall tree, Spy-glass shoulder, bearing a point to the N. of N.N.E."
        units = analyze_paragraph(bearing)
        self.assertEqual(len(units), 1)
        unit = units[0]
        self.assertEqual(unit.discourse_function,
                         "documentary_navigation_notation")
        self.assertEqual(unit.structural_status, "nonprose_documentary")
        self.assertFalse(unit.eligible_for_parse)
        matrix = next(c for c in unit.constituents if c.id == "s0")
        self.assertEqual(matrix.function, "documentary_navigation_notation")
        self.assertEqual(bearing[matrix.start:matrix.end], bearing)
        nodes = {n.id: n for n in unit.constituents}
        self.assertEqual(nodes["d0"].function, "document_nominal_reference")
        self.assertEqual(nodes["d1"].function, "directional_participial_supplement")
        self.assertEqual(nodes["d1"].governor, "d0")
        self.assertEqual(bearing[nodes["d1"].start:nodes["d1"].end],
                         "bearing a point to the N. of N.N.E.")
        rows, counts = extract(Book(999, "Mock", "No", "train"), bearing,
                               length_min=1)
        self.assertEqual(rows, [])
        self.assertEqual(counts["nonprose_documentary"], 1)
        self.assertEqual(counts["requires_source_context"], 0)

    def test_postscript_marker_is_paratext_not_ungrammatical_prose(self):
        source = "P.P.S.--Hawkins may stay one night with his mother."
        unit, = analyze_paragraph(source)
        self.assertEqual(unit.discourse_function, "documentary_postscript")
        self.assertEqual(unit.structural_status, "nonprose_documentary")
        self.assertFalse(unit.eligible_for_parse)
        nodes = {n.id: n for n in unit.constituents}
        self.assertEqual(nodes["d0"].function, "document_marker")
        self.assertEqual(nodes["d1"].function, "document_content_clause_candidate")
        self.assertEqual(nodes["d1"].governor, "d0")
        self.assertEqual(source[nodes["d1"].start:nodes["d1"].end],
                         "Hawkins may stay one night with his mother.")

    def test_minor_sentences_are_valid_utterances_not_broken_clauses(self):
        examples = (
            ("‘Perfectly, sir.’", "dialogue_response"),
            ("Good night, my sister.", "social_formula"),
            ("“Indeed!”", "dialogue_response"),
        )
        for text, relation in examples:
            with self.subTest(text=text):
                unit, = analyze_paragraph(text)
                self.assertTrue(unit.eligible_for_parse)
                self.assertEqual(unit.discourse_function, "minor_utterance")
                self.assertEqual(unit.discourse_relation, relation)
                self.assertEqual(unit.structural_status,
                                 "provisional_complete_utterance")
                s0 = next(c for c in unit.constituents if c.id == "s0")
                self.assertEqual(s0.function, "minor_utterance")

    def test_no_overclassification_of_major_clauses_and_dialect(self):
        sentences = (
            "These biscuits, should anything befall me, would keep me from starving.",
            "Only Mary would know what I had seen.",
            "We went to the harbour and waited.",
            "The compass pointed to the N. of the bay.",
            "He said, ‘--was it the last thing we heard?’",
            "Thinkin' o' Flint--I think it were--as done me.",
            "He stopped suddenly. But he returned.",
        )
        for text in sentences:
            with self.subTest(text=text):
                units = analyze_paragraph(text)
                self.assertTrue(all(x.eligible_for_parse for x in units))
                self.assertTrue(all(x.discourse_function ==
                                    "clausal_utterance_candidate" for x in units))

    def test_quotation_context_not_conflated_with_text_integrity(self):
        text = "‘He went before us."
        unit, = analyze_paragraph(text)
        self.assertFalse(unit.eligible_for_parse)
        self.assertEqual(unit.quotation_status, "unresolved_source_quotation")
        self.assertEqual(unit.discourse_function, "clausal_utterance_candidate")
        self.assertEqual(unit.text, text)


if __name__ == "__main__":
    unittest.main()
