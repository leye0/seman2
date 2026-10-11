#!/usr/bin/env python3
"""Small reproducible benchmark for the syntax/semantics boundary."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from time import perf_counter

from seman_parser import Parser


DEFAULT_TEXTS = (
    "John opened the box.",
    "John gave Mary the box.",
    "I saw the man with the telescope.",
)


def percentile(values: list[float], fraction: float) -> float:
    """Linearly interpolated percentile (same definition for every phase)."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def distribution(rows: list[dict[str, float]], key: str) -> dict[str, float]:
    values = [row[key] for row in rows]
    return {
        "p50": round(percentile(values, 0.50), 4),
        "p90": round(percentile(values, 0.90), 4),
        "p95": round(percentile(values, 0.95), 4),
    }


def run(data: Path, *, repeats: int, deduplicate: bool) -> list[dict[str, object]]:
    parser = Parser.from_dir(
        data, cache_size=0, deduplicate_lexical=deduplicate,
    )
    for text in DEFAULT_TEXTS:
        parser.parse(text)  # warm the shared WordNet indexes
    output: list[dict[str, object]] = []
    for text in DEFAULT_TEXTS:
        samples: list[dict[str, float]] = []
        result = None
        alternatives = ()
        gc.collect()
        gc.disable()
        try:
            for _ in range(repeats):
                started = perf_counter()
                report = parser.parse(text)
                parse_total = (perf_counter() - started) * 1000
                result = report.result
                started = perf_counter()
                alternatives = result.alternatives(limit=4)
                kbest_access = (perf_counter() - started) * 1000
                best = result.best()
                started = perf_counter()
                report.interpret(best)
                semantic = (perf_counter() - started) * 1000
                samples.append({
                    "parse_total_ms": parse_total,
                    "lexical_ms": float(result.stats.get("lexical_ms", 0)),
                    "recognition_ms": float(result.stats.get("recognition_ms", 0)),
                    "best_ms": float(result.stats.get("best_ms", 0)),
                    "kbest_ms": kbest_access,
                    "semantic_ms": semantic,
                })
        finally:
            gc.enable()
        assert result is not None
        output.append({
            "text": text,
            "timings_ms": {key: distribution(samples, key) for key in samples[0]},
            "lexical_candidates": len(result.lattice.candidates),
            "forest_nodes": result.stats.get("forest_nodes"),
            "structural_derivations": result.stats.get("structural_derivations"),
            "materialized_items": result.stats.get("materialized_items"),
            "alternatives": len(alternatives),
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--repeats", type=int, default=15)
    args = parser.parse_args()
    payload = {
        "syntax_without_deduplication": run(args.data, repeats=args.repeats, deduplicate=False),
        "syntax_with_deduplication": run(args.data, repeats=args.repeats, deduplicate=True),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
