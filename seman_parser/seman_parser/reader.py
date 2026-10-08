"""Sentence-reader pipeline: parse, extract mentions, resolve coreference.

Parse stays local to the sentence; discourse context is global and
persistent. Coreference decisions are ranked hypotheses, not verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .coref import CoreferenceResolver, ResolverConfig, link_best
from .discourse import CoreferenceHypothesis, DiscourseState, Mention
from .engine import Parser, ParseReport
from .mentions import extract_event_mentions, extract_mentions


@dataclass
class SentenceAnalysis:
    """One sentence: parse report, mentions, coreference hypotheses."""

    index: int
    text: str
    report: ParseReport
    mentions: tuple[Mention, ...]
    hypotheses: Mapping[str, tuple[CoreferenceHypothesis, ...]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "parse": self.report.as_dict(),
            "mentions": [m.as_dict() for m in self.mentions],
            "coreference": {
                mid: [h.as_dict() for h in hyps] for mid, hyps in self.hypotheses.items()
            },
        }


@dataclass
class DiscourseReport:
    """Full session report after one or more sentences."""

    state: DiscourseState
    sentences: tuple[SentenceAnalysis, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.as_dict(),
            "sentences": [s.as_dict() for s in self.sentences],
        }

    def entity_chains(self) -> Mapping[str, list[str]]:
        """entity_id -> mention surfaces, for quick inspection."""
        out: dict[str, list[str]] = {}
        for entity in self.state.entities.values():
            out[entity.entity_id] = list(entity.surfaces)
        return out


class DiscourseProcessor:
    """Stateful reader over multiple sentences."""

    def __init__(
        self,
        parser: Parser,
        *,
        resolver_config: ResolverConfig | None = None,
    ) -> None:
        self.parser = parser
        self.state = DiscourseState()
        self.resolver = CoreferenceResolver(
            types=parser.resources.types,
            config=resolver_config or ResolverConfig(),
        )
        self._sentence_index = 0

    @classmethod
    def from_dir(cls, directory: str | Path, **kwargs: Any) -> "DiscourseProcessor":
        return cls(Parser.from_dir(Path(directory)), **kwargs)

    def read(self, text: str) -> SentenceAnalysis:
        """Parse one sentence, extract mentions, resolve and commit."""
        report = self.parser.parse(text)
        best = report.result.best()
        mentions: tuple[Mention, ...] = ()
        hypotheses: dict[str, tuple[CoreferenceHypothesis, ...]] = {}

        if best is not None:
            mentions = tuple(
                extract_mentions(best, self._sentence_index)
                + extract_event_mentions(best, self._sentence_index)
            )
            for mention in mentions:
                self.state.mentions[mention.mention_id] = mention
                ranked = self.resolver.resolve(mention, self.state)
                hypotheses[mention.mention_id] = ranked
                link_best(mention, self.state, self.resolver)
            # Fold the sentence semantics into the persistent graph.
            self.state.graph = self.state.graph.merge(best.semantic.graph)

        analysis = SentenceAnalysis(
            index=self._sentence_index,
            text=text,
            report=report,
            mentions=mentions,
            hypotheses=hypotheses,
        )
        self._sentence_index += 1
        self.state.sentence_count = self._sentence_index
        for entity in self.state.entities.values():
            entity.decay_salience()
        return analysis

    def read_many(self, texts: Sequence[str]) -> DiscourseReport:
        sentences = tuple(self.read(text) for text in texts)
        return DiscourseReport(state=self.state, sentences=sentences)
