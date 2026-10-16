"""Bounded opt-in statistics for recurring, grammar-licensed ambiguity.

No lexical words, parse trees, or grammar rules are stored. Only verified
structural choices can contribute evidence; the output is a soft hint.
No automatic reader integration: this is a research component.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Conflict:
    kind: str
    parent: str
    constituent: str
    alternatives: tuple[str, ...]
    next_categories: tuple[str, ...] = ()
    caller_expectations: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ("alternatives", "next_categories", "caller_expectations"):
            values = getattr(self, name)
            if isinstance(values, str):
                raise TypeError("Structural features must be collections")
            object.__setattr__(self, name, tuple(sorted(set(values))))
        if not 2 <= len(self.alternatives) <= 4:
            raise ValueError("Expected 2..4 grammar-licensed alternatives")
        if len(self.next_categories) > 12 or len(self.caller_expectations) > 12:
            raise ValueError("Structural signature too large")
        if not self.kind or not self.parent or not self.constituent:
            raise ValueError("A structural conflict needs context")


class SparseAmbiguityMemory:
    """Soft preference at a frequent ambiguity, never a licence to parse."""

    VALID_EVIDENCE = frozenset(("gold", "verified_correction"))

    def __init__(self, *, max_contexts=256, max_votes=64,
                 min_support=8, min_share=0.80, min_margin=4):
        if not isinstance(max_contexts, int) or max_contexts < 1:
            raise ValueError("max_contexts must be positive")
        if not isinstance(max_votes, int) or max_votes < 4:
            raise ValueError("max_votes must be >=4")
        if not isinstance(min_support, int) or not 2 <= min_support <= max_votes:
            raise ValueError("min_support must be in 2..max_votes")
        if not 0.5 < min_share <= 1 or min_margin < 1:
            raise ValueError("Invalid confidence gate")
        self.max_contexts = max_contexts
        self.max_votes = max_votes
        self.min_support = min_support
        self.min_share = min_share
        self.min_margin = min_margin
        self._counts = OrderedDict()
        self.verified_observations = 0
        self.evictions = 0

    def observe(self, conflict: Conflict, chosen: str, *, source: str) -> bool:
        # A completed automatic parse is not independent ground truth.
        if source not in self.VALID_EVIDENCE or chosen not in conflict.alternatives:
            return False
        if conflict not in self._counts:
            if len(self._counts) >= self.max_contexts:
                self._counts.popitem(last=False)
                self.evictions += 1
            self._counts[conflict] = {}
        self._counts.move_to_end(conflict)
        counts = self._counts[conflict]
        if sum(counts.values()) >= self.max_votes:
            for choice in tuple(counts):
                counts[choice] //= 2
                if not counts[choice]:
                    del counts[choice]
        counts[chosen] = counts.get(chosen, 0) + 1
        self.verified_observations += 1
        return True

    def hint(self, conflict: Conflict) -> str | None:
        """Abstain unless sufficient observations favor one viable choice."""
        counts = self._counts.get(conflict)
        if not counts:
            return None
        total = sum(counts.values())
        if total < self.min_support:
            return None
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        winner, count = ordered[0]
        runner_up = ordered[1][1] if len(ordered) > 1 else 0
        if count / total < self.min_share or count - runner_up < self.min_margin:
            return None
        return winner

    def summary(self):
        return {
            "contexts": len(self._counts),
            "stored_votes": sum(sum(v.values()) for v in self._counts.values()),
            "verified_observations": self.verified_observations,
            "evictions": self.evictions,
        }
