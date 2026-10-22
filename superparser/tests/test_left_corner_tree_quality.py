"""Known quality gaps exposed when a formerly capped forest becomes complete.

These are NOT extra corpus-specific grammar rules. They are adversarial tree
acceptance tests, all through Parser.parse, documenting what must be fixed
before the left-corner feasibility optimization becomes the default.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser import Parser

DATA = Path(__file__).resolve().parents[1] / "data"


def descendants(node):
    yield node
    for child in node.children:
        yield from descendants(child)


class ExperimentalTreeQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(
            DATA, cache_size=0, lexical_left_corner_pruning=True,
        )

    @unittest.expectedFailure
    def test_verb_particle_not_reinterpreted_as_second_imperative(self):
        text = (
            "As soon as the sun had climbed above our girdle of trees, "
            "it fell with all its force upon the clearing and drank up "
            "the vapours at a draught."
        )
        best = self.parser.parse(text, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertFalse(any(
            item.rule_id == "clause_imperative"
            and text[item.start:item.end].startswith("up the vapours")
            for item in descendants(best)
        ), "In an indicative narrative, 'drank up' is one verb-particle unit")

    @unittest.expectedFailure
    def test_object_topicalization_does_not_absorb_subject_pronoun(self):
        text = (
            "“The turn of your countenance I shall never forget, as you said "
            "that I could not have addressed you in any possible way that "
            "would induce you to accept me.”"
        )
        best = self.parser.parse(text, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertFalse(any(
            item.category == "NP"
            and text[item.start:item.end].endswith(" I")
            and text[item.start:item.end].startswith("The turn")
            for item in descendants(best)
        ), "The subject 'I' must not be part of the fronted object NP")

    def test_for_my_part_is_prepositional_adjunct_not_coordination(self):
        text = (
            "For my part, as I was not much use at carrying, I was kept "
            "busy all day in the cave packing the minted money into bread-bags."
        )
        best = self.parser.parse(text, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertNotEqual(best.rule_id, "coord_clause",
                            "'For my part' is a PP, not a clausal coordinator")

    def test_copular_predicate_not_detached_into_dislocated_np(self):
        text = (
            "but while Peggotty’s eyes were full of compassion for him, "
            "she said his generous impulse would do him good, "
            "and it was better not to check it."
        )
        best = self.parser.parse(text, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertFalse(any(
            item.rule_id == "clause_cop_ellipsis"
            and text[item.start:item.end].endswith("eyes were")
            for item in descendants(best)
        ), "The predicative ADJP 'full ...' belongs to the copular clause")
        self.assertTrue(any(
            item.rule_id == "vp_cop_adjp"
            and text[item.start:item.end].startswith("were full")
            for item in descendants(best)
        ), "The explicit copula and its ADJP must form one selected predicate")


    @unittest.expectedFailure
    def test_tough_movement_requires_an_eligible_adjective(self):
        """A merely ADJ reading does not license every tough infinitive."""
        sentence = "The wall is green to believe."
        best = self.parser.parse(sentence, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertFalse(any(
            node.rule_id == "vp_tough" for node in descendants(best)
        ), "Green is not a lexically licensed tough-movement predicate")

    @unittest.expectedFailure
    def test_subject_control_infinitive_not_mislabeled_as_tough_movement(self):
        """'Ready to leave' is subject control, not object-gap tough syntax."""
        sentence = "Mary is ready to leave."
        best = self.parser.parse(sentence, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertFalse(any(
            node.rule_id == "vp_tough" for node in descendants(best)
        ), "The subject of 'leave' is Mary, not a gap object of 'leave'")


if __name__ == "__main__":
    unittest.main()
