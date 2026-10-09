"""Dedicated POC-02 benchmark; not part of the edit/test loop."""

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
from typing import Any

from research.induction import (
    AntiUnificationError,
    anti_unify_with_ports,
    generalize_reference_candidates,
    parse_to_observation,
)
from seman_parser import DiscourseProcessor, Parser, __version__
from seman_parser.chart import ChartItem, PackedNode, ParseResult, Provenance
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import LexicalLattice, tokenize
from seman_parser.semantics import SemanticGraph, SemanticPackage


POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures" / "manifest.json"
DEFAULT_DATA = Path(__file__).resolve().parents[5] / "data"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def fixture_graph(spec: dict[str, Any]):
    items: list[ChartItem] = []
    cursor = 0

    def build(node: dict[str, Any]) -> ChartItem:
        nonlocal cursor
        children = tuple(build(child) for child in node.get("children", ()))
        if children:
            start, end = children[0].start, children[-1].end
        else:
            start, end = cursor, cursor + 1
            cursor = end
        rule_id = node.get("rule_id")
        detail: dict[str, Any] = {"rule_id": rule_id} if rule_id else {}
        surface = node.get("surface")
        if surface is not None:
            detail.update({"surface": surface, "lemma": str(surface).lower()})
        item = ChartItem(
            start=start,
            end=end,
            category=node["category"],
            features=FeatureStructure.build(node.get("features", {})),
            semantic=SemanticPackage(SemanticGraph()),
            score=1.0,
            provenance=Provenance(
                source="rule" if rule_id else "fixture",
                detail=detail,
            ),
            children=children,
            rule_id=rule_id,
        )
        items.append(item)
        return item

    root = build(spec)
    text = " ".join(
        str(node.provenance.detail.get("surface", node.category)).lower()
        for node in reversed(items)
        if not node.children
    )
    packed = {
        (node.start, node.end, index): PackedNode(
            start=node.start,
            end=node.end,
            category=node.category,
            best=node,
            alternatives=[node],
        )
        for index, node in enumerate(items)
    }
    result = ParseResult(
        text=text,
        lattice=LexicalLattice(text=text, tokens=tokenize(text), candidates=()),
        packed=packed,
        roots=(root,),
        completed=True,
    )
    return parse_to_observation(result, parser_version="fixture")


def root_snapshot(graph, root_id: str) -> dict[str, Any]:
    nodes = {node.node_id: node for node in graph.nodes}
    children: dict[str, list] = {}
    for edge in graph.edges:
        if edge.role == "CHILD":
            children.setdefault(edge.source, []).append(edge)

    def expand(node_id: str) -> dict[str, Any]:
        row = nodes[node_id].properties
        ordered = sorted(children.get(node_id, ()), key=lambda edge: edge.position)
        row["children"] = [expand(edge.target) for edge in ordered]
        return row

    return expand(root_id)


def discourse_graph(parser: Parser, sentences: list[str]):
    processor = DiscourseProcessor(parser)
    analysis = None
    for sentence in sentences:
        analysis = processor.read(sentence)
    assert analysis is not None
    return parse_to_observation(
        analysis.report.result,
        parser_version=__version__,
        mentions=analysis.mentions,
        reference_links=analysis.reference_links,
        mention_catalog=processor.state.mentions,
    )


