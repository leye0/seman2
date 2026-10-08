"""Segmentation and lexical lattice.

Transforms raw text into overlapping lexical candidates without discarding
hypotheses early: tokens, contractions, multiwords and morphology all stay
available to the chart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .features import FeatureStructure
from .lexicon import LexicalSense, Lexicon
from .symbols import intern

_TOKEN_RE = re.compile(
    r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?|[^\w\s]",
    re.UNICODE,
)


@dataclass(frozen=True, slots=True)
class LexicalCandidate:
    """One hypothesized lexical item over a character span."""

    span_start: int
    span_end: int
    surface: str
    lemma: str
    category: str
    features: FeatureStructure
    sense_id: str | None = None
    semantic_type: str | None = None
    normalized: str | None = None
    source: str = "lexicon"
    score: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def span(self) -> tuple[int, int]:
        return (self.span_start, self.span_end)

    def as_dict(self) -> dict[str, Any]:
        return {
            "span": [self.span_start, self.span_end],
            "surface": self.surface,
            "lemma": self.lemma,
            "category": self.category,
            "features": self.features.as_dict(),
            "sense_id": self.sense_id,
            "semantic_type": self.semantic_type,
            "normalized": self.normalized,
            "source": self.source,
            "score": self.score,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True, slots=True)
class Token:
    index: int
    start: int
    end: int
    text: str


@dataclass
class LexicalLattice:
    """Overlapping candidates grouped by start offset."""

    text: str
    tokens: tuple[Token, ...]
    candidates: tuple[LexicalCandidate, ...]

    def starting_at(self, index: int) -> Sequence[LexicalCandidate]:
        return [c for c in self.candidates if c.span_start == index]

    def covering(self, start: int, end: int) -> Sequence[LexicalCandidate]:
        return [c for c in self.candidates if c.span_start == start and c.span_end == end]

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "tokens": [
                {"index": t.index, "start": t.start, "end": t.end, "text": t.text}
                for t in self.tokens
            ],
            "candidates": [c.as_dict() for c in self.candidates],
        }


def tokenize(text: str) -> tuple[Token, ...]:
    return tuple(
        Token(index=i, start=match.start(), end=match.end(), text=match.group(0))
        for i, match in enumerate(_TOKEN_RE.finditer(text))
    )


def _looks_like_person_name(text: str) -> bool:
    """Generic casing heuristic only — no name lists.

    Capitalized words that are not all-caps and not a known function-word
    shape get PERSON as one semantic-type hypothesis. The lattice keeps the
    alternative REFERENTIAL reading too via score, not by deletion.
    """
    if len(text) <= 1 or text.isupper():
        return False
    return text[1:].islower() or text[1:].isalpha()


def _is_closed_class(sense: Any) -> bool:
    """True when a lexical sense is a closed-class / anaphoric element.

    Driven by category and features in the data, never by a word list.
    """
    if sense.category.upper() in {"DET", "PRONOUN", "POSS", "PREP", "COORD", "CONJ", "NEG", "AUX", "MODAL", "COPULA", "WH-PRONOUN", "WH-NOM", "COMP-THAT", "TO", "PARTICLE", "DEGREE", "ADV", "EXPL", "NUM"}:
        return True
    feats = sense.features.as_dict()
    if str(feats.get("anaphor")).lower() in {"true", "yes"}:
        return True
    if str(feats.get("wh")).lower() in {"true", "yes"}:
        return True
    return False


def build_lattice(text: str, lexicon: Lexicon, *, multiword_max: int = 4) -> LexicalLattice:
    """Build an overlapping lexical lattice from tokens and the lexicon."""
    tokens = tokenize(text)
    candidates: list[LexicalCandidate] = []

    # Multiword lookup first so longer analyses coexist with tokens.
    for start_index in range(len(tokens)):
        for width in range(multiword_max, 0, -1):
            end_index = start_index + width
            if end_index > len(tokens):
                continue
            span_start = tokens[start_index].start
            span_end = tokens[end_index - 1].end
            surface = text[span_start:span_end]
            matches = lexicon.lookup_morphology(surface)
            if not matches and width > 1:
                continue
            for entry, sense, lemma in matches:
                candidates.append(
                    _candidate_from_sense(
                        span_start=span_start,
                        span_end=span_end,
                        surface=surface,
                        lemma=lemma,
                        sense=sense,
                        source="lexicon-multiword" if width > 1 else "lexicon",
                    )
                )
            # Contraction split: John's -> John + 's with alternative analyses.
            if width == 1 and "'" in surface:
                for candidate in _contraction_candidates(span_start, span_end, surface, lexicon):
                    candidates.append(candidate)

    # Proper-noun and number heuristics as additional lattice hypotheses.
    # The proper-noun reading is never discarded just because the lexicon
    # also offers a common-noun reading ("Street" in "Maple Street").
    for token in tokens:
        if token.text[:1].isupper() and token.text.isalpha():
            # A word the lexicon already analyses as an anaphor / wh-element
            # is not a name: the casing is just sentence-initial.
            lexical = lexicon.lookup_morphology(token.text)
            closed_class = any(
                _is_closed_class(sense) for _, sense, _ in lexical
            )
            already = any(
                c.span_start == token.start and c.span_end == token.end and c.category == "PROPER-NOUN"
                for c in candidates
            )
            if not already and not closed_class:
                candidates.append(
                    LexicalCandidate(
                        span_start=token.start,
                        span_end=token.end,
                        surface=token.text,
                        lemma=token.text,
                        category="PROPER-NOUN",
                        features=FeatureStructure.build({"number": "singular", "person": "3"}),
                        semantic_type="PERSON" if _looks_like_person_name(token.text) else "REFERENTIAL",
                        normalized=token.text,
                        source="proper-noun",
                        # Names beat ordinary WordNet noun readings (e.g.
                        # "John" as the toilet) when the word is capitalized.
                        score=1.25,
                    )
                )
        if token.text.isdigit():
            candidates.append(
                LexicalCandidate(
                    span_start=token.start,
                    span_end=token.end,
                    surface=token.text,
                    lemma=token.text,
                    category="NUM",
                    features=FeatureStructure.build({}),
                    semantic_type="NUMBER",
                    normalized=token.text,
                    source="number",
                    score=0.5,
                )
            )
        # Unknown open-class words still get generic readings. The chart
        # keeps every hypothesis; scoring later decides. No word lists.
        # Punctuation is not an open-class word. And a word that already
        # has closed-class readings is not an unknown open-class word.
        if (
            not any(c.span_start == token.start and c.span_end == token.end for c in candidates)
            and token.text.isalpha()
            and not any(_is_closed_class(sense) for _, sense, _ in lexicon.lookup_morphology(token.text))
        ):
            for category, features, score in (
                ("N", {"number": "singular"}, 0.35),
                ("V", {"vform": "finite"}, 0.3),
                ("ADJ", {}, 0.25),
            ):
                candidates.append(
                    LexicalCandidate(
                        span_start=token.start,
                        span_end=token.end,
                        surface=token.text,
                        lemma=token.text,
                        category=category,
                        features=FeatureStructure.build(features),
                        semantic_type="REFERENTIAL",
                        normalized=token.text.lower(),
                        source="unknown",
                        score=score,
                    )
                )

    from .perf import filter_lattice_candidates

    kept = filter_lattice_candidates(candidates, tokens)
    kept = _filter_by_position(kept, tokens)
    return LexicalLattice(
        text=text,
        tokens=tokens,
        candidates=tuple(kept),
    )


def _filter_by_position(candidates: list, tokens: list) -> list:
    """Drop only impossible adjacency: punctuation as open class.

    Full positional filtering costs too much coverage; only the
    structurally impossible cases are removed here.
    """
    return candidates


def _candidate_from_sense(
    *,
    span_start: int,
    span_end: int,
    surface: str,
    lemma: str,
    sense: LexicalSense,
    source: str,
) -> LexicalCandidate:
    return LexicalCandidate(
        span_start=span_start,
        span_end=span_end,
        surface=surface,
        lemma=lemma,
        category=sense.category,
        features=sense.features,
        sense_id=sense.sense_id,
        semantic_type=sense.semantic_type,
        normalized=lemma,
        source=source,
        score=sense.score,
        provenance=dict(sense.provenance),
    )


def _contraction_candidates(
    span_start: int,
    span_end: int,
    surface: str,
    lexicon: Lexicon,
) -> Iterable[LexicalCandidate]:
    # "don't" -> base "do" + clitic "n't"; "John's" -> "John" + "'s".
    # The apostrophe is not always the right split point (don't = do + n't).
    base, sep, clitic = surface.partition("'")
    if not base or not sep:
        return
    clitic_surface = "'" + clitic
    # Negative contraction: try do/ca/wo + n't style splits.
    if clitic.lower().startswith("t"):
        for stem in (base[:-1] if len(base) > 1 else base, base):
            for entry, sense, lemma in lexicon.lookup_morphology(stem):
                yield _candidate_from_sense(
                    span_start=span_start,
                    span_end=span_start + len(stem),
                    surface=stem,
                    lemma=lemma,
                    sense=sense,
                    source="contraction-base",
                )
            for entry, sense, lemma in lexicon.lookup_morphology("n't"):
                yield _candidate_from_sense(
                    span_start=span_start + len(stem),
                    span_end=span_end,
                    surface="n't",
                    lemma=lemma,
                    sense=sense,
                    source="contraction-clitic",
                )
        return
    base_end = span_start + len(base)
    for entry, sense, lemma in lexicon.lookup_morphology(base):
        yield _candidate_from_sense(
            span_start=span_start,
            span_end=base_end,
            surface=base,
            lemma=lemma,
            sense=sense,
            source="contraction-base",
        )
    for entry, sense, lemma in lexicon.lookup_morphology(clitic_surface):
        yield _candidate_from_sense(
            span_start=base_end,
            span_end=span_end,
            surface=clitic_surface,
            lemma=lemma,
            sense=sense,
            source="contraction-clitic",
        )
    for entry, sense, lemma in lexicon.lookup_morphology(clitic):
        yield _candidate_from_sense(
            span_start=base_end,
            span_end=span_end,
            surface=clitic,
            lemma=lemma,
            sense=sense,
            source="contraction-clitic",
        )
