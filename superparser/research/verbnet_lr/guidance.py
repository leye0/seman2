"""Cheap optional VerbNet guidance for Seman2's single-continuation L→R reader.

This module observes a BOUNDED lexical window after a verb. It never builds
a parse tree, asks a forest for k-best, or rejects a grammatical construction.
It only breaks ties after the grammar's own viability and rule score.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .adapter import predict_candidate
from .compiler import PrefixIndex

_NP_HEAD = frozenset(("N", "PROPER-NOUN", "PRON", "NUM", "NUMBER"))
_NP_START = _NP_HEAD | {"DET", "ADJ"}
_END = frozenset((".", "!", "?", ",", ";", ":"))


def project_postverb_events(
    tokens: Sequence[Any], lex: Mapping[int, Mapping[str, Sequence[Any]]],
    start: int, *, max_tokens: int = 12, max_events: int = 4,
) -> tuple[str, ...]:
    """Conservative, *approximate* event projection; not constituent parsing.

    A weak lookahead only: it cannot prove NP attachment or clausal structure.
    Stops rather than inventing evidence if tokens are not recognizable.
    """
    events: list[str] = []
    at = start
    until = min(len(tokens), start + max_tokens)
    while at < until and len(events) < max_events:
        token = tokens[at]
        word = token.text.casefold()
        if word in _END:
            break
        cats = lex.get(at, ())
        if not cats:
            break

        if word == "to" and at + 1 < until and "V" in lex.get(at + 1, ()):
            events.append("TO_INF")
            break

        if "PREP" in cats:
            events.append("PREP:" + word)
            at += 1
            continue

        # A gerund may head the next verbal argument; only accept an
        # explicit ing form when the lexical features support it.
        if "V" in cats and word.endswith("ing"):
            events.append("GERUND")
            break

        if "ADV" in cats and not (_NP_START.intersection(cats)):
            at += 1
            continue

        if not (_NP_START.intersection(cats)):
            break

        i = at
        if "DET" in cats:
            i += 1
            while i < until and (("ADJ" in lex.get(i, ())) or ("ADV" in lex.get(i, ()))) and i - at < 4:
                i += 1
            if i >= until or not (_NP_HEAD.intersection(lex.get(i, ()))):
                break  # do not invent NP without a head
            i += 1
        elif "ADJ" in cats and not (_NP_HEAD.intersection(cats)):
            while i < until and "ADJ" in lex.get(i, ()) and i - at < 3:
                i += 1
            if i >= until or not (_NP_HEAD.intersection(lex.get(i, ()))):
                break
            i += 1
        else:
            i += 1
        # Avoid swallowing adjacent proper-name tokens as another NP.
        if "PROPER-NOUN" in cats:
            while i < until and "PROPER-NOUN" in lex.get(i, ()) and i - at < 4:
                i += 1
        events.append("NP")
        at = i
    return tuple(events)


@dataclass
class VerbNetRanker:
    """Bounded optional scorer; low-confidence results abstain.

    exact: only WordNet sense-matched hints get a positive bonus.
    lemma: A/B ablation including weaker lemma-level matches.
    zero: baseline without querying VerbNet.
    """
    index: PrefixIndex
    mode: str = "exact"
    max_tokens: int = 12

    def __post_init__(self):
        if self.mode not in {"exact", "lemma", "zero"}:
            raise ValueError(f"unknown VerbNet guidance mode: {self.mode}")
        if not 1 <= self.max_tokens <= 32:
            raise ValueError("max_tokens outside 1..32")

    def score(self, candidate: Any, tokens: Sequence[Any],
              lex: Mapping[int, Mapping[str, Sequence[Any]]], position: int,
              *, events: tuple[str, ...] | None = None) -> int:
        if self.mode == "zero" or getattr(candidate, "category", None) != "V":
            return 0
        if events is None:
            events = project_postverb_events(tokens, lex, position + 1,
                                             max_tokens=self.max_tokens)
        # A guessed empty prefix is not syntactic evidence for intransitivity.
        if not events:
            return 0
        if self.mode == "lemma":
            prediction = self.index.predict(candidate.lemma, events)
            confidence = "lemma_only"
        else:
            prediction = predict_candidate(self.index, candidate, events)
            confidence = prediction.confidence
            if confidence != "sense_verified":
                return 0
        # These numbers are deliberately tiny ordinal ranks. They cannot
        # override viability, grammar constraints, or grammar rule scores.
        return 2 if prediction.status == "ATTESTED" else 1 if prediction.status == "PREFIX" else 0
