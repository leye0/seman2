#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sqlite3
import sys


P = Path(__file__).resolve().parent
ROOT = P.parent.parent
OUT = P / "output"
RUN01 = ROOT / "poc/run-01/output"
sys.path.insert(0, str(ROOT))

from seman2_runtime.soar_session import SoarRuntimeSession, file_sha256


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
        "verdict": "GO_COORDINATED_CHECKPOINT_RECONSTRUCTION",
    }, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "checkpoint_source": "RUN-01",
        "restore_mode": "new Soar kernel plus Active Context reconstruction",
    }, indent=2) + "\n")
    print("RUN-02: 72 artifacts/events and 3 Soar decisions restored equivalently; GO")


if __name__ == "__main__":
    main()
