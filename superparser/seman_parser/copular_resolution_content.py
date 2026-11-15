"""Bound a copular that-clause and its interrupted negative transfer theme."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_copular_resolution_content"
W = r"[A-Za-z][A-Za-z'’\-]*"
PATTERN = re.compile(
    rf"(?P<host>(?:that|this|the)\s+(?:condition|requirement|stipulation|rule|agreement))\s+"
    rf"(?P<be>is|was)(?P<c1>,)\s+(?P<that>that)\s+(?P<subject>I|you|he|she|we|they)\s+"
    rf"(?P<modal>should|must|will|would)\s+(?P<make>make)\s+"
    rf"(?P<decision>(?:a|an|the)\s+(?:{W}\s+)?(?:resolution|promise|pledge|commitment))\s+"
    rf"(?P<to>to)\s+(?P<grant>grant|give|lend|offer|provide)\s+(?P<no>no)\s+(?P<more>more)\s+"
    rf"(?P<theme>{W})\s+(?P<of>of)\s+(?P<source>(?:my|your|his|her|our|their|the)\s+{W})"
    rf"(?P<c2>,)\s+(?P<or>or)\s+(?P<alternative>anything)\s+(?P<else>else)(?P<c3>,)\s+"
    rf"(?P<recipient_to>to)\s+(?:(?P<title>Mr|Mrs|Ms|Dr)(?P<dot>\.)\s+)?(?P<name>{W})(?P<stop>\.)",
    re.I,
)


def plan_resolution_content(text, components):
    m = PATTERN.fullmatch(text)
    if (m is None or not m["name"][0].isupper()
            or not any(c["id"] == "s0" and c["start"] == 0 and c["end"] == len(text)
                       and c["function"] == "matrix_clause" for c in components)):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    def phrase(group, rule):
        add("NP", *m.span(group), "phrase", proof_rule=rule)

    phrase("host", "np_det_n")
    lex("be", "COPULA", vform="finite", number="singular", lemma_in="be")
    lex("that", "COMP-THAT")
    add("NP", *m.span("subject"), "subject-phrase", pronominal="true")
    lex("modal", "MODAL", vform="finite")
    lex("make", "V", vform="base", lemma_in="make", subcat_member="transitive")
    phrase("decision", "np_det_n")
    lex("to", "TO")
    lex("grant", "V", vform="base", subcat_member="prep_ditransitive")
    lex("no", "DET", negation="true", lemma_in="no")
    lex("more", "DEGREE", comparative="true", lemma_in="more")
    lex("theme", "N", number="plural", lemma_in="loan|advance|grant|offer|promise")
    lex("of", "PREP", nominal_complement="of")
    add("NP", *m.span("source"), "phrase", simple_nominal_proof="true")
    lex("or", "COORD", lemma_in="or", nominal_coordination="true")
    lex("alternative", "INDEF-PRONOUN", lemma_in="anything")
    lex("else", "ADJ", lemma_in="else")
    lex("recipient_to", "PREP", lemma_in="to")
    if m["title"]:
        lex("title", "TITLE", honorific="true")
        punct("ABBREVIATION-STOP", *m.span("dot"))
    lex("name", "PROPER-NOUN")
    for group in ("c1", "c2", "c3"):
        punct("COMMA", *m.span(group))
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
