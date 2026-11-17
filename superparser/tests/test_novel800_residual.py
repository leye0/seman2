"""Novel-800 source-first regression tests for four independently constrained repairs."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book,extract
from scripts import novel_ladder as ladder
from seman_parser.engine import Parser, ParserResources, ParseReport
from seman_parser.scoped_novel_800 import (
    FRONTED_SOURCE,PERFECT_INVERSION,UNLIKE_PREDICATE,ANAPHORIC_ELLIPSIS,
)

ROOT=Path(__file__).resolve().parents[1]
BOOK=Book(999,"Independent Novel-800 controls","Test","syntax")

class Novel800ResidualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wordnet=Path(os.environ["WORDNET_DICT"])
        if not wordnet.is_dir():
            raise RuntimeError("Pinned WordNet 3.0 dictionary required")
        cls.parser=Parser(ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet),
                          cache_size=0,max_items=50000)
        sources=ladder.load_sources()
        cohort=ladder.read_json(ROOT/"research"/"novel_800_exploration"/"novel-800-candidate-cohort.json")
        cls.cases={c["ladder_index"]:c for c in ladder.resolve(cohort,701,sources)}
        cls.parser.parse("John opened the box.")

    def parse(self,source):
        if isinstance(source,int):case=self.cases[source]
        else:
            cases,_=extract(BOOK,source,length_min=1,length_max=60)
            self.assertEqual(len(cases),1)
            case=cases[0]
        prepared,lattice,result=parse_corpus_case(self.parser,case,max_items=50000,kbest_work_limit=500000)
        self.assertEqual(prepared.analysis_text,case["source_text"])
        return prepared,lattice,result

    def verify(self,index,positive,negative,rule_id,expected_cats,links):
        for source,must in ((index,True),(positive,True),(negative,False)):
            with self.subTest(index=index,source=str(source)[:60]):
                prepared,lattice,result=self.parse(source)
                root=result.best()
                if not must:
                    self.assertTrue(root is None or root.rule_id!=rule_id)
                    continue
                self.assertTrue(result.completed)
                self.assertIsNotNone(root)
                self.assertEqual(root.rule_id,rule_id)
                self.assertEqual((root.start,root.end),(0,len(prepared.analysis_text)))
                self.assertEqual([c.category for c in root.children],expected_cats)
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                graph=ParseReport(result,self.parser._quoted_sentence_resources,lattice).best_semantic_graph()
                self.assertIsNotNone(graph)
                handles=graph["handles"]
                edges={(e["relation"],e["source"],e["target"]) for e in graph["graph"]["relations"]}
                for rel,left,right in links:
                    self.assertIn((rel,handles[left],handles[right]),edges)
                for n in graph["graph"]["nodes"]:
                    span=n.get("span")
                    surface=n.get("surface")
                    if span is not None and surface is not None:
                        a,b=span
                        self.assertEqual(surface,prepared.analysis_text[a:b])

    def test_n702_fronted_deictic_source(self):
        self.verify(702,"From there we proceeded to Paris.","From there proceeded to Paris.",
            FRONTED_SOURCE,["PREP","ADV","CLAUSE","SPEECH-STOP"],
            [("SOURCE","motion","deictic"),("MARKER","deictic","from")])

    def test_n704_yn_past_perfect_inversion_and_plural_agent(self):
        self.verify(704,"Had his eyes deceived him?","Had his eye deceived him?",
            PERFECT_INVERSION,["HAVE","NP","V","PRONOUN","QMARK"],
            [("PERFECT_ASPECT","deceived","had"),("AGENT","deceived","subject"),
             ("PATIENT","deceived","patient"),("POSSESSOR","eyes","poss")])
        for source in (704,"Had his eyes deceived him?"):
            with self.subTest(source=str(source),detail="plural-objective"):
                prepared,lattice,result=self.parse(source)
                root=result.best()
                subject=root.children[1]
                self.assertEqual(subject.category,"NP")
                self.assertEqual(subject.features.as_dict().get("number"),"plural")
                self.assertEqual(subject.children[-1].lexical_candidate.lemma,"eye")
                self.assertEqual(subject.children[-1].features.as_dict().get("number"),"plural")
                self.assertEqual(root.children[3].features.as_dict().get("case"),"accusative")

    def test_n705_copular_unlike_standard(self):
        self.verify(705,"This teacher was very unlike her colleague.",
            "This teacher were very unlike her colleague.",
            UNLIKE_PREDICATE,["NP","COPULA","ADJP","SPEECH-STOP"],
            [("SUBJECT","was","subject"),("PREDICATE","was","comparison"),
             ("COMPARISON_STANDARD","unlike","complement"),("DEGREE","unlike","very")])

    def test_n730_ellipsis_without_invented_predicate(self):
        self.verify(730,"So with the third.","So without the third.",
            ANAPHORIC_ELLIPSIS,["ADV","PP","SPEECH-STOP"],
            [("ANAPHORIC_PARALLEL","so","with")])
        prepared,lattice,result=self.parse(730)
        root=result.best()
        self.assertEqual(root.features.as_dict().get("elliptical"),"true")
        self.assertFalse(any(c.category=="V" or c.category=="CLAUSE" for c in root.children))

if __name__=="__main__":
    unittest.main()
