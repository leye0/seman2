#!/usr/bin/env python3
"""CPU A/B audit for Python implementation details of Seman2 canonical parser.

Changes under test are runtime-only monkeypatches of function bodies whose
logic, grammar, cache, data and algorithm remain unchanged. Never patch the
repository source code. Differences in grammatical output abort the benchmark.
"""
from __future__ import annotations

import argparse
import cProfile
from collections import defaultdict, Counter
from contextlib import contextmanager
from hashlib import sha256
import inspect
import json
import math
import os
from pathlib import Path
import platform
import pstats
import random
from statistics import median
import sys
import textwrap
from time import process_time_ns, perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "superparser"))
from scripts.corpus_samples import choose_cases
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice
import seman_parser.vector_chart as vc

OUTPUT = ROOT / "_cpu_ab_results"
ORIGINALS = {
    "_next_start": vc._VectorForest._next_start,
    "_add_partial": vc._VectorForest._add_partial,
    "recognize": vc._VectorForest.recognize,
}
CHANGES = {
    "next_start_locals": (
        "_next_start",
        "        while end < len(self.text) and self.text[end] in separators:",
        "        text = self.text\n"
        "        text_length = len(text)\n"
        "        while end < text_length and text[end] in separators:",
    ),
    "waiting_no_eager_empty_list": (
        "_add_partial",
        "        self.waiting.setdefault((position, expected_id), []).append(partial.partial_id)",
        "        wait_key = (position, expected_id)\n"
        "        queue = self.waiting.get(wait_key)\n"
        "        if queue is None:\n"
        "            queue = []\n"
        "            self.waiting[wait_key] = queue\n"
        "        queue.append(partial.partial_id)",
    ),
    "recognize_no_double_snapshot": (
        "recognize",
        "            for partial_id in tuple(waiting[:node.waiting_cutoff]):",
        "            for partial_id in waiting[:node.waiting_cutoff]:",
    ),
}


def write(name, obj):
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2,
                                          default=str), encoding="utf-8")


def make_variant(key):
    method, old, new = CHANGES[key]
    source = inspect.getsource(ORIGINALS[method])
    if source.count(old) != 1:
        raise AssertionError(f"Expected one exact source match for {key}")
    source = textwrap.dedent(source.replace(old, new))
    ns = dict(vars(vc))
    exec(compile(source, f"<equivalent-low-level-{key}>", "exec"), ns)
    return method, ns[method]


@contextmanager
def patch(key):
    for method, fn in ORIGINALS.items():
        setattr(vc._VectorForest, method, fn)
    if key == "baseline":
        yield
    else:
        method, fn = make_variant(key)
        setattr(vc._VectorForest, method, fn)
        try:
            yield
        finally:
            for m, original in ORIGINALS.items():
                setattr(vc._VectorForest, m, original)


def stable_report(result):
    # It is essential to force the lazy tree materialization in every arm.
    best = result.best()
    alternatives = result.alternatives(limit=2)
    # Exclude CPU/wall measurements. Include ALL other existing statistics,
    # preserving counters, route, saturation, and structural evidence.
    stats = {k: v for k, v in result.stats.items()
             if not (k.endswith("_ms") or k.endswith("_seconds"))}
    return {"completed": result.completed, "best": best.as_dict() if best else None,
            "alternatives": [x.as_dict() for x in alternatives], "stats": stats}


def signature(report):
    return sha256(json.dumps(report, sort_keys=True, separators=(",", ":"),
                             default=str).encode("utf-8")).hexdigest()


def parse_one(parser, lattice):
    start_c = process_time_ns()
    start_w = perf_counter_ns()
    result = parser.parse_grammar_lattice(
        lattice, max_items=20_000, kbest_work_limit=100_000)
    # Include requested lazy outputs in timing, independent of variant.
    result.best()
    result.alternatives(limit=2)
    cpu_ns = process_time_ns() - start_c
    wall_ns = perf_counter_ns() - start_w
    report = stable_report(result)
    return {"cpu_ns": cpu_ns, "wall_ns": wall_ns,
            "digest": signature(report), "report": report}


def qt(values, p):
    ordered = sorted(values)
    if not ordered:
        return None
    i = (len(ordered) - 1) * p
    a = int(i)
    return ordered[a] + (ordered[min(a + 1, len(ordered) - 1)] - ordered[a]) * (i - a)


def summarise(records):
    total = sum(x["cpu_ns"] for x in records)
    cpu = [x["cpu_ns"] / 1e6 for x in records]
    return {"n": len(records), "cpu_total_s": round(total / 1e9, 4),
            "cpu_per_sentence_mean_ms": round(total / len(records) / 1e6, 4),
            "cpu_p50_ms": round(qt(cpu, .5), 4),
            "cpu_p95_ms": round(qt(cpu, .95), 4),
            "wall_total_s": round(sum(r["wall_ns"] for r in records) / 1e9, 4)}


