"""Integrated vector recognizer with a shared, lazy k-best parse forest."""

from __future__ import annotations

from collections.abc import Iterator
import json
from dataclasses import dataclass, field, replace
from heapq import heappop, heappush
from itertools import count
from time import perf_counter
from typing import Any, Hashable, Sequence

from .chart import ChartItem, PackedNode, ParseResult, Provenance, _compose_syntax, _lexical_syntax
from .features import (
    TOP, Atom, Bindings, Disjunction, FeatureStructure, Variable,
    substitute_structure, unify,
)
from .grammar import Grammar, GrammarRule
from .prefix_edges import OnlinePrefixEdges, FlatOnlinePrefixEdges
from .segmentation import LexicalCandidate, LexicalLattice
from .syntax import SyntacticLink, SyntacticPackage
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
    waiting_cutoff: int = 0
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
    # When online_prefix_edges is enabled, 'derivations' is a lazy
    # rule-specific PrefixEdgeView instead of a Python object list.
    derivations: Sequence[PartialDerivation] = field(default_factory=list)
    seen: set[tuple[int | None, int]] | None = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class AnalysisUse:
    analysis: "CompactAnalysis"
    features: FeatureStructure
    bindings: Bindings


@dataclass(slots=True)
class SegmentInterface:
    """Lazy grammatical view of one independently recognized clause."""

    result: ParseResult
    offset: int
    start: int
    end: int
    _items: dict[int, ChartItem] = field(default_factory=dict, repr=False)

    def get(self, rank: int) -> ChartItem | None:
        cached = self._items.get(rank)
        if cached is not None:
            return cached
        alternatives = self.result.alternatives(limit=rank + 1)
        if rank >= len(alternatives):
            return None
        shifted = _shift_chart_item(alternatives[rank], self.offset)
        if shifted.category == "CLAUSE" and "event" not in shifted.syntax.anchors:
            handles = dict(shifted.syntax.anchors)
            event_id = next((handles[name] for name in ("main", "predicate", "sub") if name in handles), None)
            if event_id is None:
                event_id = f"clause:{shifted.start}:{shifted.end}"
            handles["event"] = event_id
            shifted = ChartItem(
                shifted.start, shifted.end, shifted.category, shifted.features,
                None, shifted.score,
                shifted.provenance, children=shifted.children,
                rule_id=shifted.rule_id, bindings=shifted.bindings,
                syntax=SyntacticPackage(handles, shifted.syntax.links),
                _sig=shifted.signature(),
            )
        self._items[rank] = shifted
        return shifted


@dataclass(frozen=True, slots=True)
class CompactAnalysis:
    analysis_id: int
    node_id: int
    features: FeatureStructure
    score: float
    bindings: Bindings
    evidence: frozenset[int] = frozenset()
    candidate: LexicalCandidate | None = None
    interface_item: ChartItem | None = None
    rule_index: int | None = None
    children: tuple[AnalysisUse, ...] = ()


def _feature_evidence(features: FeatureStructure) -> frozenset[int]:
    """Features intrinsically asserted by a lexical or interface item."""
    return frozenset(
        name for name, value in features.items()
        if value is not TOP and not isinstance(value, Variable)
    )


def _rule_evidence(
    rule: GrammarRule,
    children: Sequence[CompactAnalysis],
) -> frozenset[int]:
    """Features asserted by a rule or positively propagated from children."""
    evidence: set[int] = set()
    for lhs_name, lhs_value in rule.lhs.features.items():
        if lhs_value is TOP:
            continue
        if not isinstance(lhs_value, Variable):
            evidence.add(lhs_name)
            continue
        for symbol, child in zip(rule.rhs, children):
            for rhs_name, rhs_value in symbol.features.items():
                if (
                    isinstance(rhs_value, Variable)
                    and rhs_value.name == lhs_value.name
                    and rhs_name in child.evidence
                ):
                    evidence.add(lhs_name)
                    break
            if lhs_name in evidence:
                break
    return frozenset(evidence)


def _rule_may_provide_evidence(
    rule: GrammarRule,
    required_features: frozenset[int] | set[int],
) -> bool:
    """Return whether a rule can possibly establish every required feature.

    This is the static counterpart of :func:`_rule_evidence`.  It deliberately
    remains optimistic when evidence can be propagated from a child, keeping
    the hint admissible while excluding rules whose LHS cannot establish the
    requested proof at all.
    """
    lhs_features = dict(rule.lhs.features.items())
    for required in required_features:
        value = lhs_features.get(required, TOP)
        if value is TOP:
            return False
        if not isinstance(value, Variable):
            continue
        if not any(
            isinstance(rhs_value, Variable)
            and rhs_value.name == value.name
            for symbol in rule.rhs
            for _rhs_name, rhs_value in symbol.features.items()
        ):
            return False
    return True


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


