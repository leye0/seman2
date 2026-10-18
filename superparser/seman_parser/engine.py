"""Top-level parse pipeline.

    text -> lattice -> chart -> packed forest -> semantic alternatives

Parse is local to the string; discourse context is layered on later and
never destroys the analyses produced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

from .chart import ParseResult
from .grammar import Grammar, load_grammar, load_grammar_rows
from .dialogue import dialogue_lattice
from .complexity_routing import ComplexityPolicy, RoutingDecision, StructuralRiskRouter
from .lexicon import Lexicon, load_lexicon, load_lexicon_rows
from .perf import LRU
from .segmentation import (
    LexicalCandidate, LexicalLattice, Token, _candidate_from_sense,
    build_lattice, tokenize,
)
from .vector_chart import SegmentInterface, VectorGrammar


class _LazyTypes:
    """Compatibility proxy: semantic ontology is not loaded by parsing."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._value = None

    def _load(self):
        if self._value is None:
            from .types import load_types

            self._value = load_types(_read_json_rows(self.path))
        return self._value

    def __getattr__(self, name: str):
        return getattr(self._load(), name)

    def __len__(self) -> int:
        return len(self._load())

    def __iter__(self):
        return iter(self._load())


@dataclass
class ParserResources:
    """Everything the engine knows — all of it data."""

    grammar: Grammar
    lexicon: Lexicon
    types: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)
    _semantic_rules_cache: Mapping[str, Any] | None = field(default=None, init=False, repr=False)

    def semantic_rules(self) -> Mapping[str, Any]:
        if self._semantic_rules_cache is None:
            from .semantic_rules import load_semantic_rules

            path = self.metadata.get("semantic_rules")
            actions = load_semantic_rules(path) if path else {}
            extra = self.metadata.get("dialogue_semantic_rules")
            if extra:
                actions = {**actions, **load_semantic_rules(extra)}
            self._semantic_rules_cache = actions
        return self._semantic_rules_cache

    @classmethod
    def from_dir(
        cls,
        directory: str | Path,
        *,
        wordnet_dict: str | Path | None = None,
    ) -> "ParserResources":
        directory = Path(directory)
        semantic_path = directory / "semantic_rules.jsonl"
        if not semantic_path.exists():
            # Read-only migration path for older resource directories whose
            # recipes are still embedded in grammar.jsonl.
            semantic_path = directory / "grammar.jsonl"
        return cls(
            grammar=load_grammar(directory / "grammar.jsonl"),
            lexicon=load_lexicon(
                directory / "function_words.jsonl",
                wordnet_dict=wordnet_dict or discover_wordnet(directory),
                supplemental_paths=(directory / "syntax_lexicon.jsonl",),
                # Valency-bearing senses are not reliably ordered first in
                # WordNet.  Two senses lose productive alternations such as
                # flood/visit/endure (transitive and intransitive), turning
                # grammatical clauses into coverage failures.  Eight keeps
                # the lexical search bounded while retaining those frames.
                max_senses=8,
            ),
            types=_LazyTypes(directory / "types.json"),
            metadata={
                "source": str(directory),
                "semantic_rules": str(semantic_path),
                "dialogue_rules": str(directory / "dialogue_grammar.jsonl"),
                "dialogue_semantic_rules": str(directory / "dialogue_semantic_rules.jsonl"),
            },
        )


@dataclass
class ParseReport:
    """A full parse result plus the resources that produced it."""

    result: ParseResult
    resources: ParserResources

    def best_semantic_graph(self) -> dict[str, Any] | None:
        best = self.result.best()
        return self.interpret(best).as_dict() if best else None

    def interpret(
        self,
        item: Any | None = None,
        *,
        sense_selection: Mapping[str, str] | None = None,
    ):
        """Run optional semantic interpretation after syntax has completed."""
        from .semantics import SemanticInterpreter

        selected = item if item is not None else self.result.best()
        if selected is None:
            return None
        return SemanticInterpreter(
            self.resources.grammar, self.resources.semantic_rules(), self.resources.lexicon,
        ).interpret(selected, sense_selection=sense_selection)

    def as_dict(self) -> dict[str, Any]:
        return self.result.as_dict()


