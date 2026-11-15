"""Compose a comma-marked evaluative clause and its content reprise."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_extraposed_object_relative"
WORD = r"[A-Za-z][A-Za-z'’\-]*"
SUBJECT = r"I|you|he|she|we|they"
OBJECT = r"me|you|him|her|us|them"
EVALUATION = "judge|deem|consider|find|think"
ATTRIBUTES = "advisable|best|expedient|fitting|necessary|proper|prudent|wise"
TRANSFER = "tell|show|teach"
KNOWLEDGE = "know|learn|discover|see|hear|find|remember|observe|notice|read|collect"
REPORT = "recount|relate|report|describe|summarize|summarise|repeat|retell"
PATTERN = re.compile(
    rf"(?P<subject>{SUBJECT})\s+(?P<judge>{WORD})\s+(?P<it>it)\s+"
    rf"(?P<attribute>{ATTRIBUTES})(?P<comma_left>,)\s+(?P<time>now|then)(?P<comma_right>,)\s+"
    rf"(?P<to>to)\s+(?P<transfer>{WORD})\s+(?P<recipient>{OBJECT})\s+"
    rf"(?P<theme>all|everything|something)\s+(?P<knower>{SUBJECT})\s+(?P<know>{WORD})"
    rf"(?P<semi>;)\s+(?P<which>which)\s+(?P<reporter>{SUBJECT})\s+(?P<report>{WORD})\s+"
    rf"(?P<manner>at length|in detail)(?P<stop>\.)",
    re.I,
)


def plan_extraposed_object_relative(text, components):
    m = PATTERN.fullmatch(text)
    if m is None:
        return None
    nodes = {c["id"]: c for c in components}
    for node, governor, function, span in (
        ("s0", "u0", "matrix_clause", (0, m.start("semi"))),
        ("s1", "s0", "supplementary_relative_clause", (m.start("which"), len(text))),
    ):
        c = nodes.get(node, {})
        if (c.get("governor"), c.get("function"), c.get("start"), c.get("end")) != (
            governor, function, *span,
        ):
            return None

    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    for group in ("subject", "knower", "reporter"):
        add("NP", *m.span(group), "subject-phrase", pronominal="true")
    lex("judge", "V", vform="finite", nonbase_surface="true",
        lemma_in=EVALUATION, subcat_member="complex_transitive")
    lex("it", "EXTRAPOSITION-IT", extraposition_it="true")
    lex("attribute", "ADJ", lemma_in=ATTRIBUTES)
    lex("time", "ADV", lemma_in="now|then")
    lex("to", "TO")
    lex("transfer", "V", vform="base", lemma_in=TRANSFER, subcat_member="ditransitive")
    if m["recipient"].casefold() == "you":
        lex("recipient", "PRONOUN", lemma_in="you")
    else:
        lex("recipient", "PRONOUN", case="accusative")
    lex("theme", "PRONOUN", lemma_in="all|everything|something")
    lex("know", "V", vform="finite", nonbase_surface="true",
        lemma_in=KNOWLEDGE, subcat_member="transitive")
    lex("which", "WH-REL-OBL", relative="true", lemma_in="relative-which")
    lex("report", "V", vform="finite", nonbase_surface="true",
        lemma_in=REPORT, subcat_member="transitive")
    add("PP", *m.span("manner"), "phrase", proof_rule="pp_prep_np")
    punct("COMMA", *m.span("comma_left"))
    punct("COMMA", *m.span("comma_right"))
    punct("SEMICOLON", *m.span("semi"))
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
