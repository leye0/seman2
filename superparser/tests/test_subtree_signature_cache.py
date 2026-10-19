"""Subtree signatures are probabilistic HINTS, never grammar answers.

The original lexical lattice is immutable and all observed grammatical
rule identities are preserved as *opaque* signatures. No gold correctness
claim follows from a cache hit.
"""
from __future__ import annotations

import unittest

from research.verbnet_lr.subtree_signature_cache import (
    SubtreeSignatureCache, observations, witnessed_matches,
)
from seman_parser.chart import ChartItem, Provenance
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import Token,LexicalCandidate,LexicalLattice


def tiny(texts, categories, alternatives=()):
    start=0
    toks=[]
    candidates=[]
    for idx,(word,category) in enumerate(zip(texts,categories)):
        end=start+len(word)
        toks.append(Token(idx,start,end,word))
        candidates.append(LexicalCandidate(
            start,end,word,word,category,FeatureStructure.empty()))
        for alternative in alternatives:
            if alternative[0]==idx:
                candidates.append(LexicalCandidate(
                    start,end,word,word,alternative[1],FeatureStructure.empty()))
        start=end+1
    return LexicalLattice(" ".join(texts),tuple(toks),tuple(candidates))


def leaf(candidate):
    return ChartItem(
        candidate.span_start,candidate.span_end,candidate.category,
        FeatureStructure.empty(),None,0.0,Provenance("lexical"),
        lexical_candidate=candidate)


def parent(category,rule_id,children):
    return ChartItem(
        children[0].start,children[-1].end,category,
        FeatureStructure.empty(),None,1.0,Provenance("rule"),
        children=tuple(children),rule_id=rule_id)


class SubtreeSignatureCacheTests(unittest.TestCase):
    def test_cross_sentence_signature_match_is_hint_not_parse(self):
        train=tiny(("the","dog","walks"),("DET","N","V"))
        subtree=parent("NP","np_det_n",
                       (leaf(train.candidates[0]),leaf(train.candidates[1])))
        root=parent("CLAUSE","clause_np_v",(subtree,leaf(train.candidates[2])))
        cache=SubtreeSignatureCache()
        self.assertGreater(cache.observe(root,train),0)
        cache.freeze()
        holdout=tiny(("the","river","runs"),("DET","N","V"))
        before=holdout.as_dict()
        scan=cache.scan(holdout)
        self.assertFalse(scan.saturated)
        self.assertTrue(any(x.root_rule=="np_det_n" and
                            (x.start_token,x.end_token)==(0,2)
                            for x in scan.matches))
        self.assertEqual(before,holdout.as_dict())
        self.assertEqual(witnessed_matches(scan,cache,root,train),
                         len(scan.matches))
        with self.assertRaises(RuntimeError):
            cache.observe(root,holdout)
        # A hint has no complete/parse method: grammar is still required.
        self.assertFalse(hasattr(scan.matches[0],"completed"))

    def test_ambiguity_is_set_based_and_does_not_materialize_products(self):
        train=tiny(("the","dog"),("DET","N"))
        root=parent("NP","np_det_n",tuple(map(leaf,train.candidates)))
        cache=SubtreeSignatureCache()
        cache.observe(root,train)
        unknown=tiny(("that","walks"),("V","V"),
                     alternatives=((0,"DET"),(1,"N"),(1,"ADJ")))
        matches=cache.scan(unknown)
        self.assertTrue(any(x.root_rule=="np_det_n" for x in matches.matches))
        self.assertFalse(matches.saturated)
        self.assertEqual(cache.summary()["templates"],1)

    def test_absent_signature_never_licenses_new_root(self):
        train=tiny(("the","dog"),("DET","N"))
        root=parent("NP","np_det_n",tuple(map(leaf,train.candidates)))
        cache=SubtreeSignatureCache()
        cache.observe(root,train)
        unknown=tiny(("walks","dog"),("V","N"))
        self.assertFalse(cache.scan(unknown).matches)
        self.assertEqual(witnessed_matches(cache.scan(unknown),cache,root,train),0)

    def test_partial_budget_does_not_mark_candidate_grammatical(self):
        train=tiny(("the","dog"),("DET","N"))
        root=parent("NP","np_det_n",tuple(map(leaf,train.candidates)))
        cache=SubtreeSignatureCache()
        cache.observe(root,train)
        limited=cache.scan(train,max_transitions=1)
        self.assertTrue(limited.saturated)
        self.assertFalse(limited.matches)

    def test_multiword_or_incomplete_lexical_coverage_is_rejected(self):
        train=tiny(("the","dog"),("DET","N"))
        multi=LexicalCandidate(
            0,7,"the dog","the dog","NP",FeatureStructure.empty())
        root=parent("CLAUSE","clause_np",(leaf(multi),))
        self.assertEqual(observations(root,train),())
        cache=SubtreeSignatureCache()
        self.assertEqual(cache.observe(root,train),0)
        self.assertEqual(cache.summary()["templates"],0)

    def test_separate_rule_attachments_remain_distinct(self):
        train=tiny(("the","dog"),("DET","N"))
        leaves=tuple(map(leaf,train.candidates))
        cache=SubtreeSignatureCache()
        a=parent("NP","np_det_n",leaves)
        b=parent("NP","np_apposition",leaves)
        cache.observe(a,train)
        cache.observe(b,train)
        self.assertEqual(cache.summary()["templates"],2)
        hints=cache.scan(train).matches
        self.assertEqual({h.root_rule for h in hints},
                         {"np_det_n","np_apposition"})

    def test_bounded_training_does_not_evict_different_patterns(self):
        train=tiny(("the","dog"),("DET","N"))
        leaves=tuple(map(leaf,train.candidates))
        cache=SubtreeSignatureCache(max_templates=1)
        cache.observe(parent("NP","np_det_n",leaves),train)
        cache.observe(parent("NP","np_apposition",leaves),train)
        self.assertEqual(cache.summary()["templates"],1)
        self.assertGreater(cache.summary()["rejected_capacity"],0)
        self.assertEqual(cache.scan(train).matches[0].root_rule,"np_det_n")


if __name__=="__main__":
    unittest.main()
