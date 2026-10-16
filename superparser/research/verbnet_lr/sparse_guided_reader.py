"""Opt-in sparse guidance coupled to local L->R checkpoint recovery.

Only compiled, live, lexical-compatible choices can be preferred. A recovery
that eventually finishes is weak *operational* evidence, not a gold parse.
Observed recovery choices are bounded and never generate grammar productions.
"""
from __future__ import annotations

from .sparse_ambiguity import Conflict, SparseAmbiguityMemory
from .stack_reader import LocalCheckpointReader


class SparseGuidedCheckpointReader(LocalCheckpointReader):
    """Learn tiny decision preferences at actual successful retry sites.

    Verified observations take priority. Provisional recovery wins may guide
    parsing only with explicit opt-in, high repetition and normal grammar
    viability checks. A snapshot allows a mistaken hint to be undone.
    """

    def __init__(self, *args, sparse_memory: SparseAmbiguityMemory,
                 capture_conflicts: bool = False,
                 learn_recoveries: bool = False,
                 use_recovery_hints: bool = False, **kwargs):
        if not isinstance(sparse_memory, SparseAmbiguityMemory):
            raise TypeError("sparse_memory must be SparseAmbiguityMemory")
        super().__init__(*args, **kwargs)
        self.sparse_memory = sparse_memory
        self.capture_conflicts = capture_conflicts
        self.learn_recoveries = learn_recoveries
        self.use_recovery_hints = use_recovery_hints
        self.conflict_trace: list[tuple[Conflict, str]] = []
        self.recovery_trace: list[tuple[Conflict, str, str]] = []
        self._active_recoveries = []
        self._last_completed = False

    def read(self):
        self.conflict_trace = []
        self.recovery_trace = []
        self._active_recoveries = []
        self._last_completed = False
        outcome = super().read()
        if outcome.complete:
            self._last_completed = True
            seen = set()
            for _position, site, failed, chosen in self._active_recoveries:
                key = (site, chosen)
                if key in seen:
                    continue
                seen.add(key)
                self.recovery_trace.append((site, failed, chosen))
                # Only one weak vote per distinct input/context within
                # the bounded memory horizon; no text is stored.
                sentence_id = hash(tuple(t.text.casefold() for t in self.tokens))
                if self.learn_recoveries and self.sparse_memory.note_recovery(
                        site, failed=failed, chosen=chosen,
                        observation_id=sentence_id):
                    self.count["sparse_recoveries_learned"] += 1
                    outcome.counters["sparse_recoveries_learned"] = (
                        self.count["sparse_recoveries_learned"])
        return outcome

    def verify_last_recoveries(self, *, source: str) -> int:
        """A trusted gold evaluator may promote completed recovery evidence.

        Calling this on a parse that merely completed does not certify it.
        Callers must independently verify the selected grammatical analysis.
        """
        if not self._last_completed:
            return 0
        accepted = 0
        for site, _failed, chosen in self.recovery_trace:
            accepted += self.sparse_memory.observe(
                site, chosen, source=source)
        return accepted

    def _site(self, state, live=None):
        if not self._stack:
            return None
        frame = self._stack[-1]
        if frame.phase != "walk" or frame.state is not state:
            return None
        observed = self._categories()
        if not observed or len(observed) > 12:
            return None
        alternatives = set()
        for lexical in observed:
            for symbol in state.dispatch.get(lexical, ()):
                if symbol in alternatives:
                    continue
                hints = tuple(h for h in state.hints.get(symbol, ())
                              if live is None or id(h[0]) in live)
                if not hints:
                    continue
                direct = self._lexical_compatible(symbol, hints)
                if symbol not in self.g.nonterminals and not direct:
                    continue
                if (symbol in self.g.nonterminals and not direct
                        and self.compiled_lookahead >= 2
                        and not self._min_yield_available(symbol, self.pos)):
                    continue
                if state.finals and not self._viable(
                        state.edges[symbol], self.pos + 1):
                    continue
                alternatives.add(symbol)
                if len(alternatives) > 4:
                    return None
        finals = (state.finals if live is None
                  else [r for r in state.finals if id(r) in live])
        if (self.reduce_checkpoints and finals
                and (not self.reduce_follow_only
                     or self._parent_follow_witness())):
            alternatives.add("$REDUCE")
        if not 2 <= len(alternatives) <= 4:
            return None
        caller = self._stack[-2] if len(self._stack) > 1 else None
        expectations = (
            {tail[0] for _, _, tail in caller.pending_hints if tail}
            if caller is not None and caller.phase == "waiting" else set())
        if len(expectations) > 12:
            return None
        return Conflict(
            kind=f"transition:{state.state_id}",
            parent=caller.category if caller is not None else "$ROOT",
            constituent=frame.category,
            alternatives=tuple(alternatives),
            next_categories=tuple(observed),
            caller_expectations=tuple(expectations))

    def _extension_site(self, frame):
        if frame.phase != "extend":
            return None
        caller = self._stack[-2] if len(self._stack) > 1 else None
        observed = self._categories()
        if len(observed) > 12:
            return None
        expectations = (
            {tail[0] for _, _, tail in caller.pending_hints if tail}
            if caller is not None and caller.phase == "waiting" else set())
        if len(expectations) > 12:
            return None
        return Conflict(
            kind=f"extension:{frame.state.state_id}",
            parent=caller.category if caller is not None else "$ROOT",
            constituent=frame.category,
            alternatives=("$EXTEND", "$FINISH"),
            next_categories=tuple(observed),
            caller_expectations=tuple(expectations))

    def _hint(self, site):
        if site is None:
            return None
        confirmed = self.sparse_memory.hint(site)
        if confirmed is not None:
            return confirmed
        if self.use_recovery_hints:
            return self.sparse_memory.recovery_hint(site)
        return None

    def _select(self, state, live=None, *, excluded=frozenset()):
        selected = super()._select(state, live, excluded=excluded)
        if (selected is None or
                not self._stack or
                (not self.capture_conflicts and
                 not self.use_recovery_hints and
                 self.sparse_memory.verified_observations <
                 self.sparse_memory.min_support)):
            return selected
        site = self._site(state, live)
        if site is None or selected not in site.alternatives:
            return selected
        if self.capture_conflicts:
            self.conflict_trace.append((site, selected))
        suggestion = self._hint(site)
        if suggestion is None or suggestion == selected or suggestion in excluded:
            return selected
        if suggestion not in site.alternatives:
            return selected
        if suggestion == "$REDUCE":
            # Reduction is a real grammar final, never fabricated.
            if self.replay_budget == 0:
                return selected
        else:
            # Do not take a shortcut around ordinary live grammar filtering,
            # morphology, and viability of a candidate edge.
            rival = super()._select(
                state, live,
                excluded=frozenset(set(state.edges) - {suggestion}))
            if rival != suggestion or (
                    state.finals and not self._viable(
                        state.edges[suggestion], self.pos + 1)):
                self.count["sparse_hint_rejected"] += 1
                return selected
        self.count["sparse_hint_applied"] += 1
        return suggestion

    def _prefer_finish_extension(self, frame) -> bool:
        if (self.replay_budget == 0 or not self.extension_checkpoints
                or (self._forced is not None)):
            return False
        site = self._extension_site(frame)
        chosen = self._hint(site)
        if self.capture_conflicts and site is not None:
            self.conflict_trace.append((site, "$EXTEND"))
        if chosen == "$FINISH":
            self.count["sparse_finish_hints"] += 1
            return True
        return False

    def _restore(self):
        restored = super()._restore()
        if not restored:
            return False
        point = self._snapshots[-1]
        # Any recovery after the point we just rewound has been abandoned.
        self._active_recoveries = [
            entry for entry in self._active_recoveries if entry[0] < point.pos]
        if len(point.tried) < 2:
            return True
        failed, chosen = point.tried[-2:]
        frame = self._stack[-1]
        site = (self._extension_site(frame)
                if point.first_edge in {"$EXTEND", "$FINISH"}
                else self._site(frame.state, frame.live))
        if (site is not None and failed in site.alternatives
                and chosen in site.alternatives and failed != chosen):
            self._active_recoveries.append(
                (point.pos, site, failed, chosen))
        return True
