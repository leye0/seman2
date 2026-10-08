"""Interned symbols: compact IDs for every linguistic label.

The runtime never dispatches on symbol meaning. Symbols are opaque
interned IDs so that categories, features, roles and types stay data.
"""

from __future__ import annotations

from typing import Iterator


class SymbolTable:
    """Bidirectional string <-> integer interning table."""

    __slots__ = ("_to_id", "_to_name")

    def __init__(self) -> None:
        self._to_id: dict[str, int] = {}
        self._to_name: list[str] = []

    def intern(self, name: str) -> int:
        existing = self._to_id.get(name)
        if existing is not None:
            return existing
        symbol_id = len(self._to_name)
        self._to_id[name] = symbol_id
        self._to_name.append(name)
        return symbol_id

    def resolve(self, symbol_id: int) -> str:
        return self._to_name[symbol_id]

    def get(self, name: str) -> int | None:
        return self._to_id.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._to_id

    def __len__(self) -> int:
        return len(self._to_name)

    def __iter__(self) -> Iterator[tuple[int, str]]:
        return enumerate(self._to_name)

    def freeze(self) -> "FrozenSymbols":
        return FrozenSymbols(tuple(self._to_name), dict(self._to_id))


class FrozenSymbols:
    """Immutable snapshot of a symbol table, safe to share across caches."""

    __slots__ = ("_names", "_ids")

    def __init__(self, names: tuple[str, ...], ids: dict[str, int]) -> None:
        self._names = names
        self._ids = ids

    def intern(self, name: str) -> int:
        try:
            return self._ids[name]
        except KeyError:
            raise KeyError(f"unknown symbol: {name!r}") from None

    def resolve(self, symbol_id: int) -> str:
        return self._names[symbol_id]

    def get(self, name: str) -> int | None:
        return self._ids.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._ids

    def __len__(self) -> int:
        return len(self._names)


# Process-wide default table for convenience. Callers that need isolation
# construct their own SymbolTable.
SYMBOLS = SymbolTable()


def intern(name: str) -> int:
    return SYMBOLS.intern(name)


def resolve(symbol_id: int) -> str:
    return SYMBOLS.resolve(symbol_id)
