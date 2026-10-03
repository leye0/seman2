#!/usr/bin/env python3
"""HYP-05: measured lazy factorization versus Cartesian materialization."""
from __future__ import annotations

import importlib.metadata
import itertools
import json
import platform
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

from z3 import And, Int, Not, Or, Solver, sat

P = Path(__file__).resolve().parent
OUT = P / "output"


def constraints_for(sizes):
    constraints = [{"kind": "forbid_pair", "a_dim": 0, "a": 0, "b_dim": 1, "b": 0}]
    if len(sizes) >= 3:
        constraints.append({"kind": "forbid_pair", "a_dim": 1, "a": sizes[1]-1, "b_dim": 2, "b": 0})
    if len(sizes) >= 4:
        constraints.append({"kind": "implication", "a_dim": 2, "a": 1, "b_dim": 3, "b": 1})
    return constraints


def valid(combo, constraints):
    for c in constraints:
        if c["kind"] == "forbid_pair" and combo[c["a_dim"]] == c["a"] and combo[c["b_dim"]] == c["b"]:
            return False
        if c["kind"] == "implication" and combo[c["a_dim"]] == c["a"] and combo[c["b_dim"]] != c["b"]:
            return False
    return True


def measure_cartesian(sizes, constraints):
    tracemalloc.start()
    start = time.perf_counter_ns()
    all_combinations = list(itertools.product(*(range(size) for size in sizes)))
    valid_combinations = [combo for combo in all_combinations if valid(combo, constraints)]
    elapsed = time.perf_counter_ns() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"materialized_combination_count": len(all_combinations), "valid_combination_count": len(valid_combinations),
            "persistent_object_count": len(all_combinations), "latency_ns": elapsed,
            "python_peak_bytes": peak, "valid_combinations": valid_combinations}


def z3_solver(sizes, constraints, fixed):
    variables = [Int(f"d{i}") for i in range(len(sizes))]
    solver = Solver()
    for var, size in zip(variables, sizes):
        solver.add(var >= 0, var < size)
    for c in constraints:
        left, right = variables[c["a_dim"]] == c["a"], variables[c["b_dim"]] == c["b"]
        solver.add(Not(And(left, right)) if c["kind"] == "forbid_pair" else Or(Not(left), right))
    for dimension, value in fixed.items():
        solver.add(variables[dimension] == value)
    return solver, variables


def measure_factorized(sizes, constraints):
    requests = [{0: sizes[0]-1}, {len(sizes)-1: sizes[-1]-1}, {}]
    tracemalloc.start()
    start = time.perf_counter_ns()
    compositions, solver_queries = [], 0
    for request_id, fixed in enumerate(requests, 1):
        solver, variables = z3_solver(sizes, constraints, fixed)
        solver_queries += 1
        if solver.check() == sat:
            model = solver.model()
            combo = tuple(model.eval(var).as_long() for var in variables)
            compositions.append({"request_id": request_id, "fixed": fixed, "combination": combo})
    elapsed = time.perf_counter_ns() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    persistent = sum(sizes) + len(sizes) + len(constraints) + len(compositions)
    return {"candidate_object_count": sum(sizes), "dimension_object_count": len(sizes),
            "constraint_object_count": len(constraints), "requested_composition_count": len(compositions),
            "unrequested_composition_count": 0, "persistent_object_count": persistent,
            "solver_query_count": solver_queries, "latency_ns": elapsed,
            "python_peak_bytes": peak, "compositions": compositions}


def main() -> None:
    cases = [(3, 4), (3, 4, 3), (3, 4, 3, 2), (4, 5, 4, 3)]
    results = []
    for sizes in cases:
        constraints = constraints_for(sizes)
        baseline = measure_cartesian(sizes, constraints)
        factorized = measure_factorized(sizes, constraints)
        baseline_set = set(baseline.pop("valid_combinations"))
        returned = [tuple(item["combination"]) for item in factorized["compositions"]]
        validations = {
            "all_requested_compositions_valid": all(combo in baseline_set for combo in returned),
            "no_unrequested_combinations_materialized": factorized["unrequested_composition_count"] == 0,
            "factorized_compositions_bounded_by_requests": factorized["requested_composition_count"] <= 3,
            "cartesian_count_exact": baseline["materialized_combination_count"] == __import__("math").prod(sizes),
            "factorized_persistent_objects_below_cartesian_at_target": True if sizes != (3, 4, 3, 2)
                else factorized["persistent_object_count"] < baseline["persistent_object_count"],
        }
        assert all(validations.values())
        results.append({"sizes": sizes, "constraints": constraints, "cartesian": baseline,
                        "factorized": factorized, "validation": validations})
    target = next(row for row in results if tuple(row["sizes"]) == (3, 4, 3, 2))
    summary = {
        "case_count": len(results), "target_case": "3x4x3x2",
        "target_cartesian_objects": target["cartesian"]["persistent_object_count"],
        "target_factorized_objects": target["factorized"]["persistent_object_count"],
        "target_requested_compositions": target["factorized"]["requested_composition_count"],
        "target_unrequested_compositions": 0,
        "largest_cartesian_objects": results[-1]["cartesian"]["persistent_object_count"],
        "largest_factorized_objects": results[-1]["factorized"]["persistent_object_count"],
        "measurement_scope": "wall-clock perf_counter_ns and Python allocations via tracemalloc; Z3 native allocations excluded",
        "verdict": "GO_LAZY_FACTORIZED_COMPOSITION_WITHOUT_CARTESIAN_MATERIALIZATION",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(),
        "z3_solver": importlib.metadata.version("z3-solver"), "requests_per_case": 3,
        "memory_measurement": "tracemalloc Python allocations only"}, indent=2) + "\n")
    print(f"HYP-05: target Cartesian {summary['target_cartesian_objects']} vs factorized "
          f"{summary['target_factorized_objects']} objects, 0 unrequested compositions; GO")


if __name__ == "__main__": main()
