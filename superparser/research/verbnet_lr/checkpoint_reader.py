"""Experimental bounded L→R checkpoint replay, WITHOUT a packed parse forest.

At an ambiguous compiled-trie state, retain at most one alternate edge as
a compact checkpoint (state id, token position, edge). The primary single-path
reader runs normally; only on a failure/unfinished sentence is a different,
GRAMMAR-LICENSED transition tried. Each attempt owns one tree and one reader
stack. Failed attempt trees are discarded; no chart or forest is constructed.

This is an intentionally conservative POC, NOT parallel speculative parsing.
Replaying from the root has measurable cost; benchmark reports every attempt.
The default Seman2 engine and reader remain unchanged.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from seman_parser.reading_kernel_compiled import IncrementalReader, Outcome


@dataclass(frozen=True, slots=True)
class _Choice:
    key: tuple[int, int]
    first: str
    second: str
    selected: str


class BoundedCheckpointReader(IncrementalReader):
    def __init__(self, *args, replay_budget: int = 2, **kwargs):
        if not isinstance(replay_budget, int) or not 0 <= replay_budget <= 6:
            raise ValueError("replay_budget must be in 0..6")
        super().__init__(*args, **kwargs)
        self.replay_budget = replay_budget
        self._forced: dict[tuple[int, int], str] = {}
        self._choices: list[_Choice] = []

    def _select(self, state, live=None, *, excluded=frozenset()):
        # Respect the base reader API and avoid a second selection when a
        # continuation is already known to be unique.
        best = super()._select(state, live, excluded=excluded)
        if best is None or self.replay_budget == 0:
            return best
        if len(state.edges) < 2:
            return best
        second = super()._select(state, live, excluded=frozenset((best,)) | excluded)
        if second is None:
            return best
        key = (state.state_id, self.pos)
        selected = self._forced.get(key, best)
        if selected not in (best, second):
            selected = best
        # Duplicate probes of the same state/token pair are not new choices.
        if not any(c.key == key for c in self._choices):
            self._choices.append(_Choice(key, best, second, selected))
        return selected

    @staticmethod
    def _next_plan(choices: list[_Choice]) -> dict[tuple[int, int], str] | None:
        """Depth-first alternative of the *observed*, grammar-licensed path.

        Never preserve choices after the changed checkpoint: such descendants
        belong to an invalidated continuation.
        """
        for i in range(len(choices) - 1, -1, -1):
            choice = choices[i]
            if choice.selected != choice.first:
                continue
            plan = {c.key: c.selected for c in choices[:i] if c.selected != c.first}
            plan[choice.key] = choice.second
            return plan
        return None

    def read(self) -> Outcome:
        history: list[dict[tuple[int, int], str]] = []
        cumulative = Counter()
        peak_stack = 0
        final = None
        replays = 0
        decisions = 0
        for attempt in range(self.replay_budget + 1):
            # Reset ephemeral per-attempt recognition state. Lexical lattice,
            # compact compiled grammar, and WordNet/VerbNet index are shared.
            self.pos = 0
            self.active.clear()
            self.depth = 0
            self.count = Counter()
            self.events = []
            self._choices = []
            # Optional VerbNet guide stores sentence-local scorings. Keeping
            # this dictionary across attempts is safe: candidates and tokens
            # do not change. It avoids repeated sense lookups.
            final = super().read()
            cumulative.update(self.count)
            peak_stack = max(peak_stack, self.count.get("max_stack_depth", 0))
            decisions += len(self._choices)
            if final.complete:
                break
            if attempt == self.replay_budget:
                break
            next_plan = self._next_plan(self._choices)
            if next_plan is None or next_plan == self._forced or next_plan in history:
                break
            history.append(dict(self._forced))
            self._forced = next_plan
            replays += 1
        assert final is not None
        metrics = dict(cumulative)
        metrics["max_stack_depth"] = peak_stack
        metrics["checkpoint_replays"] = replays
        metrics["checkpoint_attempts"] = replays + 1
        metrics["checkpoint_options_seen"] = decisions
        metrics["checkpoint_budget"] = self.replay_budget
        metrics["checkpoint_failed_attempts"] = replays + int(not final.complete)
        return Outcome(final.complete, final.root, final.events, metrics, final.reason)
