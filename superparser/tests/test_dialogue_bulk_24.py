"""Rank-one grammar tests for several original dialogue failures in one batch.

Do not count permissive phrase acceptance. Every target uses the original
source text and canonical parse_corpus_case under unchanged parse budgets.
"""
from __future__ import annotations
import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser

DATA = Path(__file__).resolve().parents[1] / "data"


def walk(n):
    yield n
    for c in n.children:
        yield from walk(c)


class DialogueBulk24Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA,cache_size=0)
        cls.cases = select_cases(500)[0]

    def actual(self,idx,source):
        case = self.cases[idx]
        self.assertEqual(case["source_text"],source)
        prepared,lattice,result = parse_corpus_case(
            self.parser,case,max_items=50_000,kbest_work_limit=500_000)
        self.assertEqual(prepared.source_text,source)
        self.assertEqual(prepared.analysis_text,source)
        self.assertEqual(lattice.text,source)
        self.assertEqual(result.text,source)
        self.assertTrue(result.completed,(idx,result.stats))
        self.assertIsNotNone(result.best())
        self.assertTrue(result.stats["structural_composition"])
        self.assertTrue(result.stats["dialogue_scoped"])
        return result

    def root(self,result,rule):
        n=result.best()
        self.assertEqual(n.rule_id,rule,(result.text,result.stats))
        self.assertEqual(result.text[n.start:n.end],result.text)
        self.assertEqual(result.stats["structural_composition_kind"],rule)
        return n

    def assert_kids(self,result,node,expected):
        self.assertEqual(
            [(c.category,result.text[c.start:c.end]) for c in node.children],
            expected)

    def test_56_dash_pp_question_inverted_reporter_participial_adjunct(self):
        source="‘Without a story--really?’ inquired Dora, creeping closer to me."
        r=self.actual(56,source)
        root=self.root(r,"dialogue_structural_pp_dash_adverb_question_participial_reporter")
        self.assert_kids(r,root,[
            ("OPEN-QUOTE","‘"),("PP","Without a story"),("DASH","--"),
            ("ADV","really"),("QMARK","?"),("CLOSE-QUOTE","’"),
            ("V","inquired"),("NP","Dora"),("COMMA",","),
            ("V","creeping"),("ADV","closer"),("PP","to me"),
            ("SPEECH-STOP","."),
        ])
        self.assertEqual(root.children[1].children[0].rule_id,"pp_prep_np")
        self.assertEqual(root.children[7].children[0].rule_id,"np_proper")
        self.assertEqual(root.children[9].features.as_dict().get("vform"),"ing")
        self.assertEqual(root.children[9].features.as_dict().get("subcat"),
                         "prepositional")
        self.assertEqual(root.children[11].children[0].rule_id,"pp_prep_np")

    def test_66_interrupted_vocative_predicative_parenthetical_domain(self):
        source=("‘Now, David,’ said Mr. Murdstone, "
                "‘a sullen obdurate disposition is, of all tempers, the worst.’")
        r=self.actual(66,source)
        n=self.root(r,"dialogue_structural_split_vocative_copula_domain")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE","‘"),("ADV","Now"),("COMMA",","),
            ("NP","David"),("COMMA",","),("CLOSE-QUOTE","’"),
            ("SPEECH-TAG","said Mr. Murdstone"),("COMMA",","),
            ("OPEN-QUOTE","‘"),("DET","a"),("ADJ","sullen"),
            ("ADJ","obdurate"),("N","disposition"),("COPULA","is"),
            ("COMMA",","),("PP","of all tempers"),("COMMA",","),
            ("NP","the worst"),("SPEECH-STOP","."),("CLOSE-QUOTE","’"),
        ])
        self.assertEqual(n.children[6].children[0].rule_id,
                         "dialogue_speech_tag_inverted")
        self.assertEqual(n.children[15].children[0].rule_id,"pp_prep_np")
        self.assertEqual(n.children[17].children[0].rule_id,"np_det_n")

    def test_408_repeated_direction_exclamation_and_coordinated_report(self):
        source='"In, in, in!" he shouted, and cursed them for their delay.'
        r=self.actual(408,source)
        n=self.root(r,"dialogue_structural_repeated_directional_exclamation_coordinated_report")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE",'"'),("ADV","In"),("COMMA",","),
            ("ADV","in"),("COMMA",","),("ADV","in"),
            ("EXCL","!"),("CLOSE-QUOTE",'"'),("NP","he"),
            ("V","shouted"),("COMMA",","),("COORD","and"),
            ("V","cursed"),("NP","them"),("PP","for their delay"),
            ("SPEECH-STOP","."),
        ])
        self.assertEqual(n.children[8].children[0].rule_id,"np_indef_pron")
        self.assertEqual(n.children[9].features.as_dict().get("subcat"),"intransitive")
        self.assertEqual(n.children[12].features.as_dict().get("subcat"),"transitive")
        self.assertEqual(n.children[13].children[0].rule_id,"np_indef_pron")
        self.assertEqual(n.children[14].children[0].rule_id,"pp_prep_np")

    def test_456_overt_polite_conditional_vocative_and_finite_question(self):
        source='"If you please, sir," said Joyce, "if I see anyone, am I to fire?"'
        r=self.actual(456,source)
        n=self.root(r,"dialogue_structural_split_polite_conditional_vocative_question")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE",'"'),("CONJ","If"),("NP","you"),
            ("V","please"),("COMMA",","),("NP","sir"),
            ("COMMA",","),("CLOSE-QUOTE",'"'),
            ("SPEECH-TAG","said Joyce"),("COMMA",","),
            ("OPEN-QUOTE",'"'),("CLAUSE","if I see anyone, am I to fire?"),
            ("CLOSE-QUOTE",'"'),
        ])
        self.assertEqual(n.children[3].features.as_dict().get("polite_formula"),"true")
        self.assertEqual(n.children[8].children[0].rule_id,"dialogue_speech_tag_inverted")
        inner=n.children[11].children[0]
        self.assertEqual(inner.rule_id,"clause_cond")
        self.assertEqual(inner.children[-1].features.as_dict().get("stype"),
                         "question")

    def test_original_quote_and_syntax_gate_negative_controls(self):
        original=[
            ('"In, in, out!" he shouted, and cursed them for their delay.',
             "dialogue_structural_repeated_directional_exclamation_coordinated_report"),
            ('"If you vanish, sir," said Joyce, "if I see anyone, am I to fire?"',
             "dialogue_structural_split_polite_conditional_vocative_question"),
            ('‘Without a story--really?’ inquired Dora, creeping closer to me',
             "dialogue_structural_pp_dash_adverb_question_participial_reporter"),
        ]
        for source,forbidden in original:
            with self.subTest(source=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                if len(cases)!=1:
                    continue
                _,_,r=parse_corpus_case(self.parser,cases[0],
                              max_items=50_000,kbest_work_limit=500_000)
                for candidate in r.alternatives(limit=8):
                    self.assertFalse(any(n.rule_id==forbidden
                                        for n in walk(candidate)),source)

if __name__=="__main__":
    unittest.main()
