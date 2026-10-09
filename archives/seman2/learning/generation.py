"""Reverse use of learned semantic/structural alignments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .fragments import instantiate, linearize, parse_bracketed
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
    mode: str = "retrieve"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.candidate_id,
            "surface": self.surface,
            "structure": dict(self.structure),
            "bindings": dict(self.bindings),
            "support": list(self.support),
            "score": dict(self.score),
            "mode": self.mode,
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
        modes: Sequence[str] = ("retrieve", "instantiate"),
    ) -> tuple[GenerationCandidate, ...]:
        target_fingerprint = exact_fingerprint(target)
        candidates: list[GenerationCandidate] = []
        if "retrieve" in modes:
            candidates.extend(
                self._retrieve(target, target_fingerprint, context=context, bindings=bindings)
            )
        if "instantiate" in modes:
            candidates.extend(
                self._instantiate(
                    target,
                    target_fingerprint,
                    context=context,
                    bindings=bindings,
                )
            )
        candidates.sort(key=lambda row: (-float(row.score["total"]), row.candidate_id))
        return tuple(candidates[:limit])

    def _retrieve(
        self,
        target: Mapping[str, Any],
        target_fingerprint: str,
        *,
        context: Mapping[str, Any] | None,
        bindings: Mapping[str, Any] | None,
    ) -> list[GenerationCandidate]:
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
                "mode": "retrieve",
            }
            candidate = GenerationCandidate(
                candidate_id=digest("generation", identity),
                surface=surface,
                structure=structural.payload,
                bindings=dict(bindings or {}),
                support=supports,
                score=score,
                mode="retrieve",
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
        return candidates

    def _instantiate(
        self,
        target: Mapping[str, Any],
        target_fingerprint: str,
        *,
        context: Mapping[str, Any] | None,
        bindings: Mapping[str, Any] | None,
    ) -> list[GenerationCandidate]:
        """Recombine learned complex segments into surfaces not observed as a whole."""
        requested = dict(bindings or {})
        fragments = self.store.structures(family="dop-fragment")
        matches = self.store.structures(family="fragment-match")
        observed_bindings: dict[str, list[dict[str, Any]]] = {}
        for row in matches:
            observed_bindings.setdefault(row.payload.get("fragment", ""), []).append(
                dict(row.payload.get("bindings") or {})
            )
        candidates: list[GenerationCandidate] = []
        for fragment_row in fragments:
            source = fragment_row.payload.get("fragment")
            if not isinstance(source, str) or not source:
                continue
            try:
                pattern = parse_bracketed(source)
            except ValueError:
                continue
            slot_values = self._slot_candidates(source, observed_bindings, requested)
            if not slot_values:
                continue
            for combined in _cartesian_bindings(slot_values):
                filled = instantiate(pattern, combined)
                surface = linearize(filled)
                if not surface:
                    continue
                supports = tuple(
                    row["evidence_id"] for row in self.store.supports(fragment_row.structure_id)
                )
                compatibility = structural_similarity(target, {"surface": surface})
                context_fit = structural_similarity(context or {}, {})
                score = rank_components(
                    compatibility=compatibility,
                    support=len(supports),
                    context_fit=context_fit,
                )
                score["novelty"] = 1.0
                identity = {
                    "target": target_fingerprint,
                    "structure": fragment_row.structure_id,
                    "bindings": dict(sorted(combined.items())),
                    "mode": "instantiate",
                }
                candidate = GenerationCandidate(
                    candidate_id=digest("generation", identity),
                    surface=surface,
                    structure={"fragment": source, "bindings": dict(combined)},
                    bindings=dict(combined),
                    support=supports,
                    score=score,
                    mode="instantiate",
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
        return candidates

    @staticmethod
    def _slot_candidates(
        source: str,
        observed_bindings: Mapping[str, Sequence[Mapping[str, Any]]],
        requested: Mapping[str, Any],
    ) -> dict[str, list[Any]]:
        per_slot: dict[str, set[str]] = {}
        for row in observed_bindings.get(source, ()):
            for slot, value in row.items():
                if isinstance(value, str) and value:
                    per_slot.setdefault(slot, set()).add(value)
        for slot, value in requested.items():
            if isinstance(value, str) and value:
                per_slot.setdefault(slot, set()).add(value)
        return {slot: sorted(values) for slot, values in per_slot.items()}


def _cartesian_bindings(
    slot_values: Mapping[str, Sequence[Any]],
    *,
    cap: int = 32,
) -> list[dict[str, Any]]:
    """Bounded product of observed slot fillers; never invents lexical items."""
    slots = sorted(slot_values)
    if not slots:
        return []
    combinations: list[dict[str, Any]] = [{}]
    for slot in slots:
        next_round: list[dict[str, Any]] = []
        values = list(slot_values[slot])
        for base in combinations:
            for value in values:
                if len(next_round) >= cap:
                    break
                next_round.append({**base, slot: value})
            if len(next_round) >= cap:
                break
        combinations = next_round
        if not combinations:
            break
    return combinations
