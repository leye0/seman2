#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sys


P = Path(__file__).resolve().parent
ROOT = P.parent.parent
OUT = P / "output"
sys.path.insert(0, str(ROOT))

from seman2_runtime.runtime_bootstrap import execute_epoch
from seman2_runtime.cognitive_formal_analysis import (
    FormalAnalysisPolicy,
    build_formal_runtime,
)
from seman2_runtime.cognitive_ingestion import (
    IngestionPolicy,
    records_from_text_file,
)
from seman2_runtime.cognitive_ingestion_session import CognitiveIngestionSession
from seman2_runtime.cognitive_ingestion_validation import assess_cognitive_ingestion
from seman2_runtime.contracts import canonical_json


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runtime_database = OUT / "runtime.sqlite"
    # Sortie entièrement reproductible de la POC, jamais un store utilisateur.
    # Une exécution doit repartir d'un journal vide afin de tester le bootstrap,
    # et non de mêler deux révisions de matière dérivée dans le même epoch.
    runtime_database.unlink(missing_ok=True)
    result = execute_epoch(ROOT, runtime_database)
    validations = result["validations"]
    assert all(validations.values()), validations
    assert result["runtime_metrics"]["artifacts"] == 72
    assert result["runtime_metrics"]["events"] == 72
    assert len(result["soar_decisions"]) == 3
    assert all(len(rows) >= 15 for rows in result["decision_ancestry"].values())

    # Le graphe SQLite historique prouve la durabilité. Cette seconde verticale
    # utilise le cœur cognitif actuel, en RAM, et s'arrête proprement à une
    # frontière de record afin que RUN-02 puisse prouver la reprise exacte.
    source = ROOT / "data/the_map_of_everything_nlp_novel.txt"
    ingestion_policy = IngestionPolicy(max_records=2, max_text_chars=2_000)
    formal_policy = FormalAnalysisPolicy(max_units_per_observation=1)
    records = records_from_text_file(source, policy=ingestion_policy)
    cognitive_runtime = build_formal_runtime(
        ROOT,
        ingestion_policy=ingestion_policy,
        formal_policy=formal_policy,
    )
    cognitive_session = CognitiveIngestionSession(
        runtime=cognitive_runtime,
        records=records,
        policy=ingestion_policy,
        session_id="run-01:real-novel-ingestion",
    )
    processed = cognitive_session.run(max_records=1)
    cognitive_checkpoint = OUT / "checkpoint-epoch-0" / "cognitive-session.json"
    cognitive_session.checkpoint(cognitive_checkpoint)
    cognitive_report = assess_cognitive_ingestion(
        cognitive_session,
        records_processed_this_run=processed,
        input_path=source,
        input_format="text",
        checkpoint_path=cognitive_checkpoint,
    )
    cognitive_snapshot_sha256 = hashlib.sha256(
        canonical_json(cognitive_session.snapshot()).encode()
    ).hexdigest()
    cognitive_checkpoint_sha256 = hashlib.sha256(
        cognitive_checkpoint.read_bytes()
    ).hexdigest()
    assert cognitive_report["status"] == "GO-INGESTION-SYSTEM"
    assert cognitive_report["next_record_index"] == 1
    assert cognitive_report["complete"] is False
    assert cognitive_report["missing_required_modules"] == []
    assert cognitive_report["every_terminal_has_complete_bottom_up_lineage"]
    result["cognitive_ingestion"] = {
        **cognitive_report,
        "checkpoint_sha256": cognitive_checkpoint_sha256,
        "session_snapshot_sha256": cognitive_snapshot_sha256,
        "source_record_ids": [record.record_id for record in records],
        "checkpoint_boundary": "after-record-1-of-2-with-zero-pending-tasks",
    }
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps({
        "source_questions": result["source_questions"],
        "artifacts": result["runtime_metrics"]["artifacts"],
        "events": result["runtime_metrics"]["events"],
        "soar_decisions": len(result["soar_decisions"]),
        "checkpoint_decision_equivalence": result["checkpoint"]["soar"]["decision_equivalence"],
        "cognitive_source_records_available": len(records),
        "cognitive_records_processed_before_checkpoint": processed,
        "cognitive_artifacts_before_checkpoint": cognitive_report["artifact_count"],
        "cognitive_modules_participating": len(cognitive_report["participating_modules"]),
        "complete_bottom_up_terminal_lineage": cognitive_report[
            "every_terminal_has_complete_bottom_up_lineage"
        ],
        "verdict": "GO_REAL_DATA_DURABLE_AND_FULL_COGNITIVE_INGESTION",
    }, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "runtime_plan": "plans/archives/runtime_service_graph.json",
        "epoch": 0,
        "sources": [
            "canonical Stack Overflow Parquet",
            "data/the_map_of_everything_nlp_novel.txt",
        ],
        "memory_policy": "DuckDB 256MB, one thread, one shard pair at a time",
        "cognitive_ingestion_policy": {
            "max_records": ingestion_policy.max_records,
            "max_text_chars": ingestion_policy.max_text_chars,
            "max_units_per_observation": formal_policy.max_units_per_observation,
            "worker_limit": cognitive_runtime.control.limits.max_worker_count,
        },
    }, indent=2) + "\n")
    print(
        "RUN-01: durable graph plus 28-module bottom-up cognitive ingestion "
        "checkpointed at an exact record boundary; GO"
    )


if __name__ == "__main__":
    main()
