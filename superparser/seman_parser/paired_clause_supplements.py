"""Source spans for two coordinated copulas with separate medial supplements."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_paired_copular_supplements"
WORD = r"[A-Za-z][A-Za-z’'\-]*"
NP = rf"{WORD}(?:\s+{WORD}){{0,7}}?"
COPULA = r"am|is|are|was|were"
PATTERN = re.compile(
    rf"(?P<subject>{NP})(?P<c1>,)\s+(?P<discourse>besides|moreover|furthermore)"
    rf"(?P<c2>,)\s+(?P<left>{COPULA})\s+(?P<first>{WORD})\s+"
    rf"(?P<pair>and)\s+(?P<second>{WORD})(?P<c3>,)\s+(?P<coord>and)\s+"
    rf"(?P<anaphor>this|that)(?P<c4>,)\s+(?P<spatial>under|beneath|in|on|by)\s+"
    rf"(?P<place>{NP})(?P<c5>,)\s+(?P<right>{COPULA})\s+"
    rf"(?P<attr>(?:a|an|the)\s+{NP})\s+(?P<to>to)\s+(?P<recipient>{NP})(?P<stop>\.)",
    re.I,
)


def _spans(match):
    return ((0, match.end("second")), match.span("discourse"),
            (match.start("anaphor"), match.start("stop")),
            (match.start("spatial"), match.end("place")))


def paired_supplement_spans(text):
    match = PATTERN.fullmatch(text)
    return _spans(match) if match is not None else None


def paired_supplement_plan(text, components):
    match = PATTERN.fullmatch(text)
    if match is None:
        return None
    governors = ("s0", "cs0", "s0", "cs1")
    if not all(any(c["id"] == node and c["governor"] == host
                   and (c["start"], c["end"]) == span for c in components)
               for node, host, span in zip(("cs0", "csd", "cs1", "csp"), governors, _spans(match))):
        return None
    specs, add, mark, _ = _specs()

    def lexical(group, category, **features):
        add(category, *match.span(group), "lexical-alternatives", **features)

    add("NP", *match.span("subject"), "subject-phrase")
    for group in ("left", "right"):
        lexical(group, "COPULA", vform="finite", lemma_in="be")
    for group in ("first", "second"):
        lexical(group, "ADJ")
    for group in ("pair", "coord"):
        lexical(group, "COORD", nominal_coordination="true", lemma_in="and")
    lexical("discourse", "ADV")
    lexical("anaphor", "PRONOUN", anaphor="true", definiteness="demonstrative")
    lexical("spatial", "PREP", lemma_in=match["spatial"].casefold())
    lexical("to", "PREP", lemma_in="to")
    for group in ("place", "attr", "recipient"):
        add("NP", *match.span(group), "phrase", simple_nominal_proof="true")
    for group in ("c1", "c2", "c3", "c4", "c5"):
        mark("COMMA", *match.span(group))
    mark("SPEECH-STOP", *match.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