def _required_feature_ids(features: Sequence[str | int]) -> tuple[int, ...]:
    return tuple(sorted(
        intern(name) if isinstance(name, str) else name for name in features
    ))


def _context_key(
    constraint: FeatureStructure,
    bindings: Bindings,
    required_ids: tuple[int, ...],
) -> Hashable:
    return (_feature_key(constraint), _bindings_key(bindings), required_ids)


def _variable_names(value: object) -> set[str]:
    if isinstance(value, Variable):
        return {value.name}
    if isinstance(value, FeatureStructure):
        names: set[str] = set()
        for _, child in value.items():
            names.update(_variable_names(child))
        return names
    if isinstance(value, Disjunction):
        names = set()
        for child in value.options:
            names.update(_variable_names(child))
        return names
    return set()


def _project_bindings(
    constraint: FeatureStructure,
    bindings: Bindings,
) -> tuple[Bindings, frozenset[str]]:
    """Keep only inherited variables reachable from the child interface."""
    relevant = _variable_names(constraint)
    pending = list(relevant)
    while pending:
        name = pending.pop()
        bound = bindings.get(name)
        if bound is None:
            continue
        for dependency in _variable_names(bound) - relevant:
            relevant.add(dependency)
            pending.append(dependency)
    return (
        {name: value for name, value in bindings.items() if name in relevant},
        frozenset(relevant),
    )


