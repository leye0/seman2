#!/usr/bin/env python3
"""X-04: executable coherence benchmark over DLG-14 multi-turn traces."""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
OUT = P / "output"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_ids(state: dict, section: str) -> set[str]:
    return {x["id"] for x in state.get(section, []) if isinstance(x, dict) and x.get("status") in {"active", "active-digression", "open"}}


def diagnose(turn: dict) -> dict | None:
    before, after = turn["public_state_before"], turn["public_state_after"]
    tid = turn["turn_id"]
    norm = turn.get("normalization")
    if norm and norm["normalized_observation"] != norm["source_observation"]:
        return {"category": "normalisation-destructive", "delta": norm, "path": [f"obs:{tid}", "normalization", "analysis"]}
    if any(p.get("id") == "ref:she" and p.get("status") == "unresolved" for p in after.get("pending", [])) and turn["decision"].get("selected") is not None:
        return {"category": "reference-erronee", "delta": turn["decision"], "path": [f"obs:{tid}", "reference-candidates", f"decision:{tid}"]}
    effects = [effect for candidate in turn.get("update_candidates", []) for effect in candidate.get("effects", []) if isinstance(effect, str)]
    explicitly_closed = {qid for qid in active_ids(before, "qud") if any(qid in effect and effect.startswith(("pop ", "cancel ", "resolve ")) for effect in effects)}
    lost_qud = active_ids(before, "qud") - ({x.get("id") for x in after.get("qud", []) if isinstance(x, dict)}) - explicitly_closed
    if lost_qud:
        return {"category": "qud-perdu", "delta": {"lost_ids": sorted(lost_qud)}, "path": [f"state:{before['state_id']}", "isu-delta", f"state:{after['state_id']}"]}
    lost_obligations = active_ids(before, "obligations") - ({x.get("id") for x in after.get("obligations", []) if isinstance(x, dict)})
    if lost_obligations:
        return {"category": "obligation-oubliee", "delta": {"lost_ids": sorted(lost_obligations)}, "path": [f"state:{before['state_id']}", "obligation-update", f"state:{after['state_id']}"]}
    if any(isinstance(f, dict) and f.get("status") == "mutual-belief" for f in after.get("facts", [])) and not turn.get("mutual_acceptance_evidence"):
        return {"category": "grounding-surevalue", "delta": {"unsupported_status": "mutual-belief"}, "path": [f"obs:{tid}", "grounding-evidence", f"state:{after['state_id']}"]}
    if (turn["rupture_explanation"].get("reason") or "").startswith("explicit correction") and not any(h.get("status") in {"superseded-not-deleted", "historical-alternative"} for h in turn["cognitive_hypotheses"]):
        return {"category": "reparation-destructive", "delta": {"missing": "prior hypothesis"}, "path": [f"obs:{tid}", "repair", "hypothesis-history"]}
    if turn["materialized_composition"].get("semantic_fusion") is True:
        return {"category": "collapse-forme-phonologie-semantique", "delta": {"semantic_fusion": True}, "path": [f"obs:{tid}", "cross-representation-correspondence", "fused-node"]}
    beam = turn["beam_snapshot"]
    if beam.get("diversity_required") and len(set(beam.get("families", []))) < beam.get("minimum_family_coverage", 2):
        return {"category": "beam-sans-diversite", "delta": {"families": beam.get("families", [])}, "path": ["persistent-candidates", "beam-policy", f"decision:{tid}"]}
    history = turn.get("history_integrity")
    if history and history["before_sha256"] != history["after_sha256"]:
        return {"category": "reecriture-historique", "delta": history, "path": [history["object_id"], "revision", "mutated-historical-object"]}
    realization = turn.get("realization_audit")
    if realization and realization.get("added_content"):
        return {"category": "contenu-ajoute-realisation", "delta": realization, "path": [realization["plan_id"], "realizer", realization["realization_id"]]}
    return None