def ci_ratio(base_ns, test_ns, *, samples=600):
    randomizer = random.Random(271828)
    if not base_ns or not sum(base_ns):
        return (None, None)
    n = len(base_ns)
    bs = []
    for _ in range(samples):
        indexes = [randomizer.randrange(n) for _ in range(n)]
        denominator = sum(base_ns[i] for i in indexes)
        numerator = sum(test_ns[i] for i in indexes)
        bs.append(numerator / denominator if denominator else float("nan"))
    return (round(qt(bs, .025), 5), round(qt(bs, .975), 5))


def experiment(parser, rows, lattices, variant):
    """A / B / B / A for each exact same sentence; no profiler overhead."""
    arms = ("reference_a", "candidate_a", "candidate_b", "reference_b")
    results = {name: [] for name in arms}
    mismatches = []
    for i, (case, lattice) in enumerate(zip(rows, lattices)):
        checks = []
        for arm in arms:
            which = "baseline" if arm.startswith("reference") else variant
            with patch(which):
                sample = parse_one(parser, lattice)
            results[arm].append({k: v for k, v in sample.items() if k != "report"})
            checks.append(sample["digest"])
        if len(set(checks)) != 1:
            # Keep evidence, fail closed rather than claim parity.
            mismatches.append({
                "sample": i, "book": case["book_id"], "band": case["band"],
                "text": case["text"], "hashes": dict(zip(arms, checks))})
        if (i + 1) % 16 == 0:
            print(f"AB {variant}: {i + 1}/{len(rows)}", flush=True)

    base_ns = [(results["reference_a"][i]["cpu_ns"]
                + results["reference_b"][i]["cpu_ns"]) / 2
               for i in range(len(rows))]
    test_ns = [(results["candidate_a"][i]["cpu_ns"]
                + results["candidate_b"][i]["cpu_ns"]) / 2
               for i in range(len(rows))]
    ratio = sum(test_ns) / sum(base_ns)
    group_stats = {}
    for axis in ("band", "book_id"):
        names = sorted(set(r[axis] for r in rows), key=str)
        group_stats[axis] = {}
        for name in names:
            ix = [i for i, x in enumerate(rows) if x[axis] == name]
            base = sum(base_ns[i] for i in ix)
            test = sum(test_ns[i] for i in ix)
            group_stats[axis][str(name)] = {
                "n": len(ix), "base_cpu_s": round(base / 1e9, 5),
                "variant_cpu_s": round(test / 1e9, 5),
                "ratio": round(test / base, 5) if base else None}
    result = {
        "variant": variant, "cases": len(rows), "order": arms,
        "all_outputs_and_counters_identical": not mismatches,
        "mismatches": mismatches,
        "baseline_cpu_s": round(sum(base_ns) / 1e9, 5),
        "variant_cpu_s": round(sum(test_ns) / 1e9, 5),
        "ratio_variant_over_baseline": round(ratio, 5),
        "estimated_pct_cpu_change": round((ratio - 1) * 100, 3),
        "paired_bootstrap_95pct_ratio": ci_ratio(base_ns, test_ns),
        "baseline_a_vs_b_drift_ratio":
            round(sum(r["cpu_ns"] for r in results["reference_b"]) /
                  sum(r["cpu_ns"] for r in results["reference_a"]), 5),
        "by_group": group_stats,
        "arm_summary": {name: summarise(group) for name, group in results.items()},
        "per_case": [
            {"index": i, "book": rows[i]["book_id"], "band": rows[i]["band"],
             "tokens": rows[i]["tokens"], "baseline_cpu_ms": round(base_ns[i] / 1e6, 4),
             "candidate_cpu_ms": round(test_ns[i] / 1e6, 4),
             "ratio": round(test_ns[i] / base_ns[i], 5) if base_ns[i] else None}
            for i in range(len(rows))
        ],
    }
    write(f"ab_{variant}.json", result)
    print(f"RESULT {variant}: baseline {sum(base_ns)/1e9:.3f}s "
          f"variant {sum(test_ns)/1e9:.3f}s ratio={ratio:.5f} "
          f"bootstrap={result['paired_bootstrap_95pct_ratio']} "
          f"output_parity={not mismatches}", flush=True)
    if mismatches:
        raise AssertionError(f"Equivalent variant changed {len(mismatches)} parse results: {variant}")
    return result


