"""Bound a subject question whose object has a postnominal ability clause."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_subject_question_ability"
W = r"[A-Za-z][A-Za-z'’\-]*"
PATTERN = re.compile(
    rf"(?P<who>who)\s+(?P<modal>could|can|would|might)\s+(?P<act>{W})\s+"
    rf"(?P<object>(?:a|an|the)\s+{W})\s+(?P<able>capable|incapable)\s+(?P<of>of)\s+"
    rf"(?P<gerund>{W})\s+(?P<det>the)\s+(?P<modifier>{W})\s+(?P<terrain>{W})\s+"
    rf"(?P<terrain_of>of)\s+(?P<name1>{W})\s+(?P<name2>{W})(?P<stop>\?)", re.I,
)


def plan_subject_question_ability(text, components):
    m = PATTERN.fullmatch(text)
    if (m is None or not all(m[g][0].isupper() for g in ("name1", "name2"))
            or not any(c["id"] == "s0" and c["start"] == 0 and c["end"] == len(text)
                       and c["function"] == "matrix_clause" for c in components)):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    lex("who", "WH-PRONOUN", interrogative_subject="true", wh="true")
    lex("modal", "MODAL", vform="finite")
    lex("act", "V", vform="base", subcat_member="transitive")
    add("NP", *m.span("object"), "phrase", proof_rule="np_det_n")
    lex("able", "ADJ")
    lex("of", "PREP", lemma_in="of")
    lex("gerund", "V", vform="ing", subcat_member="transitive")
    lex("det", "DET", definiteness="definite")
    lex("modifier", "V", vform="ing", lemma_in="overhang|slope|tower|rise|jut",
        subcat_member="intransitive")
    lex("terrain", "N", number="plural", lemma_in="side|cliff|slope|wall|ridge|ledge")
    lex("terrain_of", "PREP", nominal_complement="of")
    for group in ("name1", "name2"):
        lex(group, "PROPER-NOUN")
    punct("QMARK", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
