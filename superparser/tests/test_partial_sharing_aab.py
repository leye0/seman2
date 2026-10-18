"""Non-lossy grouping diagnostics for research-only packed partial states."""
import unittest
from types import SimpleNamespace

from scripts.benchmark_partial_sharing_aab import structural_duplication
from seman_parser.grammar import load_grammar_rows

def symbol(category,features=None):
    return {"category":category,"features":features or {}}

class PrefixSharingTests(unittest.TestCase):
    def test_only_identical_matched_features_share_prefix_signature(self):
        rules=load_grammar_rows([
            {"id":"a","lhs":symbol("VP"),"rhs":[symbol("V"),symbol("NP")]},
            {"id":"b","lhs":symbol("VP"),"rhs":[symbol("V"),symbol("PP")]},
            {"id":"c","lhs":symbol("VP"),"rhs":[symbol("V",{"vform":"finite"}),symbol("NP")]},
            {"id":"d","lhs":symbol("CLAUSE"),"rhs":[symbol("V"),symbol("NP")]},
        ])
        forest=SimpleNamespace(
            partials=[SimpleNamespace(rule_index=i,start=0,end=4,dot=1)
                      for i in range(4)],
            compiled=SimpleNamespace(rules=[
                SimpleNamespace(rule=rule) for rule in rules]))
        info=structural_duplication(SimpleNamespace(shared_forest=forest))
        self.assertEqual(info["partials"],4)
        self.assertEqual(info["potential_duplicates"],1)
        self.assertEqual(info["potential_prefix_reuse"],2)
        self.assertEqual(info["prefix_slots"],2)

    def test_spans_and_dot_depth_are_distinct(self):
        rules=load_grammar_rows([
            {"id":"a","lhs":symbol("VP"),"rhs":[symbol("V"),symbol("NP")]}
        ])
        forest=SimpleNamespace(
            partials=[
                SimpleNamespace(rule_index=0,start=0,end=4,dot=1),
                SimpleNamespace(rule_index=0,start=1,end=4,dot=1),
                SimpleNamespace(rule_index=0,start=0,end=6,dot=1),
                SimpleNamespace(rule_index=0,start=0,end=6,dot=2),
            ],
            compiled=SimpleNamespace(rules=[SimpleNamespace(rule=rule)
                                          for rule in rules]))
        info=structural_duplication(SimpleNamespace(shared_forest=forest))
        self.assertEqual(info["potential_prefix_reuse"],0)

if __name__=="__main__":
    unittest.main()
