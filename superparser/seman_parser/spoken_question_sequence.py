"""Source-exact plans for statements followed by a wh-adjunct question."""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from .segmentation import tokenize

PLAN = "statement_wh_sequence"
ROOTS = {
    2: "dialogue_structural_statement_then_wh_question",
    3: "dialogue_structural_two_statements_then_wh_question",
}
ROOT_COUNTS = {rule: n for n, rule in ROOTS.items()}

Spec = tuple[str, int, int, str, Mapping[str, str]]
Span = tuple[int, int, int]

# Conventional stance supplements, not productive bare imperative clauses.
_STANCE = re.compile(r"thank (?:goodness|heavens|God)", re.IGNORECASE)
_DISCOURSE_STATEMENT = re.compile(r"(so) (.+) (then|now), (.+)", re.IGNORECASE)
_NEGATIVE_NOMINAL = re.compile(
    r"(.+?)(?: (am|is|are|was|were)|(['’](?:m|s|re))) (not) "
    r"((?:quite )?(?:a|an|the) .+)", re.IGNORECASE,
)
_WH = frozenset(("where", "when", "why", "how"))
_PRONOUNS = frozenset(("i", "you", "he", "she", "it", "we", "they"))
_THIRD_SINGULAR = frozenset(("he", "she", "it"))


def _group_span(match: re.Match[str], offset: int, group: int) -> tuple[int, int]:
    return offset + match.start(group), offset + match.end(group)


def _statement(text: str, a: int, b: int) -> list[Spec] | None:
    body = text[a:b]
    discourse = _DISCOURSE_STATEMENT.fullmatch(body)
    if discourse and _STANCE.fullmatch(discourse[4]):
        comma = a + discourse.end(3)
        return [
            ("ADV", *_group_span(discourse, a, 1), "lexical", {"lemma_in": "so"}),
            ("CLAUSE", *_group_span(discourse, a, 2), "phrase", {"finite_statement_proof": "true"}),
            ("ADV", *_group_span(discourse, a, 3), "lexical", {"deictic_time": "true"}),
            ("COMMA", comma, comma + 1, "source-punctuation", {}),
            ("STANCE-FORMULA", *_group_span(discourse, a, 4), "source-stance-formula", {}),
        ]
    copular = _NEGATIVE_NOMINAL.fullmatch(body)
    if copular:
        subject = copular[1].casefold()
        copula = (copular[2] or copular[3]).casefold().replace("’", "'")
        if subject in _PRONOUNS:
            singular = subject in _THIRD_SINGULAR
            if not {
                "is": singular, "'s": singular, "am": subject == "i", "'m": subject == "i",
                "are": not singular and subject != "i",
                "'re": not singular and subject != "i",
                "was": singular or subject == "i",
                "were": not singular and subject != "i",
            }[copula]:
                return None

        return [
            ("NP", *_group_span(copular, a, 1), "subject-phrase", {}),
            ("COPULA", *_group_span(copular, a, 2 if copular[2] else 3),
             "lexical-alternatives", {"vform": "finite"}),
            ("NEG", *_group_span(copular, a, 4), "lexical", {"negation": "true"}),
            ("NP", *_group_span(copular, a, 5), "phrase", {"predicative_nominal_proof": "true"}),
        ]
    return [("CLAUSE", a, b, "phrase", {"finite_statement_proof": "true"})]


def statement_question_plan(
    text: str, spans: Sequence[Span],
) -> tuple[str, list[Spec]] | None:
    """Reuse the composer's verified quote/spoken spans. Never split text here."""
    if len(spans) not in ROOTS:
        return None
    if text[spans[-1][2]] != "?" or any(text[stop] not in ".!" for _, _, stop in spans[:-1]):
        return None
    a, b, stop = spans[-1]
    tokens = tokenize(text[a:b])
    if (len(tokens) < 4 or tokens[0].text.casefold() not in _WH
            or tokens[1].text.casefold() not in ("do", "does", "did")):
        return None

    # First scope: short pronominal subjects need no speculative split.
    pronoun = tokens[2].text.casefold()
    if pronoun not in _PRONOUNS:
        return None
    # The static AUX entry groups do/does/did without person or number.
    # Preserve overt present-tense agreement rather than relying on that entry.
    auxiliary = tokens[1].text.casefold()
    if auxiliary != "did" and (auxiliary == "does") != (pronoun in _THIRD_SINGULAR):
        return None
    if any(len(text[x:y].split()) > 22 for x, y, _ in spans):
        return None
    wh, aux, subject = tokens[:3]
    out: list[Spec] = [("OPEN-QUOTE", 0, 1, "source-punctuation", {})]
    for x, y, punct in spans[:-1]:
        statement = _statement(text, x, y)
        if statement is None:
            return None
        out.extend(statement)
        out.append(("SPEECH-STOP", punct, punct + 1, "source-punctuation", {}))
    out.extend((
        ("WH-NOM", a + wh.start, a + wh.end, "lexical", {"wh_adverbial": "true"}),
        ("AUX", a + aux.start, a + aux.end, "lexical-alternatives", {
            "vform": "finite", "lemma_in": "do|does|did",
        }),
        ("NP", a + subject.start, a + subject.end, "subject-phrase", {}),
        ("VP-NP", a + tokens[3].start, b, "phrase", {"bare_predicate_proof": "true"}),
        ("QMARK", stop, stop + 1, "source-punctuation", {}),
        ("CLOSE-QUOTE", len(text) - 1, len(text), "source-punctuation", {}),
    ))
    return ROOTS[len(spans)], out


def is_stance_supplement(text: str) -> bool:
    return _STANCE.fullmatch(text) is not None
