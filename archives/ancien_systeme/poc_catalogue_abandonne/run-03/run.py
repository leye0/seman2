#!/usr/bin/env python3
"""RUN-03: real question/answer ingestion through the cognitive runtime."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from seman2_runtime.cognitive_formal_analysis import FormalAnalysisPolicy, build_formal_runtime
from seman2_runtime.cognitive_ingestion import IngestionPolicy, records_from_sample_set
from seman2_runtime.cognitive_ingestion_session import CognitiveIngestionSession
from seman2_runtime.contracts import Envelope
from seman2_runtime.corpus import CorpusSamplingService, sampling_request


POC = Path(__file__).resolve().parent
ROOT = POC.parent.parent
OUTPUT = POC / "output"


def write_json(name: str, value) -> None:
    path = OUTPUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    sampled = CorpusSamplingService(ROOT).handle(sampling_request("run-03"))
    viable = [row for row in sampled.payload["samples"] if row["answers"]]
    selected = min(
        viable,
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
    restricted_sample = {**selected, "answers": [answer]}
    restricted = Envelope(
        kind="corpus-sample-set",
        message_id="run-03:curriculum-selection",
        correlation_id="run-03",
        producer="run-03-curriculum",
        parent_ids=(sampled.message_id,),
        payload={"samples": [restricted_sample]},
        provenance=(sampled.sha256,),
        losses=("two-turn-curriculum-projection",),
    )
    policy = IngestionPolicy(max_records=2, max_text_chars=5_000)
    records = records_from_sample_set(restricted, policy=policy)
    assert len(records) == 2
    assert [row.speaker_role for row in records] == ["initiator", "respondent"]
    assert [row.turn_index for row in records] == [0, 1]
    assert all(row.native_structure["raw_html_preserved"] for row in records)

    formal = FormalAnalysisPolicy(max_units_per_observation=1)
    baseline_runtime = build_formal_runtime(ROOT, ingestion_policy=policy, formal_policy=formal)
    baseline = CognitiveIngestionSession(
        runtime=baseline_runtime,
        records=records,
        policy=policy,
        session_id="run-03:real-thread",
    )
    assert baseline.run() == 2 and baseline.complete

    interrupted_runtime = build_formal_runtime(ROOT, ingestion_policy=policy, formal_policy=formal)
    interrupted = CognitiveIngestionSession(
        runtime=interrupted_runtime,
        records=records,
        policy=policy,
        session_id="run-03:real-thread",
    )
    assert interrupted.run(max_records=1) == 1
    with tempfile.TemporaryDirectory(prefix="seman2-run-03-") as directory:
        checkpoint_path = Path(directory) / "session.json"
        interrupted.checkpoint(checkpoint_path)
        checkpoint_bytes = checkpoint_path.read_bytes()
        resumed = CognitiveIngestionSession.restore(
            checkpoint_path,
            records=records,
            registry=interrupted_runtime.registry,
            modules=interrupted_runtime.modules,
        )
        assert resumed.next_record_index == 1
        assert resumed.run() == 1 and resumed.complete

    baseline_arena = baseline.runtime.arena.as_dict()
    resumed_arena = resumed.runtime.arena.as_dict()
    if resumed_arena != baseline_arena:
        baseline_by_id = {
            row["artifact_id"]: row for row in baseline_arena["artifacts"]
        }
        resumed_by_id = {
            row["artifact_id"]: row for row in resumed_arena["artifacts"]
        }
        identifiers = sorted(set(baseline_by_id) | set(resumed_by_id))
        first = next(
            identifier
            for identifier in identifiers
            if baseline_by_id.get(identifier) != resumed_by_id.get(identifier)
        )
        raise AssertionError(
            "arena diverged at "
            + first
            + "\nbaseline="
            + json.dumps(baseline_by_id.get(first), ensure_ascii=False, sort_keys=True)
            + "\nresumed="
            + json.dumps(resumed_by_id.get(first), ensure_ascii=False, sort_keys=True)
        )
    assert resumed.runtime.scheduler.as_dict() == baseline.runtime.scheduler.as_dict()
    arena = resumed.runtime.arena
    consolidations = arena.query(artifact_type="memory-consolidation-state")
    assert len(consolidations) == 2
    final_ancestry = arena.ancestry(consolidations[-1].artifact_id)
    source_rows = [row for row in final_ancestry if row.artifact_type == "source-record"]
    assert len(source_rows) == 2
    assert {row.payload_native["speaker_role"] for row in source_rows} == {
        "initiator",
        "respondent",
    }
    cognitive_json = json.dumps(arena.as_dict(), ensure_ascii=False)
    assert not any(
        token in cognitive_json
        for token in ("native_vote_score", "accepted_answer", "sampling_rank")
    )
    retrievals = arena.query(artifact_type="retrieval-index-entry")
    assert all(
        row.payload_projection["source_corpus_query_performed"] is False
        for row in retrievals
    )
    module_counts = Counter(
        result["module_id"]
        for frontier in resumed.runtime.scheduler.trace
        for result in frontier["results"]
    )
    required_modules = {
        "observation-normalizer",
        "erg-worker",
        "lexical-resource-worker",
        "cross-representation-linker",
        "constraint-engine",
        "soar-control",
        "formal-discourse-system",
        "formal-dialogue-system",
        "situation-episode-system",
        "statistics-system",
        "induction-engine",
        "cultural-concept-system",
        "candidate-transformation-system",
        "soar-transformation-control",
        "ingestion-state-consolidator",
    }
    assert required_modules <= set(module_counts)

    result = {
        "selected_source": {
            "sample_id": selected["sample_id"],
            "question_id": selected["question_id"],
            "answer_id": answer["answer_id"],
            "question_canonical_file": selected["canonical_file"],
            "answer_canonical_file": answer["canonical_file"],
        },
        "records": [
            {
                "record_id": row.record_id,
                "turn_index": row.turn_index,
                "speaker_role": row.speaker_role,
                "source_kind": row.source_kind,
                "raw_html_preserved": row.native_structure["raw_html_preserved"],
            }
            for row in records
        ],
        "artifact_counts": dict(sorted(Counter(row.artifact_type for row in arena.query()).items())),
        "participating_modules": dict(sorted(module_counts.items())),
        "final_ancestry_source_records": len(source_rows),
        "checkpoint_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
        "checkpoint_resume_equivalent": True,
        "retrieval_queried_corpus": False,
        "corpus_labels_in_cognition": False,
    }
    summary = {
        "real_source": "Stack Overflow canonical Parquet",
        "turn_count": 2,
        "artifact_count": len(arena),
        "participating_module_count": len(module_counts),
        "checkpoint_resume_equivalent": True,
        "final_state_depends_on_both_turns": True,
        "corpus_labels_in_cognition": False,
        "verdict": "GO_BOTTOM_UP_INTER_EPOCH_INGESTION",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json("results.json", result)
    write_json("summary.json", summary)
    write_json(
        "versions-and-parameters.json",
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sampling_memory_limit": sampled.payload["sampling_policy"]["memory_limit"],
            "sampling_threads": sampled.payload["sampling_policy"]["threads"],
            "max_units_per_observation": 1,
            "worker_limit": resumed.runtime.control.limits.max_worker_count,
        },
    )
    print("RUN-03: real question then answer; full bottom-up flow; checkpoint/resume equivalent; GO")


if __name__ == "__main__":
    main()
