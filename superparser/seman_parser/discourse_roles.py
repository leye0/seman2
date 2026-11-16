"""Conservative discourse-function triage for source-faithful literary units.

Descriptive-grammar distinctions:
* major (finite) clause/utterance vs *minor* (formulaic) utterance;
* contextual/elliptical supplement vs independent matrix clause;
* document-internal notations and paratext vs narrative prose;
* a source quotation continuing an earlier syntactic construction.

These are evidence-labelled SOURCE categories, not a grammar engine, not
semantic reconstruction and not permission to manufacture missing words.
Never classify all clauses lacking an easily detected verb as fragments:
inversion, dialect, imperative and nominal predication need full syntax.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class DiscourseRole:
    """High-level provisional function, with explicit confidence boundary."""
    function: str
    relation: str
    evidence: str
    parse_as_standalone_clause: bool
    antecedent_policy: str = "none"


# Restrict negative rules to sufficiently specific morphology AND punctuation.
# A lowercase first character is NEVER enough to call a text incomplete.
_AFTERTHOUGHT = re.compile(
    r"(?i)^(?:only|not|even|just)\s+(?:upon|on|in|at|under|with|for|to)\b"
)
_QUOTED_DASH_CONTINUATION = re.compile(
    r"^[“‘\"']\s*(?:--|—|–)\s*[a-z]",
    re.IGNORECASE,
)
# The final period can be a separator when the marker is followed by
# whitespace and quoted prose or an uppercase start. The marker must
# begin the unit, so initials in a signature remain untouched.
POSTSCRIPT_FRAME = re.compile(
    # An explicit separator is unambiguous for compact or spaced initials.
    r"(?i:P\.\s?P\.\s?S\.|P\.\s?S\.)(?:\s*(?:--|—|:)\s*|$)"
    # Without a separator, compact markers can precede uppercase prose;
    # spaced marks are initials unless a pronoun or quote follows them.
    r"|(?i:P\.(?:P\.)?S\.)\s+(?=[A-Z“‘\"])"
    r"|(?i:P\.\s+S\.|P\.\s+P\.\s+S\.)\s+(?=(?:I|He|We|You|She|They|It)\b|[“‘\"])"
)
_BEARING = re.compile(
    r"(?i)\bbearing\s+(?:(?:a|one)\s+)?(?:point\s+)?to\s+"
    r"(?:the\s+)?[NSEW]\."
)
_COMPASS = re.compile(
    r"(?i)(?:N\.N\.E\.|N\.N\.W\.|S\.S\.E\.|S\.S\.W\.|"
    r"E\.S\.E\.|E\.N\.E\.|W\.S\.W\.|W\.N\.W\.)"
)
_FINITE_INDICATOR = re.compile(
    r"(?i)\b(?:am|is|are|was|were|be|been|has|have|had|"
    r"will|would|shall|should|can|could|may|might|must|"
    r"did|does|do|[a-z-]+ed)\b"
)
_SALUTATION = re.compile(
    r"(?i)^(?:good\s+(?:night|morning|evening|day|bye)|"
    r"farewell)(?=[,!.?]|\s|$)"
)
_DIALOGUE_REPLY = re.compile(
    r"(?i)^[“‘\"']\s*(?:yes|no|certainly|perfectly|indeed|"
    r"precisely|exactly|perhaps|of course)\s*(?:[,!.?]|[”’\"'])"
)


def classify_discourse(
    source: str, *,
    previous_utterance: str | None = None,
) -> DiscourseRole:
    """Distinguish dependent source and grammatical minor utterances.

    Context references are *potential discourse antecedents*, not claims of
    coreference/syntactic identity. A source continuation remains ineligible
    until its genuine upstream wording has been linked; quoted dialogue
    replies and salutations remain legitimate utterances.
    """
    text = source.strip()
    if frame := POSTSCRIPT_FRAME.match(text):
        return DiscourseRole(
            "documentary_postscript",
            "paratext_with_embedded_clause" if frame.end() < len(text) else "documentary_marker_only",
            "source_postscript_marker", False,
        )
    if (_BEARING.search(text) and _COMPASS.search(text)
            and not _FINITE_INDICATOR.search(text)):
        return DiscourseRole(
            "documentary_navigation_notation", "documentary_annotation",
            "compass_bearing_without_matrix_predication", False,
        )
    if _QUOTED_DASH_CONTINUATION.match(text):
        return DiscourseRole(
            "reported_speech_continuation", "interparagraph_continuation",
            "quotation_begins_with_dash_and_no_matrix_subject", False,
            "preceding_source_unit",
        )
    if _AFTERTHOUGHT.match(text) and (
        previous_utterance is not None
        and re.search(r"(?i)\b(?:upon|on|to|with|for|in|at)\s+(?:us|them|him|her|me|you)\b",
                      previous_utterance)
    ):
        return DiscourseRole(
            "elliptical_supplement", "anaphoric_afterthought",
            "restrictive_prepositional_afterthought_with_prior_governor",
            False, "preceding_utterance",
        )
    if _DIALOGUE_REPLY.match(text):
        return DiscourseRole(
            "minor_utterance", "dialogue_response",
            "formulaic_elliptical_answer_or_adverbial_response", True,
        )
    if _SALUTATION.match(text.lstrip("“‘\"' ")):
        return DiscourseRole(
            "minor_utterance", "social_formula",
            "conventional_salutation_or_valediction", True,
        )
    return DiscourseRole(
        "clausal_utterance_candidate", "independent_or_complex_clause",
        "no_conclusive_fragment_or_documentary_evidence", True,
    )
