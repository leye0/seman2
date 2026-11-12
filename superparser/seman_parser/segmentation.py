"""Segmentation and lexical lattice.

Transforms raw text into overlapping lexical candidates without discarding
hypotheses early: tokens, contractions, multiwords and morphology all stay
available to the chart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

from .features import TOP, Atom, Disjunction, FeatureStructure, Variable, coerce
from .lexicon import LexicalSense, Lexicon
from .symbols import intern

_TOKEN_RE = re.compile(
    r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?|[^\w\s\"\u201c\u201d\u2018\u2019]",
    re.UNICODE,
)

# The fixed 16-point compass rose is a closed notation system, not an
# open-class word-guessing heuristic. A dotted bearing (N.N.E., E.S.E., W.)
# is one lexical span; its constituent letter and period readings remain in
# the original lattice as independent alternatives.
_DOTTED_COMPASS_RE = re.compile(r"(?<![A-Za-z.])(?:[NSEW]\.){1,3}(?![A-Za-z])")
_COMPASS_ROSE = frozenset({
    "N", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW",
    "WSW", "W", "WNW", "NW", "NNW", "NNE",
})


def _compass_notation_candidates(text: str, base: list[LexicalCandidate]) -> list[LexicalCandidate]:
    """Retain the ordinary letters while adding exact dotted compass spans."""
    views = []
    for match in _DOTTED_COMPASS_RE.finditer(text):
        bearing = match.group().replace(".", "")
        if bearing not in _COMPASS_ROSE:
            continue
        views.append(LexicalCandidate(
            span_start=match.start(), span_end=match.end(),
            surface=match.group(), lemma=bearing.casefold(),
            category="COMPASS-POINT",
            features=FeatureStructure.build({"compass_point": "true"}),
            normalized=bearing,
            interpretations=(LexicalInterpretation(
                None, bearing.casefold(), provenance={"system": "16_point_compass_rose"}),),
            source="compass-notation", score=0.75,
            provenance={"construction": "dotted_compass_abbreviation",
                        "system": "16_point_compass_rose"},
        ))
    if len(views) >= 2:
        # Only a notation with at least two attested compass points can
        # license a terminal stop for the dedicated bearing/measure record.
        views.extend(replace(candidate, category="NOTATION-STOP")
                     for candidate in base
                     if candidate.surface == "." and candidate.span_end == len(text))
        # Bind the opening of a location/bearing note to an attested name
        # BEFORE the first compass direction. Without this typed anchor, a
        # general NP-leading reference rule would start inside essentially
        # every sentence, including long dialogues close to their budget.
        first_point = min(view.span_start for view in views
                          if view.category == "COMPASS-POINT")
        views.extend(replace(candidate, category="NOTATION-PLACE-START")
                     for candidate in base
                     if candidate.category == "PROPER-NOUN"
                     and candidate.span_start == 0
                     and candidate.span_end < first_point)
    return views


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
                if not _surface_matches_morphology(surface, entry, sense, lemma):
                    continue
                candidate = _candidate_from_sense(
                    span_start=span_start,
                    span_end=span_end,
                    surface=surface,
                    lemma=lemma,
                    sense=sense,
                    source="lexicon-multiword" if width > 1 else "lexicon",
                )
                candidates.append(candidate)
                # Finite *are* and *were* are plural for all persons but
                # ALSO singular for second-person *you*. Preserve both
                # grammatical feature bundles instead of loosening either
                # number or person unification globally. This is an
                # inflectional paradigm property, independent of the corpus.
                if (
                    width == 1
                    and surface.casefold() in {"are", "were"}
                    and candidate.category in {"COPULA", "AUX-BE", "V"}
                    and candidate.lemma.casefold() in {"be", "was", "is", "are"}
                    and candidate.features.as_dict().get("vform") == "finite"
                ):
                    alternate_features = {
                        **candidate.features.as_dict(),
                        "number": "singular", "person": "2",
                    }
                    candidates.append(replace(
                        candidate,
                        features=FeatureStructure.build(alternate_features),
                        provenance={
                            **candidate.provenance,
                            "agreement_variant": "second-person-singular",
                        },
                    ))
            # Contraction split: John's -> John + 's with alternative analyses.
            if width == 1 and "'" in surface:
                for candidate in _contraction_candidates(span_start, span_end, surface, lexicon):
                    candidates.append(candidate)

    # Project Gutenberg's curly apostrophes ('don’t', 'I’ll', 'John’s')
    # must have the same productive morpheme hypotheses as ASCII clitics.
    # Keep tokenize() unchanged for stable corpus offsets and cohort SHA.
    for match in re.finditer(r"[A-Za-z]+\u2019[A-Za-z]+", text):
        normalized = match.group(0).replace("\u2019", "'")
        # Full-spelling lexical readings (e.g. dialectal "ain't") must
        # survive curly apostrophes just as clitic splits do. Only an
        # independently attested dictionary sense can license one; never
        # promote orthographic shape or fabricate a missing inflection.
        for entry, sense, lemma in lexicon.lookup_morphology(normalized):
            if not _surface_matches_morphology(normalized, entry, sense, lemma):
                continue
            candidates.append(_candidate_from_sense(
                span_start=match.start(), span_end=match.end(),
                surface=match.group(0), lemma=lemma, sense=sense,
                source="typographic-full-lexicon",
            ))
        for candidate in _contraction_candidates(
            match.start(), match.end(), normalized, lexicon,
        ):
            source = text[candidate.span_start:candidate.span_end]
            candidates.append(replace(
                candidate, surface=source,
                source="typographic-" + candidate.source,
            ))


    # A plural genitive has an overt apostrophe but no additional s.
    # Offer a separate clitic edge; keep quotation and token hypotheses intact.
    for match in re.finditer(r"\b([A-Za-z]+s)(['\u2019])(?=\s+[A-Za-z])", text, re.I):
        stem_end = match.end(1)
        plural_noun = any(
            c.span_start == match.start(1) and c.span_end == stem_end
            and c.category == "N"
            and c.features.as_dict().get("number") == "plural"
            for c in candidates
        )
        if plural_noun:
            candidates.append(LexicalCandidate(
                span_start=match.start(2), span_end=match.end(2),
                surface=match.group(2), lemma="'", category="POSS",
                features=FeatureStructure.build({"genitive_clitic": "true"}),
                score=1.0, source="plural-genitive-apostrophe",
                provenance={"construction": "overt_plural_s_genitive"},
            ))
    # Keep exclamative punctuation distinct from commas (without removing
    # the existing legacy COMMA hypothesis for '!').
    for mark in re.finditer(r"!", text):
        candidates.append(LexicalCandidate(
            span_start=mark.start(), span_end=mark.end(), surface="!",
            lemma="!", category="EXCLMARK",
            features=FeatureStructure.empty(), score=0.8,
            source="punctuation-exclamation",
            provenance={"construction": "exclamative_delimiter"},
        ))

    # Productive historical day compounds (to-day, to-night, to-morrow)
    # have exactly the same lexical categories as today/tonight/tomorrow.
    # Treat this as a lexical alias spanning the full original spelling;
    # do not change tokenization or silently rewrite the novel text.
    for match in re.finditer(r"\bto-(?:day|night|morrow)\b", text, re.I):
        surface = match.group(0)
        lookup = surface.replace("-", "").lower()
        for _entry, sense, lemma in lexicon.lookup_morphology(lookup):
            candidate = _candidate_from_sense(
                span_start=match.start(), span_end=match.end(),
                surface=surface, lemma=lemma, sense=sense,
                source="historical-day-spelling",
            )
            candidates.append(replace(
                candidate, provenance={
                    **candidate.provenance,
                    "source_spelling": surface,
                    "normalized_spelling": lookup,
                    "normalization": "historical_hyphenated_day",
                },
            ))

    # Preserve the ordinary word / punctuation path, but also offer one
    # lexical edge across contiguous hyphenated compounds.  This handles
    # productive forms absent from WordNet (``third-grade``) without a word
    # list and without making the hyphen itself a syntactic category.
    occupied_spans = {(candidate.span_start, candidate.span_end) for candidate in candidates}
    candidates.extend(_hyphenated_candidates(text, tokens, lexicon, occupied_spans))

    # Attested English placeholder names ('what's-his-name',
    # 'who's-her-name') are single nominal lexical units even though their
    # orthography contains an apostrophe and multiple hyphens. The ordinary
    # token, pronoun, verb and clitic readings remain in the lattice.
    # The *lexicon* must positively license each complete spelling:
    # matching this orthographic shape alone never creates a noun.
    # The final possessive/copular "'s" in "what's-his-name's" is NOT
    # swallowed by the placeholder name; it remains its own morpheme.
    for match in re.finditer(
        r"(?<![A-Za-z])(?:what|who)[\u0027\u2019]s-(?:his|her|their)-name\b",
        text, re.I,
    ):
        surface = match.group(0)
        normalized = surface.replace("\u2019", "'").casefold()
        for _entry, sense, lemma in lexicon.lookup_morphology(normalized):
            if sense.category != "N":
                continue
            candidates.append(replace(
                _candidate_from_sense(
                    span_start=match.start(), span_end=match.end(),
                    surface=surface, lemma=lemma, sense=sense,
                    source="lexicalized-placeholder-name",
                ),
                provenance={
                    "source": "attested-placeholder-name-inventory",
                    "orthographic_expression": normalized,
                    "trailing_clitic_retained": True,
                },
            ))

    # In Gutenberg prose, "--" represents an em dash, not two separate
    # single-hyphen words. Add ONE spanning punctuation edge; do NOT alter
    # tokenize() or the pinned corpus's token positions/length strata.
    # Lone hyphens retain their ordinary compound/minus behaviour.
    for mark in re.finditer(r"--+|[\u2013\u2014]", text):
        surface = mark.group(0)
        # The legacy COMMA edge remains for existing grammar compatibility,
        # while DASH is a distinct syntactic hypothesis for appositions,
        # interruptions and explanatory --...-- parentheses. No source text
        # or historical cohort token offset is normalized in place.
        candidates.append(LexicalCandidate(
            span_start=mark.start(), span_end=mark.end(),
            surface=surface, lemma="—", normalized="—",
            category="DASH",
            features=FeatureStructure.build({"dash_kind": "em"}),
            source="punctuation-dash", score=0.9,
            provenance={"construction": "em_dash_delimiter", "source": "orthography"},
            interpretations=(LexicalInterpretation(None, "—"),),
        ))
        candidates.append(LexicalCandidate(
            span_start=mark.start(), span_end=mark.end(),
            surface=surface, lemma="—", normalized="—",
            category="COMMA",
            features=FeatureStructure.empty(),
            source="punctuation-dash",
            score=0.75,
            provenance={"construction":"em_dash_boundary", "source":"orthography"},
            interpretations=(LexicalInterpretation(None, "—"),),
        ))


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
    # Dictionary-attested names may contain lower-case elisions (Em'ly).
    # Match the complete spelling before splitting a final possessive suffix.
    # Never infer a name merely from apostrophe shape; preserve tokens/offsets.
    for match in re.finditer(r"\b[A-Za-z]+(?:['’][A-Za-z]+)+", text):
        surface = match.group(0)
        normalized = surface.replace("’", "'")
        name = normalized[:-2] if normalized.casefold().endswith("'s") else normalized
        name_end = match.start() + len(name)
        licensed = False
        for _entry, sense, lemma in lexicon.lookup_morphology(name):
            if sense.category != "PROPER-NOUN" or "'" not in name:
                continue
            licensed = True
            candidates.append(_candidate_from_sense(
                span_start=match.start(), span_end=name_end,
                surface=text[match.start():name_end], lemma=lemma,
                sense=sense, source="attested-apostrophe-name",
            ))
        if licensed and name_end < match.end():
            for _entry, sense, lemma in lexicon.lookup_morphology("'s"):
                candidates.append(_candidate_from_sense(
                    span_start=name_end, span_end=match.end(),
                    surface=text[name_end:match.end()], lemma=lemma,
                    sense=sense, source="attested-name-clitic",
                ))

    # Internal apostrophes in surnames (O'Brien, D'Artagnan, M'Graw)
    # are not possessive/contraction clitics. The uppercase continuation
    # distinguishes them from John's, I've, we'd, etc. Keep every other
    # lexical hypothesis and the original source span unchanged.
    for token in tokens:
        if re.fullmatch(r"[A-Z][A-Za-z]*['’][A-Z][A-Za-z]+", token.text):
            if not any(
                c.span_start == token.start and c.span_end == token.end
                and c.category == "PROPER-NOUN" for c in candidates
            ):
                candidates.append(LexicalCandidate(
                    span_start=token.start,
                    span_end=token.end,
                    surface=token.text,
                    lemma=token.text,
                    category="PROPER-NOUN",
                    features=FeatureStructure.build(
                        {"number": "singular", "person": "3"}
                    ),
                    interpretations=(LexicalInterpretation(None, token.text),),
                    normalized=token.text,
                    source="proper-noun-apostrophe",
                    score=1.25,
                    provenance={"construction": "internal_apostrophe_proper_name"},
                ))
    # The legacy tokenizer may split curly apostrophes into separate tokens.
    # Add the same full-span surname hypothesis without re-tokenizing or
    # disturbing the fixed Gutenberg cohort's byte-for-byte offsets.
    for match in re.finditer(r"\b[A-Z][A-Za-z]*’[A-Z][A-Za-z]+\b", text):
        if not any(
            c.span_start == match.start() and c.span_end == match.end()
            and c.category == "PROPER-NOUN" for c in candidates
        ):
            surface = match.group(0)
            candidates.append(LexicalCandidate(
                span_start=match.start(), span_end=match.end(),
                surface=surface, lemma=surface, normalized=surface,
                category="PROPER-NOUN",
                features=FeatureStructure.build(
                    {"number": "singular", "person": "3"}
                ),
                interpretations=(LexicalInterpretation(None, surface),),
                source="proper-noun-apostrophe", score=1.25,
                provenance={"construction": "internal_apostrophe_proper_name"},
            ))
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
                ("V", {"vform": "finite", "unknown": "true"}, 0.3),
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

    candidates = _apply_lexical_priors(candidates, tokens)

    from .perf import filter_lattice_candidates

    kept = filter_lattice_candidates(candidates, tokens)
    kept = _filter_by_position(kept, tokens)
    # Correlative negation and complex-transitive infinitival questions need
    # **contextual lexical starters**. A generic DET, HAVE or V first symbol
    # adds chart partials throughout long quotations (case 359 lies near the
    # fixed 50k-item budget). Do not remove or rewrite their source readings.
    def follows(left: LexicalCandidate, right: LexicalCandidate) -> bool:
        return (right.span_start > left.span_end
                and text[left.span_end:right.span_start].isspace())

    negative_correlative_det_views = []
    for determinant in kept:
        if (determinant.category != "DET" or
                determinant.features.as_dict().get("negation") != "true"):
            continue
        if any(
            follows(determinant, noun)
            and follows(noun, coordinator)
            for noun in kept if noun.category == "N"
            for coordinator in kept if coordinator.category == "COORD"
            and coordinator.features.as_dict().get("negation") == "true"
            and coordinator.features.as_dict().get("nominal_coordination") == "true"
        ):
            negative_correlative_det_views.append(
                replace(determinant, category="DET-NEG-CORR"))

    negative_have_views = [
        replace(have, category="HAVE-NEG-CORR")
        for have in kept if have.category == "HAVE"
        and have.features.as_dict().get("vform") == "finite"
        and any(follows(have, det) for det in negative_correlative_det_views)
    ]

    complex_wh_infinitive_views = []
    to_markers = [c for c in kept if c.category == "TO"]
    wh_markers = [c for c in kept if c.category == "WH-NOM"
                  and c.features.as_dict().get("wh") == "true"]
    clausal_bases = [c for c in kept if c.category == "V"
                     and c.features.as_dict().get("vform") == "base"
                     and (c.features.as_dict().get("subcat") == "clausal"
                          or isinstance(c.features.as_dict().get("subcat"), list)
                          and "clausal" in c.features.as_dict()["subcat"])]
    object_starts = [c for c in kept if c.category in {
        "PRONOUN", "DET", "POSS", "N", "PROPER-NOUN", "TITLE"
    }]
    for verb in kept:
        features = verb.features.as_dict()
        valence = features.get("subcat")
        if (verb.category != "V" or features.get("vform") != "finite"
                or not (valence == "complex_transitive" or
                        isinstance(valence, list) and "complex_transitive" in valence)):
            continue
        if any(
            follows(verb, obj) and follows(obj, to)
            and follows(to, predicate) and follows(predicate, wh)
            and to.span_start - verb.span_end <= 50
            for obj in object_starts for to in to_markers
            for predicate in clausal_bases for wh in wh_markers
        ):
            complex_wh_infinitive_views.append(
                replace(verb, category="V-COMPLEX-WH-INF"))
    # A typed lexical view keeps nominal-predicate searches from opening at
    # every V span. Retain the original V and all its sense/span provenance;
    # only positively attested base complex-transitive readings get this view.
    nominal_heads = []
    for candidate in kept:
        features = candidate.features.as_dict()
        valence = features.get("subcat")
        if (candidate.category == "V" and features.get("vform") == "base"
                and (valence == "complex_transitive" or
                     isinstance(valence, list) and "complex_transitive" in valence)):
            nominal_heads.append(replace(candidate, category="V-NOMINAL-PRED"))
    # The prenominal construction consumes an adjacent lexical adverb and
    # an attested transitive past participle. Project only complete lexical
    # pairs: opening this search at every ADV exhausts the fixed forest budget.
    # Original readings, senses and source spans are always retained.
    participial_views = []
    adverbs = [c for c in kept if c.category == "ADV"]
    for candidate in kept:
        features = candidate.features.as_dict()
        valence = features.get("subcat")
        if (candidate.category == "V" and features.get("vform") == "ed"
                and (valence == "transitive" or
                     isinstance(valence, list) and "transitive" in valence)):
            adjacent = [adv for adv in adverbs
                        if adv.span_end < candidate.span_start
                        and text[adv.span_end:candidate.span_start].isspace()]
            if adjacent:
                participial_views.append(replace(candidate, category="V-PRENOMINAL-PASSIVE"))
                participial_views.extend(replace(adv, category="ADV-PRENOMINAL-PASSIVE")
                                         for adv in adjacent)
    # Open supplementary participial searches only at attested transitive
    # present participles. Keep the V candidate and all lexical provenance.
    present_participles = []
    intransitive_gerunds = []
    for candidate in kept:
        features = candidate.features.as_dict()
        valence = features.get("subcat")
        if (candidate.category == "V" and features.get("vform") == "ing"
                and (valence == "transitive" or
                     isinstance(valence, list) and "transitive" in valence)):
            present_participles.append(replace(candidate, category="V-TRANSITIVE-ING"))
        if (candidate.category == "V" and features.get("vform") == "ing"
                and (valence == "intransitive" or
                     isinstance(valence, list) and "intransitive" in valence)):
            intransitive_gerunds.append(replace(candidate, category="V-INTRANSITIVE-ING"))
    # A delimited temporal incise licenses an infinitival-subject construction.
    # Do not open that expensive seven-symbol rule at every TO in unrelated
    # prose. The contextual view is only an anchor: grammar still validates
    # both commas, the finite subordinate clause and matrix VP. Preserve TO.
    temporal_markers = [c for c in kept if c.category == "CONJ"
                        and c.features.as_dict().get("temporal_incise") == "true"]
    literal_commas = [c for c in kept if c.category == "COMMA" and c.surface == ","]
    # A reduced conditional adjective is only licensed by the complete
    # overt sequence ", if ADJ," (not by an arbitrary comma or adjective).
    # Type the *opening punctuation*, then allow a finite ditransitive verb
    # before it to start the corresponding valence rule. This keeps dormant
    # grammar rules out of unrelated large forests, notably dialogue #359.
    # No word surface is matched: conjunction features, word classes, comma
    # adjacency and independently attested ditransitive valence are decisive.
    conditional_conjunctions = [
        c for c in kept if c.category == "CONJ"
        and c.features.as_dict().get("complementizer") == "conditional"
    ]
    conditional_adjectives = [c for c in kept if c.category == "ADJ"]
    conditional_openings = [
        opening for opening in literal_commas
        if any(
            opening.span_end < conjunction.span_start
            and text[opening.span_end:conjunction.span_start].isspace()
            and conjunction.span_end < adjective.span_start
            and text[conjunction.span_end:adjective.span_start].isspace()
            and adjective.span_end == closing.span_start
            for conjunction in conditional_conjunctions
            for adjective in conditional_adjectives
            for closing in literal_commas
        )
    ]
    conditional_punctuation_views = [
        replace(opening, category="COMMA-REDUCED-CONDITIONAL")
        for opening in conditional_openings
    ]
    conditional_ditransitive_views = []
    for candidate in kept:
        if candidate.category != "V" or candidate.features.as_dict().get("vform") != "finite":
            continue
        valence = candidate.features.as_dict().get("subcat")
        if valence != "ditransitive" and not (
            isinstance(valence, (list, tuple)) and "ditransitive" in valence
        ):
            continue
        if any(candidate.span_end < opening.span_start
               for opening in conditional_openings):
            conditional_ditransitive_views.append(
                replace(candidate, category="V-DITRANSITIVE-CONDITIONAL")
            )
    # Preposed nominal focus belongs to the clause rather than inventing a
    # DEGREE-headed NP. Require positive nominal-focus evidence followed by
    # an overt subject start; the grammar will still check NP and finite VP.
    nominal_starts = [c for c in kept if c.category in {
        "PRONOUN", "DET", "POSS", "PROPER-NOUN", "TITLE"
    }]
    preposed_subject_focus_views = [
        replace(adverb, category="ADV-PREPOSED-SUBJECT-FOCUS")
        for adverb in kept if adverb.category == "ADV"
        and adverb.features.as_dict().get("nominal_focus") == "true"
        and any(adverb.span_end < subject.span_start
                and text[adverb.span_end:subject.span_start].isspace()
                for subject in nominal_starts)
    ]
    temporal_subject_markers = []
    for candidate in kept:
        if candidate.category != "TO":
            continue
        if any(
            candidate.span_end < pre.span_start and pre.span_end <= marker.span_start
            and marker.span_end < post.span_start
            for marker in temporal_markers for pre in literal_commas
            for post in literal_commas
        ):
            temporal_subject_markers.append(replace(candidate, category="TO-TEMPORAL-SUBJECT"))
    # A postposed PP-relative can supplement the whole demonstrative partitive
    # in an equative standard: "so calm and clear as that of X, through which...".
    # Without this contextual anchor, opening the supplementary NP construction
    # at every DET/NP saturates complex dialogue (pinned case 359). Only project
    # a typed DET where the lexical evidence for the equative and partitive
    # structure exists. The grammar still has to validate all attachments.
    equative_degrees = [c for c in kept if c.category == "DEGREE"
                        and c.features.as_dict().get("equative_so") == "true"]
    equative_as = [c for c in kept if c.category == "CONJ"
                   and c.features.as_dict().get("degree") == "true"
                   and c.surface.lower() == "as"]
    partitive_of = [c for c in kept if c.category == "PREP"
                    and c.features.as_dict().get("nominal_complement") == "of"]
    relative_obliques = [c for c in kept if c.category == "WH-REL-OBL"]
    equative_partitive_markers = []
    for candidate in kept:
        if candidate.category != "DET":
            continue
        if any(
            degree.span_end < marker.span_start
            and marker.span_end < candidate.span_start
            and text[marker.span_end:candidate.span_start].isspace()
            and candidate.span_end < of.span_start
            and text[candidate.span_end:of.span_start].isspace()
            and of.span_end < comma.span_start < relative.span_start
            for degree in equative_degrees for marker in equative_as
            for of in partitive_of for comma in literal_commas
            for relative in relative_obliques
        ):
            equative_partitive_markers.append(
                replace(candidate, category="DET-EQUATIVE-PARTITIVE"))
    # The adjective "other" selects a following than-standard only when
    # an overt nominal head and comparative than are adjacent. A typed view
    # avoids opening a new nominal-comparison search at every literary
    # "other" (notably case 359: "far other plans" without a standard).
    # The original WordNet adjective and all its senses remain untouched.
    comparative_than = [c for c in kept if c.category == "PREP"
                        and c.features.as_dict().get("comparative") == "true"]
    comparative_other_views = []
    for candidate in kept:
        if candidate.category != "ADJ" or candidate.lemma.casefold() != "other":
            continue
        if any(
            candidate.span_end < noun.span_start < than.span_start
            and text[candidate.span_end:noun.span_start].isspace()
            and text[noun.span_end:than.span_start].isspace()
            for noun in kept if noun.category == "N"
            for than in comparative_than
        ):
            comparative_other_views.append(
                replace(candidate, category="ADJ-OTHER-THAN"))
    comparative_degree_other_views = []
    for candidate in kept:
        if (candidate.category != "ADV" or
                candidate.features.as_dict().get("comparative_modifier") != "true"):
            continue
        if any(
            candidate.span_end < other.span_start
            and text[candidate.span_end:other.span_start].isspace()
            and other.span_start - candidate.span_end <= 2
            for other in comparative_other_views
        ):
            comparative_degree_other_views.append(
                replace(candidate, category="ADV-DEGREE-OTHER-THAN"))
    # Bind longer compositional rules to independent overt lexical evidence,
    # rather than starting their chart partials on every HAVE, PREP or DET.
    # The original candidates and WordNet senses are never replaced.
    possession_degree_views = []
    degree_adverbs = [c for c in kept if c.category == "ADV"
                      and c.features.as_dict().get("possessive_degree") == "true"]
    for candidate in kept:
        if candidate.category != "HAVE" or candidate.features.as_dict().get("vform") != "finite":
            continue
        if any(
            candidate.span_end < degree.span_start < det.span_start
            and text[candidate.span_end:degree.span_start].isspace()
            and text[degree.span_end:det.span_start].isspace()
            and degree.span_start - candidate.span_end <= 2
            and det.span_start - degree.span_end <= 2
            for degree in degree_adverbs for det in kept if det.category == "DET"
        ):
            possession_degree_views.append(
                replace(candidate, category="HAVE-DEGREE-NP"))

    relative_prep_views = []
    poss_relatives = [c for c in kept if c.category == "WH-REL-POSS"]
    nouns = [c for c in kept if c.category == "N"]
    for candidate in kept:
        if candidate.category != "PREP":
            continue
        if any(
            candidate.span_end < noun.span_start
            and noun.span_end == first.span_start
            and first.span_end < relative.span_start
            and text[first.span_end:relative.span_start].isspace()
            and relative.span_end < last.span_start
            for noun in nouns for first in literal_commas
            for relative in poss_relatives for last in literal_commas
        ):
            relative_prep_views.append(
                replace(candidate, category="PREP-WHOSE-REL"))

    coordinated_partitive_views = []
    for candidate in kept:
        if (candidate.category != "DET" or
                candidate.features.as_dict().get("anaphor") != "true"):
            continue
        if any(
            candidate.span_end < of.span_start
            and text[candidate.span_end:of.span_start].isspace()
            and of.span_start - candidate.span_end <= 2
            for of in partitive_of
        ):
            coordinated_partitive_views.append(
                replace(candidate, category="DET-COORD-PARTITIVE"))
    # Multiple right-edge, nonfinite supplements need lexical anchors. A
    # generic NP + participle rule starts at almost every nominal and can
    # exhaust the fixed dialogue budget (#359). Project only lexical views
    # supported by a locative copula, delimited passive supplement, and the
    # coordinated -ing / passive absolute evidence in the *same* sentence.
    absolute_views = []
    passive_verbs = [c for c in kept if c.category == "V"
                     and c.features.as_dict().get("vform") == "ed"]
    by_markers = [c for c in kept if c.category == "PREP-BY"]
    if (len(literal_commas) >= 3 and intransitive_gerunds and passive_verbs
            and by_markers):
        for candidate in kept:
            if candidate.category == "PRONOUN" and any(
                candidate.span_end < cop.span_start < adv.span_start
                and adv.span_end < comma.span_start
                for cop in kept if cop.category == "COPULA"
                and cop.features.as_dict().get("vform") == "finite"
                for adv in kept if adv.category == "ADV"
                for comma in literal_commas
            ):
                absolute_views.append(replace(candidate, category="PRONOUN-SUPPLEMENT-ABS"))
            if candidate.category == "POSS" and any(
                comma.span_end < candidate.span_start < ing.span_start
                or comma.span_end < candidate.span_start < by.span_start
                for comma in literal_commas[2:]
                for ing in intransitive_gerunds for by in by_markers
            ):
                absolute_views.append(replace(candidate, category="POSS-SUPPLEMENT-ABS"))
            if candidate in passive_verbs and any(
                comma.span_end < candidate.span_start < prep.span_start
                and prep.span_start - candidate.span_end <= 2
                for comma in literal_commas[1:]
                for prep in kept if prep.category == "PREP"
            ):
                absolute_views.append(replace(candidate, category="V-SUPPLEMENT-ED"))
    kept = [*kept, *negative_correlative_det_views, *negative_have_views,
            *complex_wh_infinitive_views, *conditional_punctuation_views,
            *conditional_ditransitive_views, *preposed_subject_focus_views,
            *nominal_heads, *participial_views, *present_participles,
            *intransitive_gerunds, *temporal_subject_markers,
            *equative_partitive_markers, *comparative_other_views,
            *comparative_degree_other_views,
            *possession_degree_views, *relative_prep_views,
            *coordinated_partitive_views,
            *absolute_views]
    kept.extend(_compass_notation_candidates(text, kept))
    # A surface that already has an overt determiner reading must not be
    # silently recycled as an attributive noun modifier. Keep its original N
    # candidate (letter names and other homographs are still legitimate), but
    # expose the lexical competition as a feature to the noun-compound rule.
    # This uses category evidence, never a list of individual function words.
    determiner_spans = {
        (candidate.span_start, candidate.span_end)
        for candidate in kept if candidate.category == "DET"
    }
    kept = [
        replace(candidate, features=candidate.features.with_feature(
            "determiner_homograph", Atom.of("true")))
        if candidate.category == "N" and (
            candidate.span_start, candidate.span_end) in determiner_spans
        else candidate
        for candidate in kept
    ]
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


def _surface_matches_morphology(
    surface: str,
    entry: Any,
    sense: LexicalSense,
    lemma: str,
) -> bool:
    """Reject WordNet feature variants contradicted by the written form."""
    written = surface.casefold()
    base = lemma.replace("_", " ").casefold()
    # Closed-class forms share seed entries; a base-form DO sense is
    # not licensed on an inflected 'did' or 'does' surface.
    if base == "do" and sense.category == "V":
        if written in {"does", "did"} and sense.features.as_dict().get("vform") == "base":
            return False
    if entry.provenance.get("source") != "wordnet":
        return True
    features = sense.features
    vform = features.get("vform")
    if isinstance(vform, Atom):
        if written == base:
            return vform.name in {"base", "finite"}
        if written.endswith("ing"):
            return vform.name == "ing"
        if written.endswith(("ed", "ied")):
            return vform.name in {"finite", "ed"}
        if written.endswith("s"):
            return vform.name == "finite"
        # Irregular non-lemma forms (went, taken, ...): retain finite and
        # participial readings, but never an impossible base/gerund reading.
        return vform.name in {"finite", "ed"}
    number = features.get("number")
    if isinstance(number, Atom):
        if written == base:
            return number.name == "singular"
        return number.name == "plural"
    return True


def _apply_lexical_priors(
    candidates: Sequence[LexicalCandidate],
    tokens: Sequence[Token],
) -> list[LexicalCandidate]:
    """Apply grammatical priors without deleting genuine homographs."""
    by_span: dict[tuple[int, int], list[LexicalCandidate]] = {}
    for candidate in candidates:
        by_span.setdefault(candidate.span, []).append(candidate)
    first_word_start = next((token.start for token in tokens if token.text.isalpha()), None)
    closed = {
        "DET", "PRONOUN", "POSS", "PREP", "PREP-BY", "COORD", "CONJ",
        "NEG", "AUX", "AUX-BE", "MODAL", "COPULA", "WH-PRONOUN",
        "WH-NOM", "COMP-THAT", "TO", "PARTICLE", "DEGREE", "EXPL", "NUM",
    }
    open_class = {"N", "V", "ADJ", "ADV"}
    adjusted: list[LexicalCandidate] = []
    for candidate in candidates:
        peers = by_span[candidate.span]
        score = candidate.score
        if candidate.category in open_class and candidate.provenance.get("source") == "wordnet":
            if any(peer.category in closed and peer.source == "lexicon" for peer in peers):
                # Preserve true homographs, but a WordNet open-class sense of
                # a known function word (there=N, that=N, can=N) must not beat
                # the explicit grammatical inventory merely because a
                # shallower tree can consume it.
                # A closed-class analysis is overwhelming evidence against
                # obscure WordNet homographs (e.g. ``who`` as an N).  Keep
                # the reading in the lattice for diagnostics, but prevent a
                # cheap compound rule from outranking the WH construction.
                score -= 3.0
        if (
            candidate.category == "ADV"
            and candidate.surface.casefold().endswith("ly")
            and any(peer.category != "ADV" for peer in peers)
        ):
            # Productive -ly is strong morphological evidence when WordNet
            # itself supplies the adverb reading.  Homographs remain in the
            # lattice; this only breaks an otherwise arbitrary tie.
            score += 0.5
        if candidate.category == "PROPER-NOUN" and candidate.span_start == first_word_start:
            written = candidate.surface.casefold()
            morphologically_common = any(
                # A lexical TITLE is positive grammatical evidence of an
                # honorific role. The generic uppercase PROPER-NOUN edge
                # remains in the lattice, but casing alone must not outrank
                # an attested "Doctor Watson" or "Captain Nemo" title.
                (peer.category == "TITLE"
                 and peer.features.as_dict().get("honorific") == "true")
                or peer.category == "ADJ"
                or peer.category == "ADV"
                or (
                    peer.category == "N"
                    and peer.features.as_dict().get("number") == "plural"
                    and sum(
                        other.category == "N"
                        and other.features.as_dict().get("number") == "plural"
                        for other in peers
                    ) > 1
                )
                or (
                    peer.category == "V"
                    and written.endswith("ing")
                    and peer.features.as_dict().get("vform") == "ing"
                )
                for peer in peers
            )
            if morphologically_common:
                # Sentence casing alone must not turn a morphologically clear
                # plural/participle into a name.  This has to overcome the
                # intentionally larger structural score of ``np_proper``.
                score -= 1.5
        adjusted.append(candidate if score == candidate.score else replace(candidate, score=score))
    return adjusted


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
    features = _project_syntactic_features(sense)
    # BE's predicative nominals are complements, not direct-object gaps.
    # Keep its WordNet V hypotheses and senses, but map transitive-looking
    # frames of the closed-class BE paradigm to linking syntax.
    if sense.category == "V" and lemma.casefold() in {"be", "was", "is", "are"}:
        current = features.as_dict()
        subcat = current.get("subcat")
        values = (list(subcat) if isinstance(subcat, (list, tuple))
                  else [subcat] if subcat is not None else [])
        if "transitive" in values:
            projected = list(dict.fromkeys(
                "linking" if value == "transitive" else value
                for value in values
            ))
            features = FeatureStructure.build({
                **current,
                "subcat": projected[0] if len(projected) == 1 else projected,
            })
    # Attach *surface-proven* agreement rather than treating all inflected
    # forms in a shared BE lexical entry as interchangeable.
    if (sense.category in {"COPULA", "AUX-BE", "V"} and (
        lemma.casefold() in {"be", "was", "is", "are"} or sense.semantic_type == "BE"
    )):
        agreement = {
            "is": {"number": "singular", "person": "3"},
            "are": {"number": "plural"},
            "was": {"number": "singular"},
            "were": {"number": "plural"},
            "am": {"number": "singular", "person": "1"},
        }.get(surface.casefold())
        if agreement:
            # The original shared BE sense can carry the agreement of a
            # *different* surface (is/are/was/were). Replace both axes
            # atomically: inherited 'person=3' must not leak into 'are'.
            inflection_neutral = {
                k: v for k, v in features.as_dict().items()
                if k not in {"number", "person"}
            }
            features = FeatureStructure.build({**inflection_neutral, **agreement})
    if (sense.category == "COPULA" and sense.semantic_type == "BE"
            and surface.casefold() == "be"):
        # The infinitive 'be' after modals has base form, unlike is/are.
        # Preserve the original alternatives for all other surfaces.
        features = FeatureStructure.build({
            **{k: v for k, v in features.as_dict().items()
               if k not in {"number", "person"}}, "vform": "base",
        })
    if sense.category == "V" and (
        features.as_dict().get("vform") == "finite"
        and surface.casefold().endswith("s")
        and surface.casefold() != lemma.casefold()
        and not lemma.casefold().endswith("s")
    ):
        # Productive present third singular. Leave base and past
        # morphology open instead of inventing a number/person constraint.
        features = FeatureStructure.build({
            **features.as_dict(), "number": "singular", "person": "3",
        })
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
        features=features,
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


def _project_syntactic_features(sense: LexicalSense) -> FeatureStructure:
    """Project valency alternatives from lexical frames into syntax."""
    if sense.category != "V" or not sense.frames:
        return sense.features
    valencies: list[str] = []
    for frame in sense.frames:
        slots = {slot.syntactic for slot in frame.required_slots()}
        if "bare_inf" in slots and "object" in slots:
            valency = "bare_control"
        elif "to_inf" in slots and "object" in slots:
            valency = "object_control"
        elif "bare_inf" in slots:
            valency = "bare_complement"
        elif "to_inf" in slots:
            valency = "subject_control"
        elif "whether_inf" in slots:
            valency = "whether_clausal"
        elif "gerund" in slots and "object" in slots:
            valency = "object_gerund_control"
        elif "gerund" in slots:
            valency = "gerund_complement"
        elif "prep_object" in slots and "object" in slots:
            valency = "prep_ditransitive"
        elif "predicate" in slots and "object" in slots:
            valency = "complex_transitive"
        elif "predicate" in slots:
            valency = "linking"
        elif "clause" in slots:
            valency = "clausal"
        elif "iobj" in slots and "object" in slots:
            valency = "ditransitive"
        elif "object" in slots:
            valency = "transitive"
        elif "prep_object" in slots:
            valency = "prepositional"
        else:
            valency = "intransitive"
        if valency not in valencies:
            valencies.append(valency)
    if not valencies:
        return sense.features
    value: object = valencies[0] if len(valencies) == 1 else valencies
    return sense.features.with_feature("subcat", coerce(value))


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
                # A productive compound normally inherits NON-VERBAL head
                # readings. A verbal head is licensed only after a recognized
                # productive verb PREFIX (over-rated, under-estimated,
                # mis-judged, ...), never merely because the final word also
                # happens to be a verb (bright-eyed, carpet-bag).
                # Prefixes are morphemes here, NOT arbitrary first-word POS.
                verbal_prefixes = {
                    "over", "under", "out", "mis", "re", "pre", "un",
                }
                licensed_verb_prefix = (
                    end == start + 2
                    and first.text.casefold() in verbal_prefixes
                )
                head_readings = tuple(
                    (entry, sense, lemma)
                    for entry, sense, lemma in lexicon.lookup_morphology(head.text)
                    if _surface_matches_morphology(head.text, entry, sense, lemma)
                )
                matches = tuple(
                    (entry, sense, lemma)
                    for entry, sense, lemma in head_readings
                    if (sense.category in open_categories - {"V"}
                        or (sense.category == "V" and licensed_verb_prefix))
                )
                source = "hyphen-compound"

                # Productive English attributive compounds: X + past
                # participle -> ADJ ("river-washed", "sun-dried",
                # "well-written"). This *does not* license a verbal
                # compound: the entire X-V[ed] is an adjective.
                # The head's attested V[ed] morphology is mandatory:
                # X-"walk" or X-"bag" may not become ADJ by guessing.
                # Preserve any independent WordNet ADJ/N senses alongside
                # the derived hypothesis. With explicit dictionary readings
                # (occupied_spans), this inference is unnecessary.
                for entry, sense, lemma in head_readings:
                    if (sense.category != "V"
                            or sense.features.as_dict().get("vform") != "ed"
                            or not (head.text.casefold().endswith("ed")
                                    or head.text.casefold() != lemma.casefold())):
                        continue
                    yield LexicalCandidate(
                        span_start=first.start,
                        span_end=head.end,
                        surface=surface,
                        lemma=surface.casefold(),
                        category="ADJ",
                        features=FeatureStructure.empty(),
                        normalized=surface.casefold(),
                        source="hyphen-participial-adjective",
                        score=min(sense.score, 0.78),
                        provenance={
                            "source": "productive-hyphen-morphology",
                            "construction": "X+past_participle->ADJ",
                            "head_surface": head.text,
                            "head_lemma": lemma,
                            "verb_sense_id": sense.sense_id,
                        },
                        interpretations=(LexicalInterpretation(
                            sense_id=None,
                            lemma=surface.casefold(),
                            provenance={
                                "source": "productive-hyphen-morphology",
                                "head_lemma": lemma,
                                "verb_sense_id": sense.sense_id,
                            },
                        ),),
                    )
            for entry, sense, lemma in matches:
                if source == "lexicon-hyphen" and not _surface_matches_morphology(
                    surface, entry, sense, lemma,
                ):
                    continue
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
        # For an overt apostrophe-s, the bare dictionary noun "s" is not
        # a possible clitic reading. Keep copula, HAVE and POSS hypotheses;
        # independent uncontracted "s" remains in the lexical inventory.
        if clitic.casefold() == "s" and sense.category == "N":
            continue
        yield _candidate_from_sense(
            span_start=base_end,
            span_end=span_end,
            surface=clitic,
            lemma=lemma,
            sense=sense,
            source="contraction-clitic",
        )

