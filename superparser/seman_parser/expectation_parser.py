"""Experimental demand-driven, left-to-right syntactic parser for Seman2.

Unlike shift/reduce search, only *active grammatical expectations* can request
lexical candidates or nested productions. This is a feature-aware, prioritized
Earley-like chart with compact grammatical sharing. It emits ChartItem directly
and never invokes the production recognizer.

EXPERIMENTAL: a complete derivation is not a linguistic plausibility certificate.
This module is intentionally not imported by the production Parser.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from .engine import ParserResources
from .features import Atom, Variable, unify
from .predictive import (
    AmbiguityPoint, CompactNode, PredictiveGrammar, PredictiveParser,
    PredictiveResult, TransitionModel,
)
from .segmentation import LexicalCandidate, LexicalLattice, build_lattice
from .symbols import intern


def _binding_key(env: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    # Variable bindings are immutable as long as the partial is in the chart.
    return tuple(sorted((str(name), repr(value)) for name, value in env.items()))


def _node_key(node: CompactNode) -> tuple[Any, ...]:
    # Feature evidence and syntactic frames must not disappear when packing.
    return (
        node.grammatical_key(), tuple(sorted(node.evidence)),
        repr(node.candidate.syntactic_constraints) if node.candidate else None,
    )


def _syntax_identity(node: CompactNode) -> tuple[Any, ...]:
    """Separate different derivations while allowing grammatical sharing."""
    if node.candidate is not None:
        return ("lex", node.grammatical_key(), node.candidate.sense_id)
    return (
        node.rule.rule_id if node.rule else "?",
        tuple(_syntax_identity(child) for child in node.children),
    )


@dataclass(slots=True)
class _Partial:
    rule_index: int
    dot: int
    origin: int
    end: int
    children: tuple[CompactNode, ...] = ()
    env: dict[str, object] = field(default_factory=dict)
    score: float = 0.0


@dataclass(slots=True)
class ExpectationResult(PredictiveResult):
    _expectation_search: Any = field(default=None, repr=False, compare=False)


class _Expectations:
    """One parse session. No global forest or full-grammar pass per token."""

    def __init__(self, parser: 'ExpectationParser', text: str, lattice: LexicalLattice):
        self.parser = parser
        self.text = text
        self.lattice = lattice
        self.lex_at: dict[int, dict[int, list[LexicalCandidate]]] = defaultdict(lambda: defaultdict(list))
        for candidate in lattice.candidates:
            self.lex_at[candidate.span_start][intern(candidate.category)].append(candidate)
        self.lex_ids = {position: frozenset(categories) for position, categories in self.lex_at.items()}
        self.by_lhs: dict[int, tuple[int, ...]] = parser.by_lhs
        self.started: set[tuple[int, int]] = set()
        self.partials: dict[tuple[Any, ...], _Partial] = {}
        self.waiting: dict[tuple[int, int], list[_Partial]] = defaultdict(list)
        self.completed: dict[tuple[int, int], dict[tuple[Any, ...], list[CompactNode]]] = defaultdict(dict)
        self._identities: dict[int, tuple[Any, ...]] = {}
        self.partial_heap: list[tuple[int, float, int, _Partial]] = []
        self._lexical_node_cache: dict[int, CompactNode] = {}
        self.expected_at_position: dict[int, set[str]] = defaultdict(set)
        self.serial = count()
        self.roots: list[CompactNode] = []
        self.root_signatures: set[tuple[Any, ...]] = set()
        self.limit_hit = False
        self.stats: dict[str, int] = defaultdict(int)
        self.max_agenda = 0
        self._start_category(parser.goal_id, self._skip(0))

    def _skip(self, end: int) -> int:
        return self.parser._next_start(self.text, end)

    def _identity(self, node: CompactNode) -> tuple[Any, ...]:
        identity = self._identities.get(id(node))
        if identity is None:
            if node.candidate is not None:
                c = node.candidate
                identity = ('lex', c.category, c.span_start, c.span_end,
                            c.lemma, c.sense_id, repr(c.syntactic_constraints))
            else:
                identity = (node.rule.rule_id if node.rule else '?',
                            tuple(self._identity(child) for child in node.children))
            self._identities[id(node)] = identity
        return identity

    def _possible(self, category: int, position: int) -> bool:
        actual = self.lex_ids.get(position, frozenset())
        if not actual:
            return False
        first = self.parser.compiled.first.get(category, frozenset((category,)))
        return not first.isdisjoint(actual)

    def _start_category(self, category: int, position: int) -> None:
        self.stats['expectations_requested'] += 1
        key = (category, position)
        if key in self.started:
            return
        self.started.add(key)
        if not self._possible(category, position):
            self.stats['first_rejections'] += 1
            return
        for index in self.by_lhs.get(category, ()):
            rule = self.parser.compiled.reductions[index]
            # This check eliminates productions impossible at the next word.
            if rule.rhs_ids and not self._possible(rule.rhs_ids[0], position):
                self.stats['first_rejections'] += 1
                continue
            self._push(_Partial(index, 0, position, position))

    def _push(self, partial: _Partial) -> None:
        rule = self.parser.compiled.reductions[partial.rule_index]
        if partial.dot < len(rule.rhs_ids) and not self._possible(
            rule.rhs_ids[partial.dot], self._skip(partial.end)
        ):
            self.stats['first_rejections'] += 1
            return
        key = (
            partial.rule_index, partial.dot, partial.origin, partial.end,
            _binding_key(partial.env),
            tuple((_node_key(child), self._identity(child)) for child in partial.children),
        )
        old = self.partials.get(key)
        if old is not None:
            self.stats['shared_partials'] += 1
            if old.score >= partial.score:
                return
            # When the preferred derivation changes, explicitly revisit its
            # continuations; otherwise a lower-scored path might be frozen.
        self.partials[key] = partial
        heappush(self.partial_heap, (
            partial.end, -partial.score, next(self.serial), partial,
        ))
        self.max_agenda = max(self.max_agenda, len(self.partial_heap))
        self.stats['partial_offers'] += 1

    def _advance(self, partial: _Partial, child: CompactNode) -> None:
        row = self.parser.compiled.reductions[partial.rule_index]
        symbol = row.rule.rhs[partial.dot]
        self.stats['unification_attempts'] += 1
        if any(intern(requirement) not in child.evidence for requirement in symbol.requires):
            self.stats['feature_rejections'] += 1
            return
        merged = unify(symbol.features, child.features, partial.env)
        if merged is None:
            self.stats['feature_rejections'] += 1
            return
        _features, env = merged
        self._push(_Partial(
            partial.rule_index, partial.dot + 1, partial.origin,
            child.end, partial.children + (child,), dict(env),
            partial.score + child.score,
        ))
        self.stats['advances'] += 1

    def _make_leaf(self, candidate: LexicalCandidate) -> CompactNode:
        cached = self._lexical_node_cache.get(id(candidate))
        if cached is not None:
            return cached
        node = CompactNode(
            candidate.category, intern(candidate.category),
            candidate.span_start, candidate.span_end, candidate.features,
            frozenset(
                name for name, value in candidate.features.items()
                if not isinstance(value, Variable)
            ),
            candidate.score, candidate=candidate,
        )
        self._lexical_node_cache[id(candidate)] = node
        return node

    def _add_completed(self, node: CompactNode) -> None:
        is_root = (
            node.category_id == self.parser.goal_id
            and node.start == self._skip(0)
            and self.parser._root_span(self.text, node.end)
        )
        if is_root:
            signature = _syntax_identity(node)
            if signature not in self.root_signatures:
                self.root_signatures.add(signature)
                self.roots.append(node)
        bucket = self.completed[(node.start, node.category_id)]
        key = _node_key(node)
        alternatives = bucket.setdefault(key, [])
        if alternatives:
            self.stats['shared_nodes'] += 1
        identity = self._identity(node)
        if any(self._identity(existing) == identity for existing in alternatives):
            return
        if len(alternatives) >= self.parser.alternatives_per_node:
            weakest = min(alternatives, key=lambda current: current.score)
            if node.score <= weakest.score:
                return
            alternatives.remove(weakest)
        alternatives.append(node)
        alternatives.sort(key=lambda current: -current.score)
        self.stats['completed_offers'] += 1
        for parent in tuple(self.waiting.get((node.start, node.category_id), ())):
            self._advance(parent, node)

    def _step(self, partial: _Partial) -> None:
        row = self.parser.compiled.reductions[partial.rule_index]
        if partial.dot == len(row.rhs_ids):
            self.stats['rule_completions'] += 1
            # The actual feature checker from the existing engine is reused.
            node = self.parser._reduce(row.rule, partial.children)
            if node is None:
                self.stats['feature_rejections'] += 1
                return
            lookahead_position = self._skip(node.end)
            lookahead_ids = self.lex_ids.get(lookahead_position, frozenset())
            if self.parser.use_follow and not self.parser.compiled.reduction_viable(
                node.category_id, lookahead_ids,
                at_end=self.parser._root_span(self.text, lookahead_position),
            ):
                self.stats['follow_rejections'] += 1
                return
            # Statistical preference is for ordering, not grammatical licensing.
            categories = [child.category for child in partial.children]
            lookahead = self._best_lookahead(lookahead_position)
            prior = self.parser.model.probability(
                categories, lookahead, 'reduce:' + row.rule.rule_id,
            )
            scored = CompactNode(
                node.category, node.category_id, node.start, node.end,
                node.features, node.evidence,
                node.score + self.parser.statistical_weight * math.log(max(prior, 1e-9)),
                rule=node.rule, children=node.children,
            )
            self._add_completed(scored)
            return

        category = row.rhs_ids[partial.dot]
        position = self._skip(partial.end)
        self.stats['expectations_activated'] += 1
        self.expected_at_position[position].add(row.rule.rhs[partial.dot].category)
        # Register the continuation BEFORE predicting a recursive structure.
        self.waiting[(position, category)].append(partial)
        for group in tuple(self.completed.get((position, category), {}).values()):
            for node in tuple(group):
                self._advance(partial, node)
        for candidate in self.lex_at.get(position, {}).get(category, ()):
            self.stats['lexical_scans'] += 1
            self._advance(partial, self._make_leaf(candidate))
        self._start_category(category, position)

    def _best_lookahead(self, position: int) -> str:
        categories = self.lex_at.get(position, {})
        if not categories:
            return '$END'
        return max((cand for rows in categories.values() for cand in rows),
                   key=lambda cand: cand.score).category

    def run(self, *, roots_requested: int = 1, max_operations: int = 60_000) -> CompactNode | None:
        while self.partial_heap and len(self.roots) < roots_requested:
            if self.stats['steps'] >= max_operations:
                self.limit_hit = True
                break
            _position, _weight, _seq, partial = heappop(self.partial_heap)
            self.stats['steps'] += 1
            self._step(partial)
        if len(self.roots) >= roots_requested:
            return self.roots[roots_requested - 1]
        return None


class ExpectationParser(PredictiveParser):
    """A direct-parser POC using live grammatical expectations as the unit of work.

    No production fallback; no extra recognition pass. `expand` continues the
    same session instead of reconstructing the lexical lattice/chart.
    """

    def __init__(self, resources: ParserResources, *, model: TransitionModel | None = None,
                 max_states: int = 60_000, use_follow: bool = False,
                 statistical_weight: float = 0.15,
                 alternatives_per_node: int = 2) -> None:
        super().__init__(resources, model=model, max_states=max_states)
        self.use_follow = use_follow
        self.statistical_weight = statistical_weight
        if alternatives_per_node not in (1, 2, 3):
            raise ValueError('alternatives_per_node must be 1, 2 or 3')
        self.alternatives_per_node = alternatives_per_node
        self.by_lhs: dict[int, tuple[int, ...]] = {}
        bucket: dict[int, list[int]] = defaultdict(list)
        for rule in self.compiled.reductions:
            bucket[rule.lhs_id].append(rule.index)
        self.by_lhs = {key: tuple(value) for key, value in bucket.items()}

    @classmethod
    def from_dir(cls, directory: str | Path, **kwargs: Any) -> 'ExpectationParser':
        return cls(ParserResources.from_dir(directory), **kwargs)

    def parse(self, text: str, *, mode: str = 'fast') -> PredictiveResult:
        if mode not in {'fast', 'expand'}:
            raise ValueError("mode must be 'fast' or 'expand'")
        text = text.strip().strip('"\u201c\u201d\u2018\u2019').strip()
        started = perf_counter()
        lex_started = perf_counter()
        lattice = build_lattice(text, self.resources.lexicon, deduplicate=True)
        lexical_ms = (perf_counter() - lex_started) * 1000
        search_started = perf_counter()
        search = _Expectations(self, text, lattice)
        root = search.run(roots_requested=1, max_operations=self.max_states)
        search_ms = (perf_counter() - search_started) * 1000
        material_start = perf_counter()
        item = self._materialize(root) if root is not None else None
        material_ms = (perf_counter() - material_start) * 1000
        stats = self._stats(search, started, lexical_ms, search_ms, material_ms)
        result = ExpectationResult(
            text, item, item is not None, stats,
            (AmbiguityPoint(0, 0, 'first_complete', ('resume_expectations',)),)
            if search.partial_heap or len(search.roots) > 1 else (),
            mode == 'expand', _lattice=lattice,
        )
        result._expectation_search = search
        return result

    def expand(self, result: PredictiveResult, ambiguity_id: int) -> PredictiveResult:
        if ambiguity_id != 0:
            raise IndexError('unknown ambiguity point')
        search = getattr(result, '_expectation_search', None)
        if search is None:
            raise ValueError('no resumable expectation chart attached')
        started = perf_counter()
        search_started = perf_counter()
        root = search.run(roots_requested=2, max_operations=self.max_states * 4)
        search_ms = (perf_counter() - search_started) * 1000
        material_start = perf_counter()
        item = self._materialize(root) if root is not None else None
        material_ms = (perf_counter() - material_start) * 1000
        stats = self._stats(search, started, 0.0, search_ms, material_ms)
        return ExpectationResult(
            result.text, item, item is not None, stats,
            result.ambiguities, True, _lattice=result._lattice,
            _expectation_search=search,
        )

    @staticmethod
    def _stats(search: _Expectations, started: float, lexical_ms: float,
               search_ms: float, material_ms: float) -> dict[str, Any]:
        count = search.stats
        return {
            'engine': 'expectations-v0',
            'total_wall_ms': round((perf_counter() - started) * 1000, 4),
            'lexical_ms': round(lexical_ms, 4),
            'parsing_ms': round(search_ms, 4),
            'materialization_ms': round(material_ms, 4),
            'states_created': len(search.partials) + sum(
                len(group) for bucket in search.completed.values() for group in bucket.values()
            ),
            'transitions_executed': count['steps'] + count['advances'],
            'expectations_requested': count['expectations_requested'],
            'expectations_activated': count['expectations_activated'],
            'first_rejections': count['first_rejections'],
            'follow_rejections': count['follow_rejections'],
            'lexical_scans': count['lexical_scans'],
            'unification_attempts': count['unification_attempts'],
            'feature_rejections': count['feature_rejections'],
            'shared_partials': count['shared_partials'],
            'shared_nodes': count['shared_nodes'],
            'max_agenda': search.max_agenda,
            'known_roots': len(search.roots),
            'expected_by_position': {
                str(pos): sorted(cats)
                for pos, cats in sorted(search.expected_at_position.items())
            },
            'grammatical_derivation_found': bool(search.roots),
            'linguistically_audited': False,
            'ambiguity_enumeration_exhaustive': not bool(search.partial_heap),
            'stopped_by': ('first_complete' if search.roots else
                           'state_budget' if search.limit_hit else 'exhausted'),
            'native_success': bool(search.roots),
            'fallback': False,
        }
