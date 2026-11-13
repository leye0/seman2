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

    def test_157_true_comparative_target_vocative_and_reporter(self):
        source=("“My overhearings were more to the purpose than yours, "
                "Eliza,” said Charlotte.")
        r=self.actual(157,source)
        n=self.root(r,"dialogue_structural_postposed_comparative_vocative_report")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE","“"),("NP","My overhearings"),("COPULA","were"),
            ("DEGREE","more"),("PP","to the purpose"),("CONJ","than"),
            ("POSS-PRONOUN","yours"),("COMMA",","),("NP","Eliza"),
            ("COMMA",","),("CLOSE-QUOTE","”"),
            ("SPEECH-TAG","said Charlotte"),("SPEECH-STOP","."),
        ])
        self.assertEqual(n.children[1].children[0].rule_id,"np_poss")
        self.assertEqual(n.children[6].features.as_dict().get(
            "independent_possessive"),"true")
        self.assertEqual(n.children[8].children[0].rule_id,"np_proper")
        self.assertEqual(n.children[11].children[0].rule_id,
                         "dialogue_speech_tag_inverted")

    def test_200_reduced_temporal_reporter_clausal_vocative(self):
        source=("“We are speaking of music, madam,” said he, "
                "when no longer able to avoid a reply.")
        r=self.actual(200,source)
        n=self.root(r,"dialogue_structural_postposed_temporal_reduced_reporter")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE","“"),("CLAUSE","We are speaking of music"),
            ("COMMA",","),("NP","madam"),("COMMA",","),
            ("CLOSE-QUOTE","”"),("V","said"),("NP","he"),
            ("COMMA",","),("CONJ","when"),("NEG-DEGREE","no"),
            ("ADV","longer"),("ADJ","able"),("TO","to"),
            ("V","avoid"),("NP","a reply"),("SPEECH-STOP","."),
        ])
        self.assertEqual(n.children[1].children[0].rule_id,"clause_np_vp")
        self.assertEqual(n.children[7].children[0].rule_id,"np_indef_pron")
        self.assertEqual(n.children[10].features.as_dict().get(
            "temporal_negation"),"true")
        self.assertEqual(n.children[12].features.as_dict().get(
            "infinitival_complement"),"true")
        self.assertEqual(n.children[14].features.as_dict().get("subcat"),
                         "transitive")
        self.assertEqual(n.children[15].children[0].rule_id,"np_det_n")

    def test_445_copular_predicate_coordination_with_overt_parenthetical(self):
        source='"That is all clear, and, I dare say, true enough," replied Dr. Livesey.'
        r=self.actual(445,source)
        n=self.root(r,
            "dialogue_structural_postposed_predicative_coord_parenthetical_report")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE",'"'),("CLAUSE","That is all clear"),
            ("COMMA",","),("COORD","and"),("COMMA",","),
            ("CLAUSE","I dare say"),("COMMA",","),
            ("ADJP","true enough"),("COMMA",","),("CLOSE-QUOTE",'"'),
            ("SPEECH-TAG","replied Dr. Livesey"),("SPEECH-STOP","."),
        ])
        self.assertEqual(n.children[1].children[0].rule_id,"clause_np_vp")
        self.assertEqual(n.children[5].children[0].rule_id,"clause_np_vp")
        self.assertEqual(n.children[7].children[0].rule_id,"adjp_adj_adv")
        self.assertEqual(n.children[10].children[0].rule_id,
                         "dialogue_speech_tag_inverted")





    def test_475_minor_evaluation_comparative_aux_and_negative_object_tag(self):
        source=(
            '"So far so good. But now I find that every man before the mast '
            'knows more than I do. I don\'t call that fair, now, do you?"'
        )
        r=self.actual(475,source)
        n=self.root(r,"dialogue_structural_comparative_negative_tag_sequence")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE",'"'),("MINOR-UTTERANCE","So far so good"),
            ("SPEECH-STOP","."),
            ("CLAUSE","But now I find that every man before the mast "
                      "knows more than I do"),
            ("SPEECH-STOP","."),
            ("SPEECH-ACT","I don't call that fair, now, do you?"),
            ("CLOSE-QUOTE",'"'),
        ])
        minor=n.children[1]
        self.assertEqual(minor.rule_id,
                         "dialogue_structural_equative_minor_formula")
        self.assert_kids(r,minor,[
            ("DEGREE","So"),("ADV","far"),("DEGREE","so"),("ADJ","good"),
        ])
        self.assertEqual(minor.features.as_dict()["verbless"],"true")
        claim=n.children[3]
        self.assertEqual(claim.rule_id,
                         "dialogue_structural_cognitive_that_comparative_claim")
        comparative=claim.children[-1]
        self.assertEqual(comparative.rule_id,
                         "dialogue_structural_comparative_aux_substitution")
        self.assert_kids(r,comparative,[
            ("NP","every man before the mast"),("V","knows"),
            ("DEGREE","more"),("CONJ","than"),("CLAUSE","I do"),
        ])
        self.assertEqual(comparative.children[0].children[0].rule_id,
                         "np_pp_mod")
        self.assertEqual(comparative.children[-1].children[0].rule_id,
                         "clause_aux_ellipsis")
        statement=n.children[5]
        self.assertEqual(statement.rule_id,
                         "dialogue_structural_negative_predicative_with_tag")
        self.assert_kids(r,statement,[
            ("CLAUSE","I don't call that fair"),("COMMA",","),
            ("ADV","now"),("COMMA",","),("TAG-QUESTION","do you?"),
        ])
        negative=statement.children[0]
        self.assertEqual(negative.rule_id,
                         "dialogue_structural_negative_object_predicative")
        self.assert_kids(r,negative,[
            ("NP","I"),("AUX","do"),("NEG","n't"),("V","call"),
            ("PRONOUN","that"),("ADJ","fair"),
        ])
        self.assertEqual(negative.children[2].features.as_dict()["negation"],"true")
        self.assertEqual(statement.children[-1].rule_id,
                         "dialogue_structural_positive_aux_question_tag")
        self.assert_kids(r,statement.children[-1],[
            ("AUX","do"),("NP","you"),("QMARK","?"),
        ])
        self.assertEqual(r.stats["structural_clause_count"],3)

    def test_475_requires_source_negation_and_auxiliary_ellipsis_tag(self):
        negatives=(
            '"So far so good. But now I find that every man before the mast '
            'knows more than I do. I call that fair, now, do you?"',
            '"So far so good. But now I find that every man before the mast '
            'knows more than I do. I don\'t call that fair, now, are you?"',
            '"So far so good. But now I find that every man before the mast '
            'knows more than I do. I don\'t call that fair, now, do you."',
        )
        for source in negatives:
            with self.subTest(source=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                self.assertEqual(len(cases),1)
                _,_,r=parse_corpus_case(self.parser,cases[0],
                               max_items=50_000,kbest_work_limit=500_000)
                self.assertNotEqual(r.stats.get("structural_composition_kind"),
                         "dialogue_structural_comparative_negative_tag_sequence")

    def test_498_numeric_and_relative_copula_with_two_true_tags(self):
        source=(
            '"That\'s your seven hundred thousand pounds, is it? '
            'You\'re the man for bargains, ain\'t you? '
            'You\'re him that never bungled nothing, you wooden-headed lubber!"'
        )
        r=self.actual(498,source)
        n=self.root(r,"dialogue_structural_three_confirmatory_tags_vocative")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE",'"'),
            ("CLAUSE","That's your seven hundred thousand pounds"),
            ("COMMA",","),
            ("TAG-QUESTION","is it?"),
            ("CLAUSE","You're the man for bargains"),
            ("COMMA",","),
            ("TAG-QUESTION","ain't you?"),
            ("CLAUSE","You're him that never bungled nothing"),
            ("COMMA",","),
            ("VOCATIVE","you wooden-headed lubber"),
            ("EXCL","!"),("CLOSE-QUOTE",'"'),
        ])
        self.assertEqual(n.children[1].children[0].rule_id,"clause_np_vp")
        self.assertEqual(n.children[1].children[0].children[1].rule_id,
                         "vp_cop_np")
        self.assertEqual(
            n.children[1].children[0].children[1].children[1].rule_id,
            "np_poss_num_n")
        self.assertEqual(n.children[4].children[0].children[1].children[1].rule_id,
                         "np_pp_mod")
        third=n.children[7].children[0].children[1].children[1]
        self.assertEqual(third.rule_id,"np_relative_subj")
        self.assertEqual(third.children[1].rule_id,"wh_subj_clause")
        pos=n.children[3]
        self.assertEqual(pos.rule_id,
                         "dialogue_structural_confirmatory_positive_copular_tag")
        self.assert_kids(r,pos,[("COPULA","is"),("NP","it"),("QMARK","?")])
        neg=n.children[6]
        self.assertEqual(neg.rule_id,
                         "dialogue_structural_confirmatory_negative_copular_tag")
        self.assert_kids(r,neg,[("COPULA","ain't"),("NP","you"),("QMARK","?")])
        self.assertEqual(neg.children[0].features.as_dict()["negation"],"true")
        vocative=n.children[9]
        self.assertEqual(vocative.rule_id,
                         "dialogue_structural_direct_address_compound_epithet")
        self.assert_kids(r,vocative,[
            ("NP","you"),("ADJP","wooden-headed"),("N","lubber"),
        ])
        self.assertEqual(vocative.children[1].children[0].rule_id,"adjp_adj")
        self.assertEqual(r.stats["structural_clause_count"],3)

    def test_498_tags_require_original_polarity_and_full_vocative(self):
        negatives=(
            '"That\'s your seven hundred thousand pounds, are you? '
            'You\'re the man for bargains, ain\'t you? '
            'You\'re him that never bungled nothing, you wooden-headed lubber!"',
            '"That\'s your seven hundred thousand pounds, is it? '
            'You\'re the man for bargains, are you? '
            'You\'re him that never bungled nothing, you wooden-headed lubber!"',
            '"That\'s your seven hundred thousand pounds, is it? '
            'You\'re the man for bargains, ain\'t you? '
            'You\'re him that never bungled nothing, you wooden-headed!"',
        )
        for source in negatives:
            with self.subTest(source=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                self.assertEqual(len(cases),1)
                _,_,r=parse_corpus_case(
                    self.parser,cases[0],max_items=50_000,
                    kbest_work_limit=500_000)
                self.assertNotEqual(r.stats.get("structural_composition_kind"),
                    "dialogue_structural_three_confirmatory_tags_vocative")

    def test_223_existential_incise_passive_and_wh_subject_question(self):
        source=(
            "“There has been many a one, I fancy, overcome in the same way. "
            "I wonder who first discovered the efficacy of poetry "
            "in driving away love!”"
        )
        r=self.actual(223,source)
        n=self.root(r,"dialogue_structural_existential_and_embedded_wh")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE","“"),
            ("CLAUSE","There has been many a one, I fancy, overcome in the same way"),
            ("SPEECH-STOP","."),
            ("CLAUSE","I wonder who first discovered the efficacy of poetry "
                       "in driving away love"),
            ("EXCL","!"),("CLOSE-QUOTE","”"),
        ])
        first=n.children[1]
        self.assertEqual(first.rule_id,
            "dialogue_structural_existential_perfect_parenthetical_reduced")
        self.assert_kids(r,first,[
            ("EXPL","There"),("HAVE","has"),("AUX-BE","been"),
            ("NP","many a one"),("COMMA",","),
            ("PARENTHETICAL","I fancy"),("COMMA",","),
            ("REDUCED-PASSIVE","overcome in the same way"),
        ])
        self.assertEqual(first.children[0].features.as_dict()["expletive"],"true")
        self.assertEqual(first.children[2].features.as_dict()["vform"],"ed")
        pivot=first.children[3]
        self.assertEqual(pivot.rule_id,
            "dialogue_structural_many_a_singular_quantifier")
        self.assert_kids(r,pivot,[
            ("DET","many"),("DET","a"),("NUM","one"),
        ])
        self.assertEqual(pivot.features.as_dict()["number"],"singular")
        self.assertEqual(first.children[5].rule_id,
             "dialogue_structural_first_person_fancy_parenthetical")
        passive=first.children[7]
        self.assertEqual(passive.rule_id,
             "dialogue_structural_past_participial_oblique_reduction")
        self.assert_kids(r,passive,[
            ("V","overcome"),("PP","in the same way"),
        ])
        self.assertEqual(passive.children[0].features.as_dict()["vform"],"ed")
        self.assertEqual(passive.children[1].children[0].rule_id,"pp_prep_np")
        second=n.children[3]
        self.assertEqual(second.rule_id,
             "dialogue_structural_finite_wonder_indirect_wh")
        self.assert_kids(r,second,[
            ("NP","I"),("V","wonder"),
            ("WH-CLAUSE","who first discovered the efficacy of poetry "
                          "in driving away love"),
        ])
        wh=second.children[2]
        self.assertEqual(wh.rule_id,
             "dialogue_structural_embedded_wh_subject_transitive_question")
        self.assert_kids(r,wh,[
            ("WH-PRONOUN","who"),("ADV","first"),("V","discovered"),
            ("NP","the efficacy of poetry in driving away love"),
        ])
        self.assertEqual(wh.children[-1].children[0].rule_id,"np_det_n_of")
        self.assertEqual(r.stats["structural_clause_count"],2)
        self.assertTrue(r.stats["source_text_unchanged"])

    def test_223_requires_overt_expletive_participle_and_wh_question(self):
        negatives=(
            # Here is locative, not existential EXPL there.
            "“Here has been many a one, I fancy, overcome in the same way. "
            "I wonder who first discovered the efficacy of poetry "
            "in driving away love!”",
            # Participial morphology requires the original irregular reading.
            "“There has been many a one, I fancy, overcoming in the same way. "
            "I wonder who first discovered the efficacy of poetry "
            "in driving away love!”",
            # A relative WH pronoun must not be mislicensed as an
            # independent interrogative WH-subject.
            # A declarative 'that' is not the interrogative subject 'who'.
            "“There has been many a one, I fancy, overcome in the same way. "
            "I wonder that first discovered the efficacy of poetry "
            "in driving away love!”",
        )
        for source in negatives:
            with self.subTest(source=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                self.assertEqual(len(cases),1)
                prepared,_,r=parse_corpus_case(
                    self.parser,cases[0],max_items=50_000,
                    kbest_work_limit=500_000)
                self.assertEqual(prepared.source_text,source)
                self.assertNotEqual(r.stats.get("structural_composition_kind"),
                     "dialogue_structural_existential_and_embedded_wh")

    def test_235_intent_reporter_ditransitive_and_causal_possessive(self):
        source=(
            "“And we mean to treat you all,” added Lydia, "
            "“but you must lend us the money, for we have just spent ours "
            "at the shop out there.”"
        )
        r=self.actual(235,source)
        n=self.root(r,"dialogue_structural_split_intent_causal_request")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE","“"),("COORD","And"),
            ("CLAUSE","we mean to treat you all"),
            ("COMMA",","),("CLOSE-QUOTE","”"),
            ("SPEECH-TAG","added Lydia"),
            ("COMMA",","),("OPEN-QUOTE","“"),("COORD","but"),
            ("CAUSAL-CLAUSE", "you must lend us the money, "
                                "for we have just spent ours at the shop out there"),
            ("SPEECH-STOP","."),("CLOSE-QUOTE","”"),
        ])
        intent=n.children[2]
        self.assertEqual(intent.rule_id,
            "dialogue_structural_finite_intent_transitive_infinitive")
        self.assert_kids(r,intent,[
            ("NP","we"),("V","mean"),("TO","to"),
            ("V","treat"),("NP","you all"),
        ])
        obj=intent.children[-1]
        self.assertEqual(obj.rule_id,
            "dialogue_structural_postposed_universal_pronoun")
        self.assert_kids(r,obj,[("NP","you"),("DET","all")])
        reporter=n.children[5]
        self.assertEqual(reporter.rule_id,
            "dialogue_structural_inverted_past_clausal_report")
        self.assert_kids(r,reporter,[("V","added"),("NP","Lydia")])
        self.assertEqual(reporter.children[1].children[0].rule_id,"np_proper")
        causal=n.children[9]
        self.assertEqual(causal.rule_id,
            "dialogue_structural_causal_explanatory_coordination")
        self.assert_kids(r,causal,[
            ("CLAUSE","you must lend us the money"),("COMMA",","),
            ("COORD","for"),
            ("CLAUSE","we have just spent ours at the shop out there"),
        ])
        request=causal.children[0]
        self.assertEqual(request.rule_id,
            "dialogue_structural_modal_double_object_request")
        self.assert_kids(r,request,[
            ("NP","you"),("MODAL","must"),("V","lend"),
            ("NP","us"),("NP","the money"),
        ])
        self.assertEqual(request.children[3].children[0].rule_id,"np_indef_pron")
        self.assertEqual(request.children[4].children[0].rule_id,"np_det_n")
        self.assertEqual(causal.children[2].features.as_dict().get(
            "causal_coordination"),"true")
        explanation=causal.children[3]
        self.assertEqual(explanation.rule_id,
            "dialogue_structural_recent_perfect_independent_possessive")
        self.assert_kids(r,explanation,[
            ("NP","we"),("HAVE","have"),("ADV","just"),
            ("V","spent"),("POSS-PRONOUN","ours"),
            ("PP","at the shop out there"),
        ])
        self.assertEqual(explanation.children[4].features.as_dict().get(
            "independent_possessive"),"true")
        self.assertEqual(explanation.children[5].children[0].rule_id,
                         "pp_pp_advp")
        self.assertEqual(r.stats["structural_clause_count"],3)
        self.assertEqual(r.text,source)

    def test_235_causal_coordination_needs_real_lexical_evidence(self):
        good=(
            "“And we mean to treat you all,” added Mary, "
            "“but you must lend us the money, for we have just spent ours "
            "at the shop out there.”"
        )
        cases,_=extract(Book(999,"Grammar","Test","train"),
                        good,length_min=1,length_max=100)
        self.assertEqual(len(cases),1)
        _,_,r=parse_corpus_case(self.parser,cases[0],
                   max_items=50_000,kbest_work_limit=500_000)
        self.assertTrue(r.completed,r.stats)
        self.assertEqual(r.best().rule_id,
                         "dialogue_structural_split_intent_causal_request")
        negatives=(
            # And is not a causal 'for' subordinate/coordinator.
            "“And we mean to treat you all,” added Lydia, "
            "“but you must lend us the money, and we have just spent ours "
            "at the shop out there.”",
            # No source-licensed independent possessive 'ourselves'.
            "“And we mean to treat you all,” added Lydia, "
            "“but you must lend us the money, for we have just spent ourselves "
            "at the shop out there.”",
            # A preposition is not a postposed universal quantifier.
            "“And we mean to treat you with,” added Lydia, "
            "“but you must lend us the money, for we have just spent ours "
            "at the shop out there.”",
        )
        for source in negatives:
            with self.subTest(source=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                self.assertEqual(len(cases),1)
                prepared,_,r=parse_corpus_case(
                    self.parser,cases[0],
                    max_items=50_000,kbest_work_limit=500_000)
                self.assertEqual(prepared.source_text,source)
                self.assertNotEqual(r.stats.get("structural_composition_kind"),
                     "dialogue_structural_split_intent_causal_request")

    def test_441_true_perfect_contraction_and_marine_locative_adverbials(self):
        source=(
            '"Pew," he cried, "they\'ve been before us. '
            'Someone\'s turned the chest out alow and aloft."'
        )
        r=self.actual(441,source)
        n=self.root(r,
            "dialogue_structural_intercalated_vocative_two_perfect")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE",'"'),("NP","Pew"),("COMMA",","),
            ("CLOSE-QUOTE",'"'),("SPEECH-TAG","he cried"),
            ("COMMA",","),("OPEN-QUOTE",'"'),
            ("CLAUSE","they've been before us"),
            ("SPEECH-STOP","."),
            ("CLAUSE","Someone's turned the chest out alow and aloft"),
            ("SPEECH-STOP","."),("CLOSE-QUOTE",'"'),
        ])
        self.assertEqual(n.children[1].children[0].rule_id,"np_proper")
        self.assertEqual(n.children[4].children[0].rule_id,
                         "dialogue_speech_tag_post")
        self.assertEqual(n.children[7].children[0].rule_id,"clause_np_vp")
        last=n.children[9]
        self.assertEqual(last.rule_id,
                         "dialogue_structural_perfect_transitive_particle_adverbial")
        self.assert_kids(r,last,[
            ("NP","Someone"),("HAVE","'s"),("V","turned"),
            ("NP","the chest"),("PARTICLE","out"),
            ("ADVP","alow and aloft"),
        ])
        self.assertEqual(last.children[1].features.as_dict().get("vform"),
                         "finite")
        self.assertEqual(last.children[2].features.as_dict().get("vform"),
                         "ed")
        self.assertEqual(last.children[3].children[0].rule_id,"np_det_n")
        marine=last.children[5]
        self.assertEqual(marine.rule_id,
                         "dialogue_structural_maritime_vertical_adverbs")
        self.assert_kids(r,marine,[
            ("ADV","alow"),("COORD","and"),("ADV","aloft"),
        ])
        self.assertEqual(last.features.as_dict().get("aspect"),"perfect")
        self.assertEqual(r.stats["structural_clause_count"],2)
        self.assertEqual(r.text,source)

    def test_split_vocative_perfect_has_positive_and_morphological_negatives(self):
        positive=(
            '"John," he cried, "they\'ve been before us. '
            'Someone\'s turned the chest out alow and aloft."'
        )
        cases,_=extract(Book(999,"Grammar","Test","train"),
                        positive,length_min=1,length_max=100)
        self.assertEqual(len(cases),1)
        _,_,parsed=parse_corpus_case(
            self.parser,cases[0],max_items=50_000,kbest_work_limit=500_000)
        self.assertTrue(parsed.completed,parsed.stats)
        self.assertEqual(parsed.best().rule_id,
             "dialogue_structural_intercalated_vocative_two_perfect")
        negatives=(
            '"Pew," he cried, "they\'ve been before us. '
            'Someone\'s turning the chest out alow and aloft."',
            '"Pew," he cried, "they\'ve been before us. '
            'Someone\'s turned the chest out alow and down."',
            '"Pew," he cried, "they\'ve been before us; '
            'Someone\'s turned the chest out alow and aloft."',
        )
        for source in negatives:
            with self.subTest(source=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                self.assertEqual(len(cases),1)
                prepared,_,r=parse_corpus_case(
                    self.parser,cases[0],max_items=50_000,
                    kbest_work_limit=500_000)
                self.assertEqual(prepared.source_text,source)
                self.assertNotEqual(
                    r.stats.get("structural_composition_kind"),
                    "dialogue_structural_intercalated_vocative_two_perfect",
                )

    def test_229_three_overt_imperative_speech_acts_have_correct_governors(self):
        source=(
            "“My dear, do not give way to such gloomy thoughts. "
            "Let us hope for better things. "
            "Let us flatter ourselves that I may be the survivor.”"
        )
        r=self.actual(229,source)
        n=self.root(r,"dialogue_structural_inclusive_let_imperative_sequence")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE","“"),("NP","My dear"),("COMMA",","),
            ("CLAUSE","do not give way to such gloomy thoughts"),
            ("SPEECH-STOP","."),
            ("CLAUSE","Let us hope for better things"),
            ("SPEECH-STOP","."),
            ("CLAUSE","Let us flatter ourselves that I may be the survivor"),
            ("SPEECH-STOP","."),("CLOSE-QUOTE","”"),
        ])
        self.assertEqual(n.children[1].children[0].rule_id,"np_poss")
        self.assertEqual(n.children[3].children[0].rule_id,"clause_imp_neg")
        self.assertEqual(n.children[3].features.as_dict().get("negation"),"true")
        hope=n.children[5]
        self.assertEqual(hope.rule_id,"dialogue_structural_inclusive_let_prep_directive")
        self.assert_kids(r,hope,[
            ("V","Let"),("NP","us"),("V","hope"),
            ("PP","for better things"),
        ])
        self.assertEqual(hope.children[1].children[0].rule_id,"np_indef_pron")
        self.assertEqual(hope.children[3].children[0].rule_id,"pp_prep_np")
        self.assertEqual(hope.features.as_dict()["stype"],"imperative")
        flatter=n.children[7]
        self.assertEqual(flatter.rule_id,
                         "dialogue_structural_inclusive_let_reflexive_that_directive")
        self.assert_kids(r,flatter,[
            ("V","Let"),("NP","us"),("V","flatter"),
            ("EMPHATIC-REFLEXIVE","ourselves"),("COMP-THAT","that"),
            ("CLAUSE","I may be the survivor"),
        ])
        self.assertEqual(flatter.children[2].features.as_dict().get(
                         "reflexive_that_complement"),"true")
        self.assertEqual(flatter.children[3].features.as_dict().get(
                         "reflexive"),"true")
        self.assertEqual(
            (flatter.children[1].features.as_dict().get("person"),
             flatter.children[1].features.as_dict().get("number")),
            (flatter.children[3].features.as_dict().get("person"),
             flatter.children[3].features.as_dict().get("number")),
        )
        self.assertEqual(flatter.children[5].children[0].rule_id,"clause_np_vp")
        self.assertEqual(r.stats["structural_clause_count"],3)
        self.assertFalse(r.stats.get("elided_vp_lexical_content_inserted",False))
        self.assertTrue(r.stats["source_text_unchanged"])

    def test_inclusive_imperatives_have_independent_positive_and_negative_controls(self):
        positives=(
            "“My friend, do not give way to such gloomy thoughts. "
            "Let us hope for better things. "
            "Let us flatter ourselves that I may be the survivor.”",
        )
        for source in positives:
            with self.subTest(positive=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                self.assertEqual(len(cases),1)
                _,_,r=parse_corpus_case(
                    self.parser,cases[0],max_items=50_000,
                    kbest_work_limit=500_000,
                )
                self.assertTrue(r.completed,r.stats)
                self.assertEqual(r.best().rule_id,
                     "dialogue_structural_inclusive_let_imperative_sequence")
        negatives=(
            # Singular third-person controller is NOT inclusive 1PL.
            "“My dear, do not give way to such gloomy thoughts. "
            "Let them hope for better things. "
            "Let us flatter ourselves that I may be the survivor.”",
            # Reflexive object must agree with the first-plural controller.
            "“My dear, do not give way to such gloomy thoughts. "
            "Let us hope for better things. "
            "Let us flatter himself that I may be the survivor.”",
            # A merely adjacent conditional is not a lexically selected
            # overt THAT content clause.
            "“My dear, do not give way to such gloomy thoughts. "
            "Let us hope for better things. "
            "Let us flatter ourselves if I may be the survivor.”",
        )
        for source in negatives:
            with self.subTest(negative=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                self.assertEqual(len(cases),1)
                prepared,_,r=parse_corpus_case(
                    self.parser,cases[0],max_items=50_000,
                    kbest_work_limit=500_000,
                )
                self.assertEqual(prepared.source_text,source)
                self.assertNotEqual(
                    r.stats.get("structural_composition_kind"),
                    "dialogue_structural_inclusive_let_imperative_sequence",
                )

    def test_99_source_temporal_protasis_and_verbless_frequency_reprise(self):
        source=(
            "‘As long as you are here, my pet, I shall come over "
            "every week of my life to see you. One day, every week of my life!’"
        )
        r=self.actual(99,source)
        n=self.root(r,"dialogue_structural_temporal_vocative_minor_reprise")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE","‘"),("TEMPORAL-CLAUSE","As long as you are here"),
            ("COMMA",","),("NP","my pet"),("COMMA",","),
            ("CLAUSE","I shall come over every week of my life to see you"),
            ("SPEECH-STOP","."),("MINOR-UTTERANCE",
                "One day, every week of my life!"),("CLOSE-QUOTE","’"),
        ])
        antecedent=n.children[1]
        self.assertEqual(antecedent.rule_id,
                         "dialogue_structural_temporal_finite_subordinate")
        self.assertEqual(antecedent.children[0].rule_id,
                         "dialogue_structural_temporal_as_long_as")
        self.assertEqual(
            [(k.category,source[k.start:k.end])
             for k in antecedent.children[0].children],
            [("CONJ","As"),("ADJ","long"),("CONJ","as")],
        )
        self.assertEqual(antecedent.children[1].children[0].rule_id,
                         "clause_np_vp")
        self.assertEqual(n.children[5].children[0].rule_id,"clause_np_vp")
        minor=n.children[7]
        self.assertEqual(minor.rule_id,
                         "dialogue_structural_nominal_temporal_reprise")
        self.assertEqual(
            [(k.category,source[k.start:k.end]) for k in minor.children],
            [("NP","One day"),("COMMA",","),
             ("NP","every week of my life"),("EXCL","!")],
        )
        self.assertEqual(minor.features.as_dict().get("verbless"),"true")
        self.assertEqual(r.stats["structural_clause_count"],2)

    def test_99_does_not_promote_unproved_reprises_or_broken_temporal_markers(self):
        examples=(
            "‘As long as you are here, my pet, I shall come over "
            "every week of my life to see you. Quickly, every week of my life!’",
            "‘As soon as you are here, my pet, I shall come over "
            "every week of my life to see you. One day, every week of my life!’",
        )
        for source in examples:
            with self.subTest(source=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                self.assertEqual(len(cases),1)
                prepared,_,r=parse_corpus_case(
                    self.parser,cases[0],max_items=50_000,
                    kbest_work_limit=500_000,
                )
                self.assertNotEqual(
                    r.stats.get("structural_composition_kind"),
                    "dialogue_structural_temporal_vocative_minor_reprise",
                )
                self.assertEqual(prepared.source_text,source)

    def test_237_split_preface_shared_modal_and_possessive_gerund(self):
        source=(
            "“But surely,” said she, “I may enter his county with impunity, "
            "and rob it of a few petrified spars without his perceiving me.”"
        )
        r=self.actual(237,source)
        n=self.root(r,"dialogue_structural_split_shared_modal_coord_gerund")
        self.assert_kids(r,n,[
            ("OPEN-QUOTE","“"),("COORD","But"),("ADV","surely"),
            ("COMMA",","),("CLOSE-QUOTE","”"),
            ("SPEECH-TAG","said she"),("COMMA",","),
            ("OPEN-QUOTE","“"),("NP","I"),("MODAL","may"),
            ("VP","enter his county with impunity"),("COMMA",","),
            ("COORD","and"),
            ("VP","rob it of a few petrified spars without his perceiving me"),
            ("SPEECH-STOP","."),("CLOSE-QUOTE","”"),
        ])
        self.assertEqual(n.children[5].children[0].rule_id,
                         "dialogue_speech_tag_inverted")
        first,second=n.children[10],n.children[13]
        self.assertEqual(first.rule_id,"dialogue_structural_source_transitive_pp_vp")
        self.assertEqual(second.rule_id,
                         "dialogue_structural_source_transitive_two_pp_vp")
        self.assertEqual(
            [(x.category,source[x.start:x.end]) for x in second.children],
            [("V","rob"),("NP","it"),("PP","of a few petrified spars"),
             ("PP","without his perceiving me")],
        )
        gerund=second.children[-1]
        self.assertEqual(gerund.rule_id,"dialogue_structural_possessive_gerund_pp")
        self.assertEqual(
            [(x.category,source[x.start:x.end]) for x in gerund.children],
            [("PREP","without"),("POSS","his"),
             ("V","perceiving"),("NP","me")],
        )
        self.assertEqual(gerund.children[2].features.as_dict()["vform"],"ing")
        self.assertEqual(r.stats["structural_clause_count"],1)
        self.assertEqual(r.text,source)

    def test_237_needs_real_possessive_gerund_and_object(self):
        examples=(
            "“But surely,” said she, “I may enter his county with impunity, "
            "and rob it of a few petrified spars without his perceive me.”",
            "“But surely,” said she, “I may enter his county with impunity, "
            "and rob it of a few petrified spars without his perceiving.”",
        )
        for source in examples:
            with self.subTest(source=source):
                cases,_=extract(Book(999,"Grammar","Test","train"),
                                source,length_min=1,length_max=100)
                self.assertEqual(len(cases),1)
                prepared,_,r=parse_corpus_case(
                    self.parser,cases[0],max_items=50_000,
                    kbest_work_limit=500_000,
                )
                self.assertFalse(
                    r.stats.get("structural_composition_kind") ==
                    "dialogue_structural_split_shared_modal_coord_gerund"
                )
                self.assertEqual(prepared.source_text,source)

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
