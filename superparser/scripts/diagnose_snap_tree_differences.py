"""Diagnose why whole-tree ChartItems differ after structural snap.

Run vector parse on exact Gutenberg corpus, record template, rebuild with the
structure trie. Separate rule topology, selected lexical readings, feature
propagation and syntax annotations; never report book prose.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
from scripts.benchmark_snap_50k_two_pass import (
    spread_novel_corpus, deadline, canonical, lexical_tree,
)
from research.verbnet_lr.full_structure_snap import FullStructureSnapIndex
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]


def signature(node,part):
    if node.lexical_candidate is not None:
        c=node.lexical_candidate
        if part=="topology":
            data=(node.category,node.start,node.end,None)
        elif part=="lexical":
            data=(c.category,c.lemma,tuple(c.sense_ids),c.features.as_dict())
        elif part=="feature":
            data=node.features.as_dict()
        else:
            data=node.syntax.as_dict()
        return (data,())
    if part=="topology":
        data=(node.category,node.start,node.end,node.rule_id)
    elif part=="lexical":
        data=None
    elif part=="feature":
        data=node.features.as_dict()
    else:
        data=node.syntax.as_dict()
    return (data,tuple(signature(child,part) for child in node.children))


def first_difference(a,b,part,path=()):
    av,bv=signature(a,part)[0],signature(b,part)[0]
    if canonical(av)!=canonical(bv):
        return {"path":path,"category":a.category,
                "left_type":type(av).__name__,"right_type":type(bv).__name__,
                "left_preview":canonical(av)[:200],
                "right_preview":canonical(bv)[:200]}
    for i,(ch1,ch2) in enumerate(zip(a.children,b.children)):
        diff=first_difference(ch1,ch2,part,path+(i,))
        if diff is not None:
            return diff
    return None


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--wordnet-dir",required=True)
    parser.add_argument("--count",type=int,default=150)
    parser.add_argument("--strict",action="store_true",help="Fail if any remembered tree is lost or has any changed features/syntax")
    a=parser.parse_args()
    corpus,_=spread_novel_corpus(a.count,32)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=a.wordnet_dir)
    parser=Parser(resources,cache_size=0,max_items=20000)
    memory=FullStructureSnapIndex(resources)
    original={}
    totals=Counter()
    for i,row in enumerate(corpus):
        lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
        try:
            with deadline(.35):
                report=parser._vector_grammar.parse_lattice(
                    lattice,beam=parser.beam,max_items=20000,
                    goal_category="CLAUSE")
                item=report.best() if report.completed else None
        except Exception:
            item=None
        if item is None:
            continue
        try:
            idx=memory.observe(item,lattice=lattice)
        except ValueError:
            continue
        original[i]=(idx,item)
    details={}
    for i,(idx,item) in original.items():
        lattice=build_lattice(corpus[i]["text"],resources.lexicon,multiword_max=1)
        match=memory.match(lattice,max_templates_checked=512,
            max_states=16384,max_variants=32,max_reductions=8192)
        own=next((m.item for m in match.matches if m.template_id==idx),None)
        if own is None:
            totals["unmatched"]+=1
            continue
        totals["matched"]+=1
        for part in ("topology","lexical","feature","syntax"):
            same=canonical(signature(item,part))==canonical(signature(own,part))
            totals[part+"_same"]+=int(same)
            if not same and part not in details:
                details[part]=first_difference(item,own,part)
    print("FINAL",json.dumps({
        "indexed":len(original),"totals":dict(totals),"first_differences":details,
    }),flush=True)
    if a.strict:
        n=len(original)
        if n==0 or totals["matched"]!=n or any(
            totals[f"{part}_same"]!=n
            for part in ("topology","lexical","feature","syntax")
        ):
            raise SystemExit("STRICT FIDELITY FAILURE: stored grammatical variables or syntax not fully restored")


if __name__=="__main__":
    main()
