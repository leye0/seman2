"""Real 30-case dialogue composition: rank-1 grammar, not surface success.

The source at cohort position 413 is one of the 30 original failed
literary-dialogue witnesses, not a manufactured English sentence.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts.diagnose_novel_parses import select_cases
from scripts.audit_anchored_dialogue_30 import WITNESSES
from seman_parser.engine import Parser
from seman_parser.structural_composition import QuotedSentenceComposer


class ActualDialogueCompositions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(
            Path(__file__).resolve().parents[1] / "data", cache_size=0,
        )

    def test_original_failed_treasure_island_case_413_has_real_tree(self):
        case = select_cases(500)[0][413]
        witness = next(w for w in WITNESSES if w.index == 413)
        self.assertEqual(case["source_text"],
                         '"Very likely, sir," replied Captain Smollett.')
        self.assertEqual(
            f'{case["book_id"]}:'+
            sha256(case["source_text"].encode()).hexdigest()[:16],
            witness.case_id,
        )
        self.assertEqual(witness.baseline_status, "no_structural_root")
        prepared, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000,
            kbest_work_limit=500_000,
        )
        self.assertTrue(result.completed, result.stats)
        self.assertEqual(result.text, case["source_text"])
        self.assertEqual(lattice.text, case["source_text"])
        self.assertTrue(result.stats.get("structural_composition"))
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_postposed_minor_adverbial_vocative")
        self.assertEqual(result.best().start, 0)
        self.assertEqual(result.best().end, len(case["source_text"]))
        self.assertEqual(result.stats["structural_clause_count"], 0,
                         "A verbless answer is not a finite matrix clause")
        self.assertEqual(
            result.stats["structural_segment_rule_ids"][0],
            "advp_degree_adv",
        )
        self.assertTrue(
            result.stats["structural_segment_rule_ids"][2].startswith(
                "dialogue_speech_tag_"
            )
        )
        self.assertEqual(
            [case["source_text"][a:b]
             for a,b in result.stats["structural_segment_spans"]],
            ["Very likely", "sir", "replied Captain Smollett"],
        )
        self.assertEqual(
            [node.category for node in result.best().children],
            ["OPEN-QUOTE", "ADVP", "COMMA", "NP", "COMMA",
             "CLOSE-QUOTE", "SPEECH-TAG", "SPEECH-STOP"],
        )
        self.assertEqual(
            [node.rule_id for node in result.best().children
             if node.category in ("ADVP", "NP", "SPEECH-TAG")],
            ["segment_interface"] * 3,
        )
        self.assertEqual(prepared.source_component("r0"),
                         "replied Captain Smollett")

    def test_actual_dickens_11_nested_quoted_nominal_title(self):
        """Real corpus failure #11: title utterance, not a finite clause."""
        case=select_cases(500)[0][11]
        witness=next(w for w in WITNESSES if w.index==11)
        source="‘The “Little Em’ly”.’"
        self.assertEqual(case["source_text"],source)
        self.assertEqual(witness.baseline_status,"roots_without_valid_analysis")
        self.assertEqual(
            f'{case["book_id"]}:'+
            sha256(source.encode()).hexdigest()[:16],
            witness.case_id
        )
        plan=QuotedSentenceComposer._nested_nominal_title_plan(
            source,case["structural_constituents"]
        )
        self.assertIsNotNone(plan)
        article,name,punctuation=plan
        self.assertEqual(source[slice(*article)],"The")
        self.assertEqual(source[slice(*name)],"Little Em’ly")
        self.assertEqual(len(punctuation),5)
        prepared,lattice,result=parse_corpus_case(
            self.parser,case,max_items=50_000,kbest_work_limit=500_000,
        )
        self.assertTrue(result.completed,result.stats)
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_nested_nominal_title")
        self.assertEqual(result.stats["structural_clause_count"],0)
        self.assertEqual(result.stats["structural_composition_kind"],
                         "nominal_title_with_embedded_quote")
        self.assertEqual(
            [source[a:b] for a,b in result.stats["structural_segment_spans"]],
            ["The","Little Em’ly"]
        )
        self.assertEqual(result.stats["structural_segment_rule_ids"][1],
                         "np_adj_proper")
        self.assertEqual(
            [node.category for node in result.best().children],
            ["OPEN-QUOTE","DET","OPEN-QUOTE","NP",
             "CLOSE-QUOTE","SPEECH-STOP","CLOSE-QUOTE"]
        )
        self.assertEqual(
            [node.rule_id for node in result.best().children
             if node.category in ("DET","NP")],
            ["segment_interface","segment_interface"]
        )
        self.assertEqual(prepared.source_component("q1"),"“Little Em’ly”")
        self.assertEqual(prepared.source_text,result.text)
        self.assertFalse(prepared.synthetic_prefix)
        self.assertFalse(prepared.synthetic_suffix)

    def test_nested_quoted_adverb_not_promoted_to_nominal_title(self):
        source="‘The “very quickly”.’"
        rows,_=extract(Book(999,"Mock","Test","train"),source,
                       length_min=1,length_max=40)
        self.assertEqual(len(rows),1)
        prepared,_,result=parse_corpus_case(
            self.parser,rows[0],max_items=50_000,kbest_work_limit=500_000
        )
        self.assertFalse(result.stats.get("structural_composition",False))
        self.assertEqual(prepared.source_text,source)

    def test_actual_austen_137_topicalized_modal_ellipsis(self):
        """This is real grammatical ellipsis, not a synthetic finite verb."""
        case=select_cases(500)[0][137]
        witness=next(w for w in WITNESSES if w.index==137)
        source="“That you certainly shall.”"
        self.assertEqual(case["source_text"],source)
        self.assertEqual(witness.baseline_status,
                         "roots_without_valid_analysis")
        self.assertEqual(
            f'{case["book_id"]}:'+
            sha256(source.encode()).hexdigest()[:16],
            witness.case_id,
        )
        plan=QuotedSentenceComposer._modal_ellipsis_plan(
            source,case["structural_constituents"]
        )
        self.assertIsNotNone(plan)
        self.assertEqual([source[a:b] for a,b in plan],
                         ["That","you","certainly","shall"])
        prepared,_,result=parse_corpus_case(
            self.parser,case,max_items=50_000,kbest_work_limit=500_000,
        )
        self.assertTrue(result.completed,result.stats)
        self.assertTrue(result.stats.get("structural_composition"))
        self.assertEqual(
            result.best().rule_id,
            "dialogue_structural_topical_modal_vp_ellipsis",
        )
        self.assertEqual(result.stats["structural_composition_kind"],
                         "topical_modal_vp_ellipsis")
        self.assertEqual(
            [node.category for node in result.best().children],
            ["OPEN-QUOTE","NP","NP","ADV","MODAL",
             "SPEECH-STOP","CLOSE-QUOTE"],
        )
        self.assertTrue(result.stats["source_text_unchanged"])
        self.assertFalse(result.stats["discourse_antecedent_resolved"])
        self.assertFalse(result.stats["elided_vp_lexical_content_inserted"])
        self.assertEqual(prepared.source_text,result.text)
        self.assertFalse(prepared.synthetic_prefix)
        self.assertFalse(prepared.synthetic_suffix)

    def test_modal_ellipsis_requires_real_modal_and_demonstrative_topic(self):
        samples=(
            "“He you certainly shall.”",
            "“That you certainly dance.”",
        )
        for source in samples:
            with self.subTest(source=source):
                rows,_=extract(
                    Book(999,"Mock","Test","train"),
                    source,length_min=1,length_max=40,
                )
                self.assertEqual(len(rows),1)
                _,_,result=parse_corpus_case(
                    self.parser,rows[0],
                    max_items=50_000,kbest_work_limit=500_000,
                )
                self.assertFalse(
                    result.stats.get("structural_composition",False),
                    "An omitted verb cannot be inferred from an unsupported shape",
                )

    def test_actual_austen_157_exposes_comparative_head_without_fake_success(self):
        """Real #157 is a planned clause+vocative+tag, but needs proof.

        Never promote the proposed structure to a completed parse just from
        the existence of a speaker tag or an NP term of address.
        """
        case = select_cases(500)[0][157]
        witness = next(w for w in WITNESSES if w.index == 157)
        self.assertEqual(
            case["source_text"],
            "“My overhearings were more to the purpose than yours, Eliza,” said Charlotte.",
        )
        self.assertEqual(witness.baseline_status, "roots_without_valid_analysis")
        plan = QuotedSentenceComposer._postposed_minor_reply_plan(
            case["source_text"], case["structural_constituents"]
        )
        self.assertIsNotNone(plan)
        head, vocative, reporter, punctuation = plan
        self.assertEqual(case["source_text"][slice(*head)],
                         "My overhearings were more to the purpose than yours")
        self.assertEqual(case["source_text"][slice(*vocative)], "Eliza")
        self.assertEqual(case["source_text"][slice(*reporter)], "said Charlotte")
        self.assertEqual(len(punctuation), 5)
        prepared, _, result = parse_corpus_case(
            self.parser, case, max_items=50_000, kbest_work_limit=500_000,
        )
        self.assertEqual(result.text, case["source_text"])
        self.assertEqual(prepared.source_text, case["source_text"])
        if result.completed:
            self.assertTrue(result.stats.get("structural_composition"), result.stats)
            # The independently proven comparative predicate is now
            # composed from NP + finite copula + overt comparative domain
            # + true independent possessive target, not a fabricated
            # ordinary clause head.
            self.assertEqual(
                result.best().rule_id,
                "dialogue_structural_postposed_comparative_vocative_report",
            )
            parts = result.best().children
            self.assertEqual(
                [result.text[n.start:n.end] for n in parts],
                ["“", "My overhearings", "were", "more",
                 "to the purpose", "than", "yours", ",", "Eliza", ",",
                 "”", "said Charlotte", "."],
            )
            self.assertEqual(
                parts[6].features.as_dict().get("independent_possessive"),
                "true",
            )
            self.assertEqual(result.stats["structural_clause_count"], 1)
        else:
            self.assertFalse(result.stats.get("structural_composition", False))
            # Not seeing an accepted subclause is a real blocker. The
            # candidate source graph alone never fabricates an analysis.


    def test_actual_austen_222_interrupted_that_complement_is_source_exact(self):
        case = select_cases(500)[0][222]
        source = (
            "“I am afraid, Mr. Darcy,” observed Miss Bingley in a half whisper, "
            "“that this adventure has rather affected your admiration of her fine eyes.”"
        )
        self.assertEqual(case["source_text"], source)
        plan = QuotedSentenceComposer._intercalated_that_complement_plan(
            source, case["structural_constituents"],
        )
        self.assertIsNotNone(plan)
        self.assertEqual(
            [source[a:b] for a, b in plan[:5]],
            ["I am afraid", "Mr. Darcy",
             "observed Miss Bingley in a half whisper", "that",
             "this adventure has rather affected your admiration of her fine eyes"],
        )
        prepared, _, result = parse_corpus_case(
            self.parser, case, max_items=50_000, kbest_work_limit=500_000,
        )
        self.assertEqual(result.text, source)
        self.assertEqual(prepared.source_text, source)
        self.assertTrue(result.completed, result.stats)
        self.assertTrue(result.stats.get("structural_composition"), result.stats)
        self.assertEqual(
            result.best().rule_id,
            "dialogue_structural_intercalated_that_complement_vocative",
        )
        self.assertEqual(result.best().category, "CLAUSE")
        self.assertEqual((result.best().start, result.best().end),
                         (0, len(source)))
        self.assertEqual(
            [child.category for child in result.best().children],
            ["OPEN-QUOTE", "CLAUSE", "COMMA", "NP", "COMMA",
             "CLOSE-QUOTE", "SPEECH-TAG", "COMMA", "OPEN-QUOTE",
             "COMP-THAT", "CLAUSE", "SPEECH-STOP", "CLOSE-QUOTE"],
        )
        self.assertEqual(result.stats["structural_clause_count"], 2)
        self.assertEqual(
            result.stats["structural_segment_rule_ids"][0], "clause_np_vp",
        )
        self.assertEqual(
            result.stats["structural_segment_rule_ids"][-1], "clause_np_vp",
        )
        self.assertEqual(
            [source[a:b] for a, b in result.stats["structural_segment_spans"]],
            [source[a:b] for a, b in plan[:5]],
        )

    def test_intercalated_that_complement_needs_overt_lexical_selection(self):
        for source, expected in (
            ('"I am afraid, Mary," said John, "that Jane walks."', True),
            ('"I am tall, Mary," said John, "that Jane walks."', False),
            ('"I am afraid, Mary," said John, "if Jane walks."', False),
        ):
            with self.subTest(source=source):
                rows, _ = extract(
                    Book(999, "Mock", "Test", "train"),
                    source, length_min=1, length_max=60,
                )
                self.assertEqual(len(rows), 1)
                prepared, _, result = parse_corpus_case(
                    self.parser, rows[0],
                    max_items=50_000, kbest_work_limit=500_000,
                )
                self.assertEqual(prepared.source_text, source)
                self.assertEqual(result.text, source)
                self.assertEqual(
                    bool(result.stats.get("structural_composition")), expected,
                    result.stats,
                )
                if expected:
                    self.assertEqual(
                        result.best().rule_id,
                        "dialogue_structural_intercalated_that_complement_vocative",
                    )

    def test_syntax_generalizes_but_requires_grammar_proofs(self):
        positive = '"Very likely, sir," said Mary.'
        negative = '"Very likely, perhaps," said Mary.'
        for source, expected in ((positive, True),(negative,False)):
            with self.subTest(source=source):
                rows, _ = extract(
                    Book(999, "Mock", "Test", "train"),
                    source, length_min=1, length_max=50,
                )
                self.assertEqual(len(rows), 1)
                prepared, _, result = parse_corpus_case(
                    self.parser, rows[0], max_items=50_000,
                    kbest_work_limit=500_000,
                )
                self.assertEqual(prepared.source_text, source)
                self.assertEqual(result.text, source)
                self.assertEqual(
                    bool(result.stats.get("structural_composition")), expected,
                    result.stats,
                )

    def test_does_not_fake_a_copular_complement_or_speaker(self):
        source = '"Very likely," replied Captain Smollett.'
        rows, _ = extract(
            Book(999, "Mock", "Test", "train"),
            source, length_min=1, length_max=50,
        )
        prepared, _, result = parse_corpus_case(
            self.parser, rows[0], max_items=50_000,
            kbest_work_limit=500_000,
        )
        self.assertFalse(result.stats.get("structural_composition", False))
        self.assertEqual(prepared.source_text, source)

