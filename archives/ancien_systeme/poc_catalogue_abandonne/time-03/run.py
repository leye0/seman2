#!/usr/bin/env python3
"""TIME-03: Reichenbach E/R/S constraint structures."""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx


POC_DIR = Path(__file__).resolve().parent
OUTPUT = POC_DIR / "output"


class UnionFind:
    def __init__(self, values: set[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def solve(fixture: dict[str, Any]) -> dict[str, Any]:
    bindings = []
    raw_constraints = []
    nodes: set[str] = set()
    for context in fixture["contexts"]:
        role_bindings = {role: context[role] for role in ("E", "R", "S")}
        bindings.append({"context_id": context["id"], "roles": role_bindings})
        nodes.update(role_bindings.values())
        for left_role, operator, right_role in context["constraints"]:
            raw_constraints.append({
                "context_id": context["id"], "left_role": left_role, "right_role": right_role,
                "left": role_bindings[left_role], "operator": operator, "right": role_bindings[right_role],
                "formalism": "Reichenbach_ERS",
            })

    union_find = UnionFind(nodes)
    for constraint in raw_constraints:
        if constraint["operator"] == "=":
            union_find.union(constraint["left"], constraint["right"])

    order = nx.DiGraph()
    order.add_nodes_from({union_find.find(node) for node in nodes})
    equality_order_conflicts = []
    for constraint in raw_constraints:
        if constraint["operator"] != "<":
            continue
        left, right = union_find.find(constraint["left"]), union_find.find(constraint["right"])
        if left == right:
            equality_order_conflicts.append(constraint)
        else:
            order.add_edge(left, right, context_id=constraint["context_id"])
    consistent = not equality_order_conflicts and nx.is_directed_acyclic_graph(order)
    cycles = [] if consistent else list(nx.simple_cycles(order))
    closure = nx.transitive_closure_dag(order) if consistent else nx.DiGraph()

    def query(left: str, operator: str, right: str) -> bool:
        lroot, rroot = union_find.find(left), union_find.find(right)
        return lroot == rroot if operator == "=" else closure.has_edge(lroot, rroot)

    checked = []
    if consistent:
        for left, operator, right in fixture["oracle"]["relations"]:
            passed = query(left, operator, right)
            assert passed, (fixture["id"], left, operator, right)
            checked.append({"left": left, "operator": operator, "right": right, "oracle_passed": passed})
    assert consistent == fixture["oracle"]["consistent"]
    minimum = fixture["oracle"].get("minimum_distinct_temporal_nodes", 0)
    assert len(nodes) >= minimum
    return {
        "fixture_id": fixture["id"], "text": fixture["text"], "language": fixture["language"],
        "analysis_source": "controlled_Reichenbach_Temporal_DRT_adapter_fixture",
        "bindings": bindings, "constraints": raw_constraints,
        "distinct_temporal_nodes": sorted(nodes), "equivalence_classes": {
            root: sorted(node for node in nodes if union_find.find(node) == root)
            for root in sorted({union_find.find(node) for node in nodes})
        },
        "consistent": consistent, "cycles": cycles,
        "equality_order_conflicts": equality_order_conflicts,
        "entailed_strict_orders": sorted([list(edge) for edge in closure.edges()]) if consistent else [],
        "oracle_checks": checked,
        "external_surface_values": fixture.get("external_surface_values", []),
        "absolute_coordinate_invented": False,
        "single_normalized_value_used_as_temporal_model": False,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    results = [solve(fixture) for fixture in fixtures]
    reported = next(result for result in results if result["fixture_id"] == "fr-reported-relative-time")
    information_loss = {
        "fixture_id": reported["fixture_id"],
        "relational_structure": {
            "distinct_nodes": len(reported["distinct_temporal_nodes"]),
            "context_count": len(reported["bindings"]),
            "entailed_orders": reported["entailed_strict_orders"],
        },
        "surface_normalization_only": reported["external_surface_values"],
        "lost_if_collapsed": [
            "matrix event versus utterance time", "embedded speech-time shift",
            "departure relative to Julie's speech", "separate reference times and scopes",
        ],
        "collapse_rejected": True,
    }
    summary = {
        "fixture_count": len(results), "consistent_fixture_count": sum(r["consistent"] for r in results),
        "inconsistent_fixture_count": sum(not r["consistent"] for r in results),
        "languages": sorted({r["language"] for r in results}),
        "reported_speech_context_count": len(reported["bindings"]),
        "absolute_coordinates_invented": 0,
        "verdict": "GO_REICHENBACH_ERS_WITH_SCOPED_RELATIVE_TIME",
    }
    write_json(OUTPUT / "results.json", results)
    write_json(OUTPUT / "normalization-information-loss.json", information_loss)
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "versions-and-parameters.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "networkx": nx.__version__,
        "formalisms": ["Reichenbach_ERS", "Temporal_DRT_inspired_scoping"],
        "coordinate_policy": "no calendar or clock coordinates synthesized",
    })
    print(f"TIME-03: {len(results)} fixtures; {summary['reported_speech_context_count']} scoped contexts in reported speech; no absolute coordinate")


if __name__ == "__main__":
    main()
