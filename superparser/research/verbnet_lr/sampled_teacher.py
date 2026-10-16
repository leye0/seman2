"""Research-only 10% offline grammatical verification queue.

Enqueue is constant-work and NEVER runs Earley or adjusts statistics. An
external/periodic worker explicitly calls drain_teacher() outside the fast
parsing path. An Earley FOUND witness is grammar evidence, not gold truth.
UNKNOWN, budget exhaustion and misses leave the cache unchanged.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VerificationRequest:
    number: int
    text: str
    lattice: Any


class VerificationSamplingQueue:
    def __init__(self, *, every: int = 10, phase: int = 0,
                 max_pending: int = 256):
        if every < 1 or not 0 <= phase < every or max_pending < 1:
            raise ValueError("Invalid sampling or queue budget")
        self.every = every
        self.phase = phase
        self.max_pending = max_pending
        self.seen = 0
        self.sampled = 0
        self.dropped = 0
        self.processed = 0
        self.grammar_witnesses = 0
        self.unknown = 0
        self.unsupported = 0
        self._pending: deque[VerificationRequest] = deque()

    def enqueue(self, text: str, lattice: Any) -> bool:
        """Sample exactly one event per 'every' observed sentence events.

        Event sequence sampling is distinct from lexical category pruning.
        Queue overload drops a sample and is never falsely called verified.
        """
        event = self.seen
        self.seen += 1
        if event % self.every != self.phase:
            return False
        self.sampled += 1
        if len(self._pending) == self.max_pending:
            self.dropped += 1
            return False
        self._pending.append(VerificationRequest(event, text, lattice))
        return True

    @property
    def pending(self):
        return len(self._pending)

    def drain_teacher(self, index: Any, *, max_cases: int = 16,
                      max_seconds: float = 0.35) -> dict[str, int]:
        """Explicit offline worker entrypoint; never called inside parse().

        This checks a distinct derivation with the existing packed Earley
        oracle and generic construction guard. One teacher witness is not a
        certificate of uniqueness. Budget failures remain UNKNOWN.
        """
        if max_cases < 1 or max_seconds <= 0:
            raise ValueError("Invalid verifier budget")
        from research.verbnet_lr.packed_witness import seek_packed_witness
        from research.verbnet_lr.construction_guard import ConstructionGuard
        performed = found = unknown = unsupported = 0
        while self._pending and performed < max_cases:
            request = self._pending.popleft()
            performed += 1
            guard = ConstructionGuard(modal_forms={
                c.surface.casefold() for c in request.lattice.candidates
                if c.category == "MODAL"})
            report = seek_packed_witness(
                index.resources.grammar, request.lattice,
                max_seconds=max_seconds, max_items=60_000,
                max_expansions=30_000,
                max_paths_per_item=4, max_backpointers=4,
                validate_tree=guard.validate, return_compact_node=True)
            if report["status"] != "FOUND":
                unknown += 1
                continue
            try:
                item = index._materializer._materialize(report["witness_node"])
                index.observe(item, lattice=request.lattice,
                              evidence="grammar_witness")
                found += 1
            except ValueError:
                unsupported += 1
        self.processed += performed
        self.grammar_witnesses += found
        self.unknown += unknown
        self.unsupported += unsupported
        return {
            "processed": performed, "grammar_witnesses": found,
            "unknown_or_rejected": unknown,
            "unsupported": unsupported,
            "remaining": self.pending,
        }

    def summary(self):
        return {
            "seen": self.seen, "sampled": self.sampled,
            "dropped": self.dropped, "pending": self.pending,
            "processed": self.processed,
            "grammar_witnesses": self.grammar_witnesses,
            "unknown": self.unknown, "unsupported": self.unsupported,
        }
