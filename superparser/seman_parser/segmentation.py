"""Segmentation and lexical lattice.

Transforms raw text into overlapping lexical candidates without discarding
hypotheses early: tokens, contractions, multiwords and morphology all stay
available to the chart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .features import TOP, Atom, Disjunction, FeatureStructure, Variable
from .lexicon import LexicalSense, Lexicon
from .symbols import intern

_TOKEN_RE = re.compile(
    r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?|[^\w\s\"\u201c\u201d\u2018\u2019]",
    re.UNICODE,
)


@dataclass(frozen=True, slots=True)
class LexicalInterpretation:
    """Stable reference to a lexical sense; no meaning is copied here."""

    sense_id: str | None
    lemma: str
    score: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LexicalCandidate:
    """One hypothesized lexical item over a character span."""

    span_start: int
    span_end: int
    surface: str
    lemma: str
    category: str
    features: FeatureStructure
    normalized: str | None = None
    source: str = "lexicon"
    score: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)
    # Constraints that can change grammatical behaviour. Semantic role
    # labels are deliberately excluded from this signature.
    syntactic_constraints: tuple[Any, ...] = ()
    interpretations: tuple[LexicalInterpretation, ...] = ()
    # Optional opaque reference used by the hierarchical parser.  Ordinary
    # lexical candidates leave it empty; a clause interface points at the
    # clause's existing lazy ParseResult instead of copying its derivations.
    interface: Any | None = field(default=None, repr=False, compare=False)

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
            "sense_ids": list(self.sense_ids),
            "normalized": self.normalized,
            "source": self.source,
            "score": self.score,
            "provenance": dict(self.provenance),
            "syntactic_constraints": list(self.syntactic_constraints),
        }

    @property
    def sense_ids(self) -> tuple[str, ...]:
        ids = tuple(option.sense_id for option in self.interpretations if option.sense_id)
        if ids:
            return ids
        return ()

    @property
    def sense_id(self) -> str | None:
        return self.interpretations[0].sense_id if self.interpretations else None

    def syntactic_signature(self) -> tuple[Any, ...]:
        """Explicit equivalence key for parser-visible lexical behaviour."""
        return (
            self.span_start,
            self.span_end,
            self.category,
            _feature_signature(self.features),
            self.normalized,
            self.syntactic_constraints,
            id(self.interface) if self.interface is not None else None,
        )


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


def build_lattice(
    text: str,
    lexicon: Lexicon,
    *,
    multiword_max: int = 4,
    deduplicate: bool = True,
) -> LexicalLattice:
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

    # Preserve the ordinary word / punctuation path, but also offer one
    # lexical edge across contiguous hyphenated compounds.  This handles
    # productive forms absent from WordNet (``third-grade``) without a word
    # list and without making the hyphen itself a syntactic category.
    occupied_spans = {(candidate.span_start, candidate.span_end) for candidate in candidates}
    candidates.extend(_hyphenated_candidates(text, tokens, lexicon, occupied_spans))

    # Proper-noun and number heuristics as additional lattice hypotheses.
    # The proper-noun reading is never discarded just because the lexicon
    # also offers a common-noun reading ("Street" in "Maple Street").
    # Contractions with a capitalized base ("Theo's") also get a name.
    for token in tokens:
        if "'" in token.text and token.text[:1].isupper():
            base = token.text.split("'", 1)[0]
            if base.isalpha() and len(base) > 1:
                closed = any(
                    _is_closed_class(sense)
                    for _, sense, _ in lexicon.lookup_morphology(base)
                )
                if not closed:
                    candidates.append(
                        LexicalCandidate(
                            span_start=token.start,
                            span_end=token.start + len(base),
                            surface=base,
                            lemma=base,
                            category="PROPER-NOUN",
                            features=FeatureStructure.build({"number": "singular", "person": "3"}),
                            interpretations=(LexicalInterpretation(None, base),),
                            normalized=base,
                            source="proper-noun",
                            score=1.25,
                        )
                    )
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
                        interpretations=(LexicalInterpretation(None, token.text),),
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
                    interpretations=(LexicalInterpretation(None, token.text),),
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
                        interpretations=(LexicalInterpretation(None, token.text),),
                        normalized=token.text.lower(),
                        source="unknown",
                        score=score,
                    )
                )

    from .perf import filter_lattice_candidates

    kept = filter_lattice_candidates(candidates, tokens)
    kept = _filter_by_position(kept, tokens)
    if deduplicate:
        kept = deduplicate_syntactic_candidates(kept)
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
    constraints = _sense_syntactic_constraints(sense)
    interpretation = LexicalInterpretation(
        sense_id=sense.sense_id,
        lemma=lemma,
        score=sense.score,
        provenance=dict(sense.provenance),
    )
    return LexicalCandidate(
        span_start=span_start,
        span_end=span_end,
        surface=surface,
        lemma=lemma,
        category=sense.category,
        features=sense.features,
        normalized=lemma,
        source=source,
        score=sense.score,
        provenance=dict(sense.provenance),
        syntactic_constraints=constraints,
        interpretations=(interpretation,),
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze(child)) for key, child in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    return value


def _feature_signature(features: FeatureStructure) -> tuple[Any, ...]:
    """Hashable signature using already-interned ids (no string conversion)."""
    def value_key(value: Any) -> Any:
        if value is TOP:
            return ("top",)
        if isinstance(value, Atom):
            return ("atom", value.symbol)
        if isinstance(value, Variable):
            return ("var", value.name)
        if isinstance(value, Disjunction):
            return ("or", tuple(value_key(option) for option in value.options))
        if isinstance(value, FeatureStructure):
            return _feature_signature(value)
        return value

    return tuple(sorted((name, value_key(value)) for name, value in features.items()))


_SYNTACTIC_CONSTRAINT_CACHE: dict[int, tuple[LexicalSense, tuple[Any, ...]]] = {}


def _sense_syntactic_constraints(sense: LexicalSense) -> tuple[Any, ...]:
    cached = _SYNTACTIC_CONSTRAINT_CACHE.get(id(sense))
    if cached is not None and cached[0] is sense:
        return cached[1]
    frames = []
    for frame in sense.frames:
        slots = tuple(
            (slot.syntactic, slot.optional, _freeze(slot.features.as_dict()))
            for slot in frame.slots
        )
        frames.append(slots)
    result = (sense.particle, tuple(sorted(frames, key=repr)))
    _SYNTACTIC_CONSTRAINT_CACHE[id(sense)] = (sense, result)
    return result


def deduplicate_syntactic_candidates(
    candidates: Sequence[LexicalCandidate],
) -> list[LexicalCandidate]:
    """Collapse sense-only duplicates while preserving every interpretation."""
    grouped: dict[tuple[Any, ...], LexicalCandidate] = {}
    order: list[tuple[Any, ...]] = []
    for candidate in candidates:
        key = candidate.syntactic_signature()
        previous = grouped.get(key)
        if previous is None:
            grouped[key] = candidate
            order.append(key)
            continue
        options = previous.interpretations + tuple(
            option for option in candidate.interpretations
            if option.sense_id not in {row.sense_id for row in previous.interpretations}
        )
        # The syntax score is one score for this grammatical hypothesis, not
        # a sum or multiplicity bonus for the number of WordNet senses.
        grouped[key] = LexicalCandidate(
            span_start=previous.span_start,
            span_end=previous.span_end,
            surface=previous.surface,
            lemma=previous.lemma,
            category=previous.category,
            features=previous.features,
            normalized=previous.normalized,
            source=previous.source,
            score=max(previous.score, candidate.score),
            provenance={"sources": tuple(filter(None, (previous.provenance, candidate.provenance)))},
            syntactic_constraints=previous.syntactic_constraints,
            interpretations=options,
            interface=previous.interface,
        )
    return [grouped[key] for key in order]


def _hyphenated_candidates(
    text: str,
    tokens: Sequence[Token],
    lexicon: Lexicon,
    occupied_spans: set[tuple[int, int]],
) -> Iterable[LexicalCandidate]:
    open_categories = {"N", "V", "ADJ", "ADV", "NUM"}
    for start in range(len(tokens) - 2):
        first = tokens[start]
        if not first.text.isalpha():
            continue
        end = start
        while end + 2 < len(tokens):
            hyphen = tokens[end + 1]
            head = tokens[end + 2]
            if (
                hyphen.text != "-"
                or first.end > hyphen.start
                or tokens[end].end != hyphen.start
                or hyphen.end != head.start
                or not head.text.isalpha()
            ):
                break
            end += 2
            surface = text[first.start : head.end]
            matches = lexicon.lookup_morphology(surface)
            source = "lexicon-hyphen"
            if matches and (first.start, head.end) in occupied_spans:
                # The ordinary multiword pass already emitted these senses.
                continue
            if not matches:
                # A productive compound inherits the syntactic readings of
                # its rightmost head while keeping its full surface span.
                matches = tuple(
                    match
                    for match in lexicon.lookup_morphology(head.text)
                    if match[1].category in open_categories
                )
                source = "hyphen-compound"
            for _, sense, lemma in matches:
                candidate = _candidate_from_sense(
                    span_start=first.start,
                    span_end=head.end,
                    surface=surface,
                    lemma=lemma,
                    sense=sense,
                    source=source,
                )
                if source == "hyphen-compound":
                    candidate = LexicalCandidate(
                        span_start=candidate.span_start,
                        span_end=candidate.span_end,
                        surface=candidate.surface,
                        lemma=candidate.lemma,
                        category=candidate.category,
                        features=candidate.features,
                        normalized=surface.lower(),
                        source=candidate.source,
                        score=candidate.score - 0.1,
                        provenance=candidate.provenance,
                        syntactic_constraints=candidate.syntactic_constraints,
                        interpretations=candidate.interpretations,
                    )
                yield candidate


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
