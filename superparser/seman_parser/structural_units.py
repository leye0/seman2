"""Shallow grammatico-structural cohesion between punctuation and full parsing.

The typographic splitter proposes source boundaries. This layer asks whether a
semicolon continuation can be treated as a *self-contained analysis unit* or
needs its governing clause, coordinated predicate, or antecedent. No WordNet,
semantic guesses, invented punctuation, or second syntax parser live here.

Decisions have explicit evidence. A cautious KEEP means only that the evidence
for merging is absent, not that a grammatical tree has been certified.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class StructuralBoundary:
    """An original semicolon and the shallow reason for retaining/removing it."""
    offset: int
    merge: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ClauseSkeleton:
    """Descriptive surface signals, NEVER grammatical completeness proof."""
    starts_with_coordinator: bool
    starts_with_subordinator: bool
    starts_with_preposition: bool
    starts_with_participle: bool
    overt_subject_candidate: bool
    finite_predicate_candidate: bool


_RELATIVE = re.compile(
    r"(?i)^which\s+(?:i|you|he|she|it|we|they|the|a|an|this|that|"
    r"these|those|my|your|his|her|our|their|its|is|are|was|were|"
    r"has|have|had|does|do|did|can|could|will|would|shall|should|may|might|must)\b"
)
_SUBORDINATE = re.compile(
    r"(?i)^(?:because|although|though|unless|until|while|whereas|since|"
    r"if|when|whenever|as)\b\s+"
)
_PP_HEAD = re.compile(
    r"(?i)^(?:(?:and|or)\s+)?(?:in|with|on|at|by|from|for|"
    r"under|over|through|without|beneath|beside|beyond|between)\b"
)
_SUBJECT = re.compile(
    r"(?i)^(?:(?:and|but|or)\s+)?(?:i|you|he|she|it|we|they|"
    r"there|this|that|these|those|"
    r"(?:the|a|an|my|your|his|her|our|their)\s+[a-z-]+)\b"
)
_PROPER_SUBJECT = re.compile(r"^[A-Z][a-z]+\b")

_FINITE = re.compile(
    r"(?i)\b(?:am|is|are|was|were|has|have|had|do|does|did|"
    r"can|could|will|would|shall|should|may|might|must|"
    r"said|saw|found|left|came|went|took|made|gave|"
    r"stood|sat|thought|wrote|spoke|brought|won|"
    r"[a-z-]+ed)\b"
)
_PARTICIPLE = re.compile(
    r"(?i)^(?:(?:merely|simply|only|just)\s+)?[a-z-]+ing\b"
)
_SUBJECT_AFTER_COMMA = re.compile(
    r"(?i),\s*(?:(?:and|but)\s+)?(?:i|you|he|she|it|we|they|"
    r"the|a|an|this|that|these|those|my|your|his|her|our|their|its)\b"
)
_NAME_AFTER_COMMA = re.compile(r",\s*[A-Z][a-z]+\b")
_SHARED_PARTICIPLE = re.compile(
    r"(?i)^(?:and|but|or)\s*,\s*[a-z-]+ing\b[^;]*?,\s*([a-z-]+)\b"
)
_PAST = frozenset({
    "went", "came", "took", "made", "said", "gave", "found",
    "left", "sat", "stood", "brought", "wrote", "spoke", "thought", "saw",
})
_COMPARATIVE_MATRIX = re.compile(r"(?i)\bas\s+(?:[a-z-]+\s+){1,3}as\b")
_COMPARATIVE_TAIL = re.compile(r"(?i)^as\s+(?:[a-z-]+\s+){0,3}[a-z-]+,\s+and\s+as\b")
_PARTICIPLE_SERIES = re.compile(r"(?i)^[a-z-]+ing\b[^;]*?,\s+[a-z-]+ing\b")
_SHARED_MODAL = re.compile(
    r"(?i)^(?:and|or|but)\s+(?:might|may|can|could|would|should|"
    r"will|shall|must|have|has|had|do|does|did)\s+(?!i\b|you\b|"
    r"he\b|she\b|it\b|we\b|they\b)"
)
_SHARED_INFINITIVE = re.compile(r"(?i)^(?:and|or)\s+to\s+[a-z-]+\b")
_CAUSAL_COORDINATION = re.compile(r"(?i)^for\b(?:\s*,?\s+|$)")
_ONE_SIDE = re.compile(r"(?i)\b(?:on|at|in)\s+one\s+(?:side|hand)\b")
_OTHER_SIDE = re.compile(r"(?i)^(?:on|at|in)\s+the\s+other\b")
_FAREWELL = re.compile(r"(?i)^(?:good-?bye|farewell)\s+to\b")


def skeleton(source: str) -> ClauseSkeleton:
    """Expose lexical surface hypotheses without running the grammar engine."""
    text = source.strip().lstrip("“‘\"'([{ ").strip()
    subj = bool(_SUBJECT.match(text) or (
        not _PP_HEAD.match(text) and _PROPER_SUBJECT.match(text)
    ))
    # The finite cue must appear in the same unit. A relative clause may also
    # contain one: this field is not a claim about the matrix predicate.
    return ClauseSkeleton(
        starts_with_coordinator=bool(re.match(r"(?i)^(?:and|but|or|for)\b", text)),
        starts_with_subordinator=bool(_SUBORDINATE.match(text)),
        starts_with_preposition=bool(_PP_HEAD.match(text)),
        starts_with_participle=bool(_PARTICIPLE.match(text)),
        overt_subject_candidate=subj,
        finite_predicate_candidate=bool(_FINITE.search(text)),
    )


def _has_matrix_candidate(fragment: str) -> bool:
    """Narrow signal for a trailing clause after a preposed adjunct chain."""
    candidate = fragment.strip().lstrip("“‘\"'([{ ").strip()
    if _PP_HEAD.match(candidate):
        return False
    if not (_SUBJECT.match(candidate) or _PROPER_SUBJECT.match(candidate)):
        return False
    # Only inspect the first few words; later relative verbs do not license
    # an earlier prepositional phrase on their own.
    return bool(_FINITE.search(" ".join(candidate.split()[:9])))


def _preposed_adverbial_chain(chunks: list[str]) -> bool:
    """A series of PP prefaces followed by a potential finite matrix clause."""
    return (
        len(chunks) >= 2
        and all(_PP_HEAD.match(p.strip()) for p in chunks[:-1])
        and _has_matrix_candidate(chunks[-1])
    )


def _dependency_cue(left: str, right: str) -> str | None:
    """Classify a single semicolon link using only local structural evidence."""
    right = right.strip()
    left = left.strip()
    if "?" in right:
        return None
    if _RELATIVE.match(right):
        return "sentential_relative_antecedent"
    if _SUBORDINATE.match(right) and "," not in right:
        return "unanchored_subordinate_continuation"
    shared = _SHARED_PARTICIPLE.match(right)
    if shared and (shared.group(1).casefold().endswith("ed")
                   or shared.group(1).casefold() in _PAST):
        return "shared_subject_predicate"
    if (_COMPARATIVE_MATRIX.search(left) and _COMPARATIVE_TAIL.match(right)
            and not _SUBJECT_AFTER_COMMA.search(right)):
        return "parallel_comparative_predicate"
    if (_PARTICIPLE_SERIES.match(right)
            and not _SUBJECT_AFTER_COMMA.search(right)
            and not _NAME_AFTER_COMMA.search(right)):
        return "shared_subject_participle_series"
    if _SHARED_MODAL.match(right):
        return "coordinated_predicate_without_overt_subject"
    if _SHARED_INFINITIVE.match(right):
        return "coordinated_infinitive_without_overt_matrix"
    if (_PARTICIPLE.match(right) and not _SUBJECT_AFTER_COMMA.search(right)
            and not _NAME_AFTER_COMMA.search(right)):
        return "nonfinite_supplement_without_matrix"
    if _ONE_SIDE.search(left) and _OTHER_SIDE.match(right):
        return "contrasting_locative_nominal_ellipsis"
    if _CAUSAL_COORDINATION.match(right):
        return "causal_coordinator_refers_back"
    if _FAREWELL.match(left) and _FAREWELL.match(right):
        return "parallel_valediction"
    return None


def review_semicolon_boundaries(sentence: str) -> tuple[StructuralBoundary, ...]:
    """Review *proposed* boundaries, preserving every original character.

    A preposed PP series needs lookahead to its matrix clause. Other links
    use local cues. This is a single cheap grammatical-structure pass between
    typographic segmentation and grammar; it never queries Parser.
    """
    semicolons = [i for i, ch in enumerate(sentence) if ch == ";"]
    if not semicolons:
        return ()
    chunks = sentence.split(";")
    chain = _preposed_adverbial_chain(chunks)
    decisions: list[StructuralBoundary] = []
    for k, offset in enumerate(semicolons):
        reason = (
            "preposed_adverbial_chain_with_matrix" if chain else
            _dependency_cue(chunks[k], chunks[k + 1])
        )
        decisions.append(StructuralBoundary(
            offset=offset, merge=reason is not None,
            reason=reason or "no_supported_dependency",
        ))
    return tuple(decisions)


def source_unit_signals(source: str) -> dict[str, bool]:
    """A descriptive triage aid; none of these fields means parse failure."""
    c = skeleton(source)
    return {
        "starts_with_coordinator": c.starts_with_coordinator,
        "starts_with_subordinator": c.starts_with_subordinator,
        "starts_with_preposition": c.starts_with_preposition,
        "starts_with_participle": c.starts_with_participle,
        "overt_subject_candidate": c.overt_subject_candidate,
        "finite_predicate_candidate": c.finite_predicate_candidate,
    }
