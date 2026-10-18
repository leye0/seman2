"""Regressions for the Layer 1 -> future Layer 2 evidence contract.

A complete parse MUST keep word surfaces and alternatives accessible, rather
than emitting only abstract categories. Tests use the standard WordNet fixture.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from seman_parser.engine import Parser, ParserResources, discover_wordnet

DATA=Path(__file__).resolve().parents[1]/"data"


class Layer1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources=ParserResources.from_dir(
            DATA, wordnet_dict=os.environ.get("WORDNET_DICT"))
        cls.parser=Parser(resources,cache_size=0)

    def test_words_survive_with_original_offsets_and_lexical_alternatives(self):
        original="John opened the box."
        report=self.parser.parse(original)
        result=report.result
        self.assertTrue(result.completed)
        self.assertEqual(result.text,original)
        self.assertGreater(len(result.lattice.candidates),len(result.lattice.tokens))
        best=result.best()
        self.assertIsNotNone(best)
        self.assertEqual(best.category,"CLAUSE")
        self.assertIsNotNone(result.shared_forest)
        leaves=[]
        stack=[best]
        while stack:
            node=stack.pop()
            if node.lexical_candidate is not None:
                leaves.append(node.lexical_candidate)
            stack.extend(node.children)
        self.assertTrue(leaves)
        for candidate in leaves:
            self.assertEqual(
                original[candidate.span_start:candidate.span_end],
                candidate.surface)
        self.assertTrue(any(candidate.surface=="John"
                            for candidate in result.lattice.candidates))
        self.assertTrue(best.syntax.anchors)

    def test_serialization_preserves_both_lattice_and_tree(self):
        report=self.parser.parse("John opened the box.")
        exported=report.as_dict()
        self.assertEqual(exported["text"],"John opened the box.")
        self.assertIn("lattice",exported)
        self.assertIn("best",exported)
        self.assertIn("syntax",exported["best"])
        self.assertIn("features",exported["best"])
        self.assertIn("children",exported["best"])
        self.assertNotIn("semantic",exported["best"])

    def test_semantics_is_a_separate_postparse_step(self):
        report=self.parser.parse("John opened the box.")
        best=report.result.best()
        signature=best.signature()
        self.assertIsNone(best.semantic)
        semantic=report.interpret(best)
        relations={e.relation for e in semantic.graph.relations}
        self.assertIn("AGENT",relations)
        self.assertTrue({"AFFECTED","THEME"} & relations)
        self.assertEqual(best.signature(),signature)
        self.assertIsNone(best.semantic)

    def test_bad_wordnet_override_does_not_silently_weaken_grammar(self):
        with patch.dict(os.environ,{"WORDNET_DICT":"/this/path/does/not/exist"}):
            with self.assertRaises(FileNotFoundError):
                discover_wordnet(DATA)


if __name__=="__main__":
    unittest.main()