class InterruptedComparativeAndCleftTests(unittest.TestCase):
    NARRATIVE = (
        '“Now, Mary,” she replied—and I noticed the change as she spoke—'
        '“we should be much more cautious tomorrow than usual.”'
    )
    CLEFT = (
        '"It is him should close the gate when the storm starts; and until then '
        'we will warn the guard, if we have to mark the door with chalk."'
    )
    NARRATIVE_RULE = "dialogue_structural_split_narrative_comparative"
    CLEFT_RULE = "dialogue_structural_semicolon_cleft_conditional"

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(
            Path(__file__).resolve().parents[1] / "data", cache_size=0,
        )
        cls.cases = select_cases(500)[0]

    def parse(self, case):
        prepared, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000, kbest_work_limit=500_000,
        )
        self.assertEqual(prepared.analysis_text, case["source_text"])
        self.assertEqual(lattice.text, case["source_text"])
        return prepared, lattice, result

    def source_result(self, index, rule):
        case = self.cases[index]
        witness = next(w for w in WITNESSES if w.index == index)
        self.assertEqual(
            f'{case["book_id"]}:' + sha256(case["source_text"].encode()).hexdigest()[:16],
            witness.case_id,
        )
        prepared, lattice, result = self.parse(case)
        best = self.assert_rule(result, rule)
        self.assertEqual((best.start, best.end), (0, len(prepared.source_text)))
        self.assertFalse(result.stats.get("budget_exceeded"))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))
        return prepared, lattice, best

    def control(self, source):
        rows, _ = extract(
            Book(999, "Synthetic", "Test", "train"), source,
            length_min=1, length_max=100,
        )
        self.assertEqual([row["source_text"] for row in rows], [source])
        return self.parse(rows[0])[2]

    def assert_rule(self, result, rule):
        self.assertTrue(result.completed, result.stats)
        best = result.best()
        self.assertIsNotNone(best)
        self.assertEqual(best.rule_id, rule)
        return best

    def children(self, node, text, expected):
        self.assertEqual(
            [(child.category, text[child.start:child.end]) for child in node.children],
            expected,
        )

    def test_actual_96_preserves_narrator_and_comparison_scope(self):
        prepared, _, best = self.source_result(96, self.NARRATIVE_RULE)
        text = prepared.source_text
        self.children(best, text, [
            ("OPEN-QUOTE", "‘"), ("SPOKEN-ADDRESS", "Now, David"),
            ("COMMA", ","), ("CLOSE-QUOTE", "’"),
            ("SPEECH-TAG", "he said"),
            ("NARRATIVE-ASIDE", "--and I saw that cast again as he said it--"),
            ("OPEN-QUOTE", "‘"),
            ("CLAUSE", "you must be far more careful today than usual"),
            ("SPEECH-STOP", "."), ("CLOSE-QUOTE", "’"),
        ])
        self.assertEqual(best.children[1].children[-1].children[0].rule_id, "np_proper")
        self.assertEqual(best.children[4].children[0].rule_id, "dialogue_speech_tag_post")
        aside = best.children[5]
        self.children(aside, text, [
            ("DASH", "--"), ("COORD", "and"), ("CLAUSE", "I saw that cast again"),
            ("TEMPORAL-CLAUSE", "as he said it"), ("DASH", "--"),
        ])
        self.assertEqual(prepared.source_component("pa0"), text[aside.start + 2:aside.end - 2])
        narrator = aside.children[2].children[0]
        self.assertEqual(narrator.children[1].rule_id, "vp_adv")
        self.assertEqual(narrator.children[1].children[0].children[1].rule_id, "np_det_n")
        temporal = aside.children[3]
        self.assertEqual(temporal.children[0].features.as_dict()["simultaneous"], "true")
        self.assertEqual(temporal.children[1].children[0].children[1].rule_id, "vp_transitive")
        self.children(best.children[7], text, [
            ("NP", "you"), ("MODAL", "must"),
            ("VP-NP", "be far more careful today than usual"),
        ])
        predicate = best.children[7].children[2]
        self.children(predicate, text, [
            ("COPULA", "be"), ("ADJP", "far more careful"),
            ("ADV", "today"), ("COMPARATIVE-STANDARD", "than usual"),
        ])
        self.children(predicate.children[1], text, [
            ("ADV", "far"), ("DEGREE", "more"), ("ADJ", "careful"),
        ])

    def test_actual_495_preserves_focused_subject_and_conditional_scope(self):
        prepared, lattice, best = self.source_result(495, self.CLEFT_RULE)
        text = prepared.source_text
        self.assertEqual([child.category for child in best.children],
                         ["OPEN-QUOTE", "CLAUSE", "SEMICOLON", "COORD", "CLAUSE",
                          "SPEECH-STOP", "CLOSE-QUOTE"])
        first, second = best.children[1], best.children[4]
        self.children(first, text, [
            ("PRONOUN", "It"), ("COPULA", "'s"), ("PRONOUN", "us"),
            ("VP", "must break the treaty when the time comes"),
        ])
        self.assertEqual(first.children[2].features.as_dict()["case"], "accusative")
        self.children(first.children[3], text, [
            ("MODAL", "must"), ("V", "break"), ("NP", "the treaty"),
            ("TEMPORAL-CLAUSE", "when the time comes"),
        ])
        self.children(second, text, [
            ("PP", "till then"), ("NP", "I"), ("MODAL", "'ll"), ("V", "gammon"),
            ("NP", "that doctor"), ("COMMA", ","),
            ("CONDITIONAL-CLAUSE", "if I have to ile his boots with brandy"),
        ])
        condition = second.children[-1]
        self.children(condition, text, [
            ("CONJ", "if"), ("NP", "I"), ("HAVE", "have"),
            ("TO-VP", "to ile his boots with brandy"),
        ])
        self.assertEqual(condition.children[2].features.as_dict()["person"], "1")
        self.children(condition.children[-1], text, [
            ("TO", "to"), ("V", "ile"), ("NP", "his boots"), ("PP", "with brandy"),
        ])
        self.assertEqual(condition.children[-1].children[2].children[0].rule_id, "np_poss")
        self.assertEqual(condition.children[-1].children[3].children[0].rule_id, "pp_prep_np")
        self.assertTrue({"N", "V"} <= {
            c.category for c in lattice.candidates if c.surface == "gammon"
        })

    def test_independent_interrupted_quote_with_em_dashes(self):
        tree = self.assert_rule(self.control(self.NARRATIVE), self.NARRATIVE_RULE)
        self.assertEqual(tree.children[5].category, "NARRATIVE-ASIDE")
        comparative = tree.children[7].children[2]
        self.children(comparative, self.NARRATIVE, [
            ("COPULA", "be"), ("ADJP", "much more cautious"),
            ("ADV", "tomorrow"), ("COMPARATIVE-STANDARD", "than usual"),
        ])

    def test_independent_cleft_with_plural_and_singular_have_to(self):
        for text in (self.CLEFT, self.CLEFT.replace(
            "we will warn the guard, if we have", "he will warn the guard, if he has",
        )):
            with self.subTest(source=text):
                tree = self.assert_rule(self.control(text), self.CLEFT_RULE)
                self.assertEqual(tree.children[4].children[-1].category, "CONDITIONAL-CLAUSE")

    def test_comparative_requires_degree_and_paired_source_dashes(self):
        for text in (
            self.NARRATIVE.replace("much more", "much very"),
            self.NARRATIVE.replace("spoke—", "spoke--"),
        ):
            with self.subTest(source=text):
                result = self.control(text)
                self.assertNotEqual(result.stats.get("structural_composition_kind"),
                                    self.NARRATIVE_RULE)

    def test_cleft_conditional_keeps_case_agreement_and_material_valency(self):
        for text in (
            self.CLEFT.replace("we will warn the guard, if we have",
                               "he will warn the guard, if he have"),
            self.CLEFT.replace("if we have", "if us have"),
            self.CLEFT.replace("mark the door", "discuss the door"),
            self.CLEFT.replace("him should", "him who should"),
        ):
            with self.subTest(source=text):
                result = self.control(text)
                self.assertNotEqual(result.stats.get("structural_composition_kind"),
                                    self.CLEFT_RULE)

