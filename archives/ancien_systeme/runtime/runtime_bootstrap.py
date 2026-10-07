"""Exécute une époque réelle du graphe durable jusqu'à Soar."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import Python_sml_ClientInterface as sml

from .contracts import ContractError
from .corpus_planning import run_corpus_planning
from .durable_runtime import DurableRuntimeStore, RuntimePlan
from .soar_session import checkpoint_and_verify


def by_kind(trace, kind: str):
    matches = [row for row in trace if row.kind == kind]
    if len(matches) != 1:
        raise ContractError(f"runtime bootstrap: attendu un message {kind}, trouvé {len(matches)}")
    return matches[0].payload


def execute_epoch(root: Path, database: Path) -> dict[str, Any]:
    _, trace = run_corpus_planning(root)
    samples = by_kind(trace, "corpus-sample-set")["samples"]
    observations = by_kind(trace, "observation-batch")["observations"]
    analyses = by_kind(trace, "analyzed-corpus-batch")["rows"]
    ledger = by_kind(trace, "analysis-ledger")["entries"]
    fragments = by_kind(trace, "semantic-fragment-batch")["fragments"]
    features = by_kind(trace, "semantic-feature-batch")["fragments"]
    hypotheses = by_kind(trace, "corpus-hypothesis-ledger")["hypotheses"]

    sample_by_id = {row["sample_id"]: row for row in samples}
    analyses_by_observation = {row["observation_id"]: row for row in analyses}
    ledger_by_key = {(row["observation_id"], row["producer"]): row for row in ledger}
    feature_by_id = {row["fragment_id"]: row for row in features}
    hypothesis_by_observation: dict[str, list[dict]] = {}
    for hypothesis in hypotheses:
        hypothesis_by_observation.setdefault(hypothesis["observation_id"], []).append(hypothesis)

    plan = RuntimePlan(root / "plans/archives/runtime_service_graph.json")
    beams_for_soar = []
    ancestry_targets = []
    with DurableRuntimeStore(database, plan) as store:
        for observation in observations:
            observation_id = observation["observation_id"]
            sample = sample_by_id[observation["sample_id"]]
            source_id = f"runtime-source:{sample['question_id']}"
            store.record_artifact(
                artifact_id=source_id,
                component_id="source-reader",
                kind="canonical-parquet-record",
                epoch=0,
                payload={
                    "sample_id": sample["sample_id"],
                    "canonical_file": sample["canonical_file"],
                    "source_file": sample["source_file"],
                    "source_position": sample["source_position"],
                    "source_record_id": sample["source_record_id"],
                    "raw_body_sha256": sample["raw_body_sha256"],
                    "title": sample["title"],
                    "answers": [
                        {
                            "answer_id": answer["answer_id"],
                            "raw_body_sha256": answer["raw_body_sha256"],
                            "canonical_file": answer["canonical_file"],
                        }
                        for answer in sample["answers"]
                    ],
                },
                parent_ids=(),
                idempotency_key=source_id,
            )
            store.record_artifact(
                artifact_id=observation_id,
                component_id="observation-ledger",
                kind="text-observation",
                epoch=0,
                payload=observation,
                parent_ids=(source_id,),
                idempotency_key=observation_id,
            )

            native_ids = {}
            representation_ids = {}
            for producer in ("ACE_ERG", "dynamicsyntax-python"):
                producer_slug = "erg" if producer == "ACE_ERG" else "dynamic-syntax"
                job_id = f"analysis-job:{producer_slug}:{observation_id}"
                native_id = f"native-analysis:{producer_slug}:{observation_id}"
                store.record_artifact(
                    artifact_id=job_id,
                    component_id="analysis-dispatch",
                    kind="analysis-request",
                    epoch=0,
                    payload={"observation_id": observation_id, "producer": producer},
                    parent_ids=(observation_id,),
                    idempotency_key=job_id,
                )
                entry = ledger_by_key[(observation_id, producer)]
                store.record_artifact(
                    artifact_id=native_id,
                    component_id="native-analysis-ledger",
                    kind="native-analysis-result",
                    epoch=0,
                    payload=entry,
                    parent_ids=(job_id,),
                    idempotency_key=native_id,
                )
                native_ids[producer] = native_id
                if producer == "dynamicsyntax-python":
                    representation_id = f"representation:dynamic-syntax:{observation_id}:failure"
                    store.record_artifact(
                        artifact_id=representation_id,
                        component_id="representation-adapters",
                        kind="attributed-analysis-failure",
                        epoch=0,
                        payload={
                            "observation_id": observation_id,
                            "producer": producer,
                            "status": entry["status"],
                            "failure_is_evidence": True,
                        },
                        parent_ids=(native_id,),
                        idempotency_key=representation_id,
                    )
                    representation_ids["ds"] = representation_id

            observation_hypotheses = sorted(
                hypothesis_by_observation[observation_id], key=lambda row: row["producer_rank"]
            )
            hypothesis_ids = []
            for hypothesis in observation_hypotheses:
                fragment = feature_by_id[hypothesis["content_ref"]]
                candidate_id = fragment["candidate_id"]
                representation_id = f"representation:erg:{observation_id}:{candidate_id}"
                store.record_artifact(
                    artifact_id=representation_id,
                    component_id="representation-adapters",
                    kind="mrs-graph-fragment",
                    epoch=0,
                    payload=fragment,
                    parent_ids=(native_ids["ACE_ERG"],),
                    idempotency_key=representation_id,
                )
                linked_id = f"linked:{observation_id}:{candidate_id}"
                store.record_artifact(
                    artifact_id=linked_id,
                    component_id="cross-representation-linker",
                    kind="cross-representation-candidate",
                    epoch=0,
                    payload={
                        "mrs_fragment_id": representation_id,
                        "dynamic_syntax_fragment_id": representation_ids["ds"],
                        "asserted_identity": False,
                        "dynamic_syntax_status": "failure",
                    },
                    parent_ids=(representation_id, representation_ids["ds"]),
                    idempotency_key=linked_id,
                )
                temporal_id = f"runtime-temporal:{observation_id}:{candidate_id}"
                store.record_artifact(
                    artifact_id=temporal_id,
                    component_id="temporal-relation-manager",
                    kind="temporal-candidate",
                    epoch=0,
                    payload=fragment["temporal_candidate"],
                    parent_ids=(linked_id,),
                    idempotency_key=temporal_id,
                )
                runtime_hypothesis_id = f"runtime-{hypothesis['hypothesis_id']}"
                store.record_artifact(
                    artifact_id=runtime_hypothesis_id,
                    component_id="hypothesis-manager",
                    kind="factorized-hypothesis",
                    epoch=0,
                    payload=hypothesis,
                    parent_ids=(linked_id, temporal_id),
                    idempotency_key=runtime_hypothesis_id,
                )
                hypothesis_ids.append(runtime_hypothesis_id)

            state_id = f"situation:{observation_id}"
            store.record_artifact(
                artifact_id=state_id,
                component_id="situation-state",
                kind="interrogative-state-candidates",
                epoch=0,
                payload={
                    "observation_id": observation_id,
                    "status": "question-candidates-unselected",
                    "candidate_count": len(hypothesis_ids),
                },
                parent_ids=tuple(hypothesis_ids),
                idempotency_key=state_id,
            )
            episode_id = f"episode:{observation_id}"
            store.record_artifact(
                artifact_id=episode_id,
                component_id="episodic-store",
                kind="open-episode",
                epoch=0,
                payload={"observation_id": observation_id, "selection_event": None},
                parent_ids=(*hypothesis_ids, state_id),
                idempotency_key=episode_id,
            )
            retrieval_id = f"retrieval:{observation_id}"
            store.record_artifact(
                artifact_id=retrieval_id,
                component_id="structural-retrieval",
                kind="ranked-hypothesis-refs",
                epoch=0,
                payload={"ordered_ids": hypothesis_ids, "policy": "producer-rank-baseline"},
                parent_ids=(episode_id, state_id, *hypothesis_ids),
                idempotency_key=retrieval_id,
            )
            beam_id = f"active-beam:{observation_id}"
            store.record_artifact(
                artifact_id=beam_id,
                component_id="active-beam",
                kind="bounded-active-hypotheses",
                epoch=0,
                payload={"bound": 3, "hypothesis_ids": hypothesis_ids},
                parent_ids=(retrieval_id, *hypothesis_ids),
                idempotency_key=beam_id,
            )
            beams_for_soar.append({
                "observation_id": observation_id,
                "role": observation["role"],
                "beam_id": beam_id,
                "state_id": state_id,
                "hypothesis_ids": hypothesis_ids,
            })

        checkpoint_dir = database.parent / "checkpoint-epoch-0"
        decisions, soar_checkpoint = checkpoint_and_verify(beams_for_soar, checkpoint_dir / "soar")
        for beam, decision in zip(beams_for_soar, decisions, strict=True):
            decision_id = f"soar-decision:{beam['observation_id']}"
            store.record_artifact(
                artifact_id=decision_id,
                component_id="soar-runtime",
                kind="soar-decision",
                epoch=0,
                payload=decision,
                parent_ids=(beam["beam_id"], beam["state_id"]),
                idempotency_key=decision_id,
            )
            ancestry_targets.append(decision_id)

        metrics = store.metrics()
        ancestry = {target: store.ancestry(target) for target in ancestry_targets}
        runtime_database_checkpoint = store.checkpoint_database(checkpoint_dir / "runtime.sqlite")

    return {
        "status": "GO-REAL-DATA-TO-SOAR-DURABLE-RUNTIME",
        "epoch": 0,
        "source_questions": len(samples),
        "soar_decisions": decisions,
        "runtime_metrics": metrics,
        "checkpoint": {
            "soar": soar_checkpoint,
            "runtime_database": runtime_database_checkpoint,
        },
        "decision_ancestry": ancestry,
        "validations": {
            "every_soar_decision_has_full_ancestry": all(len(rows) >= 15 for rows in ancestry.values()),
            "all_decisions_select_a_beam_member": all(
                decision["selected_hypothesis_id"] in beam["hypothesis_ids"]
                for beam, decision in zip(beams_for_soar, decisions, strict=True)
            ),
            "dynamic_syntax_failure_remains_explicit": all(
                next(row for row in analyses_by_observation[beam["observation_id"]]["analyses"]
                     if row["producer"] == "dynamicsyntax-python")["status"] == "failure"
                for beam in beams_for_soar
            ),
            "one_durable_event_per_artifact": metrics["events"] == metrics["artifacts"],
            "single_epoch": metrics["epochs"] == 1,
            "soar_decision_equivalent_after_restore": soar_checkpoint["decision_equivalence"],
            "soar_working_memory_reconstructed_not_falsely_claimed_native": (
                soar_checkpoint["working_memory_restore_mode"] == "reconstruct-from-active-context"
                and soar_checkpoint["native_whole-working-memory_restore_claimed"] is False
            ),
            "runtime_checkpoint_covers_every_committed_artifact": (
                runtime_database_checkpoint["artifact_count"] == metrics["artifacts"]
            ),
        },
    }
