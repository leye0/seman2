#!/usr/bin/env python3
"""Reproducible production-vs-predictive benchmark on the same corpus/CPU."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import statistics
import subprocess
import sys
from time import perf_counter
import tracemalloc
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "superparser"))

from scripts.evaluate_reference_300 import normalized_gold, normalized_parser  # noqa: E402
from seman_parser import Parser  # noqa: E402
from seman_parser.predictive import (  # noqa: E402
    HybridPredictiveParser,
    PredictiveGrammar,
    PredictiveParser,
    TransitionModel,
)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def distribution(values: list[float]) -> dict[str, float]:
    if not values:
        return {key: 0.0 for key in ("p50", "p95", "p99", "maximum", "total")}
    return {
        "p50": round(percentile(values, 0.50), 4),
        "p95": round(percentile(values, 0.95), 4),
        "p99": round(percentile(values, 0.99), 4),
        "maximum": round(max(values), 4),
        "total": round(sum(values), 4),
    }


def aggregate(name: str, rows: list[dict[str, Any]], elapsed_ms: float, memory_peak: int) -> dict[str, Any]:
    timings = {
        key: distribution([float(row[key]) for row in rows])
        for key in ("total_wall_ms", "lexical_ms", "parsing_ms", "materialization_ms")
    }
    counters = {
        key: int(sum(int(row.get(key, 0)) for row in rows))
        for key in (
            "states_created", "transitions_executed", "decisions", "backtracks",
            "ambiguity_points", "configurations_visited", "unique_configurations",
            "revisited_configurations", "repeated_transitions", "max_backtrack_depth",
            "shared_nodes", "shared_partials", "feature_rejections",
            "lookahead_rejections",
        )
    }
    counters["max_backtrack_depth"] = max(
        (int(row.get("max_backtrack_depth", 0)) for row in rows), default=0,
    )
    complete = sum(bool(row["complete"]) for row in rows)
    return {
        "engine": name,
        "sentences": len(rows),
        "timings_ms": timings,
        "measured_loop_wall_ms": round(elapsed_ms, 4),
        "counters_total": counters,
        "memory_peak_bytes": memory_peak,
        "coverage": round(complete / len(rows), 6) if rows else 0.0,
        "native_successes": sum(bool(row.get("native_success")) for row in rows),
        "fallbacks": sum(bool(row.get("fallback")) for row in rows),
        "grammar_constraint_consistency": round(
            sum(bool(row.get("grammar_valid")) for row in rows) / complete, 6,
        ) if complete else 0.0,
        "grammatical_validity": "requires linguistic audit; derivability is not treated as validity",
        "normalized_reference_exact": round(
            sum(bool(row.get("reference_exact")) for row in rows) / len(rows), 6,
        ) if rows else 0.0,
        "failures": [
            {"id": row["id"], "text": row["text"], "reason": row.get("stopped_by")}
            for row in rows if not row["complete"]
        ],
    }


def memory_peak(run_one: Callable[[dict[str, Any]], Any], corpus: list[dict[str, Any]], sample: int) -> int:
    gc.collect()
    tracemalloc.start()
    for row in corpus[:sample]:
        run_one(row)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def cold_probe(engine: str, data_dir: Path, model: Path, text: str) -> dict[str, float]:
    """Measure construction and first parse in a fresh interpreter."""
    source = f"""
import json
from time import perf_counter
from seman_parser import Parser
from seman_parser.predictive import HybridPredictiveParser, PredictiveParser, TransitionModel
started = perf_counter()
if {engine!r} == 'production':
    parser = Parser.from_dir({str(data_dir)!r}, cache_size=0)
elif {engine!r} == 'hybrid':
    parser = HybridPredictiveParser.from_dir({str(data_dir)!r}, model=TransitionModel.load({str(model)!r}), lookahead=1, fast_states=64)
else:
    parser = PredictiveParser.from_dir({str(data_dir)!r}, model=TransitionModel.load({str(model)!r}))
constructed = perf_counter()
result = parser.parse({text!r})
if {engine!r} == 'production':
    result.result.best()
