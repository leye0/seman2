"""Sentence-reader pipeline: parse, extract mentions, commit reference links.

Base contract: ``plans/coreference-guide.md``. Identity comes only from
``SAME_REF`` / ``ASSERTED_IDENTITY`` links. ``MAYBE_REF`` stays open;
``DIFFERENT_REF`` blocks a pair; structural kinds do not merge individuals.

Parse stays local to the sentence; discourse context is global and
persistent. Decisions are reference links, not verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .coref import commit_links, introduce
from .discourse import DiscourseState, Mention
from .engine import Parser, ParseReport
from .mentions import extract_event_mentions, extract_mentions
from .refdetect import detect_all
from .reference import ReferenceLink


@dataclass
class SentenceAnalysis:
    """One sentence: parse report, mentions, reference links."""

    index: int
    text: str
    report: ParseReport
    mentions: tuple[Mention, ...]
    reference_links: tuple[ReferenceLink, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "parse": self.report.as_dict(),
            "mentions": [m.as_dict() for m in self.mentions],
            "reference_links": [lk.as_dict() for lk in self.reference_links],
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
        speaker_id: str | None = None,
        addressee_id: str | None = None,
    ) -> None:
        self.parser = parser
        self.state = DiscourseState()
        self.speaker_id = speaker_id
        self.addressee_id = addressee_id
        self._sentence_index = 0

    @classmethod
    def from_dir(cls, directory: str | Path, **kwargs: Any) -> "DiscourseProcessor":
        return cls(Parser.from_dir(Path(directory)), **kwargs)

    def read(self, text: str) -> SentenceAnalysis:
        """Parse one sentence, extract mentions, detect and commit links."""
        report = self.parser.parse(text)
        best = report.result.best()
        mentions: tuple[Mention, ...] = ()
        ref_links: tuple[ReferenceLink, ...] = ()

        if best is not None:
            semantic = report.interpret(best)
            mentions = tuple(
                extract_mentions(best, self._sentence_index, semantic=semantic)
                + extract_event_mentions(best, self._sentence_index, semantic=semantic)
            )
            # Register every mention; open entities for referential ones.
            for mention in mentions:
                introduce(mention, self.state)

            # Grammar-only reference links (plans/coreference-guide.md).
            prior = [
                m
                for m in self.state.mentions.values()
                if m.sentence_index < self._sentence_index
            ]
            ref_links = tuple(
                detect_all(
                    best,
                    mentions,
                    sentence_index=self._sentence_index,
                    parse_id=text[:40],
                    antecedents=prior,
                    speaker_id=self.speaker_id,
                    addressee_id=self.addressee_id,
                    text=text,
                ).links
            )
            commit_links(ref_links, self.state)

            # Semantic interpretation is explicitly post-syntactic.
            if semantic is not None:
                self.state.graph = self.state.graph.merge(semantic.graph)

        analysis = SentenceAnalysis(
            index=self._sentence_index,
            text=text,
            report=report,
            mentions=mentions,
            reference_links=ref_links,
        )
        self._sentence_index += 1
        self.state.sentence_count = self._sentence_index
        for entity in self.state.entities.values():
            entity.decay_salience()
        return analysis

    def read_many(self, texts: Sequence[str]) -> DiscourseReport:
        sentences = tuple(self.read(text) for text in texts)
        return DiscourseReport(state=self.state, sentences=sentences)
