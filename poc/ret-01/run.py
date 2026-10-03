#!/usr/bin/env python3
"""RET-01: exact attributed directed multi-subgraph matching."""
from __future__ import annotations

import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import rustworkx as rx

P = Path(__file__).resolve().parent
OUT = P / "output"


def add_occurrence(graph, prefix, lemma="greet", reverse=False):
    actor, event, target = f"{prefix}:actor", f"{prefix}:event", f"{prefix}:target"
    graph.add_node(actor, kind="person", semantic_type="agent")
    graph.add_node(event, kind="event", lemma=lemma)
    graph.add_node(target, kind="person", semantic_type="patient")
    graph.add_edge(event if reverse else actor, actor if reverse else event,
                   key=f"{prefix}:agent", relation="role", label="agent")
    graph.add_edge(actor, event, key=f"{prefix}:evidence", relation="supported_by", label="observed")
    graph.add_edge(event, target, key=f"{prefix}:patient", relation="role", label="patient")


def to_rustworkx(graph):
    converted = rx.PyDiGraph(multigraph=True)
    indexes = {node: converted.add_node({"id": node, **attrs}) for node, attrs in graph.nodes(data=True)}
    for source, target, key, attrs in graph.edges(keys=True, data=True):
        converted.add_edge(indexes[source], indexes[target], {"key": key, **attrs})
    return converted


def main() -> None:
    host = nx.MultiDiGraph()
    add_occurrence(host, "episode:A")
    add_occurrence(host, "episode:B")
    add_occurrence(host, "distractor:C", lemma="ignore", reverse=True)
    pattern = nx.MultiDiGraph()
    pattern.add_node("?actor", kind="person", semantic_type="agent")
    pattern.add_node("?event", kind="event", lemma="greet")
    pattern.add_node("?target", kind="person", semantic_type="patient")
    pattern.add_edge("?actor", "?event", key="?agent", relation="role", label="agent")
    pattern.add_edge("?actor", "?event", key="?evidence", relation="supported_by", label="observed")
    pattern.add_edge("?event", "?target", key="?patient", relation="role", label="patient")
    node_match = nx.algorithms.isomorphism.categorical_node_match(["kind", "semantic_type", "lemma"], [None, None, None])
    edge_match = nx.algorithms.isomorphism.categorical_multiedge_match(["relation", "label"], [None, None])
    matcher = nx.algorithms.isomorphism.MultiDiGraphMatcher(host, pattern, node_match=node_match, edge_match=edge_match)
    raw_mappings = list(matcher.subgraph_isomorphisms_iter())
    occurrences = []
    for index, host_to_pattern in enumerate(raw_mappings, 1):
        bindings = {pattern_node: host_node for host_node, pattern_node in host_to_pattern.items()}
        edge_bindings = []
        for p_source, p_target, p_key, p_attrs in pattern.edges(keys=True, data=True):
            h_source, h_target = bindings[p_source], bindings[p_target]
            matching = [{"source": h_source, "target": h_target, "key": key}
                        for key, attrs in host[h_source][h_target].items()
                        if all(attrs.get(name) == p_attrs.get(name) for name in ("relation", "label"))]
            assert len(matching) == 1
            edge_bindings.append({"pattern_edge": [p_source, p_target, p_key], "host_edge": matching[0]})
        occurrence_graph = host.subgraph(bindings.values()).copy()
        rx_match = rx.is_subgraph_isomorphic(to_rustworkx(occurrence_graph), to_rustworkx(pattern),
            node_matcher=lambda left, right: all(left.get(k) == right.get(k) for k in ("kind", "semantic_type", "lemma")),
            edge_matcher=lambda left, right: all(left.get(k) == right.get(k) for k in ("relation", "label")), induced=True)
        occurrences.append({"occurrence_id": f"match:{index}", "node_bindings": bindings,
                            "edge_bindings": edge_bindings, "all_attribute_constraints_satisfied": True,
                            "rustworkx_crosscheck": rx_match})
    negative_pattern = pattern.copy()
    negative_pattern.nodes["?event"]["lemma"] = "dance"
    negative_count = sum(nx.algorithms.isomorphism.MultiDiGraphMatcher(
        host, negative_pattern, node_match=node_match, edge_match=edge_match).subgraph_isomorphisms_iter())
    validations = {
        "expected_occurrence_count": len(occurrences) == 2,
        "different_host_ids_bound": all(set(o["node_bindings"]) == set(pattern.nodes) and
                                        not set(o["node_bindings"].values()) & set(pattern.nodes) for o in occurrences),
        "directions_preserved": all(o["node_bindings"]["?actor"].endswith(":actor") for o in occurrences),
        "parallel_edges_preserved": all(len([e for e in o["edge_bindings"] if e["pattern_edge"][:2] == ["?actor", "?event"]]) == 2
                                        for o in occurrences),
        "rustworkx_crosscheck": all(o["rustworkx_crosscheck"] for o in occurrences),
        "negative_query_has_no_match": negative_count == 0,
    }
    assert all(validations.values())
    result = {"host_graph": nx.node_link_data(host, edges="edges"),
              "pattern_graph": nx.node_link_data(pattern, edges="edges"),
              "occurrences": occurrences, "negative_query_match_count": negative_count,
              "validation": validations}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {"host_node_count": host.number_of_nodes(), "host_edge_count": host.number_of_edges(),
               "pattern_node_count": pattern.number_of_nodes(), "pattern_edge_count": pattern.number_of_edges(),
               "occurrence_count": len(occurrences), "negative_match_count": negative_count,
               "parallel_edges_per_occurrence": 2,
               "verdict": "GO_EXACT_ATTRIBUTED_DIRECTED_MULTISUBGRAPH_MATCHING"}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "networkx": importlib.metadata.version("networkx"),
        "rustworkx": importlib.metadata.version("rustworkx"), "networkx_algorithm": "MultiDiGraphMatcher VF2"}, indent=2) + "\n")
    print(f"RET-01: {len(occurrences)} exact occurrences with node/edge bindings and parallel edges; GO")


if __name__ == "__main__": main()
