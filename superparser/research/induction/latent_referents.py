"""POC-06: explainable latent referent families from substitution signatures."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Sequence


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True, order=True)
class SubstitutionContext:
    component_id: str
    port_id: str

    @property
    def context_id(self) -> str:
        return f"{self.component_id}:{self.port_id}"


@dataclass(frozen=True, slots=True)
class SubstitutionObservation:
    referent_id: str
    component_id: str
    port_id: str
    observation_id: str

    @property
    def context(self) -> SubstitutionContext:
        return SubstitutionContext(self.component_id, self.port_id)


@dataclass(frozen=True, slots=True)
class ReferentSignature:
    referent_id: str
    contexts: tuple[SubstitutionContext, ...]
    occurrence_count: int


@dataclass(frozen=True, slots=True)
class LatentReferentFamily:
    family_id: str
    contexts: tuple[SubstitutionContext, ...]
    members: tuple[str, ...]
    parent_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "contexts": [context.context_id for context in self.contexts],
            "members": list(self.members),
            "parent_id": self.parent_id,
        }


@dataclass(frozen=True, slots=True)
class CompatibilityPrediction:
    context: SubstitutionContext
    referent_ids: tuple[str, ...]
    supporting_families: tuple[str, ...]
    abstained: bool


class LatentReferentModel:
    """Complete-link clustering of port supports, followed by soft membership."""

    def __init__(
        self,
        *,
        context_similarity: float = 0.8,
        membership_ratio: float = 0.5,
        min_contexts: int = 2,
        min_referents: int = 2,
    ) -> None:
        if not 0.0 <= context_similarity <= 1.0:
            raise ValueError("context_similarity must be between zero and one")
        if not 0.0 < membership_ratio <= 1.0:
            raise ValueError("membership_ratio must be in (0, 1]")
        if min_contexts < 2 or min_referents < 2:
            raise ValueError("minimum family sizes must be at least two")
        self.context_similarity = context_similarity
        self.membership_ratio = membership_ratio
        self.min_contexts = min_contexts
        self.min_referents = min_referents
        self.signatures: dict[str, ReferentSignature] = {}
        self.families: tuple[LatentReferentFamily, ...] = ()
        self._context_support: dict[SubstitutionContext, frozenset[str]] = {}

    def fit(self, observations: Sequence[SubstitutionObservation]) -> "LatentReferentModel":
        by_referent: dict[str, set[SubstitutionContext]] = {}
        counts: dict[str, int] = {}
        support: dict[SubstitutionContext, set[str]] = {}
        for row in observations:
            by_referent.setdefault(row.referent_id, set()).add(row.context)
            counts[row.referent_id] = counts.get(row.referent_id, 0) + 1
            support.setdefault(row.context, set()).add(row.referent_id)
        self.signatures = {
            referent: ReferentSignature(referent, tuple(sorted(contexts)), counts[referent])
            for referent, contexts in sorted(by_referent.items())
        }
        self._context_support = {
            context: frozenset(referents) for context, referents in support.items()
        }

        clusters: list[tuple[SubstitutionContext, ...]] = [
            (context,) for context in sorted(support)
        ]
        while True:
            choices: list[tuple[float, tuple[str, ...], int, int]] = []
            for left_index, left in enumerate(clusters):
                for right_index in range(left_index + 1, len(clusters)):
                    right = clusters[right_index]
                    score = min(self._similarity(a, b) for a in left for b in right)
                    if score >= self.context_similarity:
                        names = tuple(context.context_id for context in (*left, *right))
                        choices.append((score, names, left_index, right_index))
            if not choices:
                break
            _, _, left_index, right_index = max(choices, key=lambda row: (row[0], row[1]))
            merged = tuple(sorted((*clusters[left_index], *clusters[right_index])))
            clusters = [
                cluster for index, cluster in enumerate(clusters)
                if index not in {left_index, right_index}
            ]
            clusters.append(merged)
            clusters.sort(key=lambda cluster: tuple(context.context_id for context in cluster))

        families: list[LatentReferentFamily] = []
        for contexts in clusters:
            if len(contexts) < self.min_contexts:
                continue
            required = max(1, math.ceil(len(contexts) * self.membership_ratio))
            members = tuple(
                referent
                for referent, signature in sorted(self.signatures.items())
                if len(set(signature.contexts).intersection(contexts)) >= required
            )
            if len(members) < self.min_referents:
                continue
            body = {
                "contexts": [context.context_id for context in contexts],
                "members": list(members),
            }
            family_id = "referent_family_" + sha256(
                _json(body).encode("utf-8")
            ).hexdigest()[:20]
            families.append(LatentReferentFamily(family_id, contexts, members))

        with_parents = []
        for family in families:
            parents = [
                candidate for candidate in families
                if set(family.members) < set(candidate.members)
            ]
            parent = min(
                parents,
                key=lambda candidate: (len(candidate.members), candidate.family_id),
                default=None,
            )
            with_parents.append(
                replace(family, parent_id=None if parent is None else parent.family_id)
            )
        self.families = tuple(sorted(with_parents, key=lambda family: family.family_id))
        return self

    def families_for(self, referent_id: str) -> tuple[LatentReferentFamily, ...]:
        return tuple(family for family in self.families if referent_id in family.members)

    def predict(self, component_id: str, port_id: str) -> CompatibilityPrediction:
        context = SubstitutionContext(component_id, port_id)
        supporting = tuple(family for family in self.families if context in family.contexts)
        referents = tuple(sorted({member for family in supporting for member in family.members}))
        return CompatibilityPrediction(
            context,
            referents,
            tuple(family.family_id for family in supporting),
            not supporting,
        )

    def _similarity(self, left: SubstitutionContext, right: SubstitutionContext) -> float:
        left_support = self._context_support[left]
        right_support = self._context_support[right]
        union = left_support | right_support
        return len(left_support & right_support) / len(union) if union else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "latent-referent-model/0.1",
            "policy": {
                "context_similarity": self.context_similarity,
                "membership_ratio": self.membership_ratio,
                "min_contexts": self.min_contexts,
                "min_referents": self.min_referents,
            },
            "signatures": [
                {
                    "referent_id": signature.referent_id,
                    "contexts": [context.context_id for context in signature.contexts],
                    "occurrence_count": signature.occurrence_count,
                }
                for signature in self.signatures.values()
            ],
            "families": [family.as_dict() for family in self.families],
        }


def pairwise_family_f1(
    learned: Iterable[Iterable[str]], oracle: Iterable[Iterable[str]]
) -> float:
    """Permutation-invariant pairwise F1, including overlapping families."""
    learned_pairs = _cofamily_pairs(learned)
    oracle_pairs = _cofamily_pairs(oracle)
    if not learned_pairs and not oracle_pairs:
        return 1.0
    true_positive = len(learned_pairs & oracle_pairs)
    precision = true_positive / len(learned_pairs) if learned_pairs else 0.0
    recall = true_positive / len(oracle_pairs) if oracle_pairs else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _cofamily_pairs(families: Iterable[Iterable[str]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for family in families:
        ordered = sorted(set(family))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                pairs.add((left, right))
    return pairs
