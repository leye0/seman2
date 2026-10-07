"""Reverse use of learned semantic/structural alignments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .ranking import rank_components, structural_similarity
from .store import LearningStore
from .structures import digest, exact_fingerprint


@dataclass(frozen=True, slots=True)
class GenerationCandidate:
    candidate_id: str
    surface: str
    structure: Mapping[str, Any]
    bindings: Mapping[str, Any]
    support: tuple[str, ...]
    score: Mapping[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.candidate_id,
            "surface": self.surface,
            "structure": dict(self.structure),
            "bindings": dict(self.bindings),
            "support": list(self.support),
            "score": dict(self.score),
        }


def _surface_from_projection(payload: Mapping[str, Any]) -> str:
    projection = payload.get("projection", payload)
    if not isinstance(projection, Mapping):
        return ""
    words: list[tuple[int, str]] = []
    for raw_node in projection.get("nodes", []):
        if not isinstance(raw_node, Mapping) or raw_node.get("category") != "parser-word":
            continue
        attributes = raw_node.get("attributes", {})
        if not isinstance(attributes, Mapping):
            continue
        try:
            position = int(attributes.get("position", len(words)))
        except (TypeError, ValueError):
            position = len(words)
        value = attributes.get("surface", attributes.get("value", ""))
        if isinstance(value, str) and value:
            words.append((position, value))
    result = ""
    no_leading_space = set(".,;:!?)]}")
    for _, word in sorted(words):
        if not result or word[:1] in no_leading_space:
            result += word
        else:
            result += " " + word
    return result


class Generator:
    def __init__(self, store: LearningStore) -> None:
        self.store = store

    def generate(
        self,
        target: Mapping[str, Any],
        *,
        context: Mapping[str, Any] | None = None,
        bindings: Mapping[str, Any] | None = None,
        limit: int = 10,
    ) -> tuple[GenerationCandidate, ...]:
        target_fingerprint = exact_fingerprint(target)
        semantic_rows = self.store.structures(family="semantic-observation")
        structural_rows = self.store.structures(family="structural-observation")
        structural_by_key = {
            (
                row.payload.get("analysis_id"),
                row.payload.get("hypothesis_id"),
            ): row
            for row in structural_rows
        }
        candidates: list[GenerationCandidate] = []
        for semantic in semantic_rows:
            key = (
                semantic.payload.get("analysis_id"),
                semantic.payload.get("hypothesis_id"),
            )
            structural = structural_by_key.get(key)
            if structural is None:
                continue
            semantic_projection = semantic.payload.get("projection", {})
            compatibility = structural_similarity(target, semantic_projection)
            surface = _surface_from_projection(structural.payload)
            if not surface:
                continue
            supports = tuple(
                row["evidence_id"] for row in self.store.supports(structural.structure_id)
            )
            context_fit = structural_similarity(context or {}, semantic.payload.get("context", {}))
            score = rank_components(
                compatibility=compatibility,
                support=len(supports),
                context_fit=context_fit,
            )
            identity = {
                "target": target_fingerprint,
                "structure": structural.structure_id,
                "bindings": dict(bindings or {}),
            }
            candidate = GenerationCandidate(
                candidate_id=digest("generation", identity),
                surface=surface,
                structure=structural.payload,
                bindings=dict(bindings or {}),
                support=supports,
                score=score,
            )
            self.store.put_generation(
                candidate.candidate_id,
                target_fingerprint=target_fingerprint,
                surface=candidate.surface,
                structure=candidate.structure,
                bindings=candidate.bindings,
                support=candidate.support,
                score=candidate.score,
            )
            candidates.append(candidate)
        candidates.sort(key=lambda row: (-float(row.score["total"]), row.candidate_id))
        return tuple(candidates[:limit])
