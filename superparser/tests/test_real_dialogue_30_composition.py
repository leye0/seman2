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
