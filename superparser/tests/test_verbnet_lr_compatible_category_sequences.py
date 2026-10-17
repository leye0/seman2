"""Regression: lexical ambiguity NEVER blocks a compatible structure."""
import unittest
from research.verbnet_lr.compatible_category_sequences import CompatibleCategorySequenceIndex
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import Token, LexicalCandidate, LexicalLattice


def lattice(words, choices):
    tokens, candidates = [], []
    cursor = 0
    for i, (word, options) in enumerate(zip(words, choices)):
        token = Token(i, cursor, cursor + len(word), word)
        tokens.append(token)
        for cat in options:
            candidates.append(LexicalCandidate(
                token.start, token.end, word, word.lower(), cat,
                FeatureStructure.empty()))
        cursor += len(word)+1
    return LexicalLattice(" ".join(words), tuple(tokens),tuple(candidates))


class CompatibleCategorySequenceTests(unittest.TestCase):
    def test_simple_sentences_share_det_n_v_despite_different_ambiguity(self):
        idx = CompatibleCategorySequenceIndex()
        dog=lattice(["The","dog","eats"],[
            ["DET"], ["N","V"], ["V","N","ADJ"]])
        water=lattice(["The","water","boils"],[
            ["DET","PRONOUN"], ["N","V","ADJ","PROPER-NOUN"], ["V"]])
        self.assertEqual(idx.observe(idx.lattice_slots(dog)).compatible_prior_observations,0)
        match=idx.observe(idx.lattice_slots(water))
        self.assertEqual(match.compatible_prior_observations,1)
        self.assertEqual(match.first_common_enumeration,("DET","N","V"))

    def test_more_categories_never_remove_match(self):
        idx=CompatibleCategorySequenceIndex()
        idx.observe((frozenset(["DET"]),frozenset(["N"]),frozenset(["V"])))
        simple=idx.query((frozenset(["DET"]),frozenset(["N"]),frozenset(["V"])))
        extra=idx.query((frozenset(["DET","PRONOUN","PREP"]),
                         frozenset(["ADJ","N","V"]),
                         frozenset(["ADV","N","V","MODAL"])))
        self.assertTrue(simple.has_match)
        self.assertEqual(extra.compatible_prior_observations,
                         simple.compatible_prior_observations)
        self.assertEqual(extra.first_common_enumeration,("DET","N","V"))

    def test_large_cartesian_family_is_implicit(self):
        idx=CompatibleCategorySequenceIndex()
        idx.observe((frozenset(["N","V","ADV","ADJ","DET"]),)*34)
        r=idx.query((frozenset(["N"]),)*34)
        self.assertEqual(r.compatible_prior_observations,1)
        self.assertEqual(r.first_common_enumeration,("N",)*34)

    def test_mismatched_length_and_no_overlap(self):
        idx=CompatibleCategorySequenceIndex()
        idx.observe((frozenset(["DET"]),frozenset(["N"]),frozenset(["V"])))
        self.assertFalse(idx.query((frozenset(["DET"]),frozenset(["ADV"]),
                                    frozenset(["V"]))).has_match)
        self.assertFalse(idx.query((frozenset(["DET"]),frozenset(["N"]))).has_match)

    def test_empty_slots_do_not_manufacture_matches(self):
        idx=CompatibleCategorySequenceIndex()
        idx.observe((frozenset(["N"]),frozenset()))
        self.assertFalse(idx.query((frozenset(["N"]),frozenset())).has_match)
        self.assertEqual(idx.nonempty,0)
        with self.assertRaises(ValueError):
            idx.observe(())

    def test_counts_prior_observations_not_possible_combinations(self):
        idx=CompatibleCategorySequenceIndex()
        idx.observe((frozenset(["N","V"]),frozenset(["V","N"])))
        idx.observe((frozenset(["N"]),frozenset(["V"])))
        m=idx.observe((frozenset(["N","V","ADJ"]),
                       frozenset(["V","N","ADV"])))
        self.assertEqual(m.compatible_prior_observations,2)

    def test_question_mark_trimming_preserves_lattice(self):
        idx=CompatibleCategorySequenceIndex()
        case=lattice(["The","dog","eats","?"],[
            ["DET"],["N","V"],["V"],[]])
        original=case.candidates
        self.assertEqual(len(idx.lattice_slots(case)),3)
        idx.observe(idx.lattice_slots(case))
        self.assertIs(case.candidates,original)


if __name__=="__main__":
    unittest.main()
