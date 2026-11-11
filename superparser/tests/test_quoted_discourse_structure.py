"""Dialogue compositional preanalysis with exact source and explicit governors.

These witness texts are drawn from current failed novel constructions; no
grammar rule is added to make a truncated quotation count as a finite clause.
"""
from __future__ import annotations

import unittest

from research.verbnet_lr.gutenberg_novels import Book, extract
from research.verbnet_lr.corpus_pipeline import prepare_corpus_input
from seman_parser.structural_preanalysis import analyze_paragraph


def by_id(unit):
    return {p.id: p for p in unit.constituents}


class QuotedDiscourseStructureTests(unittest.TestCase):
    def test_reporting_intercalation_links_both_halves_to_one_tag(self):
        source = (
            '“I am afraid, Mr. Darcy,” observed Miss Bingley in a half whisper, '
            '“that this adventure has rather affected your admiration of her fine eyes.”'
        )
        unit, = analyze_paragraph(source)
        self.assertTrue(unit.eligible_for_parse)
        parts = by_id(unit)
        self.assertEqual(len(parts), len(unit.constituents))
        self.assertEqual(parts["t0"].function, "split_direct_speech_turn")
        self.assertEqual(parts["r0"].function, "reporting_clause")
        self.assertEqual(parts["r0"].governor, "t0")
        self.assertEqual(
            source[parts["r0"].start:parts["r0"].end],
            "observed Miss Bingley in a half whisper",
        )
        self.assertEqual(parts["q0"].governor, "r0")
        self.assertEqual(parts["q1"].governor, "q0")
        self.assertEqual(parts["q0"].relation, "reported_content")
        self.assertEqual(parts["q1"].relation, "resumption_of_split_speech")
        self.assertEqual(
            source[parts["q1"].start:parts["q1"].end],
            '“that this adventure has rather affected your admiration of her fine eyes.”',
        )
        self.assertEqual(parts["qc1_0"].governor, "q1")
        self.assertEqual(source[parts["qc1_0"].start:parts["qc1_0"].end],
                         "that this adventure has rather affected your admiration of her fine eyes.")

    def test_quoted_aside_is_narratorial_not_speech(self):
        source = (
            "‘Now, David,’ he said--and I saw that cast again as he said it--"
            "‘you must be far more careful today than usual.’"
        )
        unit, = analyze_paragraph(source)
        parts = by_id(unit)
        self.assertEqual(parts["r0"].function, "reporting_clause")
        self.assertEqual(source[parts["r0"].start:parts["r0"].end], "he said")
        self.assertEqual(parts["q0"].governor, "r0")
        self.assertEqual(parts["q1"].governor, "q0")
        aside = next(c for c in parts.values()
                     if c.function == "narratorial_parenthetical")
        self.assertEqual(aside.governor, "t0")
        self.assertEqual(source[aside.start:aside.end],
                         "and I saw that cast again as he said it")
        self.assertNotIn("and I saw", source[parts["r0"].start:parts["r0"].end])

    def test_multiple_spoken_sentences_have_separate_source_clause_nodes(self):
        source = (
            '“My dear, do not give way to such gloomy thoughts. '
            'Let us hope for better things. '
            'Let us flatter ourselves that I may be the survivor.”'
        )
        unit, = analyze_paragraph(source)
        parts = by_id(unit)
        self.assertEqual([x.id for x in unit.constituents
                          if x.function == "spoken_clause_candidate"],
                         ["qc0_0", "qc0_1", "qc0_2"])
        phrases = [
            source[parts[f"qc0_{i}"].start:parts[f"qc0_{i}"].end]
            for i in range(3)
        ]
        self.assertEqual(phrases, [
            "My dear, do not give way to such gloomy thoughts.",
            "Let us hope for better things.",
            "Let us flatter ourselves that I may be the survivor.",
        ])
        self.assertTrue(all(parts[f"qc0_{i}"].governor == "q0"
                            for i in range(3)))
        self.assertEqual(unit.text, source)
        self.assertFalse(unit.synthetic_prefix)
        self.assertFalse(unit.synthetic_suffix)

    def test_nested_quotation_is_not_a_new_direct_speech_turn(self):
        source = "‘“When you see this, I shall be far away.”’"
        unit, = analyze_paragraph(source)
        parts = by_id(unit)
        self.assertEqual(parts["q0"].function, "direct_speech")
        self.assertEqual(parts["q1"].function, "embedded_quotation")
        self.assertEqual(parts["q1"].governor, "q0")
        self.assertNotIn("t0", parts)
        self.assertTrue(unit.eligible_for_parse)

    def test_postposed_and_preposed_reporters_are_distinguished(self):
        for source, expected in (
            ('“You will find I do my duty,” said Mary.',
             "postposed_reporting_clause"),
            ('Mary said, “You will find I do my duty.”',
             "preposed_reporting_clause"),
        ):
            with self.subTest(source=source):
                unit, = analyze_paragraph(source)
                parts = by_id(unit)
                self.assertEqual(parts["r0"].evidence, expected)
                self.assertEqual(parts["q0"].governor, "r0")
                self.assertEqual(parts["q0"].relation, "reported_content")
                self.assertEqual(source[parts["r0"].start:parts["r0"].end].strip(","),
                                 "said Mary" if expected.startswith("post") else "Mary said")

    def test_neighbouring_independent_dialogues_remain_distinct(self):
        text = '“Hello!” she cried. “Come back,” he said.'
        units = analyze_paragraph(text)
        self.assertEqual(len(units), 2)
        for unit in units:
            parts = by_id(unit)
            self.assertIn("q0", parts)
            self.assertIn("r0", parts)
            self.assertNotIn("q1", parts)
            self.assertNotIn("t0", parts)
            self.assertTrue(unit.eligible_for_parse)

    def test_abbreviated_vocative_is_not_sentence_boundary(self):
        unit, = analyze_paragraph('“Good evening, Mr. Darcy. I am here.”')
        parts = by_id(unit)
        self.assertEqual(
            [unit.text[p.start:p.end] for p in unit.constituents
             if p.function == "spoken_clause_candidate"],
            ["Good evening, Mr. Darcy.", "I am here."],
        )

    def test_book_corpus_keeps_exact_text_and_parse_gateway_component_links(self):
        text = (
            '“I am afraid,” said Mary, “I will leave now.”\n\n'
            '“I cannot.”'
        )
        cases, counts = extract(
            Book(999, "Evidence", "Evidence", "train"),
            text, length_min=1, length_max=80,
        )
        self.assertEqual(counts["eligible"], 2)
        first = cases[0]
        prepared = prepare_corpus_input(first)
        self.assertEqual(prepared.source_text, first["source_text"])
        self.assertEqual(prepared.analysis_text, first["source_text"])
        parts = {p["id"]: p for p in prepared.structural_constituents}
        self.assertEqual(prepared.source_component("r0"), "said Mary")
        self.assertEqual(prepared.source_component("qc1_0"), "I will leave now.")
        self.assertTrue(all(p["governor"] is None or p["governor"] in parts
                            for p in prepared.structural_constituents))


if __name__ == "__main__":
    unittest.main()
