"""Rule-specific grammatical feature replay must not accept a POS-only hit.

The test grammar includes shared variables and POS ambiguity. Every check
uses the SAME unify/evidence rules as the canonical lazy materializer.
A witness is evidence for ONE shape, never the set of all possible parses.
"""
from __future__ import annotations

from dataclasses import replace
import unittest

from research.verbnet_lr.subtree_feature_replay import SubtreeFeatureReplayer
from research.verbnet_lr.subtree_signature_cache import (
    SubtreeSignatureCache, SignatureHint, ObservedSubtree,
)
from seman_parser.grammar import Grammar,parse_rule
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import Token, LexicalCandidate, LexicalLattice


def sentence(readings):
    words=("this","dog")
    tokens=(Token(0,0,4,words[0]),Token(1,5,8,words[1]))
    candidates=[]
    for i,group in enumerate(readings):
        token=tokens[i]
        for category,features in group:
            candidates.append(LexicalCandidate(
                token.start,token.end,token.text,token.text,
                category,FeatureStructure.build(features)))
    return LexicalLattice("this dog",tokens,tuple(candidates))


SHAPE=("rule","np_agreement","NP",
       (("lex","DET"),("lex","N")))
TEMPLATE=ObservedSubtree(("DET","N"),"NP","np_agreement",SHAPE)
GRAMMAR=Grammar((parse_rule({
    "id":"np_agreement",
    "lhs":{"category":"NP","features":{"number":"?n"}},
    "rhs":[
        {"category":"DET","features":{"number":"?n"}},
        {"category":"N","features":{"number":"?n"},
         "requires":["number"]},
    ],
}),))
HINT=SignatureHint(0,2,0,8,0,"NP","np_agreement")


class SubtreeFeatureReplayTests(unittest.TestCase):
    def setUp(self):
        self.replayer=SubtreeFeatureReplayer([TEMPLATE],GRAMMAR)

    def test_agreement_is_replayed_not_just_matching_categories(self):
        matching=sentence((
            [("DET",{"number":"sg"})],[("N",{"number":"sg"})],
        ))
        wrong=sentence((
            [("DET",{"number":"sg"})],[("N",{"number":"pl"})],
        ))
        self.assertEqual(self.replayer.replay(HINT,matching).status,"WITNESS")
        self.assertEqual(self.replayer.replay(HINT,wrong).status,"NO_WITNESS")

    def test_positive_evidence_is_required_not_inferred_from_lhs(self):
        missing=sentence((
            [("DET",{"number":"sg"})],[("N",{})],
        ))
        self.assertEqual(self.replayer.replay(HINT,missing).status,"NO_WITNESS")

    def test_alternative_lexical_reading_is_preserved(self):
        alternatives=sentence((
            [("DET",{"number":"sg"})],
            [("N",{"number":"pl"}),("N",{"number":"sg"}),("V",{})],
        ))
        result=self.replayer.replay(HINT,alternatives)
        self.assertEqual(result.status,"WITNESS")
        self.assertEqual(result.witness_categories,("DET","N"))
        self.assertEqual(len(alternatives.candidates),4)

    def test_bounded_search_is_unknown_not_ungrammatical(self):
        alternatives=sentence((
            [("DET",{"number":"sg"})],
            [("N",{"number":"pl"}),("N",{"number":"sg"})],
        ))
        result=self.replayer.replay(HINT,alternatives,max_steps=1)
        self.assertEqual(result.status,"BUDGET_UNKNOWN")

    def test_unsupported_when_rule_changed_or_removed(self):
        stale=SubtreeFeatureReplayer([TEMPLATE],Grammar(()))
        self.assertEqual(stale.replay(HINT,sentence((
            [("DET",{"number":"sg"})],[("N",{"number":"sg"})]
        ))).status,"UNSUPPORTED")

    def test_reject_forged_span_and_rule_identity(self):
        correct=sentence((
            [("DET",{"number":"sg"})],[("N",{"number":"sg"})],
        ))
        self.assertEqual(self.replayer.replay(
            replace(HINT,end_char=7),correct).status,"UNSUPPORTED")
        self.assertEqual(self.replayer.replay(
            replace(HINT,root_rule="other"),correct).status,"UNSUPPORTED")

    def test_nested_rule_evidence_and_sibling_variable_context(self):
        grammar=Grammar((
            GRAMMAR.rules[0],
            parse_rule({
                "id":"clause_np_verb_agreement",
                "lhs":{"category":"CLAUSE","features":{"number":"?n"}},
                "rhs":[
                    {"category":"NP","features":{"number":"?n"},
                     "requires":["number"]},
                    {"category":"V","features":{"number":"?n"},
                     "requires":["number"]},
                ],
            }),
        ))
        shape=("rule","clause_np_verb_agreement","CLAUSE",(
            SHAPE,("lex","V")))
        template=ObservedSubtree(
            ("DET","N","V"),"CLAUSE",
            "clause_np_verb_agreement",shape)
        replayer=SubtreeFeatureReplayer([template],grammar)
        tokens=(Token(0,0,4,"this"),Token(1,5,8,"dog"),
                Token(2,9,13,"runs"))
        def lattice(verb_number):
            return LexicalLattice("this dog runs",tokens,tuple(
                LexicalCandidate(t.start,t.end,t.text,t.text,category,
                    FeatureStructure.build({"number":value}))
                for t,category,value in zip(tokens,("DET","N","V"),
                                             ("sg","sg",verb_number))))
        hint=SignatureHint(0,3,0,13,0,"CLAUSE",
                           "clause_np_verb_agreement")
        self.assertEqual(replayer.replay(hint,lattice("sg")).status,"WITNESS")
        self.assertEqual(replayer.replay(hint,lattice("pl")).status,"NO_WITNESS")

    def test_routine_does_not_add_or_remove_candidates(self):
        lattice=sentence((
            [("DET",{"number":"sg"}),("ADV",{})],
            [("N",{"number":"sg"}),("N",{"number":"pl"})],
        ))
        before=lattice.as_dict()
        self.assertEqual(self.replayer.replay(HINT,lattice).status,"WITNESS")
        self.assertEqual(before,lattice.as_dict())


if __name__=="__main__":
    unittest.main()
