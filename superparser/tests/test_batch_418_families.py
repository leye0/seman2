"""Multi-case structural repairs after immutable 418/500 source baseline.

Never credit an ordinary surface acceptance without inspecting the selected
full-span rank-one tree and the actual corpus source. All three target cases
use the unchanged 50k/500k canonical corpus parse gateway.
"""
from __future__ import annotations
from pathlib import Path
import unittest

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser

DATA = Path(__file__).resolve().parents[1] / "data"


def descendants(node):
    yield node
    for child in node.children:
        yield from descendants(child)


class MultiFamily418Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)
        cls.cases = select_cases(500)[0]

    def case_result(self, index, expected):
        case = self.cases[index]
        self.assertEqual(case["source_text"], expected)
        prepared, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000,
            kbest_work_limit=500_000,
        )
        self.assertEqual(prepared.source_text, expected)
        self.assertEqual(prepared.analysis_text, expected)
        self.assertEqual(lattice.text, expected)
        self.assertEqual(result.text, expected)
        self.assertTrue(result.completed, (index, result.stats))
        self.assertIsNotNone(result.best())
        return result

    def assert_node(self, result, rule, span):
        root = result.best()
        nodes = [n for n in descendants(root) if n.rule_id == rule]
        self.assertTrue(nodes, (rule, result.stats))
        self.assertIn(span, [result.text[n.start:n.end] for n in nodes])
        return next(n for n in nodes if result.text[n.start:n.end] == span)

    def test_141_reflexive_agrees_with_subject_and_finite_predicate(self):
        text = "The envelope itself was likewise full."
        r = self.case_result(141, text)
        root = self.assert_node(
            r, "structural_emphatic_reflexive_subject_predicate", text,
        )
        self.assertEqual(
            [text[c.start:c.end] for c in root.children],
            ["The envelope", "itself", "was likewise full", "."],
        )
        self.assertEqual([c.category for c in root.children],
                         ["NP", "EMPHATIC-REFLEXIVE", "VP", "SPEECH-STOP"])
        self.assertEqual(root.children[0].children[0].rule_id, "np_det_n")
        self.assertEqual(root.children[2].children[0].rule_id,
                         "vp_copula_predicative_scope_adjective")
        self.assertEqual(r.stats["structural_composition_kind"],
                         "coreferential_emphatic_subject")
        self.assertEqual(r.stats["structural_segment_count"], 2)

    def test_301_lost_forever_is_postadjectival_temporal_predicate(self):
        text = "Is this gentle and lovely being lost forever?"
        r = self.case_result(301, text)
        clause = self.assert_node(
            r, "clause_yn_copular_adjp_question", text,
        )
        self.assertEqual([c.category for c in clause.children],
                         ["COPULA", "NP", "ADJP", "QMARK"])
        self.assertEqual(text[clause.children[1].start:clause.children[1].end],
                         "this gentle and lovely being")
        self.assertEqual(clause.children[1].rule_id,
                         "np_determiner_adjp_head")
        self.assertEqual(clause.children[2].rule_id, "adjp_adj_adv")
        self.assertEqual(
            [text[c.start:c.end] for c in clause.children[2].children],
            ["lost", "forever"],
        )
        self.assertEqual(
            clause.children[2].children[1].features.as_dict()
            .get("postadjectival"), "true",
        )

    def test_386_locative_fronting_with_stative_congregated_participle(self):
        text = "There all hands were already congregated."
        r = self.case_result(386, text)
        clause = self.assert_node(r, "clause_front_adv_nocomma", text[:-1])
        self.assertEqual([c.category for c in clause.children],
                         ["ADV", "CLAUSE"])
        self.assertEqual(text[clause.children[0].start:clause.children[0].end],
                         "There")
        sub = self.assert_node(r, "clause_np_vp",
                               "all hands were already congregated")
        self.assertEqual(text[sub.children[0].start:sub.children[0].end],
                         "all hands")
        pred = self.assert_node(
            r, "vp_copula_predicative_scope_adjective",
            "were already congregated",
        )
        self.assertEqual([text[c.start:c.end] for c in pred.children],
                         ["were", "already", "congregated"])
        self.assertEqual(pred.children[2].features.as_dict()
                         .get("stative_resultative"), "true")

    def test_52_exceptive_purpose_attaches_to_the_modal_wh_question(self):
        text = "Why should he go to India, except to harass me?"
        r = self.case_result(52, text)
        clause = self.assert_node(
            r, "clause_wh_modal_exceptive_infinitival_purpose", text,
        )
        self.assertEqual(
            [node.category for node in clause.children],
            ["WH-NOM", "MODAL", "NP", "VP-NP", "COMMA",
             "EXCEPTIVE", "TO", "VP-NP", "QMARK"],
        )
        self.assertEqual(
            [text[node.start:node.end] for node in clause.children],
            ["Why", "should", "he", "go to India", ",",
             "except", "to", "harass me", "?"],
        )
        self.assertEqual(clause.children[3].rule_id,
                         "vpnp_bare_prepositional_pp")
        self.assertEqual(clause.children[7].rule_id, "vp_bare_trans")
        self.assertEqual(
            clause.children[5].features.as_dict().get("exceptive_purpose"),
            "true",
        )

    def test_independent_productive_positive_controls(self):
        examples = (
            ("He himself was already ready.",
             "structural_emphatic_reflexive_subject_predicate"),
            ("The workers themselves were already ready.",
             "structural_emphatic_reflexive_subject_predicate"),
            ("Is the cottage empty forever?",
             "clause_yn_copular_adjp_question"),
            ("There the visitors were already congregated.",
             "clause_front_adv_nocomma"),
            ("Why would she go to Boston, except to visit him?",
             "clause_wh_modal_exceptive_infinitival_purpose"),
        )
        for text, rule in examples:
            with self.subTest(text=text):
                cases, _ = extract(
                    Book(999, "Grammar", "Test", "train"),
                    text, length_min=1, length_max=60,
                )
                self.assertEqual(len(cases), 1, text)
                _, _, result = parse_corpus_case(
                    self.parser, cases[0], max_items=50_000,
                    kbest_work_limit=500_000,
                )
                self.assertTrue(result.completed, (text, result.stats))
                self.assertTrue(
                    any(n.rule_id == rule for n in descendants(result.best())),
                    (text, rule),
                )

    def test_negative_agreement_and_lexical_licensing(self):
        examples = (
            ("He ourselves was already ready.",
             "structural_emphatic_reflexive_subject_predicate"),
            ("The workers himself were already ready.",
             "structural_emphatic_reflexive_subject_predicate"),
            ("Is the cottage empty quickly?",
             "adjp_adj_adv"),
            ("There the visitors were already laughed.",
             "vp_copula_predicative_scope_adjective"),
            ("Why would she go to Boston, unless to visit him?",
             "clause_wh_modal_exceptive_infinitival_purpose"),
        )
        for text, forbidden in examples:
            with self.subTest(text=text):
                cases, _ = extract(
                    Book(999, "Grammar", "Test", "train"),
                    text, length_min=1, length_max=60,
                )
                self.assertEqual(len(cases), 1, text)
                _, _, result = parse_corpus_case(
                    self.parser, cases[0], max_items=50_000,
                    kbest_work_limit=500_000,
                )
                for best in result.alternatives(limit=8):
                    for node in descendants(best):
                        if node.rule_id != forbidden:
                            continue
                        if forbidden == "adjp_adj_adv" and (
                                text[node.start:node.end] != "empty quickly"):
                            continue
                        if (forbidden ==
                                "vp_copula_predicative_scope_adjective"
                                and text[node.start:node.end] !=
                                "were already laughed"):
                            continue
                        self.fail(
                            f"Invalid {forbidden} licensed in {text}: "
                            f"{text[node.start:node.end]}"
                        )


if __name__ == "__main__":
    unittest.main()
