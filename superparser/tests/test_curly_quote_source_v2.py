"""Exact source and quote-pair regressions for the clipped-apostrophe fix."""
from __future__ import annotations

import unittest

from research.verbnet_lr.clean_novel_corpus import load_cleaned
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, analysis_units, extract, tokenize
from seman_parser.dialogue import quotation_boundaries
from seman_parser.structural_preanalysis import analyze_paragraph, quote_scan


class CurlyQuoteSourceTests(unittest.TestCase):
    def test_clipped_participle_does_not_end_multisentence_speech(self):
        text = "‘I was waitin’ for her! Then she came.’ The door closed."
        units = analyze_paragraph(text)
        first = "‘I was waitin’ for her! Then she came.’"
        self.assertEqual([u.source_text for u in units], [first, "The door closed."])
        self.assertEqual(quote_scan(first)[1:], ([(0, len(first))], 0))
        self.assertEqual([(b.start, b.side) for b in quotation_boundaries(first)],
                         [(0, "open"), (len(first) - 1, "close")])
        self.assertFalse(any(u.synthetic_prefix or u.synthetic_suffix for u in units))

    def test_true_close_is_retained_without_later_close_in_same_quote(self):
        text = "She said ‘waitin’ to amuse him. ‘That was not funny!’ he said."
        quotes = quote_scan(text)[1]
        self.assertEqual([text[a:b] for a, b in quotes], ["‘waitin’", "‘That was not funny!’"])
        self.assertEqual([text[x.start] for x in quotation_boundaries(text)], ["‘", "’", "‘", "’"])

    def test_nested_quotes_and_internal_apostrophes_keep_exact_spans(self):
        text = "‘I was thinkin’ about it. He said, “Don’t go!” and left.’"
        marks = [(b.start, b.side) for b in quotation_boundaries(text)]
        self.assertEqual(marks, [(0, "open"), (text.index("“"), "open"),
                                 (text.index("”"), "close"), (len(text) - 1, "close")])
        self.assertEqual(quote_scan(text)[2], 0)

    def test_quote_is_not_completed_with_synthetic_punctuation(self):
        passage = "‘I was waiting for her! Then she came."
        unit, = analyze_paragraph(passage)
        self.assertFalse(unit.eligible_for_parse)
        self.assertFalse(unit.synthetic_prefix or unit.synthetic_suffix)
        self.assertEqual(unit.source_text, passage)

    def test_dickens_frozen_fragment_recovers_its_actual_full_turn(self):
        book = next(b for b in TRAIN_BOOKS if b.ebook_id == 766)
        body, _ = load_cleaned(book)
        start = body.index("‘Lighted up, accordin’ to custom!")
        a = body.rindex("\n\n", 0, start) + 2
        b = body.index("\n\n", start)
        paragraph = body[a:b]
        unit = next(u for u in analysis_units(paragraph) if a + u.core_start == start)
        self.assertEqual(unit.source_text, " ".join(paragraph[unit.core_start:unit.core_end].split()))
        self.assertEqual(unit.quotation_status, "balanced")
        self.assertEqual(len(tokenize(unit.source_text)), 126)
        functions = {p.function for p in unit.constituents}
        self.assertTrue({"reporting_clause", "split_direct_speech_turn", "embedded_quotation"} <= functions)
        self.assertFalse(unit.synthetic_prefix or unit.synthetic_suffix or unit.synthetic_terminal)
        clipped = paragraph.index("accordin’") + len("accordin")
        self.assertNotIn(clipped - unit.core_start, [q.start for q in quotation_boundaries(unit.source_text)])
        rows, stats = extract(book, paragraph, length_min=4, length_max=32)
        self.assertFalse(any(r["source_text"].startswith("‘Lighted up") for r in rows))
        self.assertEqual(stats["too_long"], 1)


if __name__ == "__main__":
    unittest.main()
