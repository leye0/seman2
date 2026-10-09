"""Induction structuraliste minimale sur occurrences relationnelles.

Le moteur ne connaît aucun nom de concept. Il extrait des invariants de petits
ensembles d'occurrences, conserve les outcomes et propose des spécialisations
quand une structure trop générale masque des comportements divergents.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import itertools
from typing import Iterable

from .contracts import ContractError, canonical_json
from .developmental_core import DevelopmentalCore, DistributedForm, FormFactor


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"induction: {name} requis")
    return value


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(sorted(set(values)))
    if not result:
        raise ContractError("induction: collection vide")
    return result


def _structure_id(pattern: tuple[str, ...]) -> str:
    digest = hashlib.sha256(canonical_json(list(pattern)).encode()).hexdigest()
    return f"learned:{digest[:24]}"


@dataclass(frozen=True)
class InductionPolicy:
    minimum_support: int = 2
    minimum_pattern_size: int = 2
    minimum_specialization_support: int = 2
    maximum_structures: int = 128

    def __post_init__(self) -> None:
        for name in (
            "minimum_support",
            "minimum_pattern_size",
            "minimum_specialization_support",
            "maximum_structures",
        ):
            if getattr(self, name) < 1:
                raise ContractError(f"induction: {name} doit être positif")


@dataclass(frozen=True)
class StructuralOccurrence:
    occurrence_ref: str
    structural_factors: tuple[str, ...]
    context_refs: tuple[str, ...]
    outcome_refs: tuple[str, ...]
    support_refs: tuple[str, ...]
    distributed_form_ref: str | None = None

    def __post_init__(self) -> None:
        _required(self.occurrence_ref, "occurrence_ref")
        object.__setattr__(
            self, "structural_factors", _sorted_unique(self.structural_factors)
        )
        object.__setattr__(self, "context_refs", _sorted_unique(self.context_refs))
        object.__setattr__(self, "outcome_refs", _sorted_unique(self.outcome_refs))
        object.__setattr__(self, "support_refs", _sorted_unique(self.support_refs))


@dataclass(frozen=True)
class LearnedStructure:
    learned_structure_id: str
    structural_pattern: tuple[str, ...]
    support_occurrences: tuple[str, ...]
    exceptions: tuple[str, ...]
    contexts_of_use: tuple[str, ...]
    observed_outcomes: tuple[tuple[str, int], ...]
    specializations: tuple[str, ...]
    generalizations: tuple[str, ...]
    activation_history: tuple[int, ...]
    distributed_prototype_ref: str | None = None

    @property
    def support_count(self) -> int:
        return len(self.support_occurrences)


@dataclass(frozen=True)
class StructureMatch:
    structure_ref: str
    coverage: float
    full_match: bool
    matched_factors: tuple[str, ...]
    missing_factors: tuple[str, ...]
    predicted_outcomes: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class SpecializationProposal:
    parent_structure_ref: str
    outcome_ref: str
    differentiating_pattern: tuple[str, ...]
    support_occurrences: tuple[str, ...]
    support_count: int


class ConceptInducer:
    """Petit inducteur explicable destiné aux gates, pas à l'échelle corpus."""

    def __init__(self, policy: InductionPolicy | None = None) -> None:
        self.policy = policy or InductionPolicy()
        self.occurrences: dict[str, StructuralOccurrence] = {}
        self.structures: dict[str, LearnedStructure] = {}

    def observe(self, occurrence: StructuralOccurrence) -> None:
        existing = self.occurrences.get(occurrence.occurrence_ref)
        if existing and existing != occurrence:
            raise ContractError("induction: occurrence en conflit")
        self.occurrences[occurrence.occurrence_ref] = occurrence

    def induce(self) -> tuple[LearnedStructure, ...]:
        occurrences = tuple(
            self.occurrences[key] for key in sorted(self.occurrences)
        )
        patterns: set[tuple[str, ...]] = set()
        for left, right in itertools.combinations(occurrences, 2):
            common = tuple(
                sorted(set(left.structural_factors) & set(right.structural_factors))
            )
            if len(common) >= self.policy.minimum_pattern_size:
                patterns.add(common)

        candidates: list[tuple[tuple[str, ...], tuple[StructuralOccurrence, ...]]] = []
        for pattern in patterns:
            pattern_set = set(pattern)
            support = tuple(
                row
                for row in occurrences
                if pattern_set <= set(row.structural_factors)
            )
            if len(support) >= self.policy.minimum_support:
                candidates.append((pattern, support))

        # Pour un même ensemble de supports, la description la plus précise est
        # conservée. Les généralisations qui couvrent réellement plus de cas
        # restent donc disponibles.
        maximal: dict[tuple[str, ...], tuple[tuple[str, ...], tuple[StructuralOccurrence, ...]]] = {}
        for pattern, support in candidates:
            support_key = tuple(row.occurrence_ref for row in support)
            current = maximal.get(support_key)
            if current is None or len(pattern) > len(current[0]):
                maximal[support_key] = (pattern, support)

        ranked = sorted(
            maximal.values(),
            key=lambda item: (
                -(len(item[0]) * len(item[1])),
                -len(item[1]),
                item[0],
            ),
        )[: self.policy.maximum_structures]

        rebuilt: dict[str, LearnedStructure] = {}
        for pattern, support in ranked:
            identifier = _structure_id(pattern)
            outcome_counts: dict[str, int] = {}
            for row in support:
                for outcome in row.outcome_refs:
                    outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
            existing = self.structures.get(identifier)
            dominant_outcome = min(
                outcome_counts,
                key=lambda outcome: (-outcome_counts[outcome], outcome),
            )
            exceptions = tuple(
                row.occurrence_ref
                for row in support
                if dominant_outcome not in row.outcome_refs
            )
            rebuilt[identifier] = LearnedStructure(
                learned_structure_id=identifier,
                structural_pattern=pattern,
                support_occurrences=tuple(row.occurrence_ref for row in support),
                exceptions=exceptions,
                contexts_of_use=tuple(
                    sorted({context for row in support for context in row.context_refs})
                ),
                observed_outcomes=tuple(sorted(outcome_counts.items())),
                specializations=existing.specializations if existing else (),
                generalizations=existing.generalizations if existing else (),
                activation_history=(
                    (existing.activation_history if existing else ()) + (len(support),)
                ),
                distributed_prototype_ref=(
                    existing.distributed_prototype_ref if existing else None
                ),
            )
        self.structures = rebuilt
        self._link_generalizations()
        return tuple(self.structures[key] for key in sorted(self.structures))

    def match(self, structural_factors: Iterable[str]) -> tuple[StructureMatch, ...]:
        observed = set(structural_factors)
        matches = []
        for structure in self.structures.values():
            pattern = set(structure.structural_pattern)
            matched = pattern & observed
            coverage = len(matched) / len(pattern)
            total_outcomes = sum(count for _, count in structure.observed_outcomes)
            predictions = tuple(
                (outcome, count / total_outcomes)
                for outcome, count in structure.observed_outcomes
            )
            matches.append(
                StructureMatch(
                    structure_ref=structure.learned_structure_id,
                    coverage=coverage,
                    full_match=pattern <= observed,
                    matched_factors=tuple(sorted(matched)),
                    missing_factors=tuple(sorted(pattern - observed)),
                    predicted_outcomes=predictions,
                )
            )
        matches.sort(
            key=lambda row: (
                not row.full_match,
                -row.coverage,
                -len(row.matched_factors),
                row.structure_ref,
            )
        )
        return tuple(matches)

    def propose_specializations(
        self, structure_ref: str
    ) -> tuple[SpecializationProposal, ...]:
        try:
            structure = self.structures[structure_ref]
        except KeyError as exc:
            raise ContractError(f"induction: structure absente {structure_ref}") from exc
        support = [self.occurrences[ref] for ref in structure.support_occurrences]
        outcomes = sorted({outcome for row in support for outcome in row.outcome_refs})
        proposals = []
        parent_pattern = set(structure.structural_pattern)
        for outcome in outcomes:
            group = [row for row in support if outcome in row.outcome_refs]
            if len(group) < self.policy.minimum_specialization_support:
                continue
            common = set(group[0].structural_factors)
            for row in group[1:]:
                common &= set(row.structural_factors)
            differentiating = tuple(sorted(common - parent_pattern))
            if not differentiating:
                continue
            proposals.append(
                SpecializationProposal(
                    parent_structure_ref=structure_ref,
                    outcome_ref=outcome,
                    differentiating_pattern=differentiating,
                    support_occurrences=tuple(row.occurrence_ref for row in group),
                    support_count=len(group),
                )
            )
        return tuple(proposals)

    def materialize_distributed_prototype(
        self,
        structure_ref: str,
        *,
        core: DevelopmentalCore,
        context_ref: str,
    ) -> DistributedForm:
        try:
            structure = self.structures[structure_ref]
        except KeyError as exc:
            raise ContractError(f"induction: structure absente {structure_ref}") from exc
        form_ref = f"form:{structure_ref}"
        form = core.encode_form(
            form_ref,
            tuple(
                FormFactor(
                    factor_ref=f"{structure_ref}:factor:{index}",
                    value_ref=factor,
                    context_ref=context_ref,
                    role_ref="structural-factor",
                    position=index,
                    support_refs=structure.support_occurrences,
                )
                for index, factor in enumerate(structure.structural_pattern)
            ),
        )
        core.memory.remember(
            structure_ref,
            kind="learned-structure",
            features=structure.structural_pattern,
            context_refs=structure.contexts_of_use,
            support_refs=structure.support_occurrences,
            distinctiveness=min(1.0, len(structure.structural_pattern) / 8.0),
        )
        self.structures[structure_ref] = LearnedStructure(
            **{
                **structure.__dict__,
                "distributed_prototype_ref": form_ref,
            }
        )
        return form

    def _link_generalizations(self) -> None:
        rows = list(self.structures.values())
        specializations: dict[str, set[str]] = {row.learned_structure_id: set() for row in rows}
        generalizations: dict[str, set[str]] = {row.learned_structure_id: set() for row in rows}
        for general, specific in itertools.permutations(rows, 2):
            general_pattern = set(general.structural_pattern)
            specific_pattern = set(specific.structural_pattern)
            if general_pattern < specific_pattern:
                specializations[general.learned_structure_id].add(
                    specific.learned_structure_id
                )
                generalizations[specific.learned_structure_id].add(
                    general.learned_structure_id
                )
        for identifier, structure in tuple(self.structures.items()):
            self.structures[identifier] = LearnedStructure(
                **{
                    **structure.__dict__,
                    "specializations": tuple(sorted(specializations[identifier])),
                    "generalizations": tuple(sorted(generalizations[identifier])),
                }
            )
