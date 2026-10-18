"""Opt-in *preparse* structural-risk routing for the canonical vector grammar.

The only source of routing evidence is the existing lexical lattice and a
cheap FIRST-category index compiled from the SAME grammar. It never
prunes a reading, changes a rule or consults parse outcomes. The canonical
path is the default and receives no per-sentence predictive computation.

Thresholds MUST be explicit and independently validated before rollout.
Quotation/dialogue analysis is deliberately excluded in this first pilot.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Literal


@dataclass(frozen=True)
class ComplexityPolicy:
    """Research policy. No unvalidated implicit complexity cutoff."""
    rule_start_threshold: int
    min_tokens: int = 17
    difficult_strategy: Literal["online", "flat", "indexed"] = "flat"
    # (minimum length, maximum length, min rule starts), fitted offline;
    # never derive thresholds from a test phrase's parsing outcome.
    band_thresholds: tuple[tuple[int, int, int], ...] = ()

    def __post_init__(self) -> None:
        if self.rule_start_threshold < 1 or self.min_tokens < 1:
            raise ValueError("Complexity routing requires positive explicit thresholds")
        if self.difficult_strategy not in ("online", "flat", "indexed"):
            raise ValueError("Unrecognized difficult-sentence strategy")
        occupied = set()
        for lower, upper, threshold in self.band_thresholds:
            if lower < self.min_tokens or upper < lower or threshold < 1:
                raise ValueError("Invalid explicit length-band threshold")
            for n in range(lower, upper + 1):
                if n in occupied:
                    raise ValueError("Overlapping length-band thresholds")
                occupied.add(n)

    def threshold_for(self, token_count: int) -> int:
        for low, high, cutoff in self.band_thresholds:
            if low <= token_count <= high:
                return cutoff
        return self.rule_start_threshold


@dataclass(frozen=True)
class RoutingDecision:
    strategy: Literal["canonical", "online", "flat", "indexed"]
    reason: str
    score: int | None
    measured_ms: float
    token_count: int


class StructuralRiskRouter:
    """Bitmask FIRST-category continuation pressure, built only once.

    Counts original rule variants instead of conflating common skeletons.
    This is a predictor, not an acceptance check or substitute parser.
    """
    def __init__(self, grammar, policy: ComplexityPolicy) -> None:
        self.policy = policy
        rules = tuple(rule for rule in grammar if rule.rhs)
        categories = {s.category for rule in rules for s in rule.rhs}
        categories.update(rule.lhs.category for rule in rules)
        first = {category: {category} for category in categories}
        while True:
            changed = False
            for rule in rules:
                lhs = first[rule.lhs.category]
                before = len(lhs)
                lhs.update(first[rule.rhs[0].category])
                if len(lhs) != before:
                    changed = True
            if not changed:
                break
        masks: dict[str, int] = {}
        for i, rule in enumerate(rules):
            for category in first[rule.rhs[0].category]:
                masks[category] = masks.get(category, 0) | (1 << i)
        self.start_masks = masks

    def score(self, lattice) -> int:
        """Exactly the fast_start_sum metric from the research probe."""
        by_span: dict[tuple[int, int], set[str]] = {}
        for candidate in lattice.candidates:
            span = (candidate.span_start, candidate.span_end)
            by_span.setdefault(span, set()).add(candidate.category)
        total = 0
        for token in lattice.tokens:
            mask = 0
            for category in by_span.get((token.start, token.end), ()):
                mask |= self.start_masks.get(category, 0)
            total += mask.bit_count()
        return total

    def choose(self, lattice, *, dialogue: bool = False) -> RoutingDecision:
        count = len(lattice.tokens)
        # Hard short-circuit BEFORE any candidate-set construction.
        if dialogue:
            return RoutingDecision("canonical", "dialogue_preserved", None, 0.0, count)
        if count < self.policy.min_tokens:
            return RoutingDecision("canonical", "below_min_tokens", None, 0.0, count)
        start = perf_counter_ns()
        value = self.score(lattice)
        elapsed = (perf_counter_ns() - start) / 1e6
        if value < self.policy.threshold_for(count):
            return RoutingDecision("canonical", "risk_below_threshold", value, elapsed, count)
        return RoutingDecision(self.policy.difficult_strategy, "risk_above_threshold", value,
                               elapsed, count)
