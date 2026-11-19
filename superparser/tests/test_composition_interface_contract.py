"""Splitting a constituent must not make the same rules less expressive."""
from __future__ import annotations

import os
import unittest
from dataclasses import replace
from pathlib import Path

from seman_parser.engine import Parser, ParserResources
from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.segmentation import LexicalCandidate, LexicalLattice, tokenize
from seman_parser.vector_chart import SegmentInterface, VectorGrammar


def symbol(category, requires=(), **features):
    return RuleSymbol(category, FeatureStructure.build(features), requires=requires)


HEAD = GrammarRule("predicate", (symbol("V", number="?n", vform="?v"),),
                   symbol("VP", number="?n", vform="?v"), score=2)
PARENT = GrammarRule(
    "subject_predicate",
    (symbol("NP", number="?n"), symbol("VP", ("number",), number="?n", vform="finite")),
    symbol("CLAUSE"), score=2,
)


def candidate(start, surface, category, score=0, **features):
    return LexicalCandidate(start, start + len(surface), surface, surface, category,
                            FeatureStructure.build(features), score=score)


def parse(text, candidates, rules, goal, *, k=8, work=500_000):
    return VectorGrammar(Grammar(rules)).parse_lattice(
        LexicalLattice(text, tuple(tokenize(text)), tuple(candidates)),
        beam=80, max_items=50_000, goal_category=goal, diagnostic_k=k, kbest_work_limit=work,
    )


def compare_flat_to_factored(local, *, visible=1, k=8):
    subject = candidate(0, "They", "NP", number="plural")
    part = parse("fish", local, [HEAD], "VP", k=visible)
    interface = LexicalCandidate(5, 9, "fish", "<VP>", "VP",
                                 part.best().features, score=part.best().score,
                                 interface=SegmentInterface(part, 5, 5, 9))
    assembled = parse("They fish", [subject, interface], [PARENT], "CLAUSE", k=k)
    flat = parse("They fish", [subject, *(replace(w, span_start=5, span_end=9) for w in local)],
                 [HEAD, PARENT], "CLAUSE", k=k)
    return part, assembled, flat


