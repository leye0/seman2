#!/usr/bin/env python3
"""Compare *production-default* Seman2 Parser.parse() with GC policy on/off.

Exactly 1000 distinct sentences, the same corpus and order in independent
Python processes, all Parser constructor parameters left at their defaults.
No custom max_items / kbest_work_limit. No monkeypatches / explicit GC sweeps.
Enable/disable the shipping GC policy only via SEMAN2_DISABLE_GC_FREEZE.
Evidence is persisted every 25 sentences to survive interruption.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import resource
import sys
from time import process_time_ns, perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "superparser"))

from scripts.corpus_samples import choose_cases
from seman_parser.engine import Parser, ParserResources
from seman_parser.runtime_gc import _WORDNET_POSITIONS
import seman_parser.runtime_gc as runtime_gc

OUT = ROOT / "_gc_production_1000"
OUT.mkdir(exist_ok=True)
PAGE = os.sysconf("SC_PAGE_SIZE")

def resident_mib():
    try:
        return int(Path("/proc/self/statm").read_text().split()[1]) * PAGE / (1024**2)
    except (OSError, ValueError, IndexError):
        return None

def write_json(path, obj):
    temp = OUT / (path + ".tmp")
    temp.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True,default=str),encoding="utf-8")
    temp.replace(OUT / path)

def pctl(seq,q):
    ordered = sorted(seq)
    if not ordered:
        return None
    p = (len(ordered)-1)*q
    i = int(p)
    return ordered[i] + (ordered[min(i+1,len(ordered)-1)]-ordered[i])*(p-i)

def sample():
    # Recreate exact balanced 1000 from original 1000-sentence GC benchmark,
    # archived in git history. Never silently replace a sentence.
    selected, manifest = choose_cases(70)
    groups = defaultdict(list)
    seen = set()
    for row in selected:
        normalized = " ".join(row["text"].casefold().split())
        if normalized in seen:
            continue
        seen.add(normalized)
        groups[(row["book_id"],row["band"])].append(row)
    keys = sorted(groups)
    if len(keys)!=16:
        raise AssertionError(f"Expected 4 Gutenberg books x 4 length bands: {len(keys)}")
    counts = [63 if i < 8 else 62 for i in range(len(keys))]
    for key,n in zip(keys,counts):
        if len(groups[key])<n:
            raise AssertionError(f"Insufficient distinct sentences {key} {len(groups[key])} < {n}")
    groups = {key:groups[key][:count] for key,count in zip(keys,counts)}
    result=[]
    for i in range(max(counts)):
        for key in keys:
            if i<len(groups[key]):
                row=groups[key][i]
                result.append({"book_id":row["book_id"],"band":row["band"],
                    "ordinal":row["ordinal"],"tokens":row["tokens"],
                    "text":row["text"]})
    assert len(result)==1000
    return result, manifest

def canonical_result(report):
    result=report.result
    best=result.best()
    alternatives=result.alternatives(limit=2)
    stats={k:v for k,v in result.stats.items()
           if not k.endswith("_ms") and not k.endswith("_seconds")}
    payload={
       "completed":bool(result.completed),
       "best":best.as_dict() if best else None,
       "alternatives":[a.as_dict() for a in alternatives],
       "stats":stats,
    }
    fingerprint=sha256(json.dumps(payload,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()
    return fingerprint, payload

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--mode",choices=("normal","optimized"),required=True)
    cli.add_argument("--run",type=int,default=1)
    cli.add_argument("--max-rss-mib",type=int,default=6100)
    args=cli.parse_args()
    disabled=os.environ.get("SEMAN2_DISABLE_GC_FREEZE")=="1"
    assert disabled == (args.mode=="normal"),"Mode must match GC opt-out env"
    assert os.environ.get("PYTHONHASHSEED")=="0","Stable hash seed required for cross-process output parity"

    cases, manifest=sample()
    source_sig=sha256("\n".join(row["text"] for row in cases).encode()).hexdigest()
    output_name=f"{args.mode}_{args.run}.json"
    res=ParserResources.from_dir(ROOT/"superparser"/"data",wordnet_dict=os.environ["WORDNET_DICT"])
    parser=Parser(res)  # all production defaults, including cache_size=2048, max_items=50k
    assert parser.max_items==50_000 and parser.beam==80
    assert parser._parse_cache._capacity==2048
    assert parser._complexity_policy is None

    gc_events=Counter()
    gc_cpu_ns=Counter()
    starts={}
    def callback(phase,info):
        generation=str(info.get("generation",-1))
        if phase=="start":
            starts[generation]=process_time_ns()
        elif phase=="stop":
            t=starts.pop(generation,None)
            if t is not None:
                gc_cpu_ns[generation]+=process_time_ns()-t
                gc_events[generation]+=1

    samples=[]
    checkpoints=[]
    started_cpu=process_time_ns()
    started_wall=perf_counter_ns()
    gc.callbacks.append(callback)
    status="running"
    failure=None

    def snapshot():
        durations=[x["cpu_ms"] for x in samples]
        partial_failed=Counter()
        for x in samples:
            if not x["completed"]:
                if x["budget_exceeded"]:
                    partial_failed["recognition_budget_exceeded"]+=1
                elif x["kbest_budget_exceeded"]:
                    partial_failed["kbest_budget_exceeded"]+=1
                else:
                    partial_failed["no_completed_root_other"]+=1
        return {
            "status":status,
            "mode":args.mode,"run":args.run,"cases_done":len(samples),
            "cpu_seconds":round((process_time_ns()-started_cpu)/1e9,5),
            "wall_seconds":round((perf_counter_ns()-started_wall)/1e9,5),
            "cpu_gc_seconds":round(sum(gc_cpu_ns.values())/1e9,5),
            "cpu_gc_generations":{k:round(v/1e9,5) for k,v in gc_cpu_ns.items()},
            "gc_events":dict(gc_events),
            "completed":sum(int(x["completed"]) for x in samples),
            "failure_causes":dict(partial_failed),
            "rss_mib":resident_mib(),
            "maxrss_mib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
            "freeze_count":gc.get_freeze_count(),
            "freeze_applied_by_engine":runtime_gc._frozen,
            "p50_cpu_ms":pctl(durations,.5),
            "p95_cpu_ms":pctl(durations,.95),
            "p99_cpu_ms":pctl(durations,.99),
        }

    try:
        for i,row in enumerate(cases):
            before_cpu=process_time_ns()
            before_wall=perf_counter_ns()
            # Exact normal public entrypoint, no special budgets or changed
            # caching. Returns ParseReport.
            report=parser.parse(row["text"])
            fingerprint,payload=canonical_result(report)
            cpu_ns=process_time_ns()-before_cpu
            wall_ns=perf_counter_ns()-before_wall
            stat=payload["stats"]
            samples.append({
                "i":i,"book_id":row["book_id"],"band":row["band"],
                "tokens":row["tokens"],
                "completed":payload["completed"],
                "budget_exceeded":bool(stat.get("budget_exceeded")),
                "kbest_budget_exceeded":bool(stat.get("kbest_budget_exceeded")),
                "goal_saturated":bool(stat.get("goal_saturated")),
                "forest_nodes":stat.get("forest_nodes"),
                "partial_states":stat.get("partial_states"),
                "engine":stat.get("engine"),
                "cpu_ms":round(cpu_ns/1e6,5),
                "wall_ms":round(wall_ns/1e6,5),
                "fingerprint":fingerprint,
            })
            del report, payload
            if (i+1)%25==0 or i+1==1000:
                record=snapshot()
                record["after_sentence"]=i+1
                checkpoints.append(record)
                print("PROGRESS",args.mode,args.run,i+1,"/1000",
                      "CPU",round(record["cpu_seconds"],2),
                      "GC",round(record["cpu_gc_seconds"],2),
                      "RSS",round(record["rss_mib"],1) if record["rss_mib"] else None,
                      "complete",record["completed"],flush=True)
                # Checkpoint on disk for clarity if the runner stops.
                write_json(output_name,{
                    "meta":{"platform":platform.platform(),"python":sys.version,
                            "git_commit":os.environ.get("GITHUB_SHA"),
                            "gc_opt_out":disabled,
                            "parser_max_items":parser.max_items,
                            "parser_cache_capacity":parser._parse_cache._capacity,
                            "parse_entrypoint":"Parser.parse",
                            "kbest_work_limit":"unset, production default",
                            "seed":os.environ["PYTHONHASHSEED"],
                            "source_sha256":source_sig,"corpus":manifest},
                    "status":status,"statistics":record,
                    "checkpoints":checkpoints,"samples":samples})
                if record["rss_mib"] is not None and record["rss_mib"] > args.max_rss_mib:
                    raise MemoryError(f"RSS > {args.max_rss_mib}MiB; aborting to protect CI runner")
        status="success"
    except BaseException as exc:
        status="failure"
        failure={"name":type(exc).__name__,"reason":str(exc),"at":len(samples)}
        raise
    finally:
        gc.callbacks.remove(callback)
        final=snapshot()
        if failure:
            final["failure"]=failure
        write_json(output_name,{
            "meta":{"platform":platform.platform(),"python":sys.version,
                    "git_commit":os.environ.get("GITHUB_SHA"),
                    "gc_opt_out":disabled,
                    "parser_max_items":parser.max_items,
                    "parser_cache_capacity":parser._parse_cache._capacity,
                    "parse_entrypoint":"Parser.parse",
                    "kbest_work_limit":"unset, production default",
                    "seed":os.environ["PYTHONHASHSEED"],
                    "source_sha256":source_sig,"corpus":manifest},
            "status":status,"statistics":final,
            "checkpoints":checkpoints,"samples":samples})
        print("FINAL",args.mode,args.run,json.dumps(final,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
