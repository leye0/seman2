#!/usr/bin/env python3
"""Valide l'ancien échafaudage durable RUN-01/02, non le blueprint cognitif."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "plans/archives/runtime_service_graph.json"


def main() -> int:
    plan = json.loads(PLAN.read_text())
    nodes = {row["id"]: row for row in plan["nodes"]}
    assert len(nodes) == len(plan["nodes"]), "duplicate node"
    assert "soar-runtime" in nodes and nodes["soar-runtime"]["memory"] == "soar-working-memory"
    assert len(nodes["soar-runtime"]["control_scope"]) >= 5
    assert "bounded-hypothesis-beam" in nodes["soar-runtime"]["working_memory_partitions"]
    assert nodes["observation-ledger"]["memory"].startswith("durable")
    assert nodes["hypothesis-manager"]["memory"].startswith("durable")
    assert plan["memory_policy"]["full_corpus_in_active_memory"] is False
    assert plan["evaluation_plane"]["in_runtime_data_path"] is False

    adjacency = {node_id: set() for node_id in nodes}
    reverse = {node_id: set() for node_id in nodes}
    for edge in plan["edges"]:
        assert edge["from"] in nodes and edge["to"] in nodes
        assert edge["artifact"] and edge["kind"] in {"data", "control", "feedback", "background", "decision-loop"}
        if edge["kind"] == "feedback":
            assert edge["epoch_delta"] == 1
            continue
        if edge["kind"] == "decision-loop":
            assert edge["epoch_delta"] == 0 and edge["from"] == "soar-runtime"
            continue
        assert edge["epoch_delta"] == 0
        adjacency[edge["from"]].add(edge["to"])
        reverse[edge["to"]].add(edge["from"])

    indegree = {node_id: len(parents) for node_id, parents in reverse.items()}
    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = []
    while ready:
        node = ready.pop(0)
        visited.append(node)
        for target in sorted(adjacency[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    assert len(visited) == len(nodes), "within-epoch processing/control graph contains a cycle"

    reachable = {"source-reader"}
    changed = True
    while changed:
        changed = False
        for source in tuple(reachable):
            for target in adjacency[source]:
                if target not in reachable:
                    reachable.add(target)
                    changed = True
    required_reachable = {
        "native-analysis-ledger", "representation-adapters", "hypothesis-manager",
        "situation-state", "active-beam", "soar-runtime", "communicative-planning",
        "surface-realization", "system-output-ledger",
    }
    assert required_reachable <= reachable, sorted(required_reachable - reachable)

    soar_inputs = reverse["soar-runtime"]
    assert {"active-beam", "situation-state", "candidate-transformations"} <= soar_inputs
    soar_outputs = {
        edge["to"] for edge in plan["edges"] if edge["from"] == "soar-runtime"
    }
    assert {"structural-retrieval", "candidate-transformations", "communicative-planning"} <= soar_outputs

    barrier = plan["checkpoint"]["barrier_order"]
    restore = plan["checkpoint"]["restore_order"]
    assert "capture-active-context-and-beam" in barrier
    assert "rebuild-working-memory-from-active-context-snapshot" in restore
    assert "write-atomic-checkpoint-manifest" in barrier

    print(json.dumps({
        "status": "GO-TRANSITIONAL-RUNTIME-SCAFFOLD-STRUCTURALLY-VALID",
        "nodes": len(nodes),
        "edges": len(plan["edges"]),
        "within_epoch_topological_order": visited,
        "feedback_edges": sum(edge["kind"] == "feedback" for edge in plan["edges"]),
        "soar_inputs": sorted(soar_inputs),
        "soar_outputs": sorted(soar_outputs),
        "checkpoint_steps": len(barrier),
        "restore_steps": len(restore),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
