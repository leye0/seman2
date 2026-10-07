"""Vocabulaire ouvert et réparations concurrentes sans réécriture de surface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Iterable

from .contracts import ContractError, canonical_json


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"forme ouverte: {name} requis")
    return value


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    rows = tuple(values)
    if len(rows) != len(set(rows)):
        raise ContractError("forme ouverte: références dupliquées")
    return rows


class InterpretationKind(str, Enum):
    VALID_KNOWN = "valid-known"
    NEW_LEXEME = "new-lexeme"
    NEW_INFLECTION = "new-inflection"
    TYPO_REPAIR = "typo-repair"
    AGREEMENT_REPAIR = "agreement-repair"
    TOKENIZATION_REPAIR = "tokenization-repair"
    PROPER_NAME = "proper-name"
    BORROWING = "borrowing"
    CODE_SWITCH = "code-switch"
    DIALECT = "dialect"
    ARTISTIC = "artistic"
    QUOTED_FORM = "quoted-form"


class LexicalAction(str, Enum):
    UNRESOLVED = "unresolved"
    PRESERVE_AS_NEW = "preserve-as-new"
    ALIGN_WITH_KNOWN = "align-with-known"
    PRESERVE_ARTISTIC = "preserve-artistic"


@dataclass(frozen=True)
class ObservedForm:
    observation_ref: str
    context_ref: str
    surface: str
    span_start: int
    span_end: int

    def __post_init__(self) -> None:
        _required(self.observation_ref, "observation_ref")
        _required(self.context_ref, "context_ref")
        _required(self.surface, "surface")
        if self.span_start < 0 or self.span_end <= self.span_start:
            raise ContractError("forme ouverte: span invalide")
        if self.span_end - self.span_start != len(self.surface):
            raise ContractError("forme ouverte: span et surface incohérents")


@dataclass(frozen=True)
class FormEvidence:
    evidence_ref: str
    producer: str
    evidence_kind: str
    value: str
    weight: float
    support_ref: str

    def __post_init__(self) -> None:
        for name in (
            "evidence_ref",
            "producer",
            "evidence_kind",
            "value",
            "support_ref",
        ):
            _required(getattr(self, name), name)
        if not 0.0 <= self.weight <= 1.0:
            raise ContractError("forme ouverte: poids d'évidence hors [0,1]")


@dataclass(frozen=True)
class FormInterpretationCandidate:
    interpretation_ref: str
    kind: InterpretationKind
    proposed_forms: tuple[str, ...]
    category_candidates: tuple[str, ...]
    syntactic_slots: tuple[str, ...]
    semantic_role_slots: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    score: float
    changes_surface: bool

    def __post_init__(self) -> None:
        _required(self.interpretation_ref, "interpretation_ref")
        for name in (
            "proposed_forms",
            "category_candidates",
            "syntactic_slots",
            "semantic_role_slots",
            "evidence_refs",
        ):
            object.__setattr__(self, name, _unique(getattr(self, name)))
        if not self.proposed_forms:
            raise ContractError("interprétation de forme: proposition requise")
        if not 0.0 <= self.score <= 1.0:
            raise ContractError("interprétation de forme: score hors [0,1]")


@dataclass(frozen=True)
class OpenLexicalPlaceholder:
    placeholder_ref: str
    observed: ObservedForm
    phonological_candidates: tuple[str, ...]
    morphological_candidates: tuple[str, ...]
    category_candidates: tuple[str, ...]
    syntactic_slots: tuple[str, ...]
    semantic_role_slots: tuple[str, ...]
    evidence: tuple[FormEvidence, ...]
    interpretations: tuple[FormInterpretationCandidate, ...]

    def __post_init__(self) -> None:
        _required(self.placeholder_ref, "placeholder_ref")
        for name in (
            "phonological_candidates",
            "morphological_candidates",
            "category_candidates",
            "syntactic_slots",
            "semantic_role_slots",
        ):
            object.__setattr__(self, name, _unique(getattr(self, name)))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "interpretations", tuple(self.interpretations))


@dataclass(frozen=True)
class InterpretationDecision:
    selected_ref: str | None
    active_refs: tuple[str, ...]
    action: LexicalAction
    rationale: str
    correction_should_be_said: bool = False


class OpenVocabularyBuilder:
    """Assemble des indices sans décider qu'une forme inconnue est une faute."""

    def build(
        self,
        observed: ObservedForm,
        *,
        evidence: Iterable[FormEvidence] = (),
        interpretations: Iterable[FormInterpretationCandidate] = (),
        phonological_candidates: Iterable[str] = (),
        morphological_candidates: Iterable[str] = (),
        category_candidates: Iterable[str] = (),
        syntactic_slots: Iterable[str] = (),
        semantic_role_slots: Iterable[str] = (),
    ) -> OpenLexicalPlaceholder:
        evidence_tuple = tuple(evidence)
        interpretation_tuple = tuple(
            sorted(interpretations, key=lambda row: (-row.score, row.interpretation_ref))
        )
        known_evidence = {row.evidence_ref for row in evidence_tuple}
        for candidate in interpretation_tuple:
            unknown = set(candidate.evidence_refs) - known_evidence
            if unknown:
                raise ContractError(
                    f"interprétation de forme: évidences absentes {sorted(unknown)}"
                )
        digest = hashlib.sha256(
            canonical_json(
                {
                    "observation_ref": observed.observation_ref,
                    "context_ref": observed.context_ref,
                    "surface": observed.surface,
                    "span": [observed.span_start, observed.span_end],
                }
            ).encode()
        ).hexdigest()
        return OpenLexicalPlaceholder(
            placeholder_ref=f"open-form:{digest[:24]}",
            observed=observed,
            phonological_candidates=_unique(phonological_candidates),
            morphological_candidates=_unique(morphological_candidates),
            category_candidates=_unique(category_candidates),
            syntactic_slots=_unique(syntactic_slots),
            semantic_role_slots=_unique(semantic_role_slots),
            evidence=evidence_tuple,
            interpretations=interpretation_tuple,
        )

    def decide(
        self,
        placeholder: OpenLexicalPlaceholder,
        *,
        minimum_score: float = 0.8,
        minimum_margin: float = 0.2,
        explicit_confirmation_ref: str | None = None,
    ) -> InterpretationDecision:
        active = tuple(row.interpretation_ref for row in placeholder.interpretations)
        if explicit_confirmation_ref:
            selected = next(
                (
                    row
                    for row in placeholder.interpretations
                    if row.interpretation_ref == explicit_confirmation_ref
                ),
                None,
            )
            if selected is None:
                raise ContractError("décision lexicale: confirmation inconnue")
            return InterpretationDecision(
                selected_ref=selected.interpretation_ref,
                active_refs=active,
                action=_action_for(selected.kind),
                rationale="confirmation explicite devenue expérience attribuée",
                correction_should_be_said=False,
            )
        if not placeholder.interpretations:
            return InterpretationDecision(
                selected_ref=None,
                active_refs=(),
                action=LexicalAction.PRESERVE_AS_NEW,
                rationale="aucune analyse disponible; surface conservée comme forme nouvelle",
            )
        best = placeholder.interpretations[0]
        runner_up = (
            placeholder.interpretations[1].score
            if len(placeholder.interpretations) > 1
            else 0.0
        )
        if best.score < minimum_score or best.score - runner_up < minimum_margin:
            return InterpretationDecision(
                selected_ref=None,
                active_refs=active,
                action=LexicalAction.UNRESOLVED,
                rationale="support ou marge insuffisante; alternatives conservées",
            )
        return InterpretationDecision(
            selected_ref=best.interpretation_ref,
            active_refs=active,
            action=_action_for(best.kind),
            rationale="support contextuel suffisant sous les seuils configurés",
            correction_should_be_said=False,
        )