class VectorGrammar:
    """Compile category symbols and all grammar transitions once."""

    def __init__(self, grammar: Grammar, *, early_lexical_filter: bool = False,
                 preserve_quote_delimiters: bool = False,
                 cache_boundaries: bool = False,
                 online_prefix_edges: bool = False,
                 flat_prefix_edges: bool = False) -> None:
        self.grammar = grammar
        # Research A/B switch. Default OFF: canonical behaviour is unchanged.
        self.early_lexical_filter = early_lexical_filter
        # Scoped dialogue grammar consumes quotation punctuation explicitly.
        self.preserve_quote_delimiters = preserve_quote_delimiters
        # Research A/B: memoize identical punctuation/whitespace boundary
        # scans within a sentence. Default off pending paired benchmarks.
        self.cache_boundaries = cache_boundaries
        # Experimental online group edge interning; canonical mode remains
        # byte-for-byte equivalent and is still the default.
        self.online_prefix_edges = online_prefix_edges or flat_prefix_edges
        self.flat_prefix_edges = flat_prefix_edges
        # Lexical nodes of a category built by a grammar LHS can later acquire
        # nonlexical derivations; they must NEVER be rejected on lexical evidence.
        self._pure_lexical_categories = frozenset(
            intern(symbol.category)
            for rule in grammar for symbol in rule.rhs
            if symbol.category not in {r.lhs.category for r in grammar}
        )
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
        self.prefix_ids: tuple[tuple[int, ...], ...] = ()
        if self.online_prefix_edges:
            # Compile all consumed-symbol signatures ONCE per grammar, not
            # once per partial state. Keep variant-specific rule indices.
            names: dict[tuple[str, ...], int] = {}
            prefixes: list[tuple[int, ...]] = []
            for item in self.rules:
                consumed: tuple[str, ...] = ()
                per_rule: list[int] = []
                for dot in range(len(item.rule.rhs) + 1):
                    if dot:
                        symbol = item.rule.rhs[dot - 1]
                        consumed += (json.dumps(symbol.as_dict(),sort_keys=True,
                                               separators=(",",":"),ensure_ascii=False),)
                    idx = names.get(consumed)
                    if idx is None:
                        idx = len(names)
                        names[consumed] = idx
                    per_rule.append(idx)
                prefixes.append(tuple(per_rule))
            self.prefix_ids = tuple(prefixes)

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
        diagnostic_k: int | None = None,
        witness_cache: Any | None = None,
        kbest_work_limit: int | None = None,
    ) -> ParseResult:
        recognition_start = perf_counter()
        forest = _VectorForest(self, lattice, max_items=max_items)
        root_nodes = forest.recognize(goal_category)
        recognition_ms = (perf_counter() - recognition_start) * 1000

        length = len(lattice.text)
        # Normal parsing deliberately materializes only a small k-best view
        # of the complete packed forest.  Audits need a wider view to tell a
        # missing derivation from a ranking error; recognition remains the
        # same symbolic exhaustive algorithm in both modes.
        requested_k = (
            max(1, diagnostic_k)
            if diagnostic_k is not None
            else min(beam, 2 if length > 160 else 4 if length > 80 else 8)
        )
        materializer = _LazyMaterializer(self, forest, work_limit=kbest_work_limit)
        if witness_cache is not None:
            witness_cache.bind(self, forest, lattice)
            materializer.witness_cache = witness_cache
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
            "semantic_graphs": 0,
            "semantic_operations": 0,
            "lexical_candidates": len(lattice.candidates),
            "recognition_ms": round(recognition_ms, 4),
            "best_ms": 0.0,
            "kbest_ms": 0.0,
            "lexical_spans": forest.lexical_spans,
            "early_lexical_filter": self.early_lexical_filter,
            "early_lexical_pruned": forest.early_lexical_pruned,
            "early_lexical_considered": forest.early_lexical_considered,
            "category_bits": len(self._bits),
            "forest_nodes": len(forest.nodes),
            "structural_derivations": forest.derivation_count,
            "partial_states": len(forest.partials),
            "partial_derivations": forest.partial_derivation_count,
            "online_prefix_edges_enabled": self.online_prefix_edges,
            "online_prefix_flat_enabled": self.flat_prefix_edges,
            **(forest.prefix_store.diagnostics() if forest.prefix_store is not None else
               {"online_prefix_groups":0,"online_prefix_unique_edges":0,
                "online_prefix_shared_edge_hits":0,"online_prefix_member_count":0,
                "online_prefix_array_bytes":0}),
            "partial_proposals": forest.partial_proposals,
            "duplicate_partial_proposals": forest.duplicate_partial_proposals,
            "duplicate_transitions_avoided": forest.duplicate_transitions_avoided,
            "boundary_cache_hits": forest.boundary_cache_hits,
            "boundary_cache_misses": forest.boundary_cache_misses,
            "recognition_operations": forest.operations,
            "unification_attempts": 0,
            "unification_rejections": 0,
            "hint_unification_attempts": 0,
            "hint_unification_rejections": 0,
            "hint_compatibility_cache_hits": 0,
            "unification_cache_hits": 0,
            "constraint_context_cache_hits": 0,
            "failed_continuation_cache_hits": 0,
            "projected_bindings": 0,
            "projected_context_cache_hits": 0,
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
        try:
            root_provider.ensure(1, charge_kbest=False)
        except KBestWorkBudgetExceeded:
            # There may be a derivation somewhere in the packed forest, but
            # no optimal grammatical witness was certified within budget.
            # Never expose a partial or unranked candidate as success.
            stats["kbest_budget_exceeded"] = True
            stats["kbest_work_units"] = materializer.work_units
            stats["kbest_work_limit"] = kbest_work_limit
            stats["best_ms"] = round((perf_counter() - best_start) * 1000, 4)
            root_provider.refresh_stats()
            return ParseResult(
                text=lattice.text, lattice=lattice, packed=packed,
                roots=(), completed=False, stats=stats,
                shared_forest=forest,
            )
        stats["kbest_budget_exceeded"] = False
        stats["kbest_work_units"] = materializer.work_units
        stats["kbest_work_limit"] = kbest_work_limit
        stats["best_ms"] = round((perf_counter() - best_start) * 1000, 4)
        stats["nodes_visited_for_best"] = materializer.nodes_initialized
        stats["combinations_visited_for_best"] = materializer.combinations_visited
        root_provider.refresh_stats()
        if witness_cache is not None:
            stats["prepacked_witnesses"] = witness_cache.summary()
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
        self.partial_proposals = 0
        self.duplicate_partial_proposals = 0
        self.duplicate_transitions_avoided = 0
        self.lexical_spans = 0
        self.budget_exceeded = False
        self.early_lexical_considered = 0
        self.early_lexical_pruned = 0
        self.boundary_cache_hits = 0
        self.boundary_cache_misses = 0
        self._next_start_cache: dict[int, int] = {}
        self.prefix_store = (
            (FlatOnlinePrefixEdges if compiled.flat_prefix_edges else
             OnlinePrefixEdges)(compiled.prefix_ids, PartialDerivation)
            if compiled.online_prefix_edges else None
        )
        if compiled.cache_boundaries:
            # Assign a cached implementation once, avoiding an extra branch
            # at each hot-path call in the *uncached* reference parser.
            self._next_start = self._next_start_cached

    def _lexical_first_slot_possible(self, node: ForestNode, rule_index: int, dot: int) -> bool:
        """Sound *necessary* test for a pure lexical symbol.

        No child bindings are assumed. Disjunctive/unbound feature values
        remain possible. If any candidate might unify, keep the transition.
        Grammar-derived or interface-backed nodes are never pruned here.
        """
        if not self.compiled.early_lexical_filter:
            return True
        if node.category_id not in self.compiled._pure_lexical_categories:
            return True
        if any(not isinstance(d, LexicalDerivation) for d in node.derivations):
            return True
        rule = self.compiled.rules[rule_index].rule
        if dot >= len(rule.rhs):
            return True
        symbol = rule.rhs[dot]
        self.early_lexical_considered += 1
        required = set(_required_feature_ids(symbol.requires))
        for derivation in node.derivations:
            for candidate in derivation.candidates:
                if candidate.interface is not None:
                    return True
                if not required.issubset(_feature_evidence(candidate.features)):
                    continue
                if unify(symbol.features, candidate.features) is not None:
                    return True
        self.early_lexical_pruned += 1
        return False

    def _next_start(self, end: int) -> int:
        separators = (' \t\r\n' if self.compiled.preserve_quote_delimiters
                      else ' \t\r\n"\u201c\u201d\u2018\u2019')
        while end < len(self.text) and self.text[end] in separators:
            end += 1
        return end

    def _next_start_cached(self, end: int) -> int:
        # Cache is forest-local: quotes and separators follow the compiled
        # grammar's mode, so no value can leak between different sentences.
        previous = self._next_start_cache.get(end)
        if previous is not None:
            self.boundary_cache_hits += 1
            return previous
        result = _VectorForest._next_start(self, end)
        self._next_start_cache[end] = result
        self.boundary_cache_misses += 1
        return result

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
            # Partials already waiting when the node appears have not seen
            # it.  Later entries necessarily advance eagerly over this
            # visible node, so only this prefix must run on the agenda turn.
            waiting_cutoff = len(self.waiting.get((start, category_id), ()))
            node = ForestNode(
                len(self.nodes), start, end, category_id, category, mask,
                waiting_cutoff=waiting_cutoff,
            )
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
        self.partial_proposals += 1
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
            if self.prefix_store is not None:
                partial.derivations = self.prefix_store.register(partial)
                partial.seen = None
            self.operations += 1
        if self.prefix_store is None:
            signature = (previous_id, child_id)
            if signature not in partial.seen:
                partial.seen.add(signature)
                partial.derivations.append(PartialDerivation(previous_id, child_id))
                self.partial_derivation_count += 1
            else:
                self.duplicate_partial_proposals += 1
        elif partial.derivations.append(previous_id, child_id):
            self.partial_derivation_count += 1
        else:
            self.duplicate_partial_proposals += 1
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
        if (partial.dot < len(rule.rhs_masks) and node.mask & rule.rhs_masks[partial.dot]
                and self._lexical_first_slot_possible(node, partial.rule_index, partial.dot)):
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
                if (node.mask & rule.rhs_masks[0]
                        and self._lexical_first_slot_possible(node, rule_index, 0)):
                    self._add_partial(rule_index, 1, node.start, node.end, None, node.node_id)
            waiting = self.waiting.get((node.start, node.category_id), ())
            self.duplicate_transitions_avoided += len(waiting) - node.waiting_cutoff
            for partial_id in tuple(waiting[:node.waiting_cutoff]):
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
    required_features: tuple[int, ...] = ()
    initialized: bool = False
    initializing: bool = False
    exhausted: bool = False
    results: list[CompactAnalysis] = field(default_factory=list)
    heap: list[tuple[float, int, str, Any]] = field(default_factory=list)
    pushed_rules: set[tuple[int, int, tuple[int, ...]]] = field(default_factory=set)
    scheduled_rules: set[tuple[int, int, tuple[int, ...]]] = field(default_factory=set)
    failed_continuations: set[Hashable] = field(default_factory=set)
    seen_results: set[Hashable] = field(default_factory=set)


