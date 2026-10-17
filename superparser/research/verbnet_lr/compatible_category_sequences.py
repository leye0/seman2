"""Index all lexical-category enumerations without expanding the product.

An observed sentence is a series of category sets. Two sentences have a
compatible enumeration exactly when their sets intersect at every token.
This is only lexical retrieval; full syntax still needs grammar unification.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CompatibleSequenceResult:
    compatible_prior_observations: int
    first_common_enumeration: tuple[str, ...] | None
    first_observation_id: int | None

    @property
    def has_match(self) -> bool:
        return self.compatible_prior_observations > 0


@dataclass(slots=True)
class _LengthBucket:
    # For position i and category C, a bit indicates an observation with C.
    postings: list[dict[str, int]]
    observations: list[tuple[frozenset[str], ...]] = field(default_factory=list)


class CompatibleCategorySequenceIndex:
    """Exact existential match, with no Cartesian product.

    Additional lexical alternatives can only ADD matches, never remove any.
    The original candidate lattice, syntactic subcategories, features and
    semantics remain untouched for the downstream grammatical verifier.
    """

    def __init__(self):
        self._by_length: dict[int, _LengthBucket] = {}
        self.observed = 0
        self.nonempty = 0

    @staticmethod
    def lattice_slots(lattice: Any) -> tuple[frozenset[str], ...]:
        spans: dict[tuple[int, int], set[str]] = {}
        for candidate in lattice.candidates:
            spans.setdefault(
                (candidate.span_start, candidate.span_end), set()
            ).add(candidate.category)
        tokens = tuple(lattice.tokens)
        while tokens and tokens[-1].text in (".", "!", "?"):
            tokens = tokens[:-1]
        return tuple(frozenset(
            spans.get((token.start, token.end), ())
        ) for token in tokens)

    @staticmethod
    def _validate(slots) -> tuple[frozenset[str], ...]:
        if not slots:
            raise ValueError("Empty token sequence")
        return tuple(frozenset(slot) for slot in slots)

    def query(self, slots) -> CompatibleSequenceResult:
        slots = self._validate(slots)
        bucket = self._by_length.get(len(slots))
        if bucket is None or not bucket.observations or any(not x for x in slots):
            return CompatibleSequenceResult(0, None, None)
        # OR within a position, AND over positions. Exact disjunctive
        # matching, regardless of how many categories an individual word has.
        matched = (1 << len(bucket.observations)) - 1
        for pos, options in enumerate(slots):
            possible = 0
            posting = bucket.postings[pos]
            for category in options:
                possible |= posting.get(category, 0)
            matched &= possible
            if not matched:
                return CompatibleSequenceResult(0, None, None)
        first = (matched & -matched).bit_length() - 1
        witness = bucket.observations[first]
        assignment = tuple(sorted(a & b)[0] for a, b in zip(slots, witness))
        return CompatibleSequenceResult(matched.bit_count(), assignment, first)

    def observe(self, slots) -> CompatibleSequenceResult:
        """Count previously compatible sentences BEFORE inserting this one."""
        slots = self._validate(slots)
        previous = self.query(slots)
        bucket = self._by_length.get(len(slots))
        if bucket is None:
            bucket = _LengthBucket([{} for _ in slots])
            self._by_length[len(slots)] = bucket
        ident = len(bucket.observations)
        bucket.observations.append(slots)
        self.observed += 1
        self.nonempty += int(all(slots))
        bit = 1 << ident
        for pos, options in enumerate(slots):
            postings = bucket.postings[pos]
            for cat in options:
                postings[cat] = postings.get(cat, 0) | bit
        return previous

    def summary(self):
        return {
            "observed": self.observed,
            "eligible_with_candidates_in_every_slot": self.nonempty,
            "length_buckets": len(self._by_length),
        }
