"""Propose source spans for an object gap inside an adjectival complement."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_embedded_relative_sentence"
WORD = r"[A-Za-z][A-Za-z’'\-]*"
SPAN = r"[^,;.!?()]+?"
TRANSFER = re.compile(
    rf"(?P<subject>(?:these|those|the)\s+{SPAN})\s+(?P<matrix>{WORD})\s+"
    rf"(?P<recipient>me|him|her|us|them|you)\s+(?P<head>(?:the|a|an)\s+{SPAN})\s+"
    rf"(?P<that>that)\s+(?P<inner>{WORD})\s+(?P<copula>{WORD})\s+"
    rf"(?P<adj>{WORD})\s+(?P<of>of)\s+(?P<ing>{WORD}ing)", re.I,
)
AFTERTHOUGHT = re.compile(
    rf"(?P<count>two|three|four|five|six|seven|eight|nine|ten)\s+(?P<of>of)\s+"
    rf"(?P<det>the)\s+(?P<plural>{WORD})(?P<c1>,)\s+(?P<part>{WORD})\s+"
    rf"(?P<passive_pp>in\s+{SPAN})(?P<c2>,)\s+(?P<matrix>{WORD})\s+"
    rf"(?P<head>(?:a|an)\s+[^,;.!?()]+?)(?P<dash>--|—)\s*"
    rf"(?P<one>one)\s+(?P<that>that)\s+(?P<inner>{WORD})\s+"
    rf"(?P<copula>{WORD})\s+(?P<adj>{WORD})\s+(?P<to>to)\s+"
    rf"(?P<bare>{WORD})\s+(?P<manner>{WORD})\s+(?P<with>with)", re.I,
)


def plan_embedded_relative_scope(text):
    if not text.endswith("."):
        return None
    m = TRANSFER.fullmatch(text[:-1])
    transfer = m is not None
    if m is None:
        m = AFTERTHOUGHT.fullmatch(text[:-1])
    if m is None:
        return None
    specs, add, punct, _ = _specs()

    def piece(group, cat, kind="phrase", **features):
        add(cat, *m.span(group), kind, **features)

    def lex(group, cat, **features):
        piece(group, cat, "lexical-alternatives", **features)

    def verb(group, form, frame, **features):
        lex(group, "V", vform=form, subcat_member=frame, **features)

    lex("that", "COMP-THAT")
    piece("inner", "NP", "subject-phrase", pronominal="true")
    lex("copula", "COPULA", vform="finite")
    piece("head", "NP", proof_rule="np_det_n")
    if transfer:
        piece("subject", "NP", proof_rule="np_determiner_adjp_head")
        verb("matrix", "finite", "transitive", nonbase_surface="true",
             relative_frame="ditransitive")
        piece("recipient", "NP", pronominal="true")
        lex("adj", "ADJ", relative_frame="adjective_of_gerund")
        lex("of", "PREP", nominal_complement="of")
        verb("ing", "ing", "transitive")
    else:
        lex("count", "NUM")
        lex("of", "PREP", nominal_complement="of")
        lex("det", "DET", number="plural")
        lex("plural", "N", number="plural")
        piece("c1", "COMMA", "source-punctuation")
        verb("part", "ed", "transitive")
        piece("passive_pp", "PP", proof_rule="pp_prep_np")
        piece("c2", "COMMA", "source-punctuation")
        verb("matrix", "finite", "transitive", nonbase_surface="true")
        piece("dash", "DASH", "source-punctuation")
        lex("one", "NUM")
        lex("adj", "ADJ", to_infinitive="true")
        lex("to", "TO")
        verb("bare", "base", "intransitive", relative_frame="comitative_movement")
        lex("manner", "ADV")
        lex("with", "PREP")
    punct("SPEECH-STOP", len(text)-1, len(text))
    return sorted(specs, key=lambda row: row[1])
