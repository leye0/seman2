"""Fast, bounded microbenchmark of COMPLETE structural snapping (no lexing).

A direct positional index hit still has to select lexical candidates,
validate the remembered grammar and materialize a ChartItem. Report this
separately from raw index lookup, to avoid pretending they have the
same cost.
"""
from __future__ import annotations

from collections import Counter
import json
from statistics import median
from time import perf_counter_ns
from random import Random

from research.verbnet_lr.positional_template_index import PositionalTemplateIndex
from research.verbnet_lr.full_structure_snap import FullStructureSnapIndex
from seman_parser.engine import ParserResources
from seman_parser.features import FeatureStructure, Variable
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.segmentation import LexicalCandidate, LexicalLattice, Token
from seman_parser.predictive import CompactNode, PredictiveParser
from seman_parser.symbols import intern
from scripts.benchmark_snap_index_only import make_signatures,percentile_ns


def grammar_case(n):
    s=lambda cat, **k:RuleSymbol(cat,FeatureStructure.build(k))
    rules=[GrammarRule(f"clause-{n}",tuple(s("N") for _ in range(n)),
         s("CLAUSE"))]
    grammar=Grammar(rules)
    resources=ParserResources(grammar,None,None)
    nodes=[]
    cand=[]
    tokens=[]
    index=0
    for i in range(n):
        word="w"+str(i)
        start=index
        end=index+len(word)
        token=Token(i,start,end,word)
        c=LexicalCandidate(start,end,word,word,"N",
                           FeatureStructure.build({"number":"singular"}),
                           score=1.0)
        tokens.append(token)
        cand.append(c)
        nodes.append(CompactNode("N",intern("N"),start,end,c.features,
                                 frozenset(c.features.keys()),c.score,
                                 candidate=c))
        index=end+1
    text=" ".join(t.text for t in tokens)
    lattice=LexicalLattice(text,tuple(tokens),tuple(cand))
    root=PredictiveParser._reduce(rules[0],tuple(nodes))
    if root is None:
        raise AssertionError("Invalid test grammar")
    item=PredictiveParser(resources)._materialize(root)
    memory=FullStructureSnapIndex(resources)
    own=memory.observe(item,lattice=lattice)

    # The same pattern count as Gutenberg, but no extra grammatically valid
    # templates are claimed. Irrelevant category sequences stress retrieval.
    for i,sig in enumerate(make_signatures(17391)):
        memory._positional_index.add(sig,i+1)
    return memory,lattice,own


def run():
    result={}
    for n in (8,16,24):
        memory,lattice,own=grammar_case(n)
        samples=[]
        found=True
        for _ in range(1300):
            start=perf_counter_ns()
            r=memory.match(lattice,max_templates_checked=32,max_states=8192,
                           max_variants=4,max_reductions=512)
            samples.append(perf_counter_ns()-start)
            if not r.complete or r.matches[0].template_id!=own:
                found=False
        sample=samples[100:]
        result[str(n)+"_words"]={
            "hits_correct":found,"p50_ms":percentile_ns(sample,.5),
            "p95_ms":percentile_ns(sample,.95),
            "p99_ms":percentile_ns(sample,.99),
            "over_1ms":sum(x>1_000_000 for x in sample),
        }
    print("FINAL_COMPLETE_MATCH",json.dumps(result,separators=(",",":")),flush=True)
    return result

if __name__=="__main__":
    run()
