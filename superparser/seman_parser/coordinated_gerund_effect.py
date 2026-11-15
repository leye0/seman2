"""Compose an effect nominal containing two gerunds and object control."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_coordinated_gerund_effect"
W = r"[A-Za-z][A-Za-z'’\-]*"
POSS = r"my|your|his|her|our|their"
PATTERN = re.compile(
    rf"(?P<subject>the\s+(?:sight|view|sound|spectacle|image))\s+(?P<of1>of)\s+"
    rf"(?P<det1>the)\s+(?P<quality1>{W})\s+(?P<and1>and)\s+(?P<quality2>{W})\s+"
    rf"(?P<in>in)\s+(?P<context>nature|art|music|life)\s+(?P<have>has|had)\s+"
    rf"(?P<stance>indeed|certainly)\s+(?P<frequency>always|often|usually)\s+"
    rf"(?P<effect>the\s+(?:effect|result))\s+(?P<of2>of)\s+(?P<gerund1>{W})\s+"
    rf"(?P<affected>(?:{POSS})\s+{W})\s+(?P<and2>and)\s+(?P<gerund2>{W})\s+"
    rf"(?P<controller>me|you|him|her|us|them)\s+(?P<to>to)\s+(?P<action>{W})\s+"
    rf"(?P<det2>the)\s+(?P<modifier>{W})\s+(?P<theme>{W})\s+(?P<of3>of)\s+"
    rf"(?P<domain>{W})(?P<stop>\.)", re.I,
)


def plan_gerund_effect(text, components):
    m = PATTERN.fullmatch(text)
    if (m is None or not any(c["id"] == "s0" and c["function"] == "matrix_clause"
                            and c["start"] == 0 and c["end"] == len(text) for c in components)):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    for group in ("subject", "effect"):
        add("NP", *m.span(group), "phrase", proof_rule="np_det_n", number="singular")
    for group in ("of1", "of2", "of3"):
        lex(group, "PREP", nominal_complement="of")
    for group in ("det1", "det2"):
        lex(group, "DET", definiteness="definite")
    for group in ("quality1", "quality2"):
        lex(group, "ADJ")
    for group in ("and1", "and2"):
        lex(group, "COORD", lemma_in="and", nominal_coordination="true")
    lex("in", "PREP", lemma_in="in")
    lex("context", "N", number="singular")
    lex("have", "V", lemma_in="have", vform="finite", subcat_member="transitive")
    for group in ("stance", "frequency"):
        lex(group, "ADV")
    lex("gerund1", "V", vform="ing", subcat_member="transitive")
    add("NP", *m.span("affected"), "phrase", proof_rule="np_poss")
    lex("gerund2", "V", vform="ing", lemma_in="cause|lead|prompt|induce|compel",
        subcat_member="object_control")
    if m["controller"].casefold() == "you":
        lex("controller", "PRONOUN", lemma_in="you")
    else:
        lex("controller", "PRONOUN", case="accusative")
    lex("to", "TO")
    lex("action", "V", vform="base", subcat_member="transitive")
    lex("modifier", "ADJ", lemma_in="passing|daily|ordinary|petty|usual|constant")
    lex("theme", "N", number="plural", lemma_in="care|worry|trouble|concern|burden|distraction")
    lex("domain", "N", number="singular")
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
