"""Dedicated POC-00 benchmark; intentionally not part of the unit-test loop."""

from __future__ import annotations

import argparse
import gc
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import median
import time
import tracemalloc

from research.induction import (
    ObservationGraph,
    parse_to_observation,
    structural_snapshot_from_parse,
)
from seman_parser import DiscourseProcessor, Parser, __version__


POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures" / "manifest.json"
DEFAULT_DATA = Path(__file__).resolve().parents[5] / "data"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def run(manifest_path: Path, data_dir: Path, limit: int | None = None) -> dict:
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    cases = manifest["cases"][:limit]
    parser = Parser.from_dir(data_dir)
    discourse_processors: dict[str, DiscourseProcessor] = {}
    rows: list[dict] = []
    for case in cases:
        parse_start = time.perf_counter()
        projection_args: dict = {}
        discourse_group = case.get("discourse_group")
        if discourse_group:
            processor = discourse_processors.setdefault(
                discourse_group, DiscourseProcessor(parser)
            )
            analysis = processor.read(case["text"])
            result = analysis.report.result
            projection_args = {
                "mentions": analysis.mentions,
                "reference_links": analysis.reference_links,
                "mention_catalog": processor.state.mentions,
            }
        else:
            result = parser.parse(case["text"]).result
        parse_ms = (time.perf_counter() - parse_start) * 1000

        projection_start = time.perf_counter()
        graph = parse_to_observation(
            result, parser_version=__version__, **projection_args
        )
        projection_ms = (time.perf_counter() - projection_start) * 1000
        canonical = graph.canonical_json()
        del graph
        gc.collect()

        # Measure allocations in a separate pass so tracemalloc does not
        # distort the reported projection latency or include parser memory.
        tracemalloc.start()
        graph = parse_to_observation(
            result, parser_version=__version__, **projection_args
        )
        _, projection_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        restored = ObservationGraph.from_json(canonical)
        structural_roundtrip = (
            restored.structural_snapshot() == structural_snapshot_from_parse(result)
        )
        reference_count = sum(edge.role == "REFERENCE" for edge in graph.edges)
        completion_met = result.completed == case["expected_completed"]
        references_met = reference_count >= case.get("expected_reference_min", 0)
        rows.append(
            {
                "id": case["id"],
                "completed": result.completed,
                "expected_completed": case["expected_completed"],
                "expectation_met": completion_met and references_met,
                "canonical_roundtrip": restored.canonical_json() == canonical == graph.canonical_json(),
                "structural_roundtrip": structural_roundtrip,
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "root_alternatives": len(graph.root_ids),
                "reference_candidates": reference_count,
                "json_bytes": len(graph.canonical_json().encode("utf-8")),
                "parse_ms": round(parse_ms, 3),
                "projection_ms": round(projection_ms, 3),
                "projection_peak_memory_mb": round(projection_peak / (1024 * 1024), 3),
            }
        )
    projection_times = [row["projection_ms"] for row in rows]
    return {
        "poc": "POC-00",
        "parser_version": __version__,
        "schema_version": manifest["schema_version"],
        "data_manifest": sha256(raw_manifest).hexdigest(),
        "case_count": len(rows),
        "metrics": {
            "roundtrip_exact_rate": sum(
                row["canonical_roundtrip"] and row["structural_roundtrip"]
                for row in rows
            ) / len(rows),
            "parser_expectation_rate": sum(row["expectation_met"] for row in rows) / len(rows),
            "median_projection_ms": round(median(projection_times), 3),
            "p95_projection_ms": round(percentile(projection_times, 0.95), 3),
            "peak_memory_mb": max(row["projection_peak_memory_mb"] for row in rows),
        },
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.manifest, args.data, args.limit)
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()

