#!/usr/bin/env python3
"""TIME-01: observable partial order with quarantined external anchors."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import networkx as nx

POC_DIR = Path(__file__).resolve().parent
OUTPUT = POC_DIR / "output"
ORDER_TYPES = {"precedes_in_source", "reply_to_precedence", "observed_predecessor"}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_anchor(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def relation_signature(graph: nx.MultiDiGraph) -> str:
    cognitive = {
        "nodes": sorted(node for node, data in graph.nodes(data=True) if data["kind"] == "observation"),
        "edges": sorted(
            (source, target, data["relation_type"])
            for source, target, data in graph.edges(data=True)
            if data["layer"] == "observable_relation"
        ),
    }
    return stable_hash(cognitive)


def run_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    graph = nx.MultiDiGraph()
    order = nx.DiGraph()
    for node in fixture["nodes"]:
        graph.add_node(node, kind="observation")
        order.add_node(node)
    for index, relation in enumerate(fixture["relations"]):
        order_bearing = relation.get("order_bearing", relation["type"] in ORDER_TYPES)
        graph.add_edge(
            relation["source"], relation["target"], key=f"relation-{index}",
            layer="observable_relation", relation_type=relation["type"],
            order_bearing=order_bearing, provenance="fixture_source",
        )
        if order_bearing:
            order.add_edge(relation["source"], relation["target"], relation_type=relation["type"])

    signature_before_anchors = relation_signature(graph)
    anchors_by_target: dict[str, list[dict[str, Any]]] = {}
    for anchor in fixture["anchors"]:
        graph.add_node(anchor["id"], kind="external_anchor", anchor_type=anchor["type"], value=anchor["value"])
        graph.add_edge(
            anchor["id"], anchor["target"], key=f"anchors-{anchor['id']}",
            layer="provenance", relation_type="anchors_source_occurrence", order_bearing=False,
        )
        anchors_by_target.setdefault(anchor["target"], []).append(anchor)

    consistent = nx.is_directed_acyclic_graph(order)
    cycles = [] if consistent else [cycle for cycle in nx.simple_cycles(order)]
    closure = nx.transitive_closure_dag(order) if consistent else nx.DiGraph()
    ordered_pairs = sorted([list(edge) for edge in closure.edges()]) if consistent else []
    incomparable_pairs = []
    if consistent:
        for left, right in combinations(sorted(fixture["nodes"]), 2):
            if not closure.has_edge(left, right) and not closure.has_edge(right, left):
                incomparable_pairs.append([left, right])

    anchor_conflicts = []
    if consistent:
        for left, right in closure.edges():
            for left_anchor in anchors_by_target.get(left, []):
                for right_anchor in anchors_by_target.get(right, []):
                    if parse_anchor(left_anchor["value"]) > parse_anchor(right_anchor["value"]):
                        anchor_conflicts.append({
                            "ordered_pair": [left, right], "left_anchor": left_anchor["id"],
                            "right_anchor": right_anchor["id"],
                            "classification": "external_anchor_conflicts_with_observable_order",
                            "effect_on_observable_order": "none",
                        })

    graph_without_anchors = graph.copy()
    graph_without_anchors.remove_nodes_from(
        [node for node, data in graph_without_anchors.nodes(data=True) if data["kind"] == "external_anchor"]
    )
    signature_after_anchor_removal = relation_signature(graph_without_anchors)
    result = {
        "fixture_id": fixture["id"], "consistent_observable_order": consistent,
        "observable_relations": [
            {**relation, "order_bearing": relation.get("order_bearing", relation["type"] in ORDER_TYPES)}
            for relation in fixture["relations"]
        ],
        "ordered_pairs": ordered_pairs, "incomparable_pairs": incomparable_pairs,
        "cycles": cycles, "external_anchors": fixture["anchors"],
        "anchor_conflicts": anchor_conflicts, "anchor_edges_promoted_to_cognitive_order": 0,
        "relational_signature_before_anchors": signature_before_anchors,
        "relational_signature_after_anchor_removal": signature_after_anchor_removal,
        "anchor_removal_preserves_relational_order": signature_before_anchors == signature_after_anchor_removal,
    }
    oracle = fixture["oracle"]
    assert result["consistent_observable_order"] == oracle["consistent"]
    assert result["ordered_pairs"] == sorted(oracle["ordered_pairs"])
    assert result["incomparable_pairs"] == sorted(oracle["incomparable_pairs"])
    assert len(result["anchor_conflicts"]) == oracle["anchor_conflict_count"]
    assert result["anchor_removal_preserves_relational_order"]
    return result


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    results = [run_fixture(fixture) for fixture in fixtures]
    summary = {
        "fixture_count": len(results),
        "consistent_fixture_count": sum(result["consistent_observable_order"] for result in results),
        "inconsistent_fixture_count": sum(not result["consistent_observable_order"] for result in results),
        "incomparable_pair_count": sum(len(result["incomparable_pairs"]) for result in results),
        "external_anchor_count": sum(len(result["external_anchors"]) for result in results),
        "anchor_conflict_count": sum(len(result["anchor_conflicts"]) for result in results),
        "anchor_edges_promoted_to_cognitive_order": 0,
        "all_anchor_removal_invariants_passed": all(result["anchor_removal_preserves_relational_order"] for result in results),
        "verdict": "GO_OBSERVABLE_ORDER_WITH_QUARANTINED_EXTERNAL_ANCHORS",
    }
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "networkx": nx.__version__,
        "schema": "seman2.temporal-observable-order-poc.v1",
        "order_semantics": "strict partial order; no order inferred from anchor values",
    }
    write_json(OUTPUT / "results.json", results)
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "versions-and-parameters.json", versions)
    write_json(OUTPUT / "observable-order-contract.json", {
        "observable_relation_layer": sorted(ORDER_TYPES),
        "external_anchor_node_types": ["ExternalClockAnchor", "ExternalCalendarAnchor", "SourceTimestamp"],
        "anchor_edge": "anchors_source_occurrence",
        "forbidden_implicit_operation": "derive cognitive temporal order from clock/calendar value",
        "invariant": "removing every external anchor preserves the observable relational subgraph",
    })
    print(f"TIME-01: {len(results)} fixtures; {summary['inconsistent_fixture_count']} cycle; {summary['anchor_conflict_count']} quarantined anchor conflict")


if __name__ == "__main__":
    main()
