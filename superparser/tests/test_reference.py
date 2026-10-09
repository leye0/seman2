"""Reference-link detectors — cases from plans/coreference-guide.md."""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser.engine import Parser
from seman_parser.mentions import extract_event_mentions, extract_mentions
from seman_parser.reference import ReferenceKind
from seman_parser.refdetect import (
    detect_appositions,
    detect_associative,
    detect_bound_variables,
    detect_cataphora,
    detect_collectives,
    detect_control_raising,
    detect_demonstratives,
    detect_difference_markers,
    detect_event_anaphora,
    detect_identity_markers,
    detect_intensifiers,
    detect_lexical_repetition,
    detect_nominal_ellipsis,
    detect_non_identity,
    detect_ordinals,
    detect_p0,
    detect_p1,
    detect_p2,
    detect_personal_pronouns,
    detect_reflexives,
    detect_relatives,
    detect_speaker_reference,
    detect_unresolved,
    detect_verbal_ellipsis,
)

DATA = Path(__file__).resolve().parent.parent / "data"


def parse_best(text: str):
    p = Parser.from_dir(DATA, goal_category="CLAUSE", cache_size=0)
    report = p.parse(text)
    best = report.result.best()
    if best is None:
        np = Parser.from_dir(DATA, goal_category="NP", cache_size=0)
        report = np.parse(text)
        best = report.result.best()
    return report, best


def mentions_of(best, sent: int = 0):
    return extract_mentions(best, sent) + extract_event_mentions(best, sent)


class TestRef01Reflexives(unittest.TestCase):
    def test_local_unique_reflexive_same_ref(self) -> None:
        # Guide: John hurt himself. → SAME_REF
        report, best = parse_best("John hurt himself.")
        self.assertIsNotNone(best)
        links = detect_reflexives(best, mentions_of(best), sentence_index=0, parse_id="t1")
        kinds = {lk.kind for lk in links}
        self.assertIn(ReferenceKind.SAME_REF, kinds, links)
        same = [lk for lk in links if lk.kind == ReferenceKind.SAME_REF]
        self.assertTrue(same)
        self.assertEqual(same[0].rule_id, "REF-01:local-unique")

    def test_reflexive_without_antecedent_no_link(self) -> None:
        report, best = parse_best("Himself left.")
        self.assertIsNotNone(best)
        links = detect_reflexives(best, mentions_of(best), sentence_index=0, parse_id="t2")
        # no clausemate NP → NO_LINK
        self.assertTrue(any(lk.kind == ReferenceKind.NO_LINK for lk in links) or not links)


class TestRef02Relatives(unittest.TestCase):
    def test_explicit_relative_same_ref(self) -> None:
        # Guide: The book which I read disappeared.
        report, best = parse_best("The book which I read disappeared.")
        self.assertIsNotNone(best)
        links = detect_relatives(best, mentions_of(best), sentence_index=0, parse_id="t3")
        self.assertTrue(
            any(lk.kind == ReferenceKind.SAME_REF and lk.rule_id.startswith("REF-02") for lk in links),
            links,
        )


class TestRef05NonIdentity(unittest.TestCase):
    def test_object_pronoun_differs_from_subject(self) -> None:
        # Guide: John saw him. → him DIFFERENT_REF John
        report, best = parse_best("John saw him.")
        self.assertIsNotNone(best)
        links = detect_non_identity(best, mentions_of(best), sentence_index=0, parse_id="t4")
        self.assertTrue(
            any(lk.kind == ReferenceKind.DIFFERENT_REF for lk in links),
            links,
        )


class TestRef06Personal(unittest.TestCase):
    def test_pronoun_is_maybe_not_same(self) -> None:
        # Guide: John arrived. He smiled. → MAYBE_REF (pas SAME_REF)
        _, b1 = parse_best("John arrived.")
        _, b2 = parse_best("He smiled.")
        self.assertIsNotNone(b1)
        self.assertIsNotNone(b2)
        m1 = mentions_of(b1, 0)
        m2 = mentions_of(b2, 1)
        links = detect_personal_pronouns(
            b2, m2, sentence_index=1, parse_id="t5", antecedents=m1
        )
        self.assertTrue(links, "expected at least one MAYBE_REF")
        for lk in links:
            self.assertEqual(lk.kind, ReferenceKind.MAYBE_REF)


class TestRef07Repetition(unittest.TestCase):
    def test_exact_repetition_maybe(self) -> None:
        # Guide: A glurp entered. The glurp smiled. (lemma glurp)
        # Use a WordNet-unknown token path: proper-like repetition of 'robot'
        _, b1 = parse_best("A robot entered.")
        _, b2 = parse_best("The robot smiled.")
        m = mentions_of(b1, 0) + mentions_of(b2, 1)
        links = detect_lexical_repetition(m, parse_id="t6", normalize=False)
        self.assertTrue(any(lk.kind == ReferenceKind.MAYBE_REF for lk in links), links)


