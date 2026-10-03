#!/usr/bin/env python3
"""TIME-05: preserve attributed temporal-discourse candidates."""

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

POC_DIR = Path(__file__).resolve().parent
OUTPUT = POC_DIR / "output"


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    results = []
    for fixture in fixtures:
        analysis = fixture["analysis"]
        start, end = analysis["marker_span"]
        candidates = []
        for index, candidate in enumerate(analysis["candidates"]):
            assert candidate["antecedent"] in fixture["events"] and candidate["target"] in fixture["events"]
            candidates.append({
                "hypothesis_id": f"{fixture['id']}:temporal-candidate:{index}", **candidate,
                "formalism": analysis["producer"], "selected": False,
                "source_marker": {"span": [start, end], "text": fixture["text"][start:end]},
            })
        status = "unresolved" if not candidates else ("ambiguous" if len(candidates) > 1 else "resolved_candidate_set")
        assert status == fixture["oracle"]["status"]
        assert len(candidates) == fixture["oracle"]["candidate_count"]
        if fixture["oracle"].get("preserve_disjunction"):
            assert len(candidates[0]["relations"]) > 1
        results.append({
            "fixture_id": fixture["id"], "text": fixture["text"], "events": fixture["events"],
            "status": status, "candidates": candidates,
            "lexical_marker_used_as_cognitive_truth": False,
            "arbitrary_candidate_selected": False,
        })
    summary = {
        "fixture_count": len(results), "ambiguous_count": sum(r["status"] == "ambiguous" for r in results),
        "unresolved_count": sum(r["status"] == "unresolved" for r in results),
        "candidate_count": sum(len(r["candidates"]) for r in results),
        "arbitrary_selection_count": 0,
        "verdict": "GO_ATTRIBUTED_TEMPORAL_DISCOURSE_CANDIDATES",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, value in (("results.json", results), ("summary.json", summary), ("versions-and-parameters.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "formalisms": ["DRT", "Temporal_DRT", "SDRT"], "input_status": "controlled external analyses",
    })):
        (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"TIME-05: {summary['candidate_count']} candidates; {summary['ambiguous_count']} ambiguous; {summary['unresolved_count']} unresolved")


if __name__ == "__main__":
    main()
