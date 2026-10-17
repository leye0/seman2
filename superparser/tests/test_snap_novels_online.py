"""The online experiment counts overlapping category enumerations."""
import unittest
from research.verbnet_lr.compatible_category_sequences import CompatibleCategorySequenceIndex
from seman_parser.segmentation import Token, LexicalCandidate, LexicalLattice
from seman_parser.features import FeatureStructure

def lattice(words, choices):
    tokens,candidates=[],[]
    at=0
    for i,(word,cats) in enumerate(zip(words,choices)):
        tok=Token(i,at,at+len(word),word)
        tokens.append(tok)
        for cat in cats:
            candidates.append(LexicalCandidate(
                tok.start,tok.end,word,word,cat,FeatureStructure.empty()))
        at+=len(word)+1
    return LexicalLattice(" ".join(words),tuple(tokens),tuple(candidates))

class AllSentenceNovelTests(unittest.TestCase):
    def test_shared_det_n_v_despite_different_ambiguities(self):
        index=CompatibleCategorySequenceIndex()
        first=lattice(["the","dog","eats"],[
            ["DET"],["N","V"],["V","N"]])
        second=lattice(["the","water","boils"],[
            ["DET","PRONOUN"],["N","ADJ"],["V","ADV"]])
        index.observe(index.lattice_slots(first))
        hit=index.observe(index.lattice_slots(second))
        self.assertEqual(hit.first_common_enumeration,("DET","N","V"))
        self.assertEqual(hit.compatible_prior_observations,1)

    def test_no_overlap_does_not_fabricate_a_match(self):
        index=CompatibleCategorySequenceIndex()
        index.observe((frozenset(["DET"]),frozenset(["N"])))
        self.assertFalse(index.query(
            (frozenset(["DET"]),frozenset(["V"]))
        ).has_match)

if __name__=="__main__":
    unittest.main()
