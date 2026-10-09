"""Dedicated POC-01 benchmark; not part of the edit/test loop."""

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

from research.induction import parse_to_observation, propose_root_generalizations
from seman_parser import Parser, __version__


POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures" / "manifest.json"
DEFAULT_DATA = Path(__file__).resolve().parents[5] / "data"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def root_snapshot(graph, root_id: str) -> dict:
    nodes = {node.node_id: node for node in graph.nodes}
    children: dict[str, list] = {}
    for edge in graph.edges:
        if edge.role == "CHILD":
            children.setdefault(edge.source, []).append(edge)

    def expand(node_id: str) -> dict:
        row = nodes[node_id].properties
        ordered = sorted(children.get(node_id, ()), key=lambda edge: edge.position)
        row["children"] = [expand(edge.target) for edge in ordered]
        return row

    return expand(root_id)


def run(manifest_path: Path, data_dir: Path, limit: int | None = None) -> dict:
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    cases = manifest["cases"][:limit]
    parser = Parser.from_dir(data_dir)
    graph_cache = {}

    def graph(text: str):
        if text not in graph_cache:
            graph_cache[text] = parse_to_observation(
                parser.parse(text).result,
                parser_version=__version__,
            )
        return graph_cache[text]

    rows: list[dict] = []
    total_candidates = 0
    exact_candidates = 0
    for case in cases:
        left = graph(case["left"])
        right = graph(case["right"])
        heldout = graph(case["heldout"]) if case.get("heldout") else None

        started = time.perf_counter()
        candidates = propose_root_generalizations(left, right, limit=50)
        proposal_ms = (time.perf_counter() - started) * 1000

        reconstructed = [
            candidate.instantiate_left() == root_snapshot(left, candidate.left_root_id)
            and candidate.instantiate_right() == root_snapshot(right, candidate.right_root_id)
            for candidate in candidates
        ]
        heldout_matches = 0
        if heldout is not None:
            heldout_matches = sum(
                candidate.template.match(heldout, root_id) is not None
                for candidate in candidates
                for root_id in heldout.root_ids
            )

        del candidates
        gc.collect()
        tracemalloc.start()
        measured = propose_root_generalizations(left, right, limit=50)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        has_candidate = bool(measured)
        heldout_ok = bool(heldout_matches) if case["expected_heldout_match"] else not heldout_matches
        expectation_met = (
            has_candidate == case["expected_candidate"] and heldout_ok
        )
        candidate_count = len(measured)
        total_candidates += candidate_count
        exact_candidates += sum(reconstructed)
        rows.append(
            {
                "id": case["id"],
                "left_roots": len(left.root_ids),
                "right_roots": len(right.root_ids),
                "candidate_count_capped": candidate_count,
                "all_candidates_reconstruct": all(reconstructed),
                "heldout_matches": heldout_matches,
                "expectation_met": expectation_met,
                "proposal_ms": round(proposal_ms, 3),
                "proposal_peak_memory_mb": round(peak / (1024 * 1024), 3),
                "best_variable_count": measured[0].evaluation.variable_count if measured else None,
                "best_residual_variable_count": measured[0].evaluation.residual_variable_count if measured else None,
                "best_estimated_gain_bytes": measured[0].evaluation.estimated_gain_bytes if measured else None
            }
        )

    times = [row["proposal_ms"] for row in rows]
    return {
        "poc": "POC-01",
        "parser_version": __version__,
        "schema_version": manifest["schema_version"],
        "data_manifest": sha256(raw_manifest).hexdigest(),
        "case_count": len(rows),
        "metrics": {
            "reconstruction_exact_rate": exact_candidates / total_candidates if total_candidates else 1.0,
            "case_expectation_rate": sum(row["expectation_met"] for row in rows) / len(rows),
            "median_proposal_ms": round(median(times), 3),
            "p95_proposal_ms": round(percentile(times, 0.95), 3),
            "peak_memory_mb": max(row["proposal_peak_memory_mb"] for row in rows),
        },
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.data, args.limit), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

