"""Fast multiword precheck must preserve exact lexical lattice alternatives."""
import unittest

from research.verbnet_lr.fast_lattice import FastMultiwordLexicon
from seman_parser.lexicon import Lexicon, parse_entry
from seman_parser.segmentation import build_lattice


class TestFastMultiword(unittest.TestCase):
    def setUp(self):
        self.lex = Lexicon((
            parse_entry({"lemma":"take a breath",
                         "surfaces":["take a breath"],
                         "senses":[{"id":"t1","category":"V",
                                    "features":{"vform":"base"}}]}),
            parse_entry({"lemma":"red car","surfaces":["red car"],
                         "senses":[{"id":"c1","category":"N",
                                    "features":{"number":"singular"}}]}),
            parse_entry({"lemma":"the","surfaces":["the"],
                         "senses":[{"id":"det","category":"DET","features":{}}]}),
        ))

    def test_exact_multiword_survives(self):
        fast = FastMultiwordLexicon(self.lex)
        a = build_lattice("Take a breath after lunch.",self.lex)
        b = build_lattice("Take a breath after lunch.",fast)
        self.assertEqual({c.syntactic_signature() for c in a.candidates},
                         {c.syntactic_signature() for c in b.candidates})
        self.assertGreater(fast.precheck_rejections,0)

    def test_inflected_multiword_lookups_preserved(self):
        fast = FastMultiwordLexicon(self.lex)
        self.assertTrue(fast._could_exist("red cars"))
        self.assertTrue(fast._could_exist("opened boxes"))

    def test_known_static_lemma_survives(self):
        fast = FastMultiwordLexicon(self.lex)
        self.assertTrue(fast._could_exist("take a breath"))
        self.assertFalse(fast._could_exist("a breath after"))

    def test_nonmultiword_falls_through(self):
        fast = FastMultiwordLexicon(self.lex)
        before = self.lex.lookup_morphology("the")
        after = fast.lookup_morphology("the")
        self.assertEqual(tuple(before), after)


if __name__=="__main__":
    unittest.main()
