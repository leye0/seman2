#!/usr/bin/env python3
"""GRAPH-03: factorized ambiguity graph retaining incompatible candidates."""
from __future__ import annotations

import hashlib
import importlib.metadata
import itertools
import json
import math
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


def load(poc_id: str):
    return json.loads((ROOT / "poc" / poc_id / "output/results.json").read_text())


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def main() -> None:
    graph = nx.MultiDiGraph(contract="seman2-factorized-ambiguity-v1")
    payloads = []
    groups = []

    def support(poc_id: str, selector: str, payload_hashes: list[str]) -> str:
        node_id = f"support:{poc_id}:{hashlib.sha256(selector.encode()).hexdigest()[:12]}"
        if node_id not in graph:
            graph.add_node(node_id, node_type="external_annotation_support", poc_id=poc_id,
                           source_artifact=None if poc_id == "contract-fixture" else f"poc/{poc_id}/output/results.json",
                           source_selector=selector, supported_payload_sha256=payload_hashes,
                           graph02_contract="seman2.graph.v1.ExternalAnnotation",
                           graph02_record_id=None,
                           provenance_note="exact source slice; no claim that GRAPH-02 representative record is this slice")
        return node_id

    def add_group(group_id: str, producer: str, formalism: str, source_poc: str,
                  candidates: list[dict], relation: str = "exclusive_alternatives",
                  constraints: list | None = None, source_selector: str | None = None) -> None:
        graph.add_node(group_id, node_type="candidate_group", producer=producer, formalism=formalism,
                       relation=relation, constraints=constraints or [], selection=None)
        selector = source_selector or group_id
        sid = support(source_poc, selector, [digest(item["payload"]) for item in candidates])
        ids = []
        for rank, item in enumerate(candidates):
            payload = item["payload"]
            candidate_id = f"{group_id}:candidate:{rank + 1}:{digest(payload)[:12]}"
            ids.append(candidate_id)
            graph.add_node(candidate_id, node_type="candidate", rank=rank + 1,
                           score=item.get("score"), score_kind=item.get("score_kind"),
                           selected=False, producer=producer, formalism=formalism,
                           payload_sha256=digest(payload), constraints=item.get("constraints", []))
            graph.add_edge(candidate_id, group_id, key=f"{candidate_id}:member", edge_type="member_of")
            graph.add_edge(candidate_id, sid, key=f"{candidate_id}:support", edge_type="supported_by")
            payloads.append({"candidate_id": candidate_id, "source_poc": source_poc,
                             "payload_json": canonical(payload), "sha256": digest(payload)})
        if relation == "exclusive_alternatives":
            for left, right in itertools.combinations(ids, 2):
                graph.add_edge(left, right, key=f"conflict:{left}:{right}", edge_type="conflicts_with",
                               reason="same producer candidate set")
        groups.append({"id": group_id, "producer": producer, "formalism": formalism,
                       "source_poc": source_poc, "source_selector": selector,
                       "support_id": sid, "candidate_count": len(ids), "relation": relation})

    nlp03 = load("nlp-03")[0]
    add_group("group:erg-attachment", "ACE/ERG/PyDelphin", "HPSG/MRS", "nlp-03", [
        {"payload": value, "score": value.get("score"), "score_kind": "ACE native score"}
        for value in nlp03["analyses"]], constraints=["all candidates analyze the same source observation"],
              source_selector="$[0].analyses[*]")

    nlp05 = load("nlp-05")[1]
    add_group("group:link-grammar-attachment", "Link Grammar", "linkage", "nlp-05", [
        {"payload": value, "score": value.get("costs", {}).get("disjunct_cost"),
         "score_kind": "native disjunct cost (cost, not probability)"}
        for value in nlp05["strict_parse"]["linkages"]], source_selector="$[1].strict_parse.linkages[*]")

    time02 = load("time-02")[1]
    allen_query = time02["queries"][0]
    add_group("group:allen-disjunction", "seman2 Allen reasoner", "Allen interval algebra", "time-02", [
        {"payload": {"left": allen_query["left"], "relation": relation, "right": allen_query["right"],
                     "asserted_constraints": time02["asserted_constraints"]},
         "constraints": time02["asserted_constraints"]} for relation in allen_query["relations"]],
              source_selector="$[1].queries[0].relations[*]")

    time05 = load("time-05")[1]
    add_group("group:temporal-discourse-antecedent", "seman2 temporal discourse adapter",
              "Temporal DRT/SDRT", "time-05", [{"payload": value} for value in time05["candidates"]],
              source_selector="$[1].candidates[*]")

    time08 = load("time-08")["integration"]["external_analyses"]
    duck = next(value for value in time08 if value["id"] == "duckling:en-ambiguous:0")
    add_group("group:duckling-surface-normalizations", "Duckling", "surface temporal normalization", "time-08", [
        {"payload": value} for value in duck["alternatives"]],
              source_selector="$.integration.external_analyses[id=duckling:en-ambiguous:0].alternatives[*]")

    sem04 = load("sem-04")["analyses"][0]
    add_group(f"group:phonetisaurus-{sem04['word']}", "Phonetisaurus", "WFST G2P", "sem-04", [
        {"payload": value, "score": value.get("score"), "score_kind": "native score when exposed"}
        for value in sem04["candidates"]], source_selector=f"$.analyses[word={sem04['word']}].candidates[*]")

    dlg04 = load("dlg-04")[0]
    by_target = {}
    for act in dlg04["dialogue_acts"]:
        by_target.setdefault(act["target"], []).append(act)
    target, acts = next((target, values) for target, values in by_target.items() if len(values) > 1)
    add_group("group:diaml-multidimensional", "DialogBank", "ISO 24617-2/DiAML", "dlg-04",
              [{"payload": act} for act in acts], relation="compatible_multilabel",
              constraints=[f"same functional segment: {target}"],
              source_selector=f"$[0].dialogue_acts[target={target}]")

    dlg05 = load("dlg-05")[0]
    relation_by_id = {value["id"]: value for value in dlg05["relations"]}
    crossing_ids = dlg05["crossing_relation_pairs"][0]
    add_group("group:sdrt-crossing-structure", "DISRPT/STAC", "SDRT", "dlg-05",
              [{"payload": relation_by_id[rid]} for rid in crossing_ids], relation="compatible_structure",
              constraints=["crossing relation pair retained as graph edges, not forced into a tree"],
              source_selector=f"$[0].relations[id in {crossing_ids}]")

    disc01 = next(value for value in load("disc-01") if value["trees"])
    add_group("group:rst-analysis", "IsaNLP RST", "RST binary constituency", "disc-01",
              [{"payload": disc01["trees"][0]}], relation="single_measured_analysis",
              source_selector="$[first fixture with trees].trees[0]")

    dlg03 = load("dlg-03")[0]
    erg, dynamic = dlg03["analyses"]
    add_group("group:erg-ds-coanalysis", "ACE/ERG and dynamicsyntax-python", "MRS + TTR", "dlg-03", [
        {"payload": {"producer": erg["producer"], "candidate": erg["candidates"][0]}},
        {"payload": {"producer": dynamic["producer"], "semantics": dynamic["semantics"],
                     "incremental_states": dynamic["incremental_states"], "actions": dynamic["actions"]}},
    ], relation="cross_formalism_coanalysis",
       constraints=["shared surface only", "no MRS/TTR node identity asserted"],
       source_selector="$[0].analyses[*]")

    dlg07 = load("dlg-07")
    ambiguous_step = next(step for step in dlg07["steps"] if step["selection"]["candidate_id"] is None)
    add_group("group:isu-measured-ambiguity", "seman2 ISU engine", "Information State Update", "dlg-07", [
        {"payload": candidate, "score": candidate.get("score"), "score_kind": "native ISU candidate score"}
        for candidate in ambiguous_step["candidates"]
    ], constraints=["measured no-decision step; alternatives retained"],
       source_selector="$.steps[selection.candidate_id=null].candidates[*]")

    exclusive = [group for group in groups if group["relation"] == "exclusive_alternatives"]
    potential_product = math.prod(group["candidate_count"] for group in exclusive)
    candidate_nodes = [n for n, d in graph.nodes(data=True) if d["node_type"] == "candidate"]
    conflict_edges = [(u, v) for u, v, d in graph.edges(data=True) if d["edge_type"] == "conflicts_with"]
    cross_group_conflicts = [(u, v) for u, v in conflict_edges if u.rsplit(":candidate:", 1)[0] != v.rsplit(":candidate:", 1)[0]]
    selection_nodes = [n for n, d in graph.nodes(data=True) if d["node_type"] == "selection"]
    combination_nodes = [n for n, d in graph.nodes(data=True) if d["node_type"] == "cartesian_combination"]
    exact_supports = all(
        sorted(graph.nodes[group["support_id"]]["supported_payload_sha256"]) ==
        sorted(graph.nodes[candidate]["payload_sha256"] for candidate in graph.predecessors(group["id"])
               if graph.nodes[candidate]["node_type"] == "candidate")
        for group in groups)

    node_rows = [{"id": n, "node_type": d["node_type"], "attributes_json": canonical(d)}
                 for n, d in graph.nodes(data=True)]
    edge_rows = [{"source": u, "target": v, "id": key, "edge_type": d["edge_type"],
                  "attributes_json": canonical(d)} for u, v, key, d in graph.edges(keys=True, data=True)]
    rust_graph = rx.PyDiGraph(multigraph=True)
    rust_nodes = {row["id"]: rust_graph.add_node(row) for row in node_rows}
    for row in edge_rows:
        rust_graph.add_edge(rust_nodes[row["source"]], rust_nodes[row["target"]], row)
    OUT.mkdir(parents=True, exist_ok=True)
    tables = {
        "nodes": pa.Table.from_pylist(node_rows), "edges": pa.Table.from_pylist(edge_rows),
        "candidate-payloads": pa.Table.from_pylist(payloads),
    }
    roundtrip = {}
    for name, table in tables.items():
        path = OUT / f"{name}.parquet"
        pq.write_table(table, path, compression="zstd")
        roundtrip[name] = pq.read_table(path).to_pylist() == table.to_pylist()

    result = {
        "contract": "seman2-factorized-ambiguity-v1", "groups": groups,
        "graph": nx.node_link_data(graph, edges="edges"),
        "validation": {
            "candidate_count": len(candidate_nodes), "exclusive_group_count": len(exclusive),
            "potential_cartesian_combination_count": potential_product,
            "materialized_cartesian_combination_count": len(combination_nodes),
            "selection_node_count": len(selection_nodes), "conflict_edge_count": len(conflict_edges),
            "cross_group_conflict_count": len(cross_group_conflicts), "parquet_roundtrips": roundtrip,
            "all_payload_hashes_valid": all(digest(json.loads(row["payload_json"])) == row["sha256"] for row in payloads),
            "all_support_slices_match_candidate_payloads": exact_supports,
            "all_groups_from_measured_outputs": all(group["source_poc"] != "contract-fixture" for group in groups),
            "rustworkx_node_count_matches": rust_graph.num_nodes() == graph.number_of_nodes(),
            "rustworkx_edge_count_matches": rust_graph.num_edges() == graph.number_of_edges(),
        },
    }
    validation = result["validation"]
    assert all(roundtrip.values()) and validation["all_payload_hashes_valid"] and exact_supports
    assert validation["all_groups_from_measured_outputs"]
    assert validation["rustworkx_node_count_matches"] and validation["rustworkx_edge_count_matches"]
    assert potential_product > 1 and not combination_nodes and not selection_nodes and not cross_group_conflicts
    assert all(graph.nodes[group["id"]]["selection"] is None for group in groups)
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {
        "group_count": len(groups), "candidate_count": len(candidate_nodes),
        "exclusive_group_count": len(exclusive), "compatible_or_single_group_count": len(groups) - len(exclusive),
        "potential_cartesian_combination_count": potential_product,
        "materialized_cartesian_combination_count": 0, "selection_count": 0,
        "conflict_edge_count": len(conflict_edges), "cross_group_conflict_count": 0,
        "all_support_slices_match_candidate_payloads": exact_supports,
        "all_groups_from_measured_outputs": True,
        "networkx_rustworkx_agreement": True,
        "verdict": "GO_FACTORIZED_NON_DESTRUCTIVE_AMBIGUITY_GRAPH",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "networkx": importlib.metadata.version("networkx"),
        "rustworkx": importlib.metadata.version("rustworkx"),
        "pyarrow": importlib.metadata.version("pyarrow"), "selection_policy": "none",
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"GRAPH-03: {len(groups)} groups/{len(candidate_nodes)} candidates; "
          f"0 of {potential_product} Cartesian combinations materialized; ambiguity graph GO")


if __name__ == "__main__":
    main()
