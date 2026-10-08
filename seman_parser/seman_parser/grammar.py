"""Declarative grammar rules.

A rule is data: RHS pattern, LHS output, feature constraints, variable
bindings and a semantic composition recipe. The runtime never special-cases
a construction; it matches, unifies and expands whatever rules it is given.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .features import FeatureStructure, Variable
from .symbols import intern


@dataclass(frozen=True, slots=True)
class SemanticAction:
    """One semantic composition step carried by a rule.

    ``kind`` is a generic operation name loaded from data, not a coded
    construction: ``link``, ``introduce``, ``copy``, ``compose``.
    """

    kind: str
    args: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, **dict(self.args)}


@dataclass(frozen=True, slots=True)
class RuleSymbol:
    """One RHS or LHS symbol: category, feature constraints, handle exports."""

    category: str
    features: FeatureStructure = field(default_factory=FeatureStructure.empty)
    # child handle name -> rule-level name used by semantic actions
    exports: Mapping[str, str] = field(default_factory=dict)

    @property
    def category_id(self) -> int:
        return intern(self.category)

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "features": self.features.as_dict(),
            "exports": dict(self.exports),
        }


@dataclass(frozen=True, slots=True)
class GrammarRule:
    """A single construction expressed as data."""

    rule_id: str
    rhs: tuple[RuleSymbol, ...]
    lhs: RuleSymbol
    semantic: tuple[SemanticAction, ...] = ()
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
            "semantic": [action.as_dict() for action in self.semantic],
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


def _parse_action(raw: Mapping[str, Any]) -> SemanticAction:
    payload = dict(raw)
    # Accept both {kind: link, ...} and the blueprint's nested {link: {...}}.
    if "kind" in payload:
        kind = str(payload.pop("kind"))
        return SemanticAction(kind=kind, args=payload)
    if "op" in payload:
        kind = str(payload.pop("op"))
        return SemanticAction(kind=kind, args=payload)
    if len(payload) == 1:
        kind, body = next(iter(payload.items()))
        if isinstance(body, Mapping):
            return SemanticAction(kind=str(kind), args=dict(body))
        return SemanticAction(kind=str(kind), args={"value": body})
    return SemanticAction(kind="copy", args=payload)


def parse_rule(raw: Mapping[str, Any]) -> GrammarRule:
    return GrammarRule(
        rule_id=str(raw["id"]),
        rhs=tuple(_parse_symbol(row) for row in raw.get("rhs", ())),
        lhs=_parse_symbol(raw["lhs"]),
        semantic=tuple(_parse_action(row) for row in raw.get("semantic", ())),
        score=float(raw.get("score", 0.0)),
        provenance=dict(raw.get("provenance", {})),
    )


class Grammar:
    """Indexed collection of declarative rules."""

    __slots__ = ("rules", "_by_first", "_by_id", "_by_arity")

    def __init__(self, rules: Iterable[GrammarRule] = ()) -> None:
        self.rules: tuple[GrammarRule, ...] = tuple(rules)
        self._by_id: dict[str, GrammarRule] = {}
        self._by_first: dict[int, list[GrammarRule]] = {}
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

    def candidates_for_first(self, category: str | int) -> Sequence[GrammarRule]:
        key = intern(category) if isinstance(category, str) else category
        return self._by_first.get(key, ())

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
