"""Curriculum ordonné et évaluations externes sans autorité cognitive."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Mapping

from .contracts import ContractError, canonical_json


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"curriculum: {name} requis")
    return value


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(values)
    if len(result) != len(set(result)):
        raise ContractError("curriculum: références dupliquées")
    return result


@dataclass(frozen=True)
class CurriculumExperience:
    experience_ref: str
    content_digest: str
    capability_tags: tuple[str, ...]
    source_order: int

    def __post_init__(self) -> None:
        _required(self.experience_ref, "experience_ref")
        if len(self.content_digest) != 64:
            raise ContractError("curriculum: content_digest SHA-256 requis")
        object.__setattr__(self, "capability_tags", _unique(self.capability_tags))
        if self.source_order < 0:
            raise ContractError("curriculum: source_order négatif")

    @classmethod
    def from_text(
        cls,
        experience_ref: str,
        text: str,
        capability_tags: Iterable[str],
        source_order: int,
    ) -> "CurriculumExperience":
        return cls(
            experience_ref,
            hashlib.sha256(text.encode()).hexdigest(),
            tuple(capability_tags),
            source_order,
        )


@dataclass(frozen=True)
class EvaluationCriterion:
    criterion_ref: str
    dimension: str
    threshold: float
    weight: float = 1.0
    evaluator_kind: str = "deterministic"

    def __post_init__(self) -> None:
        _required(self.criterion_ref, "criterion_ref")
        _required(self.dimension, "dimension")
        if not 0.0 <= self.threshold <= 1.0:
            raise ContractError("curriculum: seuil hors [0,1]")
        if self.weight <= 0:
            raise ContractError("curriculum: poids positif requis")
        if self.evaluator_kind not in {"deterministic", "external-llm"}:
            raise ContractError("curriculum: type d'évaluateur inconnu")


@dataclass(frozen=True)
class EvaluationProbe:
    probe_ref: str
    content_digest: str
    criterion_refs: tuple[str, ...]
    required_experience_refs: tuple[str, ...]
    capability_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        _required(self.probe_ref, "probe_ref")
        if len(self.content_digest) != 64:
            raise ContractError("curriculum: digest de probe invalide")
        for name in (
            "criterion_refs",
            "required_experience_refs",
            "capability_tags",
        ):
            object.__setattr__(self, name, _unique(getattr(self, name)))

    @classmethod
    def from_text(
        cls,
        probe_ref: str,
        text: str,
        criterion_refs: Iterable[str],
        required_experience_refs: Iterable[str],
        capability_tags: Iterable[str],
    ) -> "EvaluationProbe":
        return cls(
            probe_ref,
            hashlib.sha256(text.encode()).hexdigest(),
            tuple(criterion_refs),
            tuple(required_experience_refs),
            tuple(capability_tags),
        )


@dataclass(frozen=True)
class CurriculumStage:
    stage_ref: str
    prerequisite_stage_refs: tuple[str, ...]
    experience_refs: tuple[str, ...]
    probe_refs: tuple[str, ...]
    criterion_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _required(self.stage_ref, "stage_ref")
        for name in (
            "prerequisite_stage_refs",
            "experience_refs",
            "probe_refs",
            "criterion_refs",
        ):
            object.__setattr__(self, name, _unique(getattr(self, name)))


@dataclass(frozen=True)
class EvaluationRecord:
    evaluation_ref: str
    stage_ref: str
    probe_ref: str
    evaluator: str
    criterion_scores: tuple[tuple[str, float], ...]
    evidence_refs: tuple[str, ...]
    rubric_digest: str
    runtime_write_performed: bool = False


@dataclass(frozen=True)
class StageDecision:
    stage_ref: str
    promoted: bool
    failed_criteria: tuple[str, ...]
    reinforcement_tags: tuple[str, ...]
    evaluation_refs: tuple[str, ...]
    rationale: str


class CurriculumController:
    """Registre append-only; l'évaluateur ne reçoit aucune méthode de mutation."""

    def __init__(
        self,
        *,
        experiences: Iterable[CurriculumExperience],
        criteria: Iterable[EvaluationCriterion],
        probes: Iterable[EvaluationProbe],
        stages: Iterable[CurriculumStage],
    ) -> None:
        self.experiences = _index(experiences, "experience_ref")
        self.criteria = _index(criteria, "criterion_ref")
        self.probes = _index(probes, "probe_ref")
        self.stages = _index(stages, "stage_ref")
        self.presented_experience_refs: list[str] = []
        self.completed_stage_refs: list[str] = []
        self.evaluations: list[EvaluationRecord] = []
        self._validate_plan()
        self.rubric_digest = hashlib.sha256(
            canonical_json(
                [
                    {
                        "criterion_ref": row.criterion_ref,
                        "dimension": row.dimension,
                        "threshold": row.threshold,
                        "weight": row.weight,
                        "evaluator_kind": row.evaluator_kind,
                    }
                    for row in sorted(
                        self.criteria.values(), key=lambda item: item.criterion_ref
                    )
                ]
            ).encode()
        ).hexdigest()

    def present(self, experience_ref: str) -> CurriculumExperience:
        try:
            experience = self.experiences[experience_ref]
        except KeyError as exc:
            raise ContractError("curriculum: expérience non planifiée") from exc
        if experience_ref not in self.presented_experience_refs:
            self.presented_experience_refs.append(experience_ref)
        return experience

    def available_probe(self, probe_ref: str) -> EvaluationProbe:
        try:
            probe = self.probes[probe_ref]
        except KeyError as exc:
            raise ContractError("curriculum: probe inconnu") from exc
        missing = set(probe.required_experience_refs) - set(
            self.presented_experience_refs
        )
        if missing:
            raise ContractError(
                f"curriculum: le tuteur ne peut questionner un contenu non ingéré: {sorted(missing)}"
            )
        return probe

    def record_evaluation(
        self,
        *,
        stage_ref: str,
        probe_ref: str,
        evaluator: str,
        criterion_scores: Mapping[str, float],
        evidence_refs: Iterable[str],
    ) -> EvaluationRecord:
        _required(evaluator, "evaluator")
        stage = self._stage(stage_ref)
        probe = self.available_probe(probe_ref)
        allowed = set(stage.criterion_refs) & set(probe.criterion_refs)
        if set(criterion_scores) != allowed:
            raise ContractError(
                "curriculum: les scores doivent correspondre exactement aux critères préenregistrés"
            )
        for criterion_ref, score in criterion_scores.items():
            if criterion_ref not in self.criteria or not 0.0 <= score <= 1.0:
                raise ContractError("curriculum: score ou critère invalide")
        identifier = hashlib.sha256(
            canonical_json(
                {
                    "stage_ref": stage_ref,
                    "probe_ref": probe_ref,
                    "evaluator": evaluator,
                    "criterion_scores": sorted(criterion_scores.items()),
                    "ordinal": len(self.evaluations),
                }
            ).encode()
        ).hexdigest()
        record = EvaluationRecord(
            evaluation_ref=f"evaluation:{identifier[:24]}",
            stage_ref=stage_ref,
            probe_ref=probe_ref,
            evaluator=evaluator,
            criterion_scores=tuple(sorted(criterion_scores.items())),
            evidence_refs=_unique(evidence_refs),
            rubric_digest=self.rubric_digest,
            runtime_write_performed=False,
        )
        self.evaluations.append(record)
        return record

    def decide_stage(self, stage_ref: str) -> StageDecision:
        stage = self._stage(stage_ref)
        missing_prerequisites = set(stage.prerequisite_stage_refs) - set(
            self.completed_stage_refs
        )
        if missing_prerequisites:
            raise ContractError(
                f"curriculum: prérequis incomplets {sorted(missing_prerequisites)}"
            )
        records = [row for row in self.evaluations if row.stage_ref == stage_ref]
        evaluated_probes = {row.probe_ref for row in records}
        if evaluated_probes != set(stage.probe_refs):
            raise ContractError("curriculum: probes du stage incomplets")
        score_by_criterion: dict[str, list[float]] = {
            ref: [] for ref in stage.criterion_refs
        }
        for record in records:
            for criterion_ref, score in record.criterion_scores:
                score_by_criterion[criterion_ref].append(score)
        failed = tuple(
            sorted(
                criterion_ref
                for criterion_ref, scores in score_by_criterion.items()
                if not scores
                or sum(scores) / len(scores)
                < self.criteria[criterion_ref].threshold
            )
        )
        promoted = not failed
        if promoted and stage_ref not in self.completed_stage_refs:
            self.completed_stage_refs.append(stage_ref)
        reinforcement = tuple(
            sorted(
                {
                    tag
                    for probe_ref in stage.probe_refs
                    for tag in self.probes[probe_ref].capability_tags
                    if failed
                    and set(self.probes[probe_ref].criterion_refs) & set(failed)
                }
            )
        )
        return StageDecision(
            stage_ref=stage_ref,
            promoted=promoted,
            failed_criteria=failed,
            reinforcement_tags=reinforcement,
            evaluation_refs=tuple(row.evaluation_ref for row in records),
            rationale=(
                "tous les seuils préenregistrés sont atteints"
                if promoted
                else "renforcement ciblé requis avant une nouvelle évaluation"
            ),
        )

    def _stage(self, stage_ref: str) -> CurriculumStage:
        try:
            return self.stages[stage_ref]
        except KeyError as exc:
            raise ContractError("curriculum: stage inconnu") from exc

    def _validate_plan(self) -> None:
        experience_digests = {row.content_digest for row in self.experiences.values()}
        for probe in self.probes.values():
            if probe.content_digest in experience_digests:
                raise ContractError("curriculum: fuite d'un probe dans les expériences")
            if unknown := set(probe.criterion_refs) - set(self.criteria):
                raise ContractError(f"curriculum: critères de probe inconnus {unknown}")
            if unknown := set(probe.required_experience_refs) - set(self.experiences):
                raise ContractError(f"curriculum: expériences requises inconnues {unknown}")
        for stage in self.stages.values():
            if unknown := set(stage.experience_refs) - set(self.experiences):
                raise ContractError(f"curriculum: expériences de stage inconnues {unknown}")
            if unknown := set(stage.probe_refs) - set(self.probes):
                raise ContractError(f"curriculum: probes de stage inconnus {unknown}")
            if unknown := set(stage.criterion_refs) - set(self.criteria):
                raise ContractError(f"curriculum: critères de stage inconnus {unknown}")
            if unknown := set(stage.prerequisite_stage_refs) - set(self.stages):
                raise ContractError(f"curriculum: stages prérequis inconnus {unknown}")
            for probe_ref in stage.probe_refs:
                probe = self.probes[probe_ref]
                if not set(probe.criterion_refs) <= set(stage.criterion_refs):
                    raise ContractError("curriculum: probe hors grille du stage")


def _index(rows: Iterable[object], key: str) -> dict[str, object]:
    result = {}
    for row in rows:
        identifier = getattr(row, key)
        if identifier in result:
            raise ContractError(f"curriculum: identifiant dupliqué {identifier}")
        result[identifier] = row
    return result

