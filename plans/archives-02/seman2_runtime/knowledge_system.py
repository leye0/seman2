"""Admission L3→L4 depuis des branches réellement composées."""

from __future__ import annotations

import hashlib
import time
from typing import Iterable

from .cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactStatus,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    CognitiveArtifact,
    thaw_json,
)
from .contracts import ContractError, canonical_json
from .developmental_core import (
    ContextFrame,
    ContextKind,
    DevelopmentalCore,
    FormFactor,
    RoleBinding,
)
from .formal_composition import register_composition_types
from .hypothesis_system import register_hypothesis_types
from .low_level_system import register_low_level_types
from .semantic_admission import (
    AdmissionProjection,
    EvidenceOccurrence,
    EvidencePolarity,
    SemanticAdmissionLedger,
    SemanticCandidate,
)


KNOWLEDGE_BUILD = "active-L3-to-L4-admission"


def register_knowledge_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "episode-memory",
            "seman2/active/L4/episode-memory",
            4,
            allowed_producers=frozenset({"knowledge-admission"}),
            parent_types=frozenset({"situation-branch-set"}),
            required_native_fields=frozenset(
                {"experience_ref", "observation_ref", "candidate_refs", "memory_item"}
            ),
            required_projection_fields=frozenset({"cognitively_accessible"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "memory-admission",
            "seman2/active/L4/memory-admission",
            4,
            allowed_producers=frozenset({"knowledge-admission"}),
            parent_types=frozenset({"situation-branch-set"}),
            required_native_fields=frozenset(
                {
                    "semantic_candidate_ref",
                    "assessment",
                    "relation_occurrence_ref",
                    "distributed_form_ref",
                    "memory_item",
                }
            ),
            required_projection_fields=frozenset({"cognitively_accessible"}),
        )
    )


def build_knowledge_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    register_composition_types(registry)
    register_hypothesis_types(registry)
    register_knowledge_types(registry)
    registry.freeze()
    return registry