class KBestWorkBudgetExceeded(RuntimeError):
    """A full best-tree proof was not obtained within a measured work budget."""


class _LazyMaterializer:
    """Demand-driven k-best extraction with feature-aware failure recovery."""

    # A non-positive cycle contribution is required by the lazy k-best
    # search.  Productive ordinary rules carry score 2.0 and are therefore
    # depth-neutral; marked category conversions stay below this baseline.
    # This prevents both unlimited profitable cycles and a blanket preference
    # for shallower, grammatically incoherent trees.
    RULE_COST = 2.0

    def __init__(self, compiled: VectorGrammar, forest: _VectorForest,
                 *, work_limit: int | None = None) -> None:
        if work_limit is not None and work_limit < 1:
            raise ValueError("k-best work limit must be positive")
        self.work_limit = work_limit
        self.work_units = 0
        self.compiled = compiled
        self.forest = forest
        self.witness_cache: Any | None = None
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
        self.unification_rejections = 0
        self.hint_unification_attempts = 0
        self.hint_unification_rejections = 0
        self.unification_cache_hits = 0
        self.hint_compatibility_cache_hits = 0
        self.context_cache_hits = 0
        self.failed_continuation_cache_hits = 0
        self.projected_bindings = 0
        self.projected_context_cache_hits = 0
        self.nodes_initialized = 0
        self.combinations_visited = 0
        self._node_hints: dict[int, float] = {}
        self._partial_hints: dict[int, float] = {}
        self._constrained_node_hints: dict[
            tuple[int, Hashable, tuple[int, ...]], float
        ] = {}
        self._constrained_partial_hints: dict[int, float] = {}
        self._hint_nodes_active: set[int] = set()
        self._hint_partials_active: set[int] = set()
        self._active_contexts: set[tuple[int, Hashable]] = set()
        # Bound computation asks the same static grammar constraint about
        # the same lexical/rule interface many times.  These objects remain
        # alive with this materializer, so their identities form a safe,
        # allocation-free key.  Cache only the boolean answer: contextual
        # unification and its bindings still happen on the real path.
        self._hint_compatibility: dict[tuple[int, int], bool] = {}

    def _charge(self) -> None:
        """Bound ranking effort without a wall-clock timeout or silent beam."""
        self.work_units += 1
        if self.work_limit is not None and self.work_units > self.work_limit:
            raise KBestWorkBudgetExceeded(
                f"k-best work budget {self.work_limit} exhausted")

    def _hint_compatible(
        self,
        constraint: FeatureStructure,
        features: FeatureStructure,
    ) -> bool:
        key = (id(constraint), id(features))
        cached = self._hint_compatibility.get(key)
        if cached is not None:
            self.hint_compatibility_cache_hits += 1
            return cached
        compatible = unify(constraint, features) is not None
        self._hint_compatibility[key] = compatible
        return compatible

    def get(
        self,
        node_id: int,
        rank: int,
        constraint: FeatureStructure | None = None,
        bindings: Bindings | None = None,
        required_features: Sequence[str | int] = (),
    ) -> CompactAnalysis | None:
        required = constraint if constraint is not None else FeatureStructure.empty()
        required_ids = _required_feature_ids(required_features)
        inherited = dict(bindings or {})
        projected, relevant_names = _project_bindings(required, inherited)
        self.projected_bindings += len(inherited) - len(projected)
        context_key = _context_key(required, projected, required_ids)
        if len(projected) != len(inherited) and (node_id, context_key) in self.node_states:
            self.projected_context_cache_hits += 1
        active_key = (node_id, context_key)
        # Only the exact same constrained subproblem is cyclic.  The same
        # span/category may legitimately reappear after a unary rule changes
        # its feature context.
        if active_key in self._active_contexts:
            return None
        self._active_contexts.add(active_key)
        try:
            analysis = self._get_contextual(
                node_id, rank, required, projected, required_ids, context_key,
            )
            if analysis is None or len(projected) == len(inherited):
                return analysis
            # The cached child calculation is independent of unrelated
            # bindings, but its caller must retain them for later siblings.
            merged_bindings = dict(analysis.bindings)
            for name, value in inherited.items():
                if name not in relevant_names:
                    merged_bindings[name] = value
            return replace(analysis, bindings=merged_bindings)
        finally:
            self._active_contexts.remove(active_key)

    def _get_contextual(
        self,
        node_id: int,
        rank: int,
        required: FeatureStructure,
        inherited: Bindings,
        required_ids: tuple[int, ...],
        context_key: Hashable,
    ) -> CompactAnalysis | None:
        cache_key = (node_id, context_key)
        state = self.node_states.get(cache_key)
        if state is None:
            state = _NodeState(required, inherited, required_ids)
            self.node_states[cache_key] = state
        else:
            self.context_cache_hits += 1
        if state.initializing:
            return None
        if not state.initialized and self.witness_cache is not None:
            shortcut = self.witness_cache.take(node_id, state, self)
            if shortcut is not None:
                # Certified unique constituent: no other analysis of this
                # chart node is hidden by the fast path. All other nodes
                # still follow the canonical lazy materializer.
                state.results.append(shortcut)
                state.initialized = True
                state.exhausted = True
                self.analysis_count += 1
                self.nodes_initialized += 1
        if not state.initialized:
            self._initialize_node(node_id, state)
        while len(state.results) <= rank and state.heap:
            self._charge()
            negative_bound, _, kind, payload = heappop(state.heap)
            if kind == "lexical":
                candidate, merged, env = payload
                signature = ("lexical", id(candidate))
                if signature in state.seen_results:
                    continue
                state.seen_results.add(signature)
                analysis = CompactAnalysis(
                    next(self._analysis_ids), node_id, merged,
                    candidate.score, env, _feature_evidence(candidate.features), candidate=candidate,
                )
            elif kind == "interface":
                candidate, interface_rank, interface_item, merged, env = payload
                signature = ("interface", id(candidate), interface_rank)
                if signature in state.seen_results:
                    continue
                state.seen_results.add(signature)
                interface = candidate.interface
                assert isinstance(interface, SegmentInterface)
                following = interface.get(interface_rank + 1)
                if following is not None:
                    self.unification_attempts += 1
                    following_result = unify(state.constraint, following.features, state.bindings)
                    if following_result is not None:
                        following_features, following_env = following_result
                        heappush(state.heap, (
                            -following.score, next(self._serial), "interface",
                            (candidate, interface_rank + 1, following, following_features, following_env),
                        ))
                    else:
                        self.unification_rejections += 1
                analysis = CompactAnalysis(
                    next(self._analysis_ids), node_id, merged,
                    interface_item.score, env, _feature_evidence(interface_item.features), candidate=candidate,
                    interface_item=interface_item,
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
                    env, _rule_evidence(rule, combo),
                    rule_index=derivation.rule_index, children=uses,
                )
            if not set(state.required_features).issubset(analysis.evidence):
                continue
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
            self._charge()
            if isinstance(derivation, LexicalDerivation):
                for candidate in derivation.candidates:
                    if isinstance(candidate.interface, SegmentInterface):
                        interface_item = candidate.interface.get(0)
                        if interface_item is None:
                            continue
                        if not set(state.required_features).issubset(
                            _feature_evidence(interface_item.features)
                        ):
                            continue
                        self.unification_attempts += 1
                        result = unify(state.constraint, interface_item.features, state.bindings)
                        if result is None:
                            self.unification_rejections += 1
                            continue
                        merged, env = result
                        heappush(state.heap, (
                            -interface_item.score, next(self._serial), "interface",
                            (candidate, 0, interface_item, merged, env),
                        ))
                        continue
                    self.unification_attempts += 1
                    result = unify(state.constraint, candidate.features, state.bindings)
                    if result is None:
                        self.unification_rejections += 1
                        continue
                    merged, env = result
                    heappush(state.heap, (
                        -candidate.score, next(self._serial), "lexical", (candidate, merged, env),
                    ))
            else:
                rule = self.compiled.rules[derivation.rule_index].rule
                # A positive-evidence requirement is stronger than ordinary
                # open-world unification.  Do not enqueue a derivation whose
                # rule cannot possibly establish the requested evidence: an
                # ``-inf`` hint left in the heap would eventually be explored
                # and can make an impossible constrained stream enumerate a
                # combinatorial number of children before reporting failure.
                if state.required_features and not _rule_may_provide_evidence(
                    rule, set(state.required_features),
                ):
                    continue
                self.unification_attempts += 1
                if unify(state.constraint, rule.lhs.features, state.bindings) is None:
                    self.unification_rejections += 1
                    continue
                partial_bound = self._constrained_partial_hint(derivation.partial_id)
                if partial_bound == float("-inf"):
                    continue
                bound = partial_bound + rule.score - self.RULE_COST
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
        self._charge()
        combo: list[CompactAnalysis] = []
        rule = self.compiled.rules[derivation.rule_index].rule
        self.unification_attempts += 1
        lhs_result = unify(state.constraint, rule.lhs.features, state.bindings)
        if lhs_result is None:
            self.unification_rejections += 1
            return
        _lhs_merged, env = lhs_result
        for index, (child_id, rank) in enumerate(zip(path, ranks)):
            child_constraint = rule.rhs[index].features
            child = self.get(
                child_id, rank, child_constraint, env,
                required_features=rule.rhs[index].requires,
            )
            if child is None:
                child_bindings, _ = _project_bindings(child_constraint, env)
                child_required_ids = _required_feature_ids(
                    rule.rhs[index].requires
                )
                child_context = _context_key(
                    child_constraint, child_bindings, child_required_ids,
                )
                child_state = self.node_states.get((child_id, child_context))
                failure_key = (
                    derivation.rule_index, index, child_id,
                    _feature_key(child_constraint), _bindings_key(child_bindings),
                    child_required_ids,
                )
                # Only memoize a genuinely exhausted constrained stream.  A
                # transient exact-context cycle also returns None, but may
                # become productive after its active caller unwinds.
                if child_state is not None and child_state.exhausted:
                    if failure_key in state.failed_continuations:
                        self.failed_continuation_cache_hits += 1
                        return
                    state.failed_continuations.add(failure_key)
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
                self._constrained_node_hint(
                    child_id, symbol.features, symbol.requires,
                )
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
            self._charge()
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
        symbol = rule.rhs[partial.dot - 1]
        child_bound = self._constrained_node_hint(
            derivation.child_id, symbol.features, symbol.requires,
        )
        if child_bound == float("-inf"):
            return
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
            self._charge()
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
        required_features: Sequence[str | int] = (),
    ) -> float:
        required_ids = _required_feature_ids(required_features)
        required_set = set(required_ids)
        key = (node_id, _feature_key(constraint), required_ids)
        cached = self._constrained_node_hints.get(key)
        if cached is not None:
            return cached
        if node_id in self._hint_nodes_active:
            return float("-inf")
        self._hint_nodes_active.add(node_id)
        best = float("-inf")
        for derivation in self.forest.nodes[node_id].derivations:
            self._charge()
            if isinstance(derivation, LexicalDerivation):
                for candidate in derivation.candidates:
                    if (
                        not isinstance(candidate.interface, SegmentInterface)
                        and not required_set.issubset(
                            _feature_evidence(candidate.features)
                        )
                    ):
                        continue
                    self.hint_unification_attempts += 1
                    if self._hint_compatible(constraint, candidate.features):
                        best = max(best, candidate.score)
                    else:
                        self.hint_unification_rejections += 1
            else:
                rule = self.compiled.rules[derivation.rule_index].rule
                if required_set and not _rule_may_provide_evidence(
                    rule, required_set,
                ):
                    continue
                self.hint_unification_attempts += 1
                if not self._hint_compatible(constraint, rule.lhs.features):
                    self.hint_unification_rejections += 1
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
            child = self._constrained_node_hint(
                derivation.child_id, symbol.features, symbol.requires,
            )
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
        if analysis.interface_item is not None:
            source = analysis.interface_item
            item = ChartItem(
                node.start, node.end, node.category, features,
                None, analysis.score,
                Provenance("segment-interface", {
                    "children": (source.provenance,),
                    "local_rule_id": source.rule_id,
                }),
                children=(source,),
                rule_id="segment_interface",
                bindings=bindings,
                syntax=source.syntax,
                _sig=analysis.analysis_id,
            )
            self.item_cache[cache_key] = item
            return item
        if analysis.candidate is not None:
            candidate = analysis.candidate
            item = ChartItem(
                node.start, node.end, node.category, features,
                None, analysis.score,
                Provenance(candidate.source, {
                    "surface": candidate.surface,
                    "lemma": candidate.lemma,
                    "sense_id": candidate.sense_id,
                }),
                bindings=bindings,
                syntax=_lexical_syntax(candidate),
                lexical_candidate=candidate,
                _sig=analysis.analysis_id,
            )
            self.item_cache[cache_key] = item
            return item

        assert analysis.rule_index is not None
        rule = self.compiled.rules[analysis.rule_index].rule
        children = tuple(self._item_for_use(use) for use in analysis.children)
        syntax = _compose_syntax(rule, children)
        item = ChartItem(
            node.start, node.end, node.category, features, None, analysis.score,
            Provenance("rule", {
                "rule_id": rule.rule_id,
                "children": tuple(child.provenance for child in children),
            }),
            children=children,
            rule_id=rule.rule_id,
            bindings=bindings,
            syntax=syntax,
            _sig=analysis.analysis_id,
        )
        self.item_cache[cache_key] = item
        return item

