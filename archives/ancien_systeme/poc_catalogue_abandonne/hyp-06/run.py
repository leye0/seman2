#!/usr/bin/env python3
"""HYP-06: progressive structural sharing and deduplicated postings."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import networkx as nx
import pyarrow as pa
import pyarrow.parquet as pq
import zstandard as zstd

P = Path(__file__).resolve().parent
OUT = P / "output"
ROOT = P.parents[1]

TEMPLATES = {
    "active": {"nodes": [("actor", "person"), ("event", "event"), ("target", "object"), ("context", "context")], "edges": [("actor", "event", "agent"), ("event", "target", "theme"), ("event", "context", "in_context")]},
    "passive": {"nodes": [("target", "object"), ("event", "event"), ("actor", "person"), ("context", "context")], "edges": [("target", "event", "surface_subject"), ("event", "actor", "agent_by"), ("event", "context", "in_context")]},
    "instrumented": {"nodes": [("actor", "person"), ("event", "event"), ("target", "object"), ("tool", "instrument"), ("context", "context")], "edges": [("actor", "event", "agent"), ("event", "target", "theme"), ("event", "tool", "instrument"), ("event", "context", "in_context")]},
}


def canonical_payload(template: dict) -> dict:
    graph = nx.DiGraph()
    for node, kind in template["nodes"]:
        graph.add_node(node, kind=kind)
    for source, target, relation in template["edges"]:
        graph.add_edge(source, target, relation=relation)
    return nx.node_link_data(graph, edges="edges")


def signature(template: dict) -> str:
    nodes = sorted(kind for _, kind in template["nodes"])
    edges = sorted((dict(template["nodes"])[a], rel, dict(template["nodes"])[b]) for a, b, rel in template["edges"])
    return hashlib.sha256(json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True).encode()).hexdigest()


def occurrence(i: int) -> tuple[str, dict, dict]:
    family = "active" if i < 700 else "passive" if i < 950 else "instrumented"
    context = ("work", "home", "public", "laboratory" if i >= 900 else "work")[i % 4]
    contradiction = i % 19 == 0
    bindings = {role: f"{role}-{i:04d}" for role, _ in TEMPLATES[family]["nodes"]}
    metadata = {"occurrence_id": f"occ-{i:04d}", "context": context, "supports": not contradiction, "confidence": round(0.7 + (i % 29) / 100, 2), "bindings": bindings}
    expanded = canonical_payload(TEMPLATES[family])
    for node in expanded["nodes"]:
        node["id"] = bindings[node["id"]]
    expanded["occurrence_id"] = metadata["occurrence_id"]
    expanded["context"] = context
    expanded["supports"] = not contradiction
    return family, metadata, expanded


def load_json_with_hash(path: Path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def integrated_hypothesis_sharing() -> tuple[dict, dict[str, bool]]:
    """Store the real HYP-02 DAG once and reference it from each hypothesis."""
    hyp02_path = ROOT / "poc/hyp-02/output/results.json"
    hyp04_path = ROOT / "poc/hyp-04/output/results.json"
    hyp02, hyp02_sha256 = load_json_with_hash(hyp02_path)
    hyp04, hyp04_sha256 = load_json_with_hash(hyp04_path)
    graph_data = hyp02["justification_graph"]
    node_by_id = {node["id"]: node for node in graph_data["nodes"]}

    nodes = [{
        "node_id": node_id,
        "kind": node["kind"],
        "value": node["value"],
        "source_cognitive_artifact_id": node.get("source_cognitive_artifact_id"),
        "node_json": json.dumps(node, sort_keys=True, separators=(",", ":")),
    } for node_id, node in sorted(node_by_id.items())]
    edges = [{"source": edge["source"], "target": edge["target"], "relation": edge["relation"]}
             for edge in graph_data["edges"]]
    postings = []
    expected_closures: dict[str, list[str]] = {}
    for hypothesis_id, explanation in sorted(hyp02["explanations"].items()):
        closure = sorted([hypothesis_id, *explanation["transitive_dependencies"]])
        expected_closures[hypothesis_id] = closure
        for node_id in closure:
            postings.append({"hypothesis_id": hypothesis_id, "node_id": node_id})

    pq.write_table(pa.Table.from_pylist(nodes), OUT / "integrated-nodes.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pylist(edges), OUT / "integrated-edges.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pylist(postings), OUT / "integrated-hypothesis-postings.parquet", compression="zstd")
    con = duckdb.connect()
    posting_path = str((OUT / "integrated-hypothesis-postings.parquet").resolve()).replace("'", "''")
    restored = con.execute(f"""
        SELECT hypothesis_id, list(node_id ORDER BY node_id) AS node_ids
        FROM read_parquet('{posting_path}') GROUP BY hypothesis_id ORDER BY hypothesis_id
    """).fetchall()
    con.close()
    restored_closures = {hypothesis_id: node_ids for hypothesis_id, node_ids in restored}

    # The Evidence Ledger must reference the same shared leaf supports and the
    # same immutable cognitive hypothesis artifacts, not copies with new IDs.
    artifact_ids = hyp04["upstream"]["hypothesis_artifact_ids"]
    ledger_refs_resolve = []
    for entry in hyp04["ledger"]:
        hypothesis_id = entry["hypothesis_id"]
        support_ids = json.loads(entry["justification_support_ids_json"])
        ledger_refs_resolve.append(
            entry["hypothesis_artifact_id"] == artifact_ids[hypothesis_id]
            and set(support_ids) <= set(hyp02["explanations"][hypothesis_id]["minimal_leaf_dependencies"])
            and all(support_id in node_by_id for support_id in support_ids)
        )

    shared_node_count = len(nodes)
    naive_node_instances = len(postings)
    shared_files = [
        OUT / "integrated-nodes.parquet",
        OUT / "integrated-edges.parquet",
        OUT / "integrated-hypothesis-postings.parquet",
    ]
    details = {
        "sources": {
            "hyp02_results_sha256": hyp02_sha256,
            "hyp04_results_sha256": hyp04_sha256,
        },
        "hypothesis_artifact_ids": artifact_ids,
        "shared_node_count": shared_node_count,
        "shared_edge_count": len(edges),
        "hypothesis_posting_count": naive_node_instances,
        "naive_copied_node_count": hyp02["sharing_measurement"]["naive_copied_node_count"],
        "node_instances_avoided": naive_node_instances - shared_node_count,
        "shared_nodes": sorted(node_by_id),
        "reconstructed_closures": restored_closures,
        "ledger_entry_count": len(hyp04["ledger"]),
        "storage_bytes": sum(path.stat().st_size for path in shared_files),
        "files": [path.name for path in shared_files],
    }
    validations = {
        "actual_hyp02_hash_matches_hyp04": hyp04["upstream"]["result_sha256"] == hyp02_sha256,
        "actual_closures_reconstruct_exactly": restored_closures == expected_closures,
        "actual_shared_node_count_matches_upstream": shared_node_count == hyp02["sharing_measurement"]["shared_node_count"],
        "actual_naive_count_matches_postings": naive_node_instances == hyp02["sharing_measurement"]["naive_copied_node_count"],
        "actual_node_instances_avoided": naive_node_instances > shared_node_count,
        "actual_all_ledger_references_resolve": len(ledger_refs_resolve) == 13 and all(ledger_refs_resolve),
        "actual_hypothesis_artifact_ids_preserved": all(
            node_by_id[hypothesis_id]["source_cognitive_artifact_id"] == artifact_id
            for hypothesis_id, artifact_id in artifact_ids.items()
        ),
    }
    return details, validations


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    compressor = zstd.ZstdCompressor(level=9)
    prototypes, occurrences, postings, growth, naive_lines = [], [], [], [], []
    seen = set()
    for family, template in TEMPLATES.items():
        sig = signature(template)
        prototypes.append({"prototype_id": f"proto-{family}", "family": family, "signature": sig, "graph_json": json.dumps(canonical_payload(template), sort_keys=True, separators=(",", ":"))})
    proto_by_family = {r["family"]: r for r in prototypes}
    for i in range(1000):
        family, metadata, expanded = occurrence(i)
        proto = proto_by_family[family]
        seen.add(proto["prototype_id"])
        packed = compressor.compress(json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode())
        occurrences.append({"occurrence_id": metadata["occurrence_id"], "prototype_id": proto["prototype_id"], "context": metadata["context"], "supports": metadata["supports"], "detail_zstd": packed})
        postings.append({"prototype_id": proto["prototype_id"], "ordinal": i, "occurrence_id": metadata["occurrence_id"]})
        naive_lines.append(json.dumps(expanded, sort_keys=True, separators=(",", ":")) + "\n")
        if (i + 1) % 100 == 0:
            growth.append({"occurrences_ingested": i + 1, "prototype_count": len(seen), "posting_count": i + 1, "positive_supports": sum(r["supports"] for r in occurrences), "contradictions": sum(not r["supports"] for r in occurrences)})

    pq.write_table(pa.Table.from_pylist(prototypes), OUT / "prototypes.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pylist(occurrences), OUT / "occurrences.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pylist(postings), OUT / "postings.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pylist(growth), OUT / "growth.parquet", compression="zstd")
    (OUT / "naive-expanded.jsonl").write_text("".join(naive_lines))
    db = OUT / "hyp-06.duckdb"
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    for name in ("prototypes", "occurrences", "postings", "growth"):
        path = str((OUT / f"{name}.parquet").resolve()).replace("'", "''")
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
    aggregates = [dict(zip([d[0] for d in con.description], row)) for row in con.execute("""
        SELECT prototype_id, count(*) AS references, sum(supports::INT) AS positive_supports,
               sum((NOT supports)::INT) AS contradictions, count(DISTINCT context) AS contexts
        FROM occurrences GROUP BY prototype_id ORDER BY prototype_id
    """).fetchall()]
    requested_ids = ["occ-0000", "occ-0711", "occ-0977"]
    selected = con.execute("SELECT occurrence_id, prototype_id, detail_zstd FROM occurrences WHERE occurrence_id IN (SELECT unnest(?)) ORDER BY occurrence_id", [requested_ids]).fetchall()
    decompressor = zstd.ZstdDecompressor()
    proto_json = {r[0]: json.loads(r[1]) for r in con.execute("SELECT prototype_id, graph_json FROM prototypes").fetchall()}
    reconstructions = []
    for occurrence_id, prototype_id, packed in selected:
        detail = json.loads(decompressor.decompress(bytes(packed)))
        graph = json.loads(json.dumps(proto_json[prototype_id]))
        for node in graph["nodes"]:
            node["id"] = detail["bindings"][node["id"]]
        graph.update({"occurrence_id": occurrence_id, "context": detail["context"], "supports": detail["supports"]})
        _, expected_detail, expected_graph = occurrence(int(occurrence_id.split("-")[1]))
        reconstructions.append({"occurrence_id": occurrence_id, "prototype_id": prototype_id, "detail": detail, "semantic_equal_to_original": graph == expected_graph, "bindings_preserved": detail == expected_detail})
    con.close()

    shared_files = [OUT / "prototypes.parquet", OUT / "occurrences.parquet", OUT / "postings.parquet"]
    shared_bytes = sum(path.stat().st_size for path in shared_files)
    naive_bytes = (OUT / "naive-expanded.jsonl").stat().st_size
    family_signatures = {p["family"]: p["signature"] for p in prototypes}
    integrated_sharing, integrated_validations = integrated_hypothesis_sharing()
    validations = {
        "all_occurrences_referenced_once": len(occurrences) == len(postings) == 1000 and len({p["occurrence_id"] for p in postings}) == 1000,
        "prototype_growth_bounded": growth[-1]["prototype_count"] == 3,
        "controlled_family_counts": {a["prototype_id"]: a["references"] for a in aggregates} == {"proto-active": 700, "proto-instrumented": 50, "proto-passive": 250},
        "contradictions_retained": sum(a["contradictions"] for a in aggregates) == 53,
        "incompatible_variants_not_merged": len(set(family_signatures.values())) == 3,
        "detailed_episode_random_access": len(reconstructions) == len(requested_ids) and all(r["semantic_equal_to_original"] and r["bindings_preserved"] for r in reconstructions),
        "shared_storage_smaller_than_naive": shared_bytes < naive_bytes,
        **integrated_validations,
    }
    assert all(validations.values()), validations
    result = {"growth": growth, "aggregates": aggregates, "random_access_reconstructions": reconstructions, "storage": {"shared_bytes": shared_bytes, "naive_expanded_bytes": naive_bytes, "shared_to_naive_ratio": shared_bytes / naive_bytes, "shared_files": [p.name for p in shared_files]}, "prototype_signatures": family_signatures, "integrated_hypothesis_sharing": integrated_sharing, "validations": validations}
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {"occurrences": 1000, "prototypes": len(prototypes), "postings": len(postings), "contradictions": 53, "shared_bytes": shared_bytes, "naive_bytes": naive_bytes, "shared_to_naive_ratio": shared_bytes / naive_bytes, "integrated_shared_nodes": integrated_sharing["shared_node_count"], "integrated_naive_node_instances": integrated_sharing["naive_copied_node_count"], "integrated_node_instances_avoided": integrated_sharing["node_instances_avoided"], "integrated_ledger_entries": integrated_sharing["ledger_entry_count"], "verdict": "GO_STRUCTURAL_SHARING"}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "duckdb": importlib.metadata.version("duckdb"), "pyarrow": importlib.metadata.version("pyarrow"), "networkx": importlib.metadata.version("networkx"), "zstandard": importlib.metadata.version("zstandard"), "occurrences": 1000, "zstd_level": 9}, indent=2) + "\n")
    print(f"HYP-06: 1000 occurrences -> 3 prototypes; ratio={shared_bytes / naive_bytes:.3f}; GO")


if __name__ == "__main__":
    main()
