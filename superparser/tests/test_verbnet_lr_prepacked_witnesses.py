"""Parity, ambiguity and actual unification savings for opt-in packed C witnesses."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace

from research.verbnet_lr.prepacked_witnesses import PrepackedWitnessIndex
from research.verbnet_lr.hybrid_vector import HybridVectorParser
from seman_parser.chart import ChartItem, Provenance, _compose_syntax
from seman_parser.engine import Parser, ParserResources
from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.segmentation import LexicalCandidate, LexicalLattice, Token
from seman_parser.vector_chart import VectorGrammar


def small_case(*, ambiguous=False, constrained=False):
    text="ax bx"
    empty=FeatureStructure.empty()
    a=LexicalCandidate(0,2,"ax","ax","A",empty,score=1.0)
    b=LexicalCandidate(3,5,"bx","bx","B",empty,score=1.0)
    lattice=LexicalLattice(text,(Token(0,0,2,"ax"),Token(1,3,5,"bx")),(a,b))
    sym_a=RuleSymbol("A",FeatureStructure.build({"case":"acc"}) if constrained else empty)
    rule=GrammarRule("combine",(sym_a,RuleSymbol("B")),RuleSymbol("CLAUSE"),score=2.0)
    rules=[rule]
    if ambiguous:
        rules.append(GrammarRule("combine_other",(RuleSymbol("A"),RuleSymbol("B")),
                                 RuleSymbol("CLAUSE"),score=1.0))
    grammar=VectorGrammar(Grammar(rules))
    one=ChartItem(0,2,"A",empty,None,1.0,Provenance("lexicon"),lexical_candidate=a)
    two=ChartItem(3,5,"B",empty,None,1.0,Provenance("lexicon"),lexical_candidate=b)
    whole=ChartItem(0,5,"CLAUSE",empty,None,4.0,Provenance("rule"),
                    children=(one,two),rule_id="combine",
                    syntax=_compose_syntax(rule,(one,two)))
    return lattice,grammar,PrepackedWitnessIndex((SimpleNamespace(tree=whole),))


def comparable(tree):
    if tree is None:
        return None
    return (tree.category, tree.start,tree.end,tree.rule_id,
            tree.features.as_dict(),tree.syntax.as_dict(),
            tree.lexical_candidate.surface if tree.lexical_candidate else None,
            tuple(comparable(c) for c in tree.children))


class PrepackedWitnessTests(unittest.TestCase):
    def test_unique_closed_subtree_is_replayed_without_losing_full_tree(self):
        lattice,grammar,cache=small_case()
        args=dict(beam=8,max_items=1000,goal_category="CLAUSE")
        original=grammar.parse_lattice(lattice,**args)
        reused=grammar.parse_lattice(lattice,witness_cache=cache,**args)
        self.assertEqual(comparable(original.best()),comparable(reused.best()))
        self.assertEqual(original.best().score,reused.best().score)
        self.assertTrue(reused.completed)
        self.assertEqual(original.stats["forest_nodes"],reused.stats["forest_nodes"])
        self.assertEqual(original.stats["structural_derivations"],
                         reused.stats["structural_derivations"])
        self.assertGreaterEqual(cache.summary().get("certified",0),1)
        self.assertGreaterEqual(cache.summary().get("reused",0),1)
        self.assertLess(reused.stats["unification_attempts"],
                        original.stats["unification_attempts"])

    def test_ambiguous_chart_never_discards_second_analysis(self):
        lattice,grammar,cache=small_case(ambiguous=True)
        args=dict(beam=8,max_items=1000,goal_category="CLAUSE")
        reference=grammar.parse_lattice(lattice,**args)
        candidate=grammar.parse_lattice(lattice,witness_cache=cache,**args)
        self.assertEqual(cache.summary().get("certified",0),0)
        self.assertEqual(tuple(comparable(x) for x in reference.alternatives(limit=2)),
                         tuple(comparable(x) for x in candidate.alternatives(limit=2)))

    def test_child_constraints_disallow_shortcut(self):
        lattice,grammar,cache=small_case(constrained=True)
        args=dict(beam=8,max_items=1000,goal_category="CLAUSE")
        reference=grammar.parse_lattice(lattice,**args)
        candidate=grammar.parse_lattice(lattice,witness_cache=cache,**args)
        self.assertEqual(cache.summary().get("certified",0),0)
        self.assertEqual(reference.completed,candidate.completed)
        self.assertEqual(comparable(reference.best()),comparable(candidate.best()))


class RealGrammarParity(unittest.TestCase):
    def test_candidate_training_cannot_suppress_lexical_or_parse_alternatives(self):
        data=Path(__file__).resolve().parents[1]/"data"
        resources=ParserResources.from_dir(data,wordnet_dict=os.environ.get("WORDNET_DICT"))
        source=Parser(resources,cache_size=0)
        accelerated=HybridVectorParser(resources,cache_size=0,
                                       min_rule_sentences=1,
                                       prepacked_witnesses=True)
        for index,sentence in enumerate((
            "John opened the box.",
            "Mary opened the door.",
            "John gave Mary the book.",
        )):
            accelerated.observe(source.parse(sentence),source_id=str(index))
        accelerated.compile_guidance()
        for sentence in (
            "Mary opened the box.",
            "The child watched the man with a telescope.",
            "She did not open the window.",
            "The dogs barks loudly.",
        ):
            with self.subTest(sentence=sentence):
                old=source.parse(sentence).result
                new=accelerated.parse(sentence).result
                self.assertEqual(old.completed,new.completed)
                self.assertEqual(comparable(old.best()),comparable(new.best()))
                self.assertEqual(old.best().score if old.best() else None,
                                 new.best().score if new.best() else None)
                self.assertEqual(
                    {(x.span_start,x.span_end,x.category) for x in old.lattice.candidates},
                    {(x.span_start,x.span_end,x.category) for x in new.lattice.candidates},
                )
                self.assertEqual(old.stats["forest_nodes"],new.stats["forest_nodes"])
                self.assertEqual(old.stats["structural_derivations"],
                                 new.stats["structural_derivations"])


if __name__ == "__main__":
    unittest.main()
