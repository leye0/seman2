"""Admission épistémique de structures candidates dans la mémoire sémantique."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Iterable

from .contracts import ContractError, canonical_json
from .developmental_core import (
    DevelopmentalCore,
    EpistemicState,
    Polarity,
    RelationOccurrence,
    RoleBinding,
)


class EvidencePolarity(str, Enum):
    SUPPORT = "support"
    CONTRADICTION = "contradiction"


class AdmissionStatus(str, Enum):
    PENDING = "pending"
    CONSOLIDATED = "consolidated"
    CONTESTED = "contested"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class AdmissionPolicy:
    minimum_independent_experiences: int = 2
    minimum_support_weight: float = 1.5
    maximum_contradiction_ratio: float = 0.25

    def __post_init__(self) -> None:
        if self.minimum_independent_experiences < 1:
            raise ContractError("admission: nombre d'expériences invalide")
        if self.minimum_support_weight <= 0:
            raise ContractError("admission: support minimal invalide")
        if not 0.0 <= self.maximum_contradiction_ratio <= 1.0:
            raise ContractError("admission: ratio de contradiction invalide")


@dataclass(frozen=True)
class SemanticCandidate:
    candidate_ref: str
    relation_form_ref: str
    bindings: tuple[RoleBinding, ...]
    context_scope_ref: str

    def __post_init__(self) -> None:
        if not self.candidate_ref or not self.relation_form_ref or not self.context_scope_ref:
            raise ContractError("admission: candidat incomplet")
        object.__setattr__(self, "bindings", tuple(self.bindings))
        if not self.bindings:
            raise ContractError("admission: bindings requis")


@dataclass(frozen=True)
class EvidenceOccurrence:
    evidence_ref: str
    candidate_ref: str
    experience_ref: str
    analysis_ref: str
    source_ref: str
    polarity: EvidencePolarity
    weight: float
    evidence_kind: str
    artifact_path_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "evidence_ref",
            "candidate_ref",
            "experience_ref",
            "analysis_ref",
            "source_ref",
            "evidence_kind",
        ):
            if not getattr(self, name):
                raise ContractError(f"admission: {name} requis")
        if not 0.0 < self.weight <= 1.0:
            raise ContractError("admission: poids hors ]0,1]")
        object.__setattr__(self, "artifact_path_refs", tuple(self.artifact_path_refs))
        if len(set(self.artifact_path_refs)) != len(self.artifact_path_refs):
            raise ContractError("admission: chemin d'artefacts dupliqué")


@dataclass(frozen=True)
class AdmissionAssessment:
    candidate_ref: str
    status: AdmissionStatus
    independent_support_experiences: tuple[str, ...]
    independent_contradiction_experiences: tuple[str, ...]
    support_weight: float
    contradiction_weight: float
    contradiction_ratio: float
    evidence_refs: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class AdmissionProjection:
    candidate_ref: str
    assessment: AdmissionAssessment
    relation_occurrence_ref: str
    previous_projection_refs: tuple[str, ...]


class SemanticAdmissionLedger:
    def __init__(self, policy: AdmissionPolicy | None = None) -> None:
        self.policy = policy or AdmissionPolicy()
        self.candidates: dict[str, SemanticCandidate] = {}
        self.evidence: dict[str, EvidenceOccurrence] = {}
        self.assessment_history: dict[str, list[AdmissionAssessment]] = {}
        self.projections: dict[str, list[str]] = {}

    def register_candidate(self, candidate: SemanticCandidate) -> None:
        existing = self.candidates.get(candidate.candidate_ref)
        if existing and existing != candidate:
            raise ContractError("admission: candidat en conflit")
        self.candidates[candidate.candidate_ref] = candidate

    def observe(self, evidence: EvidenceOccurrence) -> None:
        if evidence.candidate_ref not in self.candidates:
            raise ContractError("admission: candidat absent")
        existing = self.evidence.get(evidence.evidence_ref)
        if existing and existing != evidence:
            raise ContractError("admission: évidence en conflit")
        self.evidence[evidence.evidence_ref] = evidence

    def assess(self, candidate_ref: str) -> AdmissionAssessment:
        if candidate_ref not in self.candidates:
            raise ContractError("admission: candidat absent")
        rows = sorted(
            (row for row in self.evidence.values() if row.candidate_ref == candidate_ref),
            key=lambda row: row.evidence_ref,
        )
        support_by_experience = _max_weight_by_experience(
            row for row in rows if row.polarity is EvidencePolarity.SUPPORT
        )
        contradiction_by_experience = _max_weight_by_experience(
            row for row in rows if row.polarity is EvidencePolarity.CONTRADICTION
        )
        support_weight = sum(support_by_experience.values())
        contradiction_weight = sum(contradiction_by_experience.values())
        total = support_weight + contradiction_weight
        ratio = contradiction_weight / total if total else 0.0
        if not rows:
            status = AdmissionStatus.INSUFFICIENT
            rationale = "aucune évidence"
        elif contradiction_by_experience and ratio > self.policy.maximum_contradiction_ratio:
            status = AdmissionStatus.CONTESTED
            rationale = "contradictions indépendantes au-dessus du seuil"
        elif (
            len(support_by_experience) >= self.policy.minimum_independent_experiences
            and support_weight >= self.policy.minimum_support_weight
        ):
            status = AdmissionStatus.CONSOLIDATED
            rationale = "support indépendant suffisant"
        else:
            status = AdmissionStatus.PENDING
            rationale = "davantage d'expériences indépendantes sont requises"
        assessment = AdmissionAssessment(
            candidate_ref=candidate_ref,
            status=status,
            independent_support_experiences=tuple(sorted(support_by_experience)),
            independent_contradiction_experiences=tuple(
                sorted(contradiction_by_experience)
            ),
            support_weight=support_weight,
            contradiction_weight=contradiction_weight,
            contradiction_ratio=ratio,
            evidence_refs=tuple(row.evidence_ref for row in rows),
            rationale=rationale,
        )
        history = self.assessment_history.setdefault(candidate_ref, [])
        if not history or history[-1] != assessment:
            history.append(assessment)
        return assessment

    def project(
        self,
        core: DevelopmentalCore,
        candidate_ref: str,
        *,
        temporal_index: int,
    ) -> AdmissionProjection:
        candidate = self.candidates[candidate_ref]
        assessment = self.assess(candidate_ref)
        if assessment.status not in {
            AdmissionStatus.CONSOLIDATED,
            AdmissionStatus.CONTESTED,
        }:
            raise ContractError("admission: structure non admissible")
        prior = tuple(self.projections.get(candidate_ref, ()))
        support_rows = tuple(
            row
            for row in self.evidence.values()
            if row.candidate_ref == candidate_ref
            and row.polarity is EvidencePolarity.SUPPORT
        )
        contradiction_rows = tuple(
            row
            for row in self.evidence.values()
            if row.candidate_ref == candidate_ref
            and row.polarity is EvidencePolarity.CONTRADICTION
        )
        support_artifact_refs = tuple(
            sorted(
                {
                    ref
                    for row in support_rows
                    for ref in (row.artifact_path_refs or (row.source_ref,))
                }
            )
        )
        contradiction_artifact_refs = tuple(
            sorted(
                {
                    ref
                    for row in contradiction_rows
                    for ref in (row.artifact_path_refs or (row.source_ref,))
                }
            )
        )
        digest = hashlib.sha256(
            canonical_json(
                {
                    "candidate_ref": candidate_ref,
                    "status": assessment.status.value,
                    "evidence_refs": assessment.evidence_refs,
                    "ordinal": len(prior),
                }
            ).encode()
        ).hexdigest()
        relation_ref = f"admitted-relation:{digest[:24]}"
        core.universe.add_relation(
            RelationOccurrence(
                relation_occurrence_id=relation_ref,
                relation_form_ref=candidate.relation_form_ref,
                bindings=candidate.bindings,
                context_ref=candidate.context_scope_ref,
                temporal_index=temporal_index,
                polarity=Polarity.POSITIVE,
                modality="learned",
                attribution_ref=None,
                support_refs=support_artifact_refs,
                contradiction_refs=contradiction_artifact_refs,
                epistemic_state=(
                    EpistemicState.CONSOLIDATED
                    if assessment.status is AdmissionStatus.CONSOLIDATED
                    else EpistemicState.CONTESTED
                ),
            )
        )
        core.memory.remember(
            relation_ref,
            kind="semantic-relation",
            features=(
                candidate.relation_form_ref,
                *(f"{row.role_ref}:{row.value_ref}" for row in candidate.bindings),
                f"status:{assessment.status.value}",
            ),
            context_refs=(candidate.context_scope_ref,),
            support_refs=support_artifact_refs,
            distinctiveness=0.8,
            utility=0.5,
        )
        self.projections.setdefault(candidate_ref, []).append(relation_ref)
        return AdmissionProjection(candidate_ref, assessment, relation_ref, prior)


def _max_weight_by_experience(
    rows: Iterable[EvidenceOccurrence],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        result[row.experience_ref] = max(result.get(row.experience_ref, 0.0), row.weight)
    return result
