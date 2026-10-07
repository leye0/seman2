"""Apprentissage de transformations depuis des épisodes L4 réellement composés."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
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
from .formal_composition import register_composition_types
from .hypothesis_system import register_hypothesis_types
from .knowledge_system import register_knowledge_types
from .low_level_system import register_low_level_types


TRANSFORMATION_BUILD = "active-episode-transformation-learner"


def register_transformation_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "transformation-episode",
            "seman2/active/L4/transformation-episode",
            4,
            allowed_producers=frozenset({"transformation-learner"}),
            parent_types=frozenset({"episode-memory"}),
            required_native_fields=frozenset(
                {
                    "scenario_ref",
                    "alternatives",
                    "structural_factors",
                    "outcome_refs",
                }
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "learned-transformation",
            "seman2/active/L5/learned-transformation",
            5,
            allowed_producers=frozenset({"transformation-learner"}),
            parent_types=frozenset({"transformation-episode"}),
            required_native_fields=frozenset(
                {
                    "learned_structure_ref",
                    "structural_pattern",
                    "support_occurrences",
                    "observed_outcomes",
                    "exceptions",
                    "distributed_prototype_ref",
                }
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "learned-transformation-contribution",
            "seman2/active/L2/learned-transformation-contribution",
            2,
            allowed_producers=frozenset({"transformation-learner"}),
            feedback_parent_types=frozenset(
                {"learned-transformation", "episode-memory"}
            ),
            required_native_fields=frozenset(
                {
                    "learned_structure_ref",
                    "observed_structural_factors",
                    "input_alternatives",
                    "matched_factors",
                    "missing_factors",
                    "predicted_outcomes",
                    "qualification",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "transformation-expectation-set",
            "seman2/active/L3/transformation-expectation-set",
            3,
            allowed_producers=frozenset({"transformation-learner"}),
            parent_types=frozenset({"learned-transformation-contribution"}),
            required_native_fields=frozenset(
                {"candidate_ref", "expectations", "selected_ref"}
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed"}
            ),
        )
    )


def build_transformation_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    register_composition_types(registry)
    register_hypothesis_types(registry)
    register_knowledge_types(registry)
    register_transformation_types(registry)
    registry.freeze()
    return registry


@dataclass(frozen=True)
class TransformationAlternative:
    event_form_ref: str
    participant_form_ref: str
    participant_bindings: tuple[tuple[str, str], ...]
    before_state_ref: str
    after_state_ref: str | None
    event_role_shape: tuple[str, ...]
    modifier_factor_refs: tuple[str, ...]
    support_artifact_refs: tuple[str, ...]

    @property
    def structural_factors(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    f"event-form:{self.event_form_ref}",
                    f"pre-state:{self.before_state_ref}",
                    *(f"event-role:{role}" for role in self.event_role_shape),
                    *self.modifier_factor_refs,
                }
            )
        )

    @property
    def outcome_ref(self) -> str | None:
        return (
            f"post-state:{self.after_state_ref}"
            if self.after_state_ref is not None
            else None
        )


class TransformationLearningEngine:
    def __init__(
        self,
        arena: ArtifactArena,
        *,
        core: DevelopmentalCore,
        context_ref: str = "ctx:model",
        induction_policy: InductionPolicy | None = None,
    ) -> None:
        self.arena = arena
        self.core = core
        self.context_ref = context_ref
        self.inducer = ConceptInducer(induction_policy or InductionPolicy())
        self.occurrences: dict[str, StructuralOccurrence] = {}
        self.episode_artifacts: dict[str, CognitiveArtifact] = {}
        self.learned_artifacts: dict[str, CognitiveArtifact] = {}
        self.predictions: dict[
            tuple[str, str, str], tuple[CognitiveArtifact, CognitiveArtifact]
        ] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "input": "episode-memory",
                    "alignment": "shared-native-participant-form",
                    "main_state": "MRS-indexed-adjectival-state",
                    "main_event": "MRS-indexed-verbal-relation",
                    "induction_policy": self.inducer.policy.__dict__,
                }
            ).encode()
        ).hexdigest()

    def observe_scenario(
        self,
        scenario_ref: str,
        *,
        before_episode: CognitiveArtifact,
        event_episode: CognitiveArtifact,
        after_episode: CognitiveArtifact,
    ) -> tuple[StructuralOccurrence, CognitiveArtifact]:
        started = time.perf_counter()
        if scenario_ref in self.occurrences:
            return self.occurrences[scenario_ref], self.episode_artifacts[scenario_ref]
        episodes = (before_episode, event_episode, after_episode)
        if any(row.artifact_type != "episode-memory" for row in episodes):
            raise ContractError("SYS-04: scénario exige trois épisodes L4")
        alternatives = self._scenario_alternatives(*episodes)
        factor_sets = [set(row.structural_factors) for row in alternatives]
        common_factors = tuple(sorted(set.intersection(*factor_sets)))
        outcomes = tuple(
            sorted({row.outcome_ref for row in alternatives if row.outcome_ref})
        )
        if len(common_factors) < self.inducer.policy.minimum_pattern_size or not outcomes:
            raise ContractError("SYS-04: delta épisodique insuffisant")
        support_refs = tuple(
            sorted(
                {
                    ref
                    for alternative in alternatives
                    for ref in alternative.support_artifact_refs
                }
                | {row.artifact_id for row in episodes}
            )
        )
        occurrence = StructuralOccurrence(
            occurrence_ref=scenario_ref,
            structural_factors=common_factors,
            context_refs=(self.context_ref,),
            outcome_refs=outcomes,
            support_refs=support_refs,
        )
        self.inducer.observe(occurrence)
        self.occurrences[scenario_ref] = occurrence
        source_anchors = self._source_anchors(episodes)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="transformation-episode",
                producer_id="transformation-learner",
                producer_build=TRANSFORMATION_BUILD,
                configuration_digest=self.configuration_digest,
                mode=before_episode.mode,
                session_id=before_episode.session_id,
                wave=4,
                parent_ids=tuple(row.artifact_id for row in episodes),
                observation_refs=tuple(
                    ref for row in episodes for ref in row.observation_refs
                ),
                context_refs=(self.context_ref,),
                source_anchors=source_anchors,
                resource_cost={
                    "wall_time_ms": elapsed_ms,
                    "alternative_count": len(alternatives),
                },
                payload_native={
                    "scenario_ref": scenario_ref,
                    "alternatives": [self._alternative_payload(row) for row in alternatives],
                    "structural_factors": list(common_factors),
                    "outcome_refs": list(outcomes),
                },
                payload_projection={"truth_committed": False},
                idempotency_key=f"transformation-episode:{scenario_ref}",
            )
        )
        self.episode_artifacts[scenario_ref] = artifact
        return occurrence, artifact

    def learn(self) -> tuple[CognitiveArtifact, ...]:
        started = time.perf_counter()
        structures = self.inducer.induce()
        artifacts = []
        for structure in structures:
            prototype = self.inducer.materialize_distributed_prototype(
                structure.learned_structure_id,
                core=self.core,
                context_ref=self.context_ref,
            )
            structure = self.inducer.structures[structure.learned_structure_id]
            parents = tuple(
                self.episode_artifacts[ref].artifact_id
                for ref in structure.support_occurrences
            )
            artifact = self.arena.publish(
                ArtifactProposal(
                    artifact_type="learned-transformation",
                    producer_id="transformation-learner",
                    producer_build=TRANSFORMATION_BUILD,
                    configuration_digest=self.configuration_digest,
                    mode=self.arena.get(parents[0]).mode,
                    session_id=self.arena.get(parents[0]).session_id,
                    wave=5,
                    parent_ids=parents,
                    observation_refs=tuple(
                        ref
                        for parent in parents
                        for ref in self.arena.get(parent).observation_refs
                    ),
                    context_refs=(self.context_ref,),
                    source_anchors=self._source_anchors(
                        tuple(self.arena.get(parent) for parent in parents)
                    ),
                    resource_cost={
                        "wall_time_ms": round(
                            (time.perf_counter() - started) * 1000, 3
                        ),
                        "support_count": structure.support_count,
                    },
                    payload_native={
                        "learned_structure_ref": structure.learned_structure_id,
                        "structural_pattern": list(structure.structural_pattern),
                        "support_occurrences": list(structure.support_occurrences),
                        "observed_outcomes": [list(row) for row in structure.observed_outcomes],
                        "exceptions": list(structure.exceptions),
                        "distributed_prototype_ref": prototype.form_id,
                    },
                    payload_projection={"truth_committed": False},
                    idempotency_key=f"learned-transformation:{structure.learned_structure_id}",
                )
            )
            self.learned_artifacts[structure.learned_structure_id] = artifact
            artifacts.append(artifact)
        return tuple(artifacts)

    def predict(
        self,
        learned_artifact: CognitiveArtifact,
        *,
        before_episode: CognitiveArtifact,
        event_episode: CognitiveArtifact,
    ) -> tuple[CognitiveArtifact, CognitiveArtifact]:
        started = time.perf_counter()
        if learned_artifact.artifact_type != "learned-transformation":
            raise ContractError("SYS-04: prédiction exige une structure L5")
        prediction_key = (
            learned_artifact.artifact_id,
            before_episode.artifact_id,
            event_episode.artifact_id,
        )
        if prediction_key in self.predictions:
            return self.predictions[prediction_key]
        learned = thaw_json(learned_artifact.payload_native)
        structure_ref = learned["learned_structure_ref"]
        alternatives = self._partial_alternatives(before_episode, event_episode)
        observed = tuple(
            sorted(set.intersection(*(set(row.structural_factors) for row in alternatives)))
        )
        match = next(
            row for row in self.inducer.match(observed) if row.structure_ref == structure_ref
        )
        qualification = (
            "full-match-with-observed-exceptions"
            if match.full_match and learned["exceptions"]
            else "full-match"
            if match.full_match
            else "partial-match"
        )
        parents = (
            learned_artifact.artifact_id,
            before_episode.artifact_id,
            event_episode.artifact_id,
        )
        contribution = self.arena.publish(
            ArtifactProposal(
                artifact_type="learned-transformation-contribution",
                producer_id="transformation-learner",
                producer_build=TRANSFORMATION_BUILD,
                configuration_digest=self.configuration_digest,
                mode=before_episode.mode,
                session_id=before_episode.session_id,
                wave=6,
                parent_ids=parents,
                observation_refs=before_episode.observation_refs
                + event_episode.observation_refs,
                context_refs=(self.context_ref,),
                source_anchors=self._source_anchors((before_episode, event_episode)),
                resource_cost={
                    "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
                    "alternative_count": len(alternatives),
                },
                payload_native={
                    "learned_structure_ref": structure_ref,
                    "observed_structural_factors": list(observed),
                    "input_alternatives": [
                        self._alternative_payload(row) for row in alternatives
                    ],
                    "matched_factors": list(match.matched_factors),
                    "missing_factors": list(match.missing_factors),
                    "predicted_outcomes": [list(row) for row in match.predicted_outcomes],
                    "qualification": qualification,
                },
                payload_projection={
                    "truth_committed": False,
                    "world_update_performed": False,
                },
                status=ArtifactStatus.SUCCESS if match.full_match else ArtifactStatus.PARTIAL,
                idempotency_key=(
                    f"learned-transformation-contribution:{structure_ref}:"
                    f"{before_episode.artifact_id}:{event_episode.artifact_id}"
                ),
            )
        )
        expectations = [
            {
                "outcome_ref": outcome,
                "confidence": probability,
                "epistemic_status": "expected-not-observed",
                "selected": False,
            }
            for outcome, probability in match.predicted_outcomes
        ]
        expectation_set = self.arena.publish(
            ArtifactProposal(
                artifact_type="transformation-expectation-set",
                producer_id="transformation-learner",
                producer_build=TRANSFORMATION_BUILD,
                configuration_digest=self.configuration_digest,
                mode=contribution.mode,
                session_id=before_episode.session_id,
                wave=7,
                parent_ids=(contribution.artifact_id,),
                observation_refs=contribution.observation_refs,
                context_refs=(self.context_ref,),
                source_anchors=tuple(
                    thaw_json(row) for row in contribution.source_anchors
                ),
                resource_cost={"expectation_count": len(expectations)},
                payload_native={
                    "candidate_ref": contribution.artifact_id,
                    "expectations": expectations,
                    "selected_ref": None,
                },
                payload_projection={
                    "truth_committed": False,
                    "world_update_performed": False,
                },
                idempotency_key=f"transformation-expectation:{contribution.artifact_id}",
            )
        )
        result = (contribution, expectation_set)
        self.predictions[prediction_key] = result
        return result

    def observed_outcomes(
        self,
        *,
        before_episode: CognitiveArtifact,
        event_episode: CognitiveArtifact,
        after_episode: CognitiveArtifact,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    row.outcome_ref
                    for row in self._scenario_alternatives(
                        before_episode, event_episode, after_episode
                    )
                    if row.outcome_ref
                }
            )
        )

    def partial_structural_factors(
        self,
        *,
        before_episode: CognitiveArtifact,
        event_episode: CognitiveArtifact,
    ) -> tuple[str, ...]:
        """Expose the role-normalized factors of a real, not-yet-resolved event.

        SYS-08 uses this public boundary to compare learned structures without
        rebuilding either MRS-derived participants or episodic alignments.
        """
        alternatives = self._partial_alternatives(before_episode, event_episode)
        return tuple(
            sorted(set.intersection(*(set(row.structural_factors) for row in alternatives)))
        )

    def _scenario_alternatives(
        self,
        before_episode: CognitiveArtifact,
        event_episode: CognitiveArtifact,
        after_episode: CognitiveArtifact,
    ) -> tuple[TransformationAlternative, ...]:
        before = self._main_states(before_episode)
        events = self._main_events(event_episode)
        after = self._main_states(after_episode)
        rows = {
            TransformationAlternative(
                event["event_form_ref"],
                event["participant_form_ref"],
                event["participant_bindings"],
                left["state_form_ref"],
                right["state_form_ref"],
                event["event_role_shape"],
                event["modifier_factor_refs"],
                tuple(
                    sorted(
                        set(left["support_artifact_refs"])
                        | set(event["support_artifact_refs"])
                        | set(right["support_artifact_refs"])
                    )
                ),
            )
            for left in before
            for event in events
            for right in after
            if left["participant_form_ref"]
            == event["participant_form_ref"]
            == right["participant_form_ref"]
        }
        if not rows:
            raise ContractError("SYS-04: aucun alignement avant/événement/après")
        return tuple(sorted(rows, key=lambda row: canonical_json(self._alternative_payload(row))))

    def _partial_alternatives(
        self, before_episode: CognitiveArtifact, event_episode: CognitiveArtifact
    ) -> tuple[TransformationAlternative, ...]:
        before = self._main_states(before_episode)
        events = self._main_events(event_episode)
        rows = {
            TransformationAlternative(
                event["event_form_ref"],
                event["participant_form_ref"],
                event["participant_bindings"],
                left["state_form_ref"],
                None,
                event["event_role_shape"],
                event["modifier_factor_refs"],
                tuple(
                    sorted(
                        set(left["support_artifact_refs"])
                        | set(event["support_artifact_refs"])
                    )
                ),
            )
            for left in before
            for event in events
            if left["participant_form_ref"] == event["participant_form_ref"]
        }
        if not rows:
            raise ContractError("SYS-04: aucun alignement avant/événement")
        return tuple(sorted(rows, key=lambda row: canonical_json(self._alternative_payload(row))))

    def _main_states(self, episode: CognitiveArtifact) -> tuple[dict[str, Any], ...]:
        rows = []
        for l2 in self._L2_candidates(episode):
            payload = thaw_json(l2.payload_native)
            index_ref = payload["proposition"]["index_ref"]
            for state in payload["state_candidates"]:
                if state["event_ref"] != index_ref or not state["bearer_ref"]:
                    continue
                for noun in self._entity_forms(payload, state["bearer_ref"]):
                    rows.append(
                        {
                            "state_form_ref": state["state_form_ref"],
                            "participant_form_ref": noun,
                            "support_artifact_refs": self._ancestry_refs(l2),
                        }
                    )
        return self._unique_dicts(rows)

    def _main_events(self, episode: CognitiveArtifact) -> tuple[dict[str, Any], ...]:
        rows = []
        for l2 in self._L2_candidates(episode):
            payload = thaw_json(l2.payload_native)
            index_ref = payload["proposition"]["index_ref"]
            for relation in payload["relations"]:
                bindings = {row["role_ref"]: row["value_ref"] for row in relation["bindings"]}
                if (
                    relation["part_of_speech"] != "v"
                    or bindings.get("ARG0") != index_ref
                    or "ARG2" not in bindings
                ):
                    continue
                patient = bindings["ARG2"]
                modifiers = tuple(
                    sorted(
                        f"patient-facet:external:mrs:{other['predicate']}"
                        for other in payload["relations"]
                        if other["part_of_speech"] == "a"
                        and any(
                            binding["role_ref"] == "ARG1"
                            and binding["value_ref"] == patient
                            for binding in other["bindings"]
                        )
                    )
                )
                participant_bindings = tuple(
                    sorted(
                        (role, form)
                        for role, value_ref in bindings.items()
                        if role != "ARG0"
                        for form in self._entity_forms(payload, value_ref)
                    )
                )
                for noun in self._entity_forms(payload, patient):
                    rows.append(
                        {
                            "event_form_ref": f"external:mrs:{relation['predicate']}",
                            "participant_form_ref": noun,
                            "participant_bindings": participant_bindings,
                            "event_role_shape": tuple(sorted(bindings)),
                            "modifier_factor_refs": modifiers,
                            "support_artifact_refs": self._ancestry_refs(l2),
                        }
                    )
        return self._unique_dicts(rows)

    def _L2_candidates(self, episode: CognitiveArtifact) -> tuple[CognitiveArtifact, ...]:
        if episode.artifact_type != "episode-memory" or len(episode.parent_ids) != 1:
            raise ContractError("SYS-04: mémoire épisodique L4 invalide")
        branch_set = self.arena.get(episode.parent_ids[0])
        payload = thaw_json(branch_set.payload_native)
        return tuple(
            self.arena.get(branch["candidate_ref"])
            for branch in payload["branches"]
        )

    @staticmethod
    def _entity_forms(payload: dict[str, Any], value_ref: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    (
                        f"external:mrs:named:{relation['constant']}"
                        if relation["predicate"] == "named"
                        and isinstance(relation.get("constant"), str)
                        else f"external:mrs:{relation['predicate']}"
                    )
                    for relation in payload["relations"]
                    if (
                        relation["part_of_speech"] in {"n", "u"}
                        or (
                            relation["predicate"] == "named"
                            and isinstance(relation.get("constant"), str)
                        )
                    )
                    and any(
                        binding["role_ref"] == "ARG0"
                        and binding["value_ref"] == value_ref
                        for binding in relation["bindings"]
                    )
                }
            )
        )

    def _ancestry_refs(self, artifact: CognitiveArtifact) -> tuple[str, ...]:
        return tuple(row.artifact_id for row in self.arena.ancestry(artifact.artifact_id))

    @staticmethod
    def _unique_dicts(rows: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
        unique = {canonical_json(row): row for row in rows}
        return tuple(unique[key] for key in sorted(unique))

    @staticmethod
    def _alternative_payload(row: TransformationAlternative) -> dict[str, Any]:
        return {
            "event_form_ref": row.event_form_ref,
            "participant_form_ref": row.participant_form_ref,
            "participant_bindings": [
                {"role_ref": role, "participant_form_ref": form}
                for role, form in row.participant_bindings
            ],
            "before_state_ref": row.before_state_ref,
            "after_state_ref": row.after_state_ref,
            "event_role_shape": list(row.event_role_shape),
            "modifier_factor_refs": list(row.modifier_factor_refs),
            "support_artifact_refs": list(row.support_artifact_refs),
        }

    @staticmethod
    def _source_anchors(rows: Iterable[CognitiveArtifact]) -> tuple[dict[str, Any], ...]:
        anchors = {
            canonical_json(thaw_json(anchor)): thaw_json(anchor)
            for row in rows
            for anchor in row.source_anchors
        }
        return tuple(anchors[key] for key in sorted(anchors))