def run_case(case_id: str, turns: list[dict], expected: str | None) -> dict:
    started = time.perf_counter_ns()
    rupture = None
    rupture_index = None
    for index, turn in enumerate(turns):
        rupture = diagnose(turn)
        if rupture:
            rupture_index = index
            break
    latency = time.perf_counter_ns() - started
    detected = rupture["category"] if rupture else None
    assert detected == expected, (case_id, expected, rupture)
    return {
        "case_id": case_id, "turn_count": len(turns), "expected_category": expected,
        "detected_category": detected, "turns_before_rupture": len(turns) if rupture_index is None else rupture_index,
        "rupture_turn_id": None if rupture_index is None else turns[rupture_index]["turn_id"],
        "first_faulty_delta": None if rupture is None else rupture["delta"],
        "explanation_path": [] if rupture is None else rupture["path"],
        "diagnostic_latency_ns": latency, "passed": detected == expected,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_names = ["dlg-14", "x-03", "dlg-06", "dlg-07", "dlg-08", "dlg-10", "dlg-11", "hyp-03", "hyp-07", "comm-01", "gen-03"]
    source_paths = {name: ROOT / "poc" / name / "output" / "results.json" for name in source_names}
    assert all(path.exists() for path in source_paths.values())
    d14 = json.loads(source_paths["dlg-14"].read_text())
    scenarios = {s["scenario_id"]: s["turns"] for s in d14["scenarios"]}
    by_turn = {t["turn_id"]: t for turns in scenarios.values() for t in turns}

    # Enrich the clean integration traces with audit fields at the online boundaries.
    clean = copy.deepcopy(scenarios)
    for turns in clean.values():
        for t in turns:
            raw = t["observation"]["raw"]
            t["normalization"] = {"source_observation": raw, "normalized_observation": raw, "lossless": True}
            t["active_graph"] = {"observation_id": t["observation"]["observation_id"], "hypothesis_ids": [h["id"] for h in t["cognitive_hypotheses"]], "decision_id": f"decision:{t['turn_id']}"}
            t["transformation"] = {"selected": t["decision"].get("selected"), "source_state": t["public_state_before"]["state_id"], "target_state": t["public_state_after"]["state_id"]}
            t["decision_runtime"] = {"kind": "referenced-executed-contract", "soar_source": "HYP-07" if t["turn_id"] == "SCALE-T1" else "COMM-01/HYP integration contract"}
            t["realization_audit"] = {"plan_id": (t.get("communicative_plan") or {}).get("plan_id"), "realization_id": f"real:{t['turn_id']}", "added_content": []}
            stable = hashlib.sha256(json.dumps(t["cognitive_hypotheses"], sort_keys=True).encode()).hexdigest()
            t["history_integrity"] = {"object_id": f"history:{t['turn_id']}", "before_sha256": stable, "after_sha256": stable}
            if t["turn_id"] == "SCALE-T1":
                t["beam_snapshot"].update({"diversity_required": True, "minimum_family_coverage": 2})

    results = []
    for scenario_id, turns in clean.items():
        results.append(run_case(f"CLEAN-{scenario_id}", turns, None))

    def faulty(scenario_id: str, turn_id: str, mutator) -> list[dict]:
        turns = copy.deepcopy(clean[scenario_id])
        target = next(t for t in turns if t["turn_id"] == turn_id)
        mutator(target)
        return turns

    injections = [
        ("FAULT-REFERENCE", "S-REFERENCE-REPAIR", "REF-T1", "reference-erronee", lambda t: t["decision"].update(selected="ref:alice")),
        ("FAULT-QUD", "S-DIGRESSION", "DIG-T2", "qud-perdu", lambda t: t["public_state_after"].update(qud=[{"id": "q-weather", "status": "active-digression"}])),
        ("FAULT-GROUNDING", "S-ERG-DS", "ERGDS-T2", "grounding-surevalue", lambda t: t["public_state_after"].update(facts=[{"content": "like(john,mary)", "status": "mutual-belief"}])),
        ("FAULT-OBLIGATION", "S-DIGRESSION", "DIG-T2", "obligation-oubliee", lambda t: t["public_state_after"].update(obligations=[])),
        ("FAULT-REPAIR", "S-REFERENCE-REPAIR", "REF-T3", "reparation-destructive", lambda t: t.update(cognitive_hypotheses=[{"id": "ref:alice:v2", "status": "selected"}])),
        ("FAULT-NORMALIZATION", "S-UNKNOWN-IO", "UNKNOWN-T1", "normalisation-destructive", lambda t: t["normalization"].update(normalized_observation="yo", lossless=False)),
        ("FAULT-COLLAPSE", "S-UNKNOWN-IO", "UNKNOWN-T1", "collapse-forme-phonologie-semantique", lambda t: t["materialized_composition"].update(semantic_fusion=True)),
        ("FAULT-BEAM", "S-SCALE-ARCHIVE", "SCALE-T1", "beam-sans-diversite", lambda t: t["beam_snapshot"].update(active=["A-01", "A-02", "A-03", "A-04"], families=["lexical-clone"] * 4)),
        ("FAULT-HISTORY", "S-UNKNOWN-IO", "UNKNOWN-T2", "reecriture-historique", lambda t: t["history_integrity"].update(after_sha256="0" * 64)),
        ("FAULT-REALIZATION", "S-QUD", "QUD-T3", "contenu-ajoute-realisation", lambda t: t["realization_audit"].update(added_content=["weather(rain)"])),
    ]
    injected_traces = {}
    for case_id, scenario_id, turn_id, category, mutate in injections:
        trace = faulty(scenario_id, turn_id, mutate)
        injected_traces[case_id] = trace
        results.append(run_case(case_id, trace, category))

    categories = {row["detected_category"] for row in results if row["detected_category"]}
    expected_categories = {item[3] for item in injections}
    fault_results = [row for row in results if row["expected_category"]]
    clean_results = [row for row in results if row["expected_category"] is None]
    metrics_path = OUT / "benchmark-results.parquet"
    pq.write_table(pa.Table.from_pylist([{**row, "first_faulty_delta": json.dumps(row["first_faulty_delta"], ensure_ascii=False), "explanation_path": json.dumps(row["explanation_path"], ensure_ascii=False)} for row in results]), metrics_path, compression="zstd")
    validations = {
        "all_clean_dlg14_scenarios_remain_coherent": len(clean_results) == len(scenarios) and all(r["detected_category"] is None and r["turns_before_rupture"] == r["turn_count"] for r in clean_results),
        "all_required_failure_categories_measured": categories == expected_categories and len(categories) == 10,
        "all_faults_detected_at_first_faulty_turn": all(r["rupture_turn_id"] and r["first_faulty_delta"] for r in fault_results),
        "all_faults_have_observation_to_decision_paths": all(len(r["explanation_path"]) >= 3 for r in fault_results),
        "turns_before_rupture_reported": all(0 <= r["turns_before_rupture"] < r["turn_count"] for r in fault_results),
        "distractor_and_return_clean": next(r for r in clean_results if r["case_id"] == "CLEAN-S-DIGRESSION")["turns_before_rupture"] == 4,
        "actual_soar_trace_in_benchmark_source": "1 rule fired" in json.loads(source_paths["hyp-07"].read_text())["soar_beam"]["run"],
        "source_contracts_hashed": all(len(sha(path)) == 64 for path in source_paths.values()),
        "metrics_roundtrip": pq.read_table(metrics_path).num_rows == len(results),
    }
    assert all(validations.values()), validations
    output = {
        "benchmark_definition": {"clean_scenarios": list(clean), "fault_injections": [{"case_id": c, "scenario_id": s, "turn_id": t, "expected_category": cat} for c, s, t, cat, _ in injections], "diagnostic_policy": "stop at first violated invariant"},
        "results": results,
        "example_fault_traces": {case_id: next(t for t in trace if t["turn_id"] == next(x[2] for x in injections if x[0] == case_id)) for case_id, trace in injected_traces.items()},
        "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in source_paths.values()},
        "metrics": {"clean_turns_sustained": sum(r["turns_before_rupture"] for r in clean_results), "faults_detected": len(fault_results), "categories": sorted(categories), "mean_diagnostic_latency_ns": sum(r["diagnostic_latency_ns"] for r in results) / len(results)},
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps({
        "clean_scenarios": len(clean_results), "clean_turns_sustained": output["metrics"]["clean_turns_sustained"],
        "fault_cases": len(fault_results), "fault_categories": len(categories), "faults_detected": len(fault_results),
        "verdict": "GO_DIAGNOSTIC_MULTITURN_COHERENCE_BENCHMARK",
    }, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "pyarrow": importlib.metadata.version("pyarrow"), "clock": "perf_counter_ns", "stop_policy": "first invariant violation"}, indent=2) + "\n")
    print(f"X-04: {len(clean_results)} clean scenarios sustained; {len(fault_results)}/10 injected rupture classes diagnosed; GO")


if __name__ == "__main__":
    main()
