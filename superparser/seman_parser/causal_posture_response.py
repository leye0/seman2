"""Compose a causal explanation with a temporal onset and shared depictives."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_causal_posture_response"
W = r"[A-Za-z][A-Za-z'’\-]*"
POSS = r"its|my|our|his|her|their|your"
PATTERN = re.compile(
    rf"(?P<effect>(?:{POSS}|the)\s+(?:effect|impact|result|consequence|outcome))\s+"
    rf"(?P<be>was|is)\s+(?P<degree>most|rather|quite|very)\s+(?P<quality>{W})(?P<semi>;)\s+"
    rf"(?P<for>for)\s+(?P<on>on|upon)\s+(?P<first>first)\s+(?P<perceive>{W})\s+"
    rf"(?P<object>it|this|that)(?P<c1>,)\s+"
    rf"(?P<title>Mr|Mrs|Ms|Dr)(?P<dot>\.)\s+(?P<name>{W})\s+(?P<posture>{W})\s+"
    rf"(?P<intensity>quite|very|perfectly|entirely)\s+(?P<state>{W})(?P<c2>,)\s+"
    rf"(?P<and>and)\s+(?P<ability>unable|powerless)\s+(?P<to>to)\s+(?P<utter>{W})\s+"
    rf"(?P<theme>(?:a|an|the)\s+(?:{W}\s+)?{W})(?P<stop>\.)", re.I,
)


def plan_causal_posture(text, components):
    m = PATTERN.fullmatch(text)
    if m is None or not m["name"][0].isupper():
        return None
    nodes = {node["id"]: node for node in components}
    for node, governor, span in (
        ("s0", "u0", (0, m.start("semi"))), ("s1", "s0", (m.start("for"), len(text))),
    ):
        c = nodes.get(node, {})
        if (c.get("governor"), c.get("start"), c.get("end")) != (governor, *span):
            return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    add("NP", *m.span("effect"), "phrase", simple_nominal_proof="true", number="singular")
    lex("be", "COPULA", vform="finite", lemma_in="be", number="singular")
    lex("degree", "ADV")
    lex("quality", "ADJ")
    punct("SEMICOLON", *m.span("semi"))
    lex("for", "COORD", causal_coordination="true")
    lex("on", "PREP", lemma_in="on|upon")
    lex("first", "ADV", lemma_in="first")
    lex("perceive", "V", vform="ing", lemma_in="hear|read|see|learn|notice|receive",
        subcat_member="transitive")
    lex("object", "PRONOUN")
    lex("title", "TITLE", honorific="true")
    punct("ABBREVIATION-STOP", *m.span("dot"))
    lex("name", "PROPER-NOUN")
    lex("posture", "V", vform="finite", lemma_in="sit|stand|remain|lie",
        nonbase_surface="true", subcat_member="intransitive")
    lex("intensity", "ADV")
    lex("state", "ADJ", lemma_in="still|silent|motionless|quiet|speechless|rigid|calm")
    lex("and", "COORD", lemma_in="and")
    lex("ability", "ADJ")
    lex("to", "TO")
    lex("utter", "V", vform="base", subcat_member="transitive")
    add("NP", *m.span("theme"), "phrase", proof_rule="np_det_n")
    for group in ("c1", "c2"):
        punct("COMMA", *m.span(group))
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
