#!/usr/bin/env python3
"""GRAPH-01: loss-aware common graph + Parquet representation smoke test."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import pyarrow as pa
import pyarrow.parquet as pq
import rustworkx as rx

P = Path(__file__).resolve().parent
ROOT = P.parent.parent
OUT = P / "output"


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def source_artifacts() -> list[Path]:
    return sorted(
        path for path in (ROOT / "poc").glob("*/output/results.json")
        if not path.parts[-3].startswith("graph-") and "legacy" not in path.parts
    )


def main() -> None:
    graph = nx.MultiDiGraph(contract="seman2-analysis-graph-v1")
    payload_rows = []
    source_inventory = []

    def add_node(node_id: str, node_type: str, attrs: dict, payload=None,
                 source_kind: str = "measured") -> None:
        payload_sha = digest(payload) if payload is not None else None
        graph.add_node(node_id, node_type=node_type, attrs=attrs,
                       payload_sha256=payload_sha, source_kind=source_kind)
        if payload is not None:
            payload_rows.append({"node_id": node_id, "media_type": "application/json",
                                 "source_path": attrs.get("source_path"),
                                 "payload_json": canonical(payload), "sha256": payload_sha})

    def add_edge(edge_id: str, source: str, target: str, edge_type: str,
                 order: int | None = None, attrs: dict | None = None) -> None:
        graph.add_edge(source, target, key=edge_id, edge_id=edge_id,
                       edge_type=edge_type, order=order, attrs=attrs or {})

    for path in source_artifacts():
        poc_id = path.parts[-3]
        value = json.loads(path.read_text())
        # Le payload complet est conservé. Sélectionner seulement le cas le plus
        # riche perdrait précisément les alternatives que GRAPH-01 doit porter.
        complete_payload = value
        version_path = path.with_name("versions-and-parameters.json")
        version = json.loads(version_path.read_text()) if version_path.exists() else {}
        artifact_id = f"artifact:{poc_id}"
        analysis_id = f"analysis-set:{poc_id}:complete"
        relative = str(path.relative_to(ROOT))
        add_node(artifact_id, "source_artifact", {
            "source_path": relative, "poc_id": poc_id, "whole_artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "producer_metadata": version,
        })
        add_node(analysis_id, "external_analysis", {
            "source_path": relative, "poc_id": poc_id,
            "payload_scope": "complete results.json root; no representative selection",
            "payload_encoding": "canonical JSON; recursive structures intentionally not flattened",
        }, complete_payload)
        add_edge(f"edge:{poc_id}:contains", artifact_id, analysis_id, "contains", 0)
        source_inventory.append({"poc_id": poc_id, "source_path": relative,
                                 "complete_payload_sha256": digest(complete_payload),
                                 "payload_root_type": type(complete_payload).__name__})

    # Contract fixtures exercise structures not produced until later phases. They
    # are visibly typed as fixtures and never presented as measured tool output.
    fixtures = {
        "fixture:overlapping-spans": {
            "spans": [{"id": "s1", "start": 0, "end": 6}, {"id": "s2", "start": 3, "end": 9}],
            "overlap_is_intentional": True,
        },
        "fixture:temporal-state": {
            "entity": "public-fact-1", "states": [
                {"valid_from": "t1", "valid_to": "t3", "status": "proposed"},
                {"valid_from": "t3", "valid_to": None, "status": "accepted"}],
        },
        "fixture:update-candidates": {
            "covers_planned_poc": "dlg-07",
            "candidates": [{"id": "u1", "rule": "accept", "status": "pending"},
                           {"id": "u2", "rule": "request_clarification", "status": "pending"}],
            "selected": None,
        },
        "fixture:communicative-plan": {
            "steps": [{"order": 0, "act": "acknowledge"}, {"order": 1, "act": "answer"}],
            "rejected_alternatives": ["answer_without_acknowledgement"],
        },
        "fixture:semiotic-relations": {
            "relations": [{"type": "realizes", "from": "form:io", "to": "meaning:greeting"},
                          {"type": "evokes", "from": "meaning:greeting", "to": "script:opening"}],
        },
        "fixture:dialogue-gameboard": {
            "covers_planned_poc": "dlg-06", "moves": [], "qud": [], "public_facts": [],
            "obligations": [], "pending": [], "unresolved_fields": ["addressee"]},
        "fixture:grounding": {
            "covers_planned_poc": "dlg-08", "acts": [{"type": "acknowledgement", "status": "candidate"}],
            "mutual_belief_asserted": False},
        "fixture:qud-fragment": {
            "covers_planned_poc": "dlg-09", "raw_fragment": "Rouge.",
            "qud_candidates": ["colour(x)", "confirm(red(x))"], "completion_selected": None},
        "fixture:repair-history": {
            "covers_planned_poc": "dlg-10", "states": ["original", "repair_requested", "corrected"],
            "original_deleted": False},
        "fixture:discursive-obligation": {
            "covers_planned_poc": "dlg-11", "debtor": "participant:b", "content": "answer(q1)",
            "status_history": ["created", "active"]},
        "fixture:reference-baseline": {
            "covers_planned_poc": "dlg-12", "mentions": ["Alice", "elle"],
            "candidate_links": [[1, 0]], "internal_identity_asserted": False},
        "fixture:dialogue-tool-boundary": {
            "covers_planned_poc": "dlg-13", "observation_loader": "ConvoKit", "policy_engine": None,
            "capability_claims": ["load_turns", "reply_links"]},
        "fixture:formal-multiturn-scenario": {
            "covers_planned_poc": "dlg-14", "turns": ["question", "fragment_answer", "repair"],
            "formal_layers": ["DGB", "ISU", "SDRT"], "layers_fused": False},
    }
    for node_id, payload in fixtures.items():
        add_node(node_id, "contract_fixture", {"future_poc": True, "source_path": None,
                 "covers_planned_poc": payload.get("covers_planned_poc")}, payload, "contract_fixture")

    add_node("fixture:mrs", "formal_analysis", {"formalism": "MRS", "source_path": None,
             "covers_planned_poc": "sem-05"}, {"rels": ["_red_a_1"]}, "contract_fixture")
    add_node("fixture:ttr", "formal_analysis", {"formalism": "TTR", "source_path": None,
             "covers_planned_poc": "sem-05"}, {"fields": ["x:Ind"]}, "contract_fixture")
    add_edge("edge:cross-repr:surface", "fixture:mrs", "fixture:ttr", "shares_surface_observation", 0,
             {"identity_claim": False})
    add_edge("edge:cross-repr:candidate", "fixture:mrs", "fixture:ttr", "candidate_correspondence", 1,
             {"identity_claim": False, "status": "unresolved"})

    node_rows = [{"id": node_id, "node_type": data["node_type"],
                  "attrs_json": canonical(data["attrs"]), "payload_sha256": data["payload_sha256"],
                  "source_kind": data["source_kind"]} for node_id, data in graph.nodes(data=True)]
    edge_rows = [{"id": key, "source": source, "target": target,
                  "edge_type": data["edge_type"], "order": data["order"],
                  "attrs_json": canonical(data["attrs"])}
                 for source, target, key, data in graph.edges(keys=True, data=True)]
    rust_graph = rx.PyDiGraph(multigraph=True)
    rust_nodes = {row["id"]: rust_graph.add_node(row) for row in node_rows}
    for row in edge_rows:
        rust_graph.add_edge(rust_nodes[row["source"]], rust_nodes[row["target"]], row)
    schemas = {
        "nodes": pa.schema([("id", pa.string()), ("node_type", pa.string()), ("attrs_json", pa.large_string()),
                            ("payload_sha256", pa.string()), ("source_kind", pa.string())]),
        "edges": pa.schema([("id", pa.string()), ("source", pa.string()), ("target", pa.string()),
                            ("edge_type", pa.string()), ("order", pa.int64()), ("attrs_json", pa.large_string())]),
        "payloads": pa.schema([("node_id", pa.string()), ("media_type", pa.string()), ("source_path", pa.string()),
                               ("payload_json", pa.large_string()), ("sha256", pa.string())]),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    expected = {"nodes": node_rows, "edges": edge_rows, "payloads": payload_rows}
    roundtrips = {}
    for name, rows in expected.items():
        table = pa.Table.from_pylist(rows, schema=schemas[name])
        target = OUT / f"{name}.parquet"
        pq.write_table(table, target, compression="zstd")
        decoded = pq.read_table(target).to_pylist()
        roundtrips[name] = decoded == rows
    payload_roundtrip = all(json.loads(row["payload_json"]) ==
                            json.loads((ROOT / row["source_path"]).read_text())
        for row in payload_rows if row["source_path"])
    parallel_edges = sum(graph.number_of_edges(u, v) > 1 for u, v in {(u, v) for u, v in graph.edges()})
    rust_parallel_edges = sum(
        len(rust_graph.edge_indices_from_endpoints(rust_nodes[u], rust_nodes[v])) > 1
        for u, v in {(u, v) for u, v in graph.edges()}
    )
    planned = ([f"nlp-{i:02d}" for i in range(1, 7)] + [f"lex-{i:02d}" for i in range(1, 8)] +
               [f"time-{i:02d}" for i in range(1, 9)] + [f"sem-{i:02d}" for i in range(1, 6)] +
               [f"disc-{i:02d}" for i in range(1, 3)] + [f"dlg-{i:02d}" for i in range(1, 15)] +
               [f"code-{i:02d}" for i in range(1, 3)])
    measured_ids = {row["poc_id"] for row in source_inventory}
    fixture_coverage = {payload.get("covers_planned_poc") for payload in fixtures.values()}
    fixture_coverage.add("sem-05")
    coverage = [{"poc_id": poc_id,
                 "status": "measured_output" if poc_id in measured_ids else
                           "contract_fixture_only" if poc_id in fixture_coverage else "uncovered"}
                for poc_id in planned]
    assert not [row for row in coverage if row["status"] == "uncovered"]
    result = {
        "contract": "seman2-analysis-graph-v1",
        "graph": nx.node_link_data(graph, edges="edges"),
        "source_inventory": source_inventory,
        "planned_coverage": coverage,
        "parquet_schemas": {name: str(schema) for name, schema in schemas.items()},
        "validation": {"parquet_roundtrips": roundtrips, "payload_json_roundtrip": payload_roundtrip,
                       "unique_node_ids": len(graph) == len(set(graph.nodes)),
                       "unique_edge_ids": graph.number_of_edges() == len({k for *_, k in graph.edges(keys=True)}),
                       "parallel_source_target_pairs": parallel_edges,
                       "rustworkx_node_count_matches": rust_graph.num_nodes() == graph.number_of_nodes(),
                       "rustworkx_edge_count_matches": rust_graph.num_edges() == graph.number_of_edges(),
                       "rustworkx_parallel_pairs_match": rust_parallel_edges == parallel_edges},
        "direct_representation_limits": [
            "Recursive analyzer payloads are stored as canonical JSON blobs referenced by graph nodes, not flattened into scalar attributes.",
            "Original byte streams are represented by source path and SHA-256; arbitrary binary bytes are not graph-native.",
            "Parquet tables preserve multi-edge identity through explicit edge IDs; NetworkX carries the in-memory multigraph semantics.",
        ],
    }
    assert all(roundtrips.values()) and payload_roundtrip and parallel_edges
    assert rust_graph.num_nodes() == graph.number_of_nodes()
    assert rust_graph.num_edges() == graph.number_of_edges() and rust_parallel_edges == parallel_edges
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {
        "measured_source_artifact_count": len(source_inventory), "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(), "contract_fixture_count": len(fixtures) + 2,
        "planned_poc_count": len(coverage),
        "measured_planned_poc_count": sum(x["status"] == "measured_output" for x in coverage),
        "fixture_only_planned_poc_count": sum(x["status"] == "contract_fixture_only" for x in coverage),
        "uncovered_planned_poc_count": sum(x["status"] == "uncovered" for x in coverage),
        "final_measured_coverage_rerun_required": any(x["status"] != "measured_output" for x in coverage),
        "parallel_source_target_pair_count": parallel_edges, "unrepresentable_without_indirection_count": 2,
        "parquet_roundtrip_passed": all(roundtrips.values()), "payload_roundtrip_passed": payload_roundtrip,
        "complete_result_roots_preserved": True,
        "networkx_rustworkx_agreement": True,
        "verdict": "GO_COMPLETE_MEASURED_OUTPUT_ROOTS_LOSS_AWARE_GRAPH_PARQUET",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "networkx": importlib.metadata.version("networkx"),
        "rustworkx": importlib.metadata.version("rustworkx"),
        "pyarrow": importlib.metadata.version("pyarrow"), "compression": "zstd",
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"GRAPH-01: {len(source_inventory)} measured artifacts, {graph.number_of_nodes()} nodes, "
          f"{graph.number_of_edges()} edges; loss-aware graph/Parquet GO")


if __name__ == "__main__":
    main()
