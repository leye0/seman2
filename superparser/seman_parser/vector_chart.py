"""Integrated vector recognizer with a shared, lazy k-best parse forest."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
from time import perf_counter
from typing import Any, Hashable, Sequence

from .chart import ChartItem, PackedNode, ParseResult, Provenance
from .features import (
    TOP, Atom, Bindings, Disjunction, FeatureStructure, Variable,
    substitute_structure, unify,
)
from .grammar import Grammar, GrammarRule
from .segmentation import LexicalCandidate, LexicalLattice
from .semantics import SemanticGraph, SemanticPackage, apply_action
from .symbols import intern


@dataclass(frozen=True, slots=True)
class CompiledRule:
    index: int
    rule: GrammarRule
    lhs_id: int
    lhs_mask: int
    rhs_ids: tuple[int, ...]
    rhs_masks: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LexicalDerivation:
    candidates: tuple[LexicalCandidate, ...]


@dataclass(frozen=True, slots=True)
class RuleDerivation:
    rule_index: int
    partial_id: int


Derivation = LexicalDerivation | RuleDerivation


@dataclass(slots=True)
class ForestNode:
    node_id: int
    start: int
    end: int
    category_id: int
    category: str
    mask: int
    derivations: list[Derivation] = field(default_factory=list)
    seen: set[Hashable] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class PartialDerivation:
    previous_id: int | None
    child_id: int


@dataclass(slots=True)
class PackedPartial:
    partial_id: int
    rule_index: int
    dot: int
    start: int
    end: int
    derivations: list[PartialDerivation] = field(default_factory=list)
    seen: set[tuple[int | None, int]] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class AnalysisUse:
    analysis: "CompactAnalysis"
    features: FeatureStructure
    bindings: Bindings


@dataclass(frozen=True, slots=True)
class CompactAnalysis:
    analysis_id: int
    node_id: int
    features: FeatureStructure
    score: float
    bindings: Bindings
    candidate: LexicalCandidate | None = None
    rule_index: int | None = None
    children: tuple[AnalysisUse, ...] = ()


def _value_key(value: object) -> Hashable:
    if value is TOP:
        return ("top",)
    if isinstance(value, Atom):
        return ("atom", value.symbol)
    if isinstance(value, Variable):
        return ("variable", value.name)
    if isinstance(value, Disjunction):
        return ("or", tuple(_value_key(option) for option in value.options))
    if isinstance(value, FeatureStructure):
        return _feature_key(value)
    if isinstance(value, (str, int, float, bool, type(None))):
        return (type(value).__name__, value)
    return (type(value).__name__, repr(value))


def _feature_key(features: FeatureStructure) -> Hashable:
    return tuple(sorted((name, _value_key(value)) for name, value in features.items()))


def _bindings_key(bindings: Bindings) -> Hashable:
    return tuple(sorted((name, _value_key(value)) for name, value in bindings.items()))


class VectorGrammar:
    """Compile category symbols and all grammar transitions once."""

    def __init__(self, grammar: Grammar) -> None:
        self.grammar = grammar
        self._bits: dict[int, int] = {}
        for rule in grammar:
            self._bit(rule.lhs.category)
            for symbol in rule.rhs:
                self._bit(symbol.category)
        compiled: list[CompiledRule] = []
        first: dict[int, list[int]] = {}
        for rule in grammar:
            rhs_ids = tuple(symbol.category_id for symbol in rule.rhs)
            if not rhs_ids:
                continue
            index = len(compiled)
            item = CompiledRule(
                index=index,
                rule=rule,
                lhs_id=rule.lhs.category_id,
                lhs_mask=self._bit(rule.lhs.category),
                rhs_ids=rhs_ids,
                rhs_masks=tuple(self._bit(symbol.category) for symbol in rule.rhs),
            )
            compiled.append(item)
            first.setdefault(rhs_ids[0], []).append(index)
        self.rules = tuple(compiled)
        self.first = {category: tuple(indices) for category, indices in first.items()}

    def _bit(self, category: str) -> int:
        category_id = intern(category)
        bit = self._bits.get(category_id)
        if bit is None:
            bit = 1 << len(self._bits)
            self._bits[category_id] = bit
        return bit

    def bit(self, category: str) -> int:
        return self._bit(category)

    def parse_lattice(
        self,
        lattice: LexicalLattice,
        *,
        beam: int,
        max_items: int,
        goal_category: str,
    ) -> ParseResult:
        recognition_start = perf_counter()
        forest = _VectorForest(self, lattice, max_items=max_items)
        root_nodes = forest.recognize(goal_category)
        recognition_ms = (perf_counter() - recognition_start) * 1000

        length = len(lattice.text)
        requested_k = min(beam, 2 if length > 160 else 4 if length > 80 else 8)
        materializer = _LazyMaterializer(self, forest)
        packed: dict[tuple[int, int, int], PackedNode] = {}

        def pack(item: ChartItem) -> None:
            for child in item.children:
                pack(child)
            key = item.key
            signature = item.signature()
            node = packed.get(key)
            if node is None:
                node = PackedNode(item.start, item.end, item.category, item)
                packed[key] = node
            if signature not in node.seen_signatures:
                node.add(item, signature)

        stats: dict[str, Any] = {
            "engine": "vector-lazy-kbest",
            "recognition_ms": round(recognition_ms, 4),
            "best_ms": 0.0,
            "kbest_ms": 0.0,
            "lexical_spans": forest.lexical_spans,
            "category_bits": len(self._bits),
            "forest_nodes": len(forest.nodes),
            "structural_derivations": forest.derivation_count,
            "partial_states": len(forest.partials),
            "partial_derivations": forest.partial_derivation_count,
            "recognition_operations": forest.operations,
            "unification_attempts": 0,
            "unification_cache_hits": 0,
            "constraint_context_cache_hits": 0,
            "compact_analyses": 0,
            "materialized_items": 0,
            "nodes_visited_for_best": 0,
            "combinations_visited_for_best": 0,
            "nodes_visited_total": 0,
            "combinations_visited_total": 0,
            "budget_exceeded": forest.budget_exceeded,
            "expanded": len(forest.nodes),
            "pushed": len(forest.nodes),
            "packed_nodes": 0,
            "partials": len(forest.partials),
            "goal_saturated": False,
        }
        root_provider = _LazyRoots(
            root_nodes, materializer, pack, requested_k=requested_k, stats=stats,
        )
        best_start = perf_counter()
        root_provider.ensure(1, charge_kbest=False)
        stats["best_ms"] = round((perf_counter() - best_start) * 1000, 4)
        stats["nodes_visited_for_best"] = materializer.nodes_initialized
        stats["combinations_visited_for_best"] = materializer.combinations_visited
        root_provider.refresh_stats()
        roots = LazyRootSequence(root_provider)
        return ParseResult(
            text=lattice.text,
            lattice=lattice,
            packed=packed,
            roots=roots,  # type: ignore[arg-type]
            completed=root_provider.best() is not None,
            stats=stats,
            shared_forest=forest,
        )


class _VectorForest:
    """Packed category and dotted-rule forest with no per-slot path cap."""

    def __init__(self, compiled: VectorGrammar, lattice: LexicalLattice, *, max_items: int) -> None:
        self.compiled = compiled
        self.lattice = lattice
        self.text = lattice.text
        self.max_items = max_items
        self.nodes: list[ForestNode] = []
        self.by_key: dict[tuple[int, int, int], ForestNode] = {}
        self.by_start_category: dict[tuple[int, int], list[ForestNode]] = {}
        self.partials: list[PackedPartial] = []
        self.partial_by_key: dict[tuple[int, int, int, int], PackedPartial] = {}
        self.waiting: dict[tuple[int, int], list[int]] = {}
        self.agenda: list[int] = []
        self.operations = 0
        self.derivation_count = 0
        self.partial_derivation_count = 0
        self.lexical_spans = 0
        self.budget_exceeded = False

    def _next_start(self, end: int) -> int:
        separators = ' \t\r\n"\u201c\u201d\u2018\u2019'
        while end < len(self.text) and self.text[end] in separators:
            end += 1
        return end

    def _root_span(self, start: int, end: int) -> bool:
        if start != 0:
            return False
        if end == len(self.text):
            return True
        tail = self.text[end:].strip().strip(".!?;:,\"\u201c\u201d\u2018\u2019")
        return end < len(self.text) and not tail

    def _add_node_derivation(
        self,
        start: int,
        end: int,
        category_id: int,
        category: str,
        mask: int,
        derivation: Derivation,
        signature: Hashable,
    ) -> ForestNode:
        key = (start, end, category_id)
        node = self.by_key.get(key)
        if node is None:
            node = ForestNode(len(self.nodes), start, end, category_id, category, mask)
            self.nodes.append(node)
            self.by_key[key] = node
            self.by_start_category.setdefault((start, category_id), []).append(node)
            self.agenda.append(node.node_id)
        if signature not in node.seen:
            node.seen.add(signature)
            node.derivations.append(derivation)
            self.derivation_count += 1
        return node

    def _seed_lexicon(self) -> None:
        grouped: dict[tuple[int, int], dict[int, list[LexicalCandidate]]] = {}
        for candidate in self.lattice.candidates:
            category_id = intern(candidate.category)
            grouped.setdefault((candidate.span_start, candidate.span_end), {}).setdefault(category_id, []).append(candidate)
        self.lexical_spans = len(grouped)
        for (start, end), categories in grouped.items():
            span_mask = 0
            rows: list[tuple[int, str, int, tuple[LexicalCandidate, ...]]] = []
            for category_id, candidates in categories.items():
                category = candidates[0].category
                bit = self.compiled.bit(category)
                span_mask |= bit
                rows.append((category_id, category, bit, tuple(candidates)))
            for category_id, category, bit, candidates in rows:
                if span_mask & bit:
                    self._add_node_derivation(
                        start, end, category_id, category, bit,
                        LexicalDerivation(candidates), ("lexical", category_id),
                    )

    def _add_partial(
        self,
        rule_index: int,
        dot: int,
        start: int,
        end: int,
        previous_id: int | None,
        child_id: int,
    ) -> None:
        key = (rule_index, dot, start, end)
        partial = self.partial_by_key.get(key)
        is_new = partial is None
        if partial is None:
            if len(self.nodes) + len(self.partials) >= self.max_items:
                self.budget_exceeded = True
                return
            partial = PackedPartial(len(self.partials), rule_index, dot, start, end)
            self.partials.append(partial)
            self.partial_by_key[key] = partial
            self.operations += 1
        signature = (previous_id, child_id)
        if signature not in partial.seen:
            partial.seen.add(signature)
            partial.derivations.append(PartialDerivation(previous_id, child_id))
            self.partial_derivation_count += 1
        if not is_new:
            return
        rule = self.compiled.rules[rule_index]
        if dot >= len(rule.rhs_ids):
            self._add_node_derivation(
                start, end, rule.lhs_id, rule.rule.lhs.category, rule.lhs_mask,
                RuleDerivation(rule_index, partial.partial_id),
                ("rule", rule_index, partial.partial_id),
            )
            return
        position = self._next_start(end)
        expected_id = rule.rhs_ids[dot]
        self.waiting.setdefault((position, expected_id), []).append(partial.partial_id)
        for node in tuple(self.by_start_category.get((position, expected_id), ())):
            if node.mask & rule.rhs_masks[dot]:
                self._advance(partial, node)

    def _advance(self, partial: PackedPartial, node: ForestNode) -> None:
        rule = self.compiled.rules[partial.rule_index]
        if partial.dot < len(rule.rhs_masks) and node.mask & rule.rhs_masks[partial.dot]:
            self._add_partial(
                partial.rule_index, partial.dot + 1, partial.start, node.end,
                partial.partial_id, node.node_id,
            )

    def recognize(self, goal_category: str) -> tuple[ForestNode, ...]:
        self._seed_lexicon()
        cursor = 0
        while cursor < len(self.agenda) and not self.budget_exceeded:
            node = self.nodes[self.agenda[cursor]]
            cursor += 1
            self.operations += 1
            for rule_index in self.compiled.first.get(node.category_id, ()):
                rule = self.compiled.rules[rule_index]
                if node.mask & rule.rhs_masks[0]:
                    self._add_partial(rule_index, 1, node.start, node.end, None, node.node_id)
            for partial_id in tuple(self.waiting.get((node.start, node.category_id), ())):
                self._advance(self.partials[partial_id], node)
        goal_id = intern(goal_category)
        return tuple(
            node for node in self.nodes
            if node.category_id == goal_id and self._root_span(node.start, node.end)
        )


@dataclass(slots=True)
class _PathState:
    initialized: bool = False
    exhausted: bool = False
    results: list[tuple[tuple[int, ...], float]] = field(default_factory=list)
    heap: list[tuple[float, int, int, int, tuple[int, ...], float]] = field(default_factory=list)
    pushed: set[tuple[int, int]] = field(default_factory=set)
    seen_results: set[tuple[int, ...]] = field(default_factory=set)


@dataclass(slots=True)
class _NodeState:
    constraint: FeatureStructure
    bindings: Bindings
    initialized: bool = False
    initializing: bool = False
    exhausted: bool = False
    results: list[CompactAnalysis] = field(default_factory=list)
    heap: list[tuple[float, int, str, Any]] = field(default_factory=list)
    pushed_rules: set[tuple[int, int, tuple[int, ...]]] = field(default_factory=set)
    scheduled_rules: set[tuple[int, int, tuple[int, ...]]] = field(default_factory=set)
    seen_results: set[Hashable] = field(default_factory=set)


class _LazyMaterializer:
    """Demand-driven k-best extraction with feature-aware failure recovery."""

    RULE_COST = 0.5

    def __init__(self, compiled: VectorGrammar, forest: _VectorForest) -> None:
        self.compiled = compiled
        self.forest = forest
        self.node_states: dict[tuple[int, Hashable], _NodeState] = {}
        self.path_states: dict[int, _PathState] = {}
        self.item_cache: dict[tuple[str, int], ChartItem] = {}
        self.unification_cache: dict[
            Hashable,
            tuple[FeatureStructure, Bindings, tuple[AnalysisUse, ...]] | None,
        ] = {}
        self._serial = count()
        self._analysis_ids = count(1)
        self.analysis_count = 0
        self.unification_attempts = 0
        self.unification_cache_hits = 0
        self.context_cache_hits = 0
        self.nodes_initialized = 0
        self.combinations_visited = 0
        self._node_hints: dict[int, float] = {}
        self._partial_hints: dict[int, float] = {}
        self._constrained_node_hints: dict[tuple[int, Hashable], float] = {}
        self._constrained_partial_hints: dict[int, float] = {}
        self._hint_nodes_active: set[int] = set()
        self._hint_partials_active: set[int] = set()
        self._active_contexts: set[tuple[int, Hashable]] = set()

    def get(
        self,
        node_id: int,
        rank: int,
        constraint: FeatureStructure | None = None,
        bindings: Bindings | None = None,
    ) -> CompactAnalysis | None:
        required = constraint if constraint is not None else FeatureStructure.empty()
        inherited = dict(bindings or {})
        context_key = (_feature_key(required), _bindings_key(inherited))
        active_key = (node_id, context_key)
        # Only the exact same constrained subproblem is cyclic.  The same
        # span/category may legitimately reappear after a unary rule changes
        # its feature context.
        if active_key in self._active_contexts:
            return None
        self._active_contexts.add(active_key)
        try:
            return self._get_contextual(
                node_id, rank, required, inherited, context_key,
            )
        finally:
            self._active_contexts.remove(active_key)

    def _get_contextual(
        self,
        node_id: int,
        rank: int,
        required: FeatureStructure,
        inherited: Bindings,
        context_key: Hashable,
    ) -> CompactAnalysis | None:
        cache_key = (node_id, context_key)
        state = self.node_states.get(cache_key)
        if state is None:
            state = _NodeState(required, inherited)
            self.node_states[cache_key] = state
        else:
            self.context_cache_hits += 1
        if state.initializing:
            return None
        if not state.initialized:
            self._initialize_node(node_id, state)
        while len(state.results) <= rank and state.heap:
            negative_bound, _, kind, payload = heappop(state.heap)
            if kind == "lexical":
                candidate, merged, env = payload
                signature = ("lexical", id(candidate))
                if signature in state.seen_results:
                    continue
                state.seen_results.add(signature)
                analysis = CompactAnalysis(
                    next(self._analysis_ids), node_id, merged,
                    candidate.score, env, candidate=candidate,
                )
            elif kind in {"rule_seed", "rule_retry"}:
                derivation_index, path_rank, ranks = payload
                state.scheduled_rules.discard((derivation_index, path_rank, ranks))
                self._push_rule(node_id, state, derivation_index, path_rank, ranks)
                continue
            else:
                derivation_index, path_rank, ranks, path, combo = payload
                derivation = self.forest.nodes[node_id].derivations[derivation_index]
                assert isinstance(derivation, RuleDerivation)
                # Neighbours are retained before unification.  A failed high
                # scoring combination therefore cannot hide a later valid one.
                for axis in range(len(ranks)):
                    neighbour = list(ranks)
                    neighbour[axis] += 1
                    self._schedule_rule(
                        state, derivation_index, path_rank, tuple(neighbour), -negative_bound,
                    )
                signature = (derivation.rule_index, tuple(child.analysis_id for child in combo))
                if signature in state.seen_results:
                    continue
                state.seen_results.add(signature)
                rule = self.compiled.rules[derivation.rule_index].rule
                lhs_features, env, uses = self._compose_rule_context(
                    state, derivation.rule_index, rule, combo,
                )
                analysis = CompactAnalysis(
                    next(self._analysis_ids), node_id, lhs_features,
                    sum(child.score for child in combo) + rule.score - self.RULE_COST,
                    env, rule_index=derivation.rule_index, children=uses,
                )
            state.results.append(analysis)
            self.analysis_count += 1
        if len(state.results) <= rank:
            state.exhausted = True
            return None
        return state.results[rank]

    def _initialize_node(self, node_id: int, state: _NodeState) -> None:
        if state.initializing:
            return
        state.initializing = True
        self.nodes_initialized += 1
        node = self.forest.nodes[node_id]
        for derivation_index, derivation in enumerate(node.derivations):
            if isinstance(derivation, LexicalDerivation):
                for candidate in derivation.candidates:
                    self.unification_attempts += 1
                    result = unify(state.constraint, candidate.features, state.bindings)
                    if result is None:
                        continue
                    merged, env = result
                    heappush(state.heap, (
                        -candidate.score, next(self._serial), "lexical", (candidate, merged, env),
                    ))
            else:
                rule = self.compiled.rules[derivation.rule_index].rule
                self.unification_attempts += 1
                if unify(state.constraint, rule.lhs.features, state.bindings) is None:
                    continue
                bound = (
                    self._constrained_partial_hint(derivation.partial_id)
                    + rule.score - self.RULE_COST
                )
                heappush(state.heap, (
                    -bound, next(self._serial), "rule_seed", (derivation_index, 0, ()),
                ))
        state.initializing = False
        state.initialized = True

    def _push_rule(
        self,
        node_id: int,
        state: _NodeState,
        derivation_index: int,
        path_rank: int,
        ranks: tuple[int, ...],
    ) -> None:
        derivation = self.forest.nodes[node_id].derivations[derivation_index]
        if not isinstance(derivation, RuleDerivation):
            return
        path_row = self._get_path(derivation.partial_id, path_rank)
        if path_row is None:
            return
        path, _path_bound = path_row
        if not ranks:
            ranks = tuple(0 for _ in path)
            following = self._get_path(derivation.partial_id, path_rank + 1)
            if following is not None:
                rule = self.compiled.rules[derivation.rule_index].rule
                heappush(state.heap, (
                    -(following[1] + rule.score - self.RULE_COST),
                    next(self._serial), "rule_seed", (derivation_index, path_rank + 1, ()),
                ))
        if len(ranks) != len(path):
            return
        key = (derivation_index, path_rank, ranks)
        if key in state.pushed_rules:
            return
        # Reserve before descending into contextual child streams.  Cyclic
        # grammar paths and failed sibling contexts can otherwise reschedule
        # the same tuple recursively.
        state.pushed_rules.add(key)
        # Count every combination we actually inspect, including candidates
        # that are subsequently rejected by a contextual unification.
        self.combinations_visited += 1
        combo: list[CompactAnalysis] = []
        rule = self.compiled.rules[derivation.rule_index].rule
        self.unification_attempts += 1
        lhs_result = unify(state.constraint, rule.lhs.features, state.bindings)
        if lhs_result is None:
            return
        _lhs_merged, env = lhs_result
        for index, (child_id, rank) in enumerate(zip(path, ranks)):
            child = self.get(child_id, rank, rule.rhs[index].features, env)
            if child is None:
                # A later child can reject bindings chosen by an earlier one.
                # Continue lazily with the next earlier alternative.
                for axis in range(index):
                    neighbour = list(ranks)
                    neighbour[axis] += 1
                    self._schedule_rule(
                        state, derivation_index, path_rank, tuple(neighbour),
                        self._rule_bound(path, rule),
                    )
                return
            combo.append(child)
            env = dict(child.bindings)
        score = sum(child.score for child in combo) + rule.score - self.RULE_COST
        heappush(state.heap, (
            -score, next(self._serial), "rule",
            (derivation_index, path_rank, ranks, path, tuple(combo)),
        ))

    def _schedule_rule(
        self,
        state: _NodeState,
        derivation_index: int,
        path_rank: int,
        ranks: tuple[int, ...],
        bound: float,
    ) -> None:
        key = (derivation_index, path_rank, ranks)
        if key in state.pushed_rules or key in state.scheduled_rules:
            return
        state.scheduled_rules.add(key)
        heappush(state.heap, (
            -bound, next(self._serial), "rule_retry", key,
        ))

    def _rule_bound(self, path: tuple[int, ...], rule: GrammarRule) -> float:
        return (
            sum(
                self._constrained_node_hint(child_id, symbol.features)
                for child_id, symbol in zip(path, rule.rhs)
            )
            + rule.score - self.RULE_COST
        )

    def _get_path(self, partial_id: int, rank: int) -> tuple[tuple[int, ...], float] | None:
        state = self.path_states.setdefault(partial_id, _PathState())
        partial = self.forest.partials[partial_id]
        if not state.initialized:
            state.initialized = True
            for derivation_index in range(len(partial.derivations)):
                self._push_path(partial, state, derivation_index, 0)
        while len(state.results) <= rank and state.heap:
            _, _, derivation_index, previous_rank, path, score = heappop(state.heap)
            derivation = partial.derivations[derivation_index]
            if derivation.previous_id is not None:
                self._push_path(partial, state, derivation_index, previous_rank + 1)
            if path in state.seen_results:
                continue
            state.seen_results.add(path)
            state.results.append((path, score))
        if len(state.results) <= rank:
            state.exhausted = True
            return None
        return state.results[rank]

    def _push_path(
        self,
        partial: PackedPartial,
        state: _PathState,
        derivation_index: int,
        previous_rank: int,
    ) -> None:
        key = (derivation_index, previous_rank)
        if key in state.pushed:
            return
        derivation = partial.derivations[derivation_index]
        rule = self.compiled.rules[partial.rule_index].rule
        child_bound = self._constrained_node_hint(
            derivation.child_id, rule.rhs[partial.dot - 1].features,
        )
        if derivation.previous_id is None:
            if previous_rank:
                return
            path = (derivation.child_id,)
            score = child_bound
        else:
            previous = self._get_path(derivation.previous_id, previous_rank)
            if previous is None:
                return
            previous_path, previous_score = previous
            path = previous_path + (derivation.child_id,)
            score = previous_score + child_bound
        state.pushed.add(key)
        heappush(state.heap, (
            -score, next(self._serial), derivation_index, previous_rank, path, score,
        ))

    def _node_hint(self, node_id: int) -> float:
        cached = self._node_hints.get(node_id)
        if cached is not None:
            return cached
        if node_id in self._hint_nodes_active:
            return float("-inf")
        self._hint_nodes_active.add(node_id)
        best = float("-inf")
        for derivation in self.forest.nodes[node_id].derivations:
            if isinstance(derivation, LexicalDerivation):
                if derivation.candidates:
                    best = max(best, max(candidate.score for candidate in derivation.candidates))
            else:
                rule = self.compiled.rules[derivation.rule_index].rule
                best = max(
                    best,
                    self._partial_hint(derivation.partial_id) + rule.score - self.RULE_COST,
                )
        self._hint_nodes_active.remove(node_id)
        self._node_hints[node_id] = best
        return best

    def _partial_hint(self, partial_id: int) -> float:
        cached = self._partial_hints.get(partial_id)
        if cached is not None:
            return cached
        if partial_id in self._hint_partials_active:
            return float("-inf")
        self._hint_partials_active.add(partial_id)
        best = float("-inf")
        partial = self.forest.partials[partial_id]
        for derivation in partial.derivations:
            child = self._node_hint(derivation.child_id)
            if derivation.previous_id is None:
                score = child
            else:
                score = self._partial_hint(derivation.previous_id) + child
            best = max(best, score)
        self._hint_partials_active.remove(partial_id)
        self._partial_hints[partial_id] = best
        return best

    def _constrained_node_hint(
        self,
        node_id: int,
        constraint: FeatureStructure,
    ) -> float:
        key = (node_id, _feature_key(constraint))
        cached = self._constrained_node_hints.get(key)
        if cached is not None:
            return cached
        if node_id in self._hint_nodes_active:
            return float("-inf")
        self._hint_nodes_active.add(node_id)
        best = float("-inf")
        for derivation in self.forest.nodes[node_id].derivations:
            if isinstance(derivation, LexicalDerivation):
                for candidate in derivation.candidates:
                    if unify(constraint, candidate.features) is not None:
                        best = max(best, candidate.score)
            else:
                rule = self.compiled.rules[derivation.rule_index].rule
                if unify(constraint, rule.lhs.features) is None:
                    continue
                best = max(
                    best,
                    self._constrained_partial_hint(derivation.partial_id)
                    + rule.score - self.RULE_COST,
                )
        self._hint_nodes_active.remove(node_id)
        self._constrained_node_hints[key] = best
        return best

    def _constrained_partial_hint(self, partial_id: int) -> float:
        cached = self._constrained_partial_hints.get(partial_id)
        if cached is not None:
            return cached
        if partial_id in self._hint_partials_active:
            return float("-inf")
        self._hint_partials_active.add(partial_id)
        partial = self.forest.partials[partial_id]
        rule = self.compiled.rules[partial.rule_index].rule
        symbol = rule.rhs[partial.dot - 1]
        best = float("-inf")
        for derivation in partial.derivations:
            child = self._constrained_node_hint(derivation.child_id, symbol.features)
            if derivation.previous_id is None:
                score = child
            else:
                score = self._constrained_partial_hint(derivation.previous_id) + child
            best = max(best, score)
        self._hint_partials_active.remove(partial_id)
        self._constrained_partial_hints[partial_id] = best
        return best

    def _compose_rule_context(
        self,
        state: _NodeState,
        rule_index: int,
        rule: GrammarRule,
        combo: tuple[CompactAnalysis, ...],
    ) -> tuple[FeatureStructure, Bindings, tuple[AnalysisUse, ...]]:
        key = (
            rule_index,
            tuple(child.analysis_id for child in combo),
            _feature_key(state.constraint),
            _bindings_key(state.bindings),
        )
        if key in self.unification_cache:
            self.unification_cache_hits += 1
            cached = self.unification_cache[key]
            assert cached is not None
            return cached
        self.unification_attempts += 1
        lhs_result = unify(state.constraint, rule.lhs.features, state.bindings)
        assert lhs_result is not None
        lhs_merged, env = lhs_result
        uses: list[AnalysisUse] = []
        for symbol, child in zip(rule.rhs, combo):
            env = dict(child.bindings)
            uses.append(AnalysisUse(child, child.features, dict(env)))
        result = (substitute_structure(lhs_merged, env), dict(env), tuple(uses))
        self.unification_cache[key] = result
        return result

    def item(self, analysis: CompactAnalysis) -> ChartItem:
        key = ("analysis", analysis.analysis_id)
        cached = self.item_cache.get(key)
        if cached is not None:
            return cached
        return self._build_item(analysis, analysis.features, analysis.bindings, key)

    def _item_for_use(self, use: AnalysisUse) -> ChartItem:
        key = ("use", id(use))
        cached = self.item_cache.get(key)
        if cached is not None:
            return cached
        return self._build_item(use.analysis, use.features, use.bindings, key)

    def _build_item(
        self,
        analysis: CompactAnalysis,
        features: FeatureStructure,
        bindings: Bindings,
        cache_key: tuple[str, int],
    ) -> ChartItem:
        node = self.forest.nodes[analysis.node_id]
        if analysis.candidate is not None:
            candidate = analysis.candidate
            graph = SemanticGraph()
            kind = "event" if candidate.category.upper().startswith("V") else "entity"
            semantic_node = graph.add_node(
                kind=kind,
                type_name=candidate.semantic_type or candidate.lemma.upper(),
                span=candidate.span,
                surface=candidate.surface,
                lemma=candidate.lemma,
            )
            handles = {"head": semantic_node.node_id, "referent": semantic_node.node_id}
            if kind == "event":
                handles["event"] = semantic_node.node_id
            item = ChartItem(
                node.start, node.end, node.category, features,
                SemanticPackage(graph, handles), analysis.score,
                Provenance(candidate.source, {
                    "surface": candidate.surface,
                    "lemma": candidate.lemma,
                    "sense_id": candidate.sense_id,
                }),
                bindings=bindings,
                _sig=analysis.analysis_id,
            )
            self.item_cache[cache_key] = item
            return item

        assert analysis.rule_index is not None
        rule = self.compiled.rules[analysis.rule_index].rule
        children = tuple(self._item_for_use(use) for use in analysis.children)
        aliases: Bindings = dict(bindings)
        for symbol, child in zip(rule.rhs, children):
            for child_name, rule_name in symbol.exports.items():
                resolved = child.semantic.handles.get(child_name)
                if resolved:
                    aliases[rule_name] = resolved
            for name in ("referent", "event", "head"):
                resolved = child.semantic.handles.get(name)
                if resolved:
                    aliases.setdefault(name, resolved)
        semantic = self._compose(rule, children, aliases)
        item = ChartItem(
            node.start, node.end, node.category, features, semantic, analysis.score,
            Provenance("rule", {
                "rule_id": rule.rule_id,
                "children": tuple(child.provenance for child in children),
            }),
            children=children,
            rule_id=rule.rule_id,
            bindings=aliases,
            _sig=analysis.analysis_id,
        )
        self.item_cache[cache_key] = item
        return item

    @staticmethod
    def _compose(rule: GrammarRule, children: tuple[ChartItem, ...], aliases: Bindings) -> SemanticPackage:
        child_graphs = [child.semantic.graph for child in children]
        child_handles = [child.semantic.handles for child in children]
        handle_aliases = {key: value for key, value in aliases.items() if isinstance(value, str) and value}
        graph = SemanticGraph.merge_all(child_graphs)
        if not rule.semantic:
            handles: dict[str, str] = dict(handle_aliases)
            for child in children:
                for key, value in child.semantic.handles.items():
                    handles.setdefault(key, value)
            return SemanticPackage(graph, handles)
        package = SemanticPackage(graph, dict(handle_aliases))
        for action in rule.semantic:
            package = apply_action(
                action,
                package=package,
                child_handles=child_handles,
                child_graphs=child_graphs,
                aliases=handle_aliases,
            )
        return package


class _LazyRoots:
    def __init__(
        self,
        root_nodes: Sequence[ForestNode],
        materializer: _LazyMaterializer,
        pack: Any,
        *,
        requested_k: int,
        stats: dict[str, Any],
    ) -> None:
        self.root_nodes = tuple(root_nodes)
        self.materializer = materializer
        self.pack = pack
        self.requested_k = max(1, requested_k)
        self.stats = stats
        self.items: list[ChartItem] = []
        self.heap: list[tuple[float, int, int, CompactAnalysis]] = []
        self._serial = count()
        self.initialized = False

    def _initialize(self) -> None:
        if self.initialized:
            return
        self.initialized = True
        for node in self.root_nodes:
            analysis = self.materializer.get(node.node_id, 0)
            if analysis is not None:
                heappush(self.heap, (-analysis.score, next(self._serial), 0, analysis))

    def ensure(self, amount: int, *, charge_kbest: bool = True) -> None:
        start = perf_counter()
        self._initialize()
        while len(self.items) < amount and self.heap:
            _, _, rank, analysis = heappop(self.heap)
            item = self.materializer.item(analysis)
            self.items.append(item)
            self.pack(item)
            following = self.materializer.get(analysis.node_id, rank + 1)
            if following is not None:
                heappush(self.heap, (-following.score, next(self._serial), rank + 1, following))
        if charge_kbest:
            self.stats["kbest_ms"] = round(
                float(self.stats["kbest_ms"]) + (perf_counter() - start) * 1000,
                4,
            )
        self.refresh_stats()

    def refresh_stats(self) -> None:
        materializer = self.materializer
        self.stats["unification_attempts"] = materializer.unification_attempts
        self.stats["unification_cache_hits"] = materializer.unification_cache_hits
        self.stats["constraint_context_cache_hits"] = materializer.context_cache_hits
        self.stats["compact_analyses"] = materializer.analysis_count
        self.stats["materialized_items"] = len(materializer.item_cache)
        self.stats["nodes_visited_total"] = materializer.nodes_initialized
        self.stats["combinations_visited_total"] = materializer.combinations_visited
        self.stats["packed_nodes"] = len({item.key for item in materializer.item_cache.values()})
        self.stats["goal_saturated"] = len(self.items) >= self.requested_k

    def best(self) -> ChartItem | None:
        self.ensure(1, charge_kbest=False)
        return self.items[0] if self.items else None


class LazyRootSequence(Sequence[ChartItem]):
    """Sequence facade that asks the root heap for analyses only on demand."""

    def __init__(self, provider: _LazyRoots) -> None:
        self.provider = provider

    def best(self) -> ChartItem | None:
        return self.provider.best()

    def take(self, limit: int) -> tuple[ChartItem, ...]:
        if limit <= 0:
            return ()
        self.provider.ensure(min(limit, self.provider.requested_k))
        return tuple(self.provider.items[:limit])

    def __len__(self) -> int:
        self.provider.ensure(self.provider.requested_k)
        return len(self.provider.items)

    def __getitem__(self, index: int | slice) -> ChartItem | Sequence[ChartItem]:
        if isinstance(index, slice):
            stop = index.stop
            amount = self.provider.requested_k if stop is None or stop < 0 else stop
            self.provider.ensure(min(amount, self.provider.requested_k))
            return self.provider.items[index]
        if index < 0:
            self.provider.ensure(self.provider.requested_k)
        else:
            self.provider.ensure(min(index + 1, self.provider.requested_k))
        return self.provider.items[index]

    def __iter__(self) -> Iterator[ChartItem]:
        self.provider.ensure(self.provider.requested_k)
        return iter(self.provider.items)


__all__ = ["LazyRootSequence", "VectorGrammar"]