def profile_large_cohort(parser, rows, lattices):
    # CPU profiler deliberately separate from A/B timings.
    with patch("baseline"):
        profiler = cProfile.Profile(timer=lambda: process_time_ns() / 1e9)
        start = process_time_ns()
        profiler.enable()
        results = []
        try:
            for lattice in lattices:
                result = parser.parse_grammar_lattice(
                    lattice, max_items=20_000, kbest_work_limit=100_000)
                best = result.best()
                result.alternatives(limit=2)
                results.append({
                    "completed": result.completed,
                    "forest_nodes": int(result.stats.get("forest_nodes") or 0),
                    "partial_states": int(result.stats.get("partial_states") or 0),
                    "structural_derivations": int(result.stats.get("structural_derivations") or 0),
                    "best_category": best.category if best else None})
        finally:
            profiler.disable()
        wall_cpu = (process_time_ns() - start) / 1e9
        profiler.dump_stats(str(OUTPUT / "large_cohort.pstats"))
    stats = pstats.Stats(profiler)
    hot = []
    for (file, line, name), (pc, nc, self_s, inclusive, callers) in stats.stats.items():
        if "seman_parser" in file:
            hot.append({"file":file.replace(str(ROOT)+os.sep,""),"line":line,
                        "function":name,"calls":nc,
                        "cpu_self_s":round(self_s,6),"cpu_inclusive_s":round(inclusive,6)})
    write("large_cohort_profile.json",{
        "sentences":len(rows), "profiled_cpu_s":wall_cpu,
        "completed":sum(int(x["completed"]) for x in results),
        "total_partial_states":sum(x["partial_states"] for x in results),
        "total_forest_nodes":sum(x["forest_nodes"] for x in results),
        "top_exclusive":sorted(hot,key=lambda r:r["cpu_self_s"],reverse=True)[:100],
        "top_inclusive":sorted(hot,key=lambda r:r["cpu_inclusive_s"],reverse=True)[:100],
        "warning":"cProfile CPU is instrumented, not directly comparable to baseline."})
    print(f"LARGE PROFILE: {len(rows)} sentences, {wall_cpu:.2f}s CPU with cProfile,"
          f" {sum(x['completed'] for x in results)} complete",flush=True)
    for row in sorted(hot,key=lambda r:r["cpu_self_s"],reverse=True)[:22]:
        print(f"HOT {row['cpu_self_s']:.4f}s {row['calls']:8d} "
              f"{row['file']}:{row['line']} {row['function']}",flush=True)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--per-book-per-band", type=int, default=8)
    cli.add_argument("--ab-per-book-per-band", type=int, default=4)
    cli.add_argument("--skip-large-profile", action="store_true")
    args = cli.parse_args()
    assert 1 <= args.ab_per_book_per_band <= args.per_book_per_band <= 12
    OUTPUT.mkdir(exist_ok=True)
    manifest_rows, sources = choose_cases(args.per_book_per_band)
    rows = [{"text":r["text"],"book_id":r["book_id"],"band":r["band"],
             "tokens":r["tokens"]} for r in manifest_rows]
    for i, t in enumerate(["John opened the box.", "John gave Mary the box.", '"Hello," said Mary.']):
        rows.append({"text":t,"book_id":"fixture","band":"dialogue" if '"' in t else "04-08",
                     "tokens":6})
    write("environment.json",{"python":sys.version,"platform":platform.platform(),
          "cpu_count":os.cpu_count(),"commit":os.environ.get("GITHUB_SHA"),
          "full_n":len(rows), "sources":sources, "sentences":rows,
          "frozen_main":True,"production_source_modified":False,
          "changes":{k:{"method":v[0],"before":v[1],"after":v[2]}
                     for k,v in CHANGES.items()}})
    resources = ParserResources.from_dir(
        ROOT/"superparser"/"data",wordnet_dict=os.environ["WORDNET_DICT"])
    parser = Parser(resources,cache_size=0)
    lattices = [build_lattice(r["text"],resources.lexicon) for r in rows]
    print("Loaded", len(lattices), "canonical lexical lattices",flush=True)
    if not args.skip_large_profile:
        profile_large_cohort(parser,rows,lattices)

    # Sample cases spaced deterministically across all four books and bands.
    by_group = defaultdict(list)
    for row, lattice in zip(rows, lattices):
        by_group[(row["book_id"],row["band"])].append((row,lattice))
    selected=[]
    for group in sorted(by_group,key=lambda x:str(x)):
        choices=by_group[group]
        n=min(args.ab_per_book_per_band,len(choices))
        indexes=[min(len(choices)-1,((2*i+1)*len(choices))//(2*n)) for i in range(n)]
        selected.extend(choices[i] for i in indexes)
    ab_rows=[x[0] for x in selected]
    ab_lattices=[x[1] for x in selected]
    print("A/B cohort",len(ab_rows), "sentences",flush=True)
    summary={}
    for variant in CHANGES:
        r=experiment(parser,ab_rows,ab_lattices,variant)
        summary[variant]={
            "n":r["cases"],"cpu_pct_change":r["estimated_pct_cpu_change"],
            "paired_ci_ratio":r["paired_bootstrap_95pct_ratio"],
            "all_outputs_identical":r["all_outputs_and_counters_identical"],
            "a_to_b_drift_ratio":r["baseline_a_vs_b_drift_ratio"],
            "ratio_by_band":{k:v["ratio"] for k,v in r["by_group"]["band"].items()}}
    write("summary.json",summary)
    print("SUMMARY",json.dumps(summary,sort_keys=True),flush=True)
    print("COMPLETE: All A/B variants parity verified; production implementation unchanged.",flush=True)


if __name__ == "__main__":
    main()
