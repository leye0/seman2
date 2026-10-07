#!/usr/bin/env python3
"""Validate the active architecture graph and its POC derivation."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "plans" / "systeme_cognitif_developpemental.json"
REQUIRED = ROOT / "plans" / "required_poc.md"
HEADING = re.compile(r"^###\s+(SYS-\d+)\s+—", re.MULTILINE)


def validate() -> list[str]:
    errors: list[str] = []
    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    components = data.get("components", [])
    by_id = {row.get("id"): row for row in components}

    if len(by_id) != len(components) or None in by_id:
        errors.append("component identifiers must be present and unique")

    expected_levels = [f"L{i}-" for i in range(8)]
    levels = data.get("artifact_levels", [])
    for prefix in expected_levels:
        if sum(value.startswith(prefix) for value in levels) != 1:
            errors.append(f"missing or duplicate artifact level {prefix[:-1]}")

    for identifier, component in by_id.items():
        for dependency in component.get("dependencies", []):
            if dependency not in by_id:
                errors.append(f"{identifier}: unknown dependency {dependency}")
        if component.get("raw_source_access") and identifier != "experience-gateway":
            errors.append(f"{identifier}: forbidden raw source access")
        if component.get("layer", 0) >= 2:
            if any("source-record" == item for item in component.get("consumes", [])):
                errors.append(f"{identifier}: high level consumes a source record")

    visited: set[str] = set()
    active: list[str] = []

    def visit(identifier: str) -> None:
        if identifier in active:
            cycle = " -> ".join(active[active.index(identifier) :] + [identifier])
            errors.append(f"same-wave dependency cycle: {cycle}")
            return
        if identifier in visited:
            return
        active.append(identifier)
        for dependency in by_id[identifier].get("dependencies", []):
            visit(dependency)
        active.pop()
        visited.add(identifier)

    for identifier in by_id:
        visit(identifier)

    for source, target, timing in data.get("allowed_feedback_edges", []):
        if source not in by_id or target not in by_id:
            errors.append(f"feedback edge references unknown component: {source}->{target}")
        if timing not in {"next-wave-only", "next-turn-only", "attributed-experience-only", "state-read-only"}:
            errors.append(f"feedback edge has unknown timing: {source}->{target}:{timing}")

    required_ids = HEADING.findall(REQUIRED.read_text(encoding="utf-8"))
    graph_ids = data.get("required_poc_order", [])
    if required_ids != graph_ids:
        errors.append(
            f"POC order differs between graph and required plan: {required_ids} != {graph_ids}"
        )
    if re.search(r"^###\s+(?!SYS-)[A-Z]+-\d+\s+—", REQUIRED.read_text(encoding="utf-8"), re.MULTILINE):
        errors.append("active POC plan contains a non-SYS legacy identifier")

    forbidden = set(data.get("forbidden_paths", []))
    expected_forbidden = {
        "raw-source-to-high-level-component",
        "audit-journal-to-cognitive-retrieval",
        "dictionary-to-semantic-memory",
        "external-evaluator-to-runtime-write",
        "surface-analyzer-to-cultural-interpretation",
    }
    missing = expected_forbidden - forbidden
    if missing:
        errors.append(f"missing forbidden paths: {sorted(missing)}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"status": "INVALID", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "status": "VALID",
                "components": len(data["components"]),
                "artifact_levels": len(data["artifact_levels"]),
                "required_pocs": len(data["required_poc_order"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
