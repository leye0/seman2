#!/usr/bin/env python3
"""Isolate Python garbage-collector costs in Seman2; no production code edits.

Compare default generational GC with periodic manual collection, using
identical explicit cleanup checkpoints and fully checked grammatical outputs.
Measures CPU time, collection callback CPU, full processing, jitter and RSS.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import random
import resource
import sys
from time import process_time_ns, perf_counter_ns
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"superparser"))
from scripts.corpus_samples import choose_cases
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

OUT = ROOT/"_cpu_gc_results"
OUT.mkdir(exist_ok=True)
BLOCK_SIZE=8


def save(name, obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),
                          encoding="utf-8")


def percent(xs,q):
    xs=sorted(xs)
    if not xs:return None
    x=(len(xs)-1)*q
    a=int(x)
    return xs[a]+(xs[min(a+1,len(xs)-1)]-xs[a])*(x-a)


def fingerprint(result):
    best=result.best()
    alts=result.alternatives(limit=2)
    meaningful={k:v for k,v in result.stats.items()
                if not k.endswith("_ms") and not k.endswith("_seconds")}
    payload={"completed":result.completed,
             "best":best.as_dict() if best else None,
             "alternatives":[a.as_dict() for a in alts],
             "stats":meaningful}
    return sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()


def run_arm(parser,lattices,rows, mode):
    """Count all production operations; per-8-sentence cleanup cost included."""
    gc.collect(2)    # outside measurement for identical starting condition
    gc.enable()
    callbacks_start={}
    gc_cpu=defaultdict(int)
    gc_count=Counter()
    reclaimed=Counter()

    def on_gc(phase, info):
        generation=info.get("generation",-1)
        if phase=="start":
            callbacks_start[generation]=process_time_ns()
        elif phase=="stop":
            begin=callbacks_start.pop(generation,None)
            if begin is not None:
                gc_cpu[str(generation)]+=process_time_ns()-begin
                gc_count[str(generation)]+=1
                reclaimed[str(generation)]+=info.get("collected",0)

    gc.callbacks.append(on_gc)
    before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    timed_cases=[]
    explicit_ns=0
    wall_total=0
    try:
        if mode=="manual_eight":
            gc.disable()
        for index,(row,lattice) in enumerate(zip(rows,lattices)):
            cpu0=process_time_ns()
            wall0=perf_counter_ns()
            parsed=parser.parse_grammar_lattice(
                lattice,max_items=20_000,kbest_work_limit=100_000)
            # Explicitly include lazy kbest.
            digest=fingerprint(parsed)
            cpudt=process_time_ns()-cpu0
            walldt=perf_counter_ns()-wall0
            timed_cases.append({
                "index":index, "book_id":row["book_id"],"band":row["band"],
                "tokens":row["tokens"],"cpu_ns":cpudt,
                "wall_ns":walldt,"digest":digest,
                "completed":parsed.completed,
                "partial_states":int(parsed.stats.get("partial_states") or 0)})
            wall_total+=walldt
            if (index+1)%BLOCK_SIZE==0 or index+1==len(rows):
                # Explicit full collection in BOTH regimes; included in total.
                tick=process_time_ns()
                gc.collect(2)
                explicit_ns+=process_time_ns()-tick
        # Keep consistent manual behavior only for the duration of each arm.
    finally:
        gc.enable()
        gc.callbacks.remove(on_gc)

    total_case_cpu=sum(x["cpu_ns"] for x in timed_cases)
    total_case_wall=sum(x["wall_ns"] for x in timed_cases)
    total_including_cleanup=total_case_cpu+explicit_ns
    return {
        "mode":mode,"case_count":len(timed_cases),
        "cpu_cases_s":round(total_case_cpu/1e9,6),
        "cpu_explicit_cleanup_s":round(explicit_ns/1e9,6),
        "cpu_total_including_cleanup_s":round(total_including_cleanup/1e9,6),
        "wall_cases_s":round(total_case_wall/1e9,6),
        "p50_per_case_ms":round(percent([x["cpu_ns"]/1e6 for x in timed_cases],.5),4),
        "p95_per_case_ms":round(percent([x["cpu_ns"]/1e6 for x in timed_cases],.95),4),
        "p99_per_case_ms":round(percent([x["cpu_ns"]/1e6 for x in timed_cases],.99),4),
        "gc_collections_by_generation":dict(gc_count),
        "gc_cpu_s_by_generation":{k:round(v/1e9,6) for k,v in gc_cpu.items()},
        "gc_collected_objects_by_generation":dict(reclaimed),
        "gc_cpu_total_s":round(sum(gc_cpu.values())/1e9,6),
        "rss_peak_kb_before_arm":before,
        "rss_peak_kb_after_arm":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "cases":timed_cases,
    }


def main():
    selected,_=choose_cases(4)
    rows=[{"text":x["text"],"book_id":x["book_id"],
           "band":x["band"],"tokens":x["tokens"]} for x in selected]
    rows.extend([
        {"text":"John opened the box.","book_id":"fixture","band":"04-08","tokens":5},
        {"text":"John gave Mary the box.","book_id":"fixture","band":"04-08","tokens":6},
        {"text":'"Hello," said Mary.',"book_id":"fixture","band":"dialogue","tokens":6},
    ])
    save("environment.json",{
        "commit":os.environ.get("GITHUB_SHA"),"python":sys.version,
        "platform":platform.platform(),"cpu_count":os.cpu_count(),
        "gc_thresholds":gc.get_threshold(),
        "mode_definition":"default=ordinary automatic Python GC plus explicit gen2 collection every 8 sentences; manual_eight=no automatic GC within arm, explicit gen2 collection every 8 sentences; CPU includes both parsing and identical cleanup checkpoints.",
        "code_modified":False, "rows":rows})
    resources=ParserResources.from_dir(ROOT/"superparser"/"data",
                                       wordnet_dict=os.environ["WORDNET_DICT"])
    parser=Parser(resources,cache_size=0)
    lattices=[build_lattice(row["text"],resources.lexicon) for row in rows]
    print("READY",len(rows),"sentences, automatic GC thresholds",gc.get_threshold(),flush=True)

    arms=("default_a","manual_a","manual_b","default_b")
    results={}
    reference=None
    for key in arms:
        mode="default" if key.startswith("default") else "manual_eight"
        r=run_arm(parser,lattices,rows,mode)
        if reference is None:
            reference=[c["digest"] for c in r["cases"]]
        else:
            for i,case in enumerate(r["cases"]):
                if case["digest"]!=reference[i]:
                    save("mismatch.json",{"arm":key,"case":i,"row":rows[i]})
                    raise AssertionError("GC regimes produced different grammatical outputs")
        results[key]=r
        save(key+".json",r)
        print(f"GC ARM {key}: CPU parse {r['cpu_cases_s']:.3f}s, "
              f"forced full cleanup {r['cpu_explicit_cleanup_s']:.3f}s, "
              f"GC observed CPU {r['gc_cpu_total_s']:.3f}s, "
              f"gc_counts {r['gc_collections_by_generation']}, "
              f"RSS peak KB {r['rss_peak_kb_after_arm']}",flush=True)

    def avg(a,b,k):
        return (results[a][k]+results[b][k])/2
    base=avg("default_a","default_b","cpu_total_including_cleanup_s")
    test=avg("manual_a","manual_b","cpu_total_including_cleanup_s")
    n=len(rows)
    pairs=[]
    for i in range(n):
        ba=(results["default_a"]["cases"][i]["cpu_ns"]
            +results["default_b"]["cases"][i]["cpu_ns"])/2
        bb=(results["manual_a"]["cases"][i]["cpu_ns"]
            +results["manual_b"]["cases"][i]["cpu_ns"])/2
        pairs.append((ba,bb))
    total_ratio=test/base if base else None
    by_band={}
    for band in sorted(set(r["band"] for r in rows)):
        ix=[i for i,x in enumerate(rows) if x["band"]==band]
        a=sum(pairs[i][0] for i in ix)
        b=sum(pairs[i][1] for i in ix)
        by_band[band]={"count":len(ix),
            "default_parse_cpu_s":round(a/1e9,4),
            "manual_parse_cpu_s":round(b/1e9,4),
            "ratio_parse_only":round(b/a,4) if a else None}
    rng=random.Random(72)
    ratios=[]
    for _ in range(600):
        ix=[rng.randrange(n) for j in range(n)]
        a=sum(pairs[i][0] for i in ix)
        b=sum(pairs[i][1] for i in ix)
        ratios.append(b/a if a else float("nan"))
    summary={
        "cases":n,"all_results_identical":True,
        "default_cpu_including_cleanup_s":base,
        "manual_cpu_including_cleanup_s":test,
        "manual_over_default_ratio":round(total_ratio,5),
        "manual_minus_default_pct":round((total_ratio-1)*100,3),
        "cpu_parse_only_ratio":round(sum(v[1] for v in pairs)/
                                     sum(v[0] for v in pairs),5),
        "parse_only_bootstrap_95pct_ratio":[round(percent(ratios,.025),5),
                                             round(percent(ratios,.975),5)],
        "per_band":by_band,
        "arms":{key:{k:v for k,v in r.items() if k!="cases"}
                for key,r in results.items()},
        "warning":"Full-GC checkpoints are included in total CPU and occur in both regimes. Memory peak from ru_maxrss is global process peak, not arm-local peak. Shared GitHub runners can experience CPU noise.",
    }
    save("summary.json",summary)
    print("GC SUMMARY",json.dumps({k:v for k,v in summary.items()
                                   if k not in ("arms","per_band")},sort_keys=True),flush=True)
    print("COMPLETE: identical parse outputs and equal GC-cleanup checkpoints",flush=True)


if __name__=="__main__":
    main()
