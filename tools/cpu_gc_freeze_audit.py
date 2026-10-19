#!/usr/bin/env python3
"""Compare CPython GC with/without freezing long-lived parser resources.

No Seman2 source code, language analysis, caches, or algorithms are changed.
No explicit collections INSIDE the timed production workload. Each arm starts
from gc.collect(2), and frozen objects are unfrozen after timing for parity.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import resource
import sys
from time import perf_counter_ns, process_time_ns

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"superparser"))
from scripts.corpus_samples import choose_cases
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

OUT=ROOT/"_cpu_freeze_results"
OUT.mkdir(exist_ok=True)


def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding="utf-8")


def observed_parse(parser,lattice):
    start=process_time_ns()
    result=parser.parse_grammar_lattice(
        lattice,max_items=20_000,kbest_work_limit=100_000)
    top=result.best()
    alts=result.alternatives(limit=2)
    stats={k:v for k,v in result.stats.items() if not k.endswith("_ms") and not k.endswith("_seconds")}
    digest=sha256(json.dumps({
        "completed":result.completed,
        "best":top.as_dict() if top else None,
        "alternatives":[x.as_dict() for x in alts],
        "stats":stats},sort_keys=True,default=str).encode()).hexdigest()
    return process_time_ns()-start,digest,result.completed


def arm(parser,lattices,rows,mode):
    gc.enable()
    gc.unfreeze()
    gc.collect(2)
    if mode=="freeze_resources":
        gc.freeze()
    frozen=gc.get_freeze_count()
    starts={}
    cpu_gc=defaultdict(int)
    count_gc=Counter()
    collected_gc=Counter()
    def observer(phase,info):
        gen=str(info.get("generation",-1))
        if phase=="start":
            starts[gen]=process_time_ns()
        elif phase=="stop":
            t=starts.pop(gen,None)
            if t is not None:
                cpu_gc[gen]+=process_time_ns()-t
                count_gc[gen]+=1
                collected_gc[gen]+=info.get("collected",0)
    gc.callbacks.append(observer)
    timings=[]
    w0=perf_counter_ns()
    start=process_time_ns()
    try:
        for i,(row,lattice) in enumerate(zip(rows,lattices)):
            ns,digest,completed=observed_parse(parser,lattice)
            timings.append({"index":i,"band":row["band"],"book":row["book_id"],
                            "tokens":row["tokens"],"cpu_ns":ns,
                            "digest":digest,"completed":completed})
    finally:
        total_cpu=process_time_ns()-start
        wall=perf_counter_ns()-w0
        gc.callbacks.remove(observer)
        gc.unfreeze()
    # The post-arm final collection is measured separately, so memory cleanup
    # cannot be swept under the rug when comparing lifetime CPU.
    cleanup_start=process_time_ns()
    gc.collect(2)
    cleanup_ns=process_time_ns()-cleanup_start
    return {"mode":mode,"case_count":len(timings),"freeze_objects":frozen,
            "cpu_parse_s":round(total_cpu/1e9,6),
            "cpu_post_cleanup_s":round(cleanup_ns/1e9,6),
            "cpu_total_including_cleanup_s":round((total_cpu+cleanup_ns)/1e9,6),
            "wall_parse_s":round(wall/1e9,6),
            "gc_events_by_generation":dict(count_gc),
            "gc_cpu_s_by_generation":{k:round(v/1e9,6) for k,v in cpu_gc.items()},
            "gc_collected_objects_by_generation":dict(collected_gc),
            "gc_cpu_total_s":round(sum(cpu_gc.values())/1e9,6),
            "rss_peak_kb":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "cases":timings}


def main():
    raw,manifest=choose_cases(4)
    rows=[{"text":r["text"],"book_id":r["book_id"],"band":r["band"],
           "tokens":r["tokens"]} for r in raw]
    for t in ("John opened the box.","John gave Mary the box.",'"Hello," said Mary.'):
        rows.append({"text":t,"book_id":"fixture","band":"dialogue" if '"' in t else "04-08",
                     "tokens":len(t.split())})
    save("environment.json",{"sha":os.environ.get("GITHUB_SHA"),
         "python":sys.version,"platform":platform.platform(),
         "gc_threshold":gc.get_threshold(),"cpu_count":os.cpu_count(),
         "cases":rows,"manifest":manifest,
         "production_changes":False,
         "note":"gc.freeze() called on already-loaded long-lived Python objects only. GC remains enabled during parsing. gc.unfreeze and full GC after each arm."})
    resources=ParserResources.from_dir(
        ROOT/"superparser"/"data",wordnet_dict=os.environ["WORDNET_DICT"])
    parser=Parser(resources,cache_size=0)
    lattices=[build_lattice(r["text"],resources.lexicon) for r in rows]
    print("READY",len(lattices),"cases",flush=True)
    order=("default_a","freeze_a","freeze_b","default_b")
    measurements={}
    original_digests=None
    for name in order:
        mode="default" if name.startswith("default") else "freeze_resources"
        result=arm(parser,lattices,rows,mode)
        hashes=[r["digest"] for r in result["cases"]]
        if original_digests is None:
            original_digests=hashes
        elif hashes!=original_digests:
            save("mismatch.json",{"arm":name,"references":original_digests,"computed":hashes})
            raise AssertionError("GC freeze affected parse output")
        measurements[name]=result
        save(name+".json",result)
        print("ARM",name,"parse_cpu_s",result["cpu_parse_s"],
              "after_collection_s",result["cpu_post_cleanup_s"],
              "gc_cpu_during_s",result["gc_cpu_total_s"],
              "gc_events",result["gc_events_by_generation"],
              "frozen",result["freeze_objects"],flush=True)
    mean=lambda a,b,key:(measurements[a][key]+measurements[b][key])/2
    base=mean("default_a","default_b","cpu_parse_s")
    freeze=mean("freeze_a","freeze_b","cpu_parse_s")
    base_all=mean("default_a","default_b","cpu_total_including_cleanup_s")
    freeze_all=mean("freeze_a","freeze_b","cpu_total_including_cleanup_s")
    ratios={}
    for i,row in enumerate(rows):
        base_i=(measurements["default_a"]["cases"][i]["cpu_ns"]+
                measurements["default_b"]["cases"][i]["cpu_ns"])/2
        freeze_i=(measurements["freeze_a"]["cases"][i]["cpu_ns"]+
                  measurements["freeze_b"]["cases"][i]["cpu_ns"])/2
        ratios.setdefault(row["band"],[]).append((base_i,freeze_i))
    by_band={band:{"n":len(a),"ratio":round(sum(x[1] for x in a)/sum(x[0] for x in a),4)}
             for band,a in ratios.items() if sum(x[0] for x in a)}
    summary={
        "n":len(rows),"all_outputs_identical":True,
        "baseline_parse_cpu_s":base,
        "freeze_parse_cpu_s":freeze,
        "freeze_to_default_parse_ratio":round(freeze/base,5),
        "freeze_parse_cpu_pct_change":round((freeze/base-1)*100,3),
        "baseline_including_final_gc_s":base_all,
        "freeze_including_final_gc_s":freeze_all,
        "freeze_to_default_lifetime_ratio":round(freeze_all/base_all,5),
        "freeze_lifetime_cpu_pct_change":round((freeze_all/base_all-1)*100,3),
        "by_band":by_band,
        "arms":{k:{key:value for key,value in v.items() if key!="cases"}
                for k,v in measurements.items()},
        "warning":"Freezing global live objects impacts garbage collection and memory. This is a research experiment, not a production optimization recommendation without further lifetime and RSS validation."
    }
    save("summary.json",summary)
    print("SUMMARY",json.dumps({k:v for k,v in summary.items() if k!="arms"},sort_keys=True),flush=True)


if __name__=="__main__":
    main()
