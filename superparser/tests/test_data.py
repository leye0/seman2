"""Grammar and lexicon data-loading tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser.grammar import Grammar, load_grammar, load_grammar_rows, parse_rule
from seman_parser.lexicon import Lexicon, load_lexicon, load_lexicon_rows
from seman_parser.features import Variable
from seman_parser.segmentation import build_lattice

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

    def test_inflected_surfaces_keep_only_compatible_morphology(self) -> None:
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        lattice = build_lattice("workers asked", lexicon)
        workers = [candidate for candidate in lattice.candidates if candidate.surface == "workers"]
        asked = [candidate for candidate in lattice.candidates if candidate.surface == "asked"]
        self.assertTrue(any(c.category == "N" and c.features.as_dict().get("number") == "plural" for c in workers))
        self.assertFalse(any(c.category == "N" and c.features.as_dict().get("number") == "singular" for c in workers))
        self.assertFalse(any(c.lemma == "as" for c in asked))
        self.assertFalse(any(c.category == "V" and c.features.as_dict().get("vform") == "base" for c in asked))

    def test_wordnet_exception_keeps_its_part_of_speech(self) -> None:
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        lattice = build_lattice("said mattered", lexicon)
        said = [candidate for candidate in lattice.candidates if candidate.surface == "said"]
        mattered = [candidate for candidate in lattice.candidates if candidate.surface == "mattered"]
        self.assertTrue(any(c.category == "V" and c.lemma == "say" for c in said))
        self.assertFalse(any(c.category == "N" and c.lemma == "say" for c in said))
        self.assertFalse(any(c.category == "N" and c.lemma == "matter" for c in mattered))

    def test_pronoun_forms_do_not_invent_possessives(self) -> None:
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        lattice = build_lattice("He saw him", lexicon)
        he = [candidate for candidate in lattice.candidates if candidate.surface == "He"]
        him = [candidate for candidate in lattice.candidates if candidate.surface == "him"]
        self.assertFalse(any(c.category == "POSS" for c in he))
        self.assertEqual(
            {c.features.as_dict().get("case") for c in he if c.category == "PRONOUN"},
            {"nominative"},
        )
        self.assertEqual(
            {c.features.as_dict().get("case") for c in him if c.category == "PRONOUN"},
            {"accusative"},
        )

    def test_sentence_initial_common_noun_is_not_preferred_as_a_name(self) -> None:
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        lattice = build_lattice("Workers arrived", lexicon)
        workers = [candidate for candidate in lattice.candidates if candidate.surface == "Workers"]
        noun_score = max(c.score for c in workers if c.category == "N")
        name_score = max(c.score for c in workers if c.category == "PROPER-NOUN")
        self.assertGreater(noun_score, name_score)


if __name__ == "__main__":
    unittest.main()