def _shift_chart_item(item: ChartItem, offset: int) -> ChartItem:
    """Translate a local clause tree to source offsets without semantics."""
    if offset == 0:
        return item
    memo: dict[int, ChartItem] = {}

    def shift_anchor(anchor: str) -> str:
        if not anchor.startswith("lex:"):
            return anchor
        fields = anchor.split(":", 4)
        if len(fields) != 5:
            return anchor
        try:
            start = int(fields[1]) + offset
            end = int(fields[2]) + offset
        except ValueError:
            return anchor
        return f"lex:{start}:{end}:{fields[3]}:{fields[4]}"

    def shift(current: ChartItem) -> ChartItem:
        cached = memo.get(id(current))
        if cached is not None:
            return cached
        children = tuple(shift(child) for child in current.children)
        syntax = SyntacticPackage(
            {name: shift_anchor(anchor) for name, anchor in current.syntax.anchors.items()},
            tuple(
                SyntacticLink(link.relation, shift_anchor(link.target), link.child_index)
                for link in current.syntax.links
            ),
        )
        candidate = current.lexical_candidate
        if candidate is not None:
            candidate = replace(
                candidate,
                span_start=candidate.span_start + offset,
                span_end=candidate.span_end + offset,
            )
        shifted = ChartItem(
            current.start + offset,
            current.end + offset,
            current.category,
            current.features,
            None,
            current.score,
            current.provenance,
            children=children,
            rule_id=current.rule_id,
            bindings=dict(current.bindings),
            syntax=syntax,
            lexical_candidate=candidate,
            _sig=("shift", offset, current.signature()),
        )
        memo[id(current)] = shifted
        return shifted

    return shift(item)


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
        self.stat_offsets: dict[str, int] = {}
        self.next_rank: dict[int, int] = {}
        self.pending_nodes: set[int] = set()
        self.yielded_nodes: set[int] = set()

    def _initialize(self) -> None:
        if self.initialized:
            return
        self.initialized = True
        for node in self.root_nodes:
            analysis = self.materializer.get(node.node_id, 0)
            if analysis is not None:
                heappush(self.heap, (-analysis.score, next(self._serial), 0, analysis))
                self.pending_nodes.add(node.node_id)
                self.next_rank[node.node_id] = 1

    def _schedule_following(self, node_id: int) -> None:
        if node_id in self.pending_nodes:
            return
        rank = self.next_rank.get(node_id, 0)
        following = self.materializer.get(node_id, rank)
        self.next_rank[node_id] = rank + 1
        if following is not None:
            heappush(self.heap, (-following.score, next(self._serial), rank, following))
            self.pending_nodes.add(node_id)

    def ensure(self, amount: int, *, charge_kbest: bool = True) -> None:
        start = perf_counter()
        self._initialize()
        if len(self.items) < amount:
            for node_id in tuple(self.yielded_nodes):
                self._schedule_following(node_id)
        while len(self.items) < amount and self.heap:
            _, _, rank, analysis = heappop(self.heap)
            self.pending_nodes.discard(analysis.node_id)
            self.yielded_nodes.add(analysis.node_id)
            item = self.materializer.item(analysis)
            self.items.append(item)
            self.pack(item)
            if len(self.items) < amount:
                self._schedule_following(analysis.node_id)
        if charge_kbest:
            self.stats["kbest_ms"] = round(
                float(self.stats["kbest_ms"]) + (perf_counter() - start) * 1000,
                4,
            )
        self.refresh_stats()

    def refresh_stats(self) -> None:
        materializer = self.materializer
        offset = self.stat_offsets
        self.stats["unification_attempts"] = materializer.unification_attempts + offset.get("unification_attempts", 0)
        self.stats["unification_rejections"] = materializer.unification_rejections + offset.get("unification_rejections", 0)
        self.stats["hint_unification_attempts"] = materializer.hint_unification_attempts + offset.get("hint_unification_attempts", 0)
        self.stats["hint_unification_rejections"] = materializer.hint_unification_rejections + offset.get("hint_unification_rejections", 0)
        self.stats["hint_compatibility_cache_hits"] = materializer.hint_compatibility_cache_hits + offset.get("hint_compatibility_cache_hits", 0)
        self.stats["unification_cache_hits"] = materializer.unification_cache_hits
        self.stats["constraint_context_cache_hits"] = materializer.context_cache_hits
        self.stats["failed_continuation_cache_hits"] = materializer.failed_continuation_cache_hits + offset.get("failed_continuation_cache_hits", 0)
        self.stats["projected_bindings"] = materializer.projected_bindings + offset.get("projected_bindings", 0)
        self.stats["projected_context_cache_hits"] = materializer.projected_context_cache_hits + offset.get("projected_context_cache_hits", 0)
        self.stats["compact_analyses"] = materializer.analysis_count
        self.stats["materialized_items"] = len(materializer.item_cache)
        self.stats["nodes_visited_total"] = materializer.nodes_initialized + offset.get("nodes_visited_total", 0)
        self.stats["combinations_visited_total"] = materializer.combinations_visited + offset.get("combinations_visited_total", 0)
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
