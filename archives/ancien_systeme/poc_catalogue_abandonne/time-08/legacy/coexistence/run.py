#!/usr/bin/env python3
"""Run TIME-03: align, but never collapse, HeidelTime and Duckling analyses."""

from __future__ import annotations

import hashlib
import json
import platform
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POC_DIR = Path(__file__).resolve().parent
ROOT = POC_DIR.parents[3]
TIME01 = POC_DIR.parent / "heideltime" / "output"
TIME02 = POC_DIR.parent / "duckling" / "output"
OUTPUT = POC_DIR / "output"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(payload.encode()).hexdigest()


def heidel_canonical(annotation: dict[str, Any]) -> dict[str, Any]:
    value = annotation.get("value")
    kind = annotation.get("type")
    comparable = value
    if kind == "TIME" and value and "T" in value:
        comparable = "T" + value.split("T", 1)[1]
    return {"family": kind.lower() if kind else None, "comparable_value": comparable}


def duckling_canonical(annotation: dict[str, Any]) -> dict[str, Any]:
    dimension = annotation["dimension"]
    value = annotation.get("value")
    grain = annotation.get("grain")
    comparable: Any = value
    family = dimension
    if dimension == "time":
        family = "date" if grain in {"day", "week", "month", "quarter", "year"} else "time"
        if annotation.get("interval"):
            comparable = annotation["interval"]
            family = "interval"
        elif isinstance(value, str) and grain == "day":
            comparable = value[:10]
        elif isinstance(value, str) and grain == "month":
            comparable = value[:7]
        elif isinstance(value, str) and grain in {"hour", "minute", "second"}:
            match = re.search(r"T(\d\d:\d\d(?::\d\d)?)", value)
            comparable = "T" + match.group(1) if match else value
            if comparable.endswith(":00") and grain == "minute":
                comparable = comparable[:-3]
    elif dimension == "duration":
        family = "duration"
        units = {"hour": "H", "minute": "M", "second": "S", "day": "D", "week": "W"}
        unit = annotation.get("unit")
        number = annotation.get("value")
        if unit in units and number is not None:
            prefix = "P" if unit in {"day", "week"} else "PT"
            comparable = f"{prefix}{number:g}{units[unit]}"
    return {"family": family, "comparable_value": comparable}


