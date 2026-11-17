"""Source-grounded rank-one semantic checks for previously unreviewed cases.

Do NOT mark an individual verified solely because a test method passed:
the exact original source, an independent grammatical positive, an invalid
near-miss, a correct selected rule and overt semantic relations must all pass.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts import novel_ladder as ladder
from seman_parser.engine import Parser, ParserResources, ParseReport

ROOT=Path(__file__).resolve().parents[1]
BOOK=Book(91991, "Semantic audit independent controls", "Audit", "syntax")

class SemanticReviewCandidates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wordnet=Path(os.environ["WORDNET_DICT"])
        if not wordnet.is_dir():
            raise RuntimeError("WordNet 3.0 is required")
        cls.parser=Parser(ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet),
                          cache_size=0,max_items=50000)
        sources=ladder.load_sources()
        cohort=ladder.read_json(ladder.LADDER/"novel-700-cohort.json")
        cls.cases={r["ladder_index"]:r for r in ladder.resolve(cohort,601,sources)}
        candidate=ladder.read_json(ROOT/"research/novel_800_exploration/novel-800-candidate-cohort.json")
        cls.cases.update({r["ladder_index"]:r for r in ladder.resolve(candidate,701,sources)})
        cls.parser.parse("John opened the box.")

    def parse(self,source):
        if isinstance(source,int):
            case=self.cases[source]
        else:
            extracted,_=extract(BOOK,source,length_min=1,length_max=45)
            self.assertEqual(len(extracted),1,f"Unusable independent control: {source!r}")
            case=extracted[0]
        prepared,lattice,result=parse_corpus_case(self.parser,case,max_items=50000,kbest_work_limit=500000)
        self.assertEqual(prepared.analysis_text,case["source_text"])
        return prepared,lattice,result

    def check(self,index,positive,negative,links,expected_root):
        for source,is_positive in ((index,True),(positive,True),(negative,False)):
            with self.subTest(index=index,source=str(source)[:55]):
                prepared,lattice,result=self.parse(source)
                tree=result.best()
                if not is_positive:
                    self.assertFalse(tree and tree.rule_id==expected_root,
                                     "An unsuitable near-miss selected the allegedly verified source construction")
                    continue
                self.assertTrue(result.completed)
                self.assertIsNotNone(tree)
                self.assertEqual(tree.rule_id,expected_root)
                self.assertEqual(tree.start,0)
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                resources=(self.parser._quoted_sentence_resources or self.parser.resources
                           if result.stats.get("structural_composition") else
                           self.parser._dialogue_resources or self.parser.resources
                           if result.stats.get("dialogue_scoped") else self.parser.resources)
                package=ParseReport(result,resources,lattice).best_semantic_graph()
                self.assertIsNotNone(package)
                n={node["id"]:node for node in package["graph"]["nodes"]}
                observed={(e["relation"],n[e["source"]].get("surface"),
                                     n[e["target"]].get("surface"))
                          for e in package["graph"]["relations"]}
                for wanted in links:
                    self.assertIn(wanted,observed)
                for node in n.values():
                    span=node.get("span")
                    if span is not None and node.get("surface") is not None:
                        a,b=span
                        self.assertEqual(node["surface"],prepared.analysis_text[a:b])
                self.assertTrue(any(node.get("surface") == word for node in n.values()
                                    for word in (links[0][1],links[0][2])))

    def test_n655_bodypart_possession(self):
        self.check(655,"He shook his head.","He shake his head.",
            [("POSSESSOR","head","his"),("AFFECTED","shook","head"),
             ("AGENT","shook","He")],"clause_np_vp")

    def test_n663_reported_copular_content_and_vocative(self):
        positive="‘I hope Mrs. Micawber and your family are well, sir,’ said his aunt."
        negative="‘I hope Mrs. Micawber and your family are well, sir,’ said his."
        self.check(663,positive,negative,
            [("COMPLEMENT","hope","are"),("REPORTED_CONTENT","said","hope"),
             ("ATTRIBUTE","are","well"),("ADDRESSEE","said","sir")],
            "dialogue_structural_postposed_finite_clause_vocative")

    def test_n681_selected_passive_patient(self):
        self.check(681,"Mary was distressed.","Mary were distressed.",
            [("THEME","distressed","Mary")],"clause_passive")

    def test_n706_modalized_future_event(self):
        self.check(706,"But victory SHALL crown my efforts.",
            "But victory SHALL crowns my efforts.",
            [("MODALITY","crown","SHALL"),("AGENT","crown","victory"),
             ("AFFECTED","crown","efforts")],"coord_clause")

if __name__=="__main__":
    unittest.main()
