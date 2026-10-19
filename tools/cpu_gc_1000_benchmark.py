#!/usr/bin/env python3
"""Seman2: 1,000-sentence paired CPU/GC benchmark, without parser modifications.

Experiments on a single fixed, balanced corpus of 1,000 distinct Gutenberg
sentences, four sequential arms: default / freeze / freeze / default.
Each arm does lexical construction, canonical parsing, lazy best/alternatives,
and output signatures. No parser cache, no persisted forests, no forced
garbage collections during each timed arm.

gc.freeze() is PROCESS-GLOBAL. The experimental freeze happens only after
resources, WordNet, and benchmark input have been loaded; gc.unfreeze() and
explicit cleanup are outside the timed arm. This tests a possible implementation
choice, NOT an automatically safe production configuration.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gc
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import sys
from time import perf_counter_ns, process_time_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "superparser"))
from scripts.corpus_samples import BANDS, choose_cases
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

OUT = ROOT / "_cpu_gc_1000"
OUT.mkdir(exist_ok=True)
PAGE_BYTES = os.sysconf("SC_PAGE_SIZE")
ARMS = ("default_a", "freeze_a", "freeze_b", "default_b")


def write(path, obj):
    (OUT / path).write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, default=str),
        encoding="utf-8")


def resident_bytes():
    # Linux only; ru_maxrss is NOT an arm-specific peak.
    try:
        with open("/proc/self/statm", encoding="ascii") as f:
            return int(f.read().split()[1]) * PAGE_BYTES
    except (OSError, IndexError, ValueError):
        return None


def percentile(values, q):
    vals = sorted(values)
    if not vals:
        return None
    i = (len(vals) - 1) * q
    left = int(i)
    return vals[left] + (vals[min(left+1, len(vals)-1)] - vals[left]) * (i-left)


def cases_1000():
    # Corpus files already checked in; 4 books x 4 token bands.
    selected, manifest = choose_cases(70)
    groups = defaultdict(list)
    seen = set()
    for row in selected:
        normalized = " ".join(row["text"].casefold().split())
        if normalized in seen:
            continue
        seen.add(normalized)
        groups[(row["book_id"], row["band"])].append(row)
    keys = sorted(groups)
    if len(keys) != 16:
        raise AssertionError(f"Expected 16 book × length groups, got {len(keys)}")
    # 8 groups x 63 + 8 groups x 62 = 1,000; fixed, balanced, interleaved.
    desired = [63 if i < 8 else 62 for i in range(len(keys))]
    for key, n in zip(keys, desired):
        if len(groups[key]) < n:
            raise AssertionError(f"Too few unique Gutenberg sentences in {key}: {len(groups[key])}/{n}")
    chosen_by_group = {key: groups[key][:n] for key,n in zip(keys,desired)}
    rows = []
    for i in range(max(desired)):
        for key in keys:
            group = chosen_by_group[key]
            if i < len(group):
                row=group[i]
                rows.append({
                    "book_id":row["book_id"],"band":row["band"],
                    "ordinal":row["ordinal"],"tokens":row["tokens"],
                    "text":row["text"], "text_sha256":sha256(row["text"].encode()).hexdigest()})
    assert len(rows) == 1000
    return rows, manifest


def digest_of(result):
    """Exact output/counter parity; exclude only time-based metrics."""
    best = result.best()
    alternatives = result.alternatives(limit=2)
    stats = {k:v for k,v in result.stats.items()
             if not k.endswith("_ms") and not k.endswith("_seconds")}
    payload = {
        "completed": result.completed,
        "best": best.as_dict() if best else None,
        "alternatives": [item.as_dict() for item in alternatives],
        "stats": stats,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, default=str,
                               ensure_ascii=False).encode()).hexdigest()
    return digest, result.completed, stats


def run_arm(name, rows, parser, reference):
    gc.enable()
    gc.unfreeze()
    gc.collect(2)                 # identical fresh baseline, outside timed area
    if name.startswith("freeze"):
        gc.freeze()
    frozen = gc.get_freeze_count()
    gc_times = defaultdict(int)
    gc_events = Counter()
    gc_collected = Counter()
    gc_uncollectable = Counter()
    active = {}
    def on_gc(phase, info):
        generation = str(info.get("generation", -1))
        if phase == "start":
            active[generation] = process_time_ns()
        else:
            start = active.pop(generation, None)
            if start is not None:
                gc_times[generation] += process_time_ns() - start
                gc_events[generation] += 1
                gc_collected[generation] += info.get("collected", 0)
                gc_uncollectable[generation] += info.get("uncollectable", 0)

    gc.callbacks.append(on_gc)
    resident_start = resident_bytes()
    per_case, snapshots = [], []
    t0c, t0w = process_time_ns(), perf_counter_ns()
    mismatch = None
    try:
        for i,row in enumerate(rows):
            startc = process_time_ns()
            startw = perf_counter_ns()
            lattice = build_lattice(row["text"], parser.resources.lexicon)
            result = parser.parse_grammar_lattice(
                lattice, max_items=20_000, kbest_work_limit=100_000)
            digest, completed, stats = digest_of(result)
            cpu_ns = process_time_ns()-startc
            wall_ns = perf_counter_ns()-startw
            if reference is not None and digest != reference[i]:
                mismatch = {"arm":name, "index":i, "book_id":row["book_id"],
                            "ordinal":row["ordinal"], "text":row["text"],
                            "expected":reference[i], "observed":digest}
                write("mismatch.json", mismatch)
                raise AssertionError(f"Grammar/output parity mismatch {name}, sentence #{i}")
            per_case.append({
                "i":i, "sha256":row["text_sha256"],"book":row["book_id"],
                "band":row["band"], "tokens":row["tokens"],
                "cpu_ms":round(cpu_ns/1e6,5),
                "wall_ms":round(wall_ns/1e6,5),
                "completed":bool(completed),
                "digest":digest,
                "forest_nodes":int(stats.get("forest_nodes") or 0),
                "partial_states":int(stats.get("partial_states") or 0),
            })
            # Do not hold a packed parse forest across sentences.
            del result, lattice
            if (i+1) % 100 == 0:
                snap = {"at":i+1,"rss_mb":resident_bytes()/2**20,
                        "gc_counts":list(gc.get_count()),
                        "gc_cpu_s":round(sum(gc_times.values())/1e9,6),
                        "cpu_elapsed_s":round((process_time_ns()-t0c)/1e9,6)}
                snapshots.append(snap)
                print(f"PROGRESS {name} {i+1}/1000 CPU={snap['cpu_elapsed_s']:.2f}s "
                      f"RSS={snap['rss_mb']:.1f}MiB GC={snap['gc_cpu_s']:.2f}s", flush=True)
    finally:
        arm_cpu_ns = process_time_ns()-t0c
        arm_wall_ns = perf_counter_ns()-t0w
        gc.callbacks.remove(on_gc)
        gc.unfreeze()
    # Separately account for final cleanup even though it is not production
    # parsing; identical explicit cleanup after each arm.
    end_cleanup_start = process_time_ns()
    gc.collect(2)
    cleanup_ns = process_time_ns()-end_cleanup_start
    if mismatch:
        write("mismatch.json", mismatch)
    cpu = [r["cpu_ms"] for r in per_case]
    summary = {
        "arm":name,"n":len(per_case),"frozen_objects":frozen,
        "cpu_s":round(arm_cpu_ns/1e9,6),
        "wall_s":round(arm_wall_ns/1e9,6),
        "post_arm_cleanup_cpu_s":round(cleanup_ns/1e9,6),
        "cpu_including_cleanup_s":round((arm_cpu_ns+cleanup_ns)/1e9,6),
        "gc_cpu_s":round(sum(gc_times.values())/1e9,6),
        "gc_cpu_by_generation_s":{k:round(v/1e9,6) for k,v in gc_times.items()},
        "gc_collections":dict(gc_events),
        "gc_collected":dict(gc_collected),
        "gc_uncollectable":dict(gc_uncollectable),
        "rss_start_mb":round(resident_start/2**20,3) if resident_start else None,
        "rss_end_mb":round(resident_bytes()/2**20,3),
        "max_rss_process_mb":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,3),
        "p50_cpu_ms":round(percentile(cpu,.5),4) if cpu else None,
        "p95_cpu_ms":round(percentile(cpu,.95),4) if cpu else None,
        "p99_cpu_ms":round(percentile(cpu,.99),4) if cpu else None,
        "completed":sum(1 for x in per_case if x["completed"]),
        "forest_nodes_total":sum(x["forest_nodes"] for x in per_case),
        "partial_states_total":sum(x["partial_states"] for x in per_case),
        "memory_and_gc_snapshots":snapshots,
    }
    write(f"{name}.json", {"summary":summary,"per_case":per_case})
    print(f"ARM COMPLETE {name}: CPU={summary['cpu_s']:.3f}s "
          f"GC={summary['gc_cpu_s']:.3f}s P95={summary['p95_cpu_ms']:.2f}ms "
          f"RSS={summary['rss_end_mb']:.1f}MiB completed={summary['completed']}", flush=True)
    return summary, [x["digest"] for x in per_case], per_case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",type=int,default=1000)
    args = parser.parse_args()
    if args.limit != 1000:
        raise ValueError("This benchmark intentionally uses exactly 1000 cases.")
    rows, manifest = cases_1000()
    write("workload.json",{
        "git_sha":os.environ.get("GITHUB_SHA"),
        "python":sys.version,"platform":platform.platform(),
        "cpu_count":os.cpu_count(),"gc_thresholds":gc.get_threshold(),
        "cases":len(rows), "books":sorted(set(r["book_id"] for r in rows)),
        "groups":dict(Counter(str((r["book_id"],r["band"])) for r in rows)),
        "corpus":manifest,
        "input_sha256":sha256("\n".join(x["text_sha256"] for x in rows).encode()).hexdigest(),
        "input_rows":[{k:v for k,v in row.items() if k!="text"} for row in rows],
        "important":"CPython GC only; no modification to Seman2 grammar, algorithms, caching or parser source."})
    resources = ParserResources.from_dir(
        ROOT/"superparser"/"data",wordnet_dict=os.environ["WORDNET_DICT"])
    parser = Parser(resources,cache_size=0)
    # Ensure lazy WordNet is loaded before the first arm. Different warm-up
    # sentences, not part of the 1000-case benchmark.
    for phrase in ("John opened the box.","Mary wrote a letter.",
                   '"Hello," said Mary.',"The children waited patiently."):
        lattice=build_lattice(phrase,resources.lexicon)
        r=parser.parse_grammar_lattice(lattice,max_items=20_000,kbest_work_limit=100_000)
        digest_of(r)
        del lattice,r
    # Lexicon builds and indexes WordNet-derived lexical entries lazily.
    # Bring all 1000 selected surfaces and morphological variants into memory
    # BEFORE ANY MEASURED ARM so a second arm cannot benefit from entries
    # learned/indexed only by the first one.
    for row in rows:
        lattice = build_lattice(row["text"], resources.lexicon)
        del lattice
    gc.collect(2)
    # Cheap deterministic control before spending CPU on four 1000-case runs.
    # Same data, no gc.freeze yet: catch changing lexical outcomes early.
    for index in range(0, 1000, 67):
        row = rows[index]
        digests = []
        for _ in range(2):
            lattice = build_lattice(row["text"], resources.lexicon)
            check = parser.parse_grammar_lattice(
                lattice, max_items=20_000, kbest_work_limit=100_000)
            digests.append(digest_of(check)[0])
            del lattice, check
        if digests[0] != digests[1]:
            write("lexical_preflight_failure.json",
                  {"index": index, "book": row["book_id"],
                   "text": row["text"], "digests": digests})
            raise AssertionError(f"Repeated parse not deterministic after warm-up: {index}")
    gc.collect(2)
    print("PREFLIGHT PASS: all 1000 surfaces warmed; 15 repeated sentence checks identical",flush=True)
    print("START: 1000 unique phrases, 4 matched passes, real lexical+canonical parse+outputs",flush=True)
    baseline=None
    all_summaries={}
    all_records={}
    for name in ARMS:
        s,hashes,records=run_arm(name,rows,parser,baseline)
        if baseline is None:
            baseline=hashes
        all_summaries[name]=s
        all_records[name]=records
    def armmean(names,key):
        return statistics.mean(all_summaries[n][key] for n in names)
    standard=("default_a","default_b")
    frozen=("freeze_a","freeze_b")
    base=armmean(standard,"cpu_s")
    optimized=armmean(frozen,"cpu_s")
    base_lifetime=armmean(standard,"cpu_including_cleanup_s")
    freeze_lifetime=armmean(frozen,"cpu_including_cleanup_s")
    paired=[]
    by_band=defaultdict(list)
    for i,row in enumerate(rows):
        a=statistics.mean(all_records[arm][i]["cpu_ms"] for arm in standard)
        b=statistics.mean(all_records[arm][i]["cpu_ms"] for arm in frozen)
        paired.append((a,b))
        by_band[row["band"]].append((a,b))
    rng=random.Random(1729)
    bootstrap=[]
    for _ in range(900):
        sample=[paired[rng.randrange(len(paired))] for j in range(len(paired))]
        bootstrap.append(sum(v for _,v in sample)/sum(v for v,_ in sample))
    group_stats={}
    for band, samples in by_band.items():
        group_stats[band]={"n":len(samples),
                           "cpu_ratio":round(sum(x[1] for x in samples)/
                                             sum(x[0] for x in samples),5)}
    summary={
        "n_unique_sentences":1000, "total_sentences_parsed":4000,
        "output_digests_identical_for_all_1000_in_all_four_arms":True,
        "average_cpu_default_s":round(base,5),
        "average_cpu_freeze_s":round(optimized,5),
        "freeze_over_default_ratio":round(optimized/base,5),
        "freeze_cpu_change_pct":round((optimized/base-1)*100,3),
        "average_cpu_default_plus_final_gc_s":round(base_lifetime,5),
        "average_cpu_freeze_plus_final_gc_s":round(freeze_lifetime,5),
        "freeze_plus_final_gc_change_pct":round((freeze_lifetime/base_lifetime-1)*100,3),
        "mean_default_gc_cpu_s":round(armmean(standard,"gc_cpu_s"),5),
        "mean_freeze_gc_cpu_s":round(armmean(frozen,"gc_cpu_s"),5),
        "paired_bootstrap_95pct_ratio":[round(percentile(bootstrap,.025),5),
                                         round(percentile(bootstrap,.975),5)],
        "ratio_by_band":group_stats,
        "arms":all_summaries,
        "warnings":[
            "All 4 passes share one Python process, so vocabulary caches warm up between arms. A/B/B/A partially mitigates this, but separate-process validation would be stronger.",
            "gc.freeze() is a process-global GC policy, not a selective WordNet optimization.",
            "No heap or forests are retained across 1000 sentences; only small output hashes and scalar measurements.",
            "Memory RSS is sampled only every 100 sentences; transient peaks may be missed.",
            "Post-arm forced garbage collection counted separately for experimental comparison, not representative of normal termination.",
        ],
    }
    write("summary.json",summary)
    print("FINAL",json.dumps({k:v for k,v in summary.items() if k not in ("arms","warnings")},sort_keys=True),flush=True)
    print("SUCCESS all 1000 outputs identical with GC offloading test",flush=True)


if __name__ == "__main__":
    main()
