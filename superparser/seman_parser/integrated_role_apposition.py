"""Bound an integrated role apposition after a named subject."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_integrated_role_apposition"
W = r"[A-Za-z][A-Za-z'’\-]*"
PATTERN = re.compile(
    rf"(?P<person>{W})\s+(?P<article>the)\s+"
    rf"(?P<role>wife|husband|daughter|son|sister|brother|mother|father|partner|spouse|widow|widower)\s+"
    rf"(?P<of>of)\s+(?:(?P<title>Mr|Mrs|Ms|Dr)(?P<dot>\.)\s+)?(?P<name>{W})\s+"
    rf"(?P<copula>is|was)\s+(?P<det>a|an)\s+(?:(?P<degree>most|very|rather|quite)\s+)?(?P<quality>{W})\s+(?P<attribute>{W})(?P<stop>[.!])",
    re.I,
)


def plan_integrated_role_apposition(text, components):
    m = PATTERN.fullmatch(text)
    if (m is None or not all(m[g][0].isupper() for g in ("person", "name"))
            or not any(c["id"] == "s0" and c["function"] == "matrix_clause"
                       and c["start"] == 0 and c["end"] == len(text) for c in components)):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    lex("person", "PROPER-NOUN")
    lex("article", "DET", definiteness="definite")
    lex("role", "N", number="singular")
    lex("of", "PREP", nominal_complement="of")
    if m["title"]:
        lex("title", "TITLE", honorific="true")
        punct("ABBREVIATION-STOP", *m.span("dot"))
    lex("name", "PROPER-NOUN")
    lex("copula", "COPULA", lemma_in="be", vform="finite", number="singular")
    lex("det", "DET", definiteness="indefinite", number="singular")
    if m["degree"]:
        lex("degree", "ADV")
    lex("quality", "ADJ")
    lex("attribute", "N", number="singular")
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
