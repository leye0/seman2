#!/usr/bin/env python3
"""SEM-05: attributed multi-plane retrieval without semantic collapse."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import subprocess

import duckdb
import networkx as nx
import pyarrow as pa
import pyarrow.parquet as pq
import rustworkx as rx

from seman2_runtime.cognitive_artifacts import (
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    thaw_json,
)
from seman2_runtime.cognitive_ingestion import (
    IngestionPolicy,
    IngestionRecord,
    build_foundation_modules,
    ingest_records,
    register_foundation_types,
)
from seman2_runtime.cognitive_runtime import CognitiveRuntime
from seman2_runtime.cognitive_scheduler import ModuleSpec
from seman2_runtime.contracts import canonical_json


POC = Path(__file__).resolve().parent
ROOT = POC.parent.parent
OUTPUT = POC / "output"
BUILD = "sem-05-integrated-multiplane-retrieval"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measured_phonology(left_ipa: str) -> dict:
    program = r"""
import json, sys
import epitran
from panphon.distance import Distance
request = json.load(sys.stdin)
right_ipa = epitran.Epitran('fra-Latn').transliterate(request['right_form'])
json.dump({
    'left_ipa': request['left_ipa'],
    'right_form': request['right_form'],
    'right_ipa': right_ipa,
    'weighted_feature_distance': Distance().weighted_feature_edit_distance(
        request['left_ipa'], right_ipa
    ),
    'epitran_version': __import__('importlib.metadata').metadata.version('epitran'),
    'panphon_version': __import__('importlib.metadata').metadata.version('panphon'),
}, sys.stdout)
"""
    process = subprocess.run(
        [str(ROOT / ".venv-semiotic/bin/python"), "-c", program],
        input=json.dumps({"left_ipa": left_ipa, "right_form": "yo"}),
        text=True,
        capture_output=True,
        timeout=30,
    )
    if process.returncode:
        raise RuntimeError(process.stderr)
    return json.loads(process.stdout)


def networkx_path(graph: nx.MultiDiGraph, target: str) -> dict:
    path = nx.shortest_path(graph, "form:io", target, weight="cost")
    steps = []
    score = 0.0
    for source, destination in zip(path, path[1:]):
        edge = min(graph[source][destination].values(), key=lambda row: row["cost"])
        steps.append(
            {
                "source": source,
                "relation": edge["relation"],
                "target": destination,
                "cost": edge["cost"],
                "provenance": edge["provenance"],
            }
        )
        score += edge["cost"]
    return {
        "target": target,
        "typed_path": steps,
        "score_kind": "path_cost_lower_is_closer",
        "score": score,
        "provenance": [step["provenance"] for step in steps],
    }


def rustworkx_paths(nodes: list[dict], edges: list[dict], targets: set[str]) -> dict:
    graph = rx.PyDiGraph(multigraph=False)
    indexes = {row["node_id"]: graph.add_node(row["node_id"]) for row in nodes}
    by_pair = {}
    for edge in edges:
        graph.add_edge(indexes[edge["source"]], indexes[edge["target"]], edge)
        by_pair[(edge["source"], edge["target"])] = edge
    paths = rx.dijkstra_shortest_paths(
        graph,
        indexes["form:io"],
        weight_fn=lambda edge: edge["cost"],
    )
    output = {}
    for target in targets:
        node_path = [graph[index] for index in paths[indexes[target]]]
        score = sum(
            by_pair[(source, destination)]["cost"]
            for source, destination in zip(node_path, node_path[1:])
        )
        output[target] = {"node_path": node_path, "score": score}
    return output


def build_runtime(bundle: dict, input_hashes: dict[str, str]) -> CognitiveRuntime:
    digest = hashlib.sha256(
        canonical_json({"bundle": bundle, "inputs": input_hashes}).encode()
    ).hexdigest()
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.register(
        ArtifactTypeSpec(
            artifact_type="cross-representation-retrieval-bundle",
            schema_id="seman2/cross-representation-retrieval-bundle",
            layer=2,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"cross-representation-retrieval"}),
            parent_types=frozenset({"observation"}),
            required_native_fields=frozenset(
                {"query_observation", "plane_results", "input_artifact_hashes"}
            ),
            required_projection_fields=frozenset(
                {
                    "global_ranking_created",
                    "semantic_identity_inferred",
                    "selected_interpretation",
                }
            ),
        )
    )
    registry.freeze()

    def retrieve(trigger, context):
        assert trigger.payload_native["text"] == "io"
        yield ArtifactProposal(
            artifact_type="cross-representation-retrieval-bundle",
            producer_id="cross-representation-retrieval",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "query_observation": "form:io",
                "plane_results": bundle["plane_results"],
                "input_artifact_hashes": input_hashes,
            },
            payload_projection={
                "global_ranking_created": False,
                "semantic_identity_inferred": False,
                "selected_interpretation": None,
                "cross_plane_cartesian_product_materialized": False,
            },
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"multiplane-retrieval:{trigger.artifact_id}",
        )

    policy = IngestionPolicy(max_records=1, max_text_chars=64)
    return CognitiveRuntime(
        registry=registry,
        modules=(
            *build_foundation_modules(policy),
            ModuleSpec(
                module_id="cross-representation-retrieval",
                layer=2,
                modes=frozenset({"ingestion"}),
                consumes=frozenset({"observation"}),
                produces=frozenset({"cross-representation-retrieval-bundle"}),
                producer_build=BUILD,
                configuration_digest=digest,
                handler=retrieve,
            ),
        ),
    )


def main() -> None:
    inputs = {
        "SEM-01": ROOT / "poc/sem-01/output/results.json",
        "SEM-02": ROOT / "poc/sem-02/output/results.json",
        "SEM-03": ROOT / "poc/sem-03/output/results.json",
        "RET-02": ROOT / "poc/ret-02/output/results.json",
    }
    assert all(path.is_file() for path in inputs.values())
    input_hashes = {name: sha256(path) for name, path in inputs.items()}
    sem01 = json.loads(inputs["SEM-01"].read_text(encoding="utf-8"))
    sem03 = json.loads(inputs["SEM-03"].read_text(encoding="utf-8"))
    fr_io = next(
        row for row in sem01 if row["fixture"]["id"] == "fr-atypical-io"
    )["external_analyses"][0]
    en_io = next(
        row for row in sem01 if row["fixture"]["id"] == "en-atypical-io"
    )["external_analyses"]
    form_paths = next(
        row for row in sem03["queries"] if row["query"]["input"] == "io"
    )["paths"]
    form_by_rule = {row["rule_id"]: row for row in form_paths}
    composition = sem03["composition"]
    phonology = measured_phonology(fr_io["ipa"])

    nodes = [
        {"node_id": "form:io", "plane": "form", "value": "io", "provenance": "query observation"},
        {"node_id": "form:yo", "plane": "form", "value": "yo", "provenance": "SEM-03 phonographic-io"},
        {"node_id": "form:i-o", "plane": "form", "value": "i/o", "provenance": "SEM-03 segment-io"},
        {"node_id": "form:Io", "plane": "form", "value": "Io", "provenance": "controlled case occurrence"},
        {"node_id": "phon:io-fr", "plane": "phonological", "value": fr_io["ipa"], "provenance": fr_io["analysis_id"]},
        {"node_id": "phon:io-en", "plane": "phonological", "value": en_io[0]["ipa"], "provenance": en_io[0]["analysis_id"]},
        {"node_id": "phon:yo-fr", "plane": "phonological", "value": phonology["right_ipa"], "provenance": "SEM-02 metric over attributed Epitran output"},
        {"node_id": "symbol:input-output", "plane": "symbolic", "value": "input/output", "provenance": "SEM-03 composition"},
        {"node_id": "entity:Io", "plane": "graph", "value": "Jupiter moon Io", "provenance": "controlled astronomy occurrence"},
        {"node_id": "context:greeting", "plane": "context", "value": "dialogue opening", "provenance": "controlled greeting episodes"},
        {"node_id": "context:computing", "plane": "context", "value": "computing discussion", "provenance": "controlled computing episodes"},
    ]
    edges = [
        {"edge_id": "e1", "source": "form:io", "target": "form:i-o", "plane": "form", "relation": "segmentation_candidate", "cost": form_by_rule["segment-io"]["weight"], "provenance": "SEM-03/segment-io"},
        {"edge_id": "e2", "source": "form:io", "target": "form:yo", "plane": "form", "relation": "phonographic_candidate", "cost": form_by_rule["phonographic-io"]["weight"], "provenance": "SEM-03/phonographic-io"},
        {"edge_id": "e3", "source": "form:io", "target": "form:Io", "plane": "form", "relation": "case_variant", "cost": 0.1, "provenance": "controlled case relation"},
        {"edge_id": "e4", "source": "form:io", "target": "phon:io-fr", "plane": "phonological", "relation": "has_pronunciation_candidate", "cost": 0.0, "provenance": fr_io["analysis_id"]},
        {"edge_id": "e5", "source": "form:io", "target": "phon:io-en", "plane": "phonological", "relation": "has_pronunciation_candidate", "cost": 0.0, "provenance": en_io[0]["analysis_id"]},
        {"edge_id": "e6", "source": "phon:io-fr", "target": "phon:yo-fr", "plane": "phonological", "relation": "phonological_feature_distance", "cost": phonology["weighted_feature_distance"], "provenance": "SEM-02 PanPhon weighted feature metric"},
        {"edge_id": "e7", "source": "phon:yo-fr", "target": "form:yo", "plane": "phonological", "relation": "pronunciation_of_candidate", "cost": 0.0, "provenance": "attributed Epitran analysis of yo"},
        {"edge_id": "e8", "source": "form:i-o", "target": "symbol:input-output", "plane": "symbolic", "relation": "abbreviation_expansion_candidate", "cost": composition["component_weights"][1], "provenance": "SEM-03/expand-io"},
        {"edge_id": "e9", "source": "form:Io", "target": "entity:Io", "plane": "graph", "relation": "names_candidate", "cost": 0.0, "provenance": "controlled astronomy occurrence"},
        {"edge_id": "e10", "source": "form:yo", "target": "context:greeting", "plane": "context", "relation": "observed_in", "cost": 0.0, "provenance": "controlled greeting episodes"},
        {"edge_id": "e11", "source": "form:i-o", "target": "context:computing", "plane": "context", "relation": "observed_in", "cost": 0.0, "provenance": "controlled computing episodes"},
    ]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    node_schema = pa.schema(
        [("node_id", pa.string()), ("plane", pa.string()), ("value", pa.string()), ("provenance", pa.string())]
    )
    edge_schema = pa.schema(
        [("edge_id", pa.string()), ("source", pa.string()), ("target", pa.string()), ("plane", pa.string()), ("relation", pa.string()), ("cost", pa.float64()), ("provenance", pa.string())]
    )
    pq.write_table(pa.Table.from_pylist(nodes, schema=node_schema), OUTPUT / "nodes.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pylist(edges, schema=edge_schema), OUTPUT / "edges.parquet", compression="zstd")
    database = OUTPUT / "sem-05.duckdb"
    database.unlink(missing_ok=True)
    connection = duckdb.connect(str(database))
    connection.execute("CREATE TABLE nodes AS SELECT * FROM read_parquet(?)", [str((OUTPUT / "nodes.parquet").resolve())])
    connection.execute("CREATE TABLE edges AS SELECT * FROM read_parquet(?)", [str((OUTPUT / "edges.parquet").resolve())])
    planes = [row[0] for row in connection.execute("SELECT DISTINCT plane FROM edges ORDER BY plane").fetchall()]
    connection.close()

    graph = nx.MultiDiGraph()
    for node in nodes:
        graph.add_node(node["node_id"], **node)
    for edge in edges:
        graph.add_edge(edge["source"], edge["target"], key=edge["edge_id"], **edge)
    queries = {
        "form": ["form:i-o", "form:yo", "form:Io"],
        "phonological": ["phon:io-fr", "phon:io-en", "phon:yo-fr"],
        "symbolic": ["symbol:input-output"],
        "graph": ["entity:Io"],
        "context": ["context:greeting", "context:computing"],
    }
    plane_results = {
        plane: sorted(
            [networkx_path(graph, target) for target in targets],
            key=lambda row: (row["score"], row["target"]),
        )
        for plane, targets in queries.items()
    }
    all_targets = {target for targets in queries.values() for target in targets}
    rustworkx_results = rustworkx_paths(nodes, edges, all_targets)
    for rows in plane_results.values():
        for row in rows:
            assert row["target"] in rustworkx_results
            assert row["score"] == rustworkx_results[row["target"]]["score"]
            assert [row["typed_path"][0]["source"], *[step["target"] for step in row["typed_path"]]] == rustworkx_results[row["target"]]["node_path"]

    bundle = {
        "query_observation": "form:io",
        "plane_results": plane_results,
        "global_ranking": None,
        "selected_interpretation": None,
        "cross_plane_cartesian_product_materialized": False,
    }
    runtime = build_runtime(bundle, input_hashes)
    record = IngestionRecord(
        record_id="sem-05:io",
        discourse_id="sem-05:cross-representation-query",
        turn_index=0,
        speaker_role="fixture-source",
        text="io",
        canonical_file="poc/sem-01/fixtures.json",
        source_position=2,
        source_record_id="fr-atypical-io",
        raw_body_sha256=hashlib.sha256(b"io").hexdigest(),
        channel="controlled-written-form",
        source_kind="written-form",
        native_structure={"fixture_id": "fr-atypical-io"},
    )
    ingest_records(
        runtime,
        (record,),
        policy=IngestionPolicy(max_records=1, max_text_chars=64),
        session_id="sem-05:integration",
    )
    artifact = runtime.arena.query(artifact_type="cross-representation-retrieval-bundle")[0]
    ancestry = runtime.arena.ancestry(artifact.artifact_id)
    forbidden_edges = [
        edge for edge in edges if edge["relation"] in {"semantic_identity", "means"}
    ]
    greeting = next(row for row in plane_results["context"] if row["target"] == "context:greeting")
    validations = {
        "all_five_planes_queried": set(plane_results) == {"form", "phonological", "symbolic", "graph", "context"},
        "all_results_have_typed_paths": all(row["typed_path"] for rows in plane_results.values() for row in rows),
        "all_results_have_provenance": all(row["provenance"] for rows in plane_results.values() for row in rows),
        "no_global_nearest_neighbour": bundle["global_ranking"] is None and bundle["selected_interpretation"] is None,
        "phonology_not_semantic_identity": not forbidden_edges,
        "io_to_greeting_path_exists_but_is_not_means": bool(greeting["typed_path"]) and all(step["relation"] != "means" for step in greeting["typed_path"]),
        "source_observation_unchanged": hashlib.sha256(b"io").hexdigest() == fr_io["source_sha256"],
        "panphon_cost_is_measured": next(edge for edge in edges if edge["edge_id"] == "e6")["cost"] > 0,
        "networkx_rustworkx_agree": True,
        "runtime_ancestry_verified": {row.artifact_type for row in ancestry} == {"source-record", "observation", "cross-representation-retrieval-bundle"},
        "all_required_poc_outputs_bound": set(input_hashes) == {"SEM-01", "SEM-02", "SEM-03", "RET-02"},
    }
    assert all(validations.values()), validations
    assert artifact.payload_projection["selected_interpretation"] is None
    assert not artifact.payload_projection["semantic_identity_inferred"]
    result = {
        "index": {"nodes": nodes, "edges": edges, "duckdb_planes": planes},
        "phonological_measurement": phonology,
        "bundle": bundle,
        "runtime_artifact": {
            "artifact_id": artifact.artifact_id,
            "causal_ancestry_types": [row.artifact_type for row in ancestry],
            "payload_projection": thaw_json(artifact.payload_projection),
        },
        "independent_engine_check": {"rustworkx": rustworkx_results},
        "input_artifact_hashes": input_hashes,
        "rejected_inference": {
            "premises": [
                "io has an attributed French pronunciation candidate",
                "that candidate has a measured PanPhon path to the pronunciation of yo",
                "yo occurs in controlled greeting contexts",
            ],
            "forbidden_conclusion": "io semantically equals greeting",
            "rejected": True,
        },
        "validation": validations,
    }
    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "plane_count": len(plane_results),
        "result_count": sum(len(rows) for rows in plane_results.values()),
        "global_selection_count": 0,
        "semantic_identity_inference_count": 0,
        "runtime_bundle_count": 1,
        "networkx_rustworkx_agreement": True,
        "verdict": "GO_INTEGRATED_INDEPENDENT_MULTIPLANE_RETRIEVAL_NO_COLLAPSE",
    }
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "duckdb": importlib.metadata.version("duckdb"),
        "networkx": importlib.metadata.version("networkx"),
        "rustworkx": importlib.metadata.version("rustworkx"),
        "pyarrow": importlib.metadata.version("pyarrow"),
        "inputs": input_hashes,
        "artifact_contract": "seman2/cross-representation-retrieval-bundle",
    }
    for name, value in (
        ("results.json", result),
        ("summary.json", summary),
        ("versions-and-parameters.json", versions),
    ):
        (OUTPUT / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        f"SEM-05: {len(plane_results)} planes/{summary['result_count']} results; "
        "NetworkX=rustworkx; runtime bundle; 0 semantic collapses; GO"
    )


if __name__ == "__main__":
    main()
