"""Feature structures and unification.

Values are atoms, variables, nested feature structures, disjunctions or
the open top. Unification is non-destructive: it returns a new structure
plus an extended binding environment, so failed attempts leave no trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .symbols import SymbolTable, intern, resolve

# Sentinel for an unbound / unspecified slot.
TOP = object()


class UnificationFailure(Exception):
    """Raised only when callers prefer exceptions over None returns."""


@dataclass(frozen=True, slots=True)
class Atom:
    """An interned atomic value (symbol id)."""

    symbol: int

    @classmethod
    def of(cls, name: str) -> "Atom":
        return cls(intern(name))

    @property
    def name(self) -> str:
        return resolve(self.symbol)

    def __repr__(self) -> str:
        return f"Atom({self.name!r})"


@dataclass(frozen=True, slots=True)
class Variable:
    """A unification variable, written ``?name`` in data files."""

    name: str

    def __repr__(self) -> str:
        return f"Variable({self.name!r})"


@dataclass(frozen=True, slots=True)
class Disjunction:
    """A finite set of alternative values."""

    options: tuple[object, ...]

    def __repr__(self) -> str:
        return f"Disjunction({list(self.options)!r})"


@dataclass(frozen=True, slots=True)
class FeatureStructure:
    """A recursive attribute-value matrix keyed by interned feature names."""

    features: Mapping[int, object] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "FeatureStructure":
        return cls({})

    @classmethod
    def build(cls, values: Mapping[str, object], *, symbols: SymbolTable | None = None) -> "FeatureStructure":
        table = symbols
        out: dict[int, object] = {}
        for key, value in values.items():
            symbol = table.intern(key) if table is not None else intern(key)
            out[symbol] = coerce(value, symbols=table)
        return cls(out)

    def get(self, feature: str | int) -> object | None:
        symbol = intern(feature) if isinstance(feature, str) else feature
        return self.features.get(symbol)

    def has(self, feature: str | int) -> bool:
        symbol = intern(feature) if isinstance(feature, str) else feature
        return symbol in self.features

    def with_feature(self, feature: str | int, value: object) -> "FeatureStructure":
        symbol = intern(feature) if isinstance(feature, str) else feature
        merged = dict(self.features)
        merged[symbol] = value
        return FeatureStructure(merged)

    def keys(self) -> Iterable[int]:
        return self.features.keys()

    def items(self) -> Iterable[tuple[int, object]]:
        return self.features.items()

    def as_dict(self, symbols: SymbolTable | None = None) -> dict[str, object]:
        table = symbols
        out: dict[str, object] = {}
        for symbol, value in self.features.items():
            name = table.resolve(symbol) if table is not None else resolve(symbol)
            out[name] = dump_value(value, symbols=table)
        return out

    def __repr__(self) -> str:
        return f"FeatureStructure({self.as_dict()!r})"


def coerce(value: object, *, symbols: SymbolTable | None = None) -> object:
    """Normalize Python data into runtime values."""
    if value is TOP or value is None:
        return TOP
    if isinstance(value, (Atom, Variable, Disjunction, FeatureStructure)):
        return value
    if isinstance(value, str):
        if value.startswith("?") and len(value) > 1:
            return Variable(value[1:])
        return Atom.of(value) if symbols is None else Atom(symbols.intern(value))
    if isinstance(value, Mapping):
        return FeatureStructure.build(value, symbols=symbols)
    if isinstance(value, (list, tuple, set, frozenset)):
        return Disjunction(tuple(coerce(option, symbols=symbols) for option in value))
    if isinstance(value, bool | int | float):
        return Atom.of(str(value)) if symbols is None else Atom(symbols.intern(str(value)))
    raise TypeError(f"unsupported feature value: {value!r}")


def dump_value(value: object, *, symbols: SymbolTable | None = None) -> object:
    if value is TOP:
        return None
    if isinstance(value, Atom):
        return value.name if symbols is None else symbols.resolve(value.symbol)
    if isinstance(value, Variable):
        return f"?{value.name}"
    if isinstance(value, Disjunction):
        return [dump_value(option, symbols=symbols) for option in value.options]
    if isinstance(value, FeatureStructure):
        return value.as_dict(symbols=symbols)
    return value


# ---------------------------------------------------------------------------
# Unification
# ---------------------------------------------------------------------------

Bindings = dict[str, object]


def _deref(value: object, bindings: Bindings) -> object:
    while isinstance(value, Variable):
        bound = bindings.get(value.name)
        if bound is None:
            return value
        value = bound
    return value


def unify_values(left: object, right: object, bindings: Bindings) -> object | None:
    """Unify two values under ``bindings``; return the result value or None."""
    left = _deref(left, bindings)
    right = _deref(right, bindings)

    if left is TOP:
        return right
    if right is TOP:
        return left

    if isinstance(left, Variable) and isinstance(right, Variable):
        if left.name == right.name:
            return left
        bindings[right.name] = left
        return left

    if isinstance(left, Variable):
        bindings[left.name] = right
        return right
    if isinstance(right, Variable):
        bindings[right.name] = left
        return left

    if isinstance(left, Atom) and isinstance(right, Atom):
        return left if left.symbol == right.symbol else None

    if isinstance(left, FeatureStructure) and isinstance(right, FeatureStructure):
        unified = unify_structures(left, right, bindings)
        return unified

    if isinstance(left, Disjunction) or isinstance(right, Disjunction):
        return _unify_disjunction(left, right, bindings)

    return None


def _unify_disjunction(left: object, right: object, bindings: Bindings) -> object | None:
    left_options = left.options if isinstance(left, Disjunction) else (left,)
    right_options = right.options if isinstance(right, Disjunction) else (right,)
    results: list[object] = []
    for left_option in left_options:
        for right_option in right_options:
            trial: Bindings = dict(bindings)
            merged = unify_values(left_option, right_option, trial)
            if merged is not None:
                bindings.clear()
                bindings.update(trial)
                results.append(merged)
    if not results:
        return None
    if len(results) == 1:
        return results[0]
    # Preserve remaining alternatives as a narrowed disjunction.
    unique: list[object] = []
    for result in results:
        if result not in unique:
            unique.append(result)
    return Disjunction(tuple(unique)) if len(unique) > 1 else unique[0]


def unify_structures(
    left: FeatureStructure,
    right: FeatureStructure,
    bindings: Bindings | None = None,
) -> FeatureStructure | None:
    """Unify two feature structures. Returns a new structure or None."""
    env: Bindings = bindings if bindings is not None else {}
    merged: dict[int, object] = {}
    for symbol in left.features.keys() | right.features.keys():
        left_value = left.features.get(symbol, TOP)
        right_value = right.features.get(symbol, TOP)
        value = unify_values(left_value, right_value, env)
        if value is None:
            return None
        if value is not TOP:
            merged[symbol] = value
    if bindings is None:
        return FeatureStructure(merged)
    # Caller owns the environment; still publish merged features.
    return FeatureStructure(merged)


def unify(
    left: FeatureStructure,
    right: FeatureStructure,
    bindings: Bindings | None = None,
) -> tuple[FeatureStructure, Bindings] | None:
    """Unify and return ``(structure, bindings)`` or ``None`` on failure."""
    if left is right and not bindings:
        return left, {}
    env: Bindings = dict(bindings or {})
    result = unify_structures(left, right, env)
    if result is None:
        return None
    return result, env


def substitute(value: object, bindings: Bindings) -> object:
    """Apply a binding environment to a value, recursively."""
    value = _deref(value, bindings)
    if isinstance(value, FeatureStructure):
        return FeatureStructure(
            {symbol: substitute(nested, bindings) for symbol, nested in value.features.items()}
        )
    if isinstance(value, Disjunction):
        return Disjunction(tuple(substitute(option, bindings) for option in value.options))
    return value


def substitute_structure(structure: FeatureStructure, bindings: Bindings) -> FeatureStructure:
    return substitute(structure, bindings)  # type: ignore[return-value]


def variables_in(value: object) -> set[str]:
    value_kind = value
    if isinstance(value_kind, Variable):
        return {value_kind.name}
    if isinstance(value_kind, FeatureStructure):
        found: set[str] = set()
        for nested in value_kind.features.values():
            found |= variables_in(nested)
        return found
    if isinstance(value_kind, Disjunction):
        found = set()
        for option in value_kind.options:
            found |= variables_in(option)
        return found
    return set()


def structures_equal(left: FeatureStructure, right: FeatureStructure) -> bool:
    if left.features.keys() != right.features.keys():
        return False
    for symbol, left_value in left.features.items():
        right_value = right.features[symbol]
        if not values_equal(left_value, right_value):
            return False
    return True


def values_equal(left: object, right: object) -> bool:
    if left is TOP or right is TOP:
        return left is right
    if isinstance(left, Atom) and isinstance(right, Atom):
        return left.symbol == right.symbol
    if isinstance(left, Variable) and isinstance(right, Variable):
        return left.name == right.name
    if isinstance(left, FeatureStructure) and isinstance(right, FeatureStructure):
        return structures_equal(left, right)
    if isinstance(left, Disjunction) and isinstance(right, Disjunction):
        return set(left.options) == set(right.options)  # type: ignore[arg-type]
    return False
