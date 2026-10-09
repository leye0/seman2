"""POC-07: domain-scoped hypotheses between opaque relations."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class RelationObservation:
    scenario_id: str
    domain_id: str
    source_id: str
    target_id: str
    relation_id: str
    truth: bool


@dataclass(frozen=True, slots=True)
class RelationHypothesis:
    hypothesis_id: str
    kind: str
    domain_id: str
    left_relation: str
    right_relation: str
    support: int
    evaluated: int
    opportunities: int
    confidence: float
    calibrated_confidence: float
    coverage: float
    contradictions: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "kind": self.kind,
            "domain_id": self.domain_id,
            "left_relation": self.left_relation,
            "right_relation": self.right_relation,
            "support": self.support,
            "evaluated": self.evaluated,
            "opportunities": self.opportunities,
            "confidence": self.confidence,
            "calibrated_confidence": self.calibrated_confidence,
            "coverage": self.coverage,
            "contradictions": self.contradictions,
        }


@dataclass(frozen=True, slots=True)
class RelationPrediction:
    scenario_id: str
    domain_id: str
    source_id: str
    target_id: str
    relation_id: str
    truth: bool
    hypothesis_id: str
    confidence: float


@dataclass(frozen=True, slots=True)
class _Evidence:
    support: int
    evaluated: int
    opportunities: int

    @property
    def contradictions(self) -> int:
        return self.evaluated - self.support

    @property
    def confidence(self) -> float:
        return self.support / self.evaluated if self.evaluated else 0.0

    @property
    def coverage(self) -> float:
        return self.evaluated / self.opportunities if self.opportunities else 0.0


class LatentRelationModel:
    def __init__(
        self,
        *,
        min_support: int = 6,
        min_confidence: float = 0.95,
        min_coverage: float = 0.5,
        min_calibrated_confidence: float = 0.55,
    ) -> None:
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_coverage = min_coverage
        self.min_calibrated_confidence = min_calibrated_confidence
        self.hypotheses: tuple[RelationHypothesis, ...] = ()

    def fit(self, observations: Sequence[RelationObservation]) -> "LatentRelationModel":
        index = {
            (row.scenario_id, row.domain_id, row.source_id, row.target_id, row.relation_id): row.truth
            for row in observations
        }
        domains: dict[str, set[str]] = {}
        rows_by_domain: dict[str, list[RelationObservation]] = {}
        for row in observations:
            domains.setdefault(row.domain_id, set()).add(row.relation_id)
            rows_by_domain.setdefault(row.domain_id, []).append(row)

        hypotheses: list[RelationHypothesis] = []
        for domain, relations in sorted(domains.items()):
            rows = rows_by_domain[domain]
            implication: dict[tuple[str, str], _Evidence] = {}
            inverse: dict[tuple[str, str], _Evidence] = {}
            for left in sorted(relations):
                for right in sorted(relations - {left}):
                    implication[left, right] = self._evidence(rows, index, left, right, False, True)
                    inverse[left, right] = self._evidence(rows, index, left, right, True, True)

            equivalent_pairs: set[frozenset[str]] = set()
            inverse_pairs: set[frozenset[str]] = set()
            for left in sorted(relations):
                for right in sorted(relation for relation in relations if relation > left):
                    forward = implication[left, right]
                    backward = implication[right, left]
                    if self._accepted(forward) and self._accepted(backward):
                        hypotheses.append(self._hypothesis("EQUIVALENT", domain, left, right, _combine(forward, backward)))
                        equivalent_pairs.add(frozenset((left, right)))
                    forward_inverse = inverse[left, right]
                    backward_inverse = inverse[right, left]
                    if self._accepted(forward_inverse) and self._accepted(backward_inverse):
                        hypotheses.append(self._hypothesis("INVERSE", domain, left, right, _combine(forward_inverse, backward_inverse)))
                        inverse_pairs.add(frozenset((left, right)))

                    incompatible = _combine(
                        self._evidence(rows, index, left, right, False, False),
                        self._evidence(rows, index, right, left, False, False),
                    )
                    if self._accepted(incompatible):
                        hypotheses.append(self._hypothesis("INCOMPATIBLE", domain, left, right, incompatible))

            for (left, right), evidence in implication.items():
                if frozenset((left, right)) in equivalent_pairs:
                    continue
                if self._accepted(evidence):
                    hypotheses.append(self._hypothesis("IMPLIES", domain, left, right, evidence))

        unique = {hypothesis.hypothesis_id: hypothesis for hypothesis in hypotheses}
        self.hypotheses = tuple(sorted(unique.values(), key=lambda row: row.hypothesis_id))
        return self

    def predict(self, observation: RelationObservation) -> tuple[RelationPrediction, ...]:
        if not observation.truth:
            return ()
        predictions: dict[tuple[str, str, str, bool], RelationPrediction] = {}
        for hypothesis in self.hypotheses:
            if hypothesis.domain_id != observation.domain_id:
                continue
            relation = None
            source, target = observation.source_id, observation.target_id
            truth = True
            if hypothesis.kind == "IMPLIES" and hypothesis.left_relation == observation.relation_id:
                relation = hypothesis.right_relation
            elif hypothesis.kind == "EQUIVALENT" and observation.relation_id in {
                hypothesis.left_relation, hypothesis.right_relation
            }:
                relation = (
                    hypothesis.right_relation
                    if observation.relation_id == hypothesis.left_relation
                    else hypothesis.left_relation
                )
            elif hypothesis.kind == "INVERSE" and observation.relation_id in {
                hypothesis.left_relation, hypothesis.right_relation
            }:
                relation = (
                    hypothesis.right_relation
                    if observation.relation_id == hypothesis.left_relation
                    else hypothesis.left_relation
                )
                source, target = target, source
            elif hypothesis.kind == "INCOMPATIBLE" and observation.relation_id in {
                hypothesis.left_relation, hypothesis.right_relation
            }:
                relation = (
                    hypothesis.right_relation
                    if observation.relation_id == hypothesis.left_relation
                    else hypothesis.left_relation
                )
                truth = False
            if relation is None:
                continue
            prediction = RelationPrediction(
                observation.scenario_id,
                observation.domain_id,
                source,
                target,
                relation,
                truth,
                hypothesis.hypothesis_id,
                hypothesis.calibrated_confidence,
            )
            predictions[source, target, relation, truth] = prediction
        return tuple(sorted(predictions.values(), key=lambda row: (row.relation_id, row.source_id, row.target_id, row.truth)))

    def _evidence(self, rows, index, left, right, reverse, expected):
        anchors = [row for row in rows if row.relation_id == left and row.truth]
        support = evaluated = 0
        for row in anchors:
            source, target = (row.target_id, row.source_id) if reverse else (row.source_id, row.target_id)
            value = index.get((row.scenario_id, row.domain_id, source, target, right))
            if value is None:
                continue
            evaluated += 1
            support += value is expected
        return _Evidence(support, evaluated, len(anchors))

    def _accepted(self, evidence: _Evidence) -> bool:
        return (
            evidence.support >= self.min_support
            and evidence.confidence >= self.min_confidence
            and evidence.coverage >= self.min_coverage
            and _wilson_lower(evidence.support, evidence.evaluated) >= self.min_calibrated_confidence
        )

    def _hypothesis(self, kind, domain, left, right, evidence):
        body = [kind, domain, left, right]
        return RelationHypothesis(
            "relation_hypothesis_" + sha256(json.dumps(body).encode()).hexdigest()[:20],
            kind,
            domain,
            left,
            right,
            evidence.support,
            evidence.evaluated,
            evidence.opportunities,
            evidence.confidence,
            _wilson_lower(evidence.support, evidence.evaluated),
            evidence.coverage,
            evidence.contradictions,
        )


def _combine(left: _Evidence, right: _Evidence) -> _Evidence:
    return _Evidence(
        left.support + right.support,
        left.evaluated + right.evaluated,
        left.opportunities + right.opportunities,
    )


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator
