"""The compiled one-token reader cannot consume multiword candidate spans.

Check that removing such spans leaves all token-wide lexical hypotheses
unchanged, including contractions, closed-class readings and proper names.
"""
from __future__ import annotations

import unittest

from seman_parser.lexicon import Lexicon, parse_entry
from seman_parser.segmentation import build_lattice


class TokenOnlyLatticeTests(unittest.TestCase):
    def test_exact_single_token_syntactic_candidates_unchanged(self):
        lex = Lexicon((
            parse_entry({"lemma": "take a breath", "surfaces": ["take a breath"],
                         "senses": [{"id": "multi", "category": "V",
                                     "features": {"vform": "base"}}]}),
            parse_entry({"lemma": "red car", "surfaces": ["red car"],
                         "senses": [{"id": "redcar", "category": "N",
                                     "features": {"number": "singular"}}]}),
            parse_entry({"lemma": "the", "surfaces": ["the"],
                         "senses": [{"id": "det", "category": "DET",
                                     "features": {}}]}),
        ))
        for text in (
            "Take a breath after the storm.",
            "The red car was parked near Maple Street.",
            "Theo's red car wasn't moving.",
            "One red car and another red car.",
        ):
            full = build_lattice(text, lex, multiword_max=4)
            token = build_lattice(text, lex, multiword_max=1)
            spans = {(t.start, t.end) for t in full.tokens}
            baseline = {
                c.syntactic_signature() for c in full.candidates
                if (c.span_start, c.span_end) in spans
            }
            reduced = {c.syntactic_signature() for c in token.candidates
                       if (c.span_start, c.span_end) in spans}
            self.assertEqual(baseline, reduced, text)

    def test_full_lattice_does_contain_longer_entries(self):
        lex = Lexicon((parse_entry({
            "lemma": "red car", "surfaces": ["red car"],
            "senses": [{"id": "redcar", "category": "N", "features": {}}]
        }),))
        full = build_lattice("red car", lex, multiword_max=4)
        compact = build_lattice("red car", lex, multiword_max=1)
        self.assertTrue(any(c.surface == "red car" for c in full.candidates))
        self.assertFalse(any(c.surface == "red car" for c in compact.candidates))


if __name__ == "__main__":
    unittest.main()
