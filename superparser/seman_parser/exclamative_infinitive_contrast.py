"""Bound a clausal exclamation and the detached, more striking details."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_exclamative_infinitive_contrast"
W = r"[A-Za-z][A-Za-z'’\-]*"
SUBJ = r"I|you|he|she|we|they"
OBJ = r"me|you|him|her|us|them"
PATTERN = re.compile(
    rf"(?P<that>that)\s+(?P<subject>{SUBJ})\s+(?P<modal>should|would|could)\s+(?P<even>even)\s+"
    rf"(?P<speak>{W})\s+(?P<to_person>to)\s+(?P<person>{OBJ})\s+(?P<was>is|was)\s+(?P<adj>{W})"
    rf"(?P<first>!)(?P<dash>--|—)\s*(?P<but>but)\s+(?P<to1>to)\s+(?P<repeat>{W})\s+"
    rf"(?P<with>with)\s+(?P<such>such)\s+(?P<manner>{W})(?P<comma>,)\s+(?P<to2>to)\s+"
    rf"(?P<inquire>{W})\s+(?P<after>after|about)\s+"
    rf"(?P<family>(?:his|her|my|your|their|our|the)\s+{W})(?P<stop>!)", re.I,
)


def plan_exclamative_contrast(text, components):
    m = PATTERN.fullmatch(text)
    if (m is None or m["speak"].casefold() != m["repeat"].casefold()
            or not any(c["id"] == "s0" and c["start"] == 0 and c["end"] == len(text)
                       and c["function"] == "matrix_clause" for c in components)):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    lex("that", "COMP-THAT")
    add("NP", *m.span("subject"), "subject-phrase", pronominal="true")
    lex("modal", "MODAL", vform="finite")
    lex("even", "ADV", scalar_focus="true")
    for group in ("speak", "repeat"):
        lex(group, "V", vform="base", lemma_in="speak|talk|write", subcat_member="prepositional")
    lex("to_person", "PREP", lemma_in="to")
    if m["person"].casefold() == "you":
        lex("person", "PRONOUN", lemma_in="you")
    else:
        lex("person", "PRONOUN", case="accusative")
    lex("was", "COPULA", lemma_in="be", vform="finite", number="singular")
    lex("adj", "ADJ", lemma_in="amazing|astonishing|surprising|startling|remarkable|unexpected")
    lex("but", "COORD", lemma_in="but")
    for group in ("to1", "to2"):
        lex(group, "TO")
    lex("with", "PREP", lemma_in="with")
    lex("such", "DEGREE", lemma_in="such")
    lex("manner", "N")
    lex("inquire", "V", vform="base", lemma_in="inquire|enquire|ask",
        subcat_member="prepositional")
    lex("after", "PREP", lemma_in=m["after"].casefold())
    add("NP", *m.span("family"), "phrase", simple_nominal_proof="true")
    punct("EXCL", *m.span("first"))
    punct("DASH", *m.span("dash"))
    punct("COMMA", *m.span("comma"))
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
