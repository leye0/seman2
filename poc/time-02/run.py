#!/usr/bin/env python3
"""TIME-02: Allen interval-algebra constraint network."""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
from typing import Any


POC_DIR = Path(__file__).resolve().parent
OUTPUT = POC_DIR / "output"
RELATIONS = (
    "before", "meets", "overlaps", "starts", "during", "finishes", "equals",
    "finished_by", "contains", "started_by", "overlapped_by", "met_by", "after",
)
ALL = frozenset(RELATIONS)
CONVERSE = {
    "before": "after", "meets": "met_by", "overlaps": "overlapped_by",
    "starts": "started_by", "during": "contains", "finishes": "finished_by",
    "equals": "equals", "finished_by": "finishes", "contains": "during",
    "started_by": "starts", "overlapped_by": "overlaps", "met_by": "meets", "after": "before",
}


def relation(left: tuple[int, int], right: tuple[int, int]) -> str:
    a, b = left
    c, d = right
    if b < c: return "before"
    if b == c: return "meets"
    if a < c < b < d: return "overlaps"
    if a == c and b < d: return "starts"
    if c < a and b < d: return "during"
    if c < a and b == d: return "finishes"
    if a == c and b == d: return "equals"
    if a < c and b == d: return "finished_by"
    if a < c and d < b: return "contains"
    if a == c and d < b: return "started_by"
    if c < a < d < b: return "overlapped_by"
    if d == a: return "met_by"
    if d < a: return "after"
    raise AssertionError((left, right))


def build_composition_table() -> dict[tuple[str, str], frozenset[str]]:
    intervals = [(start, end) for start in range(7) for end in range(start + 1, 7)]
    table: dict[tuple[str, str], set[str]] = {(a, b): set() for a in RELATIONS for b in RELATIONS}
    for first in intervals:
        for middle in intervals:
            left_relation = relation(first, middle)
            for last in intervals:
                right_relation = relation(middle, last)
                table[left_relation, right_relation].add(relation(first, last))
    assert all(table.values()), "finite-domain derivation did not cover the full algebra"
    return {key: frozenset(value) for key, value in table.items()}


COMPOSITION = build_composition_table()


def compose(left: frozenset[str], right: frozenset[str]) -> frozenset[str]:
    return frozenset(result for a in left for b in right for result in COMPOSITION[a, b])


def converse(relations: frozenset[str]) -> frozenset[str]:
    return frozenset(CONVERSE[item] for item in relations)


def solve(fixture: dict[str, Any]) -> dict[str, Any]:
    nodes = fixture["nodes"]
    constraints = {(left, right): (frozenset({"equals"}) if left == right else ALL) for left in nodes for right in nodes}
    provenance: dict[tuple[str, str], list[dict[str, Any]]] = {(left, right): [] for left in nodes for right in nodes}
    inconsistency: dict[str, Any] | None = None

    for item in fixture["constraints"]:
        left, right = item["left"], item["right"]
        proposed = frozenset(item["relations"])
        previous = constraints[left, right]
        refined = previous & proposed
        provenance[left, right].append({"kind": "asserted", "source": item["source"], "relations": sorted(proposed)})
        if not refined:
            inconsistency = {"pair": [left, right], "existing": sorted(previous), "incoming": sorted(proposed), "source": item["source"]}
            break
        constraints[left, right] = refined
        inverse_previous = constraints[right, left]
        inverse_refined = inverse_previous & converse(proposed)
        provenance[right, left].append({"kind": "asserted_converse", "source": item["source"], "relations": sorted(converse(proposed))})
        if not inverse_refined:
            inconsistency = {"pair": [right, left], "existing": sorted(inverse_previous), "incoming": sorted(converse(proposed)), "source": item["source"]}
            break
        constraints[right, left] = inverse_refined

    refinements = []
    changed = inconsistency is None
    while changed and inconsistency is None:
        changed = False
        for left, middle, right in permutations(nodes, 3):
            candidate = constraints[left, right] & compose(constraints[left, middle], constraints[middle, right])
            if not candidate:
                inconsistency = {
                    "pair": [left, right], "via": middle,
                    "existing": sorted(constraints[left, right]),
                    "composed": sorted(compose(constraints[left, middle], constraints[middle, right])),
                }
                break
            if candidate != constraints[left, right]:
                record = {
                    "pair": [left, right], "via": middle,
                    "before": sorted(constraints[left, right]), "after": sorted(candidate),
                    "left_support": sorted(constraints[left, middle]),
                    "right_support": sorted(constraints[middle, right]),
                }
                refinements.append(record)
                provenance[left, right].append({"kind": "path_consistency_refinement", **record})
                constraints[left, right] = candidate
                constraints[right, left] = converse(candidate)
                changed = True

    consistent = inconsistency is None
    queries = []
    if consistent:
        for query in fixture["oracle"]["queries"]:
            actual = sorted(constraints[query["left"], query["right"]])
            expected = sorted(ALL) if query["relations"] == "ALL" else sorted(query["relations"])
            assert actual == expected, (fixture["id"], query, actual)
            queries.append({"left": query["left"], "right": query["right"], "relations": actual, "oracle_passed": True})
    assert consistent == fixture["oracle"]["consistent"]
    return {
        "fixture_id": fixture["id"], "formalism": "AllenIntervalAlgebra",
        "consistent": consistent, "asserted_constraints": fixture["constraints"],
        "queries": queries, "refinements": refinements, "inconsistency": inconsistency,
        "atomic_relation_selected_without_evidence": False,
        "learned_graph_primitives_created": False,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    results = [solve(fixture) for fixture in fixtures]
    assert len(RELATIONS) == 13 and all(CONVERSE[CONVERSE[r]] == r for r in RELATIONS)
    assert all(compose(frozenset({"equals"}), frozenset({r})) == frozenset({r}) for r in RELATIONS)
    summary = {
        "fixture_count": len(results), "relation_count": len(RELATIONS),
        "composition_cell_count": len(COMPOSITION),
        "consistent_fixture_count": sum(result["consistent"] for result in results),
        "inconsistent_fixture_count": sum(not result["consistent"] for result in results),
        "refinement_count": sum(len(result["refinements"]) for result in results),
        "disjunction_preserved": any(len(query["relations"]) > 1 for result in results for query in result["queries"]),
        "verdict": "GO_ALLEN_CONSTRAINT_PROPAGATION_WITH_ATTRIBUTED_FORMALISM",
    }
    write_json(OUTPUT / "results.json", results)
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "composition-table.json", {f"{a}|{b}": sorted(value) for (a, b), value in sorted(COMPOSITION.items())})
    write_json(OUTPUT / "versions-and-parameters.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "formalism": "AllenIntervalAlgebra",
        "composition_derivation": "exhaustive classification of triples of proper intervals over seven ordered endpoints",
        "closure": "path consistency to fixed point", "ontology_status": "external formalism only",
    })
    print(f"TIME-02: {len(RELATIONS)} relations, {len(COMPOSITION)} composition cells, {summary['inconsistent_fixture_count']} inconsistency detected")


if __name__ == "__main__":
    main()
