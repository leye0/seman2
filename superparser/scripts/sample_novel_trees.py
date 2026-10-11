#!/usr/bin/env python3
"""Select a deterministic, diagnostically useful sample of parsed trees."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
from typing import Any, Iterable


COMPLEX_RULE_MARKERS = (
    "clause", "coord", "list", "relative", "subord", "complement",
    "infinit", "partic", "passive", "conditional", "appos", "quote", "pp",
)


def walk(tree: dict[str, Any]) -> Iterable[tuple[dict[str, Any], int]]:
    stack = [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        yield node, depth
        stack.extend((child, depth + 1) for child in reversed(node.get("children", ())))


def tree_metrics(row: dict[str, Any]) -> dict[str, Any]:
    tree = row["best_analysis"]
    nodes = list(walk(tree))
    leaves = [node for node, _depth in nodes if not node.get("children")]
    rules = [str(node.get("rule_id") or "") for node, _depth in nodes]
    complex_rules = sorted({
        rule for rule in rules
        if any(marker in rule.casefold() for marker in COMPLEX_RULE_MARKERS)
    })
    unary_nodes = sum(len(node.get("children", ())) == 1 for node, _depth in nodes)
    syntax_links = sum(
        len((node.get("syntax") or {}).get("links", ())) for node, _depth in nodes
    )

    max_unary_chain = 0
    violations: list[str] = []
    for node, _depth in nodes:
        chain = 0
        cursor = node
        while len(cursor.get("children", ())) == 1:
            chain += 1
            cursor = cursor["children"][0]
        max_unary_chain = max(max_unary_chain, chain)

        parent_span = node.get("span") or [0, 0]
        children = node.get("children", ())
        previous_start = -1
        child_spans: list[tuple[int, int]] = []
        for child in children:
            start, end = child.get("span") or [0, 0]
            child_spans.append((start, end))
            if start < parent_span[0] or end > parent_span[1]:
                violations.append("child_outside_parent")
            if start < previous_start:
                violations.append("children_out_of_order")
            previous_start = start
        if len(children) > 1 and len(child_spans) != len(set(child_spans)):
            violations.append("duplicate_sibling_span")
        if children and not node.get("rule_id"):
            violations.append("nonterminal_without_rule")

    first_token = row["tokens"][0]["start"] if row.get("tokens") else 0
    last_content = max(
        (token["end"] for token in row.get("tokens", ()) if token["text"] not in ".,!?;:\""),
        default=0,
    )
    root_start, root_end = tree.get("span") or [0, 0]
    if root_start > first_token:
        violations.append("root_misses_prefix")
    if root_end < last_content:
        violations.append("root_misses_suffix")
    if tree.get("category") != "CLAUSE":
        violations.append("unexpected_root_category")

    token_count = len(row.get("tokens", ()))
    leaf_coverage = len(leaves) / max(token_count, 1)
    if token_count >= 12 and leaf_coverage < 0.45:
        violations.append("low_lexical_leaf_coverage")
    if max_unary_chain >= 7:
        violations.append("long_unary_chain")

    structure = row.get("structure_stats", {})
    forest_nodes = int(structure.get("forest_nodes") or 0)
    derivations = int(structure.get("structural_derivations") or 0)
    combinations = int(structure.get("combinations_visited_for_best") or 0)
    depth = max(depth for _node, depth in nodes)
    node_count = len(nodes)
    if depth >= 23:
        violations.append("unusually_deep_tree")
    complexity_score = (
        depth * 2.5 + node_count * 0.35 + token_count * 0.6
        + len(complex_rules) * 3.0 + syntax_links * 0.3
    )
    ambiguity_score = (
        math.log1p(derivations) * 6.0
        + math.log1p(derivations / max(forest_nodes, 1)) * 8.0
        + math.log1p(combinations) * 2.0
    )
    suspicious_score = (
        len(set(violations)) * 10.0
        + max(0, max_unary_chain - 5) * 2.0
        + max(0, depth - 18) * 0.5
        + max(0.0, 0.6 - leaf_coverage) * 10.0
    )
    return {
        "token_count": token_count,
        "tree_nodes": node_count,
        "leaf_nodes": len(leaves),
        "max_depth": depth,
        "unary_nodes": unary_nodes,
        "max_unary_chain": max_unary_chain,
        "syntax_links": syntax_links,
        "complex_rules": complex_rules,
        "forest_nodes": forest_nodes,
        "structural_derivations": derivations,
        "derivations_per_forest_node": round(derivations / max(forest_nodes, 1), 4),
        "combinations_for_best": combinations,
        "lexical_leaf_coverage": round(leaf_coverage, 4),
        "structural_warnings": sorted(set(violations)),
        "complexity_score": round(complexity_score, 4),
        "ambiguity_score": round(ambiguity_score, 4),
        "suspicious_score": round(suspicious_score, 4),
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * fraction)]


def select(rows: list[dict[str, Any]], *, seed: int) -> tuple[list[dict[str, Any]], dict[str, list[int]]]:
    for row in rows:
        row["sample_metrics"] = tree_metrics(row)

    complex_rows = sorted(
        rows, key=lambda row: (row["sample_metrics"]["complexity_score"], row["index"]),
        reverse=True,
    )[:10]
    ambiguous_rows = sorted(
        rows, key=lambda row: (row["sample_metrics"]["ambiguity_score"], row["index"]),
        reverse=True,
    )[:10]
    slow_rows = sorted(rows, key=lambda row: (row["duration_ms"], row["index"]), reverse=True)[:10]
    suspicious_rows = [
        row for row in sorted(
            rows, key=lambda row: (row["sample_metrics"]["suspicious_score"], row["index"]),
            reverse=True,
        )
        if row["sample_metrics"]["suspicious_score"] > 0
    ][:5]

    complexity_cutoff = percentile(
        [row["sample_metrics"]["complexity_score"] for row in rows], 0.60,
    )
    ambiguity_cutoff = percentile(
        [row["sample_metrics"]["ambiguity_score"] for row in rows], 0.60,
    )
    speed_cutoff = percentile([float(row["duration_ms"]) for row in rows], 0.60)
    ordinary_pool = [
        row for row in rows
        if 5 <= row["sample_metrics"]["token_count"] <= 24
        and row["sample_metrics"]["complexity_score"] <= complexity_cutoff
        and row["sample_metrics"]["ambiguity_score"] <= ambiguity_cutoff
        and float(row["duration_ms"]) <= speed_cutoff
        and not row["sample_metrics"]["structural_warnings"]
    ]
    ordinary_rows = random.Random(seed).sample(ordinary_pool, 10)

    groups = {
        "ordinary_random": [row["index"] for row in ordinary_rows],
        "grammatically_complex": [row["index"] for row in complex_rows],
        "high_ambiguity": [row["index"] for row in ambiguous_rows],
        "particularly_slow": [row["index"] for row in slow_rows],
        "structurally_suspicious": [row["index"] for row in suspicious_rows],
    }
    by_index = {row["index"]: row for row in rows}
    selected_indices = set(index for indices in groups.values() for index in indices)
    if len(selected_indices) < 30:
        topup_pool = [row for row in ordinary_pool if row["index"] not in selected_indices]
        topup = random.Random(seed + 1).sample(topup_pool, 30 - len(selected_indices))
        groups["ordinary_topup"] = [row["index"] for row in topup]
        selected_indices.update(groups["ordinary_topup"])

    membership: dict[int, list[str]] = {}
    for group, indices in groups.items():
        for index in indices:
            membership.setdefault(index, []).append(group)
    selected = []
    for index in sorted(selected_indices):
        row = by_index[index]
        row["sample_groups"] = membership[index]
        selected.append(row)
    return selected, groups


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path,
        default=root / "output" / "the_map_of_everything_syntax.jsonl",
    )
    parser.add_argument(
        "--output", type=Path,
        default=root / "output" / "the_map_of_everything_tree_sample.jsonl",
    )
    parser.add_argument("--seed", type=int, default=20261011)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    with args.input.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if (
                row.get("record_type") == "sentence"
                and row.get("status") == "complete"
                and row.get("best_analysis") is not None
            ):
                rows.append(row)

    selected, groups = select(rows, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        metadata = {
            "record_type": "metadata",
            "format": "seman2-tree-sample-jsonl-v1",
            "source": str(args.input),
            "seed": args.seed,
            "unique_tree_count": len(selected),
            "groups": groups,
            "criteria": {
                "ordinary_random": "random among structurally clean, lower-60% complexity/ambiguity/duration, 5-24 tokens",
                "grammatically_complex": "highest combined tree depth, tree size, length, complex-rule diversity and syntax links",
                "high_ambiguity": "highest structural derivation count/density and best-tree search combinations",
                "particularly_slow": "highest measured total parse duration",
                "structurally_suspicious": "top structural warning score (span/order/root/coverage/unary checks)",
            },
        }
        stream.write(json.dumps(metadata, ensure_ascii=False) + "\n")
        for row in selected:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.write(json.dumps({
            "record_type": "summary",
            "unique_tree_count": len(selected),
            "membership_counts": dict(Counter(
                group for row in selected for group in row["sample_groups"]
            )),
        }, ensure_ascii=False) + "\n")
    print(f"Wrote {len(selected)} unique trees to {args.output}")


if __name__ == "__main__":
    main()
