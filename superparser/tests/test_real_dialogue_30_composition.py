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
            self.assertEqual(result.best().rule_id,
                             "dialogue_structural_postposed_finite_clause_vocative")
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
        if result.completed:
            self.assertTrue(result.stats.get("structural_composition"), result.stats)
            self.assertEqual(
                result.best().rule_id,
                "dialogue_structural_intercalated_that_complement_vocative",
            )
            self.assertEqual(
                [child.category for child in result.best().children],
                ["OPEN-QUOTE", "CLAUSE", "COMMA", "NP", "COMMA",
                 "CLOSE-QUOTE", "SPEECH-TAG", "COMMA", "OPEN-QUOTE",
                 "COMP-THAT", "CLAUSE", "SPEECH-STOP", "CLOSE-QUOTE"],
            )
            self.assertEqual(result.stats["structural_clause_count"], 2)

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
                if expected and not result.stats.get("structural_composition"):
                    plan = QuotedSentenceComposer._intercalated_that_complement_plan(
                        source, rows[0]["structural_constituents"],
                    )
                    print("THAT_COMPOSITION_PLAN", plan, flush=True)
                    if plan:
                        for category, (a, b), grammar in (
                            ("CLAUSE", plan[0], self.parser._vector_grammar),
                            ("NP", plan[1], self.parser._vector_grammar),
                            ("SPEECH-TAG", plan[2], self.parser._dialogue_vector_grammar),
                            ("COMP-THAT", plan[3], self.parser._vector_grammar),
                            ("CLAUSE", plan[4], self.parser._vector_grammar),
                        ):
                            if category == "CLAUSE":
                                proof = self.parser._parse_vector_text(
                                    source[a:b], max_items=8333,
                                    kbest_work_limit=83333,
                                )
                            else:
                                proof = grammar.parse_lattice(
                                    self.parser._lattice_for_text(source[a:b]),
                                    goal_category=category, max_items=8333,
                                    kbest_work_limit=83333,
                                    beam=self.parser.beam,
                                )
                            best = proof.best()
                            print("THAT_COMPOSITION_PIECE", category, repr(source[a:b]),
                                  proof.completed, best.rule_id if best else None,
                                  [(ch.category, ch.rule_id, ch.features.as_dict(),
                                    [(n.category, n.rule_id, n.features.as_dict()) for n in ch.children])
                                   for ch in best.children] if best else None, flush=True)
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


if __name__ == "__main__":
    unittest.main()
