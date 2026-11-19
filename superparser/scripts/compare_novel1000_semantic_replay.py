"""Verify an additive graph migration on exact Novel-1000 v3 syntax and sources."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts import novel_ladder as ladder
from scripts import novel_source_reporting_v3 as v3

REVIEW = ladder.ROOT / "research" / "novel1000_generalization" / "reviewed-graph-deltas.json"
SCHEMA = "seman2-novel1000-reviewed-graph-deltas-v1"


def _normalized(package):
    graph = package["graph"]
    ids = {node["id"]: i for i, node in enumerate(graph["nodes"])}
    nodes = [{k: v for k, v in node.items() if k != "id"} for node in graph["nodes"]]
    handles = {key: ids[value] for key, value in package["handles"].items()}
    edges = [{**edge, "source": ids[edge["source"]], "target": ids[edge["target"]]}
             for edge in graph["relations"]]
    return nodes, handles, edges


def graph_additions(before, after):
    """Keep every existing node, handle and edge in its original order."""
    old_nodes, old_handles, old_edges = _normalized(before)
    nodes, handles, edges = _normalized(after)
    if nodes != old_nodes or handles != old_handles:
        raise ValueError("Existing nodes or handles changed")
    added = []
    idx = 0
    for edge in edges:
        if idx < len(old_edges) and edge == old_edges[idx]:
            idx += 1
            continue
        source, target = nodes[edge["source"]], nodes[edge["target"]]
        if not source["span"] or not target["span"] or edge.get("attributes"):
            raise ValueError("Unexpected inferred span or edge attributes")
        added.append({"relation": edge["relation"], "source_span": source["span"],
                      "target_span": target["span"]})
    if idx != len(old_edges):
        raise ValueError("An existing edge was removed, changed or reordered")
    return added


def compare_replays(baseline, candidate):
    manifest, groups, reference = v3.prepare()
    if manifest != ladder.read_json(v3.DIRECTORY / "source-manifest.json"):
        raise ValueError("Novel-1000 v3 source manifest changed")
    expected = ladder.read_json(v3.DIRECTORY / "baseline.json")
    observed, _ = v3.evaluate(manifest, groups, reference, baseline)
    if observed != expected:
        raise ValueError("The baseline replay does not reproduce the immutable v3 pins")
    result = {}
    stats = Counter()
    for group, (header, cases) in groups.items():
        end = cases[-1]["ladder_index"]
        base_path = baseline / f"novel-{end}-parses.jsonl"
        new_path = candidate / base_path.name
        with base_path.open(encoding="utf-8") as a, new_path.open(encoding="utf-8") as b:
            rows = [(json.loads(old), json.loads(new)) for old, new in zip(a, b, strict=True)]
        summary = ladder.read_json(candidate / f"novel-{end}-result.json")
        if (summary["cohort_sha256"] != header["cohort_sha256"] or summary["limits"] != ladder.LIMITS
                or len(rows) != len(cases) or summary["cases"] != ladder.signatures([new for _, new in rows])):
            raise ValueError(f"Unexpected cohort, limits, or result signatures for {group}")
        for case, (old, new) in zip(cases, rows, strict=True):
            ident = case["transfer_id"]
            keys = ("status", "forest_budget_exceeded", "kbest_budget_exceeded", "tree")
            if (any(new.get(k) != v for k, v in case.items())
                    or any(old.get(k) != new.get(k) for k in keys)):
                raise ValueError(f"{ident}: source, selected syntax, status, or budget flag changed")
            after_sha = ladder.graph_digest(new["selected_graph"])
            if ladder.graph_digest(old["selected_graph"]) != after_sha:
                try:
                    edges = graph_additions(old["selected_graph"], new["selected_graph"])
                except ValueError as error:
                    raise ValueError(f"{ident}: {error}") from error
                result[ident] = {"source_sha256": ladder.case_hash(case),
                                 "selected_graph_sha256": after_sha, "additions": edges}
            stats["dialogue_witnesses" if group == "witnesses" else "benchmark_passages"] += 1
    return {"schema": SCHEMA, "manifest_sha256": ladder.digest(manifest),
            "compared": dict(stats), "cases": result}


def assert_reviewed(observed, review):
    if any(observed[k] != review.get(k) for k in ("schema", "manifest_sha256", "compared")):
        raise ValueError("The graph review applies to a different corpus")
    expected = {ident: {k: row[k] for k in ("source_sha256", "selected_graph_sha256", "additions")}
                for ident, row in review["cases"].items()}
    differences = sorted(ident for ident in expected.keys() | observed["cases"].keys()
                         if expected.get(ident) != observed["cases"].get(ident))
    if differences:
        raise ValueError(f"Unreviewed or missing graph deltas: {', '.join(differences)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--review", type=Path, default=REVIEW)
    parser.add_argument("--inspect", action="store_true",
                        help="print measured deltas for manual review instead of accepting them")
    args = parser.parse_args()
    result = compare_replays(args.baseline, args.candidate)
    if args.inspect:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    assert_reviewed(result, ladder.read_json(args.review))
    additions = sum(len(row["additions"]) for row in result["cases"].values())
    print("NOVEL1000_SEMANTIC_REPLAY", {**result["compared"], "changed_graphs": len(result["cases"]),
                                        "reviewed_added_edges": additions}, flush=True)


if __name__ == "__main__":
    main()
