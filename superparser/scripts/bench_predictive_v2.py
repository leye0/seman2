#!/usr/bin/env python3
"""Short, repeatable ablation loop for Predictive V2."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "superparser"))

from scripts.evaluate_reference_300 import normalized_gold, normalized_parser  # noqa: E402
from seman_parser.engine import ParserResources  # noqa: E402
from seman_parser.predictive import (  # noqa: E402
    HybridPredictiveParser, PredictiveParser, SharedPredictiveParser, TransitionModel,
)


SAMPLE_INDICES = tuple(
    list(range(0, 15))       # simple
    + list(range(50, 65))    # ordinary/embedded
    + list(range(215, 225))  # PP/multiple attachments
    + list(range(225, 235))  # relatives/gaps
    + list(range(275, 285))  # nested/complex coordination
)


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    point = (len(values) - 1) * p
    lower = int(point)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] * (upper - point) + values[upper] * (point - lower)


def summarize(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    times = [row["stats"]["total_wall_ms"] for row in rows]
    completed = [row for row in rows if row["completed"]]
    counter_names = (
        "transitions_executed", "configurations_visited", "unique_configurations",
        "revisited_configurations", "backtracks", "max_backtrack_depth",
        "shared_nodes", "ambiguity_points", "repeated_transitions",
        "premature_reductions", "feature_rejections", "lookahead_rejections",
    )
    return {
        "name": name,
        "sentences": len(rows),
        "native_coverage": round(len(completed) / len(rows), 6),
        "grammatically_valid": round(len(completed) / len(rows), 6),
        "exact_normalized_diagnostic": round(
            sum(row["exact"] for row in rows) / len(rows), 6,
        ),
        "wall_ms": {
            "p50": round(percentile(times, .5), 4),
            "p95": round(percentile(times, .95), 4),
            "p99": round(percentile(times, .99), 4),
            "max": round(max(times), 4), "total": round(sum(times), 4),
        },
        "totals": {
            key: sum(int(row["stats"].get(key, 0)) for row in rows)
            for key in counter_names
        },
        "shared_escalations": sum(bool(row["stats"].get("shared_escalation")) for row in rows),
        "failures": [row["id"] for row in rows if not row["completed"]],
    }


def run_variant(
    name: str, parser: PredictiveParser, rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parser.parse("Warm engines turn.")
    output = []
    gc.collect()
    for row in rows:
        result = parser.parse(row["text"])
        output.append({
            "id": row["id"], "text": row["text"], "completed": result.completed,
            "exact": bool(
                result.item is not None
                and normalized_parser(result.item) == normalized_gold(row["tree"])
            ),
            "stats": result.stats,
        })
    return summarize(name, output), output


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=ROOT / "data" / "seman2_reference_300_compact.json")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "superparser" / "data")
    ap.add_argument("--model", type=Path, default=ROOT / "superparser" / "data" / "predictive_transitions.json")
    ap.add_argument("--output", type=Path, default=ROOT / "superparser" / "predictive_v2_ablation_60.json")
    ap.add_argument("--max-states", type=int, default=5_000)
    args = ap.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))["sentences"]
    rows = [corpus[index] for index in SAMPLE_INDICES]
    resources = ParserResources.from_dir(args.data_dir)
    model = TransitionModel.load(args.model)
    variants: list[tuple[str, PredictiveParser]] = [
        ("v1_no_memo", PredictiveParser(resources, model=model, max_states=args.max_states, memoization=False)),
        ("v1_memo", PredictiveParser(resources, model=model, max_states=args.max_states)),
        ("v1_first_follow", PredictiveParser(resources, model=model, max_states=args.max_states, lookahead=1)),
        ("v1_lookahead2_conservative", PredictiveParser(resources, model=model, max_states=args.max_states, lookahead=2)),
        ("v1_context_items", PredictiveParser(resources, model=model, max_states=args.max_states, contextual_statistics=True)),
        ("v1_delayed", PredictiveParser(resources, model=model, max_states=args.max_states, lookahead=1, delayed_commitments=True)),
        ("v2_shared", SharedPredictiveParser(resources, model=model, max_states=50_000, lookahead=1)),
        ("v2_hybrid", HybridPredictiveParser(resources, model=model, max_states=50_000, fast_states=128, lookahead=1)),
    ]
    summaries = []
    details: dict[str, Any] = {}
    for name, parser in variants:
        started = perf_counter()
        summary, variant_rows = run_variant(name, parser, rows)
        summary["loop_wall_ms"] = round((perf_counter() - started) * 1000, 4)
        summaries.append(summary)
        details[name] = variant_rows
        print(name, summary["native_coverage"], summary["wall_ms"], file=sys.stderr, flush=True)
    baseline_rows = details["v1_memo"]
    expensive = sorted(
        baseline_rows, key=lambda row: row["stats"]["total_wall_ms"], reverse=True,
    )[:10]
    diagnostics = [
        {
            "id": row["id"], "text": row["text"],
            "total_transitions": row["stats"]["transitions_executed"],
            "unique_configurations": row["stats"]["unique_configurations"],
            "revisits": row["stats"]["revisited_configurations"],
            "backtracks": row["stats"]["backtracks"],
            "max_backtrack_depth": row["stats"]["max_backtrack_depth"],
            "premature_reductions": row["stats"]["premature_reductions"],
            "repeated_transitions": row["stats"]["repeated_transitions"],
            "early_conflict_hotspots": row["stats"]["early_conflict_hotspots"],
        }
        for row in expensive
    ]
    payload = {
        "format": "seman2-predictive-v2-ablation-v1",
        "sample": {
            "sentences": len(rows), "indices_1_based": [index + 1 for index in SAMPLE_INDICES],
            "composition": {"simple": 15, "ordinary": 15, "pp": 10, "relative": 10, "complex": 10},
        },
        "variants": summaries,
        "top10_v1_diagnostics": diagnostics,
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
