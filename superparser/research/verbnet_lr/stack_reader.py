"""Research-only iterative L->R parser with resumable local continuations.

The baseline reader uses recursive _parse/_walk and the earlier checkpoint POC
replays a whole sentence. This version *defunctionalizes the call stack* into
compact continuation frames. A failed branch restores a previously saved
stack of grammar states and an immutable tuple of already-built children.
The prefix is not read again. No forest, chart, beams or candidate expansion.

This is deliberately opt-in and has an explicit maximum number of restores.
It reuses the existing CompiledGrammar, lexical scorer, _consume, _reduce,
viability, unification and event semantics. Never reports UNKNOWN as invalid.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Any

from seman_parser.reading_kernel_compiled import (
    Event, IncrementalReader, Outcome, ReadNode, State, Stop,
)


@dataclass(slots=True)
class _Frame:
    category: str
    start: int
    stop_at: frozenset[str]
    state: State
    children: tuple[ReadNode, ...] = ()
    live: frozenset[int] | None = None
    phase: str = "walk"           # walk, waiting, extend
    steps: int = 0
    result: ReadNode | None = None
    pending_target: State | None = None
    pending_hints: tuple = ()


@dataclass(slots=True)
class _Snapshot:
    stack: tuple[_Frame, ...]     # copied *frames*, not child trees
    pos: int
    event_len: int
    state_id: int
    first_edge: str
    tried: tuple[str, ...]


class LocalCheckpointReader(IncrementalReader):
    """Single-path explicit-stack continuation with bounded in-place restores.

    Frame snapshots are compact but not zero-cost; the measurements include
    copies, rejected edges, and restore overhead. The number of saved points
    is bounded independently of sentence length.
    """

    def __init__(self, *args, replay_budget: int = 2,
                 max_checkpoints: int = 24, **kwargs):
        if not isinstance(replay_budget, int) or not 0 <= replay_budget <= 6:
            raise ValueError("replay_budget must be in 0..6")
        if not isinstance(max_checkpoints, int) or not 1 <= max_checkpoints <= 128:
            raise ValueError("max_checkpoints must be 1..128")
        super().__init__(*args, **kwargs)
        self.replay_budget = replay_budget
        self.max_checkpoints = max_checkpoints
        self._stack: list[_Frame] = []
        self._snapshots: list[_Snapshot] = []
        self._forced: tuple[int, int, str] | None = None
        self._peak_checkpoints = 0

    def _emit(self, action, expected, detail='', *, at=None):
        """Bound active-path events; count abandoned work separately.

        The recursive reader uses an event-count budget per parse. After
        restoring a continuation we must not accidentally count discarded
        events as part of the *new* active continuation.
        """
        at = self.pos if at is None else at
        tok = self.tokens[at] if at < len(self.tokens) else None
        self.events.append(Event(
            at, tok.text if tok else '$END', action, expected, detail))
        self.count['events'] += 1
        if len(self.events) > self.limit:
            raise Stop('event_budget')

    def _enter(self, category: str, stop_at=frozenset()):
        key = (category, self.pos)
        if key in self.active:
            raise Stop(f"nonconsuming_recursive_{category}_at_{self.pos}")
        root = self.g.roots.get(category)
        if root is None:
            raise Stop(f"grammar_has_no_entry_{category}_at_{self.pos}")
        self.active.add(key)
        self.depth += 1
        self.count["max_stack_depth"] = max(
            self.count["max_stack_depth"], self.depth)
        self._emit("EXPECT", category, f"compiled state {root.state_id}")
        self._stack.append(_Frame(category, self.pos, frozenset(stop_at), root))

    def _register(self, frame: _Frame, edge: str):
        if self.replay_budget == 0 or len(frame.state.edges) < 2:
            return
        if self._forced is not None:
            depth, state_id, forced = self._forced
            if (depth, state_id, forced) == (
                len(self._stack), frame.state.state_id, edge):
                # This is the already-saved checkpoint being resumed.
                self._forced = None
                return
        # Lazy: only check a second eligible edge if/when we need a restore.
        snapshot = _Snapshot(
            stack=tuple(replace(f) for f in self._stack),
            pos=self.pos,
            event_len=len(self.events),
            state_id=frame.state.state_id,
            first_edge=edge,
            tried=(edge,),
        )
        if len(self._snapshots) >= self.max_checkpoints:
            # Keep later decision points: they are nearest to an eventual
            # failure. Reverting farther back is deliberately budget-limited.
            self._snapshots.pop(0)
            self.count["checkpoint_evictions"] += 1
        self._snapshots.append(snapshot)
        self._peak_checkpoints = max(
            self._peak_checkpoints, len(self._snapshots))
        self.count["checkpoint_saves"] += 1

    def _attach(self, frame: _Frame, child: ReadNode):
        target = frame.pending_target
        hints = frame.pending_hints
        if target is None:
            raise Stop("missing_pending_transition")
        live = frozenset(
            id(rule) for rule, slot, _ in hints
            if self._slot_candidate(child, slot) is not None
        )
        if not live:
            raise Stop(
                f"no_live_rule_{frame.category}_at_{self.pos}")
        self.count["active_rule_filters"] += 1
        frame.children = frame.children + (child,)
        frame.state = target
        frame.live = live
        frame.pending_target = None
        frame.pending_hints = ()
        frame.phase = "walk"

    def _finish(self, node: ReadNode):
        frame = self._stack.pop()
        self.active.remove((frame.category, frame.start))
        self.depth -= 1
        if self._stack:
            parent = self._stack[-1]
            if parent.phase != "waiting":
                raise Stop("unexpected_child_completion")
            self._attach(parent, node)
            return None
        return node

    def _step(self) -> ReadNode | None:
        frame = self._stack[-1]
        if frame.phase == "extend":
            root = self.g.extensions.get(frame.category)
            if (root is None or self.pos >= len(self.tokens)
                    or self._categories() & frame.stop_at
                    or self._select(root) is None):
                assert frame.result is not None
                return self._finish(frame.result)
            self.count["extensions"] += 1
            self._emit("EXTEND", frame.category,
                       f"compiled suffix at {root.state_id}")
            assert frame.result is not None
            frame.state = root
            frame.children = (frame.result,)
            frame.live = None
            frame.steps = 0
            frame.phase = "walk"
            return None

        if frame.phase != "walk":
            raise Stop("unexpected_waiting_frame")
        frame.steps += 1
        if frame.steps > len(self.tokens) * 3 + 4:
            raise Stop("nonprogressing_continuation")

        state = frame.state
        selected = self._select(state, frame.live)
        if self._forced is not None:
            depth, state_id, forced_edge = self._forced
            if depth == len(self._stack) and state_id == state.state_id:
                # This alternative was validated against the grammar's live
                # mask when restoring the checkpoint.
                selected = forced_edge
        if state.finals and selected is not None:
            if not self._viable(state.edges[selected], self.pos + 1):
                selected = None
        if selected is None:
            finals = (state.finals if frame.live is None else
                      [r for r in state.finals if id(r) in frame.live])
            if not finals:
                raise Stop(
                    f"expected_continuation_{frame.category}_at_{self.pos}_"
                    f"state_{state.state_id}")
            frame.result = self._reduce(frame.category, frame.children, finals)
            frame.phase = "extend"
            return None

        self._register(frame, selected)
        target = state.edges[selected]
        hints = tuple(
            h for h in state.hints.get(selected, ())
            if frame.live is None or id(h[0]) in frame.live
        )
        direct = self._lexical_compatible(selected, hints)
        if selected in self.g.nonterminals and not direct:
            boundary = set(target.dispatch)
            extension = self.g.extensions.get(selected)
            if (extension is not None and "COORD" in extension.edges
                    and "COORD" not in target.edges):
                boundary.discard("COORD")
            frame.pending_target = target
            frame.pending_hints = hints
            frame.phase = "waiting"
            self.count["nonterminal_opens"] += 1
            self._enter(selected, boundary)
        else:
            if target.finals and not (
                self._categories(self.pos + 1) & target.dispatch.keys()
            ):
                final_ids = {id(r) for r in target.finals}
                closing = tuple(
                    (rule, slot, tail) for rule, slot, tail in hints
                    if not tail and id(rule) in final_ids)
                if closing:
                    hints = closing
            child = self._consume(selected, hints)
            self._attach_from_direct(frame, child, target, hints)
        return None

    def _attach_from_direct(self, frame: _Frame, child: ReadNode,
                            target: State, hints):
        frame.pending_target = target
        frame.pending_hints = hints
        self._attach(frame, child)

    def _restore(self) -> bool:
        """Pop to nearest actual alternative, restore local state, and resume.

        If a saved site has no different eligible edge, discard that point;
        nothing is revisited and no baseline branch is retried.
        """
        while self._snapshots:
            point = self._snapshots.pop()
            self._stack = [replace(frame) for frame in point.stack]
            self.pos = point.pos
            self.events = self.events[:point.event_len]
            self.active = {(f.category, f.start) for f in self._stack}
            self.depth = len(self._stack)
            frame = self._stack[-1]
            alternative = self._select(
                frame.state, frame.live, excluded=frozenset(point.tried))
            if alternative is None:
                self.count["checkpoint_dead_ends"] += 1
                continue
            point.tried += (alternative,)
            self._snapshots.append(point)
            self._forced = (
                len(self._stack), point.state_id, alternative)
            self.count["checkpoint_restores"] += 1
            return True
        return False

    def read(self) -> Outcome:
        self._stack = []
        self._snapshots = []
        self._forced = None
        self.active.clear()
        self.depth = 0
        self.pos = 0
        self.events = []
        self.count = Counter()
        restores = 0
        completed_root = None
        reason = ""
        try:
            self._enter(self.goal)
            while True:
                try:
                    if completed_root is None:
                        node = self._step()
                        if node is not None:
                            completed_root = node
                    if completed_root is not None:
                        while (self.pos < len(self.tokens)
                               and self.tokens[self.pos].text in (".", "!")):
                            self._emit("CLOSE", "punctuation", "sentence end")
                            self.pos += 1
                        if self.pos < len(self.tokens):
                            raise Stop(
                                f"unconsumed_{self.pos}_{self.tokens[self.pos].text}")
                        self._emit("ACCEPT", self.goal, "input consumed")
                        self.count["checkpoint_restores_total"] = restores
                        self.count["checkpoint_peak_saved"] = self._peak_checkpoints
                        self.count["checkpoint_attempts"] = restores + 1
                        return Outcome(
                            True, completed_root, self.events, dict(self.count))
                except Stop as exc:
                    reason = str(exc)
                    if restores >= self.replay_budget or not self._restore():
                        break
                    restores += 1
                    completed_root = None
        except Stop as exc:
            reason = str(exc)
        self._emit("STOP", self.goal, reason)
        self.count["checkpoint_restores_total"] = restores
        self.count["checkpoint_peak_saved"] = self._peak_checkpoints
        self.count["checkpoint_attempts"] = restores + 1
        return Outcome(False, None, self.events, dict(self.count), reason)
