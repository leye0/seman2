"""Case 96: exact rank-one syntax, source spans and contrastive controls.

The frozen Gutenberg quotation must always pass through parse_corpus_case.
Short independent controls use only Parser.parse. WordNet 3.0 is required.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from seman_parser.engine import Parser, ParserResources

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    "‘And there I shall take you to the stage-cutch, and the stage-cutch "
    "that’ll take you to--wherever it is.’"
)


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def surface(node, text):
    return text[node.start:node.end]


class Case96LocativeRelativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wordnet_dir = os.environ.get("WORDNET_DICT")
        if not wordnet_dir:
            raise unittest.SkipTest("reference WordNet 3.0 directory required")
        resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
        if not resources.lexicon.has_wordnet:
            raise unittest.SkipTest("reference WordNet 3.0 not available")
        cls.parser = Parser(resources, cache_size=0, max_items=50_000)

    def parse_control(self, sentence):
        report = self.parser.parse(
            sentence, max_items=50_000, kbest_work_limit=500_000,
        )
        return report.result.best(), report.result

    def test_frozen_quote_selected_tree_exact_attachments(self):
        book = Book(766, "David Copperfield", "Charles Dickens", "train")
        rows, _ = extract(book, SOURCE, length_min=1, length_max=100)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_text"], SOURCE)
        prepared, lattice, result = parse_corpus_case(
            self.parser, rows[0], max_items=50_000, kbest_work_limit=500_000,
        )
        self.assertEqual(prepared.source_text, SOURCE)
        self.assertEqual(prepared.analysis_text, SOURCE)
        self.assertTrue(result.completed)
        self.assertFalse(result.stats.get("budget_exceeded"))
        best = result.best()
        self.assertIsNotNone(best)
        self.assertEqual(best.rule_id, "dialogue_unattributed")
        self.assertEqual((best.start, best.end), (0, len(SOURCE)))

        coordinated = [node for node in walk(best)
                       if node.rule_id == "np_list_last"]
        self.assertTrue(coordinated, "the two destinations must share one NP coordination")
        pair = next(node for node in coordinated
                    if "stage-cutch, and the stage-cutch" in surface(node, SOURCE))
        self.assertEqual([child.category for child in pair.children],
                         ["NP", "COMMA", "COORD", "NP"])
        self.assertEqual(surface(pair.children[0], SOURCE), "the stage-cutch")
        self.assertEqual(pair.children[3].rule_id, "np_relative_subj")
        self.assertEqual(surface(pair.children[3], SOURCE),
                         "the stage-cutch that’ll take you to--wherever it is")

        candidates = [node for node in walk(pair.children[3])
                      if node.rule_id == "np_dash_locative_free_relative"]
        self.assertEqual(len(candidates), 1)
        pp = candidates[0]
        self.assertEqual(surface(pp, SOURCE), "--wherever it is")
        self.assertEqual([child.category for child in pp.children],
                         ["DASH", "WH-NOM", "CLAUSE"])
        self.assertEqual([surface(child, SOURCE) for child in pp.children],
                         ["--", "wherever", "it is"])
        self.assertEqual(pp.children[2].rule_id, "clause_np_vp")
        self.assertTrue(any(n.rule_id == "pp_prep_np" and
                            surface(n, SOURCE) == "to--wherever it is"
                            for n in walk(pair.children[3])))
        self.assertEqual(prepared.reference_span(pp.start, pp.end),
                         (pp.start, pp.end))

    def test_independent_directional_positive(self):
        sentence = "I will take her to--wherever she is."
        best, result = self.parse_control(sentence)
        self.assertTrue(result.completed)
        pps = [node for node in walk(best)
               if node.rule_id == "np_dash_locative_free_relative"]
        self.assertEqual([surface(node, sentence) for node in pps],
                         ["--wherever she is"])

    def test_without_dash_stays_ordinary_locative_np(self):
        sentence = "I shall take you to wherever it is."
        best, result = self.parse_control(sentence)
        self.assertTrue(result.completed)
        self.assertFalse(any(node.rule_id == "np_dash_locative_free_relative"
                             for node in walk(best)))
        self.assertTrue(any(node.rule_id == "np_wh_clause"
                            and surface(node, sentence) == "wherever it is"
                            for node in walk(best)))

    def test_nonlocative_relative_cannot_use_dash_rule(self):
        sentence = "I will go to--whatever it is."
        best, _ = self.parse_control(sentence)
        if best is not None:
            self.assertFalse(any(node.rule_id == "np_dash_locative_free_relative"
                                 for node in walk(best)))


if __name__ == "__main__":
    unittest.main()
