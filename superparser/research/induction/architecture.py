"""POC-13: evidence-neutral comparison of induction engine boundaries.

The candidates deliberately share every learned primitive and every measured
quality result.  This module compares topology only: ownership, crossings,
duplication and the blast radius of empirically failing capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


CAPABILITIES = (
    "observation",
    "abstraction",
    "composition",
    "mdl",
    "referents",
    "relations",
    "deltas",
    "transitions",
    "revision",
    "transfer",
    "incremental",
)

DEPENDENCIES = (
    ("observation", "abstraction"),
    ("abstraction", "composition"),
    ("composition", "mdl"),
    ("abstraction", "referents"),
    ("referents", "relations"),
    ("relations", "deltas"),
    ("deltas", "transitions"),
    ("transitions", "revision"),
    ("transitions", "transfer"),
    ("incremental", "abstraction"),
)


@dataclass(frozen=True, slots=True)
class ArchitectureCandidate:
    candidate_id: str
    label: str
    engines: tuple[str, ...]
    ownership: tuple[tuple[str, str], ...]
    rationale: str

    @property
    def owners(self) -> dict[str, str]:
        return dict(self.ownership)

    def validate(self) -> None:
        owners = self.owners
        if set(owners) != set(CAPABILITIES):
            missing = sorted(set(CAPABILITIES) - set(owners))
            extra = sorted(set(owners) - set(CAPABILITIES))
            raise ValueError(f"invalid capability ownership: missing={missing}, extra={extra}")


def default_candidates() -> tuple[ArchitectureCandidate, ...]:
    unified = tuple((capability, "unified") for capability in CAPABILITIES)
    structural = {"observation", "abstraction", "composition", "mdl", "incremental"}
    dual = tuple(
        (capability, "structural" if capability in structural else "inferential")
        for capability in CAPABILITIES
    )
    category = {"referents"}
    relation = {"relations"}
    transformation = {"deltas", "transitions", "revision", "transfer"}
    triple = tuple(
        (
            capability,
            "category"
            if capability in category
            else "relation"
            if capability in relation
            else "transformation"
            if capability in transformation
            else "shared-library",
        )
        for capability in CAPABILITIES
    )
    return (
        ArchitectureCandidate(
            "A", "moteur unique multimode", ("unified",), unified,
            "Une seule frontière d'exécution pour tous les modes.",
        ),
        ArchitectureCandidate(
            "B", "deux moteurs", ("structural", "inferential"), dual,
            "Structure/compression séparées des hypothèses relationnelles et de changement.",
        ),
        ArchitectureCandidate(
            "C", "trois moteurs", ("category", "relation", "transformation"), triple,
            "Catégories, relations et transformations séparées autour d'une bibliothèque commune.",
        ),
    )


def topology_metrics(
    candidate: ArchitectureCandidate,
    *,
    failed_capabilities: Sequence[str],
    dependencies: Sequence[tuple[str, str]] = DEPENDENCIES,
) -> dict[str, object]:
    candidate.validate()
    owners = candidate.owners
    crossings = tuple(
        (source, target)
        for source, target in dependencies
        if owners[source] != owners[target]
    )
    owner_sizes: dict[str, int] = {}
    for owner in owners.values():
        owner_sizes[owner] = owner_sizes.get(owner, 0) + 1
    failure_owners = {owners[name] for name in failed_capabilities}
    # Each primitive has one implementation. A shared library is a dependency,
    # not a copy inside every engine.
    return {
        "engine_count": len(candidate.engines),
        "shared_service_count": len(set(owners.values()) - set(candidate.engines)),
        "cross_engine_dependency_count": len(crossings),
        "cross_engine_dependencies": [list(row) for row in crossings],
        "primitive_implementation_count": len(CAPABILITIES),
        "duplicated_primitive_count": 0,
        "failed_engine_count": len(failure_owners),
        "maximum_failure_blast_radius": max(
            (owner_sizes[owner] for owner in failure_owners), default=0
        ),
    }


def compare_architectures(
    common_measurements: Mapping[str, object],
    *,
    failed_capabilities: Sequence[str] = ("relations", "transitions"),
) -> dict[str, object]:
    """Compare boundaries without changing the empirical measurements."""
    rows = []
    for candidate in default_candidates():
        rows.append(
            {
                "candidate": candidate.candidate_id,
                "label": candidate.label,
                "engines": list(candidate.engines),
                "rationale": candidate.rationale,
                "topology": topology_metrics(
                    candidate, failed_capabilities=failed_capabilities
                ),
                "measurements": dict(common_measurements),
            }
        )
    if any(row["measurements"] != rows[0]["measurements"] for row in rows[1:]):
        raise AssertionError("architectures received unequal empirical evidence")
    return {
        "candidates": rows,
        "provisional_choice": "B",
        "decision_rule": (
            "choose the smallest boundary split that isolates the real-corpus "
            "relation/transition failures from the stable structural path, "
            "without duplicating primitives"
        ),
    }
