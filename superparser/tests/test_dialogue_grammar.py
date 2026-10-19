"""Regression contract for real direct speech, kept separate from novels."""
from __future__ import annotations

from pathlib import Path
import unittest

from seman_parser.dialogue import dialogue_lattice, quotation_boundaries
from scripts.smoke_cleaned_novel_dialogues import (
    choose_stratified, quote_surface_layout, token_length_band,
)
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

    def test_real_novel_audit_layout_labels_only_visible_quotes(self):
        self.assertEqual(quote_surface_layout('"Hello!"'),"quote_only")
        self.assertEqual(quote_surface_layout('Mary said, "Hello!"'),
                         "narration_before_quote")
        self.assertEqual(quote_surface_layout('"Hello!" Mary said.'),
                         "narration_after_quote")
        self.assertEqual(quote_surface_layout('"Hello," said Mary, "Goodbye."'),
                         "multiple_quoted_spans")
        self.assertEqual(quote_surface_layout("I'm leaving."),
                         "no_balanced_double_quotes")

    def test_audit_stratification_is_deterministic_and_lossless(self):
        rows=[{"ordinal":i,"tokens":(5,12,20,29)[i%4]} for i in range(160)]
        first=choose_stratified(rows,40)
        self.assertEqual(first,choose_stratified(rows,40))
        self.assertEqual(len(first),40)
        self.assertEqual(len({r["ordinal"] for r in first}),40)
        self.assertEqual({token_length_band(r["tokens"]) for r in first},
                         {"04-08","09-16","17-24","25-32"})
        self.assertEqual(choose_stratified(rows[:2],10),rows[:2])

    def test_quote_boundaries_not_confused_with_apostrophes(self):
        sentence='"I am here," said Mary.'
        boundaries=quotation_boundaries(sentence)
        self.assertEqual([b.side for b in boundaries],["open","close"])
        self.assertEqual(quotation_boundaries("I'm leaving."),())
        self.assertEqual(quotation_boundaries('"Unfinished'),())
        self.assertEqual(quotation_boundaries('“hello"'),())
        self.assertEqual([b.side for b in quotation_boundaries('“Hello,” she said.')],
                         ["open","close"])

    def test_curly_single_quotes_are_dialogue_but_apostrophes_are_not(self):
        text="‘I don’t know.’"
        delimiters=quotation_boundaries(text)
        self.assertEqual(
            [(boundary.surface,boundary.side) for boundary in delimiters],
            [("‘","open"),("’","close")],
        )
        self.assertEqual(quotation_boundaries("I don’t know."),())
        self.assertEqual(quotation_boundaries("I know John’s family."),())
        self.assertEqual(quotation_boundaries("‘Unfinished sentence"),())
        self.assertEqual(quotation_boundaries("‘Broken”"),())

    def test_curly_single_quoted_clauses_use_scoped_dialogue_grammar(self):
        for text in ("‘John walks.’",):
            with self.subTest(text=text):
                result=self.parser.parse(text).result
                self.assertTrue(result.completed,result.stats)
                self.assertTrue(result.stats.get("dialogue_scoped"),result.stats)
                self.assertIn("dialogue_unattributed",descendant_ids(result.best()))

    def test_balanced_ascii_single_quotes_but_not_possessives(self):
        for text in ("'Who are you?'", "'John walks.'", "\"'I have food.'\""):
            with self.subTest(text=text):
                marks=quotation_boundaries(text)
                self.assertEqual(
                    [(item.side, item.surface) for item in marks if item.surface=="'"],
                    [("open", "'"), ("close", "'")],
                )
        for unquoted in ("John's book.", "a few minutes' conversation.",
                         "They've returned.", "M'Graw arrived."):
            with self.subTest(unquoted=unquoted):
                self.assertEqual(quotation_boundaries(unquoted), ())
        result=self.parser.parse("'John walks.'").result
        self.assertTrue(result.completed,result.stats)
        self.assertTrue(result.stats.get("dialogue_scoped"),result.stats)

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

    def test_quoted_prepositional_answer_as_direct_speech(self):
        # Pride and Prejudice contains the same standalone elliptical PP.
        original = '“With all my heart.”'
        report = self.parser.parse(original)
        self.assertTrue(report.result.completed, report.result.stats)
        self.assertTrue(report.result.stats.get("dialogue_scoped"))
        rules = descendant_ids(report.result.best())
        self.assertIn("dialogue_quote_pp_stop", rules)
        self.assertIn("np_universal_quantifier_possessive", rules)
        self.assertEqual(report.result.text, original)
        # Being a grammatical conversational answer does NOT imply that
        # every isolated PP should become a finite clause in ordinary prose.
        plain = self.parser.parse("With all my heart.")
        self.assertFalse(plain.result.stats.get("dialogue_scoped", False))

    def test_elliptical_dialogue_advp_and_asyndetic_pp_list(self):
        examples = (
            ("“Very, very much.”", ("advp_repeated_degree", "dialogue_quote_advp_stop")),
            ("“by reason, by reflection, by everything.”",
             ("dialogue_asyndetic_pp_triple", "dialogue_quote_pp_stop")),
            ("“Letters of business, too!”",
             ("clause_nominal_exclamation_post_adv", "dialogue_quote_clause")),
            ("“Indeed, I could not.”",
             ("clause_negative_modal_ellipsis", "dialogue_unattributed")),
        )
        for text, required in examples:
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(result.stats.get("dialogue_scoped"), result.stats)
                ids = set(descendant_ids(result.best()))
                for rule in required:
                    self.assertIn(rule, ids)

    def test_vocative_discourse_marker_in_quoted_question(self):
        text = "“Well, Jane, who is it from?”"
        result = self.parser.parse(text).result
        self.assertTrue(result.completed, result.stats)
        self.assertTrue(result.stats.get("dialogue_scoped"), result.stats)
        ids = set(descendant_ids(result.best()))
        self.assertIn("dialogue_discourse_vocative_clause", ids)
        self.assertIn("clause_wh_copula_stranded_prep_question", ids)
        unquoted = self.parser.parse("Well, Jane, who is it from?")
        self.assertFalse(unquoted.result.stats.get("dialogue_scoped", False))

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

    def test_split_quoted_subject_and_predicate_after_speech_tag(self):
        for sentence, focused in (
            ('"She," said Mary, "walks."', False),
            ('"She most of all," said Mary, "walks."', True),
        ):
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(result.stats.get("dialogue_scoped"), result.stats)
                ids = set(descendant_ids(result.best()))
                self.assertIn("dialogue_split_subject_predicate_tag", ids)
                self.assertIn(
                    "dialogue_quoted_subject_focus_fragment"
                    if focused else "dialogue_quoted_subject_pronoun_fragment", ids,
                )

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

    def test_split_quotation_with_attribution_and_continuation(self):
        text='"John walks," said Mary, "John listens."'
        report=self.parser.parse(text)
        best=report.result.best()
        self.assertIsNotNone(best, report.result.stats)
        self.assertIn("dialogue_split_tag", descendant_ids(best))
        relations=[edge.relation for edge in report.interpret().graph.relations]
        self.assertIn("REPORTED_CONTENT", relations)
        self.assertIn("CONTINUED_SPEECH", relations)

    def test_reporting_tag_with_prepositional_complement(self):
        text='Mary said to John, "John walks."'
        report=self.parser.parse(text)
        best=report.result.best()
        self.assertIsNotNone(best,report.result.stats)
        self.assertIn("dialogue_speech_tag_post_pp",descendant_ids(best))

    def test_quoted_fragment_with_reporting_tag(self):
        text='"Hello!" said Mary.'
        report=self.parser.parse(text)
        best=report.result.best()
        self.assertIsNotNone(best,report.result.stats)
        self.assertIn("dialogue_post_tag",descendant_ids(best))

    def test_semantic_speaker_is_not_the_reporting_verb(self):
        text='"John walks," said Mary.'
        report=self.parser.parse(text)
        graph=report.interpret().graph
        relations=graph.relations
        agents=[edge for edge in relations if edge.relation=="AGENT"]
        self.assertTrue(agents)
        target_nodes=[graph.nodes[edge.target] for edge in agents]
        self.assertIn("Mary",{node.surface for node in target_nodes})

    def test_single_apostrophes_do_not_enable_dialogue_grammar(self):
        for text in ["I'm leaving.", "John's book is here."]:
            with self.subTest(text=text):
                result=self.parser.parse(text).result
                self.assertFalse(result.stats.get("dialogue_scoped",False))

    def test_dialogue_cache_returns_same_certified_tree(self):
        parser=Parser.from_dir(DATA,cache_size=32,max_items=20000)
        text='"John walks," said Mary.'
        first=parser.parse(text)
        second=parser.parse(text)
        self.assertIs(first.result,second.result)
        self.assertIs(first.result.best(),second.result.best())
        self.assertTrue(second.result.stats.get("dialogue_scoped"))

    def test_future_corpus_lattice_dispatch_recognizes_dialogue(self):
        from seman_parser.segmentation import build_lattice
        text='"John walks," Mary said.'
        raw=build_lattice(text,self.parser.resources.lexicon,multiword_max=1)
        scoped=self.parser.parse_grammar_lattice(
            raw,kbest_work_limit=100000,max_items=20000)
        self.assertTrue(scoped.completed,scoped.stats)
        self.assertTrue(scoped.stats.get("dialogue_scoped"))
        self.assertIn("dialogue_post_tag",descendant_ids(scoped.best()))
        ordinary=self.parser._vector_grammar.parse_lattice(
            raw,beam=self.parser.beam,max_items=20000,
            goal_category=self.parser.goal_category,
            kbest_work_limit=100000)
        self.assertFalse(ordinary.stats.get("dialogue_scoped",False))

    def test_diagnostic_mode_preserves_dialogue_tree_and_roles(self):
        text='"John walks," said Mary.'
        report=self.parser.parse_diagnostic(text,alternatives=2,max_items=20000)
        self.assertTrue(report.result.completed)
        self.assertTrue(report.result.stats["dialogue_scoped"])
        self.assertTrue(report.result.stats["diagnostic_mode"])
        self.assertIn("dialogue_post_tag",descendant_ids(report.result.best()))
        self.assertIn("REPORTED_CONTENT",
                      [edge.relation for edge in report.interpret().graph.relations])

    def test_unquoted_prose_keeps_canonical_grammar(self):
        report=self.parser.parse("John walks.")
        self.assertFalse(report.result.stats.get("dialogue_scoped",False))
        self.assertNotIn("dialogue_post_tag",descendant_ids(report.result.best()))


if __name__=="__main__":
    unittest.main()
