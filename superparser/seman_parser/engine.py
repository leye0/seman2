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
from .runtime_gc import freeze_loaded_wordnet_once
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
                supplemental_paths=(
                    directory / "syntax_lexicon.jsonl",
                    directory / "literary_lexicon.jsonl",
                ),
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
    lattice: LexicalLattice | None = None

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
        lexical_left_corner_pruning: bool = False,
    ) -> None:
        self.resources = resources
        self.beam = beam
        self.max_items = max_items
        self.goal_category = goal_category
        self.deduplicate_lexical = deduplicate_lexical
        self.lexical_left_corner_pruning = lexical_left_corner_pruning
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
        self._assembly_vector_grammar = VectorGrammar(
            Grammar(assembly_rules),
            lexical_left_corner_pruning=lexical_left_corner_pruning,
        )
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
        self._vector_grammar = VectorGrammar(
            Grammar(syntax_rules),
            lexical_left_corner_pruning=lexical_left_corner_pruning,
        )
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
                lazy_trie_recognition=True,
                lexical_left_corner_pruning=lexical_left_corner_pruning,
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
                    lexical_left_corner_pruning=lexical_left_corner_pruning,
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

    def _lattice_for_text(self, text: str) -> LexicalLattice:
        """The same lexical preparation for public parsing and corpus audits."""
        lattice = self._lattice_cache.get(text)
        if lattice is None:
            lattice = build_lattice(
                text, self.resources.lexicon,
                deduplicate=self.deduplicate_lexical,
            )
            self._lattice_cache.put(text, lattice)
        return lattice

    def parse(
        self,
        text: str,
        *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseReport:
        """SINGLE public parsing entry point, including corpus diagnostics.

        Dialogue, safe clause segmentation, routing and ordinary recognition
        follow the same order for every caller. Explicit budgets disable the
        ordinary result cache so trials cannot silently reuse a different run.
        """
        original = text.strip()
        use_cache = all(value is None for value in (
            max_items, kbest_work_limit, diagnostic_k, beam,
        ))
        dialogue_key = (original, self.goal_category)
        if self.goal_category == "CLAUSE" and self._dialogue_vector_grammar is not None:
            from .dialogue import quotation_boundaries
            if quotation_boundaries(original):
                if use_cache:
                    cached = self._parse_cache.get(dialogue_key)
                    if cached is not None:
                        return ParseReport(
                            result=cached,
                            resources=(self._dialogue_resources or self.resources)
                            if cached.stats.get("dialogue_scoped") else self.resources,
                            lattice=self._lattice_for_text(original),
                        )
                original_lattice = self._lattice_for_text(original)
                # One recognizer call: it tries scoped dialogue then the
                # ordinary grammar. NEVER discard quote marks and retry.
                spoken = self._parse_lattice(
                    original_lattice, max_items=max_items,
                    kbest_work_limit=kbest_work_limit,
                    diagnostic_k=diagnostic_k, beam=beam,
                )
                if use_cache:
                    self._parse_cache.put(dialogue_key, spoken)
                return ParseReport(
                    result=spoken,
                    resources=(self._dialogue_resources or self.resources)
                    if spoken.stats.get("dialogue_scoped") else self.resources,
                    lattice=original_lattice,
                )
        # No silent normalization: an incomplete quoted sentence must fail
        # with its original quote context, not succeed as a different string.
        normalized = original
        cache_key = (normalized, self.goal_category)
        if use_cache:
            cached = self._parse_cache.get(cache_key)
            if cached is not None:
                return ParseReport(
                    result=cached, resources=self.resources,
                    lattice=self._lattice_for_text(normalized),
                )

        light_tokens = tokenize(normalized)
        plan = self._clause_plan(normalized, light_tokens)
        if plan is None:
            plan = self._binary_coord_clause_plan(normalized, light_tokens)
        if plan is not None:
            hierarchical = self._parse_hierarchical(
                normalized, light_tokens, plan, max_items=max_items,
                kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if hierarchical is not None:
                if use_cache:
                    self._parse_cache.put(cache_key, hierarchical)
                return ParseReport(
                    result=hierarchical, resources=self.resources,
                    lattice=self._lattice_for_text(normalized),
                )

        lattice = self._lattice_for_text(normalized)
        result = self._parse_lattice(
            lattice, max_items=max_items,
            kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )
        if plan is not None and isinstance(result.stats, dict):
            result.stats["segmentation_fallback"] = True
        if use_cache:
            self._parse_cache.put(cache_key, result)
        return ParseReport(
            result=result, resources=self.resources, lattice=lattice,
        )

    def _select_vector_grammar(
        self, lattice: Any, *, dialogue: bool = False,
    ) -> tuple[VectorGrammar, RoutingDecision | None]:
        """Select before forest recognition; never repeat the completed parse."""
        if self._complexity_router is None:
            return self._vector_grammar, None
        # The fast path is decided by token count first: it must not
        # inspect lexical ambiguity or even scan quotation characters.
        short = len(lattice.tokens) < self._complexity_policy.min_tokens
        decision = self._complexity_router.choose(
            lattice, dialogue=(
                False if short else dialogue or any(
                    quote in lattice.text for quote in ('"', '“', '”', '‘', '’')
                )
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

    def _parse_lattice(
        self,
        lattice: LexicalLattice,
        *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult:
        """Internal recognizer. Only Parser.parse dispatches public analyses.

        Keep the dialogue-scoped grammar and complexity policy centralized,
        including when analyzing validated hierarchical clause segments.
        """
        freeze_loaded_wordnet_once(self.resources.lexicon)
        budget = self.max_items if max_items is None else max_items
        active_beam = self.beam if beam is None else beam
        is_dialogue = False
        dialogue_attempt = None
        if self.goal_category == "CLAUSE" and self._dialogue_vector_grammar is not None:
            extended = dialogue_lattice(lattice)
            if extended is not None:
                is_dialogue = True
                spoken = self._dialogue_vector_grammar.parse_lattice(
                    extended, beam=active_beam, max_items=budget,
                    goal_category=self.goal_category,
                    kbest_work_limit=kbest_work_limit,
                    diagnostic_k=diagnostic_k,
                )
                if not spoken.completed:
                    # A scoped dialogue parse may exhaust the forest or k-best
                    # budget before ordinary grammar fallback succeeds/fails.
                    # Preserve this independent evidence for corpus diagnostics;
                    # never mislabel an inconclusive dialogue attempt as a
                    # conclusive absence of grammatical structure.
                    dialogue_attempt = {
                        "budget_exceeded": bool(spoken.stats.get("budget_exceeded")),
                        "kbest_budget_exceeded": bool(
                            spoken.stats.get("kbest_budget_exceeded")),
                        "structural_root_nodes": int(
                            spoken.stats.get("structural_root_nodes", 0)),
                        "forest_nodes": int(spoken.stats.get("forest_nodes", 0)),
                        "partial_states": int(
                            spoken.stats.get("partial_states", 0)),
                        "kbest_work_units": int(
                            spoken.stats.get("kbest_work_units", 0)),
                        "saturation_top_rules": spoken.stats.get(
                            "saturation_top_rules", []),
                        "saturation_top_categories": spoken.stats.get(
                            "saturation_top_categories", []),
                        "unreachable_prefix_proposals": int(
                            spoken.stats.get("unreachable_prefix_proposals", 0)),
                    }
                if spoken.completed:
                    if isinstance(spoken.stats, dict):
                        spoken.stats["dialogue_scoped"] = True
                        spoken.stats["dialogue_source"] = "explicit_balanced_quotes"
                    if self._complexity_router is not None:
                        _, choice = self._select_vector_grammar(lattice, dialogue=True)
                        self._attach_complexity_route(spoken, choice)
                    return spoken
        grammar, decision = self._select_vector_grammar(
            lattice, dialogue=is_dialogue,
        )
        result = grammar.parse_lattice(
            lattice, beam=active_beam, max_items=budget,
            goal_category=self.goal_category,
            kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,
        )
        if dialogue_attempt is not None and isinstance(result.stats, dict):
            result.stats["dialogue_attempt"] = dialogue_attempt
        return self._attach_complexity_route(result, decision)

    def parse_diagnostic(
        self,
        text: str,
        *,
        alternatives: int = 64,
        max_items: int = 500_000,
    ) -> ParseReport:
        """Convenience preset for Parser.parse, never another parser route."""
        report = self.parse(
            text, max_items=max(max_items, self.max_items),
            diagnostic_k=alternatives, beam=max(self.beam, alternatives),
        )
        if isinstance(report.result.stats, dict):
            report.result.stats["diagnostic_mode"] = True
            report.result.stats["diagnostic_k"] = alternatives
        return report

    def _parse_vector_text(
        self,
        text: str,
        *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult:
        """Internal segment recognition through the SAME core dispatcher."""
        lexical_start = perf_counter()
        lattice = self._lattice_for_text(text)
        lexical_ms = (perf_counter() - lexical_start) * 1000
        result = self._parse_lattice(
            lattice, max_items=max_items,
            kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )
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


    def _binary_coord_clause_plan(
        self,
        text: str,
        tokens: Sequence[Token],
    ) -> tuple[tuple[tuple[int, int], ...], tuple[Token, ...]] | None:
        """Propose ONLY an explicit comma + coordinator between full clauses.

        'but' is ambiguous: in 'You were but a man', it is a restrictive
        adverb, NOT a coordination boundary. A token's COORD lexical sense
        is necessary but insufficient: the follow-up hierarchical stage
        requires each side to independently parse as a finite-subject
        clause; otherwise the original unsplit forest is used.
        """
        if self.goal_category != "CLAUSE" or len(tokens) < 7:
            return None
        # Quote and punctuation context can change clause scope. Prefer
        # the full grammar rather than removing such context as an
        # optimization.
        if any(mark in text for mark in ('"', '“', '”', '‘', '’')):
            return None
        commas = [i for i, tok in enumerate(tokens) if tok.text == ","]
        if len(commas) != 1:
            return None
        comma = commas[0]
        if comma < 2 or comma + 3 >= len(tokens):
            return None
        coordinator = tokens[comma + 1]
        if coordinator.text.casefold() not in self._coord_surfaces:
            return None

        def explicit_subject_start(token: Token) -> bool:
            surface = token.text.casefold()
            if surface in self._clause_subject_surfaces:
                return True
            if surface in self._determiner_surfaces:
                return True
            # Capitalized names may begin clauses; a subsequent full
            # finite clause parse is still mandatory.
            return token.text[:1].isupper() and surface not in self._coord_surfaces

        if not explicit_subject_start(tokens[0]):
            return None
        right_start = tokens[comma + 2]
        if not explicit_subject_start(right_start):
            return None
        end_index = len(tokens) - 1
        while end_index > comma + 2 and tokens[end_index].text in {".", "!", "?"}:
            end_index -= 1
        if end_index <= comma + 2:
            return None
        spans = (
            (tokens[0].start, tokens[comma - 1].end),
            (right_start.start, tokens[end_index].end),
        )
        return spans, (tokens[comma], coordinator)

    def _parse_hierarchical(
        self,
        text: str,
        tokens: Sequence[Token],
        plan: tuple[tuple[tuple[int, int], ...], tuple[Token, ...]],
        *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Validate clause pieces, then parse only their compact interfaces."""
        spans, separators = plan
        segment_results: list[ParseResult] = []
        interfaces: list[SegmentInterface] = []
        candidates: list[LexicalCandidate] = []
        for start, end in spans:
            local_text = text[start:end]
            segment = self._parse_vector_text(
                local_text, max_items=max_items,
                kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if not segment.completed:
                return None
            best = segment.best()
            if best is None or best.category != self.goal_category:
                return None
            # Binary clause decomposition must demonstrate a conventional
            # independently finite subject-predicate analysis on EACH side,
            # not an elliptical NP/ADJP promoted to a CLAUSE by homographs.
            if len(spans) == 2 and best.rule_id != "clause_np_vp":
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
            beam=self.beam if beam is None else beam,
            max_items=self.max_items if max_items is None else max_items,
            goal_category=self.goal_category,
            kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,
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
