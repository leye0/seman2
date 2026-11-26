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

    def test_as_to_nominal_topic_is_not_finite_subordination(self):
        cases = (
            "As to a fish-kittle, Mrs. Crupp said, well! would I only come and look at the range?",
            "As to the garden, she had no objections.",
        )
        for source in cases:
            with self.subTest(source=source):
                unit, = analyze_paragraph(source)
                self.assertEqual(unit.source_text, source)
                self.assertFalse(any(
                    c.function == "adverbial_subordinate_clause" and
                    c.evidence == "subordinator_preposed_comma"
                    for c in unit.constituents
                ))
        # Real as-subordinates retain the fronted-clause evidence.
        unit, = analyze_paragraph("As she grew tired, she returned.")
        self.assertTrue(any(
            c.function == "adverbial_subordinate_clause"
            for c in unit.constituents
        ))

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

    def test_indented_quote_line_keeps_original_book_and_normalized_spans(self):
        prefix = "We found these verses in the book.\n\n"
        quote = "“Listen to the sound of the rain\n      While darkness covers the trees.”"
        unit = list(analysis_units(prefix + quote))[1]
        self.assertEqual((unit.core_start, unit.core_end), (len(prefix), len(prefix + quote)))
        line, = (c for c in unit.constituents if c.function == "typographic_line_break")
        self.assertEqual((line.start, line.end), (quote.index("\n"), quote.index("\n") + 1))
        self.assertEqual(unit.text[line.start - 4:line.end + 5], "rain While")
        for raw in (quote.replace("\n      ", "    "), quote.replace("      ", " "), quote[1:-1]):
            with self.subTest(raw=raw):
                self.assertFalse(any(c.function == "typographic_line_break"
                                     for u in analysis_units(raw) for c in u.constituents))

    def test_paragraph_emphasis_keeps_exact_punctuation_and_sentence_boundaries(self):
        from research.verbnet_lr.gutenberg_novels import Book, extract

        source = "_She went to London. Then she returned home._ He waited here."
        expected = ["_She went to London.", "Then she returned home._", "He waited here."]
        units = analyze_paragraph(source)
        self.assertEqual([u.source_text for u in units], expected)
        for unit, relation in zip(units, ("begin_and_continue", "continuation_and_close", None)):
            self.assertEqual(source[unit.source_start:unit.source_end], unit.source_text)
            emphasis = [c for c in unit.constituents if c.function == "typographic_emphasis"]
            if relation is None:
                self.assertEqual(emphasis, [])
            else:
                self.assertEqual(len(emphasis), 1)
                self.assertEqual((emphasis[0].start, emphasis[0].end), (0, len(unit.text)))
                self.assertEqual(emphasis[0].relation, relation)
        rows, _ = extract(Book(999, "Mock", "No", "train"), source, length_min=1)
        self.assertEqual([r["source_text"] for r in rows], expected)
        single, _ = extract(Book(999, "Mock", "No", "train"), "_They went away here._", length_min=1)
        self.assertEqual([r["source_text"] for r in single], ["_They went away here._"])
        plain, = analyze_paragraph("It was a snake_case identifier.")
        self.assertFalse(any(c.function == "typographic_emphasis" for c in plain.constituents))
        orphan, = analyze_paragraph("I was here without an opener._")
        self.assertFalse(orphan.eligible_for_parse)

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
