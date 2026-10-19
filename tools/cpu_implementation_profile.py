#!/usr/bin/env python3
"""Seman2: implementation-level, read-only CPU/memory audit. No parser changes.

CPU cProfile uses process_time (not wall clock). Line profiler, when installed,
is a separate high-overhead experiment and its times must NOT be compared
directly to the uninstrumented CPU timings.
"""
from __future__ import annotations

import argparse
import ast
import cProfile
import dis
import gc
import importlib
import inspect
import json
import os
from pathlib import Path
import platform
import pstats
import resource
import statistics
import sys
import time
import tracemalloc
from collections import Counter
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "superparser"))
from scripts.corpus_samples import choose_cases
from seman_parser.engine import Parser, ParserResources, ParseReport
from seman_parser.segmentation import build_lattice

PARSER_SOURCE = ROOT / "superparser" / "seman_parser"
OUTPUT = ROOT / "_cpu_results"
MEASURED = {}


def dump(name, obj):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def timing(name, callback, *, profile=True):
    gc.collect()
    before_gc = [x.copy() for x in gc.get_stats()]
    start_wall, start_cpu = time.perf_counter_ns(), time.process_time_ns()
    prof = cProfile.Profile(timer=time.process_time) if profile else None
    try:
        if prof:
            prof.enable()
        value = callback()
    finally:
        if prof:
            prof.disable()
    cpu = (time.process_time_ns() - start_cpu) / 1e9
    wall = (time.perf_counter_ns() - start_wall) / 1e9
    data = {
        "cpu_s": round(cpu, 6), "wall_s": round(wall, 6),
        "cpu_per_wall": round(cpu / wall, 4) if wall else None,
        "gc_collections_delta": [b["collections"]-a["collections"] for a, b in zip(before_gc, gc.get_stats())],
        "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    if prof:
        prof.dump_stats(str(OUTPUT / (name + ".pstats")))
        stat = pstats.Stats(prof)
        funcs = []
        for (file, line, func), (primitive, total_calls, selftime, cumtime, callers) in stat.stats.items():
            if file.startswith(str(ROOT)) or "seman_parser" in file or "built-in method" in file:
                funcs.append({
                    "file": file.replace(str(ROOT)+os.sep, ""),
                    "line": line, "function": func,
                    "primitive_calls": primitive, "total_calls": total_calls,
                    "cpu_self_s": round(selftime, 7), "cpu_cumulative_s": round(cumtime, 7),
                })
        data["top_by_self"] = sorted(funcs, key=lambda x: x["cpu_self_s"], reverse=True)[:160]
        data["top_by_cumulative"] = sorted(funcs, key=lambda x: x["cpu_cumulative_s"], reverse=True)[:160]
    MEASURED[name] = data
    dump(name + ".json", data)
    print(f"\nPHASE {name}: CPU={cpu:.3f}s wall={wall:.3f}s CPU/wall={data['cpu_per_wall']}", flush=True)
    for f in data.get("top_by_self", [])[:18]:
        print(f"  SELF {f['cpu_self_s']:9.4f}s CALLS {f['total_calls']:9d} {f['file']}:{f['line']}:{f['function']}", flush=True)
    return value


def memory_phase(name, callback):
    gc.collect()
    tracemalloc.start(10)
    before = tracemalloc.take_snapshot()
    c0, w0 = time.process_time_ns(), time.perf_counter_ns()
    try:
        value = callback()
        current, peak = tracemalloc.get_traced_memory()
        after = tracemalloc.take_snapshot()
    finally:
        tracemalloc.stop()
    lines = []
    for item in after.compare_to(before, "lineno"):
        if not item.traceback:
            continue
        frame = item.traceback[0]
        if str(PARSER_SOURCE) not in frame.filename or item.size_diff <= 0:
            continue
        lines.append({
            "source": frame.filename.replace(str(ROOT)+os.sep, "") + ":" + str(frame.lineno),
            "net_bytes": item.size_diff, "net_count": item.count_diff
        })
    data = {"cpu_s_instrumented": round((time.process_time_ns()-c0)/1e9,5),
            "wall_s_instrumented": round((time.perf_counter_ns()-w0)/1e9,5),
            "traced_peak_bytes": peak, "traced_current_bytes": current,
            "top_net_allocation_sites": lines[:100],
            "warning": "tracemalloc is intrusive; deltas are retained allocations, not allocation churn."}
    dump(name+".json",data)
    print("MEMORY", name, "peak traced bytes", peak, "largest persistent sites", lines[:8], flush=True)
    return value


def count_and_result(items):
    counts = Counter()
    for i, result in enumerate(items):
        counts["cases"] += 1
        counts["completed"] += int(bool(result.completed))
        counts["budget_exceeded"] += int(bool(result.stats.get("budget_exceeded")))
        counts["forest_nodes"] += int(result.stats.get("forest_nodes") or 0)
        counts["partials"] += int(result.stats.get("partial_states") or 0)
        counts["derivations"] += int(result.stats.get("structural_derivations") or 0)
    return dict(counts)


def dynamic_functions():
    """Discover actual functions/methods by their code object, no guesses."""
    functions = {}
    for name, mod in tuple(sys.modules.items()):
        path = getattr(mod, "__file__", "") or ""
        if not path.startswith(str(PARSER_SOURCE)):
            continue
        for _, obj in inspect.getmembers(mod):
            if inspect.isfunction(obj):
                fn = obj
                if fn.__code__.co_filename == path:
                    functions[(path, fn.__code__.co_firstlineno)] = fn
            elif inspect.isclass(obj) and getattr(obj, "__module__", "") == name:
                for member in vars(obj).values():
                    fn = member.__func__ if isinstance(member, (staticmethod, classmethod)) else member
                    if inspect.isfunction(fn) and fn.__code__.co_filename == path:
                        functions[(path, fn.__code__.co_firstlineno)] = fn
    return functions


def line_study(parser, cases, top):
    try:
        from line_profiler import LineProfiler
        import line_profiler
    except ImportError:
        print("Line profiling skipped: line_profiler not installed")
        return
    known = dynamic_functions()
    selected = []
    seen = set()
    for f in sorted(top["top_by_self"][:70] + top["top_by_cumulative"][:70],
                    key=lambda x: x["cpu_self_s"] + x["cpu_cumulative_s"]*0.25, reverse=True):
        file = str(ROOT / f["file"])
        fn = known.get((file, f["line"]))
        if fn is not None and fn not in seen and len(selected) < 24:
            seen.add(fn)
            selected.append(fn)
    if not selected:
        print("No Python functions located for line profiler")
        return
    lp = LineProfiler()
    for fn in selected:
        lp.add_function(fn)
    print("LINE INSTRUMENTATION", [f.__qualname__ for f in selected], flush=True)
    # Curated but unmodified same parser path; this run has instrumentation overhead.
    subset = [r for r in cases if r["band"] in ("04-08", "09-16", "17-24")][:5]
    def task():
        for row in subset:
            lattice = build_lattice(row["text"], parser.resources.lexicon)
            result = parser.parse_grammar_lattice(lattice)
            result.best()
    gc.collect()
    start_cpu = time.process_time()
    lp.enable_by_count()
    try:
        task()
    finally:
        lp.disable_by_count()
    stats = lp.get_stats()
    rows = []
    for (file, lineno, func), entries in stats.timings.items():
        for source_line, hits, ticks in entries:
            if hits and ticks:
                rows.append({"file": file.replace(str(ROOT)+os.sep,""), "function":func,
                             "definition_line":lineno, "line":source_line,
                             "hits":hits, "time_s":round(ticks*stats.unit,7),
                             "time_per_hit_us": round(ticks*stats.unit*1e6/hits,4)})
    data = {"selected": [f.__qualname__ for f in selected],
            "instrumented_cpu_s": round(time.process_time()-start_cpu,4),
            "unit_seconds_per_tick": stats.unit,
            "cases": len(subset),
            "warning": "Line profiler times are instrumented wall times, not uninstrumented CPU times. Nested functions may overlap.",
            "all_lines": sorted(rows,key=lambda x:x["time_s"],reverse=True)}
    dump("line_level.json", data)
    with (OUTPUT/"line_level.txt").open("w",encoding="utf-8") as stream:
        lp.print_stats(stream=stream, output_unit=1e-6)
    print("TOP LINES (instrumented, NOT baseline CPU):", flush=True)
    for item in data["all_lines"][:30]:
        print(f"  LINE {item['time_s']:.4f}s {item['hits']:8d}x {item['file']}:{item['line']} {item['function']}",flush=True)


def language_audit(top):
    """Locate language-level patterns; do not mistake static warnings for measured hot spots."""
    counts = Counter()
    occurrences = []
    hot_files = {r["file"]: r for r in top["top_by_self"][:70]}
    for path in sorted(PARSER_SOURCE.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        loop_depth = 0
        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
                continue
            for child in ast.walk(node):
                if child is node:
                    continue
                kind = None
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name) and child.func.id in ("list","dict","set","tuple","sorted","str","repr"):
                        kind = "container_or_sort_in_loop:"+child.func.id
                    elif isinstance(child.func, ast.Attribute) and child.func.attr in ("as_dict","casefold","lower","copy","replace","split","join","items"):
                        kind = "method_in_loop:"+child.func.attr
                if isinstance(child, (ast.DictComp,ast.SetComp,ast.ListComp)):
                    kind = "comprehension_in_loop"
                if kind:
                    rel = str(path.relative_to(ROOT))
                    occurrences.append({"file":rel,"line":child.lineno,"kind":kind,
                                        "source":source.splitlines()[child.lineno-1].strip()[:170]})
                    counts[kind] += 1
    dump("language_patterns.json", {"counts":dict(counts),"occurrences":occurrences,
         "warning":"STATIC audit. Presence does not establish runtime impact."})
    selected = dynamic_functions()
    rows=[]
    for f in top["top_by_self"][:30]:
        fn = selected.get((str(ROOT/f["file"]),f["line"]))
        if fn is None:
            continue
        instructions = list(dis.get_instructions(fn))
        n = Counter(i.opname for i in instructions)
        rows.append({"function":f["function"],"file":f["file"],"line":f["line"],
                     "profiled_self_cpu_s":f["cpu_self_s"],"calls":f["total_calls"],
                     "bytecode_instruction_counts":dict(n.most_common()),
                     "note":"Bytecode counts are STATIC instructions in function body, not runtime execution frequencies."})
    dump("hot_bytecode.json",rows)
    print("STATIC PATTERN COUNTS",dict(counts),flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("core","lines"),default="core")
    args=ap.parse_args()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    print("SYSTEM",json.dumps({"python":sys.version,"platform":platform.platform(),
          "cpu_count":os.cpu_count(),"commit":os.environ.get("GITHUB_SHA"),
          "mode":args.mode}), flush=True)
    corpus, manifest = choose_cases(1)   # Four different Gutenberg books, four token bands.
    cases=[{"text":r["text"],"book_id":r["book_id"],"band":r["band"],
            "tokens":r["tokens"]} for r in corpus]
    cases += [{"text":'John opened the box.',"book_id":"fixture","band":"04-08","tokens":5},
              {"text":'John gave Mary the box.',"book_id":"fixture","band":"04-08","tokens":6},
              {"text":'"Hello," said Mary.',"book_id":"fixture","band":"dialogue","tokens":6}]
    dump("environment_and_cases.json",{
        "python":sys.version,"platform":platform.platform(),
        "cpu_count":os.cpu_count(),"commit":os.environ.get("GITHUB_SHA"),
        "workload":cases, "manifest":manifest,
        "constraints":"Production canonical only; never change parser algorithms, settings, cache policy or grammar. Individual phases measured separately.",
        "profile_limitations":"cProfile has call overhead; profiler CPU totals do not equal uninstrumented baseline; cumulative times overlap."})
    resources = timing("resource_startup",lambda:ParserResources.from_dir(
        ROOT/"superparser"/"data",wordnet_dict=os.environ.get("WORDNET_DICT")))
    parser = timing("parser_compile",lambda:Parser(resources,cache_size=0))
    if args.mode=="lines":
        prior_path=OUTPUT/"parser_cpu.json"
        if prior_path.exists():
            prior=json.loads(prior_path.read_text())
            line_study(parser,cases,prior)
        else:
            print("Missing primary profile for lines mode")
        return
    # Warm up interpreter + lazy WordNet separately so warm/cold costs are not conflated.
    timing("first_lexical_lookup",lambda:build_lattice(cases[0]["text"],resources.lexicon))
    lattices = timing("lexical_lattice_cpu",lambda:[
        build_lattice(c["text"],resources.lexicon) for c in cases])
    parsed = timing("parser_cpu",lambda:[
        parser.parse_grammar_lattice(lattice) for lattice in lattices])
    print("WORKLOAD RESULT",count_and_result(parsed),flush=True)
    def make_best():
        return [r.best() for r in parsed]
    bests=timing("best_tree_cpu",make_best)
    timing("serialize_best_cpu",lambda:[item.as_dict() for item in bests if item is not None])
    timing("alternatives_cpu",lambda:[r.alternatives(limit=2) for r in parsed])
    # Second independent end-to-end path exercising public API; no result caching.
    timing("end_to_end_cpu",lambda:[parser.parse(c["text"]) for c in cases[:10]])
    memory_phase("lexical_memory",lambda:[
        build_lattice(c["text"],resources.lexicon) for c in cases[:6]])
    memory_phase("parser_memory",lambda:[
        parser.parse_grammar_lattice(lattice) for lattice in lattices[:3]])
    language_audit(MEASURED["parser_cpu"])
    dump("phase_summary.json",{k:{"cpu_s":v["cpu_s"],"wall_s":v["wall_s"],
                                     "cpu_per_wall":v["cpu_per_wall"],
                                     "gc_collections_delta":v["gc_collections_delta"]}
                                   for k,v in MEASURED.items()})
    print("COMPLETE: Read CPU self times per function, call counts, allocation sites, and line profile as separate output files.",flush=True)


if __name__=="__main__":
    main()
