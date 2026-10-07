#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import platform
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "poc/core-03/output"
CHECKPOINT = OUTPUT / "developmental-session.json"


def write_json(name: str, payload: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def execute(*extra: str) -> dict:
    command = [
        sys.executable,
        "-m",
        "seman2_runtime.developmental_ingestion_cli",
        "--input",
        "data/the_map_of_everything_nlp_novel.txt",
        "--max-records",
        "2",
        "--max-units-per-observation",
        "1",
        *extra,
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"commande échouée ({completed.returncode}): {completed.stdout}")
    return json.loads(completed.stdout.strip().splitlines()[-1])


def main() -> int:
    interrupted = execute(
        "--max-this-run", "1", "--checkpoint", str(CHECKPOINT)
    )
    resumed = execute("--resume", "--checkpoint", str(CHECKPOINT))
    continuous = execute()

    checks = {
        "interrupted_is_incomplete": interrupted["complete"] is False,
        "interrupted_cursor": interrupted["next_record_index"] == 1,
        "resumed_is_complete": resumed["complete"] is True,
        "resumed_cursor": resumed["next_record_index"] == 2,
        "continuous_is_complete": continuous["complete"] is True,
        "all_semantics_adapted": not resumed["unadapted_semantic_refs"]
        and not continuous["unadapted_semantic_refs"],
        "no_pending_tasks": resumed["pending_analysis_tasks"] == 0
        and continuous["pending_analysis_tasks"] == 0,
        "same_core": resumed["developmental_core_sha256"]
        == continuous["developmental_core_sha256"],
        "same_analysis_arena": resumed["analysis_arena_sha256"]
        == continuous["analysis_arena_sha256"],
        "same_relation_count": resumed["relations"] == continuous["relations"],
        "same_form_count": resumed["distributed_forms"]
        == continuous["distributed_forms"],
        "no_high_level_raw_read": not resumed["raw_source_queried_by_high_level"]
        and not continuous["raw_source_queried_by_high_level"],
        "no_truth_commit": not resumed["analysis_candidates_committed_as_truth"]
        and not continuous["analysis_candidates_committed_as_truth"],
    }
    verdict = (
        "GO-DEVELOPMENTAL-INGESTION-EXACT-RESUME"
        if all(checks.values())
        else "NO-GO-DEVELOPMENTAL-INGESTION-RESUME"
    )
    results = {
        "verdict": verdict,
        "checks": checks,
        "interrupted": interrupted,
        "resumed": resumed,
        "continuous": continuous,
    }
    write_json("results.json", results)
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "records": 2,
            "maximum_units_per_observation": 1,
            "maximum_workers": 4,
            "rst_model_loaded": False,
            "command": "seman2_runtime.developmental_ingestion_cli",
        },
    )
    write_json(
        "summary.json",
        {
            "verdict": verdict,
            "checks_passed": sum(checks.values()),
            "checks_total": len(checks),
            "relations": resumed["relations"],
            "distributed_forms": resumed["distributed_forms"],
        },
    )
    print(json.dumps(results, ensure_ascii=False))
    if verdict.startswith("NO-GO"):
        raise AssertionError(verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