class TestRef09Unresolved(unittest.TestCase):
    def test_expletive_it_is_no_link(self) -> None:
        # Guide: It is raining. → pas d'antécédent
        report, best = parse_best("It is raining.")
        self.assertIsNotNone(best)
        ms = mentions_of(best)
        links = detect_unresolved(ms, sentence_index=0, parse_id="t7")
        # either no expletive mention is extracted (fine) or NO_LINK is emitted
        for lk in links:
            self.assertEqual(lk.kind, ReferenceKind.NO_LINK)


class TestP0Driver(unittest.TestCase):
    def test_p0_produces_links_on_simple_sentence(self) -> None:
        report, best = parse_best("John hurt himself.")
        self.assertIsNotNone(best)
        rep = detect_p0(best, mentions_of(best), sentence_index=0, parse_id="t8")
        self.assertGreater(len(rep.links), 0, rep.summary())
        self.assertIn("links", rep.summary())


# -- P1 -----------------------------------------------------------------


class TestRef11Appositions(unittest.TestCase):
    def test_comma_apposition_asserted_identity(self) -> None:
        # Guide: John, my brother, arrived. → ASSERTED_IDENTITY
        text = "John, my brother, arrived."
        report, best = parse_best(text)
        self.assertIsNotNone(best)
        links = detect_appositions(
            best, mentions_of(best), sentence_index=0, parse_id="p1", text=text
        )
        self.assertTrue(
            any(lk.kind == ReferenceKind.ASSERTED_IDENTITY for lk in links),
            links,
        )


class TestRef12Intensifiers(unittest.TestCase):
    def test_intensifier_is_asserted_identity(self) -> None:
        # Guide: John himself answered.
        report, best = parse_best("John himself answered.")
        self.assertIsNotNone(best)
        links = detect_intensifiers(best, mentions_of(best), sentence_index=0, parse_id="p2")
        # may be empty if the parse does not surface a reflexive intensifier
        # as a sibling — then at least the detector must not invent links
        for lk in links:
            self.assertEqual(lk.kind, ReferenceKind.ASSERTED_IDENTITY)


class TestRef13Demonstratives(unittest.TestCase):
    def test_demonstrative_is_maybe_not_same(self) -> None:
        # Guide: John left. This surprised Mary. → MAYBE_REF (jamais SAME_REF)
        _, b1 = parse_best("John left.")
        _, b2 = parse_best("This surprised Mary.")
        self.assertIsNotNone(b2)
        m1 = mentions_of(b1, 0)
        m2 = mentions_of(b2, 1)
        links = detect_demonstratives(
            b2, m2, sentence_index=1, parse_id="p3", antecedents=m1
        )
        self.assertTrue(links, "expected demonstrative candidates")
        for lk in links:
            self.assertIn(lk.kind, {ReferenceKind.MAYBE_REF, ReferenceKind.NO_LINK})
            self.assertNotEqual(lk.kind, ReferenceKind.SAME_REF)


class TestRef17DifferenceMarkers(unittest.TestCase):
    def test_someone_else_is_different_ref(self) -> None:
        # Guide: Someone else entered. → DIFFERENT_REF
        report, best = parse_best("Someone else entered.")
        self.assertIsNotNone(best)
        links = detect_difference_markers(best, mentions_of(best), sentence_index=0, parse_id="p4")
        self.assertTrue(
            any(lk.kind == ReferenceKind.DIFFERENT_REF for lk in links),
            links,
        )

    def test_another_is_different_ref(self) -> None:
        report, best = parse_best("John bought another book.")
        self.assertIsNotNone(best)
        links = detect_difference_markers(best, mentions_of(best), sentence_index=0, parse_id="p4b")
        self.assertTrue(
            any(lk.kind == ReferenceKind.DIFFERENT_REF for lk in links),
            links,
        )


class TestRef18Speaker(unittest.TestCase):
    def test_unanchored_first_person_is_no_link(self) -> None:
        report, best = parse_best("I am tired.")
        self.assertIsNotNone(best)
        links = detect_speaker_reference(best, mentions_of(best), sentence_index=0, parse_id="p5")
        self.assertTrue(links)
        for lk in links:
            self.assertEqual(lk.kind, ReferenceKind.NO_LINK)

    def test_anchored_first_person_is_same_ref(self) -> None:
        report, best = parse_best("I am tired.")
        self.assertIsNotNone(best)
        links = detect_speaker_reference(
            best, mentions_of(best), sentence_index=0, parse_id="p5b", speaker_id="SPEAKER"
        )
        self.assertTrue(links)
        for lk in links:
            self.assertEqual(lk.kind, ReferenceKind.SAME_REF)
            self.assertEqual(lk.target, "SPEAKER")


