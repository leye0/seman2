"""Top-level parse pipeline.

    text -> lattice -> chart -> packed forest -> semantic alternatives

Parse is local to the string; discourse context is layered on later and
never destroys the analyses produced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

from .chart import ParseResult
from .grammar import Grammar, load_grammar, load_grammar_rows
from .lexicon import Lexicon, load_lexicon, load_lexicon_rows
from .perf import LRU
from .segmentation import LexicalCandidate, LexicalLattice, Token, build_lattice, tokenize
from .types import TypeHierarchy, load_types
from .vector_chart import SegmentInterface, VectorGrammar


@dataclass
class ParserResources:
    """Everything the engine knows — all of it data."""

    grammar: Grammar
    lexicon: Lexicon
    types: TypeHierarchy
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dir(
        cls,
        directory: str | Path,
        *,
        wordnet_dict: str | Path | None = None,
    ) -> "ParserResources":
        directory = Path(directory)
        return cls(
            grammar=load_grammar(directory / "grammar.jsonl"),
            lexicon=load_lexicon(
                directory / "function_words.jsonl",
                wordnet_dict=wordnet_dict or discover_wordnet(directory),
            ),
            types=load_types(_read_json_rows(directory / "types.json")),
            metadata={"source": str(directory)},
        )


@dataclass
class ParseReport:
    """A full parse result plus the resources that produced it."""

    result: ParseResult
    resources: ParserResources

    def best_semantic_graph(self) -> dict[str, Any] | None:
        best = self.result.best()
        return best.semantic.as_dict() if best else None

    def as_dict(self) -> dict[str, Any]:
        payload = self.result.as_dict()
        payload["semantic"] = self.best_semantic_graph()
        return payload


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
    ) -> None:
        self.resources = resources
        self.beam = beam
        self.max_items = max_items
        self.goal_category = goal_category
        self._lattice_cache: LRU[str, Any] = LRU(cache_size)
        self._parse_cache: LRU[tuple[str, str], ParseResult] = LRU(cache_size)
        # Grammar masks and transition indexes are immutable and shared by
        # every sentence parsed by this instance.
        self._vector_grammar = VectorGrammar(resources.grammar)
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
        # Derived solely from the static function-word inventory.  Looking
        # for an early boundary must never wake WordNet up.
        self._coord_surfaces = frozenset(
            surface.casefold()
            for entry in resources.lexicon.entries
            if any(sense.category == "COORD" for sense in entry.senses)
            for surface in entry.surfaces
        )

    @classmethod
    def from_dir(cls, directory: str | Path, **kwargs: Any) -> "Parser":
        return cls(ParserResources.from_dir(directory), **kwargs)

    def parse(self, text: str) -> ParseReport:
        # Quotation marks are delimiters, not linguistic material.
        text = text.strip().strip('"\u201c\u201d\u2018\u2019').strip()
        cache_key = (text, self.goal_category)
        cached = self._parse_cache.get(cache_key)
        if cached is not None:
            return ParseReport(result=cached, resources=self.resources)

        light_tokens = tokenize(text)
        plan = self._clause_plan(text, light_tokens)
        if plan is not None:
            hierarchical = self._parse_hierarchical(text, light_tokens, plan)
            if hierarchical is not None:
                return ParseReport(result=hierarchical, resources=self.resources)

        result = self._parse_vector_text(text)
        if plan is not None and isinstance(result.stats, dict):
            result.stats["segmentation_fallback"] = True
        return ParseReport(result=result, resources=self.resources)

    def _parse_vector_text(self, text: str) -> ParseResult:
        lexical_start = perf_counter()
        lattice = self._lattice_cache.get(text)
        if lattice is None:
            lattice = build_lattice(text, self.resources.lexicon)
            self._lattice_cache.put(text, lattice)
        lexical_ms = (perf_counter() - lexical_start) * 1000

        result = self._vector_grammar.parse_lattice(
            lattice,
            beam=self.beam,
            max_items=self.max_items,
            goal_category=self.goal_category,
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
                rows.append(LexicalCandidate(
                    span_start=token.start,
                    span_end=token.end,
                    surface=token.text,
                    lemma=entry.lemma,
                    category=sense.category,
                    features=sense.features,
                    sense_id=sense.sense_id,
                    semantic_type=sense.semantic_type,
                    normalized=entry.lemma,
                    source="function-inventory",
                    score=sense.score,
                    provenance=dict(sense.provenance),
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

    Checks, in order: ``data/wordnet_path`` (one-line path file), then the
    project-local install used by the TRIPS setup.
    """
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