finished = perf_counter()
print(json.dumps({{'construction_ms': (constructed-started)*1000, 'first_parse_ms': (finished-constructed)*1000, 'process_work_ms': (finished-started)*1000}}))
"""
    output = subprocess.check_output(
        [sys.executable, "-c", source], cwd=ROOT / "superparser", text=True,
    )
    return {key: round(float(value), 4) for key, value in json.loads(output).items()}


def bench_predictive(
    name: str, parser: PredictiveParser, corpus: list[dict[str, Any]], *, memory_sample: int,
) -> dict[str, Any]:
    parser.parse("The child laughed.")  # WordNet/index warm-up, not a phrase cache.

    def one(row: dict[str, Any]) -> dict[str, Any]:
        result = parser.parse(row["text"])
        stats = result.stats
        complete = result.completed
        return {
            "id": row["id"], "text": row["text"], "complete": complete,
            "total_wall_ms": stats["total_wall_ms"],
            "lexical_ms": stats["lexical_ms"], "parsing_ms": stats["parsing_ms"],
            "materialization_ms": stats["materialization_ms"],
            "states_created": stats["states_created"],
            "transitions_executed": stats["transitions_executed"],
            "decisions": stats["decisions"], "backtracks": stats["backtracks"],
            "ambiguity_points": stats["ambiguity_points"],
            "configurations_visited": stats.get("configurations_visited", 0),
            "unique_configurations": stats.get("unique_configurations", 0),
            "revisited_configurations": stats.get("revisited_configurations", 0),
            "repeated_transitions": stats.get("repeated_transitions", 0),
            "max_backtrack_depth": stats.get("max_backtrack_depth", 0),
            "shared_nodes": stats.get("shared_nodes", 0),
            "shared_partials": stats.get("shared_partials", 0),
            "feature_rejections": stats.get("feature_rejections", 0),
            "lookahead_rejections": stats.get("lookahead_rejections", 0),
            "native_success": stats["native_success"], "fallback": stats["fallback"],
            "stopped_by": stats["stopped_by"],
            # Every accepted node was constructed by a declared rule and
            # passed feature/required-evidence checks in `_reduce`.
            "grammar_valid": complete,
            "reference_exact": complete and normalized_parser(result.item) == normalized_gold(row["tree"]),
        }

    gc.collect()
    started = perf_counter()
    rows = [one(row) for row in corpus]
    elapsed = (perf_counter() - started) * 1000
    peak = memory_peak(one, corpus, memory_sample)
    return aggregate(name, rows, elapsed, peak)


def bench_production(parser: Parser, corpus: list[dict[str, Any]], *, memory_sample: int) -> dict[str, Any]:
    parser.parse("The child laughed.").result.best()

    def one(row: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        result = parser.parse(row["text"]).result
        best = result.best()
        total = (perf_counter() - started) * 1000
        stats = result.stats
        return {
            "id": row["id"], "text": row["text"], "complete": best is not None,
            "total_wall_ms": total,
            "lexical_ms": float(stats.get("lexical_ms", 0)),
            "parsing_ms": float(stats.get("recognition_ms", 0)),
            "materialization_ms": float(stats.get("best_ms", 0)),
            "states_created": int(stats.get("forest_nodes", stats.get("expanded", 0))),
            "transitions_executed": int(stats.get("recognition_operations", 0)),
            "decisions": 0, "backtracks": 0,
            "ambiguity_points": max(0, len(result.alternatives(limit=2)) - 1),
            "configurations_visited": 0, "unique_configurations": 0,
            "revisited_configurations": 0, "repeated_transitions": 0,
            "max_backtrack_depth": 0, "shared_nodes": 0, "shared_partials": 0,
            "feature_rejections": 0, "lookahead_rejections": 0,
            "native_success": best is not None, "fallback": False,
            "stopped_by": "complete" if best is not None else "exhausted",
            "grammar_valid": best is not None,
            "reference_exact": best is not None and normalized_parser(best) == normalized_gold(row["tree"]),
        }

    gc.collect()
    started = perf_counter()
    rows = [one(row) for row in corpus]
    elapsed = (perf_counter() - started) * 1000
    peak = memory_peak(one, corpus, memory_sample)
    return aggregate("production-vector", rows, elapsed, peak)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=ROOT / "data" / "seman2_reference_300_compact.json")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "superparser" / "data")
    ap.add_argument("--model", type=Path, default=ROOT / "superparser" / "data" / "predictive_transitions.json")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--max-states", type=int, default=20_000)
    ap.add_argument("--memory-sample", type=int, default=10)
    ap.add_argument("--include-untrained", action="store_true")
    ap.add_argument("--v2-only", action="store_true", help="benchmark production and the retained V2 hybrid")
    ap.add_argument("--fast-states", type=int, default=64)
    args = ap.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))["sentences"][:args.limit]
    cold = {
        engine: cold_probe(engine, args.data_dir, args.model, corpus[0]["text"])
        for engine in (("production", "hybrid") if args.v2_only else ("production", "predictive", "hybrid"))
    }
    production = Parser.from_dir(args.data_dir, cache_size=0)
    model = TransitionModel.load(args.model)
    trained = PredictiveParser.from_dir(
        args.data_dir, model=model, max_states=args.max_states,
    )
    hybrid = HybridPredictiveParser.from_dir(
        args.data_dir, model=model, max_states=args.max_states,
        fast_states=args.fast_states, lookahead=1,
    )
    feasibility = PredictiveGrammar(production.resources.grammar, measure_lr0=True).report.as_dict()
    payload: dict[str, Any] = {
        "format": "seman2-predictive-benchmark-v2",
        "protocol": {
            "corpus": str(args.corpus), "sentences": len(corpus),
            "warm_wordnet": True, "parser_sentence_cache": False,
            "memory": f"separate tracemalloc pass over first {min(args.memory_sample, len(corpus))} sentences",
            "reference_exact_is_diagnostic_not_acceptance_contract": True,
            "cold_probe": "fresh interpreter; operating-system file cache uncontrolled",
        },
        "cold_start": cold,
        "grammar_feasibility": feasibility,
        "model_metadata": trained.model.metadata,
        "engines": {
            "production": bench_production(production, corpus, memory_sample=args.memory_sample),
            "predictive_v2_hybrid": bench_predictive(
                "predictive-v2-hybrid", hybrid, corpus, memory_sample=args.memory_sample,
            ),
        },
    }
    if not args.v2_only:
        payload["engines"]["predictive_trained"] = bench_predictive(
            "predictive-trained", trained, corpus, memory_sample=args.memory_sample,
        )
    if args.include_untrained:
        untrained = PredictiveParser.from_dir(
            args.data_dir, model=TransitionModel(), max_states=args.max_states,
        )
        payload["engines"]["predictive_untrained"] = bench_predictive(
            "predictive-untrained", untrained, corpus, memory_sample=args.memory_sample,
        )
    rendered = json.dumps(payload, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