class KnowledgeAdmissionEngine:
    """Extrait des relations grammaticales de L3, puis consolide dans L4."""

    def __init__(
        self,
        arena: ArtifactArena,
        *,
        context_ref: str = "ctx:model",
        vector_dimension: int = 256,
    ) -> None:
        self.arena = arena
        self.context_ref = context_ref
        self.ledger = SemanticAdmissionLedger()
        self.core = DevelopmentalCore(vector_dimension=vector_dimension)
        self.core.universe.add_context(ContextFrame(context_ref, ContextKind.CURRENT))
        self._candidate_parents: dict[str, set[str]] = {}
        self._observed_branch_sets: dict[str, tuple[str, ...]] = {}
        self._episode_artifacts: dict[str, CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "input": "situation-branch-set",
                    "composition": "generic-copular-class-predication",
                    "minimum_independent_experiences": 2,
                    "context_ref": context_ref,
                }
            ).encode()
        ).hexdigest()

    def observe(self, branch_set: CognitiveArtifact) -> tuple[str, ...]:
        started = time.perf_counter()
        if branch_set.artifact_type != "situation-branch-set":
            raise ContractError("SYS-03: admission exige un stock L3")
        if branch_set.artifact_id in self._observed_branch_sets:
            return self._observed_branch_sets[branch_set.artifact_id]
        payload = thaw_json(branch_set.payload_native)
        if len(branch_set.observation_refs) != 1:
            raise ContractError("SYS-03: expérience L3 absente ou ambiguë")
        experience_ref = branch_set.observation_refs[0]
        observation_ref = payload["observation_ref"]
        candidate_refs: set[str] = set()
        active_l2_refs = tuple(
            branch["candidate_ref"] for branch in payload["branches"]
        )
        for l2_ref in active_l2_refs:
            l2 = self.arena.get(l2_ref)
            if (
                l2.artifact_type != "composed-candidate"
                or l2.status is not ArtifactStatus.SUCCESS
            ):
                raise ContractError("SYS-03: branche L3 pointe hors L2")
            l2_payload = thaw_json(l2.payload_native)
            relations = l2_payload["relations"]
            by_arg0: dict[str, list[dict]] = {}
            for relation in relations:
                arguments = {
                    binding["role_ref"]: binding["source_value"]
                    for binding in relation["bindings"]
                }
                if "ARG0" in arguments:
                    by_arg0.setdefault(arguments["ARG0"], []).append(relation)
            for relation in relations:
                if relation["predicate"] != "_be_v_id":
                    continue
                arguments = {
                    binding["role_ref"]: binding["source_value"]
                    for binding in relation["bindings"]
                }
                subject = arguments.get("ARG1")
                complement = arguments.get("ARG2")
                if not subject or not complement:
                    continue
                subject_nouns = [
                    row for row in by_arg0.get(subject, ()) if row["part_of_speech"] == "n"
                ]
                complement_nouns = [
                    row
                    for row in by_arg0.get(complement, ())
                    if row["part_of_speech"] == "n"
                ]
                for subject_noun in subject_nouns:
                    for complement_noun in complement_nouns:
                        bindings = (
                            RoleBinding(
                                "subject",
                                f"concept-form:external:mrs:{subject_noun['predicate']}",
                            ),
                            RoleBinding(
                                "class",
                                f"concept-form:external:mrs:{complement_noun['predicate']}",
                            ),
                        )
                        signature = {
                            "relation_form_ref": "relation:kind-of",
                            "bindings": [
                                {"role_ref": row.role_ref, "value_ref": row.value_ref}
                                for row in bindings
                            ],
                            "context_ref": self.context_ref,
                        }
                        candidate_ref = _stable_ref("semantic-candidate", signature)
                        candidate = SemanticCandidate(
                            candidate_ref,
                            "relation:kind-of",
                            bindings,
                            self.context_ref,
                        )
                        self.ledger.register_candidate(candidate)
                        evidence_ref = _stable_ref(
                            "evidence",
                            {
                                "candidate_ref": candidate_ref,
                                "experience_ref": experience_ref,
                                "L3_ref": branch_set.artifact_id,
                                "L2_ref": l2_ref,
                            },
                        )
                        self.ledger.observe(
                            EvidenceOccurrence(
                                evidence_ref=evidence_ref,
                                candidate_ref=candidate_ref,
                                experience_ref=experience_ref,
                                analysis_ref=l2.parent_ids[0],
                                source_ref=branch_set.artifact_id,
                                polarity=EvidencePolarity.SUPPORT,
                                weight=1.0,
                                evidence_kind="L3-grammatical-composition",
                                artifact_path_refs=self._artifact_path(
                                    branch_set, l2
                                ),
                            )
                        )
                        self._candidate_parents.setdefault(candidate_ref, set()).add(
                            branch_set.artifact_id
                        )
                        candidate_refs.add(candidate_ref)
        result = tuple(sorted(candidate_refs))
        episode_ref = f"episode:{branch_set.artifact_id}"
        episode_item = self.core.memory.remember(
            episode_ref,
            kind="linguistic-episode",
            features=(
                "source:L3-situation",
                f"branch-count:{len(payload['branches'])}",
                *(f"candidate:{ref}" for ref in result),
            ),
            context_refs=(self.context_ref,),
            support_refs=(branch_set.artifact_id,),
            distinctiveness=0.5,
            utility=0.25,
            situation_bound=False,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        episode_artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="episode-memory",
                producer_id="knowledge-admission",
                producer_build=KNOWLEDGE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=branch_set.mode,
                session_id=branch_set.session_id,
                wave=4,
                parent_ids=(branch_set.artifact_id,),
                observation_refs=(experience_ref,),
                context_refs=(self.context_ref,),
                source_anchors=tuple(
                    thaw_json(row) for row in branch_set.source_anchors
                ),
                resource_cost={
                    "wall_time_ms": elapsed_ms,
                    "L3_branches": len(payload["branches"]),
                    "semantic_candidates": len(result),
                },
                payload_native={
                    "experience_ref": experience_ref,
                    "observation_ref": observation_ref,
                    "candidate_refs": list(result),
                    "memory_item": self._memory_item_payload(episode_item),
                },
                payload_projection={"cognitively_accessible": True},
                idempotency_key=f"episode-memory:{branch_set.artifact_id}",
            )
        )
        self._observed_branch_sets[branch_set.artifact_id] = result
        self._episode_artifacts[branch_set.artifact_id] = episode_artifact
        return result

    def project(self, candidate_ref: str, *, temporal_index: int) -> tuple[AdmissionProjection, CognitiveArtifact]:
        started = time.perf_counter()
        projection = self.ledger.project(
            self.core, candidate_ref, temporal_index=temporal_index
        )
        relation = self.core.universe.relations[projection.relation_occurrence_ref]
        factors = [
            FormFactor(
                factor_ref=f"factor:{relation.relation_occurrence_id}:relation",
                value_ref=relation.relation_form_ref,
                context_ref=relation.context_ref,
                role_ref="relation",
                support_refs=relation.support_refs,
            )
        ]
        factors.extend(
            FormFactor(
                factor_ref=f"factor:{relation.relation_occurrence_id}:{binding.role_ref}",
                value_ref=binding.value_ref,
                context_ref=relation.context_ref,
                role_ref=binding.role_ref,
                support_refs=relation.support_refs,
            )
            for binding in relation.bindings
        )
        distributed_form_ref = f"form:{relation.relation_occurrence_id}"
        distributed = self.core.encode_form(distributed_form_ref, factors)
        memory_item = self.core.memory.get(relation.relation_occurrence_id)
        assessment = projection.assessment
        parent_refs = tuple(sorted(self._candidate_parents[candidate_ref]))
        source_anchors = {
            canonical_json(thaw_json(anchor)): thaw_json(anchor)
            for parent_ref in parent_refs
            for anchor in self.arena.get(parent_ref).source_anchors
        }
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="memory-admission",
                producer_id="knowledge-admission",
                producer_build=KNOWLEDGE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=self.arena.get(parent_refs[0]).mode,
                session_id=next(
                    iter(self.arena.get(ref).session_id for ref in parent_refs)
                ),
                wave=4,
                parent_ids=parent_refs,
                observation_refs=assessment.independent_support_experiences,
                context_refs=(self.context_ref,),
                source_anchors=tuple(source_anchors[key] for key in sorted(source_anchors)),
                resource_cost={
                    "wall_time_ms": elapsed_ms,
                    "supporting_experiences": len(
                        assessment.independent_support_experiences
                    ),
                    "distributed_dimensions": self.core.forms.dimension,
                },
                payload_native={
                    "semantic_candidate_ref": candidate_ref,
                    "assessment": {
                        "status": assessment.status.value,
                        "independent_support_experiences": list(
                            assessment.independent_support_experiences
                        ),
                        "support_weight": assessment.support_weight,
                        "evidence_refs": list(assessment.evidence_refs),
                    },
                    "relation_occurrence_ref": relation.relation_occurrence_id,
                    "relation_support_artifact_refs": list(relation.support_refs),
                    "distributed_form_ref": distributed.form_id,
                    "distributed_factor_refs": [row.factor_ref for row in distributed.factors],
                    "memory_item": {
                        "content_ref": memory_item.content_ref,
                        "tier": memory_item.tier.value,
                        "features": list(memory_item.features),
                        "support_refs": list(memory_item.support_refs),
                    },
                    "episode_memory_artifact_refs": [
                        self._episode_artifacts[parent].artifact_id
                        for parent in parent_refs
                    ],
                },
                payload_projection={"cognitively_accessible": True},
                idempotency_key=(
                    f"memory-admission:{candidate_ref}:"
                    f"{len(projection.previous_projection_refs)}"
                ),
            )
        )
        return projection, artifact

    def _artifact_path(
        self, branch_set: CognitiveArtifact, l2: CognitiveArtifact
    ) -> tuple[str, ...]:
        l1 = self.arena.get(l2.parent_ids[0])
        observation = self.arena.get(l1.parent_ids[0])
        experience = self.arena.get(observation.parent_ids[0])
        return (
            branch_set.artifact_id,
            l2.artifact_id,
            l1.artifact_id,
            observation.artifact_id,
            experience.artifact_id,
        )

    @staticmethod
    def _memory_item_payload(item: object) -> dict[str, object]:
        return {
            "content_ref": item.content_ref,
            "kind": item.kind,
            "tier": item.tier.value,
            "features": list(item.features),
            "context_refs": list(item.context_refs),
            "support_refs": list(item.support_refs),
            "strength": item.strength,
            "exposures": item.exposures,
        }


def _stable_ref(prefix: str, value: object) -> str:
    digest = hashlib.sha256(canonical_json(value).encode()).hexdigest()
    return f"{prefix}:{digest[:24]}"
