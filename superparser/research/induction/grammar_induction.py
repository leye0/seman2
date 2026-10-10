"""Incremental grammar observations and conservative construction hypotheses.

The learner consumes parser results, never raw text.  It records selected-tree
productions, one-step structural macros, packed-forest alternatives and lexical
category vectors.  Hypotheses stay experimental and never mutate the parser's
grammar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from seman_parser.chart import ChartItem, ParseResult
from seman_parser.grammar import Grammar
from seman_parser.vector_chart import RuleDerivation


SCHEMA_VERSION = "grammar-hypotheses/0.1"
PROTECTED_FEATURES = frozenset(
    {"case", "gender", "inversion", "modal", "mood", "negation", "number", "person", "tense", "vform", "voice", "wh"}
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, value: Any) -> str:
    return prefix + "_" + sha256(_json(value).encode()).hexdigest()[:20]


def _constants(features: Any) -> tuple[tuple[str, Any], ...]:
    values = features.as_dict() if hasattr(features, "as_dict") else dict(features or {})
    return tuple(
        (name, value)
        for name, value in sorted(values.items())
        if name in PROTECTED_FEATURES and not (isinstance(value, str) and value.startswith("?"))
    )


@dataclass(frozen=True, slots=True)
class ProductionObservation:
    lhs: str
    rhs: tuple[str, ...]
    parent_features: tuple[tuple[str, Any], ...]
    child_features: tuple[tuple[tuple[str, Any], ...], ...]
    kind: str
    rule_ids: tuple[str, ...]

    @property
    def signature(self) -> tuple[str, tuple[str, ...], str]:
        return self.lhs, self.rhs, self.kind


@dataclass(frozen=True, slots=True)
class GapObservation:
    span: tuple[int, int]
    token_vectors: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class SentenceGrammarObservation:
    observation_id: str
    text: str
    completed: bool
    token_vectors: tuple[tuple[str, ...], ...]
    productions: tuple[ProductionObservation, ...]
    gaps: tuple[GapObservation, ...]
    forest_nodes: int
    forest_derivations: int
    alternative_rule_ids: tuple[str, ...]


def observe_parse(
    observation_id: str,
    result: ParseResult,
    grammar: Grammar,
) -> SentenceGrammarObservation:
    """Project a parser result into compact grammar-only observations."""
    vectors: list[tuple[str, ...]] = []
    for token in result.lattice.tokens:
        categories = {
            candidate.category
            for candidate in result.lattice.candidates
            if candidate.span_start <= token.start and candidate.span_end >= token.end
        }
        vectors.append(tuple(sorted(categories)))

    productions: dict[tuple[str, tuple[str, ...], str], ProductionObservation] = {}
    best = result.best()

    def visit(item: ChartItem) -> None:
        if item.children:
            direct = ProductionObservation(
                item.category,
                tuple(child.category for child in item.children),
                _constants(item.features),
                tuple(_constants(child.features) for child in item.children),
                "production",
                () if item.rule_id is None else (item.rule_id,),
            )
            productions.setdefault(direct.signature, direct)
            # Expand one internal child at a time.  The resulting sequence is
            # a lossless macro over rules actually present in the tree.
            for index, child in enumerate(item.children):
                if not child.children:
                    continue
                expanded = (*item.children[:index], *child.children, *item.children[index + 1 :])
                if not 2 <= len(expanded) <= 8:
                    continue
                rule_ids = tuple(
                    value for value in (item.rule_id, child.rule_id) if value is not None
                )
                macro = ProductionObservation(
                    item.category,
                    tuple(row.category for row in expanded),
                    _constants(item.features),
                    tuple(_constants(row.features) for row in expanded),
                    "macro",
                    rule_ids,
                )
                productions.setdefault(macro.signature, macro)
        for child in item.children:
            visit(child)

    if best is not None:
        visit(best)

    forests = tuple(_forests(result.shared_forest))
    alternative_rules: set[str] = set()
    forest_nodes = forest_derivations = 0
    covered: list[tuple[int, int]] = []
    for forest in forests:
        forest_nodes += len(forest.nodes)
        forest_derivations += forest.derivation_count
        for node in forest.nodes:
            if node.derivations and node.end > node.start:
                covered.append((node.start, node.end))
            for derivation in node.derivations:
                if isinstance(derivation, RuleDerivation):
                    alternative_rules.add(forest.compiled.rules[derivation.rule_index].rule.rule_id)

    gaps: list[GapObservation] = []
    if not result.completed:
        tokens = result.lattice.tokens
        uncovered = [
            token for token in tokens
            if not any(start <= token.start and end >= token.end and end - start > token.end - token.start for start, end in covered)
        ]
        run: list[Any] = []
        for token in (*uncovered, None):
            if token is not None and (not run or token.index == run[-1].index + 1):
                run.append(token)
                continue
            if run:
                gaps.append(GapObservation(
                    (run[0].start, run[-1].end),
                    tuple(vectors[row.index] for row in run),
                ))
            run = [] if token is None else [token]

    return SentenceGrammarObservation(
        observation_id,
        result.text,
        result.completed,
        tuple(vectors),
        tuple(sorted(productions.values(), key=lambda row: row.signature)),
        tuple(gaps),
        forest_nodes,
        forest_derivations,
        tuple(sorted(alternative_rules)),
    )


def _forests(value: Any) -> Iterable[Any]:
    if hasattr(value, "nodes") and hasattr(value, "compiled"):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _forests(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            yield from _forests(child)


@dataclass(slots=True)
class _Evidence:
    lhs: str
    rhs: tuple[str, ...]
    kind: str
    observation_ids: set[str] = field(default_factory=set)
    examples: list[str] = field(default_factory=list)
    parent_features: dict[str, Any] = field(default_factory=dict)
    child_features: list[dict[str, Any]] = field(default_factory=list)
    rule_ids: set[str] = field(default_factory=set)

    def add(self, observation: SentenceGrammarObservation, row: ProductionObservation) -> None:
        if observation.observation_id in self.observation_ids:
            return
        first = not self.observation_ids
        self.observation_ids.add(observation.observation_id)
        if len(self.examples) < 5:
            self.examples.append(observation.text)
        parent = dict(row.parent_features)
        children = [dict(value) for value in row.child_features]
        if first:
            self.parent_features = parent
            self.child_features = children
        else:
            self.parent_features = {
                key: value for key, value in self.parent_features.items() if parent.get(key) == value
            }
            for index, existing in enumerate(self.child_features):
                current = children[index] if index < len(children) else {}
                self.child_features[index] = {
                    key: value for key, value in existing.items() if current.get(key) == value
                }
        self.rule_ids.update(row.rule_ids)


@dataclass(frozen=True, slots=True)
class GrammarHypothesis:
    hypothesis_id: str
    lhs: str
    rhs: tuple[str, ...]
    classification: str
    support: int
    validation_support: int
    feature_constraints: Mapping[str, Any]
    examples: tuple[str, ...]
    rule_ids: tuple[str, ...]
    compression_gain: int
    counterexamples: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "lhs": {"category": self.lhs, "features": dict(self.feature_constraints)},
            "rhs": [{"category": category} for category in self.rhs],
            "classification": self.classification,
            "support": self.support,
            "validation_support": self.validation_support,
            "examples": list(self.examples),
            "counterexamples": list(self.counterexamples),
            "source_rule_ids": list(self.rule_ids),
            "estimated_compression_gain": self.compression_gain,
        }


class GrammarHypothesisRegistry:
    """Incremental, JSON-persistable evidence registry."""

    def __init__(self, grammar: Grammar) -> None:
        self.grammar = grammar
        self._known = {
            (rule.lhs.category, tuple(symbol.category for symbol in rule.rhs))
            for rule in grammar
        }
        self._evidence: dict[tuple[str, tuple[str, ...], str], _Evidence] = {}
        self._validation: dict[tuple[str, tuple[str, ...], str], set[str]] = {}
        self._counterexamples: dict[tuple[str, tuple[str, ...], str], list[str]] = {}
        self.ingested_ids: set[str] = set()
        self.gap_observations: list[tuple[str, GapObservation]] = []

    def ingest(self, observation: SentenceGrammarObservation, *, validation: bool = False) -> None:
        target_ids = self.ingested_ids
        marker = ("validation:" if validation else "observation:") + observation.observation_id
        if marker in target_ids:
            raise ValueError(f"duplicate observation: {marker}")
        target_ids.add(marker)
        for row in observation.productions:
            if validation:
                self._validation.setdefault(row.signature, set()).add(observation.observation_id)
                for signature in self._evidence:
                    lhs, rhs, _kind = signature
                    if rhs == row.rhs and lhs != row.lhs:
                        values = self._counterexamples.setdefault(signature, [])
                        if observation.text not in values and len(values) < 5:
                            values.append(observation.text)
                continue
            evidence = self._evidence.get(row.signature)
            if evidence is None:
                evidence = _Evidence(row.lhs, row.rhs, row.kind)
                self._evidence[row.signature] = evidence
            evidence.add(observation, row)
        if not validation:
            self.gap_observations.extend((observation.observation_id, gap) for gap in observation.gaps)

    def hypotheses(self, *, min_support: int = 3) -> tuple[GrammarHypothesis, ...]:
        rows: list[GrammarHypothesis] = []
        for signature, evidence in self._evidence.items():
            support = len(evidence.observation_ids)
            if support < min_support or len(evidence.rhs) < 2:
                continue
            direct = (evidence.lhs, evidence.rhs) in self._known
            classification = "known-construction" if direct else "macro"
            # Macros here come from expanding a witnessed parser subtree and
            # are therefore explicitly not advertised as new grammar rules.
            feature_constraints = dict(evidence.parent_features)
            body = [evidence.lhs, evidence.rhs, classification, sorted(feature_constraints.items())]
            rows.append(GrammarHypothesis(
                _stable_id("grammar-hypothesis", body),
                evidence.lhs,
                evidence.rhs,
                classification,
                support,
                len(self._validation.get(signature, ())),
                feature_constraints,
                tuple(evidence.examples),
                tuple(sorted(evidence.rule_ids)),
                max(0, (support - 1) * max(1, len(evidence.rhs) - 1) - len(evidence.rhs)),
                tuple(self._counterexamples.get(signature, ())),
            ))
        priority = {"potential-new": 0, "macro": 1, "known-construction": 2}
        return tuple(sorted(
            rows,
            key=lambda row: (
                priority[row.classification],
                -int(row.validation_support > 0),
                -row.compression_gain,
                -row.support,
                row.hypothesis_id,
            ),
        ))

    def as_dict(self) -> dict[str, Any]:
        evidence = []
        for key, row in sorted(self._evidence.items()):
            evidence.append({
                "lhs": row.lhs,
                "rhs": list(row.rhs),
                "kind": row.kind,
                "observation_ids": sorted(row.observation_ids),
                "examples": list(row.examples),
                "parent_features": row.parent_features,
                "child_features": row.child_features,
                "rule_ids": sorted(row.rule_ids),
                "validation_ids": sorted(self._validation.get(key, ())),
                "counterexamples": list(self._counterexamples.get(key, ())),
            })
        return {
            "schema_version": SCHEMA_VERSION,
            "ingested_ids": sorted(self.ingested_ids),
            "evidence": evidence,
            "gaps": [
                {
                    "observation_id": observation_id,
                    "span": list(gap.span),
                    "token_vectors": [list(vector) for vector in gap.token_vectors],
                }
                for observation_id, gap in self.gap_observations
            ],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, grammar: Grammar) -> "GrammarHypothesisRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported grammar hypothesis registry")
        registry = cls(grammar)
        registry.ingested_ids = set(payload.get("ingested_ids", ()))
        for value in payload.get("evidence", ()):
            row = _Evidence(str(value["lhs"]), tuple(value["rhs"]), str(value["kind"]))
            row.observation_ids = set(value["observation_ids"])
            row.examples = list(value["examples"])
            row.parent_features = dict(value["parent_features"])
            row.child_features = [dict(child) for child in value["child_features"]]
            row.rule_ids = set(value["rule_ids"])
            key = (row.lhs, row.rhs, row.kind)
            registry._evidence[key] = row
            registry._validation[key] = set(value.get("validation_ids", ()))
            registry._counterexamples[key] = list(value.get("counterexamples", ()))
        registry.gap_observations = [
            (
                str(value["observation_id"]),
                GapObservation(
                    tuple(int(number) for number in value["span"]),
                    tuple(tuple(str(category) for category in vector) for vector in value["token_vectors"]),
                ),
            )
            for value in payload.get("gaps", ())
        ]
        return registry


__all__ = [
    "GapObservation",
    "GrammarHypothesis",
    "GrammarHypothesisRegistry",
    "ProductionObservation",
    "SentenceGrammarObservation",
    "observe_parse",
]
