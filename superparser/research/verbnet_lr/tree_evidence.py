"""Observe actual VP constituent trees against VerbNet valency frames.

This is a *post-parse diagnostic*; it never modifies the chosen structure,
does not infer missing arguments, and never declares UNKNOWN ungrammatical.
It measures whether VerbNet could supply positive evidence at the point
where a future, grammar-licensed parser needs to choose a verb construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapter import predict_candidate
from .compiler import PrefixIndex


@dataclass(frozen=True, slots=True)
class FrameObservation:
    lemma: str
    rule_id: str | None
    events: tuple[str, ...]
    status: str
    confidence: str
    matching_frames: int


def _prep(node: Any) -> str | None:
    """Only syntactically anchored prepositions, never speculative tokens."""
    cat = getattr(node, "category", "")
    if cat not in {"PREP", "PREP-BY"}:
        return None
    lexical = getattr(node, "lexical_candidate", None)
    if lexical is None:
        return None
    word = getattr(lexical, "surface", "")
    return word.casefold() if word else None


def _pp_events(node: Any) -> tuple[str, ...] | None:
    """Return PP as PREP:x NP only for an explicit complete binary PP."""
    children = getattr(node, "children", ())
    if len(children) != 2 or children[1].category != "NP":
        return None
    prep = _prep(children[0])
    if prep is None:
        return None
    return ("PREP:" + prep, "NP")


def _vp_observation(node: Any, index: PrefixIndex) -> FrameObservation | None:
    """Only directly headed finite/inflected VPs with recognizable slots."""
    if node.category != "VP" or not node.children:
        return None
    head = node.children[0]
    if head.category != "V" or head.lexical_candidate is None:
        return None
    events: list[str] = []
    children = node.children
    i = 1
    while i < len(children):
        ch = children[i]
        cat = ch.category
        if cat == "NP":
            events.append("NP")
        elif cat in {"PP", "PP-BY"}:
            pp = _pp_events(ch)
            if pp is None:
                return None
            events.extend(pp)
        elif cat in {"PREP", "PREP-BY"} and i + 1 < len(children) and children[i + 1].category == "NP":
            prep = _prep(ch)
            if prep is None:
                return None
            events.extend(("PREP:" + prep, "NP"))
            i += 1
        elif cat == "TO" and i + 1 < len(children) and children[i + 1].category in {"VP", "VP-NP"}:
            events.append("TO_INF")
            i += 1
        elif cat in {"ADJ", "ADJP"}:
            events.append("ADJ")
        elif cat == "CLAUSE":
            events.append("CLAUSE")
        elif cat == "ADV":
            # Adjunct outside the required valency slots. This is a *weak*
            # projection; do not claim the frame proves adverb attachment.
            pass
        else:
            return None
        i += 1
    prediction = predict_candidate(index, head.lexical_candidate, tuple(events))
    return FrameObservation(
        lemma=head.lexical_candidate.lemma,
        rule_id=node.rule_id,
        events=tuple(events),
        status=prediction.status,
        confidence=prediction.confidence,
        matching_frames=len(prediction.matching_frames),
    )


def observe_vp_frames(tree: Any, index: PrefixIndex) -> tuple[FrameObservation, ...]:
    """Walk one chosen parse tree; no alternate structures are generated."""
    if tree is None:
        return ()
    out = []
    stack = [tree]
    while stack:
        node = stack.pop()
        observation = _vp_observation(node, index)
        if observation is not None:
            out.append(observation)
        stack.extend(reversed(getattr(node, "children", ())))
    return tuple(out)
