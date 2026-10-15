"""Experimental incremental reader with ONE active grammatical continuation.

Design distinction from expectation_parser.py: no agenda of live hypotheses.
At every moment there is one stack of left-factored grammatical frames.
Alternatives are cheap reversible checkpoints, not computed child parses.
Completed phrases do not invoke the production recognizer.

This is a POC, NOT the production parser. Direct left-recursive rules are
compiled as optional suffix continuations (e.g. NP -> NP PP). Indirect
left-recursion is guarded against at runtime; coverage is measured honestly.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from .engine import ParserResources
from .features import Variable, unify
from .predictive import (
    AmbiguityPoint, CompactNode, PredictiveGrammar, PredictiveParser,
    PredictiveResult, TransitionModel,
)
from .segmentation import LexicalCandidate, build_lattice
from .symbols import intern


@dataclass(frozen=True, slots=True)
class _Path:
    rule_index: int
    bindings: tuple[tuple[str, object], ...] = ()

    def env(self) -> dict[str, object]:
        return dict(self.bindings)


@dataclass(frozen=True, slots=True)
class _Frame:
    category_id: int
    start: int
    children: tuple[CompactNode, ...] = ()
    paths: tuple[_Path, ...] = ()
    # A complete constituent can remain extensible, without applying an
    # extension unless the next token actually warrants it.
    complete: CompactNode | None = None


@dataclass(frozen=True, slots=True)
class _Choice:
    kind: str  # open | lexical | complete | extend | return
    argument: Any = None
    weight: float = 0.0


@dataclass(slots=True)
class _Checkpoint:
    stack: tuple[_Frame, ...]
    position: int
    alternatives: list[_Choice]
    first_choice: str


@dataclass(slots=True)
class ReaderResult(PredictiveResult):
    """Drop-in predictive result with extra experimental instrumentation."""


class ContinuationCounts:
    """Tiny, persistable transition-frequency table. Does not license rules.

    Decisions are conditioned on the active construction, its recognized
    child-category prefix and next lexical category. No lexeme memorization.
    """

    FORMAT = 'seman2-continuation-counts-v1'

    def __init__(self, alpha: float = 2.0):
        self.alpha = alpha
        self.rows: dict[str, Counter[str]] = defaultdict(Counter)

    @staticmethod
    def key(category: str, prefix: tuple[str, ...], incoming: str) -> str:
        return f'{category}|{",".join(prefix[-3:])}|{incoming}'

    def observe(self, category: str, prefix: tuple[str, ...], incoming: str,
                continuation: str, weight: float = 1.0) -> None:
        for context in (
            self.key(category, prefix, incoming),
            self.key(category, (), incoming),
            self.key(category, (), '*'),
        ):
            self.rows[context][continuation] += weight

    def probability(self, category: str, prefix: tuple[str, ...], incoming: str,
                    continuation: str) -> float:
        probability = 0.08  # unseen decisions remain available
        for context in (
            self.key(category, (), '*'),
            self.key(category, (), incoming),
            self.key(category, prefix, incoming),
        ):
            counts = self.rows.get(context)
            if counts:
                probability = (counts.get(continuation, 0) + self.alpha * probability) / (sum(counts.values()) + self.alpha)
        return max(0.0001, probability)

    def observe_tree(self, root: Any, weight: float = 1.0) -> None:
        """Learn from externally accepted syntax trees (not self-confirmation)."""
        def first_pos(node: Any) -> str:
            while getattr(node, 'children', ()):
                node = node.children[0]
            return node.category

        def walk(node: Any, next_pos: str) -> None:
            children = getattr(node, 'children', ())
            for index, child in enumerate(children):
                child_follow = first_pos(children[index + 1]) if index + 1 < len(children) else next_pos
                walk(child, child_follow)
            if not children:
                return
            prefix: tuple[str, ...] = ()
            for child in children:
                self.observe(node.category, prefix, first_pos(child), child.category, weight)
                prefix += (child.category,)
            # A construction can be completed before the next lexical word,
            # not merely at sentence end. Learn that transition explicitly.
            self.observe(node.category, prefix, next_pos, '$DONE', weight)
            # A direct-left-recursive parent records the alternative to
            # extend a *completed* child at the next lexical position.
            if len(children) > 1 and children[0].category == node.category:
                base = children[0]
                base_prefix = tuple(ch.category for ch in getattr(base, 'children', ()))
                self.observe(node.category, base_prefix, first_pos(children[1]), '$EXTEND', weight)
        walk(root, '$END')

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({'format': self.FORMAT, 'alpha': self.alpha,
            'rows': {k: dict(v) for k, v in self.rows.items()}}, indent=2, sort_keys=True) + '\n')

    @classmethod
    def load(cls, path: str | Path) -> 'ContinuationCounts':
        data = json.loads(Path(path).read_text())
        if data['format'] != cls.FORMAT:
            raise ValueError('Unsupported continuation-counts version')
        model = cls(float(data['alpha']))
        for k, v in data['rows'].items():
            model.rows[k].update(v)
        return model


class _Reader:
    """One grammatical interpretation being constructed and revised."""

    def __init__(self, parser: 'ContinuationReader', text: str, lattice: Any):
        self.parser = parser
        self.text = text
        self.lattice = lattice
        self.lex: dict[int, dict[int, list[LexicalCandidate]]] = defaultdict(lambda: defaultdict(list))
        for c in lattice.candidates:
            self.lex[c.span_start][intern(c.category)].append(c)
        self.lex_mask = {pos: frozenset(bucket) for pos, bucket in self.lex.items()}
        self.position = self.skip(0)
        self.stats: Counter[str] = Counter()
        self.stack: tuple[_Frame, ...] = (self.start_frame(parser.goal_id, self.position),)
        self.checkpoints: list[_Checkpoint] = []
        self.memo_failure: set[tuple[Any, ...]] = set()
        self.visited: Counter[tuple[Any, ...]] = Counter()
        self.result: CompactNode | None = None
        self.failure_reason = 'exhausted'
        self.max_stack = 1
        self.max_checkpoints = 0
        self.best_pending: int = -1
        self.ambiguities: list[AmbiguityPoint] = []
        self.trace: list[dict[str, Any]] = []
        self._rule_lookup = parser.compiled.reductions
        self._leaf_cache: dict[int, CompactNode] = {}

    def skip(self, pos: int) -> int:
        return self.parser._next_start(self.text, pos)

    def is_end(self, pos: int | None = None) -> bool:
        return self.parser._root_span(self.text, self.position if pos is None else pos)

    def lookahead(self) -> tuple[int, ...]:
        return tuple(self.lex.get(self.position, ()))

    def possible(self, category: int, position: int) -> bool:
        candidates = self.lex_mask.get(position, frozenset())
        if not candidates:
            return False
        return not self.parser.first.get(category, frozenset((category,))).isdisjoint(candidates)

    def start_frame(self, category_id: int, position: int) -> _Frame:
        """Use compiled FIRST/POS index; create ONE shared set of paths.

        Looking up the expected category and current POS is a bounded hash
        lookup, not a fresh scan of every possible grammar derivation.
        """
        lex_categories = self.lex_mask.get(position, frozenset())
        indices: set[int] = set()
        for pos_id in lex_categories:
            indices.update(self.parser.start_index.get((category_id, pos_id), ()))
        options = tuple(_Path(index) for index in sorted(indices))
        self.stats['rules_indexed_at_open'] += len(options)
        return _Frame(category_id, position, paths=options)

    def _leaf(self, candidate: LexicalCandidate) -> CompactNode:
        key = id(candidate)
        if key not in self._leaf_cache:
            self._leaf_cache[key] = CompactNode(
                candidate.category, intern(candidate.category),
                candidate.span_start, candidate.span_end, candidate.features,
                frozenset(name for name, value in candidate.features.items()
                          if not isinstance(value, Variable)),
                candidate.score, candidate=candidate,
            )
        return self._leaf_cache[key]

    def _incoming_for(self, category: int) -> str:
        # The context is the NEXT lexical POS at the current reading point,
        # not FIRST(category): the frame may be already partially complete.
        # Otherwise we would label e.g. a following verb after a complete
        # NP as $UNKNOWN and be unable to learn when to finish the NP.
        lexical = self.lex.get(self.position, {})
        if not lexical:
            return '$END' if self.is_end() else '$UNKNOWN'
        best = max((c for group in lexical.values() for c in group),
                   key=lambda c: c.score)
        return best.category

    def _rank(self, frame: _Frame, options: list[_Choice]) -> list[_Choice]:
        if len(options) <= 1:
            return options
        category = self.parser.cat_names.get(frame.category_id, str(frame.category_id))
        prefix = tuple(n.category for n in frame.children)
        incoming = self._incoming_for(frame.category_id)
        def rank(o: _Choice) -> tuple[float, str]:
            # An explicit model is trained on decisions of this automaton,
            # not on SHIFT/REDUCE actions from the previous POCs.
            move = (self.parser.cat_names.get(o.argument, str(o.argument))
                    if o.kind == 'open' else '$DONE' if o.kind == 'return'
                    else 'lex:' + o.argument.category if o.kind == 'lexical'
                    else '$EXTEND' if o.kind == 'extend'
                    else o.kind if o.kind != 'complete'
                    else '$DONE')
            probability = self.parser.counts.probability(category, prefix, incoming, move)
            # No hardcoded sentence patterns. Only minimal generic biases:
            # consume the available lexical item instead of opening a chain
            # of unary conversions, and don't finish incomplete frames.
            base = o.weight
            if o.kind == 'lexical':
                base += 0.2
            if o.kind == 'open':
                base -= 0.08
            if o.kind == 'complete' and self.is_end():
                base += 0.5
            if o.kind == 'return' and self.is_end():
                base += 0.5
            return (base + self.parser.model_weight * math.log(probability), move)
        return sorted(options, key=rank, reverse=True)

    def _options(self, frame: _Frame) -> list[_Choice]:
        # Existing complete node: either attach to parent, or activate a
        # suffix extension signalled by the actual next token.
        if frame.complete is not None:
            opts = [_Choice('return')]
            if not self.is_end():
                for index in self.parser.by_extension.get(frame.category_id, ()):
                    r = self._rule_lookup[index]
                    if len(r.rhs_ids) > 1 and self.possible(r.rhs_ids[1], self.position):
                        opts.append(_Choice('extend', index))
            return self._rank(frame, opts)

        if self.is_end() and not frame.children:
            # No empty productions in the grammar currently used by Seman2.
            return []

        opts: list[_Choice] = []
        if not frame.children:
            for candidate in self.lex.get(self.position, {}).get(frame.category_id, ()):
                opts.append(_Choice('lexical', candidate, candidate.score))

        # A rule-path set factors common recognized prefixes. Check only the
        # NEXT expected categories of the paths, not all grammar derivations.
        expected: set[int] = set()
        for path in frame.paths:
            self.stats['rule_paths_considered'] += 1
            r = self._rule_lookup[path.rule_index]
            if len(r.rhs_ids) == len(frame.children):
                opts.append(_Choice('complete', path.rule_index, r.rule.score))
            else:
                next_cat = r.rhs_ids[len(frame.children)]
                if next_cat not in expected and self.possible(next_cat, self.position):
                    expected.add(next_cat)
                    opts.append(_Choice('open', next_cat))

        # Finishing a complete alternative is usually preferable when the
        # next lexeme doesn't match a longer alternative; otherwise predictors
        # learn which continuation to attempt first.
        if self.is_end():
            return self._rank(frame, [o for o in opts if o.kind == 'complete'])
        return self._rank(frame, opts)

    def _offer_child(self, parent: _Frame, child: CompactNode) -> _Frame | None:
        accepted: list[_Path] = []
        dot = len(parent.children)
        for path in parent.paths:
            r = self._rule_lookup[path.rule_index]
            if dot >= len(r.rhs_ids) or r.rhs_ids[dot] != child.category_id:
                continue
            sym = r.rule.rhs[dot]
            self.stats['unification_attempts'] += 1
            if any(intern(req) not in child.evidence for req in sym.requires):
                self.stats['feature_rejections'] += 1
                continue
            combined = unify(sym.features, child.features, path.env())
            if combined is None:
                self.stats['feature_rejections'] += 1
                continue
            accepted.append(_Path(path.rule_index, tuple(sorted(combined[1].items()))))
        if not accepted:
            return None
        return _Frame(parent.category_id, parent.start,
                      parent.children + (child,), tuple(accepted))

    def _node_from_rule(self, frame: _Frame, index: int) -> CompactNode | None:
        r = self._rule_lookup[index]
        # Shared canonical unifier in the existing Seman2 predictive parser.
        self.stats['unification_attempts'] += 1
        node = self.parser._reduce(r.rule, frame.children)
        if node is None:
            self.stats['feature_rejections'] += 1
        return node

    def _apply(self, choice: _Choice) -> bool:
        frame = self.stack[-1]
        if choice.kind == 'open':
            category = choice.argument
            if any(f.category_id == category and f.start == self.position
                   and not f.children and f.complete is None for f in self.stack):
                self.stats['recursive_guard'] += 1
                return False
            child_frame = self.start_frame(category, self.position)
            # Lexical categories don't require rule paths.
            if not child_frame.paths and not self.lex.get(self.position, {}).get(category):
                return False
            self.stack += (child_frame,)
            self.stats['frames_opened'] += 1
            self.max_stack = max(self.max_stack, len(self.stack))
            return True
        if choice.kind == 'lexical':
            c = choice.argument
            if c.span_start != self.position:
                return False
            self.stack = self.stack[:-1] + (_Frame(frame.category_id, frame.start,
                                                 frame.children, frame.paths,
                                                 complete=self._leaf(c)),)
            self.position = self.skip(c.span_end)
            self.stats['lexical_consumptions'] += 1
            return True
        if choice.kind == 'complete':
            node = self._node_from_rule(frame, choice.argument)
            if node is None:
                return False
            self.stack = self.stack[:-1] + (_Frame(frame.category_id, frame.start,
                                                 frame.children, frame.paths, complete=node),)
            self.stats['rules_completed'] += 1
            return True
        if choice.kind == 'extend':
            extension = self._rule_lookup[choice.argument]
            child = frame.complete
            assert child is not None
            sym = extension.rule.rhs[0]
            self.stats['unification_attempts'] += 1
            if any(intern(req) not in child.evidence for req in sym.requires):
                return False
            merged = unify(sym.features, child.features, {})
            if merged is None:
                return False
            new_frame = _Frame(frame.category_id, frame.start, (child,),
                               (_Path(extension.index, tuple(sorted(merged[1].items()))),))
            self.stack = self.stack[:-1] + (new_frame,)
            self.stats['extensions_activated'] += 1
            return True
        if choice.kind == 'return':
            assert frame.complete is not None
            node = frame.complete
            if len(self.stack) == 1:
                if not self.is_end() or node.start != self.skip(0) or node.category_id != self.parser.goal_id:
                    return False
                self.result = node
                return True
            parent = self._offer_child(self.stack[-2], node)
            if parent is None:
                return False
            self.stack = self.stack[:-2] + (parent,)
            self.stats['attachments'] += 1
            return True
        raise AssertionError(f'unknown choice kind: {choice.kind}')

    def _state_key(self) -> tuple[Any, ...]:
        # Instrumentation only; no unsound pruning of derivation-distinct
        # configurations. Failure cache records only exhaustion at a fully
        # specified checkpoint, rather than equating short category suffixes.
        return (self.position, tuple((f.category_id, f.start,
            tuple(n.grammatical_key() for n in f.children),
            tuple(p.rule_index for p in f.paths),
            f.complete.grammatical_key() if f.complete else None) for f in self.stack))

    def _reconsider(self) -> bool:
        while self.checkpoints:
            checkpoint = self.checkpoints[-1]
            if not checkpoint.alternatives:
                self.checkpoints.pop()
                continue
            alternative = checkpoint.alternatives.pop(0)
            self.stack = checkpoint.stack
            self.position = checkpoint.position
            self.stats['revisions'] += 1
            if self.parser.trace and len(self.trace) < 500:
                self.trace.append({'at': self.position, 'event': 'REPAIR',
                                   'alternative': alternative.kind,
                                   'frame': self.parser.cat_names.get(self.stack[-1].category_id, '?')})
            if self._apply(alternative):
                return True
        return False

    def run(self) -> CompactNode | None:
        while self.result is None:
            if self.stats['decisions_executed'] >= self.parser.max_steps:
                self.failure_reason = 'step_budget'
                break
            self.stats['decisions_executed'] += 1
            key = self._state_key() if self.parser.instrument_states else None
            if key is not None:
                self.visited[key] += 1
            frame = self.stack[-1]
            options = self._options(frame)
            if not options:
                self.stats['dead_ends'] += 1
                if not self._reconsider():
                    break
                continue
            # One action is executed. Other options are merely descriptors
            # stored in a reversible checkpoint; they do not get parsed.
            if len(options) > 1:
                self.checkpoints.append(_Checkpoint(self.stack, self.position,
                    list(options[1:]), options[0].kind))
                self.stats['choices_deferred'] += len(options) - 1
                self.max_checkpoints = max(self.max_checkpoints, len(self.checkpoints))
            if self.parser.trace and len(self.trace) < 500:
                self.trace.append({
                    'at': self.position,
                    'frame': self.parser.cat_names.get(frame.category_id, '?'),
                    'recognized': [child.category for child in frame.children],
                    'action': options[0].kind,
                    'target': (self.parser.cat_names.get(options[0].argument, '?')
                               if options[0].kind == 'open'
                               else options[0].argument.category if options[0].kind == 'lexical'
                               else self._rule_lookup[options[0].argument].rule.rule_id
                               if options[0].kind in {'complete', 'extend'} else None),
                    'other_actions_dormant': len(options) - 1,
                })
            if not self._apply(options[0]):
                self.stats['dead_ends'] += 1
                if not self._reconsider():
                    break
        return self.result


class ContinuationReader(PredictiveParser):
    """A real one-path incremental reader; no chart/exhaustive fallback.

    Existing Predictor's grammar, feature unification, lexical lattice,
    CompactNode and ChartItem conversion are retained for interoperability.
    """

    def __init__(self, resources: ParserResources, *,
                 counts: ContinuationCounts | None = None,
                 model_weight: float = 0.7,
                 max_steps: int = 20_000, instrument_states: bool = False,
                 trace: bool = False):
        super().__init__(resources, max_states=max_steps)
        self.counts = counts or ContinuationCounts()
        self.model_weight = model_weight
        self.max_steps = max_steps
        self.instrument_states = instrument_states
        self.trace = trace
        self.by_lhs: dict[int, tuple[int, ...]] = {}
        self.by_extension: dict[int, tuple[int, ...]] = {}
        by_lhs = defaultdict(list)
        by_extension = defaultdict(list)
        categories: set[int] = set()
        for r in self.compiled.reductions:
            by_lhs[r.lhs_id].append(r.index)
            if r.rhs_ids and r.rhs_ids[0] == r.lhs_id:
                by_extension[r.lhs_id].append(r.index)
            categories.add(r.lhs_id)
            categories.update(r.rhs_ids)
        self.by_lhs = {key: tuple(value) for key, value in by_lhs.items()}
        self.by_extension = {key: tuple(value) for key, value in by_extension.items()}
        self.cat_names: dict[int, str] = {}
        for r in self.compiled.reductions:
            self.cat_names[r.lhs_id] = r.rule.lhs.category
            for cat, sym in zip(r.rhs_ids, r.rule.rhs):
                self.cat_names[cat] = sym.category
        self.first = self.compiled.first
        start_index: dict[tuple[int, int], set[int]] = defaultdict(set)
        for r in self.compiled.reductions:
            if not r.rhs_ids or r.rhs_ids[0] == r.lhs_id:
                continue
            # Factor all productions with a shared possible lexical onset.
            # This index is built ONCE, before any sentences are read.
            for lexical_cat in self.first.get(r.rhs_ids[0], (r.rhs_ids[0],)):
                start_index[(r.lhs_id, lexical_cat)].add(r.index)
        self.start_index = {
            key: tuple(sorted(indices)) for key, indices in start_index.items()
        }

    @classmethod
    def from_dir(cls, directory: str | Path, **kwargs: Any) -> 'ContinuationReader':
        return cls(ParserResources.from_dir(directory), **kwargs)

    def parse(self, text: str, *, mode: str = 'fast') -> ReaderResult:
        if mode != 'fast':
            raise ValueError('V1 implements only fast parsing; alternatives are deferred, not enumerated')
        normalized = text.strip().strip('"\u201c\u201d\u2018\u2019').strip()
        started = perf_counter()
        lex_start = perf_counter()
        lattice = build_lattice(normalized, self.resources.lexicon, deduplicate=True)
        lexical_ms = (perf_counter() - lex_start) * 1000
        parse_start = perf_counter()
        search = _Reader(self, normalized, lattice)
        node = search.run()
        parse_ms = (perf_counter() - parse_start) * 1000
        material_start = perf_counter()
        item = self._materialize(node) if node else None
        material_ms = (perf_counter() - material_start) * 1000
        stats = dict(search.stats)
        stats.update({
            'engine': 'continuation-reader-v1',
            'total_wall_ms': round((perf_counter() - started) * 1000, 4),
            'lexical_ms': round(lexical_ms, 4),
            'parsing_ms': round(parse_ms, 4),
            'materialization_ms': round(material_ms, 4),
            'frames_max_depth': search.max_stack,
            'input_tokens': len(lattice.tokens),
            'decisions_per_token': round(search.stats['decisions_executed'] / max(1, len(lattice.tokens)), 3),
            'checkpoints_max': search.max_checkpoints,
            'unique_states_instrumented': len(search.visited),
            'repeated_states_instrumented': sum(n - 1 for n in search.visited.values()),
            'native_success': item is not None,
            'grammatical_derivation_found': item is not None,
            'linguistically_audited': False,
            'fallback': False,
            'stopped_by': 'first_complete' if item is not None else search.failure_reason,
            'alternatives_exhaustively_enumerated': False,
            **({'trace': search.trace} if self.trace else {}),
        })
        # Deferred choices exist even when only one result has been chosen.
        # They are not claimed to represent independently verified parses.
        ambiguities = ((AmbiguityPoint(0, 0, 'first_complete', ('deferred_possible',)),)
                       if search.checkpoints else ())
        return ReaderResult(normalized, item, item is not None, stats, ambiguities,
                            False, _lattice=lattice)
