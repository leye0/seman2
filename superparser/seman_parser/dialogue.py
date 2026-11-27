"""Source quote delimiters; no grammar or lexical lattice."""
from __future__ import annotations
from dataclasses import dataclass
from .quote_orthography import clipped_participle_apostrophe

@dataclass(frozen=True, slots=True)
class QuoteBoundary:
    start: int
    end: int
    side: str
    surface: str


def quotation_boundaries(text: str) -> tuple[QuoteBoundary, ...]:
    """Recognize balanced dialogue quotes without inventing missing ones.

    Double and paired single quotes (ASCII or curly) are delimiters.
    Internal apostrophes in contractions/possessives are never quote
    boundaries; a lone trailing possessive apostrophe is also ignored.
    """
    stack: list[tuple[str, int]] = []
    boundaries: list[QuoteBoundary] = []
    for pos, char in enumerate(text):
        if char not in {'"', "'", '“', '”', '‘', '’'}:
            continue
        if char == "'":
            previous = text[pos - 1] if pos else ""
            following = text[pos + 1] if pos + 1 < len(text) else ""
            if previous.isalnum() and following.isalnum():
                continue
            if stack and stack[-1][0] == "'":
                stack.pop()
                boundaries.append(QuoteBoundary(pos, pos + 1, "close", char))
                continue
            if previous.isalnum() or not following or not following.isalnum():
                continue
            stack.append((char, pos))
            boundaries.append(QuoteBoundary(pos, pos + 1, "open", char))
            continue
        if char == '’' and 0 < pos < len(text)-1:
            if text[pos-1].isalnum() and text[pos+1].isalnum():
                continue  # don't, I've, John’s — lexical apostrophe
            if stack and stack[-1][0] == "‘" and clipped_participle_apostrophe(text, pos):
                continue
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