class NestedTemporalComparativeTests(unittest.TestCase):
    RULE = "dialogue_structural_nested_temporal_comparative"
    CONTROL = (
        '“‘When you, who treat him so much worse than he has ever deserved, '
        'even when he was young, read the letter, we will be very tired.’”'
    )

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(
            Path(__file__).resolve().parents[1] / "data", cache_size=0,
        )

    def parse(self, case):
        return parse_corpus_case(
            self.parser, case, max_items=50_000, kbest_work_limit=500_000,
        )

    def control(self, text):
        rows, _ = extract(Book(999, "Synthetic", "Test", "train"), text,
                          length_min=1, length_max=100)
        self.assertEqual([row["source_text"] for row in rows], [text])
        return self.parse(rows[0])[2]

    def children(self, node, text, expected):
        self.assertEqual(
            [(child.category, text[child.start:child.end]) for child in node.children],
            expected,
        )

    def test_actual_109_preserves_nested_quotes_and_selected_attachments(self):
        case = select_cases(500)[0][109]
        text = case["source_text"]
        witness = next(w for w in WITNESSES if w.index == 109)
        self.assertEqual(
            f'{case["book_id"]}:' + sha256(text.encode()).hexdigest()[:16],
            witness.case_id,
        )
        prepared, lattice, result = self.parse(case)
        self.assertEqual(prepared.analysis_text, text)
        self.assertEqual(lattice.text, text)
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats.get("budget_exceeded"))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))
        best = result.best()
        self.assertEqual(best.rule_id, self.RULE)
        self.assertEqual((best.start, best.end), (0, len(text)))
        outer_open, inner, outer_close = best.children
        self.assertEqual((text[outer_open.start], text[outer_close.start]), ("‘", "’"))
        self.assertEqual(text[inner.start:inner.end], prepared.source_component("q1"))
        self.assertEqual([node.category for node in inner.children],
                         ["OPEN-QUOTE", "TEMPORAL-CLAUSE", "COMMA", "CLAUSE",
                          "SPEECH-STOP", "CLOSE-QUOTE"])
        temporal, matrix = inner.children[1], inner.children[3]
        self.assertEqual(text[matrix.start:matrix.end], "I shall be far away")
        self.assertEqual(matrix.children[0].rule_id, "clause_np_vp")
        self.assertEqual(matrix.children[0].children[1].rule_id, "vp_modal_bare")
        self.children(temporal, text, [
            ("CONJ", "When"),
            ("NP", "you, who love me so much better than I ever have deserved, "
                   "even when my mind was innocent,"),
            ("V", "see"), ("NP", "this"),
        ])
        subject, see, demonstrative = temporal.children[1:]
        self.assertEqual(see.features.as_dict()["person"], "2")
        self.assertEqual(demonstrative.children[0].rule_id, "np_demonstrative")
        self.assertEqual([node.category for node in subject.children],
                         ["NP", "COMMA", "REL-CLAUSE-SUBJ", "COMMA"])
        relative = subject.children[2]
        self.children(relative, text, [
            ("WH-PRONOUN", "who"), ("V", "love"), ("PRONOUN", "me"),
            ("ADVP", "so much better than I ever have deserved, "
                     "even when my mind was innocent"),
        ])
        self.assertEqual(relative.children[1].features.as_dict()["person"], "2")
        comparison = relative.children[3]
        self.assertEqual([node.category for node in comparison.children],
                         ["DEGREE", "ADV", "ADV", "COMPARATIVE-STANDARD"])
        standard = comparison.children[-1]
        self.children(standard, text, [
            ("PREP", "than"), ("CLAUSE", "I ever have deserved"), ("COMMA", ","),
            ("TEMPORAL-CLAUSE", "even when my mind was innocent"),
        ])
        gap = standard.children[1].children[1]
        self.assertEqual(gap.features.as_dict()["comparative_gap"], "object")
        self.assertEqual(gap.features.as_dict()["aspect"], "perfect")
        self.children(gap, text, [("ADV", "ever"), ("HAVE", "have"), ("V", "deserved")])
        self.assertEqual(gap.children[1].features.as_dict()["person"], "1")
        self.assertEqual(gap.children[-1].features.as_dict()["vform"], "ed")
        self.children(standard.children[3], text, [
            ("ADV", "even"), ("TEMPORAL-CLAUSE", "when my mind was innocent"),
        ])

    def test_independent_comparison_accepts_both_source_adverb_orders(self):
        for text, order in (
            (self.CONTROL, ["HAVE", "ADV", "V"]),
            (self.CONTROL.replace("he has ever deserved", "we ever have earned"),
             ["ADV", "HAVE", "V"]),
        ):
            with self.subTest(text=text):
                result = self.control(text)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, self.RULE)
                relative = result.best().children[1].children[1].children[1].children[2]
                standard = relative.children[-1].children[-1].children[1]
                self.assertEqual([n.category for n in standard.children[1].children], order)

    def test_relative_and_temporal_predicates_agree_with_the_address(self):
        for old, new in (("who treat", "who treats"), ("read the letter", "reads the letter"),
                         ("who treat", "whom treat")):
            with self.subTest(new=new):
                result = self.control(self.CONTROL.replace(old, new))
                self.assertNotEqual(result.stats.get("structural_composition_kind"), self.RULE)

    def test_standard_requires_agreeing_have_transitive_participle_and_commas(self):
        for old, new in (
            ("he has", "he have"), ("has ever deserved", "has ever deserve"),
            ("has ever deserved", "has ever existed"), ("young, read", "young read"),
        ):
            with self.subTest(new=new):
                result = self.control(self.CONTROL.replace(old, new))
                self.assertNotEqual(result.stats.get("structural_composition_kind"), self.RULE)


if __name__ == "__main__":
    unittest.main()
