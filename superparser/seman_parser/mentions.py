"""Mention extraction from parsed constituents.

Discourse kind (pronoun, definite, …) comes from lexical features in the
data, never from a hard-coded word list in the engine.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .chart import ChartItem
from .discourse import Mention
from .features import Atom, FeatureStructure


def extract_mentions(
    item: ChartItem,
    sentence_index: int,
    counter: list[int] | None = None,
    *,
    semantic: Any | None = None,
) -> list[Mention]:
    """Collect NP-level mentions from one analysis tree."""
    counter = counter if counter is not None else [0]
    found: list[Mention] = []
    if item.category == "NP":
        found.append(mention_from_item(item, sentence_index, counter, semantic=semantic))
    for child in item.children:
        found.extend(extract_mentions(child, sentence_index, counter, semantic=semantic))
    return found


def extract_event_mentions(
    item: ChartItem,
    sentence_index: int,
    counter: list[int] | None = None,
    *,
    semantic: Any | None = None,
) -> list[Mention]:
    """Event mentions identified from syntax, before semantic graphs exist."""
    counter = counter if counter is not None else [0]
    found: list[Mention] = []
    seen: set[str] = set()

    def walk(node: ChartItem) -> None:
        candidate = node.lexical_candidate
        node_id = node.syntax.anchors.get("event")
        if candidate is not None and node_id and node_id not in seen:
            semantic_node = _matching_node(semantic, node, kind="event")
            seen.add(node_id)
            counter[0] += 1
            found.append(Mention(
                mention_id=f"S{sentence_index}-EVT{counter[0]}",
                surface=candidate.surface or _surface(node) or "event",
                span=(node.start, node.end), kind="event",
                sentence_index=sentence_index,
                features=FeatureStructure.empty(),
                semantic_type=semantic_node.type_name if semantic_node is not None else None,
                node_id=semantic_node.node_id if semantic_node is not None else node_id,
                head_lemma=candidate.lemma,
                score=node.score,
                provenance={"category": node.category, "rule_id": node.rule_id},
            ))
        for child in node.children:
            walk(child)

    walk(item)
    return found


def mention_from_item(
    item: ChartItem,
    sentence_index: int,
    counter: list[int] | None = None,
    *,
    semantic: Any | None = None,
) -> Mention:
    counter = counter if counter is not None else [0]
    counter[0] += 1
    mention_id = f"S{sentence_index}-M{counter[0]}"
    kind = classify_kind(item)
    semantic_node = _matching_node(semantic, item, lemma=_head_lemma(item))
    semantic_type = semantic_node.type_name if semantic_node is not None else _semantic_type(item)
    node_id = item.syntax.anchors.get("referent") or item.syntax.anchors.get("head")
    if semantic_node is not None:
        node_id = semantic_node.node_id
    surface = _surface(item)
    head = _head_lemma(item)
    return Mention(
        mention_id=mention_id,
        surface=surface,
        span=(item.start, item.end),
        kind=kind,
        sentence_index=sentence_index,
        features=item.features,
        semantic_type=semantic_type,
        node_id=node_id,
        head_lemma=head,
        score=item.score,
        provenance={"category": item.category, "rule_id": item.rule_id},
    )


def classify_kind(item: ChartItem) -> str:
    """Discourse kind from lexical features; defaults by category."""
    features = item.features.as_dict()
    definiteness = features.get("definiteness")
    if isinstance(definiteness, list):
        definiteness = definiteness[0] if definiteness else None
    anaphor = features.get("anaphor")
    if isinstance(anaphor, list):
        anaphor = anaphor[0] if anaphor else None

    if anaphor in (True, "true", "yes") or str(anaphor).lower() == "true":
        if str(definiteness).lower() == "demonstrative":
            return "demonstrative"
        return "pronoun"

    if str(definiteness).lower() in {"definite", "def"}:
        return "definite"
    if str(definiteness).lower() in {"indefinite", "indef"}:
        return "indefinite"
    if str(definiteness).lower() == "demonstrative":
        return "demonstrative"

    # Fall back to category seen in the subtree.
    categories = set(_categories(item))
    if "PROPER-NOUN" in categories:
        return "proper"
    if "PRONOUN" in categories:
        return "pronoun"
    if "POSS" in categories:
        return "definite"
    if "DET" in categories:
        return "definite"
    return "proper" if _looks_cased_name(item) else "indefinite"


def _categories(item: ChartItem) -> list[str]:
    out = [item.category]
    for child in item.children:
        out.extend(_categories(child))
    return out


def _looks_cased_name(item: ChartItem) -> bool:
    surface = _surface(item)
    return bool(surface) and surface[:1].isupper()


def _surface(item: ChartItem) -> str:
    if not item.children:
        detail = item.provenance.detail if item.provenance else {}
        return str(detail.get("surface", ""))
    parts = [_surface(child) for child in item.children]
    return " ".join(p for p in parts if p)


def _head_lemma(item: ChartItem) -> str | None:
    if not item.children:
        detail = item.provenance.detail if item.provenance else {}
        value = detail.get("lemma")
        return str(value) if value else None
    # Prefer the last nominal/verbal child.
    for child in reversed(item.children):
        lemma = _head_lemma(child)
        if lemma:
            return lemma
    return None


def _semantic_type(item: ChartItem) -> str | None:
    anchor = item.syntax.anchors.get("referent") or item.syntax.anchors.get("head")
    for leaf in _leaves(item):
        candidate = leaf.lexical_candidate
        if candidate is not None and anchor in leaf.syntax.anchors.values():
            return None
    for child in item.children:
        found = _semantic_type(child)
        if found:
            return found
    return None


def _leaves(item: ChartItem):
    if not item.children:
        yield item
    for child in item.children:
        yield from _leaves(child)


def _matching_node(
    semantic: Any | None,
    item: ChartItem,
    *,
    kind: str | None = None,
    lemma: str | None = None,
):
    if semantic is None:
        return None
    nodes = getattr(getattr(semantic, "graph", None), "nodes", {}).values()
    for node in nodes:
        if kind is not None and node.kind != kind:
            continue
        if node.span is None or not (item.start <= node.span[0] and node.span[1] <= item.end):
            continue
        if lemma is not None and node.attributes.get("lemma") != lemma:
            continue
        return node
    return None
