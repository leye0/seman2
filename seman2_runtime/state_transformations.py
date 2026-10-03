"""Transformations d'état candidates pilotées par de vrais opérateurs Soar."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .contracts import ContractError
from .durable_runtime import ArtifactRecord, DurableRuntimeStore, RuntimePlan
from .soar_session import checkpoint_and_verify


_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_STOP = {
    "all", "and", "are", "can", "for", "from", "how", "inside", "into",
    "that", "the", "this", "use", "way", "what", "when", "with", "would",
}


def _content_terms(text: str) -> set[str]:
    return {word.casefold() for word in _WORD.findall(text) if word.casefold() not in _STOP}


def _predicate_lemmas(fragment: ArtifactRecord) -> set[str]:
    lemmas = set()
    for relation in fragment.payload.get("relations", []):
        predicate = relation.get("predicate", "")
        match = re.match(r"^_?(.+?)_[anvrpqxc]_[^_]+$", predicate)
        if match:
            lemmas.add(match.group(1).casefold())
    return lemmas


def _fragment_for_hypothesis(
    store: DurableRuntimeStore, hypothesis: ArtifactRecord
) -> ArtifactRecord:
    content_ref = hypothesis.payload.get("content_ref")
    candidate_id = hypothesis.payload.get("producer_candidate_id")
    observation_id = hypothesis.payload.get("observation_id")
    if not all(isinstance(value, str) and value for value in (content_ref, candidate_id, observation_id)):
        raise ContractError(f"hypothèse sans référence de contenu: {hypothesis.artifact_id}")
    fragment = store.get_artifact(f"representation:erg:{observation_id}:{candidate_id}")
    if fragment.payload.get("fragment_id") != content_ref:
        raise ContractError("transformation: référence d'hypothèse et fragment incohérents")
    return fragment


def _candidate_set(
    *,
    observation_id: str,
    direct_source_link: bool,
    parsed_content: bool,
    predicate_overlap: list[str],
    lexical_overlap: list[str],
) -> list[dict[str, Any]]:
    shared_evidence = {
        "direct_source_link": direct_source_link,
        "parsed_content": parsed_content,
        "predicate_overlap": predicate_overlap,
        "lexical_overlap": lexical_overlap,
    }
    return [
        {
            "transformation_id": f"TRANSFORM:{observation_id}:ATTACH",
            "kind": "attach-answer-candidate",
            "eligible": direct_source_link and parsed_content,
            "evidence": shared_evidence,
            "effect": {
                "attach_as": "answer-evidence-candidate",
                "close_question_under_discussion": False,
                "assert_answer_truth": False,
            },
        },
        {
            "transformation_id": f"TRANSFORM:{observation_id}:KEEP-OPEN",
            "kind": "keep-qud-open",
            "eligible": True,
            "evidence": shared_evidence,
            "effect": {
                "attach_as": None,
                "close_question_under_discussion": False,
                "assert_answer_truth": False,
            },
        },
        {
            "transformation_id": f"TRANSFORM:{observation_id}:REJECT",
            "kind": "reject-answer",
            "eligible": True,
            "evidence": shared_evidence,
            "effect": {
                "attach_as": "rejected-answer-candidate",
                "close_question_under_discussion": False,
                "assert_answer_truth": False,
            },
        },
    ]


def execute_state_transformation_epoch(root: Path, database: Path) -> dict[str, Any]:
    """Sélectionne puis applique une transformation prudente à l'époque 2."""
    root = root.resolve()
    plan = RuntimePlan(root / "plans/runtime_service_graph.json")
    operator_checkpoints: list[dict[str, Any]] = []
    selected_decisions: list[dict[str, Any]] = []
    applied_state_ids: list[str] = []

    with DurableRuntimeStore(database, plan) as store:
        before = store.metrics()
        if before["epochs"] != 2:
            raise ContractError(
                f"state transformations: deux époques préalables requises, reçu {before['epochs']}"
            )
        answer_decisions = store.list_artifacts(
            component_id="soar-runtime", kind="soar-decision", epoch=1
        )
        if len(answer_decisions) != 3:
            raise ContractError(
                f"state transformations: attendu 3 décisions de réponse, reçu {len(answer_decisions)}"
            )

        previous_agent = database.parent / "checkpoint-epoch-1/soar/agent.soar"
        if not previous_agent.is_file():
            raise ContractError("state transformations: agent Soar de l'époque 1 absent")

        for index, answer_decision in enumerate(answer_decisions, 1):
            if answer_decision.payload.get("next_action") != "assess-answer":
                raise ContractError("state transformations: action Soar de réponse inattendue")
            observation_id = answer_decision.payload["observation_id"]
            answer_state = store.get_artifact(f"situation:{observation_id}")
            question_observation_id = answer_state.payload["answers_question_observation_id"]
            question_decision = store.get_artifact(f"soar-decision:{question_observation_id}")
            answer_hypothesis = store.get_artifact(
                answer_decision.payload["selected_hypothesis_id"]
            )
            question_hypothesis = store.get_artifact(
                question_decision.payload["selected_hypothesis_id"]
            )
            answer_fragment = _fragment_for_hypothesis(store, answer_hypothesis)
            question_fragment = _fragment_for_hypothesis(store, question_hypothesis)
            answer_observation = store.get_artifact(observation_id)
            question_observation = store.get_artifact(question_observation_id)

            predicate_overlap = sorted(
                _predicate_lemmas(answer_fragment) & _predicate_lemmas(question_fragment)
            )
            lexical_overlap = sorted(
                _content_terms(answer_observation.payload["text"])
                & _content_terms(question_observation.payload["text"])
            )
            ancestry = store.ancestry(answer_decision.artifact_id)
            direct_source_link = any(
                row["artifact_id"] == question_decision.artifact_id for row in ancestry
            )
            parsed_content = answer_fragment.kind == "mrs-graph-fragment"
            candidates = _candidate_set(
                observation_id=observation_id,
                direct_source_link=direct_source_link,
                parsed_content=parsed_content,
                predicate_overlap=predicate_overlap,
                lexical_overlap=lexical_overlap,
            )
            candidate_artifact_ids = []
            for candidate in candidates:
                artifact_id = f"candidate-{candidate['transformation_id']}"
                store.record_artifact(
                    artifact_id=artifact_id,
                    component_id="candidate-transformations",
                    kind="state-transformation-candidate",
                    epoch=1,
                    payload=candidate,
                    parent_ids=(answer_decision.artifact_id,),
                    idempotency_key=artifact_id,
                )
                candidate_artifact_ids.append(artifact_id)

            context = {
                "observation_id": observation_id,
                "role": "state-transformation",
                "transformations": candidates,
            }
            checkpoint_dir = (
                database.parent / "checkpoint-epoch-1-operators" / f"context-{index}" / "soar"
            )
            decisions, checkpoint = checkpoint_and_verify(
                [context], checkpoint_dir, agent_file=previous_agent
            )
            decision = decisions[0]
            if decision["selected_transformation_id"] != candidates[0]["transformation_id"]:
                raise ContractError("Soar n'a pas sélectionné la transformation attribuée éligible")
            operator_checkpoints.append({
                "observation_id": observation_id,
                "checkpoint": checkpoint,
            })
            selected_decisions.append(decision)

            soar_decision_id = f"soar-transformation-decision:{observation_id}"
            store.record_artifact(
                artifact_id=soar_decision_id,
                component_id="soar-runtime",
                kind="soar-transformation-decision",
                epoch=1,
                payload=decision,
                parent_ids=(*candidate_artifact_ids, answer_state.artifact_id),
                idempotency_key=soar_decision_id,
            )
            selected_candidate_artifact = next(
                artifact_id
                for artifact_id, candidate in zip(candidate_artifact_ids, candidates, strict=True)
                if candidate["transformation_id"] == decision["selected_transformation_id"]
            )
            applied_state_id = f"situation-applied:{observation_id}"
            store.record_artifact(
                artifact_id=applied_state_id,
                component_id="situation-state",
                kind="state-after-selected-transformation",
                epoch=2,
                payload={
                    "observation_id": observation_id,
                    "previous_state_id": answer_state.artifact_id,
                    "selected_transformation_id": decision["selected_transformation_id"],
                    "effect": candidates[0]["effect"],
                    "qud_status": "open-pending-content-evaluation",
                    "answer_truth_asserted": False,
                },
                parent_ids=(
                    answer_state.artifact_id,
                    selected_candidate_artifact,
                    soar_decision_id,
                ),
                idempotency_key=applied_state_id,
            )
            prior_episode_id = f"episode:{observation_id}"
            applied_episode_id = f"episode-applied:{observation_id}"
            store.record_artifact(
                artifact_id=applied_episode_id,
                component_id="episodic-store",
                kind="state-transformation-event",
                epoch=2,
                payload={
                    "observation_id": observation_id,
                    "previous_episode_id": prior_episode_id,
                    "state_id": applied_state_id,
                    "operator_decision_id": soar_decision_id,
                },
                parent_ids=(applied_state_id, prior_episode_id),
                idempotency_key=applied_episode_id,
            )
            applied_state_ids.append(applied_state_id)

        metrics = store.metrics()
        ancestry = {artifact_id: store.ancestry(artifact_id) for artifact_id in applied_state_ids}
        selection_does_not_assert_truth = all(
            store.get_artifact(artifact_id).payload["answer_truth_asserted"] is False
            and store.get_artifact(artifact_id).payload["qud_status"]
            == "open-pending-content-evaluation"
            for artifact_id in applied_state_ids
        )
        runtime_checkpoint = store.checkpoint_database(
            database.parent / "checkpoint-epoch-2/runtime.sqlite"
        )

    return {
        "status": "GO-SOAR-OPERATOR-STATE-TRANSFORMATIONS",
        "runtime_metrics_before": before,
        "runtime_metrics_after": metrics,
        "operator_decisions": selected_decisions,
        "operator_checkpoints": operator_checkpoints,
        "applied_state_ancestry": ancestry,
        "runtime_checkpoint": runtime_checkpoint,
        "validations": {
            "three_independent_operator_decisions": len(selected_decisions) == 3,
            "real_soar_operator_preferences_used": all(
                decision["operator_semantics"] == "Soar acceptable and better preferences"
                for decision in selected_decisions
            ),
            "only_candidate_attachment_selected": all(
                decision["transformation_kind"] == "attach-answer-candidate"
                for decision in selected_decisions
            ),
            "selection_does_not_assert_truth": selection_does_not_assert_truth,
            "question_source_remains_in_applied_state_ancestry": all(
                any(row["epoch"] == 0 and row["component_id"] == "source-reader" for row in rows)
                for rows in ancestry.values()
            ),
            "answer_source_remains_in_applied_state_ancestry": all(
                any(row["epoch"] == 1 and row["component_id"] == "source-reader" for row in rows)
                for rows in ancestry.values()
            ),
            "state_advances_to_epoch_two": all(
                rows[0]["epoch"] == 2 for rows in ancestry.values()
            ),
            "operator_checkpoint_decisions_equivalent": all(
                item["checkpoint"]["decision_equivalence"] for item in operator_checkpoints
            ),
            "one_event_per_artifact": metrics["events"] == metrics["artifacts"],
            "three_epochs_persisted": metrics["epochs"] == 3,
            "runtime_checkpoint_complete": (
                runtime_checkpoint["artifact_count"] == metrics["artifacts"]
            ),
        },
    }
