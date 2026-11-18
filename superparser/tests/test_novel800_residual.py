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
        sources=ladder.load_pinned_fixture_sources()
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


    def test_n708_nonfinite_letter_subscription_and_signatory(self):
        from seman_parser.scoped_novel_800 import LETTER_SIGNOFF
        self.verify(708,'"Your affectionate and afflicted father, "Arthur Morgan.',
            '"Your affectionate and afflicted father "Arthur Morgan.',
            LETTER_SIGNOFF,["OPEN-QUOTE","NP","COMMA","CLOSE-QUOTE","NP","SPEECH-STOP"],
            [("DOCUMENT_SIGNATORY","subscription","signature")])
        for text in (708,'"Your affectionate and afflicted father, "Arthur Morgan.'):
            prepared,lattice,result=self.parse(text)
            root=result.best()
            self.assertEqual(root.features.as_dict().get("documentary"),"true")
            self.assertEqual(root.features.as_dict().get("nonfinite"),"true")

    def test_n713_source_date_keeps_truncated_year(self):
        from seman_parser.scoped_novel_800 import DOCUMENT_DATELINE
        self.verify(713,'"Oxford, May 13th, 17--."',
            '"Oxford, May 13th, 1700."',
            DOCUMENT_DATELINE,["OPEN-QUOTE","NP","COMMA","N","SOURCE-ORDINAL",
                               "COMMA","TRUNCATED-YEAR","SPEECH-STOP","CLOSE-QUOTE"],
            [("DOCUMENT_LOCATION","day","place"),("TRUNCATED_YEAR","day","year")])
        prepared,lattice,result=self.parse(713)
        root=result.best()
        year=root.children[6]
        self.assertEqual(prepared.analysis_text[year.start:year.end],"17--")
        self.assertEqual(year.features.as_dict().get("year_incomplete"),"true")
        self.assertEqual(root.features.as_dict().get("documentary"),"true")

    def test_n718_spoken_plan_colon_vocative_and_purpose(self):
        from seman_parser.scoped_novel_800 import SPOKEN_PLAN_COMMAND
        self.verify(718,'"To go instantly to London: come with me, Edward, to order the horses."',
            '"To go instantly to London; come with me, Edward, to order the horses."',
            SPOKEN_PLAN_COMMAND,["OPEN-QUOTE","TO","V","ADV","PP","COLON","CLAUSE","COMMA",
                                 "NP","COMMA","TO","V","NP","SPEECH-STOP","CLOSE-QUOTE"],
            [("GOAL","go","destination"),("DISCOURSE_PLAN","go","come"),
             ("VOCATIVE","come","vocative"),("PURPOSE","come","order"),
             ("THEME","order","horses")])

    def test_n732_overt_aborted_thought_and_reporting(self):
        from seman_parser.scoped_novel_800 import DASH_INTERRUPTED
        self.verify(732,'"I thought perhaps Dr. Murray--" I began.',
            '"I thought perhaps Dr. Murray—" I began.',
            DASH_INTERRUPTED,["OPEN-QUOTE","CLAUSE","ADV","TITLE","ABBREVIATION-STOP",
                              "NP","DASH","CLOSE-QUOTE","CLAUSE","SPEECH-STOP"],
            [("UNFINISHED_CONTENT","thought","name"),("REPORTED_CONTENT","report","thought"),
             ("HONORIFIC","name","title")])

    def test_n735_epistemic_incise_not_locative(self):
        from seman_parser.scoped_novel_800 import PARENTHETICAL_CHANCE
        self.verify(735,"In the meantime I had a better chance, as I supposed, before him.",
            "In the meantime I had a better chance as I supposed, before him.",
            PARENTHETICAL_CHANCE,["PP","CLAUSE","COMMA","CONJ","NP","V",
                                  "COMMA","PP","SPEECH-STOP"],
            [("TIME","matrix","time"),("EPISTEMIC_PARENTHESESIS","matrix","supposed"),
             ("LOCATIVE_COMPLEMENT","matrix","locative")])


    def test_n721_nested_lake_relative_is_attached_to_the_part(self):
        from seman_parser.scoped_novel_800 import STORM_LOCATIVE
        positive=("The most violent storm hung exactly north of the town, over the part of the lake "
                  "which lies between the promontory of Riverton and the village of Acton.")
        negative=("The most violent storm hung exactly north of the town, over the part of the lake "
                  "who lies between the promontory of Riverton and the village of Acton.")
        self.verify(721,positive,negative,STORM_LOCATIVE,
            ["NP","V","ADV","PP","COMMA","PREP","NP","WH-PRONOUN","V","PP","SPEECH-STOP"],
            [("AGENT","hung","storm"),("LOCATION","hung","north"),
             ("RELATIVE","part","lies"),("LOCATION","lies","between")])

    def test_n749_conditional_shared_perfect_and_overt_directional_ellipsis(self):
        from seman_parser.scoped_novel_800 import INVERTED_CONDITIONAL
        source=self.cases[749]["source_text"]
        positive=source.replace("away to sea.","away to shore.")
        negative=source.replace("should have fallen","should have fall")
        self.verify(749,positive,negative,INVERTED_CONDITIONAL,
            ["HAVE","EXPL","AUX-BE","NP","COMMA","NP","MODAL","HAVE","V","PREP",
             "NP","WH-PRONOUN","AUX-BE","V","ADV","PP","COMMA","V","NP","COMMA",
             "COORD","ADV","PP","SPEECH-STOP"],
            [("INVERTED_CONDITION","fallen","been"),
             ("MODALITY","fallen","should"),
             ("RELATIVE","mutineers","left"),
             ("SHARED_MODAL_CONJUNCT","fallen","slipped"),
             ("DIRECTIONAL_ELLIPSIS","slipped","away")])
        prepared,lattice,result=self.parse(749)
        self.assertEqual(result.best().features.as_dict().get("ellipsis"),"directional")
        self.assertFalse(any(c.category=="V" and prepared.analysis_text[c.start:c.end]=="gone"
                             for c in result.best().children))

    def test_n795_fronted_predicate_and_parallel_elliptic_attributes(self):
        from seman_parser.scoped_novel_800 import FRONTED_VAIN
        source=self.cases[795]["source_text"]
        positive=source.replace("already self-destined","still self-destined")
        negative=source.replace("vain and useless","vain or useless")
        self.verify(795,positive,negative,FRONTED_VAIN,
            ["ADJ","ADV","MODAL","COPULA","NP","COMMA","ADJ","COORD","ADJ","NP",
             "COORD","NP","COMMA","CONJ","NP","COPULA","ADV","ADJ","JOIN-HYPHEN",
             "ADJ","PREP","INDEF-PRONOUN","SPEECH-STOP"],
            [("MODALITY","be","must"),("ATTRIBUTE","attentions","vain"),
             ("ATTRIBUTE","affection","vain2"),("ATTRIBUTE","praise","useless"),
             ("CONDITIONAL","be","were"),("CONDITION_ATTRIBUTE","were","destined")])


    def test_n763_polite_intercalated_report_and_shared_modal_control(self):
        from seman_parser.scoped_novel_800 import SPLIT_POLITE_REQUEST
        source=self.cases[763]["source_text"]
        positive=source.replace("to do this.","to do that.")
        negative=source.replace("will be seated","will be seating")
        self.verify(763,positive,negative,SPLIT_POLITE_REQUEST,
            ["OPEN-QUOTE","NP","V","COMMA","TITLE","COMMA","CLOSE-QUOTE",
             "CLAUSE","COMMA","OPEN-QUOTE","COMP-THAT","NP","MODAL","COPULA",
             "V","COMMA","COORD","V","NP","TO","V","NP","SPEECH-STOP","CLOSE-QUOTE"],
            [("REPORTED_CONTENT","report","beg"),("VOCATIVE","beg","sir"),
             ("SHARED_MODAL_CONJUNCT","seated","allow"),
             ("PASSIVE_PATIENT","seated","you"),
             ("CONTROL_COMPLEMENT","allow","do"),("AGENT","do","me")])

    def test_n791_comparative_genitive_ellipsis_preserves_source_token(self):
        from seman_parser.scoped_novel_800 import EQUATIVE_FAVOURITE
        source=self.cases[791]["source_text"]
        positive=source.replace("Wickham","Darcy").replace("Jane's","Mary's")
        negative=source.replace("Jane's","Jane")
        self.verify(791,positive,negative,EQUATIVE_FAVOURITE,
            ["OPEN-QUOTE","NP","COMMA","ADV","COMMA","COPULA","NP",
             "SEMICOLON","COORD","NP","V","NP","MODAL","V","NP","ADV",
             "EQUATIVE-AS","ADV","EQUATIVE-AS","POSSESSIVE-ELLIPSIS",
             "SPEECH-STOP","CLOSE-QUOTE"],
            [("SUBJECT","is","wickham"),("EPISTEMIC_PARENTHESESIS","is","perhaps"),
             ("CONTENT","think","like"),("THEME","like","husband"),
             ("COMPARISON_STANDARD","well","jane"),
             ("ELLIPSIS_ANTECEDENT","jane","husband")])
        for text,expected in ((791,"Jane's"),(positive,"Mary's")):
            prepared,lattice,result=self.parse(text)
            root=result.best()
            nominal=next(c for c in root.children if c.category=="POSSESSIVE-ELLIPSIS")
            self.assertEqual(prepared.analysis_text[nominal.start:nominal.end],expected)
            self.assertTrue(nominal.features.as_dict().get("elliptical_nominal")=="true")
            self.assertFalse(any(c.surface=="husband" and
                                 c.start >= nominal.start for c in root.children
                                 if hasattr(c,"surface")))

    def test_n797_split_thanks_causal_anaphoric_if_and_two_outcomes(self):
        from seman_parser.scoped_novel_800 import SPLIT_CAUSAL_CONDITIONAL
        source=self.cases[797]["source_text"]
        positive=source.replace("said Lydia","said Mary")
        negative=source.replace("if you did","if you do")
        self.verify(797,positive,negative,SPLIT_CAUSAL_CONDITIONAL,
            ["OPEN-QUOTE","CLAUSE","COMMA","CLOSE-QUOTE","V","NP","COMMA",
             "OPEN-QUOTE","COORD","CONJ","NP","AUX","COMMA","CLAUSE","COMMA",
             "COORD","ADV","CLAUSE","SPEECH-STOP","CLOSE-QUOTE"],
            [("REPORTING_AGENT","said","name"),("REPORTED_CONTENT","said","thanks"),
             ("CONDITION","tell","did"),("SHARED_CONSEQUENCE","tell","consequence"),
             ("SEQUENCE","consequence","then")])

if __name__=="__main__":
    unittest.main()
