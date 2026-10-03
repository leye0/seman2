#!/usr/bin/env python3
"""CONS-01: Z3 solver result contract, models, alternatives and cores."""
from __future__ import annotations

import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import z3

P = Path(__file__).resolve().parent
OUT = P / "output"


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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {"satisfiable": sat_case(), "contradictory": unsat_case(), "underspecified": enumerate_models(), "resource_limited": unknown_case()}
    validations = {
        "sat_status_and_bindings": cases["satisfiable"]["status"] == "SAT" and len(cases["satisfiable"]["bindings"]) == 4,
        "unsat_status": cases["contradictory"]["status"] == "UNSAT",
        "minimal_relevant_core": cases["contradictory"]["unsat_core"] == ["maximum_10", "minimum_20"],
        "all_underspecified_models_enumerated": cases["underspecified"]["model_count"] == 6 and len({tuple(m.values()) for m in cases["underspecified"]["models"]}) == 6,
        "alternate_model_is_distinct": cases["underspecified"]["alternate_model"] != cases["underspecified"]["models"][0],
        "unknown_with_reason": cases["resource_limited"]["status"] == "UNKNOWN" and bool(cases["resource_limited"]["reason_unknown"]),
    }
    assert all(validations.values()), validations
    result = {"cases": cases, "validations": validations}
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for name, case in cases.items():
        if "smt2" in case:
            (OUT / f"{name}.smt2").write_text(case["smt2"])
    summary = {
        "statuses": {name: case.get("status", case.get("initial_status")) for name, case in cases.items()},
        "unsat_core": cases["contradictory"]["unsat_core"], "enumerated_models": cases["underspecified"]["model_count"],
        "unknown_reason": cases["resource_limited"]["reason_unknown"], "verdict": "GO_Z3_RESULT_CONTRACT",
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
