"""Coreference resolver: ranked, revisable hypotheses.

Pipeline (blueprint §17): candidates → syntax → agreement → accessibility →
semantic compatibility → recency → salience. Scores are additive factors so
each filter contributes evidence without hard-coding a phenomenon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .discourse import (
    CoreferenceHypothesis,
    DiscourseEntity,
    DiscourseState,
    Mention,
    _atom_name,
)
from .types import TypeHierarchy


@dataclass
class ResolverConfig:
    """Tunable weights — data, not code branches on linguistic content."""

    recency_half_life: float = 3.0
    weight_recency: float = 1.2
    weight_salience: float = 0.9
    weight_type: float = 1.1
    weight_agreement: float = 1.5
    weight_kind: float = 0.6
    weight_focus: float = 0.7
    penalty_type_mismatch: float = -2.5
    penalty_agreement_mismatch: float = -4.0
    penalty_binding: float = -3.0
    new_entity_bias: float = 0.35
    pronoun_new_entity_penalty: float = -1.2
    max_candidates: int = 12


class CoreferenceResolver:
    """Produces ranked hypotheses; never destroys alternatives."""

    def __init__(self, types: TypeHierarchy | None = None, config: ResolverConfig | None = None) -> None:
        self.types = types
        self.config = config or ResolverConfig()

    def candidates(self, mention: Mention, state: DiscourseState) -> Sequence[DiscourseEntity]:
        """Candidate generation: recent + active entities, type-filtered pool."""
        cfg = self.config
        pool = sorted(
            state.entities.values(),
            key=lambda e: (e.last_seen, e.salience),
            reverse=True,
        )
        out: list[DiscourseEntity] = []
        for entity in pool:
            if mention.sentence_index - entity.last_seen > 20:
                continue
            out.append(entity)
            if len(out) >= cfg.max_candidates:
                break
        return out

    def resolve(self, mention: Mention, state: DiscourseState) -> tuple[CoreferenceHypothesis, ...]:
        """Rank every hypothesis for one mention. Best first."""
        scored: list[CoreferenceHypothesis] = []

        for entity in self.candidates(mention, state):
            factors = self._score_entity(mention, entity, state)
            if factors.get("rejected", 0.0) < 0:
                continue
            score = sum(factors.values())
            scored.append(
                CoreferenceHypothesis(
                    mention_id=mention.mention_id,
                    entity_id=entity.entity_id,
                    score=score,
                    factors=factors,
                )
            )

        new_factors = self._score_new(mention, state)
        scored.append(
            CoreferenceHypothesis(
                mention_id=mention.mention_id,
                entity_id=None,
                score=sum(new_factors.values()),
                factors=new_factors,
            )
        )

        scored.sort(key=lambda h: h.score, reverse=True)
        ranked = tuple(
            CoreferenceHypothesis(
                mention_id=h.mention_id,
                entity_id=h.entity_id,
                score=h.score,
                factors=h.factors,
                rank=index,
            )
            for index, h in enumerate(scored)
        )
        state.decisions[mention.mention_id] = ranked
        return ranked

    def resolve_best(self, mention: Mention, state: DiscourseState) -> CoreferenceHypothesis:
        ranked = self.resolve(mention, state)
        return ranked[0]

    # -- factor scoring ---------------------------------------------------

    def _score_entity(self, mention: Mention, entity: DiscourseEntity, state: DiscourseState) -> dict[str, float]:
        cfg = self.config
        factors: dict[str, float] = {}

        # Agreement: number / person / gender. Absent features are neutral.
        agreement = self._agreement(mention, entity)
        if agreement is False:
            factors["rejected"] = cfg.penalty_agreement_mismatch
            return factors
        factors["agreement"] = cfg.weight_agreement if agreement is True else 0.0

        # Semantic type compatibility via the linguistic type DAG.
        type_score = self._type_compatibility(mention, entity)
        if type_score is False:
            factors["rejected"] = cfg.penalty_type_mismatch
            return factors
        factors["type"] = cfg.weight_type * float(type_score)

        # Kind preferences: proper names prefer names, pronouns prefer
        # established entities, indefinites prefer to introduce.
        factors["kind"] = cfg.weight_kind * self._kind_affinity(mention, entity)

        # Recency: exponential decay over sentence distance.
        distance = max(0, mention.sentence_index - entity.last_seen)
        factors["recency"] = cfg.weight_recency * (0.5 ** (distance / cfg.recency_half_life))

        # Salience / focus.
        factors["salience"] = cfg.weight_salience * entity.salience

        # Binding: reflexives need a local antecedent; pronouns avoid it.
        binding = self._binding_score(mention, entity, state)
        if binding != 0.0:
            factors["binding"] = binding

        return factors

    def _score_new(self, mention: Mention, state: DiscourseState) -> dict[str, float]:
        cfg = self.config
        factors = {"new": cfg.new_entity_bias}
        if mention.kind == "indefinite":
            factors["new"] += 0.9
        elif mention.kind == "proper":
            factors["new"] += 1.1
        elif mention.kind == "definite":
            factors["new"] += 0.15
        elif mention.kind == "event":
            # Every observed event is its own discourse referent.
            factors["new"] += 1.4
        elif mention.is_anaphor:
            factors["new"] += cfg.pronoun_new_entity_penalty
        return factors

    def _agreement(self, mention: Mention, entity: DiscourseEntity) -> bool | None:
        """True match, False mismatch, None when underspecified."""
        matched = False
        for feature_name in ("number", "person", "gender"):
            m_value = getattr(mention, feature_name)
            e_value = _atom_name(entity.features.get(feature_name))
            if m_value is None or e_value is None:
                continue
            if m_value != e_value:
                return False
            matched = True
        return True if matched else None

    def _type_compatibility(self, mention: Mention, entity: DiscourseEntity) -> bool | float:
        if self.types is None or not mention.semantic_type:
            return 0.5
        mention_type = self.types.get(mention.semantic_type)
        if mention_type is None:
            return 0.5
        best = 0.0
        compatible_seen = False
        for type_name, weight in entity.type_hypotheses or [(None, 1.0)]:
            if type_name is None:
                best = max(best, 0.5)
                compatible_seen = True
                continue
            entity_type = self.types.get(type_name)
            if entity_type is None:
                best = max(best, 0.5)
                compatible_seen = True
                continue
            if self.types.is_subtype(mention_type, entity_type) or self.types.is_subtype(entity_type, mention_type):
                return 1.0 * max(weight, 0.3)
            if self.types.compatible(mention_type, entity_type):
                best = max(best, 0.7 * max(weight, 0.3))
                compatible_seen = True
                continue
            # This hypothesis is incompatible; try the entity's other types.
            continue
        if compatible_seen or best > 0:
            return best if best > 0 else 0.5
        # No hypothesis was compatible.
        return False

    def _kind_affinity(self, mention: Mention, entity: DiscourseEntity) -> float:
        last = entity.last_surface or ""
        entity_was_name = last[:1].isupper() if last else False
        entity_is_event = any(
            state_kind == "event"
            for state_kind in [self._entity_kind(entity)]
        )
        if mention.kind == "pronoun":
            return 1.0 if entity.mentions else 0.2
        if mention.kind == "proper":
            return 1.0 if entity_was_name else 0.4
        if mention.kind == "definite":
            return 0.9
        if mention.kind == "indefinite":
            return -0.4
        if mention.kind == "demonstrative":
            # Blueprint §19: demonstratives love event antecedents.
            return 1.2 if entity_is_event else 0.8
        if mention.kind == "event":
            return 1.0 if entity_is_event else 0.1
        return 0.0

    def _entity_kind(self, entity: DiscourseEntity) -> str:
        if self.types is not None:
            event_id = self.types.get("EVENT")
            for type_name, _ in entity.type_hypotheses:
                type_id = self.types.get(type_name) if type_name else None
                if type_id is not None and event_id is not None and self.types.is_subtype(type_id, event_id):
                    return "event"
        if any(t and t.upper() in {"EVENT", "STATE", "SITUATION", "PROPOSITION"} for t, _ in entity.type_hypotheses):
            return "event"
        return "entity"

    def _binding_score(self, mention: Mention, entity: DiscourseEntity, state: DiscourseState) -> float:
        cfg = self.config
        mention_features = mention.features.as_dict()
        reflexive = mention_features.get("reflexive")
        is_reflexive = reflexive in (True, "true", "yes")
        # Same-sentence antecedent: reflexives like it, pronouns avoid it.
        same_sentence = any(
            state.mentions[mid].sentence_index == mention.sentence_index
            for mid in entity.mentions
            if mid in state.mentions
        )
        if is_reflexive and same_sentence:
            return 0.8
        if is_reflexive and not same_sentence:
            return cfg.penalty_binding
        if not is_reflexive and same_sentence and mention.is_anaphor:
            return cfg.penalty_binding * 0.5
        return 0.0


def link_best(mention: Mention, state: DiscourseState, resolver: CoreferenceResolver) -> CoreferenceHypothesis:
    """Resolve and commit the top hypothesis to the discourse state."""
    hypothesis = resolver.resolve_best(mention, state)
    state.links[mention.mention_id] = hypothesis.entity_id or ""
    if hypothesis.is_new:
        entity = DiscourseEntity(
            entity_id=_fresh_entity_id(state),
            mentions=[mention.mention_id],
            type_hypotheses=[(mention.semantic_type, 1.0)] if mention.semantic_type else [],
            first_seen=mention.sentence_index,
            last_seen=mention.sentence_index,
            node_ids=[mention.node_id] if mention.node_id else [],
            surfaces=[mention.surface],
            features=mention.features,
        )
        state.entities[entity.entity_id] = entity
    else:
        entity = state.entities[hypothesis.entity_id]
        entity.mentions.append(mention.mention_id)
        entity.surfaces.append(mention.surface)
        entity.last_seen = mention.sentence_index
        entity.salience = min(3.0, entity.salience + 0.4)
        if mention.node_id:
            entity.node_ids.append(mention.node_id)
        if mention.semantic_type:
            entity.type_hypotheses = _boost_type(entity.type_hypotheses, mention.semantic_type)
    return hypothesis


def _fresh_entity_id(state: DiscourseState) -> str:
    return f"E{len(state.entities) + 1}"


def _boost_type(hypotheses: list[tuple[str, float]], type_name: str) -> list[tuple[str, float]]:
    boosted = list(hypotheses)
    for index, (name, weight) in enumerate(boosted):
        if name == type_name:
            boosted[index] = (name, min(1.0, weight + 0.2))
            return boosted
    boosted.append((type_name, 0.6))
    return boosted
