"""Instrumented profiling for the chart parser.

Counts and times each hot stage so we can see where CPU actually goes,
not just which functions are called often. Usage:

    python -m seman_parser.profile_parse "John opened the box."
"""

from __future__ import annotations

import cProfile
import pstats
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageStats:
    """Per-stage counters and timings."""

    counts: Counter = field(default_factory=Counter)
    times: Counter = field(default_factory=Counter)
    _stack: list[tuple[str, float]] = field(default_factory=list)

    def enter(self, stage: str) -> None:
        self._stack.append((stage, time.perf_counter()))

    def exit(self, stage: str) -> None:
        if not self._stack:
            return
        name, t0 = self._stack.pop()
        if name != stage:
            return
        self.counts[name] += 1
        self.times[name] += time.perf_counter() - t0

    def add(self, stage: str, dt: float) -> None:
        self.counts[stage] += 1
        self.times[stage] += dt

    def report(self) -> str:
        rows = []
        for stage, count in self.counts.most_common():
            total = self.times[stage]
            rows.append(f"  {stage:28s} {count:8d}  {total*1000:10.1f} ms  {total*1e6/count:8.1f} µs/call")
        return "\n".join(rows)


# Global instrumentation, enabled explicitly.
STATS = StageStats()
ENABLED = False


def enable() -> None:
    global ENABLED
    ENABLED = True


def disable() -> None:
    global ENABLED
    ENABLED = False


def reset() -> None:
    STATS.counts.clear()
    STATS.times.clear()


def instrument(stage: str):
    """Decorator that records stage time when instrumentation is on."""
    def deco(fn):
        def wrapper(*args, **kwargs):
            if not ENABLED:
                return fn(*args, **kwargs)
            STATS.enter(stage)
            try:
                return fn(*args, **kwargs)
            finally:
                STATS.exit(stage)
        wrapper.__name__ = getattr(fn, "__name__", stage)
        return wrapper
    return deco


def profile_parse(text: str, *, data_dir: str = "data", top: int = 25) -> str:
    """cProfile one parse and return a human-readable report."""
    from .engine import Parser

    pr = cProfile.Profile()
    parser = Parser.from_dir(data_dir)
    parser.parse("warm up the lexicon and grammar indexes.")
    pr.enable()
    parser.parse(text)
    pr.disable()
    import io

    buf = io.StringIO()
    stats = pstats.Stats(pr, stream=buf).sort_stats("cumulative")
    stats.print_stats(top)
    return buf.getvalue()


def main() -> None:
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "John opened the box."
    print(f"=== cProfile: {text!r} ===")
    print(profile_parse(text))


if __name__ == "__main__":
    main()
