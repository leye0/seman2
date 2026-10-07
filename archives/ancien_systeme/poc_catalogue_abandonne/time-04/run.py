#!/usr/bin/env python3
"""TIME-04: small Event-Calculus-inspired state persistence engine."""

from __future__ import annotations

import copy
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POC_DIR = Path(__file__).resolve().parent
OUTPUT = POC_DIR / "output"


def run_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(fixture["initial_state"])
    snapshots = [{"position": "initial", "state": copy.deepcopy(state), "proofs": {key: ["initial_state"] for key in state}}]
    proofs = {key: ["initial_state"] for key in state}
    conflicts = []
    event_trace = []
    for position in fixture["positions"]:
        proposals: dict[str, list[dict[str, Any]]] = {}
        for event in position["events"]:
            event_trace.append({"position": position["id"], "event": event["id"], "effects": event["effects"]})
            for fluent, value in event["effects"].items():
                proposals.setdefault(fluent, []).append({"event": event["id"], "value": value})
        for fluent, changes in proposals.items():
            values = {json.dumps(change["value"], sort_keys=True) for change in changes}
            if len(values) > 1:
                conflicts.append({
                    "position": position["id"], "fluent": fluent, "proposals": changes,
                    "classification": "simultaneous_incompatible_effects",
                })
                continue
            state[fluent] = changes[0]["value"]
            proofs[fluent] = [f"initiated_or_terminated_by:{change['event']}@{position['id']}" for change in changes]
        for fluent in state:
            if fluent not in proposals:
                proofs[fluent] = proofs.get(fluent, []) + [f"persists_by_inertia_through:{position['id']}"]
        snapshots.append({"position": position["id"], "state": copy.deepcopy(state), "proofs": copy.deepcopy(proofs)})

    consistent = not conflicts
    query_results = []
    snapshot_by_position = {snapshot["position"]: snapshot for snapshot in snapshots}
    if consistent:
        for query in fixture["oracle"]["queries"]:
            snapshot = snapshot_by_position[query["position"]]
            if query.get("status") == "unknown":
                actual_status = "known" if query["fluent"] in snapshot["state"] else "unknown"
                assert actual_status == "unknown"
                actual = None
            else:
                actual_status = "known"
                actual = snapshot["state"][query["fluent"]]
                assert actual == query["value"]
            query_results.append({**query, "actual": actual, "actual_status": actual_status, "oracle_passed": True})
    assert consistent == fixture["oracle"]["consistent"]
    return {
        "fixture_id": fixture["id"], "formalism": "EventCalculusInspiredDiscreteProjection",
        "initial_state": fixture["initial_state"], "event_trace": event_trace,
        "snapshots": snapshots, "conflicts": conflicts, "consistent": consistent,
        "queries": query_results, "aspect_analyses": fixture["aspect_analyses"],
        "absolute_time_required": False, "aspect_labels_promoted_to_cognitive_primitives": False,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    results = [run_fixture(fixture) for fixture in fixtures]
    lamp = next(result for result in results if result["fixture_id"] == "lamp-successive-transformations")
    summary = {
        "fixture_count": len(results), "consistent_fixture_count": sum(r["consistent"] for r in results),
        "inconsistent_fixture_count": sum(not r["consistent"] for r in results),
        "snapshot_count": sum(len(r["snapshots"]) for r in results),
        "conflict_count": sum(len(r["conflicts"]) for r in results),
        "lamp_final_state": lamp["snapshots"][-1]["state"]["lamp.power"],
        "intermediate_states_queryable": True, "absolute_time_required": False,
        "verdict": "GO_EVENT_STATE_PERSISTENCE_WITH_EXPLICIT_CONFLICTS",
    }
    write_json(OUTPUT / "results.json", results)
    write_json(OUTPUT / "state-transition-traces.json", [{"fixture_id": r["fixture_id"], "snapshots": r["snapshots"]} for r in results])
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "versions-and-parameters.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(),
        "formalism": "Event Calculus inspired discrete fluent projection",
        "semantics": "effects at relational positions; inertia for unaffected known fluents; unknown remains unknown",
    })
    print(f"TIME-04: {len(results)} fixtures; {summary['snapshot_count']} snapshots; {summary['conflict_count']} explicit conflict")


if __name__ == "__main__":
    main()
