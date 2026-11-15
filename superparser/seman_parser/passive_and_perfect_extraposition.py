"""Keep a prepositional passive separate from a modal perfect evaluation."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_passive_and_perfect_extraposition"
W = r"[A-Za-z][A-Za-z'’\-]*"
PATTERN = re.compile(
    rf"(?P<now>now|then)\s+(?P<subject>(?:my|his|her|your|our|their|the)\s+{W})\s+"
    rf"(?P<were>was|were)\s+(?P<passive>{W})\s+(?P<prep>with|to|on)(?P<c1>,)\s+"
    rf"(?P<and>and)\s+(?P<it>it)\s+(?P<modal>would|might|could)(?P<c2>,)\s+"
    rf"(?P<indeed>indeed|surely|certainly)(?P<c3>,)\s+(?P<have>have)\s+(?P<been>been)\s+"
    rf"(?P<quality>folly|madness|a\s+mistake|a\s+pity)\s+(?P<to>to)\s+(?P<act>{W})(?P<stop>\.)",
    re.I,
)
PASSIVE = {"with": "comply|deal|dispense", "to": "agree|object|consent", "on": "act|decide|insist"}


def plan_passive_extraposition(text, components):
    m = PATTERN.fullmatch(text)
    if (m is None or not any(c["id"] == "s0" and c["start"] == 0 and c["end"] == len(text)
                            and c["function"] == "matrix_clause" for c in components)):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    lex("now", "ADV")
    add("NP", *m.span("subject"), "phrase", simple_nominal_proof="true")
    lex("were", "AUX-BE", vform="finite", lemma_in="be")
    lex("passive", "V", vform="ed", lemma_in=PASSIVE[m["prep"].casefold()],
        subcat_member="prepositional")
    lex("prep", "PREP", lemma_in=m["prep"].casefold())
    lex("and", "COORD", lemma_in="and")
    lex("it", "EXTRAPOSITION-IT", extraposition_it="true")
    lex("modal", "MODAL", vform="finite")
    lex("indeed", "ADV")
    lex("have", "HAVE", vform="base")
    lex("been", "COPULA", vform="ed")
    add("NP", *m.span("quality"), "phrase", simple_nominal_proof="true")
    lex("to", "TO")
    lex("act", "V", vform="base", subcat_member="intransitive")
    for group in ("c1", "c2", "c3"):
        punct("COMMA", *m.span(group))
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
