"""Hard-gated structural index matching benchmark (no parsing or reconstruction).

Populate 17,391 observed-like structural POS signatures (synthetic category
sequences, NOT independently grammatical trees). Benchmark 10,000 indexed
lookups of both present and absent signatures, with lexical alternatives.
The timer covers ONLY lookup after POS candidates are already supplied.

Synthetic signatures are used intentionally: running canonical VectorGrammar
for 50k training sentences is orthogonal to testing index complexity.
"""
from __future__ import annotations

import argparse
import json
from random import Random
from statistics import median
from time import perf_counter_ns

from research.verbnet_lr.positional_template_index import PositionalTemplateIndex


POS = (
    "N","V","DET","PRONOUN","NP","VP","ADJ","ADV","PREP","AUX",
    "COPULA","CONJ","MODAL","PARTICLE","DEGREE","NUM","PROPER",
    "COMP-THAT","INFINITIVE","RELATIVE","ADV-MOD","POSS","NEG",
)


def percentile_ns(numbers, q):
    ordered=sorted(numbers)
    p=(len(ordered)-1)*q
    j=int(p)
    return round((ordered[j]+(ordered[min(j+1,len(ordered)-1)]-ordered[j])*(p-j))/1e6,5)


def make_signatures(n, seed=2049):
    rng=Random(seed)
    signatures=[]
    unique=set()
    while len(signatures)<n:
        length=rng.randrange(4,38)
        categories=tuple(rng.choice(POS) for _ in range(length))
        if categories not in unique:
            signatures.append(categories)
            unique.add(categories)
    return signatures


def measure(n=17391, queries=10000, max_ms=1.0):
    index=PositionalTemplateIndex()
    signatures=make_signatures(n)
    for i,signature in enumerate(signatures):
        index.add(signature,i)
    rng=Random(71)
    hits,misses=[],[]
    fail_count=0
    for kind in ("hit","miss"):
        for i in range(queries//2):
            k=rng.randrange(n)
            signature=signatures[k]
            categories=[]
            for cat in signature:
                if kind=="miss" and len(categories)==0:
                    categories.append(("NONEXISTENT_CATEGORY",))
                else:
                    # Ambiguous POS positions; includes the true signature.
                    alt=rng.choice(POS)
                    categories.append((cat,alt) if alt!=cat else (cat,))
            # Warm-up and time ONLY index bitset intersection+ID retrieval,
            # not construction of the lexical POS alternatives.
            start=perf_counter_ns()
            found=index.lookup(categories,limit=32)
            elapsed=perf_counter_ns()-start
            if kind=="hit":
                if k not in found.template_ids and found.total<=32:
                    fail_count+=1
                hits.append(elapsed)
            else:
                if found.total:
                    fail_count+=1
                misses.append(elapsed)
    def metrics(data):
        return {
            "count":len(data),
            "p50_ms":percentile_ns(data,.5),
            "p95_ms":percentile_ns(data,.95),
            "p99_ms":percentile_ns(data,.99),
            "worst_ms":round(max(data)/1e6,5),
            "over_1ms":sum(t>1_000_000 for t in data),
        }
    result={
        "case":"synthetic-POS-patterns-index-only",
        "templates":n,
        "queries":queries,
        "candidate_categories_per_slot":"1–2",
        "includes_lexing":False,
        "includes_grammar_unification":False,
        "includes_tree_reconstruction":False,
        "hit":metrics(hits),
        "miss":metrics(misses),
        "mismatch_count":fail_count,
        "threshold_p95_ms":max_ms,
    }
    result["pass"]=(
        not fail_count and
        result["hit"]["p95_ms"]<max_ms and
        result["miss"]["p95_ms"]<max_ms and
        result["hit"]["over_1ms"] == 0 and
        result["miss"]["over_1ms"] == 0
    )
    print("FINAL",json.dumps(result,separators=(",",":")),flush=True)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--templates",type=int,default=17391)
    parser.add_argument("--queries",type=int,default=10000)
    parser.add_argument("--max-ms",type=float,default=1.0)
    opts=parser.parse_args()
    report=measure(opts.templates,opts.queries,opts.max_ms)
    if not report["pass"]:
        raise SystemExit("FAIL: structural direct-index p95 >=1 ms or incorrect matching")
