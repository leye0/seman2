"""Plans de réponse produits exclusivement depuis l'état cognitif acquis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .contracts import ContractError
from .developmental_core import (
    DevelopmentalCore,
    EpistemicState,
    QueryResult,
    RoleBinding,
)


class AnswerStatus(str, Enum):
    SUPPORTED = "supported"
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"
    ATTRIBUTED = "attributed"
    HYPOTHETICAL = "hypothetical"
    CONTESTED = "contested"


@dataclass(frozen=True)
class RelationalQuestion:
    question_ref: str
    relation_form_ref: str
    known_bindings: tuple[RoleBinding, ...]
    requested_role_ref: str
    context_ref: str

    def __post_init__(self) -> None:
        for name in (
            "question_ref",
            "relation_form_ref",
            "requested_role_ref",
            "context_ref",
        ):
            if not getattr(self, name):
                raise ContractError(f"question cognitive: {name} requis")
        object.__setattr__(self, "known_bindings", tuple(self.known_bindings))


@dataclass(frozen=True)
class StateQuestion:
    question_ref: str
    bearer_ref: str
    dimension_ref: str
    context_ref: str
    at: int | None = None


@dataclass(frozen=True)
class AnswerPlan:
    question_ref: str
    status: AnswerStatus
    value_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    context_ref: str
    communicative_act: str
    epistemic_qualification: str
    explanation_path: tuple[str, ...]
    external_source_consulted: bool = False


class AutobiographicalResponder:
    """Interroge le modèle vivant; ne possède aucune référence aux corpus."""

    def __init__(self, core: DevelopmentalCore) -> None:
        self.core = core

    def answer_relation(self, question: RelationalQuestion) -> AnswerPlan:
        relations = self.core.universe.query_relations(
            relation_form_ref=question.relation_form_ref,
            required_bindings=question.known_bindings,
            context_ref=question.context_ref,
        )
        accessible = tuple(
            relation
            for relation in relations
            if self.core.memory.accessible(relation.relation_occurrence_id)
        )
        values: dict[str, list[str]] = {}
        for relation in accessible:
            for binding in relation.bindings:
                if binding.role_ref == question.requested_role_ref:
                    values.setdefault(binding.value_ref, []).append(
                        relation.relation_occurrence_id
                    )
        if not values:
            return self._unknown(question.question_ref, question.context_ref)

        evidence = tuple(sorted({ref for refs in values.values() for ref in refs}))
        states = {
            self.core.universe.relations[ref].epistemic_state for ref in evidence
        }
        status, qualification = _answer_epistemic_status(states, len(values))
        return AnswerPlan(
            question_ref=question.question_ref,
            status=status,
            value_refs=tuple(sorted(values)),
            evidence_refs=evidence,
            context_ref=question.context_ref,
            communicative_act="answer",
            epistemic_qualification=qualification,
            explanation_path=(
                f"query:{question.relation_form_ref}",
                *(f"evidence:{ref}" for ref in evidence),
            ),
        )

    def answer_state(self, question: StateQuestion) -> AnswerPlan:
        result = self.core.universe.current_state(
            bearer_ref=question.bearer_ref,
            dimension_ref=question.dimension_ref,
            context_ref=question.context_ref,
            at=question.at,
        )
        accessible_evidence = tuple(
            ref for ref in result.evidence_refs if self.core.memory.accessible(ref)
        )
        if not accessible_evidence:
            return self._unknown(question.question_ref, question.context_ref)
        accessible_values = tuple(
            sorted(
                {
                    self.core.universe.states[ref].value_ref
                    for ref in accessible_evidence
                }
            )
        )
        status = (
            AnswerStatus.SUPPORTED
            if result.status == "supported" and len(accessible_values) == 1
            else AnswerStatus.AMBIGUOUS
        )
        return AnswerPlan(
            question_ref=question.question_ref,
            status=status,
            value_refs=accessible_values,
            evidence_refs=accessible_evidence,
            context_ref=question.context_ref,
            communicative_act="answer",
            epistemic_qualification=(
                "supported-by-accessible-state"
                if status is AnswerStatus.SUPPORTED
                else "multiple-accessible-states"
            ),
            explanation_path=(
                f"state:{question.bearer_ref}:{question.dimension_ref}",
                *(f"evidence:{ref}" for ref in accessible_evidence),
            ),
        )

    @staticmethod
    def _unknown(question_ref: str, context_ref: str) -> AnswerPlan:
        return AnswerPlan(
            question_ref=question_ref,
            status=AnswerStatus.UNKNOWN,
            value_refs=(),
            evidence_refs=(),
            context_ref=context_ref,
            communicative_act="acknowledge-ignorance",
            epistemic_qualification="no-accessible-internal-support",
            explanation_path=("no-accessible-internal-path",),
            external_source_consulted=False,
        )


def _answer_epistemic_status(
    states: Iterable[EpistemicState], value_count: int
) -> tuple[AnswerStatus, str]:
    state_set = set(states)
    if value_count > 1:
        return AnswerStatus.AMBIGUOUS, "multiple-supported-values"
    if EpistemicState.CONTESTED in state_set:
        return AnswerStatus.CONTESTED, "contested-in-memory"
    if state_set <= {EpistemicState.ATTRIBUTED}:
        return AnswerStatus.ATTRIBUTED, "according-to-attributed-source"
    if state_set <= {EpistemicState.HYPOTHESIS, EpistemicState.EXPECTED}:
        return AnswerStatus.HYPOTHETICAL, "hypothesis-or-expectation-only"
    return AnswerStatus.SUPPORTED, "supported-by-accessible-experience"

