"""Domain-free level-3 records.

The vocabulary in this module is architectural: it describes graph mechanics,
not learned categories of language or the world.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Derivation:
    algorithm: str
    version: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    inputs: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "version": self.version,
            "parameters": dict(self.parameters),
            "inputs": list(self.inputs),
        }


@dataclass(frozen=True, slots=True)
class LearnedStructure:
    structure_id: str
    family: str
    fingerprint: str
    payload: Mapping[str, Any]
    derivation: Derivation
    score: float | None = None
    parent_id: str | None = None
    created_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.structure_id,
            "family": self.family,
            "fingerprint": self.fingerprint,
            "payload": dict(self.payload),
            "derivation": self.derivation.as_dict(),
            "score": self.score,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class LearnedRelation:
    relation_id: str
    source_id: str
    target_id: str
    relation: str
    payload: Mapping[str, Any]
    derivation: Derivation
    created_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.relation_id,
            "source": self.source_id,
            "target": self.target_id,
            "relation": self.relation,
            "payload": dict(self.payload),
            "derivation": self.derivation.as_dict(),
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class Support:
    structure_id: str
    evidence_id: str
    analysis_id: str | None = None
    hypothesis_id: str | None = None
    span: Mapping[str, Any] | None = None
    weight: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "structure_id": self.structure_id,
            "evidence_id": self.evidence_id,
            "analysis_id": self.analysis_id,
            "hypothesis_id": self.hypothesis_id,
            "span": dict(self.span) if self.span is not None else None,
            "weight": self.weight,
        }
