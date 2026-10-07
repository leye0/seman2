#!/usr/bin/env python3
"""CONS-01: Z3 solver result contract, models, alternatives and cores."""
from __future__ import annotations

import importlib.metadata
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import z3

P = Path(__file__).resolve().parent
OUT = P / "output"
ROOT = P.parents[1]


def load_json_with_hash(path: Path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def value(model: z3.ModelRef, expr: z3.ExprRef):
    result = model.eval(expr, model_completion=True)
    if z3.is_true(result) or z3.is_false(result):
        return z3.is_true(result)
    if z3.is_int_value(result):
        return result.as_long()
    return str(result)


def sat_case() -> dict:
    start_a, start_b, room_a, room_b = z3.Ints("start_a start_b room_a room_b")
    solver = z3.Solver()
    solver.add(start_a >= 0, start_b >= 0, start_a + 2 <= start_b, start_b <= 6)
    solver.add(room_a >= 1, room_a <= 2, room_b >= 1, room_b <= 2, room_a != room_b)
    status = solver.check()
    assert status == z3.sat
    model = solver.model()
    bindings = {str(v): value(model, v) for v in (start_a, start_b, room_a, room_b)}
    return {"status": str(status).upper(), "bindings": bindings, "model": str(model), "smt2": solver.to_smt2()}


def unsat_case() -> dict:
    x = z3.Int("temperature")
    solver = z3.Solver()
    labels = [z3.Bool(name) for name in ("minimum_20", "maximum_10", "integer_domain")]
    solver.assert_and_track(x >= 20, labels[0])
    solver.assert_and_track(x <= 10, labels[1])
    solver.assert_and_track(x == z3.ToInt(z3.ToReal(x)), labels[2])
    status = solver.check()
    assert status == z3.unsat
    core = sorted(str(item) for item in solver.unsat_core())
    return {"status": str(status).upper(), "unsat_core": core, "core_size": len(core), "smt2": solver.to_smt2()}


def enumerate_models() -> dict:
    color, shape = z3.Ints("color shape")
    solver = z3.Solver()
    solver.add(color >= 0, color <= 2, shape >= 0, shape <= 1)
    models = []
    while solver.check() == z3.sat:
        model = solver.model()
        binding = {"color": value(model, color), "shape": value(model, shape)}
        models.append(binding)
        solver.add(z3.Or(color != binding["color"], shape != binding["shape"]))
    models.sort(key=lambda m: (m["color"], m["shape"]))
    return {
        "initial_status": "SAT", "underspecified": True, "variables": {"color": "0..2", "shape": "0..1"},
        "models": models, "model_count": len(models), "exhaustion_status": "UNSAT",
        "alternate_model": models[1], "alternatives_requested": True,
    }


def unknown_case() -> dict:
    # Pigeonhole 15 -> 14, deliberately stopped by a deterministic Z3 resource limit.
    pigeons = [z3.Int(f"pigeon_{i}") for i in range(15)]
    solver = z3.Solver()
    solver.set(rlimit=1)
    solver.add(*[z3.And(p >= 0, p < 14) for p in pigeons], z3.Distinct(pigeons))
    status = solver.check()
    assert status == z3.unknown
    return {
        "status": str(status).upper(), "reason_unknown": solver.reason_unknown(), "resource_limit": 1,
        "semantic_note": "UNKNOWN is an operational result under the configured resource limit, not evidence of satisfiability.",
        "smt2": solver.to_smt2(),
    }


def replay_hyp02_contract(hyp02: dict) -> dict:
    query = hyp02["unsat_query"]
    requested = {item.rsplit(":", 1)[-1] for item in query["requested"]}
    h1, h2 = z3.Bools("consumer_H1 consumer_H2")
    solver = z3.Solver()
    solver.assert_and_track(z3.Or(z3.Not(h1), z3.Not(h2)), "nogood_H1_H2")
    if "H1" in requested:
        solver.assert_and_track(h1, "requested_H1")
    if "H2" in requested:
        solver.assert_and_track(h2, "requested_H2")
    status = solver.check()
    return {
        "emitted_status": query["result"].upper(),
        "replayed_status": str(status).upper(),
        "emitted_unsat_core": sorted(query["unsat_core"]),
        "replayed_unsat_core": sorted(str(item) for item in solver.unsat_core()),
        "requested_hypotheses": query["requested"],
        "core_hypothesis_links": query["core_hypothesis_links"],
    }


def replay_hyp05_case(case: dict) -> dict:
    variables = [z3.Int(f"consumer_dim_{i}") for i in range(len(case["sizes"]))]
    base = z3.Solver()
    for variable, size in zip(variables, case["sizes"]):
        base.add(variable >= 0, variable < size)
    for constraint in case["constraints"]:
        left = variables[constraint["a_dim"]] == constraint["a"]
        right = variables[constraint["b_dim"]] == constraint["b"]
        if constraint["kind"] == "forbid_pair":
            base.add(z3.Not(z3.And(left, right)))
        elif constraint["kind"] == "implication":
            base.add(z3.Implies(left, right))
        else:  # pragma: no cover - protects the shared contract from silent extension
            raise AssertionError(f"unsupported HYP-05 constraint: {constraint['kind']}")

    replays = []
    for emitted in case["factorized"]["compositions"]:
        base.push()
        for variable, emitted_value in zip(variables, emitted["combination"]):
            base.add(variable == emitted_value)
        status = base.check()
        base.pop()
        replays.append({
            "request_id": emitted["request_id"],
            "combination": emitted["combination"],
            "status": str(status).upper(),
        })
    return {"sizes": case["sizes"], "composition_replays": replays}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {"satisfiable": sat_case(), "contradictory": unsat_case(), "underspecified": enumerate_models(), "resource_limited": unknown_case()}

    hyp02_path = ROOT / "poc/hyp-02/output/results.json"
    hyp05_path = ROOT / "poc/hyp-05/output/results.json"
    hyp05_summary_path = ROOT / "poc/hyp-05/output/summary.json"
    ret03_path = ROOT / "poc/ret-03/output/results.json"
    hyp02, hyp02_sha256 = load_json_with_hash(hyp02_path)
    hyp05, hyp05_sha256 = load_json_with_hash(hyp05_path)
    hyp05_summary, hyp05_summary_sha256 = load_json_with_hash(hyp05_summary_path)
    ret03, ret03_sha256 = load_json_with_hash(ret03_path)

    hyp02_replay = replay_hyp02_contract(hyp02)
    hyp05_replays = [replay_hyp05_case(case) for case in hyp05]
    ret03_match = ret03["integrated_sem06"]["match"]
    integrated_contract_consumers = {
        "hyp02_unsat_conflict": {
            "source_sha256": hyp02_sha256,
            **hyp02_replay,
        },
        "hyp05_lazy_compositions": {
            "source_sha256": hyp05_sha256,
            "summary_sha256": hyp05_summary_sha256,
            "case_replays": hyp05_replays,
            "requested_composition_count": sum(len(case["composition_replays"]) for case in hyp05_replays),
            "graph03_materialized_combinations": hyp05_summary["graph03_materialized_combinations"],
        },
        "ret03_temporal_relation": {
            "source_sha256": ret03_sha256,
            "final_constraints": ret03_match["final_constraints"],
            "cross_stage_entity_links": ret03_match["cross_stage_entity_links"],
            "bindings": ret03_match["bindings"],
        },
    }
    validations = {
        "sat_status_and_bindings": cases["satisfiable"]["status"] == "SAT" and len(cases["satisfiable"]["bindings"]) == 4,
        "unsat_status": cases["contradictory"]["status"] == "UNSAT",
        "minimal_relevant_core": cases["contradictory"]["unsat_core"] == ["maximum_10", "minimum_20"],
        "all_underspecified_models_enumerated": cases["underspecified"]["model_count"] == 6 and len({tuple(m.values()) for m in cases["underspecified"]["models"]}) == 6,
        "alternate_model_is_distinct": cases["underspecified"]["alternate_model"] != cases["underspecified"]["models"][0],
        "unknown_with_reason": cases["resource_limited"]["status"] == "UNKNOWN" and bool(cases["resource_limited"]["reason_unknown"]),
        "hyp02_emitted_and_replayed_unsat": hyp02_replay["emitted_status"] == "UNSAT" and hyp02_replay["replayed_status"] == "UNSAT",
        "hyp02_unsat_core_roundtrips": hyp02_replay["emitted_unsat_core"] == hyp02_replay["replayed_unsat_core"],
        "hyp02_core_links_resolve": set(hyp02_replay["emitted_unsat_core"]) == set(hyp02_replay["core_hypothesis_links"]),
        "hyp05_every_emitted_composition_replays_sat": all(
            replay["status"] == "SAT"
            for case in hyp05_replays
            for replay in case["composition_replays"]
        ),
        "hyp05_only_requested_compositions_materialized": all(
            case["validation"]["no_unrequested_combinations_materialized"]
            and case["factorized"]["requested_composition_count"] == len(replay["composition_replays"])
            for case, replay in zip(hyp05, hyp05_replays)
        ),
        "graph03_cartesian_product_not_materialized": hyp05_summary["graph03_materialized_combinations"] == 0,
        "ret03_integrated_constraints_sat": ret03_match["final_constraints"] == "SAT",
        "ret03_integrated_links_preserved": all(ret03_match["cross_stage_entity_links"].values()),
    }
    assert all(validations.values()), validations
    result = {"cases": cases, "integrated_contract_consumers": integrated_contract_consumers, "validations": validations}
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for name, case in cases.items():
        if "smt2" in case:
            (OUT / f"{name}.smt2").write_text(case["smt2"])
    summary = {
        "statuses": {name: case.get("status", case.get("initial_status")) for name, case in cases.items()},
        "unsat_core": cases["contradictory"]["unsat_core"], "enumerated_models": cases["underspecified"]["model_count"],
        "unknown_reason": cases["resource_limited"]["reason_unknown"], "verdict": "GO_Z3_RESULT_CONTRACT",
        "integrated_hyp02_status": hyp02_replay["replayed_status"],
        "integrated_hyp05_replayed_compositions": sum(len(case["composition_replays"]) for case in hyp05_replays),
        "integrated_ret03_status": ret03_match["final_constraints"],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "z3_solver": importlib.metadata.version("z3-solver"), "unknown_rlimit": 1,
        "model_enumeration": "blocking clause over every requested binding",
    }, indent=2) + "\n")
    print("CONS-01: SAT/UNSAT/UNKNOWN + 6 models + unsat core; GO")


if __name__ == "__main__":
    main()
