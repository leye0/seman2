"""Stable source token counting only; ACE performs grammatical tokenization."""
from __future__ import annotations
import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(
    r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?|[^\w\s\"\u201c\u201d\u2018\u2019]",
    re.UNICODE,
)

@dataclass(frozen=True, slots=True)
class Token:
    index: int
    start: int
    end: int
    text: str


def tokenize(text: str) -> tuple[Token, ...]:
    return tuple(
        Token(index=i, start=match.start(), end=match.end(), text=match.group(0))
        for i, match in enumerate(_TOKEN_RE.finditer(text))
    )


