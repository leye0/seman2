"""Progression question -> réponse sur deux époques du runtime durable.

Les réponses ne sont pas des attentes d'évaluation. Elles sont relues depuis
les Parquet canoniques à la suite d'une décision Soar, deviennent de nouvelles
observations, puis traversent les mêmes frontières basses et hautes que les
questions. Le texte brut reste dans la source; seule une unité phrastique
bornée est envoyée aux analyseurs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .contracts import ContractError, Envelope
from .corpus import CorpusSamplingService, sampling_request
from .corpus_planning import (
    AnalysisLedgerService,
    CandidateHypothesisLedgerService,
    LiveExternalAnalysisService,
    MRSFeatureProjectionService,
    MRSGraphAdapterService,
)
from .durable_runtime import DurableRuntimeStore, RuntimePlan
from .soar_session import checkpoint_and_verify


def _analysis_unit(text: str) -> tuple[str, dict[str, Any]]:
    """Retourne la première phrase bornée et une transformation audit-able."""
    normalized = " ".join(text.split())
    if not normalized:
        raise ContractError("answer observation: projection textuelle vide")
    # Les réponses techniques introduisent souvent un bloc de code par deux-
    # points. Ce signe termine alors l'unité linguistique à analyser même si
    # le document HTML continue avec du code aplati dans la projection texte.
    match = re.search(r"[.!?:](?:\s|$)", normalized)
    end = match.end() if match else min(len(normalized), 400)
    unit = normalized[:end].strip()
    final_punctuation_normalized = unit.endswith(":")
    if final_punctuation_normalized:
        unit = unit[:-1] + "."
    if len(unit) > 400:
        unit = unit[:400].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
    return unit, {
        "policy": "first-sentence-max-400-chars",
        "source_character_start": 0,
        "source_character_end": end,
        "terminal_colon_normalized_to_period": final_punctuation_normalized,
        "raw_text_preserved_in_source_artifact": True,
    }


def _answer_analysis(root: Path, samples: list[dict[str, Any]]) -> tuple[list[dict], dict[str, Any]]:
    observations = []
    selected: dict[str, dict[str, Any]] = {}
    for sample in samples:
        if not sample["answers"]:
            raise ContractError(f"aucune réponse récupérable pour {sample['question_id']}")
        answer = sample["answers"][0]
        text, segmentation = _analysis_unit(answer["text_projection"])
        observation_id = f"observation:stackoverflow:{answer['answer_id']}:answer"
        observations.append({
            "observation_id": observation_id,
            "text": text,
            "modality": "text",
            "role": "answer",
            "sample_id": sample["sample_id"],
            "question_id": sample["question_id"],
            "answer_id": answer["answer_id"],
            "segmentation": segmentation,
        })
        selected[observation_id] = {"sample": sample, "answer": answer}

    envelope = Envelope(
        kind="observation-batch",
        message_id="answer-observation-batch:epoch-1",
        correlation_id="runtime:question-answer:epoch-1",
        producer="corpus-observation",
        parent_ids=tuple(f"answer-retrieval:{row['question_id']}" for row in observations),
        payload={
            "observations": observations,
            "selection_is_derived": True,
            "raw_records_preserved_in_parent": True,
        },
    )
    analyses = LiveExternalAnalysisService(root).handle(envelope)
    ledger = AnalysisLedgerService().handle(analyses)
    fragments = MRSGraphAdapterService().handle(ledger)
    features = MRSFeatureProjectionService().handle(fragments)
    hypotheses = CandidateHypothesisLedgerService().handle(features)
    return observations, {
        "selected": selected,
        "analyses": analyses.payload["rows"],
        "ledger": ledger.payload["entries"],
        "features": features.payload["fragments"],
        "hypotheses": hypotheses.payload["hypotheses"],
    }


def execute_answer_epoch(root: Path, database: Path) -> dict[str, Any]:
    """Ajoute l'époque 1 à une base RUN-01 existante et la checkpoint."""
    root = root.resolve()
    if not database.is_file():
        raise ContractError("answer epoch: exécuter d'abord l'époque question")
    sampling = CorpusSamplingService(root).handle(sampling_request("runtime:answer-epoch"))
    samples = list(sampling.payload["samples"])
    observations, products = _answer_analysis(root, samples)
    ledger_by_key = {
        (row["observation_id"], row["producer"]): row for row in products["ledger"]
    }
    feature_by_id = {row["fragment_id"]: row for row in products["features"]}
    hypotheses_by_observation: dict[str, list[dict]] = {}
    for row in products["hypotheses"]:
        hypotheses_by_observation.setdefault(row["observation_id"], []).append(row)

    plan = RuntimePlan(root / "plans/runtime_service_graph.json")
    beams: list[dict[str, Any]] = []
    answer_ancestry_targets: list[str] = []
    with DurableRuntimeStore(database, plan) as store:
        before = store.metrics()
        if before["epochs"] != 1:
            raise ContractError(f"answer epoch: attendu une seule époque initiale, reçu {before['epochs']}")

        for observation in observations:
            observation_id = observation["observation_id"]
            question_id = observation["question_id"]
            answer = products["selected"][observation_id]["answer"]
            question_observation_id = f"observation:stackoverflow:{question_id}:title"
            prior_decision_id = f"soar-decision:{question_observation_id}"
            prior_decision = store.get_artifact(prior_decision_id)
            if prior_decision.payload.get("next_action") != "retrieve-answer":
                raise ContractError(f"Soar n'a pas demandé de réponse pour {question_id}")

            retrieval_id = f"answer-retrieval:{question_id}"
            store.record_artifact(
                artifact_id=retrieval_id,
                component_id="structural-retrieval",
                kind="retrieved-answer-reference",
                epoch=0,
                payload={
                    "question_id": question_id,
                    "selected_answer_id": answer["answer_id"],
                    "policy": "highest-native-vote-then-source-order",
                    "candidate_answer_ids": [
                        row["answer_id"]
                        for row in products["selected"][observation_id]["sample"]["answers"]
                    ],
                },
                parent_ids=(prior_decision_id,),
                idempotency_key=retrieval_id,
            )
            source_id = f"runtime-source:{answer['answer_id']}"
            store.record_artifact(
                artifact_id=source_id,
                component_id="source-reader",
                kind="canonical-parquet-answer-record",
                epoch=1,
                payload={
                    "answer_id": answer["answer_id"],
                    "question_id": question_id,
                    "canonical_file": answer["canonical_file"],
                    "source_file": answer["source_file"],
                    "source_position": answer["source_position"],
                    "source_record_id": answer["source_record_id"],
                    "native_vote_score": answer["native_vote_score"],
                    "raw_body_sha256": answer["raw_body_sha256"],
                    "raw_body": answer["body"],
                    "text_projection": answer["text_projection"],
                },
                parent_ids=(retrieval_id,),
                idempotency_key=source_id,
            )
            store.record_artifact(
                artifact_id=observation_id,
                component_id="observation-ledger",
                kind="segmented-answer-observation",
                epoch=1,
                payload=observation,
                parent_ids=(source_id,),
                idempotency_key=observation_id,
            )

            native_ids: dict[str, str] = {}
            representation_ids: dict[str, str] = {}
            for producer in ("ACE_ERG", "dynamicsyntax-python"):
                slug = "erg" if producer == "ACE_ERG" else "dynamic-syntax"
                job_id = f"analysis-job:{slug}:{observation_id}"
                native_id = f"native-analysis:{slug}:{observation_id}"
                store.record_artifact(
                    artifact_id=job_id,
                    component_id="analysis-dispatch",
                    kind="analysis-request",
                    epoch=1,
                    payload={"observation_id": observation_id, "producer": producer},
                    parent_ids=(observation_id,),
                    idempotency_key=job_id,
                )
                entry = ledger_by_key[(observation_id, producer)]
                store.record_artifact(
                    artifact_id=native_id,
                    component_id="native-analysis-ledger",
                    kind="native-analysis-result",
                    epoch=1,
                    payload=entry,
                    parent_ids=(job_id,),
                    idempotency_key=native_id,
                )
                native_ids[producer] = native_id
                if producer == "dynamicsyntax-python":
                    ds_id = f"representation:dynamic-syntax:{observation_id}:{entry['status']}"
                    store.record_artifact(
                        artifact_id=ds_id,
                        component_id="representation-adapters",
                        kind="attributed-analysis-result",
                        epoch=1,
                        payload={
                            "observation_id": observation_id,
                            "producer": producer,
                            "status": entry["status"],
                            "failure_is_evidence": entry["failure_is_evidence"],
                        },
                        parent_ids=(native_id,),
                        idempotency_key=ds_id,
                    )
                    representation_ids["ds"] = ds_id

            candidates = sorted(
                hypotheses_by_observation.get(observation_id, []),
                key=lambda row: row["producer_rank"],
            )
            if not candidates:
                raise ContractError(f"aucune hypothèse MRS pour la réponse {observation_id}")
            runtime_hypothesis_ids = []
            for hypothesis in candidates:
                fragment = feature_by_id[hypothesis["content_ref"]]
                candidate_id = fragment["candidate_id"]
                representation_id = f"representation:erg:{observation_id}:{candidate_id}"
                store.record_artifact(
                    artifact_id=representation_id,
                    component_id="representation-adapters",
                    kind="mrs-graph-fragment",
                    epoch=1,
                    payload=fragment,
                    parent_ids=(native_ids["ACE_ERG"],),
                    idempotency_key=representation_id,
                )
                linked_id = f"linked:{observation_id}:{candidate_id}"
                store.record_artifact(
                    artifact_id=linked_id,
                    component_id="cross-representation-linker",
                    kind="cross-representation-candidate",
                    epoch=1,
                    payload={
                        "mrs_fragment_id": representation_id,
                        "dynamic_syntax_fragment_id": representation_ids["ds"],
                        "asserted_identity": False,
                        "dynamic_syntax_status": ledger_by_key[
                            (observation_id, "dynamicsyntax-python")
                        ]["status"],
                    },
                    parent_ids=(representation_id, representation_ids["ds"]),
                    idempotency_key=linked_id,
                )
                temporal_id = f"runtime-temporal:{observation_id}:{candidate_id}"
                store.record_artifact(
                    artifact_id=temporal_id,
                    component_id="temporal-relation-manager",
                    kind="temporal-candidate",
                    epoch=1,
                    payload=fragment["temporal_candidate"],
                    parent_ids=(linked_id,),
                    idempotency_key=temporal_id,
                )
                hypothesis_id = f"runtime-{hypothesis['hypothesis_id']}"
                store.record_artifact(
                    artifact_id=hypothesis_id,
                    component_id="hypothesis-manager",
                    kind="factorized-hypothesis",
                    epoch=1,
                    payload=hypothesis,
                    parent_ids=(linked_id, temporal_id),
                    idempotency_key=hypothesis_id,
                )
                runtime_hypothesis_ids.append(hypothesis_id)

            prior_state_id = f"situation:{question_observation_id}"
            prior_episode_id = f"episode:{question_observation_id}"
            state_id = f"situation:{observation_id}"
            store.record_artifact(
                artifact_id=state_id,
                component_id="situation-state",
                kind="answer-state-candidates",
                epoch=1,
                payload={
                    "observation_id": observation_id,
                    "role": "answer",
                    "answers_question_observation_id": question_observation_id,
                    "previous_state_id": prior_state_id,
                    "candidate_count": len(runtime_hypothesis_ids),
                    "status": "answer-candidates-unselected",
                },
                parent_ids=(*runtime_hypothesis_ids, prior_state_id),
                idempotency_key=state_id,
            )
            episode_id = f"episode:{observation_id}"
            store.record_artifact(
                artifact_id=episode_id,
                component_id="episodic-store",
                kind="question-answer-episode",
                epoch=1,
                payload={
                    "observation_id": observation_id,
                    "question_observation_id": question_observation_id,
                    "previous_episode_id": prior_episode_id,
                    "retrieval_request_id": retrieval_id,
                    "selection_event": None,
                },
                parent_ids=(*runtime_hypothesis_ids, state_id, prior_episode_id),
                idempotency_key=episode_id,
            )
            candidate_retrieval_id = f"retrieval:{observation_id}"
            store.record_artifact(
                artifact_id=candidate_retrieval_id,
                component_id="structural-retrieval",
                kind="ranked-hypothesis-refs",
                epoch=1,
                payload={
                    "ordered_ids": runtime_hypothesis_ids,
                    "policy": "producer-rank-baseline",
                },
                parent_ids=(episode_id, state_id, *runtime_hypothesis_ids),
                idempotency_key=candidate_retrieval_id,
            )
            beam_id = f"active-beam:{observation_id}"
            store.record_artifact(
                artifact_id=beam_id,
                component_id="active-beam",
                kind="bounded-active-hypotheses",
                epoch=1,
                payload={"bound": 3, "hypothesis_ids": runtime_hypothesis_ids},
                parent_ids=(candidate_retrieval_id, *runtime_hypothesis_ids),
                idempotency_key=beam_id,
            )
            beams.append({
                "observation_id": observation_id,
                "role": "answer",
                "beam_id": beam_id,
                "state_id": state_id,
                "hypothesis_ids": runtime_hypothesis_ids,
            })

        previous_agent = database.parent / "checkpoint-epoch-0/soar/agent.soar"
        if not previous_agent.is_file():
            raise ContractError("answer epoch: checkpoint Soar de l'époque 0 absent")
        checkpoint_dir = database.parent / "checkpoint-epoch-1"
        decisions, soar_checkpoint = checkpoint_and_verify(
            beams,
            checkpoint_dir / "soar",
            agent_file=previous_agent,
        )
        for beam, decision in zip(beams, decisions, strict=True):
            decision_id = f"soar-decision:{beam['observation_id']}"
            store.record_artifact(
                artifact_id=decision_id,
                component_id="soar-runtime",
                kind="soar-decision",
                epoch=1,
                payload=decision,
                parent_ids=(beam["beam_id"], beam["state_id"]),
                idempotency_key=decision_id,
            )
            answer_ancestry_targets.append(decision_id)

        metrics = store.metrics()
        ancestry = {target: store.ancestry(target) for target in answer_ancestry_targets}
        runtime_checkpoint = store.checkpoint_database(checkpoint_dir / "runtime.sqlite")

    return {
        "status": "GO-QUESTION-ANSWER-MULTI-EPOCH-RUNTIME",
        "epochs": [0, 1],
        "selected_answers": [
            {
                "question_id": row["question_id"],
                "answer_id": row["answer_id"],
                "observation_id": row["observation_id"],
                "analysis_text": row["text"],
                "segmentation": row["segmentation"],
            }
            for row in observations
        ],
        "soar_decisions": decisions,
        "runtime_metrics_before": before,
        "runtime_metrics_after": metrics,
        "decision_ancestry": ancestry,
        "checkpoint": {"soar": soar_checkpoint, "runtime_database": runtime_checkpoint},
        "validations": {
            "all_answers_are_real_parquet_records": all(
                products["selected"][row["observation_id"]]["answer"]["canonical_file"].endswith(".parquet")
                for row in observations
            ),
            "answer_sources_advance_exactly_one_epoch": all(
                any(a["component_id"] == "source-reader" and a["epoch"] == 1 for a in rows)
                for rows in ancestry.values()
            ),
            "question_decisions_are_ancestors_of_answer_decisions": all(
                any(a["artifact_id"].startswith("soar-decision:observation:stackoverflow:") and a["epoch"] == 0 for a in rows)
                for rows in ancestry.values()
            ),
            "state_continuity_is_in_ancestry": all(
                len([a for a in rows if a["component_id"] == "situation-state"]) >= 2
                for rows in ancestry.values()
            ),
            "episode_continuity_is_in_ancestry": all(
                len([a for a in rows if a["component_id"] == "episodic-store"]) >= 2
                for rows in ancestry.values()
            ),
            "soar_changes_action_for_answers": all(
                decision["next_action"] == "assess-answer" for decision in decisions
            ),
            "soar_selects_real_answer_hypothesis": all(
                decision["selected_hypothesis_id"] in beam["hypothesis_ids"]
                for decision, beam in zip(decisions, beams, strict=True)
            ),
            "all_answer_analyses_yield_mrs_candidates": all(
                hypotheses_by_observation.get(row["observation_id"]) for row in observations
            ),
            "one_durable_event_per_artifact": metrics["events"] == metrics["artifacts"],
            "two_epochs_persisted": metrics["epochs"] == 2,
            "soar_decision_equivalent_after_restore": soar_checkpoint["decision_equivalence"],
            "runtime_checkpoint_covers_every_committed_artifact": (
                runtime_checkpoint["artifact_count"] == metrics["artifacts"]
            ),
        },
    }
