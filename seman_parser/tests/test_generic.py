"""Generic-engine invariants.

The runtime must stay corpus-agnostic: linguistic knowledge is data, the
novel is only a test corpus, and proper nouns are discovered by heuristics
rather than listed in the lexicon.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from seman_parser import Parser
from seman_parser.lexicon import load_lexicon
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1] / "seman_parser"
DATA = Path(__file__).resolve().parents[1] / "data"
WN_DICT = Path(__file__).resolve().parents[2] / ".local" / "share" / "wordnet" / "WordNet-3.0" / "dict"

# Identifiers that belong to a corpus, not to the engine.
CORPUS_TOKENS = {
    "maya", "jonah", "amira", "theo", "eli", "grandma",
    "rivera", "alvarez", "maple", "thenovel", "themap",
}


class GenericEngineTests(unittest.TestCase):
    def test_engine_code_has_no_corpus_identifiers(self) -> None:
        violations: list[str] = []
        for path in sorted(ROOT.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Name):
                    names.append(node.id)
                elif isinstance(node, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
                    names.append(node.name)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    # Only flag short name-like literals, not prose in docstrings.
                    value = node.value.strip()
                    if re.fullmatch(r"[A-Z][a-z]{2,12}", value):
                        names.append(value)
                for name in names:
                    if name.lower() in CORPUS_TOKENS:
                        violations.append(f"{path.name}:{node.lineno}:{name}")
        self.assertEqual(violations, [])

    def test_lexicon_has_no_corpus_names(self) -> None:
        """Content words must come from a resource, not a corpus word list.

        WordNet legitimately contains ``maple`` (the tree), ``maya`` (a
        people/language) and even ``jonah`` (a prophet). Those are English
        words, and their entries must say they come from WordNet. What is
        forbidden: an entry invented for a character of one book, and any
        dependence on the lexicon for ordinary unknown names.
        """
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        # Closed-class inventory is handwritten grammatical scaffolding.
        for entry in lexicon:
            if entry.senses and entry.senses[0].category in {"N", "V", "ADJ", "ADV"}:
                self.fail(f"open-class entry in static inventory: {entry.lemma}")
        # Open-class words come from WordNet at lookup time.
        for word in ("man", "run", "happy", "dog"):
            for entry in lexicon.entries_for_lemma(word):
                self.assertEqual(entry.provenance.get("source"), "wordnet", word)
        # Unknown names still parse with zero lexicon help.
        parser = Parser.from_dir(DATA)
        report = parser.parse("Zorblatt drew a map.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_unknown_capitalized_word_is_a_proper_noun(self) -> None:
        """Names are discovered generically — no lexicon entry required."""
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        self.assertIsNone(lexicon.by_lemma("Zorblatt"))
        lattice = build_lattice("Zorblatt left.", lexicon)
        proper = [c for c in lattice.candidates if c.category == "PROPER-NOUN"]
        self.assertTrue(proper, "proper-noun hypothesis missing for unknown name")
        self.assertEqual(proper[0].surface, "Zorblatt")

    def test_sentence_initial_function_word_is_not_only_a_name(self) -> None:
        """Casing alone must not force a name reading on closed-class words."""
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        lattice = build_lattice("Who left?", lexicon)
        who_categories = {c.category for c in lattice.candidates if c.surface.lower() == "who"}
        self.assertIn("WH-NOM", who_categories)
        self.assertNotIn("PROPER-NOUN", who_categories)

    def test_parses_sentence_with_invented_names(self) -> None:
        """Any names at all must parse without lexicon updates."""
        parser = Parser.from_dir(DATA)
        report = parser.parse("Zorblatt carried a blue notebook.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_both_readings_are_kept_for_ambiguous_capitalized_word(self) -> None:
        """Nothing is thrown away: common-noun + name hypotheses coexist."""
        lexicon = load_lexicon(DATA / "function_words.jsonl", wordnet_dict=WN_DICT)
        # "Street" is a known common noun but can also be part of a name.
        lattice = build_lattice("Maple Street was not famous.", lexicon)
        street = [c for c in lattice.candidates if c.surface == "Street"]
        categories = {c.category for c in street}
        self.assertIn("N", categories)
        self.assertIn("PROPER-NOUN", categories)


class KnowledgeIsDataTests(unittest.TestCase):
    def test_grammar_and_lexicon_are_data_files(self) -> None:
        self.assertTrue((DATA / "grammar.jsonl").exists())
        self.assertTrue((DATA / "function_words.jsonl").exists())
        self.assertTrue((DATA / "types.json").exists())

    def test_engine_never_dispatches_on_lemma(self) -> None:
        """No `if lemma == ...` / `if word == ...` branches in the runtime."""
        violations: list[str] = []
        for path in sorted(ROOT.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.If):
                    continue
                for child in ast.walk(node.test):
                    if isinstance(child, ast.Compare):
                        left_is_wordish = isinstance(child.left, ast.Name) and child.left.id.lower() in {
                            "lemma", "word", "surface", "verb", "token", "text",
                        }
                        if not left_is_wordish:
                            continue
                        for comparator in child.comparators:
                            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                                violations.append(f"{path.name}:{node.lineno}:{comparator.value!r}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
