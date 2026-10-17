"""Compiled positional index for exact POS-slot structural-template candidates.

No parsing, unification, rule reduction, lexical sense selection, or tree
materialization happens here. All candidate POS categories at each lexical
position are retained; matching is bitset OR per slot and AND across slots.

This returns POSSIBLE template IDs. A downstream grammar verification step is
still needed before a grammatical match may be claimed. Bounded IDs returned
do not certify that unexplored templates are absent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Collection, Sequence


@dataclass(slots=True)
class _LengthBucket:
    template_ids: list[int] = field(default_factory=list)
    positions: list[dict[str, int]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class IndexedCandidates:
    template_ids: tuple[int, ...]
    total: int
    next_offset: int | None


class PositionalTemplateIndex:
    """Indexed direct lookup; independent of the grammar implementation."""

    def __init__(self):
        self.by_length: dict[int, _LengthBucket] = {}

    def add(self, categories: Sequence[str], template_id: int) -> None:
        n = len(categories)
        if not n:
            raise ValueError("Empty lexical template")
        bucket = self.by_length.get(n)
        if bucket is None:
            bucket = _LengthBucket([], [{} for _ in categories])
            self.by_length[n] = bucket
        bit = 1 << len(bucket.template_ids)
        bucket.template_ids.append(template_id)
        for position, cat in enumerate(categories):
            postings = bucket.positions[position]
            postings[cat] = postings.get(cat, 0) | bit

    def lookup(self, categories_at_positions: Sequence[Collection[str]],
               *, limit: int = 128, offset: int = 0) -> IndexedCandidates:
        if limit <= 0 or offset < 0:
            raise ValueError("Positive limit and nonnegative offset required")
        bucket = self.by_length.get(len(categories_at_positions))
        if bucket is None:
            return IndexedCandidates((), 0, None)
        mask = (1 << len(bucket.template_ids)) - 1
        for position, categories in enumerate(categories_at_positions):
            posting = bucket.positions[position]
            allowed = 0
            for category in categories:
                allowed |= posting.get(category, 0)
            mask &= allowed
            if not mask:
                return IndexedCandidates((), 0, None)
        total = mask.bit_count()
        if offset >= total:
            return IndexedCandidates((), total, None)
        # Discard the offset lowest bits without constructing every ID.
        for _ in range(offset):
            mask &= mask-1
        found = []
        while mask and len(found) < limit:
            lowest = mask & -mask
            local_id = lowest.bit_length() - 1
            found.append(bucket.template_ids[local_id])
            mask &= mask-1
        next_offset = offset+len(found) if mask else None
        return IndexedCandidates(tuple(found), total, next_offset)
