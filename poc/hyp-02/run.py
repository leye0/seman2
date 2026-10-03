#!/usr/bin/env python3
"""HYP-02: shared justification DAG, conflicts, nogoods and Z3 queries."""
from __future__ import annotations

import importlib.metadata
import itertools
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
from z3 import And, Bool, Not, Or, Solver, is_true, sat, unsat

P = Path(__file__).resolve().parent
OUT = P / "output"


def main() -> None:
    graph = nx.DiGraph(kind="justification_dag")
    nodes = {
        "support:surface-io": ("support", "observed surface is io"),
        "support:computing-context": ("support", "computing topic active"),
        "support:greeting-context": ("support", "dialogue opening position"),
        "support:astronomy-context": ("support", "astronomy topic active"),
        "support:oov": ("support", "short out-of-vocabulary form"),
        "conclusion:short-token": ("derived_conclusion", "two-character symbolic form"),
        "conclusion:social-opening": ("derived_conclusion", "opening move expects greeting"),
        "hyp:H1": ("hypothesis", "input_output_abbreviation"),
        "hyp:H2": ("hypothesis", "informal_greeting"),
        "hyp:H3": ("hypothesis", "jupiter_moon_Io"),
        "hyp:H4": ("hypothesis", "typographic_or_unknown_form"),
    }
    for node_id, (kind, value) in nodes.items():
        graph.add_node(node_id, kind=kind, value=value)
    edges = [
        ("support:surface-io", "conclusion:short-token", "derives"),
        ("support:greeting-context", "conclusion:social-opening", "derives"),
        ("conclusion:short-token", "hyp:H1", "supports"),
        ("support:computing-context", "hyp:H1", "supports"),
        ("conclusion:short-token", "hyp:H2", "supports"),
        ("conclusion:social-opening", "hyp:H2", "supports"),
        ("conclusion:short-token", "hyp:H3", "supports"),
        ("support:astronomy-context", "hyp:H3", "supports"),
        ("conclusion:short-token", "hyp:H4", "supports"),
        ("support:oov", "hyp:H4", "supports"),
    ]
    for source, target, relation in edges:
        graph.add_edge(source, target, relation=relation)
    assert nx.is_directed_acyclic_graph(graph)

    hypotheses = [f"hyp:H{i}" for i in range(1, 5)]
    explanations = {}
    naive_node_copies = 0
    for hypothesis in hypotheses:
        ancestors = nx.ancestors(graph, hypothesis)
        subgraph_nodes = ancestors | {hypothesis}
        naive_node_copies += len(subgraph_nodes)
        leaf_supports = sorted(node for node in ancestors
                               if graph.nodes[node]["kind"] == "support" and graph.in_degree(node) == 0)
        paths = []
        for leaf in leaf_supports:
            paths.extend(nx.all_simple_paths(graph, leaf, hypothesis))
        explanations[hypothesis] = {
            "minimal_leaf_dependencies": leaf_supports,
            "transitive_dependencies": sorted(ancestors),
            "justification_paths": paths,
        }

    attempted = graph.copy()
    attempted.add_edge("hyp:H2", "support:surface-io", relation="invalid_back_edge")
    cycle_would_be_created = not nx.is_directed_acyclic_graph(attempted)
    cycle_rejected = cycle_would_be_created and not graph.has_edge("hyp:H2", "support:surface-io")

    nogoods = [("hyp:H1", "hyp:H2"), ("hyp:H1", "hyp:H3"), ("hyp:H2", "hyp:H4")]
    variables = {name: Bool(name.replace(":", "_")) for name in hypotheses}
    solver = Solver()
    solver.add(Or(*variables.values()))
    for left, right in nogoods:
        solver.add(Not(And(variables[left], variables[right])))
    compatible = []
    while solver.check() == sat:
        model = solver.model()
        chosen = sorted(name for name, var in variables.items() if is_true(model.eval(var, model_completion=True)))
        compatible.append(chosen)
        solver.add(Or(*[var != model.eval(var, model_completion=True) for var in variables.values()]))
    maximal = [model for model in compatible if not any(set(model) < set(other) for other in compatible)]

    core_solver = Solver()
    core_solver.set(unsat_core=True)
    core_solver.assert_and_track(Not(And(variables["hyp:H1"], variables["hyp:H2"])), "nogood_H1_H2")
    core_solver.assert_and_track(variables["hyp:H1"], "requested_H1")
    core_solver.assert_and_track(variables["hyp:H2"], "requested_H2")
    assert core_solver.check() == unsat
    core = [str(item) for item in core_solver.unsat_core()]
    core_links = {
        "nogood_H1_H2": ["hyp:H1", "hyp:H2"],
        "requested_H1": ["hyp:H1"],
        "requested_H2": ["hyp:H2"],
    }

    shared_nodes = graph.number_of_nodes()
    shared_edges = graph.number_of_edges()
    naive_edges = sum(graph.subgraph(nx.ancestors(graph, h) | {h}).number_of_edges() for h in hypotheses)
    measurement = {
        "shared_node_count": shared_nodes, "naive_copied_node_count": naive_node_copies,
        "node_copy_avoidance": naive_node_copies - shared_nodes,
        "node_sharing_ratio_naive_over_shared": naive_node_copies / shared_nodes,
        "shared_edge_count": shared_edges, "naive_copied_edge_count": naive_edges,
        "edge_copy_avoidance": naive_edges - shared_edges,
    }
    result = {
        "justification_graph": nx.node_link_data(graph, edges="edges"),
        "explanations": explanations,
        "conflicts": [{"left": left, "right": right, "kind": "nogood"} for left, right in nogoods],
        "compatible_models": compatible, "maximal_compatible_models": maximal,
        "unsat_query": {"requested": ["hyp:H1", "hyp:H2"], "result": "unsat",
                        "unsat_core": core, "core_hypothesis_links": {name: core_links[name] for name in core}},
        "cycle_test": {"attempted_edge": ["hyp:H2", "support:surface-io"],
                       "would_create_cycle": cycle_would_be_created, "edge_rejected": cycle_rejected},
        "sharing_measurement": measurement,
    }
    assert cycle_rejected and len(maximal) > 1 and core
    assert measurement["node_copy_avoidance"] > 0 and measurement["edge_copy_avoidance"] > 0
    assert all(explanations[h]["justification_paths"] for h in hypotheses)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {
        "justification_node_count": shared_nodes, "justification_edge_count": shared_edges,
        "hypothesis_count": len(hypotheses), "nogood_count": len(nogoods),
        "compatible_model_count": len(compatible), "maximal_compatible_model_count": len(maximal),
        "unsat_core_size": len(core), "rejected_cycle_count": int(cycle_rejected),
        **measurement, "verdict": "GO_SHARED_EXPLICIT_JUSTIFICATION_AND_CONFLICT_GRAPH",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "networkx": importlib.metadata.version("networkx"),
        "z3_solver": importlib.metadata.version("z3-solver"),
        "model_enumeration": "all non-empty compatible Boolean subsets; then inclusion-maximal filter",
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"HYP-02: {len(compatible)} compatible/{len(maximal)} maximal models, "
          f"unsat core {len(core)}, avoided {measurement['node_copy_avoidance']} node copies; GO")


if __name__ == "__main__":
    main()
