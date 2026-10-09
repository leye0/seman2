"""Commit reference links into discourse memory.

Base: ``plans/coreference-guide.md``. There is no factor score here.
A link carries a *kind* produced by a grammar rule; the committer decides
what that kind means for the discourse state.

Kind → effect on memory
-----------------------
SAME_REF            merge into one entity (grammar forces identity)
ASSERTED_IDENTITY   merge into one entity (text asserts identity)
MAYBE_REF           record as open candidate only — never merge
DIFFERENT_REF       record a non-identity pair
NO_LINK             leave unresolved (external / expletive / bridging)
BOUND_VARIABLE      record binding; do not create an individual entity
SHARED_ARGUMENT     record structural sharing; not individual coref
TYPE_ANAPHORA       record type reuse; not individual identity
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from .discourse import DiscourseEntity, DiscourseState, Mention
from .reference import ReferenceKind, ReferenceLink

_MERGE_KINDS = frozenset(
    {ReferenceKind.SAME_REF, ReferenceKind.ASSERTED_IDENTITY}
)


def _fresh_entity_id(state: DiscourseState) -> str:
    return f"E{len(state.entities) + 1}"


def introduce(
    mention: Mention,
    state: DiscourseState,
) -> DiscourseEntity | None:
    """Register a mention and open a new entity when it is referential.

    Events are their own situations (each gets an entity). Expletives
    have no referent — recorded as mentions only.
    """
    state.mentions[mention.mention_id] = mention
    if _is_expletive(mention):
        return None
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
    state.links[mention.mention_id] = entity.entity_id
    return entity


def _is_expletive(mention: Mention) -> bool:
    value = mention.features.get("expletive")
    if value is not None and str(getattr(value, "name", value)).lower() in {"true", "yes", "1"}:
        return True
    return mention.surface.strip().lower() in {"there"} and mention.kind == "pronoun"


def _entity_of(state: DiscourseState, mention_id: str) -> str | None:
    return state.links.get(mention_id)


def _merge_into(
    state: DiscourseState,
    source_id: str,
    target_id: str,
) -> None:
    """Attach source's entity to target's entity (identity)."""
    source_ent = state.entities.get(source_id)
    target_ent = state.entities.get(target_id)
    if source_ent is None or target_ent is None or source_id == target_id:
        return
    for mid in source_ent.mentions:
        target_ent.mentions.append(mid)
        state.links[mid] = target_id
    target_ent.surfaces.extend(source_ent.surfaces)
    target_ent.node_ids.extend(source_ent.node_ids)
    target_ent.last_seen = max(target_ent.last_seen, source_ent.last_seen)
    target_ent.first_seen = min(target_ent.first_seen, source_ent.first_seen)
    del state.entities[source_id]


def commit_link(link: ReferenceLink, state: DiscourseState) -> None:
    """Apply one reference link to the discourse state."""
    state.reference_links.append(link)

    if link.kind in _MERGE_KINDS:
        src_ent = _entity_of(state, link.source)
        tgt_ent = _entity_of(state, link.target) if link.target else None
        if src_ent and tgt_ent and src_ent != tgt_ent:
            _merge_into(state, src_ent, tgt_ent)
        elif src_ent and link.target and link.target.startswith("SPEAKER"):
            state.links[link.source] = link.target
        return

    if link.kind == ReferenceKind.DIFFERENT_REF:
        pair = frozenset({link.source, link.target} if link.target else {link.source})
        state.different_pairs.add(pair)
        return

    if link.kind == ReferenceKind.MAYBE_REF:
        state.maybe_links.append(link)
        return

    if link.kind == ReferenceKind.BOUND_VARIABLE:
        state.bound_variables.append(link)
        return

    if link.kind == ReferenceKind.SHARED_ARGUMENT:
        state.shared_arguments.append(link)
        return

    if link.kind == ReferenceKind.TYPE_ANAPHORA:
        state.type_anaphora.append(link)
        return

    # NO_LINK — keep the mention, do not merge.
    return


def commit_links(links: Iterable[ReferenceLink], state: DiscourseState) -> None:
    for link in links:
        commit_link(link, state)


def open_candidates(state: DiscourseState, mention_id: str) -> list[ReferenceLink]:
    """MAYBE_REF candidates for one mention (never committed)."""
    return [lk for lk in state.maybe_links if lk.source == mention_id]


def is_blocked(state: DiscourseState, a: str, b: str) -> bool:
    """True when a DIFFERENT_REF link forbids identity of a and b."""
    return frozenset({a, b}) in state.different_pairs