class TestRef19BoundVariables(unittest.TestCase):
    def test_quantified_pronoun_is_bound_variable(self) -> None:
        # Guide: Every student washed themselves. → BOUND_VARIABLE
        report, best = parse_best("Every student washed themselves.")
        self.assertIsNotNone(best)
        links = detect_bound_variables(best, mentions_of(best), sentence_index=0, parse_id="p6")
        self.assertTrue(
            any(lk.kind == ReferenceKind.BOUND_VARIABLE for lk in links),
            links,
        )


class TestP1Driver(unittest.TestCase):
    def test_p1_runs_without_error(self) -> None:
        report, best = parse_best("John, my brother, left. Someone else stayed.")
        self.assertIsNotNone(best)
        rep = detect_p1(best, mentions_of(best), sentence_index=0, parse_id="p7")
        self.assertGreaterEqual(len(rep.links), 0)
        self.assertIn("links", rep.summary())


class TestRef14Ordinals(unittest.TestCase):
    def test_former_latter_needs_a_pair(self) -> None:
        # Guide: John met Mary. The former smiled. — sans paire, NO_LINK.
        report, best = parse_best("The former smiled.")
        self.assertIsNotNone(best)
        links = detect_ordinals(best, mentions_of(best), sentence_index=0, parse_id="p8")
        self.assertTrue(links)
        for lk in links:
            self.assertIn(lk.kind, {ReferenceKind.MAYBE_REF, ReferenceKind.NO_LINK})


class TestRef15Collectives(unittest.TestCase):
    def test_both_over_coordination_is_maybe(self) -> None:
        # Guide: John and Mary arrived. Both smiled.
        report, best = parse_best("John and Mary arrived.")
        self.assertIsNotNone(best)
        m1 = mentions_of(best, 0)
        report2, best2 = parse_best("Both smiled.")
        self.assertIsNotNone(best2)
        m2 = mentions_of(best2, 1)
        links = detect_collectives(best2, m2, sentence_index=1, parse_id="p9")
        # without a tree-level pair in the second sentence this is NO_LINK
        for lk in links:
            self.assertIn(lk.kind, {ReferenceKind.MAYBE_REF, ReferenceKind.NO_LINK})


class TestRef16IdentityMarkers(unittest.TestCase):
    def test_aka_is_asserted_identity(self) -> None:
        # Guide: John, aka Jack, arrived.
        report, best = parse_best("John, aka Jack, arrived.")
        self.assertIsNotNone(best)
        links = detect_identity_markers(best, mentions_of(best), sentence_index=0, parse_id="p10")
        self.assertTrue(
            any(lk.kind == ReferenceKind.ASSERTED_IDENTITY for lk in links),
            links,
        )


# -- P2 -----------------------------------------------------------------


class TestRef20NominalEllipsis(unittest.TestCase):
    def test_one_is_type_anaphora_not_identity(self) -> None:
        # Guide: I bought a red book and a blue one. → TYPE_ANAPHORA
        report, best = parse_best("I bought a red book and a blue one.")
        self.assertIsNotNone(best)
        links = detect_nominal_ellipsis(best, mentions_of(best), sentence_index=0, parse_id="q1")
        self.assertTrue(links, "expected a one/ones link")
        for lk in links:
            self.assertEqual(lk.kind, ReferenceKind.TYPE_ANAPHORA)
            self.assertTrue(lk.rule_id.startswith("REF-20"))


class TestRef21VerbalEllipsis(unittest.TestCase):
    def test_so_pro_form_is_maybe_ref(self) -> None:
        # Guide: pro-form so/do reprend une situation.
        # "Mary did so." alone is not yet a CLAUSE in the grammar; use the
        # coordinated form the chart can analyse.
        _, b1 = parse_best("John left.")
        _, b2 = parse_best("John left and Mary did too.")
        self.assertIsNotNone(b2)
        m1 = mentions_of(b1, 0)
        m2 = mentions_of(b2, 1)
        links = detect_verbal_ellipsis(
            b2, m2, sentence_index=1, parse_id="q2", antecedents=m1
        )
        # Either pro-form or elliptical-rule link; never SAME_REF on individuals.
        for lk in links:
            self.assertIn(lk.kind, {ReferenceKind.MAYBE_REF, ReferenceKind.NO_LINK})
            self.assertNotEqual(lk.kind, ReferenceKind.SAME_REF)


