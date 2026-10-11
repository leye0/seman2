"""Declarative grammar rules.

A rule is data: RHS pattern, LHS output, feature constraints and variable
bindings. Semantic recipes are loaded separately by ``semantic_rules``. The runtime never special-cases
a construction; it matches, unifies and expands whatever rules it is given.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .features import Atom, FeatureStructure, Variable
from .symbols import intern


@dataclass(frozen=True, slots=True)
class RuleSymbol:
    """One RHS or LHS symbol: category, feature constraints, handle exports."""

    category: str
    features: FeatureStructure = field(default_factory=FeatureStructure.empty)
    # child handle name -> rule-level name used by semantic actions
    exports: Mapping[str, str] = field(default_factory=dict)
    # Features listed here must be positively established by the child
    # derivation.  Ordinary feature constraints remain open-world and may be
    # instantiated through unification.
    requires: tuple[str, ...] = ()

    @property
    def category_id(self) -> int:
        return intern(self.category)

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "features": self.features.as_dict(),
            "exports": dict(self.exports),
            "requires": list(self.requires),
        }


@dataclass(frozen=True, slots=True)
class GrammarRule:
    """A single construction expressed as data."""

    rule_id: str
    rhs: tuple[RuleSymbol, ...]
    lhs: RuleSymbol
    score: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def arity(self) -> int:
        return len(self.rhs)

    @property
    def first_category(self) -> str:
        return self.rhs[0].category if self.rhs else self.lhs.category

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.rule_id,
            "rhs": [symbol.as_dict() for symbol in self.rhs],
            "lhs": self.lhs.as_dict(),
            "score": self.score,
            "provenance": dict(self.provenance),
        }


# Keys under ``bind`` that denote semantic handles rather than features.
# The set is intentionally tiny; everything else is treated as a feature
# constraint name, so new linguistic features need no engine change.
HANDLE_KEYS = frozenset({"referent", "event", "head", "predicate", "handle"})


def _parse_symbol(raw: Mapping[str, Any]) -> RuleSymbol:
    features_raw = dict(raw.get("features", {}))
    exports = {str(key): str(value) for key, value in dict(raw.get("exports", raw.get("export", {}))).items()}

    # ``bind`` shorthand from the blueprint: feature variables and handle
    # aliases in one mapping, e.g. {number: ?n, referent: ?subject}.
    for key, value in dict(raw.get("bind", {})).items():
        key_s = str(key)
        value_s = str(value)
        if key_s in HANDLE_KEYS or value_s.startswith("?") and key_s not in features_raw and not _looks_like_agreement(key_s):
            handle_name = value_s[1:] if value_s.startswith("?") else value_s
            exports[key_s] = handle_name
        else:
            features_raw[key_s] = value_s

    return RuleSymbol(
        category=str(raw["category"]),
        features=FeatureStructure.build(features_raw),
        exports=exports,
        requires=tuple(str(name) for name in raw.get("requires", ())),
    )


def _looks_like_agreement(name: str) -> bool:
    return name.lower() in {
        "number",
        "person",
        "case",
        "gender",
        "tense",
        "aspect",
        "vform",
        "wh",
        "gap",
        "mass",
        "sort",
        "status",
        "modal",
        "negation",
        "agr",
    }


def parse_rule(raw: Mapping[str, Any]) -> GrammarRule:
    return GrammarRule(
        rule_id=str(raw["id"]),
        rhs=tuple(_parse_symbol(row) for row in raw.get("rhs", ())),
        lhs=_parse_symbol(raw["lhs"]),
        score=float(raw.get("score", 0.0)),
        provenance=dict(raw.get("provenance", {})),
    )


class Grammar:
    """Indexed collection of declarative rules."""

    __slots__ = ("rules", "_by_first", "_by_first_atoms", "_by_id", "_by_arity")

    def __init__(self, rules: Iterable[GrammarRule] = ()) -> None:
        self.rules: tuple[GrammarRule, ...] = tuple(rules)
        self._by_id: dict[str, GrammarRule] = {}
        self._by_first: dict[int, list[GrammarRule]] = {}
        # Memoized refinement of ``_by_first`` by the atomic features found
        # on an item.  The cache is populated alongside parsing, rather than
        # computing and interning feature-structure keys in the hot path.
        self._by_first_atoms: dict[
            tuple[int, tuple[tuple[int, int], ...]],
            tuple[GrammarRule, ...],
        ] = {}
        self._by_arity: dict[int, list[GrammarRule]] = {}
        for rule in self.rules:
            self._by_id[rule.rule_id] = rule
            key = intern(rule.first_category)
            self._by_first.setdefault(key, []).append(rule)
            self._by_arity.setdefault(rule.arity, []).append(rule)

    def by_id(self, rule_id: str) -> GrammarRule:
        try:
            return self._by_id[rule_id]
        except KeyError:
            raise KeyError(f"unknown rule: {rule_id!r}") from None

    def candidates_for_first(
        self,
        category: str | int,
        features: FeatureStructure | None = None,
    ) -> Sequence[GrammarRule]:
        key = intern(category) if isinstance(category, str) else category
        candidates = self._by_first.get(key, ())
        if features is None or not candidates:
            return candidates
        atoms = tuple(
            (feature, value.symbol)
            for feature, value in features.items()
            if isinstance(value, Atom)
        )
        if not atoms:
            return candidates
        cache_key = (key, atoms)
        cached = self._by_first_atoms.get(cache_key)
        if cached is not None:
            return cached
        compatible = tuple(
            rule
            for rule in candidates
            if not _has_atomic_conflict(rule.rhs[0].features, atoms)
        )
        self._by_first_atoms[cache_key] = compatible
        return compatible

    def candidates_for_arity(self, arity: int) -> Sequence[GrammarRule]:
        return self._by_arity.get(arity, ())

    def rules_waiting_for(self, category: str | int, *, after: int = 1) -> Sequence[tuple[GrammarRule, int]]:
        """``(rule, dot)`` pairs where rule.rhs[dot] matches ``category``.

        ``after`` filters to rules that have already matched ``after`` symbols
        when set to a value > 0; pass 0 to include rule starts.
        """
        key = intern(category) if isinstance(category, str) else category
        out: list[tuple[GrammarRule, int]] = []
        for rule in self.rules:
            for index, symbol in enumerate(rule.rhs):
                if index < after:
                    continue
                if symbol.category_id == key:
                    out.append((rule, index))
        return out

    def __len__(self) -> int:
        return len(self.rules)

    def __iter__(self):
        return iter(self.rules)


def _has_atomic_conflict(
    constraints: FeatureStructure,
    item_atoms: tuple[tuple[int, int], ...],
) -> bool:
    """Cheap, safe pre-check for first-symbol feature conflicts.

    Only unequal atom/atom pairs are rejected.  Variables, disjunctions and
    missing values still go through the full unifier.
    """
    for feature, item_symbol in item_atoms:
        constraint = constraints.features.get(feature)
        if isinstance(constraint, Atom) and constraint.symbol != item_symbol:
            return True
    return False


def load_grammar(path: str | Path) -> Grammar:
    """Load rules from a JSONL file, one rule object per line."""
    path = Path(path)
    rules: list[GrammarRule] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid rule JSON: {exc}") from exc
            rules.append(parse_rule(raw))
    return Grammar(rules)


def load_grammar_rows(rows: Iterable[Mapping[str, Any]]) -> Grammar:
    return Grammar(parse_rule(row) for row in rows)
