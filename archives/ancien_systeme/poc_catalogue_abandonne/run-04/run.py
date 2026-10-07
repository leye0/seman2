#!/usr/bin/env python3
"""RUN-04: select operational transformations built from emergent matter."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from seman2_runtime.cognitive_formal_analysis import FormalAnalysisPolicy, build_formal_runtime
from seman2_runtime.cognitive_ingestion import IngestionPolicy, records_from_sample_set
from seman2_runtime.cognitive_ingestion_session import CognitiveIngestionSession
from seman2_runtime.contracts import Envelope
from seman2_runtime.control_state import CognitiveParameters, ControlState, SafetyLimits
from seman2_runtime.corpus import CorpusSamplingService, sampling_request


POC = Path(__file__).resolve().parent
ROOT = POC.parent.parent
OUTPUT = POC / "output"


def write_json(name: str, value) -> None:
    path = OUTPUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    sampled = CorpusSamplingService(ROOT).handle(sampling_request("run-04"))
    selected = min(
        (row for row in sampled.payload["samples"] if row["answers"]),
        key=lambda row: (
            len(row["title"]),
            min(len(answer["text_projection"]) for answer in row["answers"]),
            row["question_id"],
        ),
    )
    answer = min(
        selected["answers"],
        key=lambda row: (len(row["text_projection"]), row["answer_id"]),
    )
    source = Envelope(
        kind="corpus-sample-set",
        message_id="run-04:curriculum-selection",
        correlation_id="run-04",
        producer="run-04-curriculum",
        parent_ids=(sampled.message_id,),
        payload={"samples": [{**selected, "answers": [answer]}]},
        provenance=(sampled.sha256,),
    )
    policy = IngestionPolicy(max_records=2, max_text_chars=5_000)
    records = records_from_sample_set(source, policy=policy)
    runtime = build_formal_runtime(
        ROOT,
        ingestion_policy=policy,
        formal_policy=FormalAnalysisPolicy(max_units_per_observation=1),
        control=ControlState(
            limits=SafetyLimits(max_worker_count=4),
            parameters=CognitiveParameters(induction_trigger=2),
        ),
    )
    session = CognitiveIngestionSession(
        runtime=runtime,
        records=records,
        policy=policy,
        session_id="run-04:real-thread",
    )
    assert session.run() == 2 and session.complete

    candidates = runtime.arena.query(artifact_type="state-transformation-candidate")
    decisions = runtime.arena.query(artifact_type="soar-transformation-decision")
    consolidations = runtime.arena.query(artifact_type="memory-consolidation-state")
    assert len(candidates) >= 4
    assert len(decisions) == 2 and len(consolidations) == 2
    assert all(row.payload_native["candidate_count"] >= 2 for row in decisions)
    assert all(row.payload_native["transformation_kind"] == "retain-episode" for row in decisions)
    assert all(row.payload_native["selection_is_operational"] for row in decisions)
    assert all(not row.payload_native["semantic_truth_selected"] for row in decisions)
    assert all(row.payload_native["applied"] for row in consolidations)
    assert all(not row.payload_native["truth_committed"] for row in consolidations)
    assert all(not row.payload_projection["uses_raw_source"] for row in candidates)
    assert all(not row.payload_projection["uses_corpus_label"] for row in candidates)

    final_types = {
        row.artifact_type
        for row in runtime.arena.ancestry(consolidations[-1].artifact_id)
    }
    required_ancestry = {
        "mrs-analysis",
        "lexical-analysis",
        "cross-representation-hypothesis",
        "semantic-structure",
        "temporal-constraint-network",
        "constraint-solution",
        "hypothesis-family",
        "soar-control-state",
        "discourse-state-candidate",
        "dialogue-state-candidate",
        "episode-candidate",
        "retrieval-index-entry",
        "statistics-snapshot",
        "induction-state",
        "cultural-learning-state",
        "state-transformation-candidate",
        "soar-transformation-decision",
    }
    assert required_ancestry <= final_types

    negative = subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "seman2_runtime/workers/soar_transformation_worker.py"),
        ],
        input=json.dumps(
            {
                "memory_limit_mib": 1_024,
                "candidates": [
                    {
                        "transformation_id": "negative:unsupported",
                        "kind": "unsupported-update",
                        "eligible": False,
                    }
                ],
            }
        ),
        text=True,
        capture_output=True,
        env=os.environ.copy(),
        timeout=20,
    )
    assert negative.returncode != 0
    assert "output absent" in negative.stderr.lower()

    selected_ids = {row.payload_native["selected_transformation_ref"] for row in decisions}
    candidate_ids = {row.artifact_id for row in candidates}
    assert selected_ids <= candidate_ids
    result = {
        "source": {
            "question_id": selected["question_id"],
            "answer_id": answer["answer_id"],
        },
        "candidate_count": len(candidates),
        "candidate_kinds": dict(Counter(row.payload_native["kind"] for row in candidates)),
        "decisions": [
            {
                "selected_transformation_ref": row.payload_native["selected_transformation_ref"],
                "kind": row.payload_native["transformation_kind"],
                "candidate_count": row.payload_native["candidate_count"],
                "semantic_truth_selected": row.payload_native["semantic_truth_selected"],
            }
            for row in decisions
        ],
        "consolidations": [
            {
                "episode_ref": row.payload_native["episode_ref"],
                "operation": row.payload_native["operation"],
                "applied": row.payload_native["applied"],
                "truth_committed": row.payload_native["truth_committed"],
            }
            for row in consolidations
        ],
        "final_ancestry_types": sorted(final_types),
        "negative_case": {
            "eligible_candidates": 0,
            "worker_returncode": negative.returncode,
            "default_choice_invented": False,
        },
    }
    summary = {
        "real_bottom_up_turns": 2,
        "transformation_candidates": len(candidates),
        "soar_decisions": len(decisions),
        "consolidations_applied": len(consolidations),
        "truth_commits": 0,
        "negative_impasse_verified": True,
        "verdict": "GO_OPERATIONAL_TRANSFORMATIONS_FROM_EMERGENT_MATTER",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json("results.json", result)
    write_json("summary.json", summary)
    write_json(
        "versions-and-parameters.json",
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input": "live bounded Stack Overflow Parquet sample",
            "induction_trigger": 2,
            "worker_limit": 4,
            "selection_engine": "Soar SML",
        },
    )
    print("RUN-04: competing operational transformations selected by Soar; unsupported case stays unresolved; GO")


if __name__ == "__main__":
    main()
