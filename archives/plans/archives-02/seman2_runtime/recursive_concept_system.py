"""Recursive conceptual induction over real episodic and learned stock."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Iterable

from .cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactStatus,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    CognitiveArtifact,
    thaw_json,
)
from .concept_learning import ConceptInducer, InductionPolicy, StructuralOccurrence
from .contracts import ContractError, canonical_json
from .developmental_core import DevelopmentalCore
from .discourse_identity_system import register_discourse_identity_types
from .formal_composition import register_composition_types
from .hypothesis_system import register_hypothesis_types
from .knowledge_system import register_knowledge_types
from .low_level_system import register_low_level_types
from .soar_control_system import register_soar_control_types
from .temporal_system import register_temporal_types
from .transformation_learning import (
    TransformationLearningEngine,
    register_transformation_types,
)


CONCEPT_BUILD = "active-recursive-concept-induction"


def register_recursive_concept_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "concept-application-goal",
            "seman2/active/L5/concept-application-goal",
            5,
            allowed_producers=frozenset({"recursive-concept-engine"}),
            parent_types=frozenset({"learned-transformation", "episode-memory"}),
            required_native_fields=frozenset(
                {"goal_ref", "observed_factors", "candidate_beam", "inactive_candidate_refs"}
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "concept-match-retrieval",
            "seman2/active/L5/concept-match-retrieval",
            5,
            allowed_producers=frozenset({"recursive-concept-engine"}),
            parent_types=frozenset({"concept-application-goal", "learned-transformation"}),
            required_native_fields=frozenset(
                {"goal_ref", "depth", "hits", "indexed_count", "work_units"}
            ),
            required_projection_fields=frozenset({"raw_source_accessed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "soar-concept-decision",
            "seman2/active/L6/soar-concept-decision",
            6,
            allowed_producers=frozenset({"recursive-concept-engine"}),
            parent_types=frozenset({"concept-application-goal", "concept-match-retrieval"}),
            required_native_fields=frozenset(
                {
                    "goal_ref", "initial_operator", "final_operator",
                    "selected_candidate_ref", "compared_candidate_refs",
                    "retrieval_result_ref", "soar_trace",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "persistent_store_copied_to_soar"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "learned-concept-contribution",
            "seman2/active/L2/learned-concept-contribution",
            2,
            allowed_producers=frozenset({"recursive-concept-engine"}),
            feedback_parent_types=frozenset(
                {"soar-concept-decision", "learned-transformation", "episode-memory"}
            ),
            required_native_fields=frozenset(
                {
                    "selected_structure_ref", "observed_factors", "matched_factors",
                    "predicted_outcomes", "qualification",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "concept-expectation-set",
            "seman2/active/L3/concept-expectation-set",
            3,
            allowed_producers=frozenset({"recursive-concept-engine"}),
            parent_types=frozenset({"learned-concept-contribution"}),
            required_native_fields=frozenset(
                {"candidate_ref", "expectations", "selected_ref"}
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "concept-feedback-episode",
            "seman2/active/L4/concept-feedback-episode",
            4,
            allowed_producers=frozenset({"recursive-concept-engine"}),
            parent_types=frozenset({"concept-expectation-set", "episode-memory"}),
            required_native_fields=frozenset(
                {
                    "application_ref", "structural_factors", "predicted_outcomes",
                    "observed_outcomes",
                }
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "recursive-learned-concept",
            "seman2/active/L5/recursive-learned-concept",
            5,
            allowed_producers=frozenset({"recursive-concept-engine"}),
            parent_types=frozenset({"concept-feedback-episode"}),
            required_native_fields=frozenset(
                {
                    "learned_structure_ref", "structural_pattern", "support_occurrences",
                    "observed_outcomes", "distributed_prototype_ref", "recursion_depth",
                }
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )


def build_recursive_concept_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    register_composition_types(registry)
    register_hypothesis_types(registry)
    register_knowledge_types(registry)
    register_transformation_types(registry)
    register_temporal_types(registry)
    register_discourse_identity_types(registry)
    register_soar_control_types(registry)
    register_recursive_concept_types(registry)
    registry.freeze()
    return registry


class RecursiveConceptEngine:
    """Select, re-inject, observe, then recursively abstract learned patterns."""

    def __init__(
        self,
        arena: ArtifactArena,
        *,
        transformation_engine: TransformationLearningEngine,
        core: DevelopmentalCore,
        project_root: Path,
        context_ref: str = "ctx:model",
        beam_bound: int = 2,
        maximum_structures: int = 16,
        memory_limit_mib: int = 2_048,
        timeout_seconds: float = 30.0,
    ) -> None:
        if beam_bound != 2:
            raise ContractError("SYS-08: la preuve SML exige un beam de deux concepts")
        if not 2 <= maximum_structures <= 128:
            raise ContractError("SYS-08: maximum_structures hors [2,128]")
        self.arena = arena
        self.transformation_engine = transformation_engine
        self.core = core
        self.project_root = Path(project_root)
        self.context_ref = context_ref
        self.beam_bound = beam_bound
        self.maximum_structures = maximum_structures
        self.memory_limit_mib = memory_limit_mib
        self.timeout_seconds = timeout_seconds
        self._applications: dict[
            tuple[tuple[str, ...], str, str],
            tuple[CognitiveArtifact, CognitiveArtifact, CognitiveArtifact, CognitiveArtifact, CognitiveArtifact],
        ] = {}
        self._feedback: dict[tuple[str, str], CognitiveArtifact] = {}
        self._recursive: dict[tuple[str, ...], CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "beam_bound": beam_bound,
                    "maximum_structures": maximum_structures,
                    "memory_limit_mib": memory_limit_mib,
                    "selection": "real-two-cycle-SML-most-specific-full-match",
                    "raw_source_access": False,
                }
            ).encode()
        ).hexdigest()

    def apply(
        self,
        learned_artifacts: Iterable[CognitiveArtifact],
        *,
        before_episode: CognitiveArtifact,
        event_episode: CognitiveArtifact,
    ) -> tuple[CognitiveArtifact, CognitiveArtifact, CognitiveArtifact, CognitiveArtifact, CognitiveArtifact]:
        learned = tuple(sorted(learned_artifacts, key=lambda row: row.artifact_id))
        if len(learned) < 2 or len(learned) > self.maximum_structures:
            raise ContractError("SYS-08: au moins deux structures L5 bornées sont requises")
        if any(row.artifact_type != "learned-transformation" for row in learned):
            raise ContractError("SYS-08: structure candidate non L5")
        if any(row.artifact_type != "episode-memory" for row in (before_episode, event_episode)):
            raise ContractError("SYS-08: application exige deux épisodes L4 réels")
        key = (tuple(row.artifact_id for row in learned), before_episode.artifact_id, event_episode.artifact_id)
        if key in self._applications:
            return self._applications[key]
        started = time.perf_counter()
        observed = self.transformation_engine.partial_structural_factors(
            before_episode=before_episode, event_episode=event_episode
        )
        matches_by_ref = {
            row.structure_ref: row
            for row in self.transformation_engine.inducer.match(observed)
        }
        candidates = []
        for artifact in learned:
            payload = thaw_json(artifact.payload_native)
            structure_ref = payload["learned_structure_ref"]
            match = matches_by_ref[structure_ref]
            pattern_size = len(payload["structural_pattern"])
            outcome_total = sum(count for _, count in payload["observed_outcomes"])
            outcome_peak = max(count for _, count in payload["observed_outcomes"]) / outcome_total
            score = round(
                (1.0 if match.full_match else 0.0)
                + match.coverage
                + pattern_size / 100.0
                + outcome_peak / 1000.0,
                6,
            )
            candidates.append(
                {
                    "candidate_ref": artifact.artifact_id,
                    "content_ref": structure_ref,
                    "score": score,
                    "full_match": match.full_match,
                    "coverage": match.coverage,
                    "pattern_size": pattern_size,
                    "matched_factors": list(match.matched_factors),
                    "missing_factors": list(match.missing_factors),
                    "predicted_outcomes": [list(row) for row in match.predicted_outcomes],
                }
            )
        candidates.sort(
            key=lambda row: (
                not row["full_match"], -row["coverage"], -row["pattern_size"],
                -row["score"], row["candidate_ref"],
            )
        )
        active = candidates[: self.beam_bound]
        if len(active) != 2 or not active[0]["full_match"]:
            raise ContractError("SYS-08: aucun beam conceptuel applicable")
        for rank, row in enumerate(active, 1):
            row["rank"] = rank
        inactive = [row["candidate_ref"] for row in candidates[self.beam_bound :]]
        goal_ref = "goal:apply-concept:" + hashlib.sha256(
            canonical_json([before_episode.artifact_id, event_episode.artifact_id, observed]).encode()
        ).hexdigest()[:24]
        goal_parents = tuple(row.artifact_id for row in learned) + (
            before_episode.artifact_id, event_episode.artifact_id,
        )
        goal = self.arena.publish(
            ArtifactProposal(
                artifact_type="concept-application-goal",
                producer_id="recursive-concept-engine",
                producer_build=CONCEPT_BUILD,
                configuration_digest=self.configuration_digest,
                mode=before_episode.mode,
                session_id=before_episode.session_id,
                wave=max(self.arena.get(ref).wave for ref in goal_parents),
                parent_ids=goal_parents,
                observation_refs=before_episode.observation_refs + event_episode.observation_refs,
                context_refs=(self.context_ref,),
                source_anchors=self._source_anchors(self.arena.get(ref) for ref in goal_parents),
                resource_cost={"beam_bound": self.beam_bound, "available_structures": len(candidates)},
                payload_native={
                    "goal_ref": goal_ref,
                    "observed_factors": list(observed),
                    "candidate_beam": active,
                    "inactive_candidate_refs": inactive,
                },
                payload_projection={"truth_committed": False},
                idempotency_key=f"concept-goal:{goal_ref}",
            )
        )
        common = {
            "goal_ref": goal_ref,
            "active_candidates": [
                {
                    "rank": row["rank"], "candidate_ref": row["candidate_ref"],
                    "content_ref": row["content_ref"], "score": row["score"],
                }
                for row in active
            ],
            "memory_limit_mib": self.memory_limit_mib,
        }
        initial = self._run_cycle({**common, "phase": "initial"})
        if initial.get("action") != "request-concept-retrieval":
            raise ContractError("SYS-08: Soar n'a pas demandé le retrieval conceptuel")
        hits = [
            {
                "rank": rank,
                "content_ref": row["content_ref"],
                "candidate_ref": row["candidate_ref"],
                "score": row["score"],
                "full_match": row["full_match"],
                "matched_factors": row["matched_factors"],
                "missing_factors": row["missing_factors"],
                "explanation": (
                    f"full={row['full_match']};coverage={row['coverage']};"
                    f"specificity={row['pattern_size']}"
                ),
            }
            for rank, row in enumerate(sorted(active, key=lambda row: (-row["score"], row["candidate_ref"])), 1)
        ]
        retrieval_parents = (goal.artifact_id,) + tuple(row["candidate_ref"] for row in active)
        retrieval = self.arena.publish(
            ArtifactProposal(
                artifact_type="concept-match-retrieval",
                producer_id="recursive-concept-engine",
                producer_build=CONCEPT_BUILD,
                configuration_digest=self.configuration_digest,
                mode=goal.mode,
                session_id=goal.session_id,
                wave=goal.wave,
                parent_ids=retrieval_parents,
                observation_refs=goal.observation_refs,
                context_refs=goal.context_refs,
                source_anchors=self._source_anchors(self.arena.get(ref) for ref in retrieval_parents),
                resource_cost={"indexed_structures": len(candidates), "returned_hits": len(hits)},
                payload_native={
                    "goal_ref": goal_ref, "depth": 1, "hits": hits,
                    "indexed_count": len(candidates), "work_units": len(candidates),
                },
                payload_projection={"raw_source_accessed": False},
                idempotency_key=f"concept-retrieval:{goal.artifact_id}:1",
            )
        )
        final = self._run_cycle(
            {**common, "phase": "retrieved", "retrieval": {"result_ref": retrieval.artifact_id, "hits": hits}}
        )
        active_refs = {row["candidate_ref"] for row in active}
        if final.get("action") != "select-concept" or set(final["compared_candidate_refs"]) != active_refs:
            raise ContractError("SYS-08: comparaison Soar incomplète")
        selected_ref = final["selected_candidate_ref"]
        if selected_ref != hits[0]["candidate_ref"]:
            raise ContractError("SYS-08: choix Soar divergent du retrieval")
        decision = self.arena.publish(
            ArtifactProposal(
                artifact_type="soar-concept-decision",
                producer_id="recursive-concept-engine",
                producer_build=CONCEPT_BUILD,
                configuration_digest=self.configuration_digest,
                mode=goal.mode,
                session_id=goal.session_id,
                wave=max(goal.wave, retrieval.wave) + 1,
                parent_ids=(goal.artifact_id, retrieval.artifact_id),
                observation_refs=goal.observation_refs,
                context_refs=goal.context_refs,
                source_anchors=self._source_anchors((goal, retrieval)),
                resource_cost={
                    "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
                    "projected_candidates": len(active), "memory_limit_mib": self.memory_limit_mib,
                },
                payload_native={
                    "goal_ref": goal_ref, "initial_operator": initial,
                    "final_operator": final["action"], "selected_candidate_ref": selected_ref,
                    "compared_candidate_refs": final["compared_candidate_refs"],
                    "retrieval_result_ref": retrieval.artifact_id, "soar_trace": final,
                },
                payload_projection={"truth_committed": False, "persistent_store_copied_to_soar": False},
                idempotency_key=f"soar-concept-decision:{goal.artifact_id}",
            )
        )
        selected = next(row for row in active if row["candidate_ref"] == selected_ref)
        selected_artifact = self.arena.get(selected_ref)
        contribution_parents = (
            decision.artifact_id, selected_artifact.artifact_id,
            before_episode.artifact_id, event_episode.artifact_id,
        )
        contribution = self.arena.publish(
            ArtifactProposal(
                artifact_type="learned-concept-contribution",
                producer_id="recursive-concept-engine",
                producer_build=CONCEPT_BUILD,
                configuration_digest=self.configuration_digest,
                mode=goal.mode,
                session_id=goal.session_id,
                wave=decision.wave + 1,
                parent_ids=contribution_parents,
                observation_refs=goal.observation_refs,
                context_refs=goal.context_refs,
                source_anchors=self._source_anchors(self.arena.get(ref) for ref in contribution_parents),
                resource_cost={"matched_factor_count": len(selected["matched_factors"])},
                payload_native={
                    "selected_structure_ref": selected["content_ref"],
                    "observed_factors": list(observed),
                    "matched_factors": selected["matched_factors"],
                    "predicted_outcomes": selected["predicted_outcomes"],
                    "qualification": "full-match" if selected["full_match"] else "partial-match",
                },
                payload_projection={"truth_committed": False, "world_update_performed": False},
                status=ArtifactStatus.SUCCESS if selected["full_match"] else ArtifactStatus.PARTIAL,
                idempotency_key=f"learned-concept-contribution:{goal.artifact_id}:{selected_ref}",
            )
        )
        expectations = [
            {
                "outcome_ref": outcome, "confidence": probability,
                "epistemic_status": "expected-not-observed", "selected": False,
            }
            for outcome, probability in selected["predicted_outcomes"]
        ]
        expectation = self.arena.publish(
            ArtifactProposal(
                artifact_type="concept-expectation-set",
                producer_id="recursive-concept-engine",
                producer_build=CONCEPT_BUILD,
                configuration_digest=self.configuration_digest,
                mode=goal.mode,
                session_id=goal.session_id,
                wave=contribution.wave,
                parent_ids=(contribution.artifact_id,),
                observation_refs=contribution.observation_refs,
                context_refs=contribution.context_refs,
                source_anchors=tuple(thaw_json(row) for row in contribution.source_anchors),
                resource_cost={"expectation_count": len(expectations)},
                payload_native={
                    "candidate_ref": contribution.artifact_id,
                    "expectations": expectations, "selected_ref": None,
                },
                payload_projection={"truth_committed": False, "world_update_performed": False},
                idempotency_key=f"concept-expectation:{contribution.artifact_id}",
            )
        )
        result = (goal, retrieval, decision, contribution, expectation)
        self._applications[key] = result
        return result

    def observe_feedback(
        self,
        expectation: CognitiveArtifact,
        *,
        after_episode: CognitiveArtifact,
    ) -> CognitiveArtifact:
        if expectation.artifact_type != "concept-expectation-set" or after_episode.artifact_type != "episode-memory":
            raise ContractError("SYS-08: feedback exige attente L3 et outcome épisodique L4")
        key = (expectation.artifact_id, after_episode.artifact_id)
        if key in self._feedback:
            return self._feedback[key]
        contribution = self.arena.get(expectation.parent_ids[0])
        contribution_payload = thaw_json(contribution.payload_native)
        before_episode = self.arena.get(contribution.parent_ids[2])
        event_episode = self.arena.get(contribution.parent_ids[3])
        observed_outcomes = self.transformation_engine.observed_outcomes(
            before_episode=before_episode,
            event_episode=event_episode,
            after_episode=after_episode,
        )
        predicted = tuple(
            row["outcome_ref"] for row in thaw_json(expectation.payload_native)["expectations"]
        )
        selected_artifact = self.arena.get(contribution.parent_ids[1])
        selected_payload = thaw_json(selected_artifact.payload_native)
        selected_pattern = selected_payload["structural_pattern"]
        structural_factors = tuple(
            sorted(
                {
                    "source-level:learned-pattern",
                    "schema-has:event-form" if any(row.startswith("event-form:") for row in selected_pattern) else "schema-missing:event-form",
                    "schema-has:pre-state" if any(row.startswith("pre-state:") for row in selected_pattern) else "schema-missing:pre-state",
                    "schema-has:observed-outcome",
                    *(f"schema-role:{row.split(':', 1)[1]}" for row in selected_pattern if row.startswith("event-role:")),
                }
            )
        )
        parents = (expectation.artifact_id, after_episode.artifact_id)
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="concept-feedback-episode",
                producer_id="recursive-concept-engine",
                producer_build=CONCEPT_BUILD,
                configuration_digest=self.configuration_digest,
                mode=expectation.mode,
                session_id=expectation.session_id,
                wave=max(expectation.wave, after_episode.wave),
                parent_ids=parents,
                observation_refs=tuple(sorted(set(expectation.observation_refs + after_episode.observation_refs))),
                context_refs=expectation.context_refs,
                source_anchors=self._source_anchors(self.arena.get(ref) for ref in parents),
                resource_cost={"factor_count": len(structural_factors)},
                payload_native={
                    "application_ref": contribution.artifact_id,
                    "structural_factors": list(structural_factors),
                    "predicted_outcomes": list(predicted),
                    "observed_outcomes": list(observed_outcomes),
                },
                payload_projection={"truth_committed": False},
                idempotency_key=f"concept-feedback:{expectation.artifact_id}:{after_episode.artifact_id}",
            )
        )
        self._feedback[key] = artifact
        return artifact

    def induce_recursively(
        self, feedback_episodes: Iterable[CognitiveArtifact]
    ) -> CognitiveArtifact:
        feedback = tuple(sorted(feedback_episodes, key=lambda row: row.artifact_id))
        if len(feedback) < 2 or any(row.artifact_type != "concept-feedback-episode" for row in feedback):
            raise ContractError("SYS-08: au moins deux feedbacks L4 réels sont requis")
        key = tuple(row.artifact_id for row in feedback)
        if key in self._recursive:
            return self._recursive[key]
        inducer = ConceptInducer(
            InductionPolicy(minimum_support=2, minimum_pattern_size=3, maximum_structures=8)
        )
        for row in feedback:
            payload = thaw_json(row.payload_native)
            inducer.observe(
                StructuralOccurrence(
                    occurrence_ref=row.artifact_id,
                    structural_factors=tuple(payload["structural_factors"]),
                    context_refs=row.context_refs,
                    outcome_refs=tuple(payload["observed_outcomes"]),
                    support_refs=(row.artifact_id,),
                )
            )
        structures = inducer.induce()
        if not structures:
            raise ContractError("SYS-08: aucune abstraction récursive inductible")
        structure = max(
            structures,
            key=lambda row: (row.support_count, len(row.structural_pattern), row.learned_structure_id),
        )
        prototype = inducer.materialize_distributed_prototype(
            structure.learned_structure_id, core=self.core, context_ref=self.context_ref
        )
        structure = inducer.structures[structure.learned_structure_id]
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="recursive-learned-concept",
                producer_id="recursive-concept-engine",
                producer_build=CONCEPT_BUILD,
                configuration_digest=self.configuration_digest,
                mode=feedback[0].mode,
                session_id=feedback[0].session_id,
                wave=max(row.wave for row in feedback) + 1,
                parent_ids=tuple(row.artifact_id for row in feedback),
                observation_refs=tuple(sorted({ref for row in feedback for ref in row.observation_refs})),
                context_refs=(self.context_ref,),
                source_anchors=self._source_anchors(feedback),
                resource_cost={"support_count": structure.support_count, "factor_count": len(structure.structural_pattern)},
                payload_native={
                    "learned_structure_ref": structure.learned_structure_id,
                    "structural_pattern": list(structure.structural_pattern),
                    "support_occurrences": list(structure.support_occurrences),
                    "observed_outcomes": [list(row) for row in structure.observed_outcomes],
                    "distributed_prototype_ref": prototype.form_id,
                    "recursion_depth": 2,
                },
                payload_projection={"truth_committed": False},
                idempotency_key=f"recursive-learned-concept:{structure.learned_structure_id}:{hashlib.sha256(canonical_json(key).encode()).hexdigest()[:16]}",
            )
        )
        self._recursive[key] = artifact
        return artifact

    def _run_cycle(self, request: dict[str, Any]) -> dict[str, Any]:
        worker = self.project_root / "seman2_runtime/workers/soar_concept_worker.py"
        try:
            completed = subprocess.run(
                [str(self.project_root / ".venv/bin/python"), str(worker)],
                cwd=self.project_root,
                env=os.environ.copy(),
                input=json.dumps(request),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContractError("SYS-08: timeout du worker Soar") from exc
        if completed.returncode:
            raise ContractError(f"SYS-08: worker Soar en échec: {completed.stderr.strip()}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ContractError("SYS-08: sortie Soar non JSON") from exc

    @staticmethod
    def _source_anchors(rows: Iterable[CognitiveArtifact]) -> tuple[dict[str, Any], ...]:
        anchors = {
            canonical_json(thaw_json(anchor)): thaw_json(anchor)
            for row in rows
            for anchor in row.source_anchors
        }
        return tuple(anchors[key] for key in sorted(anchors))
