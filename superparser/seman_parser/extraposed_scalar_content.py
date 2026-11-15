"""Candidate spans for scalar nominal modifiers inside extraposed content."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_extraposed_scalar_content"
WORD = r"[A-Za-z][A-Za-z’'\-]*"
PERSPECTIVE = "me|you|him|her|it|us|them|anyone|anybody|someone|somebody|everyone|everybody|no one|nobody"
INDEFINITE = "anyone|anybody|someone|somebody|everyone|everybody|nobody"
# These scalar senses can be evaluated from an experiencer's perspective.
SCALAR = "long|short|large|small|big|little|loud|quiet|bright|dim|strong|weak|heavy|light|slow|fast|hot|cold"
PATTERN = re.compile(
    rf"(?P<it>it)\s+(?P<copula>is|was)\s+(?P<difficulty>{WORD})\s+"
    rf"(?P<inf_to>to)\s+(?P<cognition>{WORD})\s+(?P<that>that)\s+"
    rf"(?P<subject>{WORD}(?:\s+{WORD}){{0,7}}?)\s+(?P<so>so)\s+"
    rf"(?P<subject_quality>{SCALAR})\s+(?P<subject_to>to)\s+"
    rf"(?P<subject_view>{PERSPECTIVE})(?:\s+(?P<subject_else>else))?"
    rf"(?P<pause>,)?\s+(?P<modal>can|could|may|might|must|will|would|should)\s+"
    rf"(?P<be>be)\s+(?P<predicate_quality>{SCALAR})\s+(?P<predicate_to>to)\s+"
    rf"(?P<predicate_view>{PERSPECTIVE})(?:\s+(?P<predicate_else>else))?(?P<stop>\.)",
    re.I,
)


def _source_spans(m):
    return (
        (m.start("inf_to"), m.start("stop")),
        (m.start("that"), m.start("stop")),
        (m.start("subject"), m.end("subject_else") if m["subject_else"] else m.end("subject_view")),
    )


def extraposed_scalar_spans(text):
    if m := PATTERN.fullmatch(text):
        return _source_spans(m)
    return None


def plan_extraposed_scalar_content(text, components):
    m = PATTERN.fullmatch(text)
    if not m:
        return None
    if not all(any(c["id"] == node and c["governor"] == governor
                   and (c["start"], c["end"]) == span for c in components)
               for (node, governor), span in zip(
                   (("xs0", "s0"), ("xs1", "xs0"), ("xs2", "xs1")), _source_spans(m))):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    lex("it", "EXTRAPOSITION-IT", extraposition_it="true")
    lex("copula", "COPULA", lemma_in="be", vform="finite", number="singular")
    lex("difficulty", "ADJ", tough_predicate="true")
    lex("inf_to", "TO")
    lex("cognition", "V", vform="base", subcat_member="clausal")
    lex("that", "COMP-THAT")
    add("NP", *m.span("subject"), "subject-phrase")
    lex("so", "DEGREE", lemma_in="so", scalar_degree="true")
    for prefix in ("subject", "predicate"):
        lex(f"{prefix}_quality", "ADJ")
        lex(f"{prefix}_to", "PREP", lemma_in="to")
        if m[f"{prefix}_else"]:
            lex(f"{prefix}_view", "PRONOUN", lemma_in=INDEFINITE)
            lex(f"{prefix}_else", "ADJ", lemma_in="else")
        else:
            add("NP", *m.span(f"{prefix}_view"), "phrase", pronominal="true")
    if m["pause"]:
        punct("COMMA", *m.span("pause"))
    lex("modal", "MODAL", vform="finite")
    lex("be", "COPULA", lemma_in="be", vform="base")
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
