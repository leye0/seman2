"""Explicit quotation boundaries for a scoped dialogue grammar.

The ordinary tokenizer deliberately omits typographic quotation marks.
Rather than changing the tokenization of all novels (or globally accepting
speech-like clauses), add purely syntactic, zero-semantic-cost quote terminals
to a separate lexical lattice. Balanced double quotes and typographic
single quotes are accepted. Word-internal apostrophes remain contractions
and possessives, not dialogue delimiters.
"""
from __future__ import annotations

from dataclasses import dataclass

from .features import FeatureStructure
from .segmentation import LexicalCandidate, LexicalLattice


@dataclass(frozen=True, slots=True)
class QuoteBoundary:
    start: int
    end: int
    side: str
    surface: str


def quotation_boundaries(text: str) -> tuple[QuoteBoundary, ...]:
    """Recognize balanced dialogue quotes without inventing missing ones.

    Double quotes and typographic single quote pairs are delimiters.
    Word-internal U+2019 apostrophes are not quote boundaries.
    ASCII single quotes remain ignored because contractions are ambiguous.
    """
    stack: list[tuple[str, int]] = []
    boundaries: list[QuoteBoundary] = []
    for pos, char in enumerate(text):
        if char not in {'"', '“', '”', '‘', '’'}:
            continue
        if char == '’' and 0 < pos < len(text)-1:
            if text[pos-1].isalnum() and text[pos+1].isalnum():
                continue  # don't, I've, John’s — lexical apostrophe
        if char in {'“', '‘'}:
            stack.append((char, pos))
            boundaries.append(QuoteBoundary(pos, pos+1, "open", char))
        elif char in {'”', '’'}:
            expected = '“' if char == '”' else '‘'
            if not stack or stack[-1][0] != expected:
                if char == '’' and pos > 0 and text[pos-1].isalnum():
                    continue  # plural possessive dogs’ outside single dialogue
                return ()
            stack.pop()
            boundaries.append(QuoteBoundary(pos, pos+1, "close", char))
        elif stack and stack[-1][0] == '"':
            stack.pop()
            boundaries.append(QuoteBoundary(pos, pos+1, "close", char))
        else:
            stack.append((char, pos))
            boundaries.append(QuoteBoundary(pos, pos+1, "open", char))
    if stack:
        return ()
    return tuple(boundaries) if len(boundaries) >= 2 else ()


def dialogue_lattice(base: LexicalLattice) -> LexicalLattice | None:
    """Overlay real quote boundaries and terminal punctuation, never words."""
    boundaries = quotation_boundaries(base.text)
    if not boundaries:
        return None
    candidates = list(base.candidates)
    for boundary in boundaries:
        candidates.append(LexicalCandidate(
            span_start=boundary.start,
            span_end=boundary.end,
            surface=boundary.surface,
            lemma=boundary.surface,
            category="OPEN-QUOTE" if boundary.side == "open" else "CLOSE-QUOTE",
            features=FeatureStructure.empty(),
            source="dialogue-delimiter",
            score=0,
            provenance={"boundary":boundary.side},
        ))
        if boundary.side == "close":
            # Period and exclamation/question marks belong to the quoted
            # utterance when they precede the closing quote. They were
            # previously ignored as optional trailing sentence punctuation.
            at=boundary.start-1
            while at >= 0 and base.text[at].isspace():
                at-=1
            if at>=0 and base.text[at] in ".!?":
                candidates.append(LexicalCandidate(
                    span_start=at,span_end=at+1,
                    surface=base.text[at],lemma=base.text[at],
                    category="SPEECH-STOP",
                    features=FeatureStructure.empty(),
                    source="dialogue-delimiter",score=0,
                    provenance={"boundary":"terminal_punctuation"},
                ))
    return LexicalLattice(
        text=base.text,
        tokens=base.tokens,
        candidates=tuple(candidates),
    )