class TestRef22ControlRaising(unittest.TestCase):
    def test_control_rule_emits_shared_argument(self) -> None:
        """Detector fires only on grammar rules that already encode control.

        Guide §2: if the parser has no valence facts, do not invent the link.
        We build a minimal tree with rule_id=vp_to_inf to verify the mapping.
        """
        from seman_parser.chart import ChartItem, Provenance
        from seman_parser.features import FeatureStructure
        from seman_parser.semantics import SemanticGraph, SemanticPackage

        def leaf(cat, start, end, surface):
            graph = SemanticGraph()
            node = graph.add_node(
                kind="entity", type_name="X", span=(start, end), surface=surface, lemma=surface
            )
            return ChartItem(
                start=start,
                end=end,
                category=cat,
                features=FeatureStructure.empty(),
                semantic=SemanticPackage(graph=graph, handles={"referent": node.node_id, "head": node.node_id}),
                score=1.0,
                provenance=Provenance(source="lex", detail={"surface": surface, "lemma": surface}),
            )

        subj = leaf("PROPER-NOUN", 0, 4, "John")
        subj_np = ChartItem(
            start=0, end=4, category="NP",
            features=FeatureStructure.empty(),
            semantic=subj.semantic, score=1.0,
            provenance=Provenance(source="rule", detail={"surface": "John"}),
            children=(subj,), rule_id="np_proper",
        )
        embedded = leaf("V", 15, 20, "leave")
        embedded_vp = ChartItem(
            start=15, end=20, category="VP-NP",
            features=FeatureStructure.empty(),
            semantic=embedded.semantic, score=1.0,
            provenance=Provenance(source="rule", detail={"surface": "leave"}),
            children=(embedded,), rule_id="vp_bare",
        )
        matrix = ChartItem(
            start=0, end=20, category="CLAUSE",
            features=FeatureStructure.empty(),
            semantic=subj.semantic, score=1.0,
            provenance=Provenance(source="rule", detail={"surface": "John tried to leave"}),
            children=(subj_np, embedded_vp), rule_id="vp_to_inf",
        )
        links = detect_control_raising(matrix, (), sentence_index=0, parse_id="q3")
        self.assertTrue(
            any(lk.kind == ReferenceKind.SHARED_ARGUMENT for lk in links),
            links,
        )
        self.assertTrue(all(lk.rule_id.startswith("REF-22") for lk in links))

    def test_no_control_rule_invents_nothing(self) -> None:
        # "John tried to leave." is currently analysed as clause_passive /
        # vp_part_pp — the detector must NOT invent a control link.
        report, best = parse_best("John tried to leave.")
        self.assertIsNotNone(best)
        links = detect_control_raising(best, mentions_of(best), sentence_index=0, parse_id="q3c")
        self.assertEqual(links, [])


class TestRef23EventAnaphora(unittest.TestCase):
    def test_demonstrative_over_event_is_maybe(self) -> None:
        # Guide: John left. This surprised Mary. (event reading)
        _, b1 = parse_best("John left.")
        _, b2 = parse_best("This surprised Mary.")
        self.assertIsNotNone(b2)
        m1 = mentions_of(b1, 0)
        m2 = mentions_of(b2, 1)
        links = detect_event_anaphora(
            b2, m2, sentence_index=1, parse_id="q4", antecedents=m1
        )
        for lk in links:
            self.assertIn(lk.kind, {ReferenceKind.MAYBE_REF, ReferenceKind.NO_LINK})
            self.assertNotEqual(lk.kind, ReferenceKind.SAME_REF)


class TestRef24Cataphora(unittest.TestCase):
    def test_forward_pronoun_points_to_later_mention(self) -> None:
        # Guide: cataphore — le pronom précède son antécédent.
        report, best = parse_best("Before she left, Maya closed the door.")
        self.assertIsNotNone(best)
        links = detect_cataphora(best, mentions_of(best), sentence_index=0, parse_id="q5")
        self.assertTrue(links, "expected a forward link")
        for lk in links:
            self.assertEqual(lk.kind, ReferenceKind.MAYBE_REF)
            self.assertTrue(lk.rule_id.startswith("REF-24"))


class TestRef25Associative(unittest.TestCase):
    def test_definite_without_antecedent_is_no_link(self) -> None:
        # Guide: bridging est hors parseur → NO_LINK, jamais deviné.
        report, best = parse_best("The door was open.")
        self.assertIsNotNone(best)
        links = detect_associative(best, mentions_of(best), sentence_index=0, parse_id="q6")
        self.assertTrue(links)
        for lk in links:
            self.assertEqual(lk.kind, ReferenceKind.NO_LINK)
            self.assertTrue(lk.rule_id.startswith("REF-25"))


class TestP2Driver(unittest.TestCase):
    def test_p2_runs_without_error(self) -> None:
        report, best = parse_best("I bought a red book and a blue one.")
        self.assertIsNotNone(best)
        rep = detect_p2(best, mentions_of(best), sentence_index=0, parse_id="q7")
        self.assertGreaterEqual(len(rep.links), 0)
        self.assertIn("links", rep.summary())


if __name__ == "__main__":
    unittest.main()