def reference_rows(graph) -> set[str]:
    nodes = {node.node_id: node for node in graph.nodes}
    return {
        json.dumps(
            {
                "source_port": "REF_SOURCE",
                "target_port": "REF_TARGET",
                "kind": edge.properties["kind"],
                "rule_id": edge.properties["rule_id"],
                "source": nodes[edge.source].properties,
                "target": nodes[edge.target].properties,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for edge in graph.edges
        if edge.role == "REFERENCE"
        and nodes[edge.source].kind == nodes[edge.target].kind == "MENTION"
    }


def run(manifest_path: Path, data_dir: Path) -> dict[str, Any]:
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    subgraph_rows: list[dict[str, Any]] = []
    reference_rows_out: list[dict[str, Any]] = []

    for case in manifest["subgraph_cases"]:
        left = fixture_graph(case["left"])
        right = fixture_graph(case["right"])
        heldout = fixture_graph(case["heldout"]) if case["heldout"] else None
        started = time.perf_counter()
        try:
            candidate = anti_unify_with_ports(
                left, left.root_ids[0], right, right.root_ids[0]
            )
        except AntiUnificationError:
            candidate = None
        latency_ms = (time.perf_counter() - started) * 1000
        reconstruction = candidate is not None and (
            candidate.instantiate_left() == root_snapshot(left, left.root_ids[0])
            and candidate.instantiate_right() == root_snapshot(right, right.root_ids[0])
        )
        heldout_match = bool(
            candidate is not None
            and heldout is not None
            and candidate.template.match(heldout, heldout.root_ids[0]) is not None
        )
        candidate_expected = (candidate is not None) == case["expected_candidate"]
        heldout_expected = heldout_match == case["expected_heldout_match"]

        gc.collect()
        tracemalloc.start()
        try:
            anti_unify_with_ports(left, left.root_ids[0], right, right.root_ids[0])
        except AntiUnificationError:
            pass
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        subgraph_rows.append(
            {
                "id": case["id"],
                "candidate": candidate is not None,
                "port_count": sum(
                    node.kind == "SUBGRAPH_PORT"
                    for node in candidate.template.nodes
                ) if candidate else 0,
                "exact_reconstruction": reconstruction if candidate else None,
                "heldout_match": heldout_match,
                "expectation_met": candidate_expected and heldout_expected,
                "latency_ms": round(latency_ms, 3),
                "peak_memory_mb": round(peak / (1024 * 1024), 3),
            }
        )

    parser = Parser.from_dir(data_dir)
    for case in manifest["reference_cases"]:
        left = discourse_graph(parser, case["left"])
        right = discourse_graph(parser, case["right"])
        heldout = discourse_graph(parser, case["heldout"])
        started = time.perf_counter()
        patterns = generalize_reference_candidates(left, right)
        latency_ms = (time.perf_counter() - started) * 1000
        left_observed = reference_rows(left)
        right_observed = reference_rows(right)
        left_rebuilt = {
            json.dumps(
                pattern.instantiate("left"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for pattern in patterns
        }
        right_rebuilt = {
            json.dumps(
                pattern.instantiate("right"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for pattern in patterns
        }
        heldout_matches = sum(len(pattern.match_graph(heldout)) for pattern in patterns)
        target_kinds = sorted({str(pattern.target_template["kind"]) for pattern in patterns})

        gc.collect()
        tracemalloc.start()
        generalize_reference_candidates(left, right)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        left_coverage = len(left_observed & left_rebuilt) / len(left_observed)
        right_coverage = len(right_observed & right_rebuilt) / len(right_observed)
        expected_kinds = set(case["expected_target_kinds"])
        expectation_met = (
            len(patterns) >= case["minimum_patterns"]
            and heldout_matches >= case["minimum_heldout_matches"]
            and all(pattern.is_open_candidate for pattern in patterns)
            and expected_kinds.issubset(target_kinds)
            and left_coverage == right_coverage == 1.0
        )
        reference_rows_out.append(
            {
                "id": case["id"],
                "observed_left_alternatives": len(left_observed),
                "observed_right_alternatives": len(right_observed),
                "pattern_count": len(patterns),
                "all_patterns_remain_open": all(
                    pattern.is_open_candidate for pattern in patterns
                ),
                "left_reconstruction_coverage": left_coverage,
                "right_reconstruction_coverage": right_coverage,
                "heldout_matches": heldout_matches,
                "target_kinds": target_kinds,
                "expectation_met": expectation_met,
                "latency_ms": round(latency_ms, 3),
                "peak_memory_mb": round(peak / (1024 * 1024), 3),
            }
        )

    timed_rows = subgraph_rows + reference_rows_out
    times = [row["latency_ms"] for row in timed_rows]
    positive_subgraphs = [row for row in subgraph_rows if row["candidate"]]
    return {
        "poc": "POC-02",
        "parser_version": __version__,
        "schema_version": manifest["schema_version"],
        "data_manifest": sha256(raw_manifest).hexdigest(),
        "metrics": {
            "subgraph_exact_reconstruction_rate": sum(
                row["exact_reconstruction"] is True for row in positive_subgraphs
            ) / len(positive_subgraphs),
            "reference_reconstruction_coverage": min(
                min(row["left_reconstruction_coverage"], row["right_reconstruction_coverage"])
                for row in reference_rows_out
            ),
            "open_reference_pattern_rate": sum(
                row["all_patterns_remain_open"] for row in reference_rows_out
            ) / len(reference_rows_out),
            "case_expectation_rate": sum(
                row["expectation_met"] for row in timed_rows
            ) / len(timed_rows),
            "median_latency_ms": round(median(times), 3),
            "p95_latency_ms": round(percentile(times, 0.95), 3),
            "peak_memory_mb": max(row["peak_memory_mb"] for row in timed_rows),
        },
        "subgraph_cases": subgraph_rows,
        "reference_cases": reference_rows_out,
    }


def main() -> None:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    argument_parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = argument_parser.parse_args()
    print(json.dumps(run(args.manifest, args.data), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