@dataclass(frozen=True)
class SurfaceEdit:
    start: int
    end: int
    observed: str
    replacement: str
    kind: InterpretationKind

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ContractError("réparation de surface: span invalide")
        _required(self.observed, "observed")
        _required(self.replacement, "replacement")


@dataclass(frozen=True)
class UtteranceRepairHypothesis:
    hypothesis_ref: str
    edits: tuple[SurfaceEdit, ...]
    evidence_refs: tuple[str, ...]
    score: float
    interpretation_kind: InterpretationKind

    def __post_init__(self) -> None:
        _required(self.hypothesis_ref, "hypothesis_ref")
        object.__setattr__(self, "edits", tuple(self.edits))
        object.__setattr__(self, "evidence_refs", _unique(self.evidence_refs))
        if not 0.0 <= self.score <= 1.0:
            raise ContractError("réparation de surface: score hors [0,1]")
        previous_end = -1
        for edit in sorted(self.edits, key=lambda row: row.start):
            if edit.start < previous_end:
                raise ContractError("réparation de surface: éditions chevauchantes")
            previous_end = edit.end


class RepairBeam:
    def __init__(
        self,
        observed_text: str,
        hypotheses: Iterable[UtteranceRepairHypothesis],
    ) -> None:
        self.observed_text = _required(observed_text, "observed_text")
        self.hypotheses = tuple(
            sorted(hypotheses, key=lambda row: (-row.score, row.hypothesis_ref))
        )
        for hypothesis in self.hypotheses:
            for edit in hypothesis.edits:
                if self.observed_text[edit.start : edit.end] != edit.observed:
                    raise ContractError(
                        "réparation de surface: l'édition ne correspond pas à l'observation"
                    )

    def render(self, hypothesis_ref: str) -> str:
        try:
            hypothesis = next(
                row for row in self.hypotheses if row.hypothesis_ref == hypothesis_ref
            )
        except StopIteration as exc:
            raise ContractError("réparation de surface: hypothèse absente") from exc
        text = self.observed_text
        for edit in sorted(hypothesis.edits, key=lambda row: row.start, reverse=True):
            text = text[: edit.start] + edit.replacement + text[edit.end :]
        return text


def _action_for(kind: InterpretationKind) -> LexicalAction:
    if kind in {InterpretationKind.NEW_LEXEME, InterpretationKind.NEW_INFLECTION}:
        return LexicalAction.PRESERVE_AS_NEW
    if kind is InterpretationKind.ARTISTIC:
        return LexicalAction.PRESERVE_ARTISTIC
    if kind in {
        InterpretationKind.TYPO_REPAIR,
        InterpretationKind.AGREEMENT_REPAIR,
        InterpretationKind.TOKENIZATION_REPAIR,
    }:
        return LexicalAction.ALIGN_WITH_KNOWN
    return LexicalAction.UNRESOLVED

