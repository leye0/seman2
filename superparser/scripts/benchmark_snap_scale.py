"""Synthetic scaling probe for the full-structure trie (NOT corpus coverage).

A deliberately highly ambiguous, feature-free toy CFG admits thousands of
different complete X binary trees over the very SAME 13 N lexical slots.
This is a worst-case terminal-bucket stress test, not a dataset of genuine
natural-language sentences and not independently verified linguistic gold.

Use this before designing a larger cache: benchmark 100 / 1k / 10k / 100k
shapes under the actual FullStructureSnapIndex in a fresh CI runner.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import gc
import json
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.full_structure_snap import (
    FullStructureSnapIndex, Structure, Template, _Trie,
)
from seman_parser.engine import ParserResources
from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.segmentation import LexicalCandidate, LexicalLattice, Token


def toy():
    empty = FeatureStructure.empty()
    x, n, clause = (RuleSymbol(k, empty) for k in ("X", "N", "CLAUSE"))
    rules = Grammar((
        GrammarRule("clause_x", (x,), clause),
        GrammarRule("x_pair", (x, x), x),
        GrammarRule("x_n", (n,), x),
    ))
    resources = ParserResources(rules, None, None)
    return FullStructureSnapIndex(resources, max_templates=1_000_000)


@lru_cache(maxsize=20)
def _subtrees(length: int):
    leaf = Structure("X", "x_n", (Structure("N"),))
    if length == 1:
        return (leaf,)
    found = []
    for i in range(1, length):
        for left in _subtrees(i):
            for right in _subtrees(length-i):
                found.append(Structure("X","x_pair",(left,right)))
    return tuple(found)


def _shapes(length=13):
    # Do not cache the full n=13 Catalan set: 208,012 possibilities.
    for i in range(1,length):
        for left in _subtrees(i):
            for right in _subtrees(length-i):
                yield Structure("CLAUSE", "clause_x",
                                (Structure("X","x_pair",(left,right)),))


def _lattice(count: int):
    tokens = tuple(Token(i,i*2,i*2+1,"n") for i in range(count))
    candidates = tuple(LexicalCandidate(
        t.start,t.end,"n","n","N",FeatureStructure.empty())
        for t in tokens)
    return LexicalLattice(" ".join("n" for _ in tokens),tokens,candidates)


def rss_mb():
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1])/1024,3)
    except OSError:
        pass
    return None


def snapshot(index, lattice, runs=15):
    measurements={}
    for cap in (1,8):
        # Same grammar-unifying actual recognition path, with different
        # bounded number of returned trees. Everything else stays fixed.
        times=[]
        for _ in range(runs):
            started=perf_counter()
            hit=index.match(lattice,max_templates_checked=cap,
                            max_reductions=512,max_states=1024,
                            max_variants=2)
            times.append((perf_counter()-started)*1000)
            assert len(hit.matches)==cap, (cap,len(hit.matches),hit.reason)
            assert hit.incomplete, "Remaining parses must remain available"
        times.sort()
        measurements[f"top_{cap}"]={
            "p50_ms":round(times[(len(times)-1)//2],5),
            "p95_ms":round(times[int((len(times)-1)*.95)],5),
            "candidate_templates":hit.candidate_templates,
            "returned":len(hit.matches),
            "incomplete":hit.incomplete,
        }
    late=[]
    for _ in range(runs):
        started=perf_counter()
        tail=index.match(lattice,max_templates_checked=1,
                         template_offset=len(index.templates)-1,
                         max_reductions=512)
        late.append((perf_counter()-started)*1000)
        assert len(tail.matches)==1 and tail.next_template_offset is None
    late.sort()
    measurements["last_template"]={
        "p50_ms":round(late[(len(late)-1)//2],5),
        "p95_ms":round(late[int((len(late)-1)*.95)],5),
    }
    return measurements


def run(sizes=(100,1000,10000,100000)):
    sizes=tuple(sorted(set(sizes)))
    if not sizes or sizes[0]<1 or sizes[-1]>200_000:
        raise ValueError("Invalid synthetic experiment sizes")
    index=toy()
    lattice=_lattice(13)
    baseline_rss=rss_mb()
    started=perf_counter()
    snapshots=[]
    counter=0
    # Directly insert into the same index representation as observe(); toy
    # binary grammar guarantees every generated structure is a valid CFG
    # derivation. No real sentences or gold labels are faked.
    state=index._root
    cats=("N",)*13
    for category in cats:
        state=state.edges.setdefault(category,_Trie())
    for shape in _shapes():
        if counter>=sizes[-1]:
            break
        if shape in index._by_shape:
            continue
        template_id=len(index.templates)
        index._by_shape[shape]=template_id
        index.templates.append(Template(shape,cats))
        state.template_ids.append(template_id)
        # Scaling fixtures bypass observe(); maintain the new positional
        # index explicitly so lookups test the exact same templates.
        index._positional_index.add(cats,template_id)
        counter+=1
        if counter in sizes:
            gc.collect()
            snapshots.append({
                "templates":counter,
                "index_build_elapsed_s":round(perf_counter()-started,4),
                "rss_mb":rss_mb(),
                "query":snapshot(index,lattice),
            })
    if counter!=sizes[-1]:
        raise RuntimeError("Insufficient distinct grammar shapes")
    return {
        "schema":"seman2-synthetic-whole-template-scale-v1",
        "grammar":"CLAUSE->X, X->N or X X; all leaves N; 13 lexical tokens",
        "source":"synthetic CFG derivations; NOT WordNet nor corpus gold",
        "baseline_process_rss_mb":baseline_rss,
        "snapshots":snapshots,
        "limitations":[
            "Same lexical category sequence for all shapes is pathological ambiguity, not typical corpus distribution.",
            "Only eight matches are materialized per query; incomplete=True preserves uncertainty.",
            "VmRSS is whole-process resident memory and includes grammar, Python and generator caches.",
            "Structure objects are Python dataclasses, NOT a packed 20M-template production representation.",
            "Toy feature-free grammar does not establish linguistic correctness of natural-language attachments.",
        ]
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sizes",default="100,1000,10000,100000")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    report=run(tuple(int(x) for x in args.sizes.split(",")))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in
                     ("baseline_process_rss_mb","snapshots")},indent=2))