def overlap(left: list[int], right: list[int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def main() -> None:
    heidel_results = json.loads((TIME01 / "results.json").read_text(encoding="utf-8"))
    duck_results = json.loads((TIME02 / "results.json").read_text(encoding="utf-8"))
    duck_by_key = {
        (r["fixture"]["language"], r["fixture"]["text"], r["fixture"]["reftime"][:10]): r
        for r in duck_results
    }
    occurrences = []
    all_analyses = []
    all_comparisons = []

    for hresult in heidel_results:
        fixture = hresult["fixture"]
        key = (fixture["locale"], fixture["text"], fixture["dct"])
        dresult = duck_by_key.get(key)
        if dresult is None:
            continue
        occurrence_id = stable_id("temporal-occurrence:", key)
        hanalyses = []
        for index, annotation in enumerate(hresult["annotations"]):
            analysis = {
                "analysis_id": stable_id("heideltime-analysis:", [occurrence_id, annotation.get("timex_id"), index]),
                "occurrence_id": occurrence_id,
                "producer": "HeidelTime",
                "span": annotation["span"],
                "text": annotation["text"],
                "native_type": annotation["type"],
                "native_value": annotation["value"],
                "normalized": heidel_canonical(annotation),
                "source_output": "../time-01/output/results.json",
                "selected_as_truth": False,
            }
            hanalyses.append(analysis)
            all_analyses.append(analysis)
        danalyses = []
        for index, annotation in enumerate(dresult["annotations"]):
            analysis = {
                "analysis_id": stable_id("duckling-analysis:", [occurrence_id, annotation["span"], annotation["dimension"], index]),
                "occurrence_id": occurrence_id,
                "producer": "Duckling",
                "span": annotation["span"],
                "text": annotation["text"],
                "native_type": annotation["dimension"],
                "native_value": annotation["raw_value"],
                "normalized": duckling_canonical(annotation),
                "latent": annotation["latent"],
                "alternatives": annotation["alternatives"],
                "source_output": "../time-02/output/results.json",
                "selected_as_truth": False,
            }
            danalyses.append(analysis)
            all_analyses.append(analysis)

        matched_h: set[str] = set()
        matched_d: set[str] = set()
        comparisons = []
        for left in hanalyses:
            for right in danalyses:
                if not overlap(left["span"], right["span"]):
                    continue
                matched_h.add(left["analysis_id"])
                matched_d.add(right["analysis_id"])
                exact = left["span"] == right["span"]
                agrees = (
                    left["normalized"]["family"] == right["normalized"]["family"]
                    and left["normalized"]["comparable_value"] == right["normalized"]["comparable_value"]
                )
                classification = f"{'exact' if exact else 'overlap'}_{'agreement' if agrees else 'divergence'}"
                comparisons.append({
                    "comparison_id": stable_id("temporal-comparison:", [left["analysis_id"], right["analysis_id"]]),
                    "occurrence_id": occurrence_id,
                    "source_text": fixture["text"],
                    "classification": classification,
                    "span_relation": "same_span" if exact else "overlapping_spans",
                    "heideltime_analysis_id": left["analysis_id"],
                    "duckling_analysis_id": right["analysis_id"],
                    "heideltime": {"span": left["span"], "text": left["text"], **left["normalized"]},
                    "duckling": {"span": right["span"], "text": right["text"], **right["normalized"]},
                    "normalized_values_equal": agrees,
                    "selection": None,
                })
        for analysis in hanalyses:
            if analysis["analysis_id"] not in matched_h:
                comparisons.append({"occurrence_id": occurrence_id, "source_text": fixture["text"], "classification": "heideltime_only", "analysis_id": analysis["analysis_id"], "analysis": {"span": analysis["span"], "text": analysis["text"], **analysis["normalized"]}, "selection": None})
        for analysis in danalyses:
            if analysis["analysis_id"] not in matched_d:
                comparisons.append({"occurrence_id": occurrence_id, "source_text": fixture["text"], "classification": "duckling_only", "analysis_id": analysis["analysis_id"], "analysis": {"span": analysis["span"], "text": analysis["text"], **analysis["normalized"]}, "selection": None})
        all_comparisons.extend(comparisons)
        occurrences.append({
            "occurrence_id": occurrence_id,
            "text": fixture["text"],
            "language": fixture["locale"],
            "document_date": fixture["dct"],
            "heideltime_analysis_ids": [a["analysis_id"] for a in hanalyses],
            "duckling_analysis_ids": [a["analysis_id"] for a in danalyses],
            "comparisons": comparisons,
            "selected_analysis_id": None,
        })

    counts = Counter(c["classification"] for c in all_comparisons)
    assert counts["exact_agreement"] > 0
    assert counts["exact_divergence"] + counts["overlap_divergence"] > 0
    assert counts["duckling_only"] + counts["heideltime_only"] > 0
    assert all(not a["selected_as_truth"] for a in all_analyses)
    assert all(o["selected_analysis_id"] is None for o in occurrences)

    summary = {
        "shared_occurrence_count": len(occurrences),
        "analysis_count": len(all_analyses),
        "producer_counts": dict(Counter(a["producer"] for a in all_analyses)),
        "comparison_counts": dict(sorted(counts.items())),
        "selected_analysis_count": 0,
        "arbitrary_truth_selection_performed": False,
        "verdict": "GO_WITH_ATTRIBUTED_COMMON_ADAPTER",
    }
    contract = {
        "schema": "seman2.attributed-temporal-analysis-poc.v1",
        "identity_rule": "producer-specific analysis IDs remain distinct even on the same span",
        "alignment_rule": "compare exact spans first and retain partial overlaps explicitly",
        "normalization_rule": "a small typed comparison projection; native values remain authoritative and preserved",
        "selection_rule": "none; agreement is not promotion to truth and divergence is not resolved",
    }
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "inputs": {
            "time_01_results_sha256": sha256(TIME01 / "results.json"),
            "time_02_results_sha256": sha256(TIME02 / "results.json"),
        },
    }
    write_json(OUTPUT / "results.json", {"occurrences": occurrences, "analyses": all_analyses})
    write_json(OUTPUT / "comparison-matrix.json", all_comparisons)
    write_json(OUTPUT / "common-adapter-contract.json", contract)
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "versions-and-parameters.json", versions)
    print(f"TIME-03: {len(occurrences)} shared occurrences, {len(all_analyses)} analyses; {dict(counts)}")


if __name__ == "__main__":
    main()
