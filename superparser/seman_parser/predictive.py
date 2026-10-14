"""Experimental statistically ordered left-corner shift/reduce parser.

The production parser intentionally does not import this module.  The grammar
remains the authority: the transition model only changes the order in which
legal SHIFT and REDUCE actions are attempted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Mapping, Sequence

from .chart import ChartItem, Provenance, _compose_syntax, _lexical_syntax
from .engine import ParserResources
from .features import Atom, FeatureStructure, Variable, substitute_structure, unify
from .grammar import Grammar, GrammarRule
from .segmentation import LexicalCandidate, LexicalLattice, build_lattice
from .symbols import intern


def _feature_key(features: FeatureStructure) -> tuple[tuple[int, object], ...]:
    def value_key(value: object) -> object:
        if isinstance(value, Atom):
            return ("a", value.symbol)
        if isinstance(value, Variable):
            return ("v", value.name)
        if isinstance(value, FeatureStructure):
            return ("f", _feature_key(value))
        options = getattr(value, "options", None)
        if options is not None:
            return ("o", tuple(value_key(option) for option in options))
        return (type(value).__name__, repr(value))

    return tuple(sorted((name, value_key(value)) for name, value in features.items()))


@dataclass(frozen=True, slots=True)
class CompiledReduction:
    index: int
    rule: GrammarRule
    rhs_ids: tuple[int, ...]
    lhs_id: int


@dataclass(frozen=True, slots=True)
class AutomatonReport:
    rules: int
    categories: int
    lr0_states: int
    lr0_items: int
    lr0_transitions: int
    lr0_shift_reduce_pairs: int
    lr0_reduce_reduce_pairs: int
    lr0_conflict_states: int
    left_recursive_rules: int
    unary_rules: int
    compiled_bytes_estimate: int
    compile_ms: float

    def as_dict(self) -> dict[str, int | float]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


class PredictiveGrammar:
    """Compact indexes used by the runtime; no rule scan occurs per token."""

    def __init__(self, grammar: Grammar, *, measure_lr0: bool = False) -> None:
        started = perf_counter()
        self.grammar = grammar
        reductions: list[CompiledReduction] = []
        exact: dict[tuple[int, ...], list[int]] = defaultdict(list)
        arities_by_last: dict[int, set[int]] = defaultdict(set)
        lhs_ids = {rule.lhs.category_id for rule in grammar}
        categories: set[int] = set(lhs_ids)
        for rule in grammar:
            if not rule.rhs:
                continue
            rhs = tuple(symbol.category_id for symbol in rule.rhs)
            compiled = CompiledReduction(len(reductions), rule, rhs, rule.lhs.category_id)
            reductions.append(compiled)
            exact[rhs].append(compiled.index)
            arities_by_last[rhs[-1]].add(len(rhs))
            categories.update(rhs)
        self.reductions = tuple(reductions)
        self.exact = {key: tuple(value) for key, value in exact.items()}
        first_rules: dict[int, list[CompiledReduction]] = defaultdict(list)
        for reduction in reductions:
            first_rules[reduction.rhs_ids[0]].append(reduction)
        self.first_rules = {key: tuple(value) for key, value in first_rules.items()}
        prefix_items: dict[tuple[int, ...], list[tuple[str, str, str]]] = defaultdict(list)
        for reduction in reductions:
            rhs = reduction.rhs_ids
            for dot in range(1, len(rhs) + 1):
                expected = reduction.rule.rhs[dot].category if dot < len(rhs) else "$REDUCE"
                prefix_items[rhs[:dot]].append((
                    f"{reduction.rule.rule_id}:{dot}",
                    reduction.rule.lhs.category,
                    expected,
                ))
        self.prefix_items = {key: tuple(value) for key, value in prefix_items.items()}
        self.arities_by_last = {
            key: tuple(sorted(value)) for key, value in arities_by_last.items()
        }
        self.goal_ancestors = self._goal_ancestors("CLAUSE")
        self.nullable, self.first, self.follow = self._first_follow("CLAUSE")
        self.follow_lexical = {
            category: frozenset(
                terminal
                for follower in followers if follower is not None
                for terminal in self.first.get(follower, (follower,))
            )
            for category, followers in self.follow.items()
        }
        self.follow_end = frozenset(
            category for category, followers in self.follow.items()
            if None in followers
        )
        extension_first: dict[int, set[int]] = defaultdict(set)
        for row in reductions:
            if len(row.rhs_ids) < 2:
                continue
            base = row.rhs_ids[0]
            # Only true left extensions (NP -> NP PP, VP -> VP ADV, ...)
            # represent an already recognized constituent remaining open.
            if row.lhs_id != base:
                continue
            for category in row.rhs_ids[1:]:
                extension_first[base].update(self.first.get(category, (category,)))
                if category not in self.nullable:
                    break
        self.extension_first = {
            key: frozenset(value) for key, value in extension_first.items()
        }
        lr = _lr0_metrics(grammar) if measure_lr0 else (0, 0, 0, 0, 0, 0)
        # Tuples contain Python integers/references; this estimate is explicit
        # and reproducible, not a claim about allocator/RSS precision.
        compiled_bytes = sum(64 + 8 * len(row.rhs_ids) for row in reductions)
        compiled_bytes += sum(72 + 8 * (len(key) + len(value)) for key, value in self.exact.items())
        self.report = AutomatonReport(
            rules=len(grammar), categories=len(categories),
            lr0_states=lr[0], lr0_items=lr[1], lr0_transitions=lr[2],
            lr0_shift_reduce_pairs=lr[3], lr0_reduce_reduce_pairs=lr[4],
            lr0_conflict_states=lr[5],
            left_recursive_rules=sum(
                bool(rule.rhs) and rule.rhs[0].category_id == rule.lhs.category_id
                for rule in grammar
            ),
            unary_rules=sum(rule.arity == 1 for rule in grammar),
            compiled_bytes_estimate=compiled_bytes,
            compile_ms=round((perf_counter() - started) * 1000, 4),
        )

    def _goal_ancestors(self, goal: str) -> frozenset[int]:
        useful = {intern(goal)}
        changed = True
        while changed:
            changed = False
            for row in self.reductions:
                if row.lhs_id in useful:
                    for category in row.rhs_ids:
                        if category not in useful:
                            useful.add(category)
                            changed = True
        return frozenset(useful)

    def _first_follow(
        self, goal: str,
    ) -> tuple[frozenset[int], dict[int, frozenset[int]], dict[int, frozenset[int | None]]]:
        """Category-level nullable/FIRST/FOLLOW sets compiled once.

        Lexical categories are symbols that never occur as a rule LHS.  The
        current grammar has no epsilon production, but the fixed point keeps
        this correct if one is added experimentally.
        """
        nonterminals = {row.lhs_id for row in self.reductions}
        all_categories = nonterminals | {
            category for row in self.reductions for category in row.rhs_ids
        }
        nullable: set[int] = set()
        changed = True
        while changed:
            changed = False
            for row in self.reductions:
                if not row.rhs_ids or all(category in nullable for category in row.rhs_ids):
                    if row.lhs_id not in nullable:
                        nullable.add(row.lhs_id)
                        changed = True
        # Categories may be both lexical and derived in this grammar (for
        # example N has productive conversion rules).  Seed every symbol
        # with itself, then add derivational left corners.
        first: dict[int, set[int]] = {
            category: {category} for category in all_categories
        }
        changed = True
        while changed:
            changed = False
            for row in self.reductions:
                target = first[row.lhs_id]
                before = len(target)
                for category in row.rhs_ids:
                    target.update(first[category])
                    if category not in nullable:
                        break
                changed |= len(target) != before
        follow: dict[int, set[int | None]] = {category: set() for category in nonterminals}
        follow.setdefault(intern(goal), set()).add(None)
        changed = True
        while changed:
            changed = False
            for row in self.reductions:
                trailer = set(follow[row.lhs_id])
                for category in reversed(row.rhs_ids):
                    if category in nonterminals:
                        before = len(follow[category])
                        follow[category].update(trailer)
                        changed |= len(follow[category]) != before
                        if category in nullable:
                            trailer.update(first[category])
                        else:
                            trailer = set(first[category])
                    else:
                        trailer = {category}
        return (
            frozenset(nullable),
            {key: frozenset(value) for key, value in first.items()},
            {key: frozenset(value) for key, value in follow.items()},
        )

    def reduction_viable(
        self, lhs_id: int, lookahead_ids: frozenset[int], *, at_end: bool,
    ) -> bool:
        if at_end:
            return lhs_id in self.follow_end
        followers = self.follow_lexical.get(lhs_id)
        # Unknown/no FOLLOW information is not proof of impossibility.
        return not followers or not lookahead_ids or not followers.isdisjoint(lookahead_ids)

    def reductions_for(self, category_ids: tuple[int, ...]) -> Iterable[CompiledReduction]:
        if not category_ids:
            return ()
        rows: list[CompiledReduction] = []
        for arity in self.arities_by_last.get(category_ids[-1], ()):
            if arity <= len(category_ids):
                for index in self.exact.get(category_ids[-arity:], ()):
                    row = self.reductions[index]
                    if row.lhs_id in self.goal_ancestors:
                        rows.append(row)
        return rows

    def active_items(self, category_ids: Sequence[int]) -> tuple[tuple[str, str, str], ...]:
        rows: list[tuple[str, str, str]] = []
        maximum = min(len(category_ids), max((len(key) for key in self.prefix_items), default=0))
        for width in range(maximum, 0, -1):
            matches = self.prefix_items.get(tuple(category_ids[-width:]))
            if matches:
                rows.extend(matches)
        return tuple(rows)


def _lr0_metrics(grammar: Grammar) -> tuple[int, int, int, int, int, int]:
    """Build a category-only canonical LR(0) collection for feasibility."""
    productions = [("$accept", ("CLAUSE",))] + [
        (rule.lhs.category, tuple(symbol.category for symbol in rule.rhs))
        for rule in grammar
    ]
    by_lhs: dict[str, list[int]] = defaultdict(list)
    for index, (lhs, _rhs) in enumerate(productions):
        by_lhs[lhs].append(index)

    def closure(seed: Iterable[tuple[int, int]]) -> frozenset[tuple[int, int]]:
        result = set(seed)
        pending = list(result)
        while pending:
            production, dot = pending.pop()
            rhs = productions[production][1]
            if dot >= len(rhs):
                continue
            for child in by_lhs.get(rhs[dot], ()):
                item = (child, 0)
                if item not in result:
                    result.add(item)
                    pending.append(item)
        return frozenset(result)

    initial = closure(((0, 0),))
    states = [initial]
    state_ids = {initial: 0}
    cursor = 0
    transitions = 0
    while cursor < len(states):
        state = states[cursor]
        cursor += 1
        symbols = {
            productions[production][1][dot]
            for production, dot in state
            if dot < len(productions[production][1])
        }
        for symbol in symbols:
            target = closure(
                (production, dot + 1)
                for production, dot in state
                if dot < len(productions[production][1])
                and productions[production][1][dot] == symbol
            )
            transitions += 1
            if target not in state_ids:
                state_ids[target] = len(states)
                states.append(target)
    shift_reduce = reduce_reduce = conflict_states = 0
    for state in states:
        reductions = [
            production for production, dot in state
            if dot == len(productions[production][1])
        ]
        shifts = {
            productions[production][1][dot]
            for production, dot in state
            if dot < len(productions[production][1])
        }
        conflicted = False
        if reductions and shifts:
            shift_reduce += len(reductions) * len(shifts)
            conflicted = True
        if len(reductions) > 1:
            reduce_reduce += len(reductions) * (len(reductions) - 1) // 2
            conflicted = True
        conflict_states += int(conflicted)
    return (
        len(states), sum(map(len, states)), transitions,
        shift_reduce, reduce_reduce, conflict_states,
    )


class TransitionModel:
    """Interpolated counters.  Counts rank legal actions; they never license one."""

    FORMAT = "seman2-predictive-transitions-v2"

    def __init__(self, *, alpha: float = 4.0) -> None:
        self.alpha = float(alpha)
        self.levels: list[dict[str, Counter[str]]] = [defaultdict(Counter) for _ in range(4)]
        self.item_levels: list[dict[str, Counter[str]]] = [defaultdict(Counter) for _ in range(4)]
        self.metadata: dict[str, Any] = {"validated_trees": 0, "candidate_trees": 0}

    @staticmethod
    def contexts(stack: Sequence[str], lookahead: str) -> tuple[str, str, str, str]:
        top = stack[-1] if stack else "$START"
        tail = ">".join(stack[-3:]) if stack else "$START"
        return ("*", top, f"{top}|{lookahead}", f"{tail}|{lookahead}")

    def observe(
        self, stack: Sequence[str], lookahead: str, action: str,
        *, weight: float = 1.0,
    ) -> None:
        for level, context in enumerate(self.contexts(stack, lookahead)):
            self.levels[level][context][action] += weight

    def probability(self, stack: Sequence[str], lookahead: str, action: str) -> float:
        # A real prior is essential for actions absent from a small bootstrap
        # corpus.  Near-zero mass would turn "unseen" into "ungrammatical"
        # and overpower lexical/grammar evidence, contrary to the contract.
        probability = 1e-2
        action_class = action.split(":", 1)[0]
        class_probability = 0.5
        for level, context in enumerate(self.contexts(stack, lookahead)):
            counts = self.levels[level].get(context)
            if not counts:
                continue
            total = float(sum(counts.values()))
            probability = (float(counts.get(action, 0.0)) + self.alpha * probability) / (total + self.alpha)
            class_count = sum(
                value for name, value in counts.items()
                if name == action_class or name.startswith(action_class + ":")
            )
            class_probability = (class_count + self.alpha * class_probability) / (total + self.alpha)
        # The action-class backoff lets an unseen grammar rule inherit the
        # observed REDUCE/SHIFT preference without pretending that the
        # specific rule itself was seen.
        return max(probability, 0.25 * class_probability, 1e-2)

    @staticmethod
    def _item_contexts(item: tuple[str, str, str], previous: str, lookahead: str) -> tuple[str, ...]:
        item_id, parent, expected = item
        return (
            f"{previous}|{lookahead}",
            f"{parent}>{expected}",
            f"{parent}>{expected}|{lookahead}",
            f"{item_id}|{lookahead}",
        )

    def observe_items(
        self, items: Sequence[tuple[str, str, str]], previous: str,
        lookahead: str, action: str, *, weight: float,
    ) -> None:
        for item in items:
            for level, context in enumerate(self._item_contexts(item, previous, lookahead)):
                self.item_levels[level][context][action] += weight

    def contextual_probability(
        self, items: Sequence[tuple[str, str, str]], previous: str,
        lookahead: str, action: str,
    ) -> float:
        best = 0.0
        for item in items:
            probability = self.probability((previous,), lookahead, action)
            for level, context in enumerate(self._item_contexts(item, previous, lookahead)):
                counts = self.item_levels[level].get(context)
                if not counts:
                    continue
                total = float(sum(counts.values()))
                probability = (
                    float(counts.get(action, 0.0)) + self.alpha * probability
                ) / (total + self.alpha)
            best = max(best, probability)
        return max(best, self.probability((previous,), lookahead, action))

    def save(self, path: str | Path) -> None:
        payload = {
            "format": self.FORMAT,
            "alpha": self.alpha,
            "metadata": self.metadata,
            "levels": [
                {context: dict(actions) for context, actions in level.items()}
                for level in self.levels
            ],
            "item_levels": [
                {context: dict(actions) for context, actions in level.items()}
                for level in self.item_levels
            ],
        }
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "TransitionModel":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("format") not in {cls.FORMAT, "seman2-predictive-transitions-v1"}:
            raise ValueError(f"unsupported transition model: {payload.get('format')!r}")
        model = cls(alpha=float(payload["alpha"]))
        model.metadata = dict(payload.get("metadata", {}))
        for level, rows in zip(model.levels, payload["levels"]):
            for context, actions in rows.items():
                level[context].update({key: float(value) for key, value in actions.items()})
        for level, rows in zip(model.item_levels, payload.get("item_levels", ())):
            for context, actions in rows.items():
                level[context].update({key: float(value) for key, value in actions.items()})
        return model

    def observe_tree(
        self, root: ChartItem, *, validated: bool, weight: float = 1.0,
        compiled: PredictiveGrammar | None = None,
    ) -> None:
        """Learn a canonical post-order derivation from an externally qualified tree."""
        if not validated:
            self.metadata["candidate_trees"] = int(self.metadata.get("candidate_trees", 0)) + 1
            if weight <= 0:
                return
        stack: list[str] = []

        def leaves(node: ChartItem) -> list[str]:
            if node.lexical_candidate is not None:
                return [node.category]
            output: list[str] = []
            for child in node.children:
                output.extend(leaves(child))
            return output

        ordered_leaves = leaves(root)
        leaf_cursor = 0

        def visit(node: ChartItem) -> None:
            nonlocal leaf_cursor
            if node.lexical_candidate is not None:
                # All lexical readings at a position must compete in the
                # same statistical context.  Conditioning SHIFT(N) on N and
                # SHIFT(PRONOUN) on PRONOUN would make incomparable, nearly
                # tautological probabilities.
                self.observe(stack, "$LEX", f"shift:{node.category}", weight=weight)
                if compiled is not None:
                    ids = tuple(intern(category) for category in stack)
                    self.observe_items(
                        compiled.active_items(ids), stack[-1] if stack else "$START",
                        "$LEX", f"shift:{node.category}", weight=weight,
                    )
                stack.append(node.category)
                leaf_cursor += 1
                return
            for child in node.children:
                visit(child)
            lookahead = ordered_leaves[leaf_cursor] if leaf_cursor < len(ordered_leaves) else "$END"
            if node.rule_id:
                self.observe(stack, lookahead, f"reduce:{node.rule_id}", weight=weight)
                if compiled is not None:
                    ids = tuple(intern(category) for category in stack)
                    self.observe_items(
                        compiled.active_items(ids), stack[-1] if stack else "$START",
                        lookahead, f"reduce:{node.rule_id}", weight=weight,
                    )
            if node.children:
                del stack[-len(node.children):]
            stack.append(node.category)

        visit(root)
        self.observe(stack, "$END", "accept", weight=weight)
        if validated:
            self.metadata["validated_trees"] = int(self.metadata.get("validated_trees", 0)) + 1


@dataclass(frozen=True, slots=True)
class CompactNode:
    category: str
    category_id: int
    start: int
    end: int
    features: FeatureStructure
    evidence: frozenset[int]
    score: float
    candidate: LexicalCandidate | None = None
    rule: GrammarRule | None = None
    children: tuple["CompactNode", ...] = ()
    _key: tuple[Any, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_key",
            (self.category_id, self.start, self.end, _feature_key(self.features)),
        )

    def grammatical_key(self) -> tuple[Any, ...]:
        return self._key


@dataclass(frozen=True, slots=True)
class ChoiceRecord:
    state_key: tuple[Any, ...]
    selected_action: str
    alternatives: tuple[str, ...]
    position: int
    checkpoint: Any = field(default=None, repr=False, compare=False)


@dataclass(slots=True)
class _SearchState:
    position: int
    stack: tuple[CompactNode, ...]
    cost: float
    depth: int
    parent: "_SearchState | None" = None
    action: str | None = None
    choice: ChoiceRecord | None = None
    first_conflict: tuple[int, str] | None = None
    action_rank: int = 0


@dataclass(frozen=True, slots=True)
class AmbiguityPoint:
    ambiguity_id: int
    position: int
    selected_action: str
    alternatives: tuple[str, ...]


@dataclass(slots=True)
class PredictiveResult:
    text: str
    item: ChartItem | None
    completed: bool
    stats: dict[str, Any]
    ambiguities: tuple[AmbiguityPoint, ...]
    exhaustive: bool
    _choice_records: tuple[ChoiceRecord, ...] = field(default=(), repr=False)
    _lattice: LexicalLattice | None = field(default=None, repr=False)
    _shared_search: Any = field(default=None, repr=False)
    _selected_root: CompactNode | None = field(default=None, repr=False)

    def best(self) -> ChartItem | None:
        return self.item


class PredictiveParser:
    """Best-first, left-to-right parser with local resumable conflicts."""

    def __init__(
        self,
        resources: ParserResources,
        *,
        model: TransitionModel | None = None,
        goal_category: str = "CLAUSE",
        max_states: int = 50_000,
        time_budget_ms: float | None = None,
        memoization: bool = True,
        lookahead: int = 0,
        delayed_commitments: bool = False,
        contextual_statistics: bool = False,
    ) -> None:
        self.resources = resources
        self.compiled = PredictiveGrammar(resources.grammar)
        self.model = model or TransitionModel()
        self.goal_category = goal_category
        self.goal_id = intern(goal_category)
        self.max_states = max_states
        self.time_budget_ms = time_budget_ms
        self.memoization = memoization
        self.lookahead = lookahead
        self.delayed_commitments = delayed_commitments
        self.contextual_statistics = contextual_statistics
        self._rank_cache: dict[tuple[tuple[int, ...], str, str], float] = {}

    @classmethod
    def from_dir(cls, directory: str | Path, **kwargs: Any) -> "PredictiveParser":
        return cls(ParserResources.from_dir(directory), **kwargs)

    def parse(self, text: str, *, mode: str = "fast") -> PredictiveResult:
        if mode not in {"fast", "expand"}:
            raise ValueError("mode must be 'fast' or 'expand'")
        return self._parse(text.strip().strip('"\u201c\u201d\u2018\u2019').strip(), banned=None, exhaustive=mode == "expand")

    def expand(self, result: PredictiveResult, ambiguity_id: int) -> PredictiveResult:
        record = result._choice_records[ambiguity_id]
        return self._parse(
            result.text,
            banned=(record.state_key, record.selected_action),
            exhaustive=True,
            resume=record.checkpoint,
            lattice=result._lattice,
        )

    @staticmethod
    def _next_start(text: str, position: int) -> int:
        while position < len(text) and text[position] in ' \t\r\n"\u201c\u201d\u2018\u2019':
            position += 1
        return position

    @staticmethod
    def _root_span(text: str, end: int) -> bool:
        if end == len(text):
            return True
        return not text[end:].strip().strip(".!?;:,\"\u201c\u201d\u2018\u2019")

    def _state_key(self, state: _SearchState) -> tuple[Any, ...]:
        return (state.position, tuple(node.grammatical_key() for node in state.stack))

    def _lookaheads(
        self, candidates_by_start: Mapping[int, Sequence[LexicalCandidate]], position: int,
    ) -> tuple[str, ...]:
        rows = candidates_by_start.get(position, ())
        if not rows:
            return ("$END",)
        return tuple(dict.fromkeys(candidate.category for candidate in rows))

    def _action_cost(self, stack: Sequence[CompactNode], lookahead: str, action: str, intrinsic: float) -> float:
        category_ids = tuple(node.category_id for node in stack)
        cache_key = (category_ids, lookahead, action)
        probability = self._rank_cache.get(cache_key)
        if probability is None:
            categories = [node.category for node in stack]
            ordinary = self.model.probability(categories, lookahead, action)
            items = self.compiled.active_items(category_ids) if self.contextual_statistics else ()
            contextual = self.model.contextual_probability(
                items, categories[-1] if categories else "$START", lookahead, action,
            ) if items else 0.0
            probability = max(ordinary, contextual)
            self._rank_cache[cache_key] = probability
        # Intrinsic scores break sparse-model ties without overwhelming an
        # observed transition preference.  Higher intrinsic scores lower
        # this bounded penalty.
        bounded = 2.0 / (1.0 + math.exp(max(-20.0, min(20.0, intrinsic))))
        eager_reduction = 0.5 if action.startswith("reduce:") else 0.0
        return -math.log(probability) + bounded - eager_reduction

    def _parse(
        self,
        text: str,
        *,
        banned: tuple[tuple[Any, ...], str] | None,
        exhaustive: bool,
        resume: _SearchState | None = None,
        lattice: LexicalLattice | None = None,
    ) -> PredictiveResult:
        total_started = perf_counter()
        lexical_started = perf_counter()
        lattice = lattice or build_lattice(text, self.resources.lexicon, deduplicate=True)
        lexical_ms = (perf_counter() - lexical_started) * 1000
        candidates_by_start: dict[int, list[LexicalCandidate]] = defaultdict(list)
        for candidate in lattice.candidates:
            if intern(candidate.category) in self.compiled.goal_ancestors:
                candidates_by_start[candidate.span_start].append(candidate)
        for rows in candidates_by_start.values():
            rows.sort(key=lambda candidate: candidate.score, reverse=True)

        parsing_started = perf_counter()
        initial = resume or _SearchState(self._next_start(text, 0), (), 0.0, 0)
        # A LIFO agenda implements the intended contract precisely: follow
        # the locally best continuation, retaining the remaining ordered
        # actions as compact resume points.  A global probability heap made
        # incomplete short prefixes outrank longer successful derivations.
        agenda: list[_SearchState] = [initial]
        visited: dict[tuple[Any, ...], float] = {}
        states_created = 1
        configurations_visited = revisited = improved_revisits = 0
        transitions = decisions = dead_ends = feature_rejections = 0
        lookahead_rejections = 0
        shift_reduce_conflicts = reduce_reduce_conflicts = lexical_conflicts = 0
        premature_reductions = repeated_transitions = failed_config_hits = 0
        max_backtrack_depth = 0
        max_depth_seen = 0
        transition_seen: set[tuple[tuple[Any, ...], str]] = set()
        dead_configurations: set[tuple[Any, ...]] = set()
        first_conflict_visits: Counter[tuple[int, str]] = Counter()
        max_agenda = 1
        winner: _SearchState | None = None
        stopped_by = "exhausted"
        state_limit = self.max_states * (4 if exhaustive else 1)

        while agenda:
            budget_used = len(visited) if self.memoization else configurations_visited
            if budget_used >= state_limit:
                stopped_by = "state_budget"
                break
            if self.time_budget_ms is not None and not exhaustive:
                if (perf_counter() - parsing_started) * 1000 >= self.time_budget_ms:
                    stopped_by = "time_budget"
                    break
            state = agenda.pop()
            if state.first_conflict is not None:
                first_conflict_visits[state.first_conflict] += 1
            configurations_visited += 1
            if state.depth < max_depth_seen:
                max_backtrack_depth = max(max_backtrack_depth, max_depth_seen - state.depth)
            max_depth_seen = max(max_depth_seen, state.depth)
            key = self._state_key(state)
            previous = visited.get(key)
            if previous is not None:
                revisited += 1
                if previous > state.cost:
                    improved_revisits += 1
                if self.memoization and previous <= state.cost:
                    if key in dead_configurations:
                        failed_config_hits += 1
                    continue
            if self.memoization:
                visited[key] = min(state.cost, previous) if previous is not None else state.cost
            else:
                # Still retain unique-count instrumentation without pruning.
                visited.setdefault(key, state.cost)
            if (
                len(state.stack) == 1
                and state.stack[0].category_id == self.goal_id
                and state.stack[0].start == 0
                and self._root_span(text, state.stack[0].end)
            ):
                winner = state
                stopped_by = "first_complete"
                break

            position = self._next_start(text, state.position)
            lookaheads = self._lookaheads(candidates_by_start, position)
            lookahead_ids = frozenset(
                intern(candidate.category)
                for candidate in candidates_by_start.get(position, ())
            )
            at_ignorable_tail = self._root_span(text, position)
            actions: list[tuple[float, str, int, tuple[CompactNode, ...]]] = []

            # SHIFT: lexical ambiguity is filtered by reachability before an
            # object is put on the agenda.
            for candidate in candidates_by_start.get(position, ()):
                node = CompactNode(
                    candidate.category, intern(candidate.category),
                    candidate.span_start, candidate.span_end,
                    candidate.features,
                    frozenset(name for name, value in candidate.features.items() if not isinstance(value, Variable)),
                    candidate.score, candidate=candidate,
                )
                action = f"shift:{candidate.category}"
                action_cost = self._action_cost(state.stack, "$LEX", action, candidate.score)
                actions.append((action_cost, action, self._next_start(text, candidate.span_end), state.stack + (node,)))

            # REDUCE: at most one hash lookup per RHS arity ending in the top
            # stack category; no traversal of the grammar.
            categories = tuple(node.category_id for node in state.stack)
            for reduction in self.compiled.reductions_for(categories):
                if self.lookahead and not self.compiled.reduction_viable(
                    reduction.lhs_id, lookahead_ids, at_end=at_ignorable_tail,
                ):
                    lookahead_rejections += 1
                    continue
                arity = len(reduction.rhs_ids)
                children = state.stack[-arity:]
                reduced = self._reduce(reduction.rule, children)
                if reduced is None:
                    feature_rejections += 1
                    continue
                action = f"reduce:{reduction.rule.rule_id}"
                # A reduction sees the most plausible next lexical POS.
                # Taking the minimum over every
                # WordNet homograph lets a very unlikely POS select an
                # unrelated transition context.
                action_cost = self._action_cost(
                    state.stack, lookaheads[0], action, reduction.rule.score,
                )
                if self.delayed_commitments and reduction.rhs_ids:
                    open_child = reduction.rhs_ids[-1]
                    extension = self.compiled.extension_first.get(open_child, ())
                    if extension and not lookahead_ids.isdisjoint(extension):
                        # Keep the closing reduction available, but try the
                        # grammar-licensed extension of its last child first.
                        action_cost += 1.0
                actions.append((action_cost, action, position, state.stack[:-arity] + (reduced,)))

            if banned is not None and key == banned[0]:
                actions = [row for row in actions if row[1] != banned[1]]
            if not actions:
                dead_ends += 1
                dead_configurations.add(key)
                continue
            actions.sort(key=lambda row: (row[0], row[1]))
            if len(actions) > 1:
                decisions += 1
            action_names = tuple(dict.fromkeys(row[1] for row in actions))
            shift_names = tuple(name for name in action_names if name.startswith("shift:"))
            reduce_names = tuple(name for name in action_names if name.startswith("reduce:"))
            if shift_names and reduce_names:
                shift_reduce_conflicts += 1
            if len(reduce_names) > 1:
                reduce_reduce_conflicts += 1
            if len(shift_names) > 1:
                lexical_conflicts += 1
            children_to_push: list[_SearchState] = []
            for rank, (increment, action, new_position, new_stack) in enumerate(actions):
                transitions += 1
                transition_key = (key, action)
                if transition_key in transition_seen:
                    repeated_transitions += 1
                else:
                    transition_seen.add(transition_key)
                if rank and actions[0][1].startswith("reduce:"):
                    premature_reductions += 1
                choice = None
                if len(action_names) > 1:
                    choice = ChoiceRecord(
                        key, action,
                        tuple(name for name in action_names if name != action),
                        position, checkpoint=state,
                    )
                child = _SearchState(
                    new_position, new_stack, state.cost + increment + rank * 1e-9,
                    state.depth + 1, state, action, choice,
                    state.first_conflict or (
                        (position, action) if len(action_names) > 1 else None
                    ),
                    rank,
                )
                children_to_push.append(child)
                states_created += 1
            # Reverse push so the lowest-cost action is popped first.
            agenda.extend(reversed(children_to_push))
            max_agenda = max(max_agenda, len(agenda))

        parsing_ms = (perf_counter() - parsing_started) * 1000
        materialization_started = perf_counter()
        item = self._materialize(winner.stack[0]) if winner is not None else None
        materialization_ms = (perf_counter() - materialization_started) * 1000
        records: list[ChoiceRecord] = []
        cursor = winner
        while cursor is not None:
            if cursor.choice is not None:
                records.append(cursor.choice)
            cursor = cursor.parent
        records.reverse()
        ambiguities = tuple(
            AmbiguityPoint(index, record.position, record.selected_action, record.alternatives)
            for index, record in enumerate(records)
        )
        return PredictiveResult(
            text=text, item=item, completed=item is not None,
            stats={
                "engine": "predictive-left-corner-v1",
                "mode": "expand" if exhaustive else "fast",
                "stopped_by": stopped_by,
                "total_wall_ms": round((perf_counter() - total_started) * 1000, 4),
                "lexical_ms": round(lexical_ms, 4),
                "parsing_ms": round(parsing_ms, 4),
                "materialization_ms": round(materialization_ms, 4),
                "lexical_candidates": len(lattice.candidates),
                "states_created": states_created,
                "configurations_visited": configurations_visited,
                "unique_configurations": len(visited),
                "revisited_configurations": revisited,
                "improved_revisits": improved_revisits,
                "states_visited": len(visited),
                "transitions_executed": transitions,
                "decisions": decisions,
                "backtracks": max(0, len(visited) - (winner.depth + 1 if winner else 0)),
                "dead_ends": dead_ends,
                "feature_rejections": feature_rejections,
                "lookahead_rejections": lookahead_rejections,
                "shift_reduce_backtracks": shift_reduce_conflicts,
                "reduce_reduce_backtracks": reduce_reduce_conflicts,
                "lexical_category_backtracks": lexical_conflicts,
                "premature_reductions": premature_reductions,
                "max_backtrack_depth": max_backtrack_depth,
                "repeated_transitions": repeated_transitions,
                "failed_configuration_hits": failed_config_hits,
                "early_conflict_hotspots": [
                    {"position": position, "action": action, "descendant_visits": visits}
                    for (position, action), visits in first_conflict_visits.most_common(5)
                ],
                "memoization": self.memoization,
                "lookahead": self.lookahead,
                "delayed_commitments": self.delayed_commitments,
                "contextual_statistics": self.contextual_statistics,
                "ambiguity_points": len(ambiguities),
                "max_agenda": max_agenda,
                "native_success": item is not None,
                "fallback": False,
            },
            ambiguities=ambiguities,
            exhaustive=exhaustive,
            _choice_records=tuple(records),
            _lattice=lattice,
        )

    @staticmethod
    def _reduce(rule: GrammarRule, children: tuple[CompactNode, ...]) -> CompactNode | None:
        env: dict[str, object] = {}
        for symbol, child in zip(rule.rhs, children):
            if any(intern(required) not in child.evidence for required in symbol.requires):
                return None
            result = unify(symbol.features, child.features, env)
            if result is None:
                return None
            _merged, env = result
        lhs = substitute_structure(rule.lhs.features, env)
        evidence: set[int] = set()
        for lhs_name, lhs_value in rule.lhs.features.items():
            if not isinstance(lhs_value, Variable):
                evidence.add(lhs_name)
                continue
            for symbol, child in zip(rule.rhs, children):
                if any(
                    isinstance(rhs_value, Variable)
                    and rhs_value.name == lhs_value.name
                    and rhs_name in child.evidence
                    for rhs_name, rhs_value in symbol.features.items()
                ):
                    evidence.add(lhs_name)
                    break
        return CompactNode(
            rule.lhs.category, rule.lhs.category_id,
            children[0].start, children[-1].end,
            lhs, frozenset(evidence),
            sum(child.score for child in children) + rule.score,
            rule=rule, children=children,
        )

    def _materialize(self, node: CompactNode) -> ChartItem:
        if node.candidate is not None:
            candidate = node.candidate
            return ChartItem(
                node.start, node.end, node.category, node.features, None, node.score,
                Provenance(candidate.source, {
                    "surface": candidate.surface, "lemma": candidate.lemma,
                    "sense_id": candidate.sense_id,
                }),
                syntax=_lexical_syntax(candidate), lexical_candidate=candidate,
            )
        assert node.rule is not None
        children = tuple(self._materialize(child) for child in node.children)
        return ChartItem(
            node.start, node.end, node.category, node.features, None, node.score,
            Provenance("rule", {
                "rule_id": node.rule.rule_id,
                "children": tuple(child.provenance for child in children),
            }),
            children=children, rule_id=node.rule.rule_id,
            syntax=_compose_syntax(node.rule, children),
        )


@dataclass(slots=True)
class _SharedNode:
    key: tuple[Any, ...]
    best: CompactNode
    alternatives: list[CompactNode] = field(default_factory=list)


@dataclass(slots=True)
class _SharedPartial:
    partial_id: int
    reduction: CompiledReduction
    dot: int
    start: int
    end: int
    children: tuple[CompactNode, ...]
    bindings: dict[str, object]
    alternatives: int = 0


class _SharedSearch:
    """Feature-aware left-corner chart opened only by encountered symbols.

    Equivalent constituents and dotted items share one continuation.  Their
    derivations remain attached as alternatives, so recognition work is not
    repeated for every attachment history.
    """

    def __init__(self, parser: "SharedPredictiveParser", text: str, lattice: LexicalLattice) -> None:
        self.parser = parser
        self.text = text
        self.lattice = lattice
        self.nodes: dict[tuple[Any, ...], _SharedNode] = {}
        self.by_start_category: dict[tuple[int, int], list[_SharedNode]] = defaultdict(list)
        self.partials: dict[tuple[Any, ...], _SharedPartial] = {}
        self.waiting: dict[tuple[int, int], list[_SharedPartial]] = defaultdict(list)
        self.agenda: list[tuple[int, float, int, _SharedNode]] = []
        self.serial = count()
        self.roots: list[CompactNode] = []
        self.operations = 0
        self.transitions = 0
        self.shared_nodes = 0
        self.shared_partials = 0
        self.feature_rejections = 0
        self.lookahead_rejections = 0
        self.max_agenda = 0
        self.complete = False
        self.target_roots = 1
        self.unification_cache: dict[tuple[Any, ...], dict[str, object] | None] = {}
        self.unification_cache_hits = 0
        self._seed()

    def _next_start(self, end: int) -> int:
        return self.parser._next_start(self.text, end)

    @staticmethod
    def _bindings_key(bindings: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((name, repr(value)) for name, value in bindings.items()))

    def _priority(self, node: CompactNode) -> tuple[int, float, int]:
        # Progress left-to-right by source start.  Within a start position,
        # prefer the statistically/intrinsically strongest constituent.
        return (node.start, -node.score, next(self.serial))

    def _seed(self) -> None:
        for candidate in self.lattice.candidates:
            if intern(candidate.category) not in self.parser.compiled.goal_ancestors:
                continue
            node = CompactNode(
                candidate.category, intern(candidate.category),
                candidate.span_start, candidate.span_end, candidate.features,
                frozenset(
                    name for name, value in candidate.features.items()
                    if not isinstance(value, Variable)
                ),
                candidate.score, candidate=candidate,
            )
            self._offer_node(node)

    def _offer_node(self, node: CompactNode) -> _SharedNode:
        key = node.grammatical_key()
        packed = self.nodes.get(key)
        if packed is not None:
            self.shared_nodes += 1
            signature = (
                node.rule.rule_id if node.rule else None,
                tuple(child.grammatical_key() for child in node.children),
            )
            if len(packed.alternatives) < 8 and all(
                (
                    candidate.rule.rule_id if candidate.rule else None,
                    tuple(child.grammatical_key() for child in candidate.children),
                ) != signature
                for candidate in packed.alternatives
            ):
                packed.alternatives.append(node)
                if (
                    node.category_id == self.parser.goal_id
                    and node.start == 0
                    and self.parser._root_span(self.text, node.end)
                ):
                    self.roots.append(node)
                    self.complete = len(self.roots) >= self.target_roots
            if node.score > packed.best.score:
                packed.best = node
            return packed
        packed = _SharedNode(key, node, [node])
        self.nodes[key] = packed
        self.by_start_category[(node.start, node.category_id)].append(packed)
        start, score, serial = self._priority(node)
        heappush(self.agenda, (start, score, serial, packed))
        self.max_agenda = max(self.max_agenda, len(self.agenda))
        if (
            node.category_id == self.parser.goal_id
            and node.start == 0
            and self.parser._root_span(self.text, node.end)
        ):
            self.roots.append(node)
            self.complete = len(self.roots) >= self.target_roots
        return packed

    def _offer_partial(
        self,
        reduction: CompiledReduction,
        dot: int,
        start: int,
        end: int,
        children: tuple[CompactNode, ...],
        bindings: dict[str, object],
    ) -> None:
        if self.complete:
            return
        if dot < len(reduction.rhs_ids) and self.parser.lookahead:
            position = self._next_start(end)
            expected = reduction.rhs_ids[dot]
            expected_first = self.parser.compiled.first.get(expected, frozenset((expected,)))
            lexical_here = frozenset(
                intern(candidate.category)
                for candidate in self.lattice.starting_at(position)
            )
            if expected_first and lexical_here and expected_first.isdisjoint(lexical_here):
                self.lookahead_rejections += 1
                return
        # Control position and bindings alone are insufficient: two paths can
        # bind identically while carrying children with different feature
        # obligations (e.g. passive NP versus relative NP).  Pack derivations
        # only after preserving those grammatical child identities.
        key = (
            reduction.index, dot, start, end, self._bindings_key(bindings),
            tuple(child.grammatical_key() for child in children),
        )
        existing = self.partials.get(key)
        if existing is not None:
            existing.alternatives += 1
            self.shared_partials += 1
            return
        partial = _SharedPartial(
            len(self.partials), reduction, dot, start, end, children, bindings,
        )
        self.partials[key] = partial
        if dot == len(reduction.rhs_ids):
            self._complete_partial(partial)
            return
        position = self._next_start(end)
        expected = reduction.rhs_ids[dot]
        self.waiting[(position, expected)].append(partial)
        for packed in tuple(self.by_start_category.get((position, expected), ())):
            self._advance(partial, packed.best)
            if self.complete:
                return

    def _complete_partial(self, partial: _SharedPartial) -> None:
        reduction = partial.reduction
        children = partial.children
        end = partial.end
        bindings = partial.bindings
        if self.parser.lookahead:
            position = self._next_start(end)
            ids = frozenset(
                intern(candidate.category)
                for candidate in self.lattice.starting_at(position)
            )
            if not self.parser.compiled.reduction_viable(
                reduction.lhs_id, ids,
                at_end=self.parser._root_span(self.text, position),
            ):
                self.lookahead_rejections += 1
                return
        lhs = substitute_structure(reduction.rule.lhs.features, bindings)
        evidence: set[int] = set()
        for lhs_name, lhs_value in reduction.rule.lhs.features.items():
            if not isinstance(lhs_value, Variable):
                evidence.add(lhs_name)
                continue
            for symbol, child in zip(reduction.rule.rhs, children):
                if any(
                    isinstance(rhs_value, Variable)
                    and rhs_value.name == lhs_value.name
                    and rhs_name in child.evidence
                    for rhs_name, rhs_value in symbol.features.items()
                ):
                    evidence.add(lhs_name)
                    break
        lookahead = self._lookahead(end)
        probability = self.parser.model.probability(
            [child.category for child in children], lookahead,
            f"reduce:{reduction.rule.rule_id}",
        )
        node = CompactNode(
            reduction.rule.lhs.category, reduction.lhs_id, partial.start, end, lhs,
            frozenset(evidence),
            sum(child.score for child in children) + reduction.rule.score + math.log(probability),
            rule=reduction.rule, children=children,
        )
        self._offer_node(node)

    def _lookahead(self, position: int) -> str:
        position = self._next_start(position)
        rows = self.lattice.starting_at(position)
        if not rows:
            return "$END"
        return max(rows, key=lambda candidate: candidate.score).category

    def _advance(self, partial: _SharedPartial, child: CompactNode) -> None:
        if self.complete:
            return
        self.transitions += 1
        symbol = partial.reduction.rule.rhs[partial.dot]
        if any(intern(required) not in child.evidence for required in symbol.requires):
            self.feature_rejections += 1
            return
        cache_key = (
            partial.reduction.index, partial.dot,
            self._bindings_key(partial.bindings), child.grammatical_key(),
        )
        if cache_key in self.unification_cache:
            self.unification_cache_hits += 1
            cached = self.unification_cache[cache_key]
            result = None if cached is None else (child.features, dict(cached))
        else:
            result = unify(symbol.features, child.features, partial.bindings)
            self.unification_cache[cache_key] = None if result is None else dict(result[1])
        if result is None:
            self.feature_rejections += 1
            return
        _merged, bindings = result
        self._offer_partial(
            partial.reduction, partial.dot + 1, partial.start, child.end,
            partial.children + (child,), bindings,
        )

    def _start(self, node: CompactNode) -> None:
        for reduction in self.parser.compiled.first_rules.get(node.category_id, ()):
            if self.complete:
                return
            symbol = reduction.rule.rhs[0]
            if any(intern(required) not in node.evidence for required in symbol.requires):
                self.feature_rejections += 1
                continue
            result = unify(symbol.features, node.features)
            if result is None:
                self.feature_rejections += 1
                continue
            _merged, bindings = result
            self.transitions += 1
            self._offer_partial(
                reduction, 1, node.start, node.end, (node,), bindings,
            )

    def _resolve(
        self, node: CompactNode,
        visiting: frozenset[tuple[Any, ...]] = frozenset(),
        *, replace_self: bool = True,
    ) -> CompactNode:
        """Return an immutable packed derivation without replaying recognition.

        Equivalent packed nodes retain their alternatives, but substituting a
        locally higher-scored child into an already-ranked parent changes its
        contextual derivation.  Root candidates therefore keep the concrete
        child choices with which they were constructed.
        """
        return node

    def _best_root(self) -> CompactNode | None:
        if not self.roots:
            return None
        resolved = (
            self._resolve(root, replace_self=False) for root in self.roots
        )
        return max(resolved, key=lambda node: node.score)

    @staticmethod
    def derivation_signature(node: CompactNode | None) -> tuple[Any, ...] | None:
        if node is None:
            return None
        return (
            node.rule.rule_id if node.rule else ("lex", node.category, node.start, node.end),
            tuple(_SharedSearch.derivation_signature(child) for child in node.children),
        )

    def run(self, *, roots_requested: int = 1, max_operations: int) -> CompactNode | None:
        self.target_roots = roots_requested
        self.complete = len(self.roots) >= roots_requested
        if self.complete:
            return self._best_root()
        while self.agenda and self.operations < max_operations:
            _start, _score, _serial, packed = heappop(self.agenda)
            node = packed.best
            self.operations += 1
            self._start(node)
            if self.complete:
                return self._best_root()
            waiting = tuple(self.waiting.get((node.start, node.category_id), ()))
            for partial in waiting:
                self._advance(partial, node)
                if self.complete:
                    return self._best_root()
            if len(self.roots) >= roots_requested:
                self.complete = True
                return self._best_root()
        return self._best_root()


class SharedPredictiveParser(PredictiveParser):
    """V2 fast path with packed local branches and deterministic fallback-free search."""

    @staticmethod
    def _roots_to_settle(lattice: LexicalLattice, *, expand: bool = False) -> int:
        """Open alternatives only at grammar-signalled ambiguity points."""
        categories = {candidate.category for candidate in lattice.candidates}
        target = 1
        if "COMP-THAT" in categories:
            target = 6
        elif "NEG" in categories:
            target = 6
        elif "QMARK" in categories:
            target = 4
        elif "WH-PRONOUN" in categories or "WH-NOM" in categories:
            target = 5
        first = min((candidate.span_start for candidate in lattice.candidates), default=0)
        if any(
            candidate.span_start == first
            and candidate.category == "V"
            and isinstance(candidate.features.get("vform"), Atom)
            and candidate.features.get("vform").name == "ing"
            for candidate in lattice.candidates
        ):
            target = max(target, 8)
        return max(target, 8) if expand else target

    def parse(self, text: str, *, mode: str = "fast") -> PredictiveResult:
        text = text.strip().strip('"\u201c\u201d\u2018\u2019').strip()
        total_started = perf_counter()
        lexical_started = perf_counter()
        lattice = build_lattice(text, self.resources.lexicon, deduplicate=True)
        lexical_ms = (perf_counter() - lexical_started) * 1000
        search_started = perf_counter()
        search = _SharedSearch(self, text, lattice)
        root = search.run(
            roots_requested=self._roots_to_settle(lattice, expand=mode == "expand"),
            max_operations=self.max_states * (4 if mode == "expand" else 1),
        )
        search_ms = (perf_counter() - search_started) * 1000
        materialization_started = perf_counter()
        item = self._materialize(root) if root is not None else None
        materialization_ms = (perf_counter() - materialization_started) * 1000
        ambiguity = ()
        if search.shared_nodes or search.shared_partials or search.agenda:
            ambiguity = (AmbiguityPoint(0, root.end if root else 0, "first_complete", ("continue_shared_search",)),)
        result = PredictiveResult(
            text, item, item is not None,
            {
                "engine": "predictive-shared-v2",
                "mode": mode,
                "stopped_by": "first_complete" if item is not None else (
                    "state_budget" if search.operations >= self.max_states else "exhausted"
                ),
                "total_wall_ms": round((perf_counter() - total_started) * 1000, 4),
                "lexical_ms": round(lexical_ms, 4),
                "parsing_ms": round(search_ms, 4),
                "materialization_ms": round(materialization_ms, 4),
                "lexical_candidates": len(lattice.candidates),
                "states_created": len(search.nodes) + len(search.partials),
                "configurations_visited": search.operations,
                "unique_configurations": len(search.nodes) + len(search.partials),
                "revisited_configurations": search.shared_nodes + search.shared_partials,
                "states_visited": search.operations,
                "transitions_executed": search.transitions,
                "decisions": search.shared_nodes + search.shared_partials,
                "backtracks": 0,
                "dead_ends": 0,
                "feature_rejections": search.feature_rejections,
                "lookahead_rejections": search.lookahead_rejections,
                "shift_reduce_backtracks": 0,
                "reduce_reduce_backtracks": 0,
                "lexical_category_backtracks": 0,
                "premature_reductions": 0,
                "max_backtrack_depth": 0,
                "repeated_transitions": 0,
                "failed_configuration_hits": 0,
                "shared_nodes": search.shared_nodes,
                "shared_partials": search.shared_partials,
                "unification_cache_hits": search.unification_cache_hits,
                "ambiguity_points": len(ambiguity),
                "max_agenda": search.max_agenda,
                "native_success": item is not None,
                "fallback": False,
            },
            ambiguity, mode == "expand", _lattice=lattice,
        )
        result._shared_search = search
        result._selected_root = root
        return result

    def expand(self, result: PredictiveResult, ambiguity_id: int) -> PredictiveResult:
        search = getattr(result, "_shared_search", None)
        if search is None:
            return super().expand(result, ambiguity_id)
        started = perf_counter()
        target = max(len(search.roots) + 4, 8)
        search.run(roots_requested=target, max_operations=self.max_states * 4)
        choices = sorted(
            (search._resolve(node, replace_self=False) for node in search.roots),
            key=lambda node: node.score, reverse=True,
        )
        selected_signature = search.derivation_signature(result._selected_root)
        root = next(
            (
                node for node in choices
                if search.derivation_signature(node) != selected_signature
            ),
            None,
        )
        item = self._materialize(root) if root is not None else None
        stats = dict(result.stats)
        stats.update({
            "mode": "expand", "total_wall_ms": round((perf_counter() - started) * 1000, 4),
            "lexical_ms": 0.0, "parsing_ms": round((perf_counter() - started) * 1000, 4),
            "materialization_ms": 0.0,
            "states_created": len(search.nodes) + len(search.partials),
            "unique_configurations": len(search.nodes) + len(search.partials),
            "shared_nodes": search.shared_nodes, "shared_partials": search.shared_partials,
            "transitions_executed": search.transitions,
        })
        expanded = PredictiveResult(
            result.text, item, item is not None, stats, result.ambiguities, True,
            _lattice=result._lattice,
        )
        expanded._shared_search = search
        expanded._selected_root = root
        return expanded


class HybridPredictiveParser(SharedPredictiveParser):
    """Deterministic V1 fast path with packed V2 conflict escalation.

    The escalation is internal to the experimental predictive engine and
    never calls the production vector parser.  The lexical lattice is reused.
    """

    def __init__(self, *args: Any, fast_states: int = 256, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fast_states = fast_states

    @staticmethod
    def _lexically_suspicious(item: ChartItem, lattice: LexicalLattice) -> bool:
        """Escalate, without deleting, an unlikely open-class homograph.

        Closed-class inventory entries are strong grammatical evidence.  A
        fast parse that instead consumes the same spelling as N/V/ADJ/ADV is
        legal but deserves comparison with locally shared alternatives.
        """
        closed = {
            "DET", "PRONOUN", "POSS", "PREP", "PREP-BY", "COORD", "CONJ",
            "NEG", "AUX", "AUX-BE", "MODAL", "COPULA", "WH-PRONOUN",
            "WH-NOM", "COMP-THAT", "TO", "PARTICLE", "DEGREE", "EXPL", "NUM",
        }
        open_class = {"N", "V", "ADJ", "ADV"}
        agenda = [item]
        while agenda:
            node = agenda.pop()
            agenda.extend(node.children)
            if node.rule_id == "clause_gapping_np":
                return True
            candidate = node.lexical_candidate
            if candidate is None:
                continue
            peers = lattice.covering(candidate.span_start, candidate.span_end)
            if candidate.category != "COMP-THAT" and any(
                peer.category == "COMP-THAT" for peer in peers
            ):
                return True
            if candidate.category not in open_class:
                continue
            if any(
                peer.category in closed and peer.score >= candidate.score
                for peer in peers
            ):
                return True
            if (
                candidate.surface.casefold().endswith("ing")
                and candidate.category != "V"
                and any(
                    peer.category == "V"
                    and isinstance(peer.features.get("vform"), Atom)
                    and peer.features.get("vform").name == "ing"
                    for peer in peers
                )
            ):
                return True
        return False

    def parse(self, text: str, *, mode: str = "fast") -> PredictiveResult:
        normalized = text.strip().strip('"\u201c\u201d\u2018\u2019').strip()
        original_limit = self.max_states
        self.max_states = self.fast_states
        try:
            fast = PredictiveParser._parse(
                self, normalized, banned=None, exhaustive=False,
            )
        finally:
            self.max_states = original_limit
        suspicious = bool(
            fast.completed and fast.item is not None
            and self._lexically_suspicious(fast.item, fast._lattice)
        )
        if fast.completed and fast.item is not None and not suspicious:
            fast.stats["engine"] = "predictive-hybrid-v2-fast"
            fast.stats["shared_escalation"] = False
            return fast

        shared_started = perf_counter()
        assert fast._lattice is not None
        search = _SharedSearch(self, normalized, fast._lattice)
        roots_requested = self._roots_to_settle(
            fast._lattice, expand=mode == "expand",
        )
        if suspicious:
            roots_requested = max(roots_requested, 4)
        root = search.run(
            roots_requested=roots_requested,
            max_operations=original_limit * (4 if mode == "expand" else 1),
        )
        shared_ms = (perf_counter() - shared_started) * 1000
        materialization_started = perf_counter()
        item = self._materialize(root) if root is not None else None
        materialization_ms = (perf_counter() - materialization_started) * 1000
        stats = {
            "engine": "predictive-hybrid-v2-shared",
            "mode": mode,
            "stopped_by": "first_complete" if item is not None else "state_budget",
            "total_wall_ms": round(float(fast.stats["total_wall_ms"]) + shared_ms + materialization_ms, 4),
            "lexical_ms": fast.stats["lexical_ms"],
            "parsing_ms": round(float(fast.stats["parsing_ms"]) + shared_ms, 4),
            "materialization_ms": round(materialization_ms, 4),
            "lexical_candidates": fast.stats["lexical_candidates"],
            "states_created": int(fast.stats["states_created"]) + len(search.nodes) + len(search.partials),
            "configurations_visited": int(fast.stats["configurations_visited"]) + search.operations,
            "unique_configurations": int(fast.stats["unique_configurations"]) + len(search.nodes) + len(search.partials),
            "revisited_configurations": int(fast.stats["revisited_configurations"]) + search.shared_nodes + search.shared_partials,
            "states_visited": int(fast.stats["states_visited"]) + search.operations,
            "transitions_executed": int(fast.stats["transitions_executed"]) + search.transitions,
            "decisions": int(fast.stats["decisions"]) + search.shared_nodes + search.shared_partials,
            "backtracks": fast.stats["backtracks"],
            "dead_ends": fast.stats["dead_ends"],
            "feature_rejections": int(fast.stats["feature_rejections"]) + search.feature_rejections,
            "lookahead_rejections": int(fast.stats["lookahead_rejections"]) + search.lookahead_rejections,
            "shift_reduce_backtracks": fast.stats["shift_reduce_backtracks"],
            "reduce_reduce_backtracks": fast.stats["reduce_reduce_backtracks"],
            "lexical_category_backtracks": fast.stats["lexical_category_backtracks"],
            "premature_reductions": fast.stats["premature_reductions"],
            "max_backtrack_depth": fast.stats["max_backtrack_depth"],
            "repeated_transitions": fast.stats["repeated_transitions"],
            "failed_configuration_hits": fast.stats["failed_configuration_hits"],
            "shared_nodes": search.shared_nodes,
            "shared_partials": search.shared_partials,
            "unification_cache_hits": search.unification_cache_hits,
            "ambiguity_points": 1 if search.agenda or search.shared_nodes else 0,
            "max_agenda": max(int(fast.stats["max_agenda"]), search.max_agenda),
            "native_success": item is not None,
            "fallback": False,
            "shared_escalation": True,
            "fast_path_stats": fast.stats,
        }
        ambiguity = (
            (AmbiguityPoint(0, root.end if root else 0, "first_complete", ("continue_shared_search",)),)
            if stats["ambiguity_points"] else ()
        )
        result = PredictiveResult(
            normalized, item, item is not None, stats, ambiguity, mode == "expand",
            _lattice=fast._lattice, _shared_search=search,
        )
        result._selected_root = root
        return result
