"""Isolated Seman2 adapter for event-driven Reading Kernel proof of concept.

Production Parser, grammar, and lexical resources are not altered.
Returns a valid ChartItem only after *every* completed construction passes the
real feature unification implementation. No production parsing fallback.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from .engine import ParserResources
from .predictive import CompactNode, PredictiveParser
from .features import Variable
from .segmentation import build_lattice
from .symbols import intern
from .reading_kernel import CompiledReactions, LocalReader, ReadingNode, ReadingOutcome


@dataclass
class KernelReport:
    outcome: ReadingOutcome
    item: Any | None
    lexical_ms: float
    reading_ms: float
    materialization_ms: float

    @property
    def complete(self) -> bool:
        return self.outcome.complete and self.item is not None


class SemanReadingKernel:
    def __init__(self, resources: ParserResources):
        self.resources = resources
        self.compiled = CompiledReactions(resources.grammar)
        # Reuse production's unification and ChartItem materialization only.
        # NEVER call the existing Parser's parse/search algorithm.
        self.adapter = PredictiveParser(resources)

    @classmethod
    def from_dir(cls, directory: str | Path):
        return cls(ParserResources.from_dir(directory))

    @staticmethod
    def _leaf(node: ReadingNode) -> CompactNode:
        cand = node.candidate
        assert cand is not None
        return CompactNode(cand.category, intern(cand.category),
                           cand.span_start, cand.span_end, cand.features,
                           frozenset(n for n, v in cand.features.items()
                                     if not isinstance(v, Variable)),
                           cand.score, candidate=cand)

    def parse(self, text: str) -> KernelReport:
        t0 = perf_counter()
        lattice = build_lattice(text, self.resources.lexicon)
        t1 = perf_counter()
        memo: dict[int, CompactNode] = {}

        def combine(rule: Any, children: tuple[ReadingNode, ...]) -> ReadingNode | None:
            # Children passed through the *real* syntax unification logic.
            child_nodes = tuple(memo[id(ch)] for ch in children)
            result = PredictiveParser._reduce(rule, child_nodes)
            if result is None:
                return None
            node = ReadingNode(rule.lhs.category, children[0].start, children[-1].end,
                               rule=rule, children=children)
            memo[id(node)] = result
            return node

        class _TracedReader(LocalReader):
            def _consume(self, category: str, *, subcat: str | None = None):
                node = super()._consume(category, subcat=subcat)
                memo[id(node)] = SemanReadingKernel._leaf(node)
                return node

        machine = _TracedReader(self.compiled, combine, lattice.tokens, lattice.candidates)
        outcome = machine.read()
        t2 = perf_counter()
        item = self.adapter._materialize(memo[id(outcome.root)]) if outcome.root else None
        t3 = perf_counter()
        return KernelReport(outcome, item, (t1-t0)*1000, (t2-t1)*1000, (t3-t2)*1000)
