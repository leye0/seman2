#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import shutil
import sys


P = Path(__file__).resolve().parent
ROOT = P.parent.parent
OUT = P / "output"
sys.path.insert(0, str(ROOT))

from seman2_runtime.multi_epoch import execute_answer_epoch
from seman2_runtime.runtime_bootstrap import execute_epoch


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    database = OUT / "runtime.sqlite"
    for path in (
        database,
        database.with_name("runtime.sqlite-wal"),
        database.with_name("runtime.sqlite-shm"),
    ):
        if path.exists():
            path.unlink()
    for name in ("checkpoint-epoch-0", "checkpoint-epoch-1"):
        path = OUT / name
        if path.exists():
            shutil.rmtree(path)

    epoch_zero = execute_epoch(ROOT, database)
    assert all(epoch_zero["validations"].values()), epoch_zero["validations"]
    result = execute_answer_epoch(ROOT, database)
    validations = result["validations"]
    assert all(validations.values()), validations
    assert result["runtime_metrics_before"]["artifacts"] == 72
    assert result["runtime_metrics_after"]["artifacts"] == 147
    assert result["runtime_metrics_after"]["events"] == 147
    assert len(result["soar_decisions"]) == 3
    assert all(row["next_action"] == "assess-answer" for row in result["soar_decisions"])

    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps({
        "source_questions": epoch_zero["source_questions"],
        "real_answers_processed": len(result["selected_answers"]),
        "epochs": result["runtime_metrics_after"]["epochs"],
        "artifacts": result["runtime_metrics_after"]["artifacts"],
        "events": result["runtime_metrics_after"]["events"],
        "soar_answer_decisions": len(result["soar_decisions"]),
        "checkpoint_decision_equivalence": result["checkpoint"]["soar"]["decision_equivalence"],
        "verdict": "GO_QUESTION_ANSWER_MULTI_EPOCH_RUNTIME",
    }, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "runtime_plan": "plans/runtime_service_graph.json",
        "epochs": [0, 1],
        "source": "canonical Stack Overflow Parquet",
        "answer_policy": "highest native vote, then source order",
        "analysis_unit": "first sentence, max 400 characters",
        "memory_policy": "DuckDB 256MB, one thread, bounded three-answer batch",
    }, indent=2) + "\n")
    print(
        "RUN-03: 3 real answers -> epoch 1 -> 147 durable artifacts/events "
        "-> 3 assess-answer decisions; GO"
    )


if __name__ == "__main__":
    main()
