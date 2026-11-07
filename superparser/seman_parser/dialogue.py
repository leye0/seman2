"""Explicit quotation boundaries for a scoped dialogue grammar.

The ordinary tokenizer deliberately omits typographic quotation marks.
Rather than changing the tokenization of all novels (or globally accepting
speech-like clauses), add purely syntactic, zero-semantic-cost quote terminals
to a separate lexical lattice. Balanced double quotes and typographic
single quotes are accepted. Word-internal apostrophes remain contractions
and possessives, not dialogue delimiters.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .features import FeatureStructure
from .segmentation import LexicalCandidate, LexicalLattice


@dataclass(frozen=True, slots=True)
class QuoteBoundary:
    start: int
    end: int
    side: str
    surface: str


def quotation_boundaries(text: str) -> tuple[QuoteBoundary, ...]:
    """Recognize balanced dialogue quotes without inventing missing ones.

    Double and paired single quotes (ASCII or curly) are delimiters.
    Internal apostrophes in contractions/possessives are never quote
    boundaries; a lone trailing possessive apostrophe is also ignored.
    """
    stack: list[tuple[str, int]] = []
    boundaries: list[QuoteBoundary] = []
    for pos, char in enumerate(text):
        if char not in {'"', "'", '“', '”', '‘', '’'}:
            continue
        if char == "'":
            previous = text[pos - 1] if pos else ""
            following = text[pos + 1] if pos + 1 < len(text) else ""
            if previous.isalnum() and following.isalnum():
                continue
            if stack and stack[-1][0] == "'":
                stack.pop()
                boundaries.append(QuoteBoundary(pos, pos + 1, "close", char))
                continue
            if previous.isalnum() or not following or not following.isalnum():
                continue
            stack.append((char, pos))
            boundaries.append(QuoteBoundary(pos, pos + 1, "open", char))
            continue
        if char == '’' and 0 < pos < len(text)-1:
            if text[pos-1].isalnum() and text[pos+1].isalnum():
                continue  # don't, I've, John’s — lexical apostrophe
        if char in {'“', '‘'}:
            stack.append((char, pos))
            boundaries.append(QuoteBoundary(pos, pos+1, "open", char))
        elif char in {'”', '’'}:
            expected = '“' if char == '”' else '‘'
            if not stack or stack[-1][0] != expected:
                if char == '’' and pos > 0 and text[pos-1].isalnum():
                    continue  # plural possessive dogs’ outside single dialogue
                return ()
            stack.pop()
            boundaries.append(QuoteBoundary(pos, pos+1, "close", char))
        elif stack and stack[-1][0] == '"':
            stack.pop()
            boundaries.append(QuoteBoundary(pos, pos+1, "close", char))
        else:
            stack.append((char, pos))
            boundaries.append(QuoteBoundary(pos, pos+1, "open", char))
    if stack:
        return ()
    return tuple(boundaries) if len(boundaries) >= 2 else ()


def dialogue_lattice(base: LexicalLattice) -> LexicalLattice | None:
    """Overlay real quote boundaries and terminal punctuation, never words."""
    boundaries = quotation_boundaries(base.text)
    if not boundaries:
        return None
    candidates = list(base.candidates)
    for boundary in boundaries:
        candidates.append(LexicalCandidate(
            span_start=boundary.start,
            span_end=boundary.end,
            surface=boundary.surface,
            lemma=boundary.surface,
            category="OPEN-QUOTE" if boundary.side == "open" else "CLOSE-QUOTE",
            features=FeatureStructure.empty(),
            source="dialogue-delimiter",
            score=0,
            provenance={"boundary":boundary.side},
        ))
        if boundary.side == "close":
            # Period and exclamation/question marks belong to the quoted
            # utterance when they precede the closing quote. They were
            # previously ignored as optional trailing sentence punctuation.
            at=boundary.start-1
            while at >= 0 and base.text[at].isspace():
                at-=1
            if at>=0 and base.text[at] in ".!?":
                candidates.append(LexicalCandidate(
                    span_start=at,span_end=at+1,
                    surface=base.text[at],lemma=base.text[at],
                    category="SPEECH-STOP",
                    features=FeatureStructure.empty(),
                    source="dialogue-delimiter",score=0,
                    provenance={"boundary":"terminal_punctuation"},
                ))
    # A verbless quoted continuation may inherit its omitted predicate from
    # the preceding discourse unit. Only expose the start of that structural
    # analysis when the lexical lattice independently attests an opening
    # quotation, an immediately following coordinator, adjacent adverbs,
    # a PP start, a literal comma, and another PP start. This does not
    # synthesize a predicate or replace any original lexical candidate.
    # Crucially, unrelated long quotations must not start fragment searches
    # (the canonical literary dialogue at index 359 is near its budget).
    def next_to(left: int, right: int) -> bool:
        return right > left and base.text[left:right].isspace()

    lexical = base.candidates
    literal_commas = [c for c in lexical if c.category == "COMMA"
                      and c.features.as_dict().get("literal_comma") == "true"]

    def next_candidates(left: int, category: str):
        return (c for c in lexical if c.category == category
                and next_to(left, c.span_start))

    def has_parenthetical_pp(prep: LexicalCandidate) -> bool:
        return any(
            any(closer.side == "close" and trailing.span_end < closer.start
                for closer in boundaries)
            for comma in literal_commas if prep.span_end < comma.span_start
            for trailing in next_candidates(comma.span_end, "PREP")
        )

    def has_fragment_start(coord: LexicalCandidate) -> bool:
        return any(
            has_parenthetical_pp(prep)
            for first in next_candidates(coord.span_end, "ADV")
            for second in next_candidates(first.span_end, "ADV")
            for prep in next_candidates(second.span_end, "PREP")
        )

    for boundary in boundaries:
        if boundary.side == "close":
            continue
        # A few context-dependent utterance fragments have deliberately
        # narrow entry points.  Adding their general OPEN-QUOTE rules to the
        # shared dialogue forest would consume the near-saturated #359 budget
        # even when neither fragment is lexically possible.  These overlays
        # only expose a *category* on a real opening quote; no token, source
        # span, or lexical reading is changed or synthesized.
        candidate_opener = next((c for c in candidates
                                 if c.category == "OPEN-QUOTE"
                                 and c.span_start == boundary.start), None)
        if candidate_opener is None:
            continue
        if any(c.category == "TOPIC-MARKER"
               and c.features.as_dict().get("topic_marker") == "true"
               and (boundary.end == c.span_start or next_to(boundary.end, c.span_start))
               for c in lexical):
            candidates.append(replace(
                candidate_opener, category="OPEN-QUOTE-DISCOURSE-TOPIC"))
        if any(c.category == "COORD"
               and c.features.as_dict().get("nominal_coordination") == "true"
               and (boundary.end == c.span_start or next_to(boundary.end, c.span_start))
               for c in lexical):
            candidates.append(replace(
                candidate_opener, category="OPEN-QUOTE-NOMINAL-CONTINUATION"))
        coordinators = [c for c in lexical if c.category == "COORD"
                        and c.features.as_dict().get("nominal_coordination") == "true"
                        and (boundary.end == c.span_start
                             or next_to(boundary.end, c.span_start))]
        if not coordinators:
            continue
        if any(has_fragment_start(coord) for coord in coordinators):
            candidates.append(replace(
                candidate_opener, category="OPEN-QUOTE-ELLIPTICAL-COORD"))
    return LexicalLattice(
        text=base.text,
        tokens=base.tokens,
        candidates=tuple(candidates),
    )
