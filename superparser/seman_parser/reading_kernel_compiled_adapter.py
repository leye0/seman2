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
    def __init__(self, resources: ParserResources, *,
                 verbnet_index: Any | None = None, verbnet_mode: str = 'exact',
                 structural_lookahead: int = 1, checkpoint_budget: int = 0,
                 lazy_checkpoints: bool = False,
                 stack_checkpoints: bool = False,
                 construction_guard: bool = False,
                 fast_multiword: bool = False,
                 early_construction_guard: bool = False,
                 token_only_lattice: bool = False,
                 infer_unary_promotions: bool = False,
                 reduce_checkpoints: bool = False,
                 parent_follow_reduce: bool = False,
                 reduce_follow_only: bool = False):
        self.resources = resources
        if structural_lookahead not in (1, 2, 3):
            raise ValueError('structural_lookahead must be 1, 2 or 3')
        self.structural_lookahead = structural_lookahead
        if not 0 <= checkpoint_budget <= 6:
            raise ValueError('checkpoint_budget must be 0..6')
        self.checkpoint_budget = checkpoint_budget
        self.lazy_checkpoints = lazy_checkpoints
        self.stack_checkpoints = stack_checkpoints
        self.construction_guard = construction_guard
        self.fast_multiword = fast_multiword
        self.token_only_lattice = token_only_lattice
        self.infer_unary_promotions = infer_unary_promotions
        if reduce_checkpoints and not stack_checkpoints:
            raise ValueError("reduce_checkpoints requires stack_checkpoints")
        self.reduce_checkpoints = reduce_checkpoints
        if parent_follow_reduce and not reduce_checkpoints:
            raise ValueError("parent_follow_reduce requires reduce_checkpoints")
        self.parent_follow_reduce = parent_follow_reduce
        if reduce_follow_only and not reduce_checkpoints:
            raise ValueError("reduce_follow_only requires reduce_checkpoints")
        self.reduce_follow_only = reduce_follow_only
        if early_construction_guard and not construction_guard:
            raise ValueError("early_construction_guard requires construction_guard")
        self.early_construction_guard = early_construction_guard
        grammar = resources.grammar
        self.unary_promotion_rules = ()
        if infer_unary_promotions:
            from research.verbnet_lr.unary_promotions import with_unary_head_promotions
            grammar, self.unary_promotion_rules = with_unary_head_promotions(grammar)
        self.compiled = CompiledGrammar(grammar)
        # Reuse production's unification and ChartItem materialization only.
        # NEVER call the existing Parser's parse/search algorithm.
        self.adapter = PredictiveParser(resources)
        self.verbnet_ranker = None
        if verbnet_index is not None:
            # Research-only dependency: production parser never imports VerbNet.
            from research.verbnet_lr import read_index
            from research.verbnet_lr.guidance import VerbNetRanker
            if isinstance(verbnet_index, (str, Path)):
                verbnet_index = read_index(verbnet_index)
            self.verbnet_ranker = VerbNetRanker(verbnet_index, mode=verbnet_mode)

    @classmethod
    def from_dir(cls, directory: str | Path, *, wordnet_dict: str | Path | None = None,
                 verbnet_index: Any | None = None, verbnet_mode: str = 'exact',
                 structural_lookahead: int = 1, checkpoint_budget: int = 0,
                 lazy_checkpoints: bool = False, stack_checkpoints: bool = False,
                 construction_guard: bool = False,
                 fast_multiword: bool = False,
                 early_construction_guard: bool = False,
                 token_only_lattice: bool = False):
        return cls(ParserResources.from_dir(directory, wordnet_dict=wordnet_dict),
                   verbnet_index=verbnet_index, verbnet_mode=verbnet_mode,
                   structural_lookahead=structural_lookahead, checkpoint_budget=checkpoint_budget,
                   lazy_checkpoints=lazy_checkpoints,
                   stack_checkpoints=stack_checkpoints,
                   construction_guard=construction_guard,
                   fast_multiword=fast_multiword,
                   early_construction_guard=early_construction_guard,
                   token_only_lattice=token_only_lattice,
                   infer_unary_promotions=infer_unary_promotions,
                   reduce_checkpoints=reduce_checkpoints,
                   parent_follow_reduce=parent_follow_reduce,
                   reduce_follow_only=reduce_follow_only)

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
        if self.fast_multiword:
            from research.verbnet_lr.fast_lattice import FastMultiwordLexicon
            lexical_view = FastMultiwordLexicon(self.resources.lexicon)
        else:
            lexical_view = self.resources.lexicon
        # The compiled single-token reader indexes candidates only when they
        # cover one token exactly. All multi-token entries are silently
        # ignored by IncrementalReader, so creating them is wasted work.
        # This research-only ablation leaves the default lattice unchanged.
        lattice = build_lattice(
            text, lexical_view,
            multiword_max=1 if self.token_only_lattice else 4,
        )
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

        ranker = self.verbnet_ranker
        guard = None
        if self.construction_guard:
            from research.verbnet_lr.construction_guard import ConstructionGuard
            # Derive the closed-class modal inventory from the *existing*
            # lexical lattice. No per-word grammar exceptions or new lexicon.
            guard = ConstructionGuard(
                modal_forms={c.surface.casefold() for c in lattice.candidates
                             if c.category == 'MODAL'})
        if ranker is not None:
            from research.verbnet_lr.guidance import project_postverb_events

        if self.stack_checkpoints or self.construction_guard:
            from research.verbnet_lr.stack_reader import LocalCheckpointReader
            reader_base = LocalCheckpointReader
        elif self.checkpoint_budget:
            from research.verbnet_lr.checkpoint_reader import BoundedCheckpointReader, LazyCheckpointReader
            reader_base = LazyCheckpointReader if self.lazy_checkpoints else BoundedCheckpointReader
        else:
            reader_base = IncrementalReader

        self_outer = self
        if self.early_construction_guard:
            from .reading_kernel_compiled import Stop
        class _TracedReader(reader_base):
            def _validate_completed(self, root):
                if guard is None or self_outer.early_construction_guard:
                    return True, ""
                verdict = guard.validate(root)
                return verdict.acceptable, verdict.reason

            def _reduce(self, category, children, rules):
                node = super()._reduce(category, children, rules)
                if guard is not None and self_outer.early_construction_guard:
                    verdict = guard.validate(node)
                    if not verdict.acceptable:
                        self.count["construction_early_rejections"] += 1
                        raise Stop("construction_guard_" + verdict.reason)
                return node

            def _lexical_rank_bonus(self, candidate, category: str) -> int:
                if ranker is None or category != 'V' or ranker.mode == 'zero':
                    return 0
                if not hasattr(self, '_vn_cache'):
                    self._vn_cache = {}
                    self._vn_observed = {}
                key = (self.pos, id(candidate))
                previous = self._vn_cache.get(key)
                if previous is not None:
                    self.count['verbnet_cache_hits'] += 1
                    return previous
                if self.pos not in self._vn_observed:
                    self._vn_observed[self.pos] = project_postverb_events(
                        self.tokens, self.lex, self.pos + 1,
                        max_tokens=ranker.max_tokens)
                self.count['verbnet_scoring_calls'] += 1
                bonus = ranker.score(candidate, self.tokens, self.lex, self.pos,
                                     events=self._vn_observed[self.pos])
                self._vn_cache[key] = bonus
                self.count['verbnet_positive_hints'] += int(bonus > 0)
                return bonus

            def _consume(self, category: str, hints=()):
                node = super()._consume(category, hints)
                memo[id(node)] = SemanCompiledReader._leaf(node)
                return node

        machine = _TracedReader(
            self.compiled, combine, lattice.tokens, lattice.candidates,
            compiled_lookahead=self.structural_lookahead,
            **({'replay_budget': self.checkpoint_budget,
                 'reduce_checkpoints': self.reduce_checkpoints,
                 'parent_follow_reduce': self.parent_follow_reduce,
                 'reduce_follow_only': self.reduce_follow_only}
                if self.stack_checkpoints else
                {'replay_budget': self.checkpoint_budget}
                if (self.checkpoint_budget or self.construction_guard) else {}),
        )
        outcome = machine.read()
        t2 = perf_counter()
        item = self.adapter._materialize(memo[id(outcome.root)]) if outcome.root else None
        t3 = perf_counter()
        return CompiledKernelReport(outcome, item, (t1-t0)*1000, (t2-t1)*1000, (t3-t2)*1000)
