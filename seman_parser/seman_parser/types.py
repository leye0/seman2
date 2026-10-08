"""Type DAG: a linguistic constraint ontology, not a world model.

Types form a multiple-inheritance hierarchy used to constrain role
compatibility, filter analyses and score hypotheses. Subtype tests are
precomputed bitset lookups so ``is_subtype`` is effectively constant time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class TypeNode:
    type_id: int
    name: str
    parents: tuple[int, ...]
    ancestors: int  # bitset including self


class TypeHierarchy:
    """Precompiled type DAG with ancestor bitsets."""

    __slots__ = ("_nodes", "_by_name")

    def __init__(self) -> None:
        self._nodes: list[TypeNode] = []
        self._by_name: dict[str, int] = {}

    def define(self, name: str, parents: Sequence[str] = ()) -> int:
        existing = self._by_name.get(name)
        if existing is not None:
            return existing
        type_id = len(self._nodes)
        parent_ids = tuple(self._require(parent) for parent in parents)
        ancestors = 1 << type_id
        for parent_id in parent_ids:
            ancestors |= self._nodes[parent_id].ancestors
        self._nodes.append(
            TypeNode(type_id=type_id, name=name, parents=parent_ids, ancestors=ancestors)
        )
        self._by_name[name] = type_id
        return type_id

    def _require(self, name: str) -> int:
        try:
            return self._by_name[name]
        except KeyError:
            raise KeyError(f"undefined type: {name!r}") from None

    def lookup(self, name: str) -> int:
        return self._require(name)

    def get(self, name: str) -> int | None:
        return self._by_name.get(name)

    def name_of(self, type_id: int) -> str:
        return self._nodes[type_id].name

    def node(self, type_id: int) -> TypeNode:
        return self._nodes[type_id]

    def is_subtype(self, subtype: int, supertype: int) -> bool:
        """True when subtype is equal to or below supertype in the DAG."""
        return bool(self._nodes[subtype].ancestors & (1 << supertype))

    def is_subtype_named(self, subtype: str, supertype: str) -> bool:
        return self.is_subtype(self._require(subtype), self._require(supertype))

    def ancestors_of(self, type_id: int) -> frozenset[int]:
        mask = self._nodes[type_id].ancestors
        return frozenset(i for i in range(len(self._nodes)) if mask & (1 << i))

    def compatible(self, left: int, right: int) -> bool:
        """True when one type subsumes the other (shared hierarchy)."""
        return self.is_subtype(left, right) or self.is_subtype(right, left)

    def least_general_subsumer(self, left: int, right: int) -> int | None:
        """Return the deepest common ancestor of two types, if any."""
        shared = self._nodes[left].ancestors & self._nodes[right].ancestors
        if not shared:
            return None
        best = -1
        best_depth = -1
        for candidate in range(len(self._nodes)):
            if not shared & (1 << candidate):
                continue
            depth = bin(self._nodes[candidate].ancestors).count("1")
            if depth > best_depth:
                best = candidate
                best_depth = depth
        return best if best >= 0 else None

    def define_many(self, rows: Iterable[Mapping[str, object]]) -> None:
        """Load type definitions from data rows: {name, parents}."""
        pending = [dict(row) for row in rows]
        # Resolve in dependency order so parents exist before children.
        remaining = list(pending)
        progress = True
        while remaining and progress:
            progress = False
            next_remaining: list[dict[str, object]] = []
            for row in remaining:
                parents = row.get("parents") or ()
                names = [str(parents)] if isinstance(parents, str) else [str(p) for p in parents]
                if all(parent in self._by_name for parent in names):
                    self.define(str(row["name"]), names)
                    progress = True
                else:
                    next_remaining.append(row)
            remaining = next_remaining
        if remaining:
            stuck = ", ".join(str(row["name"]) for row in remaining)
            raise ValueError(f"unresolved type parents for: {stuck}")

    def __len__(self) -> int:
        return len(self._nodes)

    def __iter__(self) -> Iterable[TypeNode]:
        return iter(self._nodes)


def load_types(rows: Iterable[Mapping[str, object]]) -> TypeHierarchy:
    hierarchy = TypeHierarchy()
    hierarchy.define_many(rows)
    return hierarchy
