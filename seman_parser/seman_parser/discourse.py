"""Discourse memory: mentions point to persistent entities.

Nothing is thrown away: every mention is recorded, every coreference
decision is a ranked hypothesis that can be revised later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .features import Atom, FeatureStructure
from .semantics import SemanticGraph


def _atom_name(value: object) -> str | None:
    """Feature value as a string, or None when unbound/variable/top."""
    if isinstance(value, Atom):
        return value.name
    return None


@dataclass(frozen=True, slots=True)
class Mention:
    """One referring expression observed in one sentence."""

    mention_id: str
    surface: str
    span: tuple[int, int]
    kind: str  # "pronoun", "proper", "definite", "indefinite", "demonstrative", "event"
    sentence_index: int
    features: FeatureStructure = field(default_factory=FeatureStructure.empty)
    semantic_type: str | None = None
    node_id: str | None = None
    head_lemma: str | None = None
    score: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def number(self) -> str | None:
        return _atom_name(self.features.get("number"))

    @property
    def person(self) -> str | None:
        return _atom_name(self.features.get("person"))

    @property
    def gender(self) -> str | None:
        return _atom_name(self.features.get("gender"))

    @property
    def is_anaphor(self) -> bool:
        return self.kind in {"pronoun", "demonstrative"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.mention_id,
            "surface": self.surface,
            "span": list(self.span),
            "kind": self.kind,
            "sentence": self.sentence_index,
            "features": self.features.as_dict(),
            "semantic_type": self.semantic_type,
            "node_id": self.node_id,
            "head_lemma": self.head_lemma,
        }


@dataclass
class DiscourseEntity:
    """A persistent discourse referent built from one or more mentions."""

    entity_id: str
    mentions: list[str] = field(default_factory=list)
    type_hypotheses: list[tuple[str, float]] = field(default_factory=list)
    salience: float = 1.0
    first_seen: int = 0
    last_seen: int = 0
    node_ids: list[str] = field(default_factory=list)
    surfaces: list[str] = field(default_factory=list)
    features: FeatureStructure = field(default_factory=FeatureStructure.empty)

    @property
    def last_surface(self) -> str | None:
        return self.surfaces[-1] if self.surfaces else None

    def decay_salience(self, *, factor: float = 0.85) -> None:
        self.salience *= factor

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.entity_id,
            "mentions": list(self.mentions),
            "type_hypotheses": [{"type": t, "score": s} for t, s in self.type_hypotheses],
            "salience": self.salience,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "surfaces": list(self.surfaces),
            "features": self.features.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class CoreferenceHypothesis:
    """One ranked candidate link between a mention and an entity (or new)."""

    mention_id: str
    entity_id: str | None
    score: float
    factors: Mapping[str, float] = field(default_factory=dict)
    rank: int = 0

    @property
    def is_new(self) -> bool:
        return self.entity_id is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "mention": self.mention_id,
            "entity": self.entity_id,
            "score": self.score,
            "rank": self.rank,
            "factors": dict(self.factors),
            "is_new": self.is_new,
        }


@dataclass
class DiscourseState:
    """Full memory of a session: entities, mentions, decisions, graph."""

    entities: dict[str, DiscourseEntity] = field(default_factory=dict)
    mentions: dict[str, Mention] = field(default_factory=dict)
    # mention_id -> ranked hypotheses (best first). Decisions are revisable.
    decisions: dict[str, tuple[CoreferenceHypothesis, ...]] = field(default_factory=dict)
    # committed link: mention_id -> entity_id
    links: dict[str, str] = field(default_factory=dict)
    sentence_count: int = 0
    graph: SemanticGraph = field(default_factory=SemanticGraph)

    def entity(self, entity_id: str) -> DiscourseEntity | None:
        return self.entities.get(entity_id)

    def mentions_of(self, entity_id: str) -> list[Mention]:
        entity = self.entities.get(entity_id)
        if entity is None:
            return []
        return [self.mentions[mid] for mid in entity.mentions if mid in self.mentions]

    def as_dict(self) -> dict[str, Any]:
        return {
            "entities": [entity.as_dict() for entity in self.entities.values()],
            "mentions": [m.as_dict() for m in self.mentions.values()],
            "decisions": {
                mid: [h.as_dict() for h in hyps] for mid, hyps in self.decisions.items()
            },
            "links": dict(self.links),
            "sentences": self.sentence_count,
        }
