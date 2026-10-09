"""POC-08: source-aware deltas between partial reported states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True, order=True)
class ReportedProposition:
    relation_id: str
    arguments: tuple[str, ...]
    truth: bool = True
    mode: str = "asserted"

    @property
    def atom(self) -> tuple[str, tuple[str, ...]]:
        return self.relation_id, self.arguments


@dataclass(frozen=True, slots=True)
class PartialState:
    state_id: str
    source_id: str
    time_index: int
    propositions: tuple[ReportedProposition, ...]

    @classmethod
    def build(cls, state_id, source_id, time_index, propositions: Sequence[ReportedProposition]):
        asserted = tuple(sorted({row for row in propositions if row.mode == "asserted"}))
        atoms: dict[tuple[str, tuple[str, ...]], bool] = {}
        for row in asserted:
            previous = atoms.setdefault(row.atom, row.truth)
            if previous != row.truth:
                raise ValueError(f"contradictory proposition in state {state_id}: {row.atom}")
        return cls(state_id, source_id, time_index, asserted)


@dataclass(frozen=True, slots=True)
class StateDelta:
    before_id: str
    after_id: str
    added: tuple[ReportedProposition, ...]
    explicitly_reversed: tuple[tuple[ReportedProposition, ReportedProposition], ...]
    unchanged: tuple[ReportedProposition, ...]
    unmentioned_after: tuple[ReportedProposition, ...]
    comparable: bool
    reason: str | None = None


def compare_partial_states(before: PartialState, after: PartialState) -> StateDelta:
    if before.source_id != after.source_id:
        return StateDelta(before.state_id, after.state_id, (), (), (), (), False, "different_source")
    if after.time_index < before.time_index:
        return StateDelta(before.state_id, after.state_id, (), (), (), (), False, "time_reversal")
    left = {row.atom: row for row in before.propositions}
    right = {row.atom: row for row in after.propositions}
    added = []
    reversed_rows = []
    unchanged = []
    unmentioned = []
    for atom, row in left.items():
        later = right.get(atom)
        if later is None:
            unmentioned.append(row)
        elif later.truth == row.truth:
            unchanged.append(row)
        else:
            reversed_rows.append((row, later))
    for atom, row in right.items():
        if atom not in left:
            added.append(row)
    return StateDelta(
        before.state_id,
        after.state_id,
        tuple(sorted(added)),
        tuple(sorted(reversed_rows)),
        tuple(sorted(unchanged)),
        tuple(sorted(unmentioned)),
        True,
    )
