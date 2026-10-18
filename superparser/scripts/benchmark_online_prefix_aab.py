"""Paired A / opt-in online prefix B / repeated A, plus sampled tracemalloc.

Uses exactly one lexical lattice per sentence. All original rule-specific
packed partials, ordered derivations, k-best trees, and search-budget outcomes
must agree. The experimental option remains disabled in production.
"""
from __future__ import annotations

import argparse
import gc
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns
import tracemalloc

from scripts.benchmark_heavy_sentence_ab import BANDS,choose_cases
from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice
from seman_parser.vector_chart import VectorGrammar

ROOT=Path(__file__).resolve().parents[1]
ARMS=("reference_a","online","flat","reference_b")
METRICS=(
    "completed","budget_exceeded","kbest_budget_exceeded",
    "forest_nodes","partial_states","partial_derivations",
    "structural_derivations","partial_proposals",
    "duplicate_partial_proposals","recognition_operations",
)


def parser_for(resources,*,online:bool,flat:bool=False):
    p=Parser(resources,cache_size=0,max_items=20000)
    if online:
        old=p._vector_grammar
        p._vector_grammar=VectorGrammar(
            old.grammar,online_prefix_edges=not flat,flat_prefix_edges=flat)
        dialog=p._dialogue_vector_grammar
        if dialog is not None:
            p._dialogue_vector_grammar=VectorGrammar(
                dialog.grammar,preserve_quote_delimiters=True,
                online_prefix_edges=not flat,flat_prefix_edges=flat)
    return p


def run_one(parser,lattice):
    start=perf_counter_ns()
    result=parser.parse_grammar_lattice(
        lattice,max_items=20000,kbest_work_limit=100000)
    best=result.best()
    alt=result.alternatives(limit=2)
    elapsed=(perf_counter_ns()-start)/1e6
    stats=result.stats
    record={
        "ms":round(elapsed,5),
        "completed":result.completed,
        "best":best.as_dict() if best else None,
        "alternatives":[x.as_dict() for x in alt],
        **{key:(result.completed if key=="completed" else stats.get(key))
           for key in METRICS},
        "online_prefix_flat_enabled":stats["online_prefix_flat_enabled"],
        "online_prefix_groups":stats["online_prefix_groups"],
        "online_prefix_unique_edges":stats["online_prefix_unique_edges"],
        "online_prefix_shared_edge_hits":stats["online_prefix_shared_edge_hits"],
        "online_prefix_array_bytes":stats["online_prefix_array_bytes"],
    }
    return result,record


def checked_equal(a,b):
    for metric in METRICS:
        if a[metric]!=b[metric]:
            raise AssertionError(f"Budget/recognition mismatch: {metric}")
    if a["best"]!=b["best"] or a["alternatives"]!=b["alternatives"]:
        raise AssertionError("Grammatical/syntax/k-best mismatch")


def all_derivations_equal(original,online):
    a=original.shared_forest
    b=online.shared_forest
    if len(a.partials)!=len(b.partials):
        raise AssertionError("Canonical state count changed")
    edges=0
    for old,new in zip(a.partials,b.partials):
        if (old.rule_index,old.dot,old.start,old.end)!=(
            new.rule_index,new.dot,new.start,new.end):
            raise AssertionError(f"State mismatch at {old.partial_id}")
        x=[(z.previous_id,z.child_id) for z in old.derivations]
        y=[(z.previous_id,z.child_id) for z in new.derivations]
        if x!=y:
            raise AssertionError(f"Lost/reordered derivation at {old.partial_id}")
        edges+=len(x)
    return edges


def memory_once(parser,lattice):
    # Trace ONLY inside parsing; resources/lattice are prebuilt, shared
    # and excluded. Tracemalloc greatly distorts wall time: report it only
    # as a measure of peak Python allocations during this isolated pass.
    gc.collect()
    tracemalloc.start()
    current0,_=tracemalloc.get_traced_memory()
    result,measurement=run_one(parser,lattice)
    _,peak=tracemalloc.get_traced_memory()
    tracked_current,_=tracemalloc.get_traced_memory()
    memory={"peak_allocated_bytes":peak-current0,
            "retained_bytes":tracked_current-current0,
            "completed":measurement["completed"]}
    del result,measurement
    tracemalloc.stop()
    gc.collect()
    return memory


def quantile(xs,p):
    if not xs:
        return None
    vals=sorted(xs)
    idx=(len(vals)-1)*p
    i=int(idx)
    return round(vals[i]+(vals[min(i+1,len(vals)-1)]-vals[i])*(idx-i),4)


