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
    kept = [*kept, *nominal_heads]
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