class Parser:
    """Generic engine: MATCH, UNIFY, EXPAND, PACK, SCORE, COMPOSE."""

    def __init__(
        self,
        resources: ParserResources,
        *,
        beam: int = 80,
        max_items: int = 50_000,
        goal_category: str = "CLAUSE",
        cache_size: int = 2048,
        deduplicate_lexical: bool = True,
        complexity_policy: ComplexityPolicy | None = None,
    ) -> None:
        self.resources = resources
        self.beam = beam
        self.max_items = max_items
        self.goal_category = goal_category
        self.deduplicate_lexical = deduplicate_lexical
        self._lattice_cache: LRU[str, Any] = LRU(cache_size)
        self._parse_cache: LRU[tuple[str, str], ParseResult] = LRU(cache_size)
        # Grammar masks and transition indexes are immutable and shared by
        # every sentence parsed by this instance.
        # The upper layer is deliberately only the coordination fragment of
        # the same declarative grammar.  This prevents permissive NP/quote
        # conversions from reinterpreting clause interfaces as appositions.
        interface_categories = {goal_category, "COMMA", "COORD"}
        assembly_rules = tuple(
            rule for rule in resources.grammar
            if rule.lhs.category == goal_category
            and any(symbol.category in {"COMMA", "COORD"} for symbol in rule.rhs)
            and all(symbol.category in interface_categories for symbol in rule.rhs)
        )
        self._assembly_vector_grammar = VectorGrammar(Grammar(assembly_rules))
        # Three/four-clause list rules are valid only after `_clause_plan`
        # has independently established clause-shaped segments.  Leaving
        # them in the unrestricted grammar lets comma-delimited NP/VP lists
        # manufacture finite clauses from lexical homographs (for example
        # ``a short name`` => subject + verb).  Ordinary binary coordination
        # remains available in the main grammar.
        hierarchical_only = {"clause_list3", "clause_list4"}
        syntax_rules = tuple(
            rule for rule in resources.grammar
            if rule.rule_id not in hierarchical_only
        )
        self._vector_grammar = VectorGrammar(Grammar(syntax_rules))
        # Opt-in dispatch, not a second parser invoked for every sentence.
        # These two grammar variants are precompiled at initialization;
        # short sentences retain the ordinary recognizer with no probe.
        self._complexity_policy = complexity_policy
        self._complexity_router = (
            StructuralRiskRouter(self._vector_grammar.grammar, complexity_policy)
            if complexity_policy is not None else None
        )
        self._difficult_vector_grammar = (
            VectorGrammar(
                self._vector_grammar.grammar,
                online_prefix_edges=complexity_policy.difficult_strategy == "online",
                flat_prefix_edges=complexity_policy.difficult_strategy == "flat",
            )
            if complexity_policy is not None else None
        )
        # Quotation rules exist only in a quote-aware forest, preserving the
        # baseline's canonical ranking and runtime on ordinary novel prose.
        dialogue_path = resources.metadata.get("dialogue_rules")
        self._dialogue_resources: ParserResources | None = None
        self._dialogue_vector_grammar: VectorGrammar | None = None
        if dialogue_path and Path(dialogue_path).is_file():
            dialogue_rules = tuple(load_grammar(dialogue_path))
            if dialogue_rules:
                dialogue_grammar = Grammar((*syntax_rules, *dialogue_rules))
                self._dialogue_vector_grammar = VectorGrammar(
                    dialogue_grammar, preserve_quote_delimiters=True,
                )
                self._dialogue_resources = ParserResources(
                    grammar=dialogue_grammar,
                    lexicon=resources.lexicon,
                    types=resources.types,
                    metadata=resources.metadata,
                )
        # Derived solely from the static function-word inventory.  Looking
        # for an early boundary must never wake WordNet up.
        self._coord_surfaces = frozenset(
            surface.casefold()
            for entry in resources.lexicon.entries
            if any(sense.category == "COORD" for sense in entry.senses)
            for surface in entry.surfaces
        )
        self._clause_subject_surfaces = frozenset(
            surface.casefold()
            for entry in resources.lexicon.entries
            if any(sense.category in {"PRONOUN", "EXPL"} for sense in entry.senses)
            for surface in entry.surfaces
        )
        self._determiner_surfaces = frozenset(
            surface.casefold()
            for entry in resources.lexicon.entries
            if any(sense.category in {"DET", "POSS"} for sense in entry.senses)
            for surface in entry.surfaces
        )

    @classmethod
    def from_dir(cls, directory: str | Path, **kwargs: Any) -> "Parser":
        return cls(ParserResources.from_dir(directory), **kwargs)

    def parse(self, text: str) -> ParseReport:
        original = text.strip()
        # Dialogue results are expensive and must be cached separately from
        # the unquoted fallback which intentionally has another source span.
        dialogue_key = (original, self.goal_category)
        if self.goal_category == "CLAUSE" and self._dialogue_vector_grammar is not None:
            from .dialogue import quotation_boundaries
            if quotation_boundaries(original):
                cached_dialogue = self._parse_cache.get(dialogue_key)
                if cached_dialogue is not None and cached_dialogue.stats.get("dialogue_scoped"):
                    return ParseReport(
                        result=cached_dialogue,
                        resources=self._dialogue_resources or self.resources,
                    )
                dialogue = self._parse_dialogue_text(original)
                if dialogue is not None and dialogue.completed:
                    self._parse_cache.put(dialogue_key, dialogue)
                    return ParseReport(
                        result=dialogue,
                        resources=self._dialogue_resources or self.resources,
                    )
        # Legacy parsing still accepts isolated outer-quoted clauses.
        text = original.strip('"\u201c\u201d\u2018\u2019').strip()
        cache_key = (text, self.goal_category)
        cached = self._parse_cache.get(cache_key)
        if cached is not None:
            return ParseReport(result=cached, resources=self.resources)

        light_tokens = tokenize(text)
        plan = self._clause_plan(text, light_tokens)
        if plan is not None:
            hierarchical = self._parse_hierarchical(text, light_tokens, plan)
            if hierarchical is not None:
                self._parse_cache.put(cache_key, hierarchical)
                return ParseReport(result=hierarchical, resources=self.resources)

        result = self._parse_vector_text(text)
        if plan is not None and isinstance(result.stats, dict):
            result.stats["segmentation_fallback"] = True
        self._parse_cache.put(cache_key, result)
        return ParseReport(result=result, resources=self.resources)

    def _select_vector_grammar(
        self, lattice: Any, *, dialogue: bool = False,
    ) -> tuple[VectorGrammar, RoutingDecision | None]:
        """Select before forest recognition; never repeat the completed parse."""
        if self._complexity_router is None:
            return self._vector_grammar, None
        decision = self._complexity_router.choose(
            lattice, dialogue=dialogue or any(
                quote in lattice.text for quote in ('"', '“', '”', '‘', '’')
            ),
        )
        if decision.strategy == "canonical":
            return self._vector_grammar, decision
        if self._difficult_vector_grammar is None:
            raise AssertionError("Missing precompiled hard-sentence grammar")
        return self._difficult_vector_grammar, decision

    @staticmethod
    def _attach_complexity_route(
        result: ParseResult, decision: RoutingDecision | None,
    ) -> ParseResult:
        if decision is not None and isinstance(result.stats, dict):
            result.stats.update({
                "complexity_route": decision.strategy,
                "complexity_reason": decision.reason,
                "complexity_score": decision.score,
                "complexity_probe_ms": round(decision.measured_ms, 5),
                "complexity_tokens": decision.token_count,
            })
        return result

    def parse_grammar_lattice(
        self,
        lattice: Any,
        *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
    ) -> ParseResult:
        """Canonical sentence-level entry point for future corpus benchmarks.

        The prior research scripts call _vector_grammar.parse_lattice
        directly, bypassing speech. New experiments should use this wrapper
        to include marked dialogues in coverage statistics without adding
        unquoted dialogue rules to the ordinary grammar.
        """
        budget = self.max_items if max_items is None else max_items
        is_dialogue = False
        if self.goal_category == "CLAUSE" and self._dialogue_vector_grammar is not None:
            extended = dialogue_lattice(lattice)
            if extended is not None:
                is_dialogue = True
                spoken = self._dialogue_vector_grammar.parse_lattice(
                    extended, beam=self.beam, max_items=budget,
                    goal_category=self.goal_category,
                    kbest_work_limit=kbest_work_limit,
                    diagnostic_k=diagnostic_k,
                )
                if spoken.completed:
                    if isinstance(spoken.stats,dict):
                        spoken.stats["dialogue_scoped"]=True
                        spoken.stats["dialogue_source"]="explicit_balanced_quotes"
                    if self._complexity_router is not None:
                        _, choice = self._select_vector_grammar(lattice, dialogue=True)
                        self._attach_complexity_route(spoken, choice)
                    return spoken
        grammar, decision = self._select_vector_grammar(
            lattice, dialogue=is_dialogue)
        return self._attach_complexity_route(grammar.parse_lattice(
            lattice, beam=self.beam, max_items=budget,
            goal_category=self.goal_category,
            kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,
        ), decision)

    def _parse_dialogue_text(self, text: str) -> ParseResult | None:
        """Parse marked speech using only balanced, explicit quote terminals.

        Every quotation mark is a syntax edge, not a discarded character.
        No permissive speech productions enter the ordinary vector grammar.
        """
        if self._dialogue_vector_grammar is None:
            return None
        from .dialogue import quotation_boundaries
        if not quotation_boundaries(text):
            return None
        lattice = self._lattice_cache.get(text)
        if lattice is None:
            lattice = build_lattice(
                text, self.resources.lexicon,
                deduplicate=self.deduplicate_lexical,
            )
            self._lattice_cache.put(text, lattice)
        extended = dialogue_lattice(lattice)
        if extended is None:
            return None
        result = self._dialogue_vector_grammar.parse_lattice(
            extended, beam=self.beam, max_items=self.max_items,
            goal_category=self.goal_category,
        )
        if isinstance(result.stats, dict):
            result.stats.update({
                "dialogue_scoped": True,
                "dialogue_quotation_count": sum(
                    c.category == "OPEN-QUOTE" for c in extended.candidates),
                "dialogue_source": "explicit_balanced_quotes",
            })
        return result

    def parse_diagnostic(
        self,
        text: str,
        *,
        alternatives: int = 64,
        max_items: int = 500_000,
    ) -> ParseReport:
        """Parse with a wide materialized root view and a generous budget.

        This mode is intended for grammar audits, not production.  It makes
        it possible to distinguish absent analyses from correct analyses that
        merely lose in ranking, without replacing the packed recognizer or
        changing its grammar.
        """
        original = text.strip()
        from .dialogue import quotation_boundaries
        if (self.goal_category == "CLAUSE"
                and self._dialogue_vector_grammar is not None
                and quotation_boundaries(original)):
            extended = dialogue_lattice(build_lattice(
                original, self.resources.lexicon,
                deduplicate=self.deduplicate_lexical,
            ))
            if extended is not None:
                result = self._dialogue_vector_grammar.parse_lattice(
                    extended, beam=max(self.beam,alternatives),
                    max_items=max(max_items,self.max_items),
                    goal_category=self.goal_category,diagnostic_k=alternatives,
                )
                if result.completed:
                    if isinstance(result.stats,dict):
                        result.stats.update({
                            "dialogue_scoped":True,
                            "dialogue_source":"explicit_balanced_quotes",
                            "diagnostic_mode":True,
                            "diagnostic_k":alternatives,
                        })
                    return ParseReport(
                        result=result,
                        resources=self._dialogue_resources or self.resources,
                    )
        text = text.strip().strip('"\u201c\u201d\u2018\u2019').strip()
        lattice = build_lattice(
            text, self.resources.lexicon,
            deduplicate=self.deduplicate_lexical,
        )
        result = self._vector_grammar.parse_lattice(
            lattice,
            beam=max(self.beam, alternatives),
            max_items=max(max_items, self.max_items),
            goal_category=self.goal_category,
            diagnostic_k=alternatives,
        )
        if isinstance(result.stats, dict):
            result.stats["diagnostic_mode"] = True
            result.stats["diagnostic_k"] = alternatives
        return ParseReport(result=result, resources=self.resources)

    def _parse_vector_text(self, text: str) -> ParseResult:
        lexical_start = perf_counter()
        lattice = self._lattice_cache.get(text)
        if lattice is None:
            lattice = build_lattice(
                text, self.resources.lexicon,
                deduplicate=self.deduplicate_lexical,
            )
            self._lattice_cache.put(text, lattice)
        lexical_ms = (perf_counter() - lexical_start) * 1000

        grammar, decision = self._select_vector_grammar(lattice)
        result = grammar.parse_lattice(
            lattice,
            beam=self.beam,
            max_items=self.max_items,
            goal_category=self.goal_category,
        )
        self._attach_complexity_route(result, decision)
        if isinstance(result.stats, dict):
            result.stats["lexical_ms"] = round(lexical_ms, 4)
        return result

    def _clause_plan(
        self,
        text: str,
        tokens: Sequence[Token],
    ) -> tuple[tuple[tuple[int, int], ...], tuple[Token, ...]] | None:
        """Suggest comma-delimited clauses using tokens and static data only."""
        comma_indices = [index for index, token in enumerate(tokens) if token.text == ","]
        if self.goal_category != "CLAUSE" or len(comma_indices) < 2:
            return None
        spans: list[tuple[int, int]] = []
        separators: list[Token] = []
        cursor = 0
        for comma_index in comma_indices:
            if comma_index <= cursor:
                return None
            spans.append((tokens[cursor].start, tokens[comma_index - 1].end))
            separators.append(tokens[comma_index])
            cursor = comma_index + 1
            if cursor < len(tokens) and tokens[cursor].text.casefold() in self._coord_surfaces:
                separators.append(tokens[cursor])
                cursor += 1
        while cursor < len(tokens) and tokens[cursor].text in {",", ".", "!", "?", ";", ":"}:
            cursor += 1
        if cursor >= len(tokens):
            return None
        last = len(tokens) - 1
        while last >= cursor and tokens[last].text in {".", "!", "?", ";", ":"}:
            last -= 1
        if last < cursor:
            return None
        spans.append((tokens[cursor].start, tokens[last].end))
        if any(not text[start:end].strip() for start, end in spans):
            return None
        tokens_by_start = {token.start: token for token in tokens}
        for start, _end in spans[1:]:
            first = tokens_by_start.get(start)
            if first is None:
                return None
            surface = first.text.casefold()
            # This fast path is an optimization for explicit clause lists,
            # not a license to promote NP/VP enumeration members to clauses.
            # Ambiguous starts safely fall back to the full shared forest.
            if surface in self._determiner_surfaces:
                return None
            if (
                surface not in self._clause_subject_surfaces
                and not first.text[:1].isupper()
            ):
                return None
        return tuple(spans), tuple(separators)

    def _parse_hierarchical(
        self,
        text: str,
        tokens: Sequence[Token],
        plan: tuple[tuple[tuple[int, int], ...], tuple[Token, ...]],
    ) -> ParseResult | None:
        """Validate clause pieces, then parse only their compact interfaces."""
        spans, separators = plan
        segment_results: list[ParseResult] = []
        interfaces: list[SegmentInterface] = []
        candidates: list[LexicalCandidate] = []
        for start, end in spans:
            local_text = text[start:end]
            segment = self._parse_vector_text(local_text)
            if not segment.completed:
                return None
            best = segment.best()
            if best is None or best.category != self.goal_category:
                return None
            interface = SegmentInterface(segment, start, start, end)
            interfaces.append(interface)
            segment_results.append(segment)
            candidates.append(LexicalCandidate(
                span_start=start,
                span_end=end,
                surface=text[start:end],
                lemma="<clause>",
                category=self.goal_category,
                features=best.features,
                source="segment-interface",
                score=best.score,
                provenance={"segment": [start, end]},
                interface=interface,
            ))

        for token in separators:
            candidates.extend(self._static_separator_candidates(token))
        interface_lattice = LexicalLattice(text, tuple(tokens), tuple(candidates))
        assembly = self._assembly_vector_grammar.parse_lattice(
            interface_lattice,
            beam=self.beam,
            max_items=self.max_items,
            goal_category=self.goal_category,
        )
        if not assembly.completed:
            return None

        segment_stats = [dict(result.stats) for result in segment_results]
        assembly_stats = dict(assembly.stats)
        sums = lambda key: sum(float(row.get(key, 0)) for row in segment_stats)
        # Keep cumulative counters stable when LazyRootSequence.refresh_stats
        # is called again by best()/alternatives() on the assembled result.
        provider = getattr(assembly.roots, "provider", None)
        if provider is not None:
            provider.stat_offsets = {
                "unification_attempts": int(sums("unification_attempts")),
                "unification_rejections": int(sums("unification_rejections")),
                "hint_unification_attempts": int(sums("hint_unification_attempts")),
                "hint_unification_rejections": int(sums("hint_unification_rejections")),
                "hint_compatibility_cache_hits": int(sums("hint_compatibility_cache_hits")),
                "failed_continuation_cache_hits": int(sums("failed_continuation_cache_hits")),
                "projected_bindings": int(sums("projected_bindings")),
                "projected_context_cache_hits": int(sums("projected_context_cache_hits")),
                "nodes_visited_total": int(sums("nodes_visited_total")),
                "combinations_visited_total": int(sums("combinations_visited_total")),
            }
            provider.refresh_stats()
        if isinstance(assembly.stats, dict):
            assembly.stats.update({
                "engine": "vector-hierarchical-lazy-kbest",
                "segmented": True,
                "segment_count": len(segment_results),
                "segment_spans": [list(span) for span in spans],
                "segment_stats": segment_stats,
                "interface_recognition_ms": assembly_stats.get("recognition_ms", 0),
                "interface_best_ms": assembly_stats.get("best_ms", 0),
                "lexical_ms": round(sums("lexical_ms"), 4),
                "recognition_ms": round(sums("recognition_ms") + float(assembly_stats.get("recognition_ms", 0)), 4),
                "partial_proposals": int(sums("partial_proposals") + float(assembly_stats.get("partial_proposals", 0))),
                "duplicate_partial_proposals": int(sums("duplicate_partial_proposals") + float(assembly_stats.get("duplicate_partial_proposals", 0))),
                "duplicate_transitions_avoided": int(sums("duplicate_transitions_avoided") + float(assembly_stats.get("duplicate_transitions_avoided", 0))),
                "best_ms": round(sums("best_ms") + float(assembly_stats.get("best_ms", 0)), 4),
                "kbest_ms": round(sums("kbest_ms") + float(assembly_stats.get("kbest_ms", 0)), 4),
                # The upper extractor may request non-best clause alternatives
                # while finding its own best.  Those visits belong to the
                # global best cost, hence the segment total here.
                "combinations_visited_for_best": int(sums("combinations_visited_total") + float(assembly_stats.get("combinations_visited_for_best", 0))),
                "combinations_visited_total": int(sums("combinations_visited_total") + float(assembly_stats.get("combinations_visited_total", 0))),
                "unification_attempts": int(sums("unification_attempts") + float(assembly_stats.get("unification_attempts", 0))),
                "unification_rejections": int(sums("unification_rejections") + float(assembly_stats.get("unification_rejections", 0))),
                "hint_unification_attempts": int(sums("hint_unification_attempts") + float(assembly_stats.get("hint_unification_attempts", 0))),
                "hint_unification_rejections": int(sums("hint_unification_rejections") + float(assembly_stats.get("hint_unification_rejections", 0))),
                "hint_compatibility_cache_hits": int(sums("hint_compatibility_cache_hits") + float(assembly_stats.get("hint_compatibility_cache_hits", 0))),
                "failed_continuation_cache_hits": int(sums("failed_continuation_cache_hits") + float(assembly_stats.get("failed_continuation_cache_hits", 0))),
                "projected_bindings": int(sums("projected_bindings") + float(assembly_stats.get("projected_bindings", 0))),
                "projected_context_cache_hits": int(sums("projected_context_cache_hits") + float(assembly_stats.get("projected_context_cache_hits", 0))),
                "nodes_visited_for_best": int(sums("nodes_visited_for_best") + float(assembly_stats.get("nodes_visited_for_best", 0))),
            })
        assembly.shared_forest = {
            "assembly": assembly.shared_forest,
            "segments": tuple(result.shared_forest for result in segment_results),
            "interfaces": tuple(interfaces),
        }
        return assembly

    def _static_separator_candidates(self, token: Token) -> list[LexicalCandidate]:
        rows: list[LexicalCandidate] = []
        surface_key = token.text.casefold()
        for entry in self.resources.lexicon.entries:
            if surface_key not in {surface.casefold() for surface in entry.surfaces}:
                continue
            for sense in entry.senses:
                if sense.category not in {"COMMA", "COORD"}:
                    continue
                rows.append(_candidate_from_sense(
                    span_start=token.start,
                    span_end=token.end,
                    surface=token.text,
                    lemma=entry.lemma,
                    sense=sense,
                    source="function-inventory",
                ))
        return rows

    def cache_stats(self) -> dict[str, Any]:
        return {
            "lattice": self._lattice_cache.stats(),
            "parse": self._parse_cache.stats(),
        }

    def analyze(self, text: str) -> dict[str, Any]:
        return self.parse(text).as_dict()


def _read_json_rows(path: Path) -> list[Mapping[str, Any]]:
    import json

    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return [raw]
    return list(raw)


def discover_wordnet(data_dir: Path) -> Path | None:
    """Find the WordNet dict directory.

    Checks, in order: explicit ``WORDNET_DICT`` environment variable,
    ``data/wordnet_path`` (one-line pointer), then historical local install.
    Invalid explicit configuration must fail loudly, not silently fall back.
    """
    data_dir = data_dir.resolve()
    configured = os.environ.get("WORDNET_DICT")
    if configured:
        explicit = Path(configured).expanduser()
        if not explicit.is_dir():
            raise FileNotFoundError(
                f"WORDNET_DICT is configured but not a directory: {explicit}"
            )
        return explicit.resolve()
    pointer = data_dir / "wordnet_path"
    if pointer.exists():
        candidate = Path(pointer.read_text(encoding="utf-8").strip())
        if candidate.is_dir():
            return candidate
    for candidate in (
        data_dir.parents[1] / ".local" / "share" / "wordnet" / "WordNet-3.0" / "dict",
        data_dir.parents[2] / ".local" / "share" / "wordnet" / "WordNet-3.0" / "dict",
    ):
        if candidate.is_dir():
            return candidate
    return None
