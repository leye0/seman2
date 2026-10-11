"""Grammar and lexicon data-loading tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser.grammar import Grammar, load_grammar, load_grammar_rows, parse_rule
from seman_parser.lexicon import Lexicon, load_lexicon, load_lexicon_rows
from seman_parser.features import Variable

DATA = Path(__file__).resolve().parents[1] / "data"
WN_DICT = Path(__file__).resolve().parents[2] / ".local" / "share" / "wordnet" / "WordNet-3.0" / "dict"


class GrammarTests(unittest.TestCase):
    def test_parse_rule_with_bind_shorthand(self) -> None:
        rule = parse_rule(
            {
                "id": "clause_np_vp",
                "rhs": [
                    {"category": "NP", "bind": {"number": "?n", "referent": "?subject"}},
                    {"category": "VP", "bind": {"number": "?n"}},
                ],
                "lhs": {"category": "CLAUSE"},
                "semantic": [{"link": {"relation": "AGENT", "source": "event", "target": "subject"}}],
            }
        )
        self.assertEqual(rule.arity, 2)
        self.assertEqual(rule.rhs[0].exports.get("referent"), "subject")
        number = rule.rhs[0].features.get("number")
        self.assertIsInstance(number, Variable)
        # Semantic recipes are intentionally absent from syntax rules.
        self.assertFalse(hasattr(rule, "semantic"))

    def test_index_by_first_category(self) -> None:
        grammar = load_grammar_rows(
            [
                {"id": "r1", "rhs": [{"category": "NP"}], "lhs": {"category": "CLAUSE"}},
                {"id": "r2", "rhs": [{"category": "V"}], "lhs": {"category": "VP"}},
            ]
        )
        candidates = grammar.candidates_for_first("NP")
        self.assertEqual([r.rule_id for r in candidates], ["r1"])

    def test_load_disk_grammar(self) -> None:
        grammar = load_grammar(DATA / "grammar.jsonl")
        self.assertGreater(len(grammar), 5)
        rule = grammar.by_id("clause_np_vp")
        self.assertEqual(rule.lhs.category, "CLAUSE")


class LexiconTests(unittest.TestCase):
    def test_load_disk_lexicon(self) -> None:
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        entry = lexicon.by_lemma("give")
        self.assertIsNotNone(entry)
        self.assertGreater(len(entry.senses), 0)  # type: ignore[union-attr]

    def test_surface_lookup(self) -> None:
        lexicon = load_lexicon_rows(
            [
                {
                    "lemma": "box",
                    "surfaces": ["box", "boxes"],
                    "senses": [{"id": "box-1", "category": "N", "features": {"number": "singular"}}],
                    "morphology": {"boxes": "box"},
                }
            ]
        )
        self.assertEqual(len(lexicon.lookup_surface("BOX")), 1)
        self.assertEqual(len(lexicon.lookup_surface("boxes")), 1)

    def test_morphology_fallback(self) -> None:
        lexicon = load_lexicon_rows(
            [
                {
                    "lemma": "open",
                    "surfaces": ["open"],
                    "senses": [{"id": "open-1", "category": "V", "features": {"vform": "finite"}}],
                }
            ]
        )
        matches = lexicon.lookup_morphology("opened")
        self.assertTrue(any(sense.sense_id == "open-1" for _, sense, _ in matches))

    def test_frames(self) -> None:
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        # by_lemma may return the noun entry; scan all POS entries for the verb.
        framed = [
            s
            for entry in lexicon.entries_for_lemma("give")
            for s in entry.senses
            if s.frames
        ]
        self.assertTrue(framed, "no WordNet frames imported for 'give'")
        roles = {slot.syntactic: slot.semantic_role for slot in framed[0].frames[0].slots}
        self.assertIn("subject", roles)
        self.assertTrue(roles["subject"])


if __name__ == "__main__":
    unittest.main()
