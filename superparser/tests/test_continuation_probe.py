"""Rule-prefix lookahead probe is diagnostic only and preserves grammar."""
import unittest
from research.verbnet_lr.continuation_probe import ContinuationIndex
from seman_parser.features import FeatureStructure
from seman_parser.grammar import load_grammar_rows
from seman_parser.segmentation import Token,LexicalCandidate,LexicalLattice

def lexical(start,end,category,features=None):
    return LexicalCandidate(start,end,"token","token",category,
                            FeatureStructure.build(features or {}))

def sym(category,features=None):
    return {"category":category,"features":features or {}}

class ContinuationProbeTests(unittest.TestCase):
    def setUp(self):
        self.grammar=load_grammar_rows([
            {"id":"np","lhs":sym("NP"),"rhs":[sym("DET"),sym("N")]},
            {"id":"clause","lhs":sym("CLAUSE"),"rhs":[sym("NP"),sym("VP")]},
            {"id":"vnp","lhs":sym("VP"),"rhs":[sym("V",{"vform":"finite"}),sym("NP")]},
            {"id":"vpp","lhs":sym("VP"),"rhs":[sym("V",{"vform":"finite"}),sym("PP")]},
            {"id":"pp","lhs":sym("PP"),"rhs":[sym("PREP"),sym("NP")]},
            {"id":"np_variant","lhs":sym("NP"),"rhs":[sym("DET"),sym("N")]}
        ])
        self.index=ContinuationIndex(self.grammar)

    def test_first_closure_reaches_lexical_starts(self):
        self.assertIn("DET",self.index.first["CLAUSE"])
        self.assertIn("V",self.index.first["VP"])
        self.assertEqual(self.index.rule_count,6)
        self.assertEqual(self.index.skeleton_count,5)

    def test_feature_conflicts_filter_only_direct(self):
        good=self.index._viable(
            [lexical(0,1,"V",{"vform":"finite"})],self.index.start)
        bad=self.index._viable(
            [lexical(0,1,"V",{"vform":"ing"})],self.index.start)
        self.assertIn(2,good)
        self.assertIn(3,good)
        self.assertNotIn(2,bad)
        self.assertNotIn(3,bad)

    def test_no_changes_to_input_or_parse_tree_and_duplicate_rules_counted(self):
        lattice=LexicalLattice("the dog",
            (Token(0,0,3,"the"),Token(1,4,7,"dog")),
            (lexical(0,3,"DET"),lexical(4,7,"N")))
        snapshot=lattice.as_dict()
        probe=self.index.signal(lattice)
        self.assertEqual(lattice.as_dict(),snapshot)
        self.assertGreater(probe["struct_start_sum"],0)
        self.assertGreater(probe["struct_variant_excess"],0)
        self.assertGreater(probe["struct_pair_sum"],0)
        self.assertGreaterEqual(probe["struct_probe_ms"],0)

    def test_cross_token_edges_never_invent_one_token_categories(self):
        lattice=LexicalLattice("new york",
            (Token(0,0,3,"new"),Token(1,4,8,"york")),
            (lexical(0,8,"NP"),))
        probe=self.index.signal(lattice)
        self.assertEqual(probe["struct_start_sum"],0)
        self.assertEqual(probe["struct_zero_leaf_tokens"],2)
        self.assertEqual(probe["struct_nonexact_spans"],1)

    def test_fast_category_bitsets_are_optimistic_and_cheap(self):
        lattice=LexicalLattice("the dog",
            (Token(0,0,3,"the"),Token(1,4,7,"dog")),
            (lexical(0,3,"DET"),lexical(4,7,"N")))
        full=self.index.signal(lattice)
        fast=self.index.fast_signal(lattice)
        self.assertGreaterEqual(fast["fast_start_sum"],full["struct_start_sum"])
        self.assertGreaterEqual(fast["fast_pair_sum"],full["struct_pair_sum"])
        self.assertGreaterEqual(fast["fast_variant_excess"],full["struct_variant_excess"])
        self.assertGreaterEqual(fast["fast_probe_ms"],0.0)

    def test_fast_path_preserves_feature_conflict_as_unproven(self):
        lattice=LexicalLattice("running",
            (Token(0,0,7,"running"),),
            (lexical(0,7,"V",{"vform":"ing"}),))
        full=self.index.signal(lattice)
        fast=self.index.fast_signal(lattice)
        self.assertGreater(fast["fast_start_sum"],full["struct_start_sum"])

    def test_recursive_first_closure_terminates(self):
        recursive=load_grammar_rows([
            {"id":"self","lhs":sym("NP"),"rhs":[sym("NP"),sym("PP")]},
            {"id":"base","lhs":sym("NP"),"rhs":[sym("DET"),sym("N")]}
        ])
        index=ContinuationIndex(recursive)
        self.assertIn("DET",index.first["NP"])

if __name__=="__main__":
    unittest.main()
