"""Shallow structural cohesion is a separate stage, not a second grammar."""
from __future__ import annotations

import unittest

from research.verbnet_lr.gutenberg_novels import Book, extract, analysis_units
from seman_parser.sentence_boundaries import (
    split_analysis_units, split_prose_sentences, split_prose_analysis_units,
)
from seman_parser.structural_units import (
    review_semicolon_boundaries, skeleton, source_unit_signals,
)

BOOK = Book(999, "attested structural controls", "research", "train")


class StructuralCohesionTests(unittest.TestCase):
    def test_real_fragments_have_explicit_reunification_evidence(self):
        cases = {
            "locative_nominal_ellipsis": (
                "On one side of the fire, sat my mother; on the other, Mr. Murdstone.",
                "contrasting_locative_nominal_ellipsis",
            ),
            "preposed_multi_pp": (
                "In her placid sisterly manner; with her beaming eyes; with her "
                "tender voice; and with that sweet composure, which had long ago "
                "made the house that held her quite a sacred place to me; she soon "
                "won me from this weakness, and led me on to tell all that had "
                "happened since our last meeting.",
                "preposed_adverbial_chain_with_matrix",
            ),
            "shared_modal_predicate": (
                "I returned to look at the old houses; and might think of the journey.",
                "coordinated_predicate_without_overt_subject",
            ),
            "participle_without_matrix": (
                "I deferred the explanation until then; merely informing her in my "
                "letters that I had much to tell her.",
                "nonfinite_supplement_without_matrix",
            ),
            "causal_for": (
                "All they wanted was a good watch and food; for, short of a complete "
                "surprise, they might have held the place against a regiment.",
                "causal_coordinator_refers_back",
            ),
            "coordinated_infinitive": (
                "I commanded him to order a meal; and to inquire about letters.",
                "coordinated_infinitive_without_overt_matrix",
            ),
            "parallel_farewell": (
                "Good-bye to the HISPANIOLA; good-bye to the squire, the doctor, "
                "and the captain!",
                "parallel_valediction",
            ),
            "source_relative": (
                "He promised to return; which he did.",
                "sentential_relative_antecedent",
            ),
        }
        for label, (source, expected) in cases.items():
            with self.subTest(label=label):
                decisions = review_semicolon_boundaries(source)
                self.assertTrue(decisions)
                self.assertTrue(all(decision.merge for decision in decisions))
                self.assertIn(expected, {decision.reason for decision in decisions})
                self.assertEqual([u.source_text for u in
                                  split_prose_analysis_units(source)], [source])
                raw = list(analysis_units(source))
                balanced = list(analysis_units(
                    source, balance_sentence_quotes=True))
                self.assertEqual([u.source_text for u in raw], [source])
                self.assertEqual([u.source_text for u in balanced], [source])
                cases_, count = extract(
                    BOOK, source, length_min=1, length_max=120)
                self.assertEqual(count["eligible"], 1)
                self.assertEqual(cases_[0]["source_text"], source)
                self.assertEqual(cases_[0]["balanced_analysis_text"], source)

    def test_unrelated_complete_clauses_and_independent_lookalikes_remain_split(self):
        sources = (
            "He arrived; she left.",
            "He paused; and, keeping her close, she turned toward the door.",
            "He paused; walking home, talking softly, she left.",
            "She paused; if the weather improves, we will leave.",
            "They stayed; for a little while, they waited.",
            "They stayed; for the last hour, they waited.",
            "The dog barked; on the other hand, the cat slept.",
            "He danced; and the singers laughed.",
            "She saw the house; and might I ask where she went?",
        )
        for source in sources:
            with self.subTest(source=source):
                decisions = review_semicolon_boundaries(source)
                self.assertTrue(decisions)
                self.assertFalse(any(d.merge for d in decisions))
                units = split_prose_analysis_units(source)
                self.assertEqual(len(units), 2)
                self.assertEqual(" ".join(u.source_text for u in units), source)

    def test_preposed_series_can_have_relative_but_requires_matrix(self):
        positive = (
            "In the garden; with the lamps that he had bought; "
            "Mary waited by the gate."
        )
        decisions = review_semicolon_boundaries(positive)
        self.assertEqual([d.reason for d in decisions],
                         ["preposed_adverbial_chain_with_matrix"] * 2)
        independent = "In the garden; with the lamps that he had bought."
        self.assertFalse(review_semicolon_boundaries(independent)[0].merge)

    def test_original_semicolon_offsets_and_quotes_are_preserved(self):
        source = ('“I wrote to her; merely informing her of the change.” '
                  'Then I departed.')
        self.assertEqual(split_prose_sentences(source), [
            '“I wrote to her; merely informing her of the change.”',
            'Then I departed.',
        ])
        units = split_prose_analysis_units(source)
        self.assertEqual([u.source_text for u in units], [
            '“I wrote to her; merely informing her of the change.”',
            'Then I departed.',
        ])
        self.assertEqual(" ".join(u.source_text for u in units), source)
        self.assertEqual(units[0].synthetic_prefix, "")
        self.assertEqual(units[0].synthetic_suffix, "")

    def test_skeleton_is_not_a_grammatical_oracle(self):
        adverb = skeleton("merely informing her in the letters.")
        self.assertTrue(adverb.starts_with_participle)
        self.assertFalse(adverb.overt_subject_candidate)
        self.assertFalse(adverb.finite_predicate_candidate)
        complete = skeleton("She returned home.")
        self.assertTrue(complete.overt_subject_candidate)
        self.assertTrue(complete.finite_predicate_candidate)
        signals = source_unit_signals("on the other, Mr. Murdstone.")
        self.assertTrue(signals["starts_with_preposition"])
        self.assertFalse(signals["overt_subject_candidate"])

if __name__ == "__main__":
    unittest.main()
