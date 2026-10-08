"""Mention extraction from parsed constituents.

Discourse kind (pronoun, definite, …) comes from lexical features in the
data, never from a hard-coded word list in the engine.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .chart import ChartItem
from .discourse import Mention
from .features import Atom, FeatureStructure


def extract_mentions(item: ChartItem, sentence_index: int, counter: list[int] | None = None) -> list[Mention]:
    """Collect NP-level mentions from one analysis tree."""
    counter = counter if counter is not None else [0]
    found: list[Mention] = []
    if item.category == "NP":
        found.append(mention_from_item(item, sentence_index, counter))
    for child in item.children:
        found.extend(extract_mentions(child, sentence_index, counter))
    return found


def extract_event_mentions(item: ChartItem, sentence_index: int, counter: list[int] | None = None) -> list[Mention]:
    """Event-level mentions (blueprint §19: anaphora to whole situations).

    One event mention per semantic event node, so ``This`` can later refer
    to a previous clause's event, not only to an object.
    """
    counter = counter if counter is not None else [0]
    found: list[Mention] = []
    seen: set[str] = set()

    def walk(node: ChartItem) -> None:
        node_id = node.semantic.handles.get("event")
        if node_id and node_id not in seen and node_id in node.semantic.graph.nodes:
            event_node = node.semantic.graph.nodes[node_id]
            if event_node.kind == "event":
                seen.add(node_id)
                counter[0] += 1
                found.append(
                    Mention(
                        mention_id=f"S{sentence_index}-EVT{counter[0]}",
                        surface=event_node.surface or _surface(node) or event_node.type_name or "event",
                        span=event_node.span or (node.start, node.end),
                        kind="event",
                        sentence_index=sentence_index,
                        features=FeatureStructure.empty(),
                        semantic_type=event_node.type_name,
                        node_id=node_id,
                        head_lemma=event_node.attributes.get("lemma") if isinstance(event_node.attributes, dict) else None,
                        score=node.score,
                        provenance={"category": node.category, "rule_id": node.rule_id},
                    )
                )
        for child in node.children:
            walk(child)

    walk(item)
    return found


def mention_from_item(item: ChartItem, sentence_index: int, counter: list[int] | None = None) -> Mention:
    counter = counter if counter is not None else [0]
    counter[0] += 1
    mention_id = f"S{sentence_index}-M{counter[0]}"
    kind = classify_kind(item)
    semantic_type = _semantic_type(item)
    node_id = item.semantic.handles.get("referent") or item.semantic.handles.get("head")
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
    handles = item.semantic.handles
    node_id = handles.get("referent") or handles.get("head") or handles.get("event")
    if node_id and node_id in item.semantic.graph.nodes:
        return item.semantic.graph.nodes[node_id].type_name
    for child in item.children:
        found = _semantic_type(child)
        if found:
            return found
    return None
