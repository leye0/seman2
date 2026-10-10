"""Experimental grammar induction from holes in an incomplete parse forest.

This module deliberately does not receive the hidden rules.  It observes
stalled dotted rules and adjacent constituents, proposes small productions,
and evaluates them by temporarily constructing a normal :class:`Grammar`.
The induced rules have no semantic actions: this experiment evaluates syntax
only and must not pretend to have recovered semantic composition.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from hashlib import sha1
import signal
from time import perf_counter
from typing import Any, Iterable, Iterator, Mapping, Sequence

from seman_parser import FeatureStructure, Grammar, GrammarRule, Parser, ParserResources, RuleSymbol
from seman_parser.chart import ParseResult
from seman_parser.symbols import resolve


PROTECTED_FEATURES = frozenset(
    {"case", "gap", "mood", "negation", "number", "person", "vform", "voice", "wh"}
)


@dataclass(frozen=True, slots=True)
class CandidateKey:
    lhs: str
    rhs: tuple[str, ...]

    def text(self) -> str:
        return f"{self.lhs} -> {' '.join(self.rhs)}"


@dataclass(slots=True)
class CandidateEvidence:
    key: CandidateKey
    observation_ids: set[str] = field(default_factory=set)
    examples: list[str] = field(default_factory=list)
    sources: Counter[str] = field(default_factory=Counter)
    lhs_features: Counter[tuple[tuple[str, Any], ...]] = field(default_factory=Counter)
    child_features: list[Counter[tuple[tuple[str, Any], ...]]] = field(default_factory=list)

    @property
    def support(self) -> int:
        return len(self.observation_ids)

    def add(
        self,
        observation_id: str,
        text: str,
        source: str,
        lhs_features: Mapping[str, Any],
        children: Sequence[Mapping[str, Any]],
    ) -> None:
        if observation_id in self.observation_ids:
            self.sources[source] += 1
            return
        self.observation_ids.add(observation_id)
        if len(self.examples) < 5:
            self.examples.append(text)
        self.sources[source] += 1
        self.lhs_features[_constants(lhs_features)] += 1
        while len(self.child_features) < len(children):
            self.child_features.append(Counter())
        for counter, values in zip(self.child_features, children):
            counter[_constants(values)] += 1


@dataclass(frozen=True, slots=True)
class SweepConfig:
    method: str
    max_pattern: int
    min_support: int
    feature_mode: str
    max_candidates: int
    generalization_depth: int = 1

    @property
    def name(self) -> str:
        return (
            f"{self.method}-l{self.max_pattern}-s{self.min_support}-"
            f"f{self.feature_mode}-n{self.max_candidates}-g{self.generalization_depth}"
        )


def _constants(values: Mapping[str, Any] | Any) -> tuple[tuple[str, Any], ...]:
    raw = values.as_dict() if hasattr(values, "as_dict") else dict(values or {})
    return tuple(
        (name, value)
        for name, value in sorted(raw.items())
        if name in PROTECTED_FEATURES
        and isinstance(value, (str, int, float, bool))
        and not (isinstance(value, str) and value.startswith("?"))
    )


def _forests(shared: Any) -> Iterator[Any]:
    if shared is None:
        return
    if hasattr(shared, "nodes") and hasattr(shared, "partials"):
        yield shared
        return
    if isinstance(shared, Mapping):
        assembly = shared.get("assembly")
        if assembly is not None:
            yield from _forests(assembly)
        for segment in shared.get("segments", ()):
            yield from _forests(getattr(segment, "shared_forest", None))


def _node_feature_rows(forest: Any, node: Any) -> list[Mapping[str, Any]]:
    """Return only grammar-observable interfaces, never materialized trees."""
    rows: list[Mapping[str, Any]] = []
    for derivation in node.derivations:
        rule_index = getattr(derivation, "rule_index", None)
        if rule_index is not None:
            rows.append(forest.compiled.rules[rule_index].rule.lhs.features.as_dict())
            continue
        for candidate in getattr(derivation, "candidates", ()):
            rows.append(candidate.features.as_dict())
    return rows or [{}]


def _chains(
    forest: Any,
    start: int,
    *,
    max_pattern: int,
    max_paths: int = 128,
) -> Iterator[tuple[Any, ...]]:
    """Enumerate compact adjacent-constituent paths with aggressive packing."""
    by_start: dict[int, list[Any]] = defaultdict(list)
    for node in forest.nodes:
        by_start[node.start].append(node)
    for nodes in by_start.values():
        # One span per category is sufficient for grammatical interfaces;
        # internal derivations remain packed in the node.
        best: dict[tuple[int, str], Any] = {}
        for node in nodes:
            best[(node.end, node.category)] = node
        nodes[:] = sorted(best.values(), key=lambda row: (row.end, row.category))

    emitted = 0

    def walk(position: int, path: tuple[Any, ...]) -> Iterator[tuple[Any, ...]]:
        nonlocal emitted
        if path:
            emitted += 1
            yield path
            if emitted >= max_paths:
                return
        if len(path) >= max_pattern:
            return
        for node in by_start.get(position, ()):
            if node.end <= position:
                continue
            yield from walk(forest._next_start(node.end), (*path, node))
            if emitted >= max_paths:
                return

    yield from walk(start, ())


def observe_holes(
    observation_id: str,
    result: ParseResult,
    *,
    max_pattern: int,
    method: str = "hybrid",
    generalization_depth: int = 1,
) -> tuple[CandidateEvidence, ...]:
    """Propose productions from stalled expectations and uncovered suffixes.

    No grammar other than the one which produced ``result`` is consulted.
    "waiting" uses a dotted rule's missing symbol.  "bridge" notices that a
    later expected constituent exists and proposes extending the immediately
    preceding constituent across the gap.  "suffix" repairs analyses which
    cover a prefix but leave adjacent material unexplained.
    """
    rows: dict[CandidateKey, CandidateEvidence] = {}

    def offer(lhs: str, nodes: Sequence[Any], source: str, lhs_features: Mapping[str, Any]) -> None:
        rhs = tuple(node.category for node in nodes)
        if not 2 <= len(rhs) <= max_pattern or rhs == (lhs,):
            return
        # These patterns only wrap material already recognized.  Punctuation
        # alone and repeated self chains are high-volume non-explanations.
        if all(category in {"COMMA", "PUNCT"} for category in rhs):
            return
        key = CandidateKey(lhs, rhs)
        evidence = rows.setdefault(key, CandidateEvidence(key))
        child_values = [_node_feature_rows(current_forest, node)[0] for node in nodes]
        evidence.add(observation_id, result.text, source, lhs_features, child_values)

    for current_forest in _forests(result.shared_forest):
        # Directly fill categories for which a dotted rule is waiting.
        if method in {"waiting", "hybrid", "bridge"}:
            for (position, expected_id), partial_ids in current_forest.waiting.items():
                expected = resolve(expected_id)
                root_end = len(current_forest.text.rstrip().rstrip(".!?;:,\"'"))
                if method in {"waiting", "hybrid"}:
                    for path in _chains(current_forest, position, max_pattern=max_pattern, max_paths=32):
                        if len(path) >= 2 and current_forest._next_start(path[-1].end) >= root_end:
                            offer(expected, path, "waiting", {})
                if method not in {"hybrid", "bridge"}:
                    continue
                # If the expected category starts later, extend the last
                # consumed child across the intervening material.  This is
                # the generic signal for NP + relative-clause attachment.
                later = sorted(set(
                    node.start for node in current_forest.nodes
                    if node.category_id == expected_id and node.start > position
                ))[:generalization_depth]
                for partial_id in partial_ids[:16]:
                    partial = current_forest.partials[partial_id]
                    rule = current_forest.compiled.rules[partial.rule_index].rule
                    if not partial.derivations or partial.dot == 0:
                        continue
                    previous_symbol = rule.rhs[partial.dot - 1]
                    for derivation in partial.derivations[:8]:
                        child = current_forest.nodes[derivation.child_id]
                        for target in later:
                            if target <= position:
                                continue
                            # Prefer an already packed constituent spanning
                            # the complete gap.  Enumerating all internal
                            # decompositions merely rediscovers ambiguity.
                            bridges = {
                                node.category: node for node in current_forest.nodes
                                if node.start == position
                                and current_forest._next_start(node.end) == target
                            }
                            for middle in bridges.values():
                                offer(
                                    previous_symbol.category,
                                    (child, middle),
                                    "bridge",
                                    previous_symbol.features.as_dict(),
                                )
                            # If the gap has no single constituent, retain a
                            # few shortest packed paths (e.g. COORD + NP).
                            paths = [
                                path for path in _chains(
                                    current_forest, position,
                                    max_pattern=max_pattern - 1, max_paths=64,
                                )
                                if path and current_forest._next_start(path[-1].end) == target
                            ]
                            paths.sort(key=lambda path: (
                                -int(path[-1].category == previous_symbol.category),
                                len(path),
                                tuple(node.category for node in path),
                            ))
                            seen_shapes: set[tuple[str, ...]] = set()
                            for path in paths:
                                shape = tuple(node.category for node in path)
                                if shape in seen_shapes:
                                    continue
                                seen_shapes.add(shape)
                                offer(
                                    previous_symbol.category,
                                    (child, *path),
                                    "bridge-path",
                                    previous_symbol.features.as_dict(),
                                )
                                if len(seen_shapes) >= 8 * generalization_depth:
                                    break

        if method in {"suffix", "hybrid"}:
            root_end = len(current_forest.text.rstrip().rstrip(".!?;:,\"'"))
            prefixes = sorted(
                (node for node in current_forest.nodes if node.start == 0 and node.end < root_end),
                key=lambda node: node.end,
                reverse=True,
            )[:24]
            for prefix in prefixes:
                position = current_forest._next_start(prefix.end)
                tails = {
                    node.category: node for node in current_forest.nodes
                    if node.start == position
                    and current_forest._next_start(node.end) >= root_end
                }
                for tail in tails.values():
                    offer(prefix.category, (prefix, tail), "suffix", {})

    return tuple(rows.values())


def aggregate_observations(
    observations: Iterable[tuple[str, ParseResult]],
    *,
    max_pattern: int,
    method: str,
    generalization_depth: int = 1,
) -> dict[CandidateKey, CandidateEvidence]:
    combined: dict[CandidateKey, CandidateEvidence] = {}
    for observation_id, result in observations:
        for row in observe_holes(
            observation_id, result, max_pattern=max_pattern, method=method,
            generalization_depth=generalization_depth,
        ):
            target = combined.setdefault(row.key, CandidateEvidence(row.key))
            for index, text in enumerate(row.examples):
                target.add(
                    next(iter(row.observation_ids)) if len(row.observation_ids) == 1 else f"{observation_id}:{index}",
                    text,
                    row.sources.most_common(1)[0][0],
                    dict(row.lhs_features.most_common(1)[0][0]) if row.lhs_features else {},
                    [dict(counter.most_common(1)[0][0]) for counter in row.child_features],
                )
    return combined


def rank_candidates(
    evidence: Mapping[CandidateKey, CandidateEvidence],
    grammar: Grammar,
    config: SweepConfig,
) -> tuple[CandidateEvidence, ...]:
    known = {
        CandidateKey(rule.lhs.category, tuple(symbol.category for symbol in rule.rhs))
        for rule in grammar
    }
    productivity = Counter(rule.lhs.category for rule in grammar)
    rows = [
        row for key, row in evidence.items()
        if key not in known
        and row.support >= config.min_support
        and len(key.rhs) <= config.max_pattern
        # A lexical-only category is not a plausible newly learned phrase
        # interface.  This removes AUX -> AUX ... style artifacts without
        # naming any construction family.
        and productivity[key.lhs] > 0
    ]
    def priority(row: CandidateEvidence) -> tuple[Any, ...]:
        recursive = int(bool(row.key.rhs) and row.key.rhs[0] == row.key.lhs)
        repeated = sum(category == row.key.lhs for category in row.key.rhs[1:])
        structural = (
            100 * row.support
            + min(20, productivity[row.key.lhs])
            + 15 * recursive
            + 10 * int(row.sources.get("bridge-path", 0) > 0)
            + 6 * int(row.sources.get("bridge", 0) > 0)
            + 4 * int(row.sources.get("suffix", 0) > 0)
            + 25 * int(
                len(row.key.rhs) > 2
                and row.key.rhs[0] == row.key.lhs
                and row.key.rhs[-1] == row.key.lhs
            )
            - 8 * repeated
        )
        return (-structural, len(row.key.rhs), row.key.lhs, row.key.rhs)

    rows.sort(key=priority)
    return tuple(rows[: config.max_candidates])


def induced_rule(row: CandidateEvidence, feature_mode: str, index: int) -> GrammarRule:
    lhs_values: Mapping[str, Any] = {}
    child_values: list[Mapping[str, Any]] = [{} for _ in row.key.rhs]
    if feature_mode == "protected" and row.lhs_features:
        lhs_values = dict(row.lhs_features.most_common(1)[0][0])
        child_values = [
            dict(counter.most_common(1)[0][0]) if counter else {}
            for counter in row.child_features
        ]
    digest = sha1(row.key.text().encode()).hexdigest()[:10]
    return GrammarRule(
        rule_id=f"induced_{index}_{digest}",
        rhs=tuple(
            RuleSymbol(category, FeatureStructure.build(values))
            for category, values in zip(row.key.rhs, child_values)
        ),
        lhs=RuleSymbol(row.key.lhs, FeatureStructure.build(lhs_values)),
        semantic=(),
        score=0.0,
        provenance={"source": "masked-grammar-induction", "syntax_only": True},
    )


def parser_with_candidates(
    base: ParserResources,
    rows: Sequence[CandidateEvidence],
    *,
    feature_mode: str,
) -> Parser:
    additions = tuple(induced_rule(row, feature_mode, index) for index, row in enumerate(rows))
    resources = ParserResources(
        Grammar((*base.grammar.rules, *additions)), base.lexicon, base.types,
        {**dict(base.metadata), "experimental_induced_rules": len(additions)},
    )
    return Parser(resources, cache_size=0)


def evaluate_candidates(
    base: ParserResources,
    rows: Sequence[CandidateEvidence],
    cases: Sequence[Any],
    *,
    feature_mode: str,
    baseline_completed: Mapping[int, bool],
    reference_completed: Mapping[int, bool],
    budget_seconds: float,
) -> dict[str, Any]:
    parser = parser_with_candidates(base, rows, feature_mode=feature_mode)
    started = perf_counter()
    completed = recovered = false_positive = induced_best = induced_forest = 0
    details: list[dict[str, Any]] = []
    for case in cases:
        remaining = budget_seconds - (perf_counter() - started)
        if remaining <= 0:
            break
        previous_handler = signal.getsignal(signal.SIGALRM)
        try:
            signal.signal(signal.SIGALRM, lambda _signum, _frame: (_ for _ in ()).throw(TimeoutError()))
            signal.setitimer(signal.ITIMER_REAL, min(1.0, remaining))
            result = parser.parse(case.text).result
        except TimeoutError:
            details.append({
                "index": case.index, "text": case.text, "completed": False, "recovered": False,
                "uses_induced": False, "induced_in_forest": False, "timeout": True,
            })
            continue
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
        ok = bool(result.completed)
        completed += int(ok)
        recovered += int(ok and not baseline_completed.get(case.index, False) and reference_completed.get(case.index, False))
        false_positive += int(ok and not reference_completed.get(case.index, False))
        best = result.best()
        uses_induced = bool(best and any(
            (item.rule_id or "").startswith("induced_") for item in _walk(best)
        ))
        forest_uses_induced = any(
            forest.compiled.rules[derivation.rule_index].rule.rule_id.startswith("induced_")
            for forest in _forests(result.shared_forest)
            for node in forest.nodes
            for derivation in node.derivations
            if getattr(derivation, "rule_index", None) is not None
        )
        induced_best += int(uses_induced)
        induced_forest += int(forest_uses_induced)
        details.append({
            "index": case.index,
            "text": case.text,
            "completed": ok,
            "recovered": bool(ok and not baseline_completed.get(case.index, False) and reference_completed.get(case.index, False)),
            "uses_induced": uses_induced,
            "induced_in_forest": forest_uses_induced,
        })
    return {
        "evaluated": len(details),
        "completed": completed,
        "recovered": recovered,
        "false_positives": false_positive,
        "induced_in_best": induced_best,
        "induced_in_forest": induced_forest,
        "elapsed_ms": round((perf_counter() - started) * 1000, 3),
        "details": details,
    }


def _walk(item: Any) -> Iterator[Any]:
    yield item
    for child in item.children:
        yield from _walk(child)


__all__ = [
    "CandidateEvidence", "CandidateKey", "SweepConfig", "aggregate_observations",
    "evaluate_candidates", "induced_rule", "observe_holes", "parser_with_candidates",
    "rank_candidates",
]
