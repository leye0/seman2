"""Correctly distinguish lexical category recurrence and full-tree reuse."""
import unittest
from types import SimpleNamespace
from research.verbnet_lr.gutenberg_novels import Book
from scripts.benchmark_snap_novels_online import category_signature,digest_signature
from seman_parser.segmentation import Token, LexicalCandidate, LexicalLattice
from seman_parser.features import FeatureStructure


class AllSentenceNovelTests(unittest.TestCase):
    def lattice(self,word,categories):
        t=Token(0,0,len(word),word)
        c=tuple(LexicalCandidate(0,len(word),word,word,category,
                                 FeatureStructure.empty())
                for category in categories)
        return LexicalLattice(word,(t,),c)

    def test_all_possible_categories_in_fingerprint(self):
        left=self.lattice("can",["N","V","MODAL"])
        self.assertEqual(category_signature(left),(("MODAL","N","V"),))
        right=self.lattice("different",["MODAL","V","N"])
        self.assertEqual(category_signature(left),category_signature(right))
        self.assertEqual(digest_signature(category_signature(left)),
                         digest_signature(category_signature(right)))
        self.assertNotEqual(category_signature(left),
                            category_signature(self.lattice("can",["V"])))

    def test_coarse_categories_and_no_word_identity(self):
        a=self.lattice("Sam",["PROPER-NOUN","N"])
        b=self.lattice("Ben",["PROPER-PLACE","N"])
        self.assertNotEqual(category_signature(a),category_signature(b))
        self.assertEqual(category_signature(a,coarse=True),
                         category_signature(b,coarse=True))


if __name__=="__main__":
    unittest.main()
