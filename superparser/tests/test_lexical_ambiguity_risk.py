"""Unit tests for lexical combinatorics and unbiased ROC ranking."""
import math
import unittest
from scripts.audit_lexical_ambiguity_risk import lexical_ambiguity,auc
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import LexicalCandidate,LexicalLattice,Token

def c(start,end,category,features=None):
    return LexicalCandidate(start,end,"x","x",category,
        FeatureStructure.build(features or {}))

class LexicalAmbiguityTests(unittest.TestCase):
    def test_product_categories_and_distinct_subtypes(self):
        lattice=LexicalLattice("one two",
            (Token(0,0,3,"one"),Token(1,4,7,"two")),
            (c(0,3,"N"),c(0,3,"V"),c(0,3,"V",{"vform":"finite"}),
             c(4,7,"DET"),c(4,7,"N"),c(4,7,"ADV")))
        traits=lexical_ambiguity(lattice)
        self.assertAlmostEqual(traits["category_bits"],math.log2(6))
        self.assertAlmostEqual(traits["syntactic_bits"],math.log2(9))
        self.assertEqual(traits["ambiguous_positions"],2)

    def test_split_and_multiword_spans_are_not_multiplied(self):
        lattice=LexicalLattice("one two",
            (Token(0,0,3,"one"),Token(1,4,7,"two")),
            (c(0,7,"N"),c(4,7,"V")))
        traits=lexical_ambiguity(lattice)
        self.assertEqual(traits["category_bits"],0)
        self.assertEqual(traits["missing_exact_spans"],1)
        self.assertEqual(traits["non_exact_spans"],1)

    def test_tie_aware_auc(self):
        rows=[{"x":0,"y":False},{"x":0,"y":True},
              {"x":1,"y":False},{"x":1,"y":True}]
        self.assertEqual(auc(rows,"x","y"),0.5)
        self.assertEqual(auc([{"x":0,"y":False},{"x":2,"y":True}],"x","y"),1.0)
        self.assertIsNone(auc([{"x":1,"y":True}],"x","y"))

if __name__=="__main__":
    unittest.main()