def cohort(rows):
    o={"n":len(rows)}
    for arm in ARMS:
        durations=[r[arm]["ms"] for r in rows]
        o[arm]={
            "sum_ms":round(sum(durations),3),
            "p50_ms":quantile(durations,.5),
            "p95_ms":quantile(durations,.95),
            "completion":sum(r[arm]["completed"] for r in rows),
            "saturations":sum(bool(r[arm]["budget_exceeded"]) for r in rows),
        }
    base=o["reference_a"]["sum_ms"]
    for arm in ("online","flat","reference_b"):
        o[arm]["ratio_vs_a"]=round(o[arm]["sum_ms"]/base,5) if base else None
    o["edge_count"]=sum(r["edges_verified"] for r in rows)
    o["unique_online_edges"]=sum(r["online"]["online_prefix_unique_edges"]
                                 for r in rows)
    o["unique_flat_edges"]=sum(r["flat"]["online_prefix_unique_edges"]
                               for r in rows)
    o["group_count"]=sum(r["online"]["online_prefix_groups"] for r in rows)
    return o


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--per-book-per-band",type=int,default=2)
    p.add_argument("--trace-samples",type=int,default=4)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    cases,sources=choose_cases(args.per_book_per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    baseline=parser_for(resources,online=False)
    experimental=parser_for(resources,online=True)
    compact=parser_for(resources,online=True,flat=True)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    with (args.out_dir/"per_sentence.jsonl").open(
        "w",encoding="utf8",buffering=1) as out:
        for i,item in enumerate(cases):
            lattice=build_lattice(item["text"],resources.lexicon,multiword_max=1)
            tasks=[("reference_a",baseline),("online",experimental),
                   ("flat",compact),("reference_b",baseline)]
            if i%2:
                tasks.reverse()
            runs={}
            result={}
            for name,parser in tasks:
                result[name],runs[name]=run_one(parser,lattice)
            checked_equal(runs["reference_a"],runs["online"])
            checked_equal(runs["reference_a"],runs["flat"])
            checked_equal(runs["reference_a"],runs["reference_b"])
            verified=all_derivations_equal(
                result["reference_a"],result["online"])
            if all_derivations_equal(result["reference_a"],result["flat"])!=verified:
                raise AssertionError("Flat online storage changed ordered edges")
            if verified!=runs["online"]["partial_derivations"]:
                raise AssertionError("Missing original partial derivations")
            for parsed in result.values():
                del parsed
            del result
            traced=None
            if args.trace_samples and i%max(1,len(cases)//args.trace_samples)==0:
                traced={
                    "reference":memory_once(baseline,lattice),
                    "online":memory_once(experimental,lattice),
                    "flat":memory_once(compact,lattice),
                }
            row={
                "index":i,"book_id":item["book_id"],"band":item["band"],
                "tokens":item["tokens"],"text":item["text"],
                "sentence_sha256":sha256(item["text"].encode()).hexdigest(),
                "edges_verified":verified,"memory_sample":traced,
                **{k:{field:value for field,value in v.items()
                      if field not in ("best","alternatives")}
                   for k,v in runs.items()}
            }
            rows.append(row)
            out.write(json.dumps(row,ensure_ascii=False)+"\n")
            if (i+1)%8==0:
                print("ONLINE_PREFIX_PROGRESS",json.dumps({
                    "seen":i+1,"verified":sum(r["edges_verified"] for r in rows),
                    "online_groups":sum(r["online"]["online_prefix_groups"]
                                        for r in rows),
                }),flush=True)
    memory=[r for r in rows if r["memory_sample"] is not None]
    report={
        "schema":"online-shared-prefix-matched-aab-v1",
        "sources":sources,
        "all":cohort(rows),
        "by_band":{band:cohort([r for r in rows if r["band"]==band])
                   for band,_,_ in BANDS},
        "memory_samples":[{
            "band":r["band"],"book_id":r["book_id"],
            "reference_peak_bytes":r["memory_sample"]["reference"]["peak_allocated_bytes"],
            "online_peak_bytes":r["memory_sample"]["online"]["peak_allocated_bytes"],
            "flat_peak_bytes":r["memory_sample"]["flat"]["peak_allocated_bytes"],
            "flat_over_reference":round(
                r["memory_sample"]["flat"]["peak_allocated_bytes"]/
                r["memory_sample"]["reference"]["peak_allocated_bytes"],5)
              if r["memory_sample"]["reference"]["peak_allocated_bytes"] else None,
            "online_over_reference":round(
                r["memory_sample"]["online"]["peak_allocated_bytes"]/
                r["memory_sample"]["reference"]["peak_allocated_bytes"],5)
              if r["memory_sample"]["reference"]["peak_allocated_bytes"] else None,
        } for r in memory],
        "notes":[
            "Both optional modes intern edges AS THEY ARE CREATED, not as posthoc compaction.",
            "Flat mode avoids per-group Python objects and per-variant Python arrays.",
            "Every canonical partial and every ordered derivation was reconstructed and compared.",
            "Grammatical trees and first two k-best analyses were matched before timing summary.",
            "Original state-count and forest-budget accounting remains unchanged.",
            "Tracemalloc starts after lexicon/lattice setup; traced passes are NOT used for timing.",
            "Traced Python allocations exclude extension/native allocator memory and full RSS.",
            "Only 32 equally stratified novel sentences; results are a first pilot, not rollout proof.",
            "A/A repetition is required to detect GitHub CI runner timing drift.",
            "The option remains OFF in canonical production."
        ],
    }
    (args.out_dir/"summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("ONLINE_PREFIX_FINAL",json.dumps(report),flush=True)


if __name__=="__main__":
    main()
