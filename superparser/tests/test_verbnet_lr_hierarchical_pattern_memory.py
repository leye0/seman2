"""C: learned typed hierarchical repetitions, alternatives, agreement."""
import unittest

from seman_parser.engine import ParserResources
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.features import FeatureStructure, Variable
from seman_parser.segmentation import LexicalCandidate,LexicalLattice,Token
from seman_parser.predictive import CompactNode,PredictiveParser
from seman_parser.symbols import intern
from research.verbnet_lr.hierarchical_pattern_memory import HierarchicalPatternMemory


def sym(category,**features):
    return RuleSymbol(category,FeatureStructure.build(features))


def rule(name,category,*children):
    return GrammarRule(name,tuple(children),sym(category),score=1.0)


class HierarchicalPatternTests(unittest.TestCase):
    def setUp(self):
        grammar=Grammar([
            rule("np_base","NP",sym("DET",number="?n"),sym("N",number="?n")),
            rule("pp_base","PP",sym("PREP"),sym("NP")),
            rule("np_pp","NP",sym("NP"),sym("PP")),
            rule("np_adj","NP",sym("DET"),sym("ADJ"),sym("N")),
        ])
        self.resources=ParserResources(grammar,None,None)
        self.rules={r.rule_id:r for r in grammar.rules}
        self.materializer=PredictiveParser(self.resources)
        self.memory=HierarchicalPatternMemory(
            self.resources,min_rule_sentences=2,max_span=12,
            variants_per_cell=3,max_expansions=20000,max_wall_ms=250)

    def make(self, words, *, categories=None, numbers=None):
        tokens=[];candidates=[];at=0
        categories=categories or [dict(the=["DET"],a=["DET"],
                              dog=["N"],cat=["N"],house=["N"],garden=["N"],
                              near=["PREP"],small=["ADJ"]).get(w,["N"])
                              for w in words]
        for i,(word,cats) in enumerate(zip(words,categories)):
            tok=Token(i,at,at+len(word),word);tokens.append(tok)
            for cat in cats:
                num=(numbers or {}).get(i,"sg")
                features=FeatureStructure.build({"number":num}
                          if cat in ("DET","N") else {})
                candidates.append(LexicalCandidate(
                    tok.start,tok.end,word,word,cat,features,score=1.0))
            at+=len(word)+1
        return LexicalLattice(" ".join(words),tuple(tokens),tuple(candidates))

    def leaf(self, candidate):
        return CompactNode(candidate.category,intern(candidate.category),
                           candidate.span_start,candidate.span_end,
                           candidate.features,
                           frozenset(k for k,_ in candidate.features.items()),
                           candidate.score,candidate=candidate)

    def reduce(self,name,*nodes):
        node=PredictiveParser._reduce(self.rules[name],nodes)
        self.assertIsNotNone(node,name)
        return node

    def train(self):
        # Two distinct source sentences with a base and one PP attachment.
        for i,(words,indices) in enumerate((
            (["the","dog","near","a","house"],(0,1,2,3,4)),
            (["a","cat","near","the","garden"],(0,1,2,3,4)),
        )):
            lattice=self.make(words)
            d,n,p,a,m=[self.leaf(x) for x in lattice.candidates]
            main=self.reduce("np_base",d,n)
            secondary=self.reduce("np_base",a,m)
            pp=self.reduce("pp_base",p,secondary)
            whole=self.reduce("np_pp",main,pp)
            item=self.materializer._materialize(whole)
            self.memory.observe([item],failed=True,sentence_id=i)

    def test_learned_np_pp_star_generalizes_to_two_attachments(self):
        self.train()
        status=self.memory.summary()
        self.assertIn("np_pp",status["recursive_extension_rule_ids"])
        self.assertIn("NP",status["root_categories_with_optional_recursive_extension"])
        self.assertGreaterEqual(status["alternative_categories"],1)
        unseen=self.make(["the","dog","near","a","house",
                           "near","the","cat"])
        matches=self.memory.match(unseen,min_report_tokens=5)
        self.assertTrue(any(h.category=="NP" and h.tokens==8
                            and h.structurally_novel for h in matches.hits),
                        (matches, self.memory.summary()))
        self.assertEqual(matches.incomplete,False)

    def test_extra_lexical_categories_never_remove_a_valid_structure(self):
        self.train()
        words=["the","dog","near","a","house","near","the","cat"]
        plain=self.make(words)
        choices=[["DET","V","ADJ"],["N","V","ADJ"],
                 ["PREP","ADV"],["DET","N"],["N","V"],
                 ["PREP","ADV"],["DET","V"],["N","V"]]
        enriched=self.make(words,categories=choices)
        before=self.memory.match(plain,min_report_tokens=8)
        after=self.memory.match(enriched,min_report_tokens=8)
        self.assertTrue(any(h.tokens==8 for h in before.hits))
        self.assertTrue(any(h.tokens==8 for h in after.hits))

    def test_bad_agreement_is_rejected_despite_matching_categories(self):
        self.train()
        malformed=self.make(["the","dog"],numbers={0:"pl",1:"sg"})
        result=self.memory.match(malformed,min_report_tokens=2)
        self.assertFalse(any(h.category=="NP" for h in result.hits))
        valid=self.make(["the","dog"])
        good=self.memory.match(valid,min_report_tokens=2)
        self.assertTrue(any(h.category=="NP" for h in good.hits))

    def test_no_training_rules_no_grammatical_claim(self):
        untrained=HierarchicalPatternMemory(self.resources,min_rule_sentences=3)
        query=self.make(["the","dog","near","a","house"])
        result=untrained.match(query)
        self.assertFalse(result.hits)
        self.assertFalse(result.incomplete)

    def test_expansion_budget_is_reported_not_hidden(self):
        self.train()
        self.memory.max_expansions=1
        query=self.make(["the","dog","near","a","house","near","the","cat"])
        result=self.memory.match(query)
        self.assertTrue(result.incomplete)


if __name__=="__main__":
    unittest.main()
