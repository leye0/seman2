"""Conservative disambiguation of apostrophes and curly speech delimiters."""
from __future__ import annotations

import re

_CLIPPED_ING = re.compile(r"\b[a-z]+in$", re.I)
_CONTINUATION = re.compile(r"^\s+(?:to|for|with|from|about|what|where|home)\b")
_PUNCTUATED_CLOSE = re.compile(r"[,!?;.:]’")
_LOOKAHEAD = 1200


def clipped_participle_apostrophe(text: str, index: int) -> bool:
    """Can this curly mark in an open single quotation continue a word?

    Require a written -in form, an overt lower-case continuation cue, and
    another punctuated close in the same quotation. Never scan past another
    opening single quote. The caller supplies the current quote-stack test.
    """
    if text[index] != "’" or not _CLIPPED_ING.search(text[max(0, index - 40):index]):
        return False
    tail = text[index + 1:index + 1 + _LOOKAHEAD].split("‘", 1)[0]
    return bool(_CONTINUATION.match(tail) and _PUNCTUATED_CLOSE.search(tail))
