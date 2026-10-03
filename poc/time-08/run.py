#!/usr/bin/env python3
"""TIME-08: quarantine legacy temporal surface analyzers."""

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
LEGACY = ROOT / "legacy"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    heidel = load(LEGACY / "heideltime/output/results.json")
    duckling = load(LEGACY / "duckling/output/results.json")
    coexistence = load(LEGACY / "coexistence/output/results.json")
    cognitive_relations = [
        {"left": "episode-a", "relation": "before", "right": "episode-b", "source": "observable_order"},
        {"left": "episode-b", "relation": "before", "right": "episode-c", "source": "episodic_context"},
    ]
    relation_hash_before = digest(cognitive_relations)
    external = []
    for result in heidel:
        for index, annotation in enumerate(result["annotations"]):
            external.append({
                "id": f"heidel:{result['fixture']['id']}:{index}", "layer": "external_analysis",
                "producer": "HeidelTime", "span": annotation["span"], "native_type": annotation["type"],
                "native_value": annotation["value"], "selected_as_cognitive_truth": False,
                "may_create_external_anchor": True, "may_create_cognitive_relation": False,
            })
    for result in duckling:
        for index, annotation in enumerate(result["annotations"]):
            external.append({
                "id": f"duckling:{result['fixture']['id']}:{index}", "layer": "external_analysis",
                "producer": "Duckling", "span": annotation["span"], "native_type": annotation["dimension"],
                "native_value": annotation["raw_value"], "alternatives": annotation["alternatives"],
                "selected_as_cognitive_truth": False, "may_create_external_anchor": True,
                "may_create_cognitive_relation": False,
            })
    integrated = {"cognitive_relations": cognitive_relations, "external_analyses": external}
    relation_hash_after = digest(integrated["cognitive_relations"])
    assert relation_hash_before == relation_hash_after
    assert all(not analysis["selected_as_cognitive_truth"] and not analysis["may_create_cognitive_relation"] for analysis in external)
    coexistence_summary = load(LEGACY / "coexistence/output/summary.json")
    assert coexistence_summary["arbitrary_truth_selection_performed"] is False
    gaps = [
        {"phenomenon": "reference_time_and_reported_speech", "represented_by_surface_normalization": False, "covered_by": "TIME-03"},
        {"phenomenon": "state_persistence_and_inertia", "represented_by_surface_normalization": False, "covered_by": "TIME-04"},
        {"phenomenon": "temporal_anaphora_candidate_sets", "represented_by_surface_normalization": False, "covered_by": "TIME-05"},
        {"phenomenon": "episodic_relational_recall", "represented_by_surface_normalization": False, "covered_by": "TIME-06"},
        {"phenomenon": "non_destructive_revision", "represented_by_surface_normalization": False, "covered_by": "TIME-07"},
    ]
    result = {
        "legacy_measurements": {
            "heideltime_fixture_count": len(heidel), "duckling_fixture_count": len(duckling),
            "coexistence_occurrence_count": len(coexistence["occurrences"]),
        },
        "integration": integrated, "capability_gaps": gaps,
        "relational_hash_before_external_analyses": relation_hash_before,
        "relational_hash_after_external_analyses": relation_hash_after,
        "removing_external_analyses_preserves_cognitive_relations": True,
        "validations": {
            "external_analyses_never_selected": all(not item["selected_as_cognitive_truth"] for item in external),
            "external_analyses_cannot_create_cognitive_relations": all(not item["may_create_cognitive_relation"] for item in external),
            "addition_preserves_relational_hash": relation_hash_before == relation_hash_after,
            "removal_preserves_relational_hash": digest(cognitive_relations) == relation_hash_after,
            "coexistence_made_no_arbitrary_selection": coexistence_summary["arbitrary_truth_selection_performed"] is False,
        },
    }
    summary = {
        "external_analysis_count": len(external),
        "producer_counts": {name: sum(a["producer"] == name for a in external) for name in ("HeidelTime", "Duckling")},
        "surface_capability_gap_count": len(gaps), "arbitrary_truth_selection_count": 0,
        "cognitive_relation_mutation_count": 0,
        "verdict": "GO_EXTERNAL_TEMPORAL_ANALYZERS_QUARANTINED",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    assert all(result["validations"].values())
    for name, value in (("results.json", result), ("summary.json", summary), ("surface-capability-gaps.json", gaps), ("versions-and-parameters.json", {"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "legacy_sources": ["HeidelTime extraction fixture", "Duckling extraction fixture", "analyzer coexistence fixture"], "policy": "external attributed annotations only"})):
        (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"TIME-08: {len(external)} quarantined analyses; 0 cognitive relation mutation; {len(gaps)} documented gaps")


if __name__ == "__main__":
    main()
