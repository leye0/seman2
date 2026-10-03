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
from seman2_runtime.state_transformations import execute_state_transformation_epoch


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for child in OUT.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    database = OUT / "runtime.sqlite"
    epoch_zero = execute_epoch(ROOT, database)
    assert all(epoch_zero["validations"].values()), epoch_zero["validations"]
    epoch_one = execute_answer_epoch(ROOT, database)
    assert all(epoch_one["validations"].values()), epoch_one["validations"]
    result = execute_state_transformation_epoch(ROOT, database)
    assert all(result["validations"].values()), result["validations"]
    assert result["runtime_metrics_before"]["artifacts"] == 147
    assert result["runtime_metrics_after"]["artifacts"] == 165
    assert result["runtime_metrics_after"]["events"] == 165
    assert len(result["operator_decisions"]) == 3

    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps({
        "independent_contexts": len(result["operator_decisions"]),
        "epochs": result["runtime_metrics_after"]["epochs"],
        "artifacts": result["runtime_metrics_after"]["artifacts"],
        "events": result["runtime_metrics_after"]["events"],
        "selected_kind": "attach-answer-candidate",
        "answer_truth_asserted": False,
        "verdict": "GO_SOAR_OPERATOR_STATE_TRANSFORMATIONS",
    }, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "runtime_plan": "plans/runtime_service_graph.json",
        "epochs": [0, 1, 2],
        "soar_context_policy": "one independent operator context per conversation",
        "selection_evidence": ["direct source link", "parsed MRS content"],
    }, indent=2) + "\n")
    print("RUN-04: 3 Soar operator selections -> epoch 2 -> 165 artifacts/events; GO")


if __name__ == "__main__":
    main()
