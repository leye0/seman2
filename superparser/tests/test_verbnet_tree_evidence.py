"""Tests of post-parse VerbNet evidence: positive, bounded, non-rejecting."""
from dataclasses import dataclass, field
import unittest

from research.verbnet_lr.compiler import Frame, PrefixIndex
from research.verbnet_lr.tree_evidence import observe_vp_frames


@dataclass
class Node:
    category: str
    children: tuple["Node", ...] = ()
    lexical_candidate: object | None = None
    rule_id: str | None = None


@dataclass
class Candidate:
    lemma: str
    surface: str
    category: str = "V"
    sense_ids: tuple[str, ...] = ("wn-1234567-v-finite",)


def index():
    return PrefixIndex((
        Frame("give", "give-13.1", "dative",
              (("NP",), ("NP",)), ("Recipient", "Theme"),
              ("give%2:40:00",), (1234567,), "exact"),
        Frame("give", "give-13.1", "to_pp",
              (("NP",), ("PREP:to",), ("NP",)),
              ("Theme", "", "Recipient"),
              ("give%2:40:00",), (1234567,), "exact"),
    ))


class TestTreeEvidence(unittest.TestCase):
    def test_ditransitive_frame(self):
        tree = Node("CLAUSE", (Node("VP", (
            Node("V", lexical_candidate=Candidate("give", "gave")),
            Node("NP"), Node("NP")), rule_id="vp_ditransitive"),))
        observations = observe_vp_frames(tree, index())
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].status, "ATTESTED")
        self.assertEqual(observations[0].events, ("NP", "NP"))
        self.assertEqual(observations[0].confidence, "sense_verified")

    def test_explicit_preposition(self):
        pp = Node("PP", (Node("PREP", lexical_candidate=Candidate("to", "to", "PREP")),
                         Node("NP")))
        vp = Node("VP", (Node("V", lexical_candidate=Candidate("give", "gave")),
                         Node("NP"), pp), rule_id="vp_transitive_pp")
        self.assertEqual(observe_vp_frames(vp, index())[0].events,
                         ("NP", "PREP:to", "NP"))

    def test_passive_and_copula_are_not_mapped_to_active_frames(self):
        passive = Node("VP", (Node("AUX-BE"),
                              Node("V", lexical_candidate=Candidate("give", "given"))),
                       rule_id="vp_passive")
        copula = Node("VP", (Node("COPULA"), Node("ADJP")), rule_id="vp_cop_adjp")
        self.assertEqual(observe_vp_frames(Node("CLAUSE", (passive, copula)), index()), ())

    def test_unsupported_attachment_is_not_silently_dropped(self):
        vp = Node("VP", (Node("V", lexical_candidate=Candidate("give", "gave")),
                         Node("NP"), Node("PP", (Node("ADV"), Node("NP")))))
        self.assertEqual(observe_vp_frames(vp, index()), ())

    def test_wrong_wordnet_sense_is_unknown(self):
        vp = Node("VP", (Node("V", lexical_candidate=Candidate(
            "give", "gave", sense_ids=("wn-111-v-finite",))), Node("NP"), Node("NP")))
        observation = observe_vp_frames(vp, index())[0]
        self.assertEqual(observation.status, "UNKNOWN")
        self.assertEqual(observation.confidence, "none")


if __name__ == "__main__":
    unittest.main()
