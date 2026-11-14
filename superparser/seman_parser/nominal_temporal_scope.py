"""Propose overt spans for a temporal adjunct inside a nominal modifier."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

WORD = r"[A-Za-z][A-Za-z'’\-]*"
SPAN = r"[^,;.!?()]+?"
NAME = r"[A-Z][A-Za-z'’\-]*"
DEPICTION = re.compile(
    rf"(?P<title>Mr|Mrs|Ms|Dr)(?P<dot>\.)\s+(?P<name>{NAME})\s+"
    rf"(?P<order>{WORD})\s+(?P<matrix>{WORD})\s+(?P<object>{SPAN})\s+"
    rf"(?P<to>to)\s+(?P<one>one)\s+(?P<of>of)\s+"
    rf"(?P<sitter_title>Miss|Mr|Mrs|Ms|Dr)(?P<sitter_dot>\.)?\s+(?P<sitter>{NAME})(?P<c1>,)\s+"
    rf"(?P<part>{WORD})\s+(?P<when>when)\s+(?P<age_subject>he|she|they)\s+"
    rf"(?P<age_be>was|were)\s+(?P<only>only)\s+(?P<age>{WORD})\s+"
    rf"(?P<unit>years|months)\s+(?P<old>old)", re.I,
)
INTERVAL = re.compile(
    rf"(?P<experiencer_state>{WORD}\s+and\s+{WORD})(?P<c1>,)\s+"
    rf"(?P<subject>the\s+{WORD})\s+(?P<which>which)\s+(?P<relative_verb>{WORD})\s+"
    rf"(?P<location>in\s+{SPAN})(?P<c2>,)\s+"
    rf"(?P<before>before)\s+(?P<time_det>the)\s+(?P<time_subject>{WORD})\s+(?P<time_verb>{WORD})(?P<c3>,)\s+"
    rf"(?P<be>was|were)\s+(?P<matrix_state>{WORD}\s+and\s+{WORD})\s+"
    rf"(?P<degree_to>to)\s+(?P<degree>a\s+degree)\s+(?P<that>that)\s+"
    rf"(?P<almost>almost)\s+(?P<cause>{WORD})\s+(?P<experiencer>him|her|them|us|me)\s+"
    rf"(?P<result>{WORD})", re.I,
)


def nominal_temporal_match(text):
    if not text.endswith("."):
        return None
    return DEPICTION.fullmatch(text[:-1]) or INTERVAL.fullmatch(text[:-1])


def nominal_temporal_spans(text):
    """Return the nominal modifier and its temporal child, without resolving syntax."""
    m = nominal_temporal_match(text)
    if m is None:
        return None
    if m.re is DEPICTION:
        return (m.start("part"), m.end("old"), m.start("when"), m.end("old"))
    return (m.start("which"), m.end("time_verb"), m.start("before"), m.end("time_verb"))


def plan_nominal_temporal_scope(text):
    m = nominal_temporal_match(text)
    if m is None:
        return None
    specs, add, punct, _ = _specs()

    def piece(group, cat, kind="phrase", **features):
        add(cat, *m.span(group), kind, **features)

    def lex(group, cat, **features):
        piece(group, cat, "lexical-alternatives", **features)

    def verb(group, form, frame, **features):
        lex(group, "V", vform=form, subcat_member=frame, **features)

    def comma(group):
        piece(group, "COMMA", "source-punctuation")

    comma("c1")
    if m.re is DEPICTION:
        lex("title", "TITLE", honorific="true")
        piece("dot", "ABBREVIATION-STOP", "source-punctuation")
        lex("name", "PROPER-NOUN")
        lex("order", "ADV")
        verb("matrix", "finite", "prep_ditransitive", nonbase_surface="true")
        piece("object", "NP", proof_rule="np_poss")
        lex("to", "PREP")
        lex("one", "NUM")
        lex("of", "PREP", nominal_complement="of")
        if m.start("sitter_dot") >= 0:
            lex("sitter_title", "TITLE", honorific="true")
            piece("sitter_dot", "ABBREVIATION-STOP", "source-punctuation")
        else:
            piece("sitter_title", "TITLE", "temporal-source-form", honorific="true")
        lex("sitter", "PROPER-NOUN")
        verb("part", "ed", "transitive", temporal_frame="depiction")
        lex("when", "CONJ", temporal_incise="true")
        piece("age_subject", "NP", "subject-phrase", pronominal="true")
        lex("age_be", "COPULA", vform="finite")
        lex("only", "ADV", nominal_focus="true")
        lex("age", "NUM")
        lex("unit", "N", number="plural")
        lex("old", "ADJ")
    else:
        piece("experiencer_state", "ADJP", proof_rule="adjp_coord")
        piece("subject", "NP", "subject-phrase", proof_rule="np_det_n")
        lex("which", "WH-REL-OBL", relative="true")
        verb("relative_verb", "finite", "prepositional", nonbase_surface="true",
             temporal_frame="interval_predicate")
        piece("location", "PP", proof_rule="pp_prep_np")
        comma("c2")
        piece("before", "CONJ", "temporal-source-form", temporal_order="before")
        lex("time_det", "DET", definiteness="definite", number="plural")
        piece("time_subject", "N", "temporal-source-form", number="plural")
        verb("time_verb", "finite", "intransitive", nonbase_surface="true", temporal_frame="bounded_arrival")
        comma("c3")
        lex("be", "COPULA", vform="finite")
        piece("matrix_state", "ADJP", proof_rule="adjp_coord")
        lex("degree_to", "PREP")
        piece("degree", "NP", proof_rule="np_det_n")
        lex("that", "WH-PRONOUN", wh="true")
        lex("almost", "ADV")
        verb("cause", "finite", "complex_transitive", nonbase_surface="true")
        piece("experiencer", "NP", pronominal="true")
        lex("result", "ADJ")
    punct("SPEECH-STOP", len(text)-1, len(text))
    return sorted(specs, key=lambda row: row[1])
