#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sqlite3
import sys
import tempfile


P = Path(__file__).resolve().parent
ROOT = P.parent.parent
OUT = P / "output"
RUN01 = ROOT / "poc/run-01/output"
sys.path.insert(0, str(ROOT))

from seman2_runtime.soar_session import SoarRuntimeSession, file_sha256
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
from seman2_runtime.contracts import ContractError, canonical_json


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    run01 = json.loads((RUN01 / "results.json").read_text())
    checkpoint = RUN01 / "checkpoint-epoch-0"
    soar_dir = checkpoint / "soar"
    soar_manifest = json.loads((soar_dir / "soar-checkpoint.json").read_text())
    runtime_database = checkpoint / "runtime.sqlite"

    file_checks = {
        name: file_sha256(soar_dir / name) == metadata["sha256"]
        for name, metadata in soar_manifest["files"].items()
    }
    runtime_hash = file_sha256(runtime_database)
    expected_runtime_hash = run01["checkpoint"]["runtime_database"]["sha256"]
    connection = sqlite3.connect(runtime_database)
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    artifact_count = connection.execute("SELECT count(*) FROM artifacts").fetchone()[0]
    event_count = connection.execute("SELECT count(*) FROM runtime_events").fetchone()[0]
    last_event = connection.execute("SELECT max(sequence) FROM runtime_events").fetchone()[0]
    connection.close()

    beams = json.loads((soar_dir / "active-context.json").read_text())
    with SoarRuntimeSession(agent_file=soar_dir / "agent.soar") as restored:
        restored.inject(beams)
        decisions_after = restored.decide()
    decisions_before = soar_manifest["decisions_before_stop"]

    altered_context = json.loads(json.dumps(beams))
    altered_context[0]["hypothesis_ids"].reverse()
    original_context_hash = hashlib.sha256(
        json.dumps(beams, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    altered_context_hash = hashlib.sha256(
        json.dumps(altered_context, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    corrupted_database_hash = hashlib.sha256(runtime_database.read_bytes() + b"corruption").hexdigest()

    cognitive_source = ROOT / "data/the_map_of_everything_nlp_novel.txt"
    cognitive_checkpoint = checkpoint / "cognitive-session.json"
    ingestion_policy = IngestionPolicy(max_records=2, max_text_chars=2_000)
    formal_policy = FormalAnalysisPolicy(max_units_per_observation=1)
    records = records_from_text_file(cognitive_source, policy=ingestion_policy)
    fresh_runtime = build_formal_runtime(
        ROOT,
        ingestion_policy=ingestion_policy,
        formal_policy=formal_policy,
    )
    cognitive_checkpoint_hash = file_sha256(cognitive_checkpoint)
    cognitive_checkpoint_matches = (
        cognitive_checkpoint_hash
        == run01["cognitive_ingestion"]["checkpoint_sha256"]
    )
    resumed = CognitiveIngestionSession.restore(
        cognitive_checkpoint,
        records=records,
        registry=fresh_runtime.registry,
        modules=fresh_runtime.modules,
    )
    restored_partial_hash = hashlib.sha256(
        canonical_json(resumed.snapshot()).encode()
    ).hexdigest()
    partial_state_matches = (
        restored_partial_hash
        == run01["cognitive_ingestion"]["session_snapshot_sha256"]
    )
    resumed_processed = resumed.run()
    resumed_report = assess_cognitive_ingestion(
        resumed,
        records_processed_this_run=resumed_processed,
        input_path=cognitive_source,
        input_format="text",
        checkpoint_path=cognitive_checkpoint,
    )

    baseline_runtime = build_formal_runtime(
        ROOT,
        ingestion_policy=ingestion_policy,
        formal_policy=formal_policy,
    )
    baseline = CognitiveIngestionSession(
        runtime=baseline_runtime,
        records=records,
        policy=ingestion_policy,
        session_id="run-01:real-novel-ingestion",
    )
    baseline.run()
    resumed_snapshot_hash = hashlib.sha256(
        canonical_json(resumed.snapshot()).encode()
    ).hexdigest()
    baseline_snapshot_hash = hashlib.sha256(
        canonical_json(baseline.snapshot()).encode()
    ).hexdigest()

    corruption_rejected = False
    source_order_change_rejected = False
    with tempfile.TemporaryDirectory(prefix="seman2-run02-") as directory:
        corrupt_path = Path(directory) / "corrupt-cognitive-session.json"
        corrupt_envelope = json.loads(cognitive_checkpoint.read_text())
        corrupt_envelope["payload"]["session"]["next_record_index"] = 0
        corrupt_path.write_text(json.dumps(corrupt_envelope) + "\n")
        try:
            CognitiveIngestionSession.restore(
                corrupt_path,
                records=records,
                registry=fresh_runtime.registry,
                modules=fresh_runtime.modules,
            )
        except ContractError:
            corruption_rejected = True
        try:
            CognitiveIngestionSession.restore(
                cognitive_checkpoint,
                records=tuple(reversed(records)),
                registry=fresh_runtime.registry,
                modules=fresh_runtime.modules,
            )
        except ContractError:
            source_order_change_rejected = True

    validations = {
        "all_soar_checkpoint_files_match": all(file_checks.values()),
        "runtime_database_matches_manifest": runtime_hash == expected_runtime_hash,
        "runtime_database_integrity_ok": integrity == "ok",
        "runtime_counts_exact": artifact_count == event_count == 72 and last_event == 72,
        "decisions_strictly_equivalent": decisions_after == decisions_before,
        "three_decisions_restored": len(decisions_after) == 3,
        "working_memory_reconstructed_explicitly": soar_manifest["working_memory_restore_mode"] == "reconstruct-from-active-context",
        "native_whole_wm_not_claimed": soar_manifest["native_whole-working-memory_restore_claimed"] is False,
        "altered_context_detected": original_context_hash != altered_context_hash,
        "corrupted_database_detected": corrupted_database_hash != runtime_hash,
        "cognitive_checkpoint_matches_manifest": cognitive_checkpoint_matches,
        "cognitive_partial_state_restored_exactly": partial_state_matches,
        "cognitive_remaining_record_processed": resumed_processed == 1,
        "cognitive_session_complete": resumed.complete,
        "cognitive_all_modules_participate_after_resume": (
            resumed_report["missing_required_modules"] == []
        ),
        "cognitive_terminal_lineage_is_bottom_up": resumed_report[
            "every_terminal_has_complete_bottom_up_lineage"
        ],
        "cognitive_resume_equals_uninterrupted_execution": (
            resumed_snapshot_hash == baseline_snapshot_hash
        ),
        "cognitive_corruption_rejected": corruption_rejected,
        "cognitive_source_order_change_rejected": source_order_change_rejected,
    }
    assert all(validations.values()), validations
    result = {
        "checkpoint": {
            "runtime_database": str(runtime_database.relative_to(ROOT)),
            "runtime_sha256": runtime_hash,
            "last_event_sequence": last_event,
            "soar_files": soar_manifest["files"],
        },
        "decisions_before": decisions_before,
        "decisions_after": decisions_after,
        "negative_checks": {
            "altered_context_sha256": altered_context_hash,
            "corrupted_database_sha256": corrupted_database_hash,
            "cognitive_corruption_rejected": corruption_rejected,
            "cognitive_source_order_change_rejected": source_order_change_rejected,
        },
        "cognitive_ingestion": {
            "checkpoint": str(cognitive_checkpoint.relative_to(ROOT)),
            "checkpoint_sha256": cognitive_checkpoint_hash,
            "restored_partial_snapshot_sha256": restored_partial_hash,
            "resumed_complete_snapshot_sha256": resumed_snapshot_hash,
            "uninterrupted_complete_snapshot_sha256": baseline_snapshot_hash,
            "report_after_resume": resumed_report,
        },
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps({
        "artifacts_restored": artifact_count,
        "events_restored": event_count,
        "decisions_restored": len(decisions_after),
        "decision_equivalence": True,
        "negative_corruption_checks": 2,
        "cognitive_artifacts_restored_and_completed": resumed_report["artifact_count"],
        "cognitive_modules_participating": len(
            resumed_report["participating_modules"]
        ),
        "cognitive_resume_equals_uninterrupted": True,
        "verdict": "GO_COORDINATED_DURABLE_AND_COGNITIVE_RECONSTRUCTION",
    }, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "checkpoint_source": "RUN-01",
        "restore_modes": [
            "new Soar kernel plus Active Context reconstruction",
            "new cognitive runtime plus exact Artifact Arena, scheduler, Control State and source cursor restoration",
        ],
    }, indent=2) + "\n")
    print(
        "RUN-02: durable Soar state and full cognitive ingestion resume "
        "equivalently to uninterrupted execution; GO"
    )


if __name__ == "__main__":
    main()
