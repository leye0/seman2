"""Isolated construction-morphology checks; no pytest or production parser."""
from dataclasses import dataclass
import unittest

from research.verbnet_lr.construction_guard import ConstructionGuard


@dataclass
class C:
    surface: str
    category: str
    lemma: str
    features: dict


@dataclass
class Node:
    category: str
    children: tuple = ()
    candidate: object = None
    rule: object = None


def leaf(surface, category, lemma=None, **features):
    return Node(category, candidate=C(surface, category, lemma or surface.lower(), features))


def clause(sub, verb, complement=None):
    vp = Node("VP", tuple([verb] + ([complement] if complement else [])))
    return Node("CLAUSE", (sub, vp))


def nominal(det, noun, number):
    return Node("NP", (leaf(det, "DET"), leaf(noun, "N", number=number)))


class TestConstructionGuard(unittest.TestCase):
    def setUp(self):
        self.guard = ConstructionGuard()

    def check(self, node):
        return self.guard.validate(node).acceptable

    def test_be_agreement_closed_paradigm(self):
        sub = nominal("The", "boy", "singular")
        self.assertFalse(self.check(clause(sub, leaf("are", "COPULA", "be"))))
        self.assertTrue(self.check(clause(sub, leaf("is", "COPULA", "be"))))
        plural = nominal("The", "books", "plural")
        self.assertFalse(self.check(clause(plural, leaf("is", "COPULA", "be"))))
        self.assertTrue(self.check(clause(plural, leaf("are", "COPULA", "be"))))

    def test_modal_base_form(self):
        he = Node("NP", (leaf("She", "PRONOUN"),))
        vp_bad = Node("VP", (leaf("should", "MODAL"), leaf("goes", "V", "go")))
        vp_good = Node("VP", (leaf("should", "MODAL"), leaf("go", "V", "go")))
        self.assertFalse(self.check(Node("CLAUSE", (he, vp_bad))))
        self.assertTrue(self.check(Node("CLAUSE", (he, vp_good))))

    def test_do_support_base_form(self):
        she = Node("NP", (leaf("She", "PRONOUN"),))
        bad = Node("CLAUSE", (she, leaf("did", "AUX", "do"),
                              leaf("not", "NEG"), Node("VP", (leaf("opened", "V", "open"),))))
        good = Node("CLAUSE", (she, leaf("did", "AUX", "do"),
                               leaf("not", "NEG"), Node("VP", (leaf("open", "V", "open"),))))
        self.assertFalse(self.check(bad))
        self.assertTrue(self.check(good))

    def test_determiner_nominal_agreement(self):
        self.assertFalse(self.check(nominal("A", "cats", "plural")))
        self.assertTrue(self.check(nominal("The", "cats", "plural")))
        self.assertTrue(self.check(nominal("A", "cat", "singular")))

    def test_non_determiner_homograph_does_not_invent_agreement(self):
        malformed = Node("NP", (leaf("These", "PROPER-NOUN"),
                                leaf("small", "N", number="singular")))
        self.assertTrue(self.check(malformed))

    def test_nonbase_surface_cannot_be_lexically_base(self):
        self.assertFalse(self.check(leaf("did", "V", "do", vform="base")))
        self.assertTrue(self.check(leaf("do", "V", "do", vform="base")))

    def test_open_class_present_s_vs_plural(self):
        plural = nominal("The", "children", "plural")
        self.assertFalse(self.check(clause(plural, leaf("plays", "V", "play"))))
        self.assertTrue(self.check(clause(plural, leaf("play", "V", "play"))))
        self.assertTrue(self.check(clause(plural, leaf("played", "V", "play"))))


if __name__ == "__main__":
    unittest.main()