class CompositionInterfaceContractTests(unittest.TestCase):
    def test_parent_can_recover_after_three_different_rejections(self):
        # Locally valid choices include the wrong finiteness, missing
        # number evidence and conflicting number. None can certify the
        # enclosing clause even though it can be top-ranked as a VP.
        part, assembled, flat = compare_flat_to_factored([
            candidate(0, "fish", "V", 9, vform="base", number="plural"),
            candidate(0, "fish", "V", 8, vform="finite"),
            candidate(0, "fish", "V", 7, vform="finite", number="singular"),
            candidate(0, "fish", "V", 6, vform="finite", number="plural"),
        ])
        self.assertEqual(part.best().features.as_dict()["vform"], "base")
        self.assertTrue(flat.completed)
        self.assertTrue(assembled.completed)
        embedded = assembled.best().children[1].children[0]
        self.assertEqual(embedded.as_dict(), flat.best().children[1].as_dict())
        self.assertEqual((embedded.start, embedded.end), (5, 9))
        self.assertEqual(len(part.alternatives(limit=10)), 1)
        self.assertEqual(len(list(part.roots)), 1)
        self.assertEqual(len(part.roots[:10]), 1)
        with self.assertRaises(IndexError):
            part.roots[1]

    def test_incompatible_middle_rank_does_not_hide_lower_analyses(self):
        _, assembled, flat = compare_flat_to_factored([
            candidate(0, "fish", "V", 9, vform="finite", number="plural", reading="first"),
            candidate(0, "fish", "V", 8, vform="finite", number="singular"),
            candidate(0, "fish", "V", 7, vform="finite", number="plural", reading="second"),
        ], visible=8)
        self.assertEqual([r.score for r in flat.alternatives(limit=8)], [9, 7])
        self.assertEqual([r.score for r in assembled.alternatives(limit=8)], [9, 7])

    def test_parent_requires_positive_evidence_not_just_compatible_features(self):
        _, assembled, flat = compare_flat_to_factored([
            candidate(0, "fish", "V", 9, vform="finite"),
            candidate(0, "fish", "V", 8, vform="finite", number="singular"),
        ])
        self.assertFalse(flat.completed)
        self.assertFalse(assembled.completed)

    def test_impossible_evidence_request_does_not_enumerate_local_readings(self):
        local = [candidate(0, "fish", "V", score,
                           vform="finite", number="plural", reading=str(score))
                 for score in range(24)]
        part = parse("fish", local, [HEAD], "VP", k=1)
        interface = SegmentInterface(part, 5, 5, 9)
        packed = replace(candidate(5, "fish", "VP", score=part.best().score),
                         features=part.best().features, interface=interface)
        asks_for_gap = GrammarRule(
            "question_with_gap", (symbol("NP"), symbol("VP", ("object_gap",), object_gap="true")),
            symbol("CLAUSE"), score=2,
        )
        result = parse("They fish", [candidate(0, "They", "NP"), packed], [asks_for_gap], "CLAUSE")
        self.assertFalse(result.completed)
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        self.assertEqual(interface._items, {})

    def test_exhaustion_of_the_child_budget_is_not_an_accepted_parse(self):
        # Keep the best local result, but leave too little work to request
        # the next one. The parent must not accept the locally valid bare V.
        local = [
            candidate(0, "fish", "V", 9, vform="base", number="plural"),
            candidate(0, "fish", "V", 6, vform="finite", number="plural"),
        ]
        initial = parse("fish", local, [HEAD], "VP", k=1)
        part = parse("fish", local, [HEAD], "VP", k=1, work=initial.stats["kbest_work_units"])
        self.assertTrue(part.completed)
        interface = LexicalCandidate(5, 9, "fish", "<VP>", "VP",
                                     part.best().features, score=part.best().score,
                                     interface=SegmentInterface(part, 5, 5, 9))
        subject = candidate(0, "They", "NP", number="plural")
        assembled = parse("They fish", [subject, interface], [PARENT], "CLAUSE")
        self.assertFalse(assembled.completed)
        self.assertTrue(assembled.stats["kbest_budget_exceeded"])

    def test_lexical_constraints_still_apply_across_the_boundary(self):
        # A present-only bare stem cannot become third-person singular
        # simply because its lexical head was memoized before agreement.
        stem = replace(candidate(0, "swim", "V", vform="finite"),
                       excludes_third_singular=True)
        statement = GrammarRule(
            "finite_agreement",
            (symbol("NP", number="?n", person="?p"),
             symbol("V", vform="finite", number="?n", person="?p")),
            symbol("CLAUSE"), score=2,
        )
        result = parse("swim", [stem], [], "V")
        packed = replace(candidate(4, "swim", "V", vform="finite"),
                         interface=SegmentInterface(result, 4, 4, 8))
        subject = candidate(0, "She", "NP", number="singular", person="3")
        flat = parse("She swim", [subject, replace(stem, span_start=4, span_end=8)],
                     [statement], "CLAUSE")
        factored = parse("She swim", [subject, packed], [statement], "CLAUSE")
        self.assertFalse(flat.completed)
        self.assertFalse(factored.completed)

    def test_canonical_constructions_share_the_lexical_head_interface(self):
        dirname = os.environ.get("WORDNET_DICT")
        if not dirname:
            self.skipTest("WordNet 3.0 required for the canonical English lattice")
        data = Path(__file__).resolve().parents[1] / "data"
        parser = Parser(ParserResources.from_dir(data, wordnet_dict=Path(dirname)))

        def selected(lattice, goal, k):
            return parser._vector_grammar.parse_lattice(
                lattice, beam=80, max_items=50_000, kbest_work_limit=500_000,
                goal_category=goal, diagnostic_k=k,
            ).best()

        def at_span(item, span):
            if (item.start, item.end, item.category) == (*span, "V"):
                return item
            return next((node for child in item.children if (node := at_span(child, span))), None)

        for text, head in (
            ("They can read the book", "read"),
            ("They want to read the book", "read"),
            ("He did read the book", "read"),
            ("Read the book", "Read"),
            ("They can set the table", "set"),
        ):
            with self.subTest(text=text):
                start = text.index(head)
                end = start + len(head)
                lattice = parser._lattice_for_text(text)
                part = parser._vector_grammar.parse_lattice(
                    parser._lattice_for_text(head), beam=80, max_items=50_000,
                    kbest_work_limit=500_000, goal_category="V", diagnostic_k=1,
                )
                local = part.best()
                self.assertNotEqual(local.features.as_dict()["vform"], "base")
                interface = replace(
                    candidate(start, head, "V", score=local.score),
                    features=local.features, interface=SegmentInterface(part, start, start, end),
                )
                outside = tuple(c for c in lattice.candidates if c.span != (start, end))
                flat = selected(lattice, "CLAUSE", 8)
                factored = selected(replace(lattice, candidates=(interface, *outside)), "CLAUSE", 8)
                self.assertIsNotNone(factored)
                self.assertEqual(factored.rule_id, flat.rule_id)
                self.assertEqual(factored.syntax.anchors, flat.syntax.anchors)
                leaf = at_span(factored, (start, end))
                self.assertEqual(leaf.rule_id, "segment_interface")
                self.assertEqual(leaf.features.as_dict()["vform"], "base")
                self.assertEqual(leaf.children[0].as_dict(), at_span(flat, (start, end)).as_dict())
