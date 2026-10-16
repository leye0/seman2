"""Opt-in L->R statistical tie-break, constrained to compiled grammar edges.

The memory is trained elsewhere using independently verified decisions.
A finished parser output is NOT training evidence. All preferences are soft:
the original reader confirms any suggested edge before it is committed.
"""
from __future__ import annotations

from .sparse_ambiguity import Conflict, SparseAmbiguityMemory
from .stack_reader import LocalCheckpointReader


class SparseGuidedCheckpointReader(LocalCheckpointReader):
    """Use a tiny, verified structural memory at actual ambiguous decisions.

    The default pipeline is unchanged: this class must be explicitly selected.
    Optional capture records choices for *manual* review, never self-training.
    """

    def __init__(self, *args, sparse_memory: SparseAmbiguityMemory,
                 capture_conflicts: bool = False, **kwargs):
        if not isinstance(sparse_memory, SparseAmbiguityMemory):
            raise TypeError("sparse_memory must be SparseAmbiguityMemory")
        super().__init__(*args, **kwargs)
        self.sparse_memory = sparse_memory
        self.capture_conflicts = capture_conflicts
        self.conflict_trace: list[tuple[Conflict, str]] = []

    def read(self):
        self.conflict_trace = []
        return super().read()

    def _select(self, state, live=None, *, excluded=frozenset()):
        selected = super()._select(state, live, excluded=excluded)
        if (selected is None or not self._stack
                or (self.sparse_memory.verified_observations <
                    self.sparse_memory.min_support and not self.capture_conflicts)):
            return selected
        # Cheap lookup over categories present at this token, not global rules.
        observed = self._categories()
        if not observed or len(observed) > 12:
            return selected
        alternatives = set()
        for category in observed:
            for symbol in state.dispatch.get(category, ()):
                if symbol in excluded or symbol in alternatives:
                    continue
                hints = tuple(h for h in state.hints.get(symbol, ())
                              if live is None or id(h[0]) in live)
                if not hints:
                    continue
                direct = self._lexical_compatible(symbol, hints)
                if symbol not in self.g.nonterminals and not direct:
                    continue
                if (symbol in self.g.nonterminals and not direct and
                        self.compiled_lookahead >= 2 and
                        not self._min_yield_available(symbol, self.pos)):
                    continue
                alternatives.add(symbol)
                if len(alternatives) > 4:
                    return selected
        if len(alternatives) < 2 or selected not in alternatives:
            return selected
        frame = self._stack[-1]
        caller = self._stack[-2] if len(self._stack) >= 2 else None
        expectations = set()
        if caller is not None and caller.phase == "waiting":
            expectations = {tail[0] for _, _, tail in caller.pending_hints if tail}
        if len(expectations) > 12:
            return selected
        site = Conflict(
            kind=f"transition:{state.state_id}",
            parent=caller.category if caller is not None else "$ROOT",
            constituent=frame.category,
            alternatives=tuple(alternatives),
            next_categories=tuple(observed),
            caller_expectations=tuple(expectations),
        )
        if self.capture_conflicts:
            self.conflict_trace.append((site, selected))
        suggestion = self.sparse_memory.hint(site)
        if suggestion is None or suggestion == selected:
            return selected
        # A remembered preference is not permission to bypass grammar,
        # active-rule masks, lexical features or bounded viability.
        rival = super()._select(
            state, live, excluded=frozenset(set(state.edges) - {suggestion}))
        if rival != suggestion or (
                state.finals and not self._viable(state.edges[rival],
                                                 self.pos + 1)):
            self.count["sparse_hint_rejected"] += 1
            return selected
        self.count["sparse_hint_applied"] += 1
        return suggestion
