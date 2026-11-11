"""Source spans and descriptive grammatical functions are checked before parsing."""
from __future__ import annotations

import unittest
from research.verbnet_lr.corpus_pipeline import prepare_corpus_input
from research.verbnet_lr.gutenberg_novels import Book, analysis_units, extract
from seman_parser.structural_preanalysis import analyze_paragraph, quote_scan


class ParagraphPreanalysisTests(unittest.TestCase):
    def test_complete_quoted_utterance_not_broken_into_orphans(self):
        for source in (
            '“I came. I saw.”',
            '‘I don’t know. I really don’t.’',
            '"Have you heard the story? Then listen carefully."',
            '‘Now I wonder,’ he muttered, ‘whether my Agnes tires of me. I should ask her.’',
            '‘Says Em’ly, “Martha, is it you? Oh, Martha, can it be you?”'
            '--for they had sat at work together, many a day, at Mr. Omer’s.’',
        ):
            with self.subTest(source=source):
                units = analyze_paragraph(source)
                self.assertEqual([u.source_text for u in units], [source])
                self.assertTrue(units[0].eligible_for_parse)
                self.assertEqual(units[0].quotation_status, "balanced")
                self.assertTrue(all(c.start < c.end for c in units[0].constituents))

    def test_independent_quoted_reporting_utterances_remain_separate(self):
        source = '“Hello!” she cried. “Come back,” he said.'
        units = analyze_paragraph(source)
        self.assertEqual([u.text for u in units],
                         ['“Hello!” she cried.', '“Come back,” he said.'])
        self.assertTrue(all(u.eligible_for_parse for u in units))
        self.assertEqual(" ".join(u.text for u in units), source)

    def test_semicolon_keeps_entire_utterance_and_exposes_dependent_parts(self):
        source = (
            "In her placid sisterly manner; with her beaming eyes; "
            "with her tender voice; she won me from my weakness."
        )
        units = analyze_paragraph(source)
        self.assertEqual(len(units), 1)
        unit = units[0]
        self.assertEqual(unit.source_text, source)
        nodes = {n.id: n for n in unit.constituents}
        self.assertEqual(nodes["s0"].function, "prepositional_phrase")
        self.assertEqual(nodes["s1"].relation, "preposed_adjunct")
        self.assertEqual(nodes["s2"].function, "prepositional_phrase")
        self.assertEqual(nodes["s3"].function, "matrix_clause")
        self.assertEqual(nodes["s0"].governor, "s3")
        self.assertEqual(nodes["s2"].governor, "s3")
        for node in unit.constituents:
            self.assertEqual(source[node.start:node.end].strip(),
                             source[node.start:node.end])
            if node.governor is not None:
                self.assertIn(node.governor, nodes)

    def test_ellipsis_nonfinite_and_causal_roles(self):
        cases = (
            ("On one side of the fire, sat my mother; on the other, Mr. Murdstone.",
             "elliptical_clause", "parallel_ellipsis"),
            ("I deferred the explanation; merely informing her in my letters.",
             "nonfinite_clause", "supplement"),
            ("He promised to return; which he did.",
             "supplementary_relative_clause", "relative_modifier"),
            ("They wanted food; for they were hungry.",
             "coordinate_clause", "causal_coordination"),
            ("I commanded him to order a meal; and to inquire about letters.",
             "coordinate_predicate", "shared_subject"),
        )
        for source, function, relation in cases:
            with self.subTest(source=source):
                unit, = analyze_paragraph(source)
                self.assertTrue(unit.eligible_for_parse)
                self.assertEqual(len([c for c in unit.constituents
                                      if c.id.startswith("s")]), 2)
                latter = next(c for c in unit.constituents if c.id == "s1")
                self.assertEqual((latter.function, latter.relation),
                                 (function, relation))
                self.assertEqual(latter.governor, "s0")
                self.assertEqual(source[latter.start:latter.end],
                                 source.split(";", 1)[1].strip())

    def test_matched_reported_speech_is_linked_to_reporting_predicate(self):
        source = '“I have arrived,” said Mary.'
        unit, = analyze_paragraph(source)
        self.assertTrue(unit.eligible_for_parse)
        speech = next(c for c in unit.constituents
                      if c.function == "direct_speech")
        reporter = next(c for c in unit.constituents
                        if c.function == "reporting_clause")
        self.assertEqual(unit.text[speech.start:speech.end], "“I have arrived,”")
        self.assertEqual(unit.text[reporter.start:reporter.end], "said Mary")
        self.assertEqual(speech.governor, reporter.id)
        self.assertEqual(speech.relation, "reported_content")

    def test_unclosed_source_quotation_is_not_synthetically_fixed(self):
        source = '"Have you heard the story?'
        unit, = analyze_paragraph(source)
        self.assertFalse(unit.eligible_for_parse)
        self.assertEqual(unit.text, source)
        self.assertEqual(unit.quotation_status, "unresolved_source_quotation")
        book = Book(999, "Mock", "No", "train")
        rows, counts = extract(book, source, length_min=1)
        self.assertEqual(rows, [])
        self.assertEqual(counts["requires_source_context"], 1)

    def test_apostrophes_are_lexical_not_misidentified_as_speech(self):
        for text in ("He couldn't go.", "Don't wait for John's dog.",
                     "He went out o' that place.", "The boys' house was old."):
            with self.subTest(text=text):
                _, quotes, faults = quote_scan(text)
                self.assertEqual(quotes, [])
                self.assertEqual(faults, 0)
                self.assertTrue(analyze_paragraph(text)[0].eligible_for_parse)

    def test_extraction_carries_validated_components_to_parse_gateway(self):
        source = '“I came. I saw.” He departed.'
        book = Book(999, "Mock", "No", "train")
        cases, counts = extract(book, source, length_min=1)
        self.assertEqual(counts["eligible"], 2)
        self.assertEqual([c["source_text"] for c in cases],
                         ['“I came. I saw.”', "He departed."])
        for case in cases:
            self.assertEqual(case["source_text"], case["balanced_analysis_text"])
            self.assertFalse(case["balanced_synthetic_prefix"])
            self.assertFalse(case["balanced_synthetic_suffix"])
            prepared = prepare_corpus_input(case)
            self.assertEqual(prepared.analysis_text, case["text"])
            self.assertEqual(prepared.source_component("u0"), case["text"])
            self.assertTrue(prepared.structural_constituents)
        broken = dict(cases[0])
        parts = [dict(c) for c in broken["structural_constituents"]]
        parts[1]["governor"] = "not_a_real_component"
        broken["structural_constituents"] = parts
        with self.assertRaisesRegex(ValueError, "governor"):
            prepare_corpus_input(broken)


if __name__ == "__main__":
    unittest.main()
