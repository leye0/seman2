"""Independent controls for the two passages introduced by source resampling."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import unittest

from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts.evaluate_novel_transfer import ROOT, _deadline, measure
from seman_parser.engine import Parser, ParserResources

BOOK = Book(99000, "Independent source revision controls", "Audit", "syntax")
NEGATIVE_TAG = "dialogue_negative_copular_stance_vocative_tag_with_reporter_adjunct"
DIRECTION = "structural_fronted_direction_with_finite_motion"


class QuoteRevisionGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(
            ROOT / "data", wordnet_dict=Path(os.environ["WORDNET_DICT"]),
        ), cache_size=0, max_items=50_000)
        cls.parser.parse("John opened the box.")
        cls.addClassCleanup(signal.signal, signal.SIGALRM,
                            signal.signal(signal.SIGALRM, _deadline))

    def parse(self, text):
        cases, _ = extract(BOOK, text, length_min=1, length_max=32)
        case, = cases
        self.assertEqual(case["source_text"], text)
        return measure(self.parser, case, with_semantics=True)

    def check(self, text, root, expected):
        row = self.parse(text)
        self.assertEqual(row["status"], "complete")
        self.assertEqual(row["root_rule"], root)
        self.assertEqual(row["tree"]["span"], [0, len(text)])
        graph = row["selected_graph"]["graph"]
        nodes = {node["id"]: node for node in graph["nodes"]}
        for node in nodes.values():
            if node.get("span") and node.get("surface") is not None:
                start, end = node["span"]
                self.assertEqual(text[start:end], node["surface"])
        edges = {(e["relation"], nodes[e["source"]].get("surface"),
                  nodes[e["target"]].get("surface")) for e in graph["relations"]}
        self.assertLessEqual(set(expected), edges)

    def test_direction_is_not_discarded(self):
        self.check("Away we went.", DIRECTION, [("DIRECTION", "went", "Away"), ("AGENT", "went", "we")])
        self.check("Home they ran.", DIRECTION, [("DIRECTION", "ran", "Home"), ("AGENT", "ran", "they")])
        self.assertNotEqual(self.parse("Away we gone.")["root_rule"], DIRECTION)

    def test_dialectal_negative_and_reporter_adjunct_have_distinct_scope(self):
        self.check(
            "‘You an’t cross, I suppose, Peggotty, are you?’ said I, after sitting quiet for a minute.",
            NEGATIVE_TAG,
            [("NEGATION", "cross", "an’t"), ("VOCATIVE", "an’t", "Peggotty"),
             ("CONFIRMATION_TAG", "an’t", "are"), ("SPEAKER", "said", "I"),
             ("TEMPORAL_CLAUSE", "said", "sitting"), ("DEPICTIVE", "sitting", "quiet")],
        )
        self.check(
            "‘You aren’t ready, I imagine, Harriet, are you?’ said she, after standing silent for a moment.",
            NEGATIVE_TAG,
            [("NEGATION", "ready", "aren’t"), ("VOCATIVE", "aren’t", "Harriet"),
             ("TEMPORAL_CLAUSE", "said", "standing"), ("AGENT", "standing", "she")],
        )
        self.assertNotEqual(self.parse(
            "‘You aren’t ready, I imagine, Harriet, you are?’ said she, after standing silent for a moment.",
        )["root_rule"], NEGATIVE_TAG)
