"""Watch memory and CPU while parsing, to find where the engine degrades.

Tracks RSS, heap size, chart size, and per-sentence wall time so we can
see whether a leak, a cache blow-up, or a combinatorial explosion is
behind the freezes after ~200 sentences.

Usage:
    python -m seman_parser.watch_resources [limit]
"""

from __future__ import annotations

import gc
import resource
import sys
import time
from pathlib import Path


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def run(limit: int = 200) -> None:
    from .coverage import extract_sentences
    from .engine import Parser
    from .perf import fs_stats

    cases = extract_sentences(Path("../data/the_map_of_everything_nlp_novel.txt"), limit=limit)
    parser = Parser.from_dir("data")
    parser.parse("warm up")

    base_rss = rss_mb()
    print(f"start  rss={base_rss:.1f} MB  cases={len(cases)}", flush=True)
    print(f"{'i':>4} {'ms':>8} {'rss':>8} {'rss_d':>7} {'ok':>3} {'packed':>7} {'partials':>8} {'exp':>7} text", flush=True)

    times = []
    for i, case in enumerate(cases):
        gc.collect()
        rss_before = rss_mb()
        t0 = time.perf_counter()
        report = parser.parse(case.text)
        dt = time.perf_counter() - t0
        times.append(dt)
        stats = report.result.stats or {}
        rss = rss_mb()
        flag = " <== SLOW" if dt > 2.0 else ""
        print(
            f"{i:4d} {dt*1000:8.1f} {rss:8.1f} {rss - rss_before:7.1f} "
            f"{'Y' if report.result.completed else 'N':>3} "
            f"{stats.get('packed_nodes', 0):7d} {stats.get('partials', 0):8d} "
            f"{stats.get('expanded', 0):7d} {case.text[:42]!r}{flag}",
            flush=True,
        )
        if dt > 15.0:
            print(f"  !! {dt:.1f}s on sentence {i} — possible freeze", flush=True)

    times.sort()
    n = len(times)
    print(f"\n=== summary ===", flush=True)
    print(f"parsed   {sum(1 for _ in times)}/{n}", flush=True)
    print(f"median   {times[n // 2] * 1000:.1f} ms", flush=True)
    print(f"p90      {times[int(n * 0.9)] * 1000:.1f} ms", flush=True)
    print(f"max      {times[-1] * 1000:.1f} ms", flush=True)
    print(f"rss end  {rss_mb():.1f} MB  (delta {rss_mb() - base_rss:+.1f} MB)", flush=True)
    print(f"fs pool  {fs_stats()}", flush=True)
    print(f"cache    {parser.cache_stats()}", flush=True)


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    run(limit)


if __name__ == "__main__":
    main()
