"""Top-level parse pipeline.

    text -> lattice -> chart -> packed forest -> semantic alternatives

Parse is local to the string; discourse context is layered on later and
never destroys the analyses produced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .chart import Chart, ParseResult
from .grammar import Grammar, load_grammar, load_grammar_rows
from .lexicon import Lexicon, load_lexicon, load_lexicon_rows
from .perf import LRU
from .segmentation import build_lattice
from .types import TypeHierarchy, load_types


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

    @classmethod
    def from_dir(cls, directory: str | Path, **kwargs: Any) -> "Parser":
        return cls(ParserResources.from_dir(directory), **kwargs)

    def parse(self, text: str) -> ParseReport:
        cache_key = (text, self.goal_category)
        cached = self._parse_cache.get(cache_key)
        if cached is not None:
            return ParseReport(result=cached, resources=self.resources)

        lattice = self._lattice_cache.get(text)
        if lattice is None:
            lattice = build_lattice(text, self.resources.lexicon)
            self._lattice_cache.put(text, lattice)

        chart = Chart(
            self.resources.grammar,
            beam=self.beam,
            max_items=self.max_items,
            goal_category=self.goal_category,
        )
        result = chart.parse_lattice(lattice)
        self._parse_cache.put(cache_key, result)
        return ParseReport(result=result, resources=self.resources)

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
