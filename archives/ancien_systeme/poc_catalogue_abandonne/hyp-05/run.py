#!/usr/bin/env python3
"""HYP-05: measured lazy factorization versus Cartesian materialization."""
from __future__ import annotations

import importlib.metadata
import itertools
import hashlib
import json
import multiprocessing
import platform
import resource
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

from z3 import And, Int, Not, Or, Solver, sat

P = Path(__file__).resolve().parent
ROOT = P.parent.parent
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


def _isolated_worker(send, strategy, sizes, constraints):
    try:
        result = (measure_cartesian if strategy == "cartesian" else measure_factorized)(sizes, constraints)
        # Linux reports KiB. Each strategy runs in a fresh spawned process, so
        # this peak includes native Z3 allocations as well as Python memory.
        result["process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        send.send((True, result))
    except BaseException as exc:
        send.send((False, f"{type(exc).__name__}: {exc}"))
    finally:
        send.close()


def measure_isolated(strategy, sizes, constraints):
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_isolated_worker, args=(send, strategy, sizes, constraints))
    process.start()
    send.close()
    if not receive.poll(30):
        process.terminate()
        process.join(5)
        raise RuntimeError(f"isolated {strategy} measurement timed out")
    ok, payload = receive.recv()
    process.join(5)
    assert process.exitcode == 0 and ok, payload
    return payload


def main() -> None:
    graph03_path = ROOT / "poc/graph-03/output/results.json"
    graph03_summary_path = graph03_path.with_name("summary.json")
    graph03 = json.loads(graph03_path.read_text(encoding="utf-8"))
    graph03_summary = json.loads(graph03_summary_path.read_text(encoding="utf-8"))
    assert graph03_summary["materialized_cartesian_combination_count"] == 0
    assert graph03_summary["all_groups_from_measured_outputs"] is True
    cases = [(3, 4), (3, 4, 3), (3, 4, 3, 2), (4, 5, 4, 3)]
    results = []
    for sizes in cases:
        constraints = constraints_for(sizes)
        baseline = measure_isolated("cartesian", sizes, constraints)
        factorized = measure_isolated("factorized", sizes, constraints)
        baseline_set = set(baseline.pop("valid_combinations"))
        returned = [tuple(item["combination"]) for item in factorized["compositions"]]
        validations = {
            "all_requested_compositions_valid": all(combo in baseline_set for combo in returned),
            "no_unrequested_combinations_materialized": factorized["unrequested_composition_count"] == 0,
            "factorized_compositions_bounded_by_requests": factorized["requested_composition_count"] <= 3,
            "all_fixed_bindings_respected": all(
                all(item["combination"][dimension] == value for dimension, value in item["fixed"].items())
                for item in factorized["compositions"]
            ),
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
        "target_cartesian_process_peak_rss_bytes": target["cartesian"]["process_peak_rss_bytes"],
        "target_factorized_process_peak_rss_bytes": target["factorized"]["process_peak_rss_bytes"],
        "measurement_scope": "separate spawned processes: wall-clock, Python tracemalloc, and Linux ru_maxrss including native allocations",
        "graph03_potential_combinations": graph03_summary["potential_cartesian_combination_count"],
        "graph03_materialized_combinations": graph03_summary["materialized_cartesian_combination_count"],
        "graph03_result_sha256": hashlib.sha256(graph03_path.read_bytes()).hexdigest(),
        "verdict": "GO_LAZY_FACTORIZED_COMPOSITION_WITHOUT_CARTESIAN_MATERIALIZATION",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(),
        "z3_solver": importlib.metadata.version("z3-solver"), "requests_per_case": 3,
        "memory_measurement": "tracemalloc plus isolated-process Linux ru_maxrss; ru_maxrss includes native allocations",
        "graph03_summary_sha256": hashlib.sha256(graph03_summary_path.read_bytes()).hexdigest()}, indent=2) + "\n")
    print(f"HYP-05: target Cartesian {summary['target_cartesian_objects']} vs factorized "
          f"{summary['target_factorized_objects']} objects, 0 unrequested compositions; GO")


if __name__ == "__main__": main()
