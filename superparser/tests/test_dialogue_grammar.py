"""Regression contract for real direct speech, kept separate from novels."""
from __future__ import annotations

from pathlib import Path
import unittest

from seman_parser.dialogue import dialogue_lattice, quotation_boundaries
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import LexicalLattice

DATA=Path(__file__).resolve().parents[1]/"data"


def descendant_ids(item):
    return (item.rule_id,)+tuple(
        rule for child in item.children for rule in descendant_ids(child)
    )


class DialogueGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser=Parser.from_dir(DATA,cache_size=0,max_items=20000)

    def test_quote_boundaries_not_confused_with_apostrophes(self):
        sentence='"I am here," said Mary.'
        boundaries=quotation_boundaries(sentence)
        self.assertEqual([b.side for b in boundaries],["open","close"])
        self.assertEqual(quotation_boundaries("I'm leaving."),())
        self.assertEqual(quotation_boundaries('"Unfinished'),())
        self.assertEqual(quotation_boundaries('“hello"'),())
        self.assertEqual([b.side for b in quotation_boundaries('“Hello,” she said.')],
                         ["open","close"])

    def test_marker_overlay_preserves_original_lexical_edges(self):
        from seman_parser.segmentation import build_lattice
        raw='"John goes."'
        base=build_lattice(raw,self.parser.resources.lexicon,multiword_max=1)
        extra=dialogue_lattice(base)
        self.assertIsNotNone(extra)
        self.assertEqual(extra.candidates[:len(base.candidates)],base.candidates)
        self.assertEqual(
            [(c.category,c.surface) for c in extra.candidates[len(base.candidates):]],
            [("OPEN-QUOTE",'"'),("CLOSE-QUOTE",'"'),("SPEECH-STOP",".")] if False
            else [("OPEN-QUOTE",'"'),("CLOSE-QUOTE",'"'),("SPEECH-STOP",".")])
        self.assertIsNone(dialogue_lattice(LexicalLattice("Hello",(),())))

    def test_parser_reports_inverted_speaker_and_spoken_content(self):
        text='"John walks," said Mary.'
        report=self.parser.parse(text)
        best=report.result.best()
        self.assertIsNotNone(best,"direct quotation with speech attribution")
        self.assertTrue(report.result.stats.get("dialogue_scoped"),report.result.stats)
        self.assertEqual(report.result.text,text)
        self.assertIn("dialogue_post_tag",descendant_ids(best))
        self.assertIn("dialogue_speech_tag_inverted",descendant_ids(best))
        package=report.interpret()
        relations=[r.as_dict() for r in package.graph.relations]
        self.assertTrue(any(r["relation"]=="AGENT" for r in relations),relations)
        self.assertTrue(any(r["relation"]=="REPORTED_CONTENT" for r in relations),relations)

    def test_parser_preposed_speaker(self):
        text='Mary said, "John walks."'
        best=self.parser.parse(text).result.best()
        self.assertIsNotNone(best)
        self.assertIn("dialogue_pre_tag",descendant_ids(best))

    def test_parser_postposed_speaker(self):
        text='"John walks," Mary said.'
        best=self.parser.parse(text).result.best()
        self.assertIsNotNone(best)
        self.assertIn("dialogue_post_tag",descendant_ids(best))

    def test_quotes_without_tag_are_not_discarded(self):
        text='"John walks."'
        report=self.parser.parse(text)
        self.assertTrue(report.result.completed)
        self.assertTrue(report.result.stats.get("dialogue_scoped"))
        self.assertIn("dialogue_unattributed",descendant_ids(report.result.best()))

    def test_unquoted_prose_keeps_canonical_grammar(self):
        report=self.parser.parse("John walks.")
        self.assertFalse(report.result.stats.get("dialogue_scoped",False))
        self.assertNotIn("dialogue_post_tag",descendant_ids(report.result.best()))


if __name__=="__main__":
    unittest.main()
