#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import sys


P = Path(__file__).resolve().parent
ROOT = P.parent.parent
OUT = P / "output"
sys.path.insert(0, str(ROOT))

from seman2_runtime.runtime_bootstrap import execute_epoch


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = execute_epoch(ROOT, OUT / "runtime.sqlite")
    validations = result["validations"]
    assert all(validations.values()), validations
    assert result["runtime_metrics"]["artifacts"] == 72
    assert result["runtime_metrics"]["events"] == 72
    assert len(result["soar_decisions"]) == 3
    assert all(len(rows) >= 15 for rows in result["decision_ancestry"].values())
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps({
        "source_questions": result["source_questions"],
        "artifacts": result["runtime_metrics"]["artifacts"],
        "events": result["runtime_metrics"]["events"],
        "soar_decisions": len(result["soar_decisions"]),
        "checkpoint_decision_equivalence": result["checkpoint"]["soar"]["decision_equivalence"],
        "verdict": "GO_REAL_DATA_DURABLE_RUNTIME_TO_SOAR",
    }, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "runtime_plan": "plans/runtime_service_graph.json",
        "epoch": 0,
        "source": "canonical Stack Overflow Parquet",
        "memory_policy": "DuckDB 256MB, one thread, one shard pair at a time",
    }, indent=2) + "\n")
    print("RUN-01: 3 real questions -> 72 durable artifacts/events -> 3 Soar decisions; GO")


if __name__ == "__main__":
    main()
