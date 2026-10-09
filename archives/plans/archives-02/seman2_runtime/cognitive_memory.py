"""Mémoire cognitive bornée, graduelle et distincte du journal d'audit.

Les objets de ce module sont les contenus encore accessibles au modèle. Une
source brute ou un journal expérimental ne peut pas être enregistré comme tier
spécial et ne participe jamais au retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Any, Iterable, Mapping

from .contracts import ContractError


def _nonempty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"mémoire: {name} requis")
    return value


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(values)
    if len(result) != len(set(result)):
        raise ContractError("mémoire: références dupliquées")
    return result


class MemoryTier(str, Enum):
    FOCAL = "focal"
    PERIPHERAL = "peripheral"
    SITUATION = "situation"
    INTERMEDIATE = "intermediate"
    LONG_TERM = "long-term"
    FORGOTTEN = "forgotten"


@dataclass(frozen=True)
class MemoryPolicy:
    focal_capacity: int = 7
    peripheral_capacity: int = 32
    situation_capacity: int = 48
    intermediate_capacity: int = 256
    long_term_capacity: int = 10_000
    consolidation_strength: float = 2.4
    consolidation_exposures: int = 3
    activation_decay: float = 0.82
    strength_decay: float = 0.995
    forgetting_strength: float = 0.12

    def __post_init__(self) -> None:
        for name in (
            "focal_capacity",
            "peripheral_capacity",
            "situation_capacity",
            "intermediate_capacity",
            "long_term_capacity",
        ):
            if getattr(self, name) < 1:
                raise ContractError(f"mémoire: {name} doit être positif")
        if self.consolidation_exposures < 1:
            raise ContractError("mémoire: consolidation_exposures doit être positif")
        for name in ("activation_decay", "strength_decay"):
            value = getattr(self, name)
            if not 0.0 < value <= 1.0:
                raise ContractError(f"mémoire: {name} hors ]0,1]")
        if self.consolidation_strength <= 0 or self.forgetting_strength < 0:
            raise ContractError("mémoire: seuils invalides")


@dataclass(frozen=True)
class MemoryItem:
    content_ref: str
    kind: str
    tier: MemoryTier
    features: tuple[str, ...]
    context_refs: tuple[str, ...]
    support_refs: tuple[str, ...]
    activation: float
    strength: float
    exposures: int
    distinctiveness: float
    utility: float
    created_step: int
    last_touched_step: int
    forgotten_step: int | None = None
    forgetting_reason: str | None = None

    def __post_init__(self) -> None:
        _nonempty(self.content_ref, "content_ref")
        _nonempty(self.kind, "kind")
        object.__setattr__(self, "features", _unique(self.features))
        object.__setattr__(self, "context_refs", _unique(self.context_refs))
        object.__setattr__(self, "support_refs", _unique(self.support_refs))
        if not self.support_refs:
            raise ContractError("mémoire: support cognitif requis")
        if self.exposures < 1:
            raise ContractError("mémoire: exposures doit être positif")
        for name in ("activation", "distinctiveness", "utility"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ContractError(f"mémoire: {name} hors [0,1]")
        if self.strength < 0 or not math.isfinite(self.strength):
            raise ContractError("mémoire: force invalide")
        if self.tier is MemoryTier.FORGOTTEN:
            if self.forgotten_step is None or not self.forgetting_reason:
                raise ContractError("mémoire oubliée: trace d'oubli requise")


@dataclass(frozen=True)
class RetrievalRequest:
    goal_ref: str
    anchor_features: tuple[str, ...] = ()
    required_features: tuple[str, ...] = ()
    context_refs: tuple[str, ...] = ()
    requested_kinds: tuple[str, ...] = ()
    maximum_results: int = 5
    activation_floor: float = 0.0
    include_intermediate: bool = True
    include_long_term: bool = True

    def __post_init__(self) -> None:
        _nonempty(self.goal_ref, "goal_ref")
        for name in (
            "anchor_features",
            "required_features",
            "context_refs",
            "requested_kinds",
        ):
            object.__setattr__(self, name, _unique(getattr(self, name)))
        if self.maximum_results < 1:
            raise ContractError("retrieval: maximum_results doit être positif")
        if not 0.0 <= self.activation_floor <= 1.0:
            raise ContractError("retrieval: activation_floor hors [0,1]")


@dataclass(frozen=True)
class RetrievalHit:
    content_ref: str
    score: float
    tier: MemoryTier
    matched_features: tuple[str, ...]
    context_match: bool
    explanation: str


class CognitiveMemory:
    """Store cognitif avec promotion, décroissance, oubli et retrieval borné."""

    def __init__(self, policy: MemoryPolicy | None = None) -> None:
        self.policy = policy or MemoryPolicy()
        self.step = 0
        self._items: dict[str, MemoryItem] = {}

    def remember(
        self,
        content_ref: str,
        *,
        kind: str,
        features: Iterable[str],
        context_refs: Iterable[str],
        support_refs: Iterable[str],
        activation: float = 1.0,
        distinctiveness: float = 0.5,
        utility: float = 0.0,
        situation_bound: bool = False,
    ) -> MemoryItem:
        _nonempty(content_ref, "content_ref")
        feature_tuple = tuple(sorted(set(features)))
        context_tuple = tuple(sorted(set(context_refs)))
        support_tuple = tuple(sorted(set(support_refs)))
        existing = self._items.get(content_ref)
        if existing and existing.tier is not MemoryTier.FORGOTTEN:
            item = replace(
                existing,
                features=tuple(sorted(set(existing.features) | set(feature_tuple))),
                context_refs=tuple(
                    sorted(set(existing.context_refs) | set(context_tuple))
                ),
                support_refs=tuple(
                    sorted(set(existing.support_refs) | set(support_tuple))
                ),
                activation=max(existing.activation, activation),
                strength=existing.strength + 1.0 + distinctiveness,
                exposures=existing.exposures + 1,
                distinctiveness=max(existing.distinctiveness, distinctiveness),
                utility=max(existing.utility, utility),
                last_touched_step=self.step,
            )
        else:
            item = MemoryItem(
                content_ref=content_ref,
                kind=kind,
                tier=(MemoryTier.SITUATION if situation_bound else MemoryTier.PERIPHERAL),
                features=feature_tuple,
                context_refs=context_tuple,
                support_refs=support_tuple,
                activation=activation,
                strength=1.0 + distinctiveness,
                exposures=1,
                distinctiveness=distinctiveness,
                utility=utility,
                created_step=self.step,
                last_touched_step=self.step,
            )
        self._items[content_ref] = item
        self._maybe_consolidate(content_ref)
        self._enforce_capacities()
        return self._items[content_ref]

    def focus(self, content_ref: str) -> MemoryItem:
        item = self.get(content_ref)
        if item.tier is MemoryTier.FORGOTTEN:
            raise ContractError("mémoire: contenu oublié inaccessible")
        focused = replace(
            item,
            tier=MemoryTier.FOCAL,
            activation=1.0,
            utility=min(1.0, item.utility + 0.05),
            last_touched_step=self.step,
        )
        self._items[content_ref] = focused
        self._enforce_capacities()
        return self._items[content_ref]

    def release_focus(self, content_ref: str, *, keep_in_situation: bool = False) -> None:
        item = self.get(content_ref)
        if item.tier is not MemoryTier.FOCAL:
            return
        self._items[content_ref] = replace(
            item,
            tier=MemoryTier.SITUATION if keep_in_situation else MemoryTier.PERIPHERAL,
            last_touched_step=self.step,
        )
        self._enforce_capacities()

    def advance(self, steps: int = 1) -> None:
        if steps < 1:
            raise ContractError("mémoire: avance positive requise")
        for _ in range(steps):
            self.step += 1
            for content_ref, item in tuple(self._items.items()):
                if item.tier in {MemoryTier.FOCAL, MemoryTier.FORGOTTEN}:
                    continue
                activation = item.activation * self.policy.activation_decay
                strength = item.strength * self.policy.strength_decay
                updated = replace(item, activation=activation, strength=strength)
                self._items[content_ref] = updated
                if (
                    updated.tier is MemoryTier.INTERMEDIATE
                    and updated.strength < self.policy.forgetting_strength
                ):
                    self._forget(content_ref, "décroissance sous le seuil")
            self._enforce_capacities()

    def consolidate(self, content_ref: str) -> bool:
        item = self.get(content_ref)
        if item.tier is MemoryTier.FORGOTTEN:
            return False
        if (
            item.exposures < self.policy.consolidation_exposures
            or item.strength < self.policy.consolidation_strength
        ):
            return False
        self._items[content_ref] = replace(
            item, tier=MemoryTier.LONG_TERM, last_touched_step=self.step
        )
        self._enforce_capacities()
        return self._items[content_ref].tier is MemoryTier.LONG_TERM

    def retrieve(self, request: RetrievalRequest) -> tuple[RetrievalHit, ...]:
        anchors = set(request.anchor_features)
        required = set(request.required_features)
        contexts = set(request.context_refs)
        kinds = set(request.requested_kinds)
        allowed = {MemoryTier.FOCAL, MemoryTier.PERIPHERAL, MemoryTier.SITUATION}
        if request.include_intermediate:
            allowed.add(MemoryTier.INTERMEDIATE)
        if request.include_long_term:
            allowed.add(MemoryTier.LONG_TERM)
        hits = []
        for item in self._items.values():
            if item.tier not in allowed or item.activation < request.activation_floor:
                continue
            item_features = set(item.features)
            if not required <= item_features:
                continue
            if kinds and item.kind not in kinds:
                continue
            matched = anchors & item_features
            feature_score = len(matched) / max(1, len(anchors | item_features))
            context_match = bool(contexts & set(item.context_refs)) if contexts else False
            score = (
                0.45 * feature_score
                + 0.20 * item.activation
                + 0.15 * min(1.0, item.strength / self.policy.consolidation_strength)
                + 0.10 * item.utility
                + 0.05 * item.distinctiveness
                + 0.05 * float(context_match)
            )
            hits.append(
                RetrievalHit(
                    content_ref=item.content_ref,
                    score=score,
                    tier=item.tier,
                    matched_features=tuple(sorted(matched)),
                    context_match=context_match,
                    explanation=(
                        f"goal={request.goal_ref}; features={len(matched)}; "
                        f"context={'yes' if context_match else 'no'}; tier={item.tier.value}"
                    ),
                )
            )
        hits.sort(key=lambda row: (-row.score, row.content_ref))
        return tuple(hits[: request.maximum_results])

    def project_retrieval_to_focus(
        self, request: RetrievalRequest
    ) -> tuple[RetrievalHit, ...]:
        hits = self.retrieve(request)
        capacity = self.policy.focal_capacity
        for hit in hits[:capacity]:
            self.focus(hit.content_ref)
        return hits[:capacity]

    def get(self, content_ref: str) -> MemoryItem:
        try:
            return self._items[content_ref]
        except KeyError as exc:
            raise ContractError(f"mémoire: contenu absent {content_ref}") from exc

    def accessible(self, content_ref: str) -> bool:
        item = self._items.get(content_ref)
        return bool(item and item.tier is not MemoryTier.FORGOTTEN)

    def by_tier(self, tier: MemoryTier) -> tuple[MemoryItem, ...]:
        return tuple(
            sorted(
                (item for item in self._items.values() if item.tier is tier),
                key=lambda item: item.content_ref,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "policy": {
                name: getattr(self.policy, name)
                for name in self.policy.__dataclass_fields__
            },
            "items": [
                {
                    **{
                        name: getattr(item, name)
                        for name in item.__dataclass_fields__
                        if name != "tier"
                    },
                    "tier": item.tier.value,
                }
                for item in sorted(self._items.values(), key=lambda row: row.content_ref)
            ],
        }

    @classmethod
    def restore(cls, payload: Mapping[str, Any]) -> "CognitiveMemory":
        try:
            memory = cls(MemoryPolicy(**payload["policy"]))
            memory.step = int(payload["step"])
            for row in payload["items"]:
                values = dict(row)
                values["tier"] = MemoryTier(values["tier"])
                for name in ("features", "context_refs", "support_refs"):
                    values[name] = tuple(values[name])
                item = MemoryItem(**values)
                memory._items[item.content_ref] = item
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError(f"mémoire: snapshot invalide: {exc}") from exc
        memory._enforce_capacities()
        return memory

    def _maybe_consolidate(self, content_ref: str) -> None:
        self.consolidate(content_ref)

    def _forget(self, content_ref: str, reason: str) -> None:
        item = self.get(content_ref)
        self._items[content_ref] = replace(
            item,
            tier=MemoryTier.FORGOTTEN,
            activation=0.0,
            forgotten_step=self.step,
            forgetting_reason=reason,
        )

    def _enforce_capacities(self) -> None:
        capacities = (
            (MemoryTier.FOCAL, self.policy.focal_capacity, MemoryTier.PERIPHERAL),
            (
                MemoryTier.PERIPHERAL,
                self.policy.peripheral_capacity,
                MemoryTier.INTERMEDIATE,
            ),
            (
                MemoryTier.SITUATION,
                self.policy.situation_capacity,
                MemoryTier.INTERMEDIATE,
            ),
        )
        for tier, capacity, destination in capacities:
            rows = self._eviction_order(tier)
            for item in rows[: max(0, len(rows) - capacity)]:
                self._items[item.content_ref] = replace(item, tier=destination)

        intermediate = self._eviction_order(MemoryTier.INTERMEDIATE)
        for item in intermediate[: max(0, len(intermediate) - self.policy.intermediate_capacity)]:
            if self._qualifies_for_consolidation(item):
                self._items[item.content_ref] = replace(item, tier=MemoryTier.LONG_TERM)
            else:
                self._forget(item.content_ref, "capacité de mémoire intermédiaire")

        long_term = self._eviction_order(MemoryTier.LONG_TERM)
        for item in long_term[: max(0, len(long_term) - self.policy.long_term_capacity)]:
            self._forget(item.content_ref, "capacité de mémoire longue")

    def _eviction_order(self, tier: MemoryTier) -> list[MemoryItem]:
        rows = [item for item in self._items.values() if item.tier is tier]
        return sorted(
            rows,
            key=lambda item: (
                item.activation,
                item.strength,
                item.utility,
                item.distinctiveness,
                item.last_touched_step,
                item.content_ref,
            ),
        )

    def _qualifies_for_consolidation(self, item: MemoryItem) -> bool:
        return (
            item.exposures >= self.policy.consolidation_exposures
            and item.strength >= self.policy.consolidation_strength
        )

