"""Source plan for a conditional series with ellipsis and a fronted object."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_conditional_ellipsis_series"
W = r"[A-Za-z][A-Za-z'’\-]*"
POSS = r"my|your|his|her|our|their"
SUBJ = r"I|you|he|she|we|they"
PATTERN = re.compile(
    rf"(?P<if>if)\s+(?P<that>that)\s+(?P<were>were)\s+(?P<so>so)(?P<c1>,)\s+"
    rf"(?P<first>(?:{POSS})\s+{W})\s+(?P<was>was)\s+(?P<value>nothing|everything|something)(?P<s1>;)\s+"
    rf"(?P<obligation>(?:{POSS})\s+(?:{W}\s+)?{W})\s+(?P<to>to)\s+(?P<beneficiary>me|you|him|her|us|them)\s+"
    rf"(?P<state>unfulfilled|unmet|unanswered|undischarged|unfinished)(?P<s2>;)\s+"
    rf"(?P<and>and)\s+(?P<head>every\s+{W}(?:\s+{W})?)\s+"
    rf"(?P<avoider>{SUBJ})\s+(?P<had>had)\s+(?P<avoid>{W})\s+(?P<from>from)(?P<c2>,)\s+"
    rf"(?P<doer>{SUBJ})\s+(?P<be>am|is|are|was|were)\s+"
    rf"(?P<time>hourly|daily|continually|constantly|repeatedly)\s+(?P<do>{W})(?P<stop>\.)", re.I,
)


def plan_conditional_series(text, components):
    m = PATTERN.fullmatch(text)
    if m is None:
        return None
    nodes = {node["id"]: node for node in components}
    for node, gov, span in (
        ("a0", "s0", (0, m.start("c1"))),
        ("s0", "u0", (0, m.start("s1"))),
        ("s1", "s0", (m.start("obligation"), m.start("s2"))),
        ("s2", "s1", (m.start("and"), len(text))),
    ):
        n = nodes.get(node, {})
        if (n.get("governor"), n.get("start"), n.get("end")) != (gov, *span):
            return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    lex("if", "CONJ", complementizer="conditional", lemma_in="if")
    lex("that", "PRONOUN", definiteness="demonstrative", number="singular")
    lex("were", "COPULA", vform="finite", lemma_in="be")
    lex("so", "ADV", lemma_in="so")
    add("NP", *m.span("first"), "phrase", proof_rule="np_poss", number="singular")
    lex("was", "COPULA", vform="finite", lemma_in="be", number="singular")
    lex("value", "PRONOUN")
    add("NP", *m.span("obligation"), "phrase", proof_rule="np_poss", number="singular")
    lex("to", "PREP", lemma_in="to")
    if m["beneficiary"].casefold() == "you":
        lex("beneficiary", "PRONOUN", lemma_in="you")
    else:
        lex("beneficiary", "PRONOUN", case="accusative")
    lex("state", "ADJ")
    lex("and", "COORD", lemma_in="and")
    add("NP", *m.span("head"), "phrase", proof_rule="np_det_n", definiteness="universal")
    for group in ("avoider", "doer"):
        add("NP", *m.span(group), "subject-phrase", pronominal="true")
    lex("had", "HAVE", vform="finite")
    lex("avoid", "V", vform="ed", lemma_in="shrink|recoil|retreat|flinch|refrain|abstain",
        subcat_member="prepositional")
    lex("from", "PREP", lemma_in="from")
    lex("be", "COPULA", vform="finite", lemma_in="be")
    lex("time", "ADV")
    lex("do", "V", vform="ing", subcat_member="transitive")
    for group in ("c1", "c2"):
        punct("COMMA", *m.span(group))
    for group in ("s1", "s2"):
        punct("SEMICOLON", *m.span(group))
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
