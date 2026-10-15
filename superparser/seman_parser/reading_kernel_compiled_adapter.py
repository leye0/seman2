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
from .reading_kernel_compiled import CompiledGrammar, IncrementalReader, ReadNode, Outcome


@dataclass
class CompiledKernelReport:
    outcome: Outcome
    item: Any | None
    lexical_ms: float
    reading_ms: float
    materialization_ms: float

    @property
    def complete(self) -> bool:
        return self.outcome.complete and self.item is not None


class SemanCompiledReader:
    def __init__(self, resources: ParserResources):
        self.resources = resources
        self.compiled = CompiledGrammar(resources.grammar)
        # Reuse production's unification and ChartItem materialization only.
        # NEVER call the existing Parser's parse/search algorithm.
        self.adapter = PredictiveParser(resources)

    @classmethod
    def from_dir(cls, directory: str | Path):
        return cls(ParserResources.from_dir(directory))

    @staticmethod
    def _leaf(node: ReadNode) -> CompactNode:
        cand = node.candidate
        assert cand is not None
        return CompactNode(cand.category, intern(cand.category),
                           cand.span_start, cand.span_end, cand.features,
                           frozenset(n for n, v in cand.features.items()
                                     if not isinstance(v, Variable)),
                           cand.score, candidate=cand)

    def parse(self, text: str) -> CompiledKernelReport:
        t0 = perf_counter()
        lattice = build_lattice(text, self.resources.lexicon)
        t1 = perf_counter()
        memo: dict[int, CompactNode] = {}

        def combine(rule: Any, children: tuple[ReadNode, ...]) -> ReadNode | None:
            # Children passed through the *real* syntax unification logic.
            child_nodes = tuple(memo[id(ch)] if id(ch) in memo else self._leaf(ch)
                                for ch in children)
            result = PredictiveParser._reduce(rule, child_nodes)
            if result is None:
                return None
            node = ReadNode(rule.lhs.category, children[0].start, children[-1].end,
                               rule=rule, children=children)
            memo[id(node)] = result
            return node

        class _TracedReader(IncrementalReader):
            def _consume(self, category: str, hints=()):
                node = super()._consume(category, hints)
                memo[id(node)] = SemanCompiledReader._leaf(node)
                return node

        machine = _TracedReader(self.compiled, combine, lattice.tokens, lattice.candidates)
        outcome = machine.read()
        t2 = perf_counter()
        item = self.adapter._materialize(memo[id(outcome.root)]) if outcome.root else None
        t3 = perf_counter()
        return CompiledKernelReport(outcome, item, (t1-t0)*1000, (t2-t1)*1000, (t3-t2)*1000)
