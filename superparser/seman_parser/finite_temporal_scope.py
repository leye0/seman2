"""Propose bounded source spans for finite temporal adjuncts."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_finite_temporal_scope_sentence"
WORD = r"[A-Za-z][A-Za-z'’\-]*"
SPAN = r"[^,;.!?()]+?"
SUBJ = r"I|you|he|she|it|we|they"
NAME = r"[A-Z][A-Za-z'’\-]*"

INTERPOSED = re.compile(
    rf"(?P<subject>{SUBJ})\s+(?P<matrix>{WORD})(?P<c1>,)\s+"
    rf"(?P<when>as)\s+(?P<time_subject>{SUBJ})\s+(?P<time_verb>{WORD})\s+"
    rf"(?P<time_pp>(?:toward|towards|past|through|into|to)\s+{SPAN})(?P<c2>,)\s+"
    rf"(?P<that>that)\s+(?P<inner>{SUBJ})\s+(?P<be>was|were)\s+"
    rf"(?P<manner>{WORD})\s+(?P<part>{WORD})\s+(?P<respect>even\s+in\s+{SPAN})", re.I,
)
AFTER_CONNECTIVE = re.compile(
    rf"(?P<connective>accordingly|therefore|consequently|thus)(?P<c1>,)\s+"
    rf"(?P<when>when)\s+(?P<title1>Mr|Mrs|Ms|Dr)(?P<dot1>\.)\s+(?P<name1>{NAME})\s+"
    rf"(?P<time_verb>{WORD})\s+(?P<place>home)\s+(?P<about>about|around|at)\s+"
    rf"(?P<hour>{WORD})\s+(?P<clock>o['’]clock)(?P<c2>,)\s+"
    rf"(?P<det>this|that)\s+(?P<description>{WORD})\s+"
    rf"(?P<title2>Mr|Mrs|Ms|Dr)(?P<dot2>\.)\s+(?P<name2>{NAME})\s+"
    rf"(?P<be>was|were)\s+(?P<activity>{WORD}ing)\s+"
    rf"(?P<activity_pp>in\s+{SPAN})(?P<c3>,)\s+(?P<state_in>in)\s+(?P<state_det>a|an)\s+(?P<intensity>{WORD})\s+(?P<state_adj1>{WORD})\s+(?P<state_coord>and)\s+(?P<state_adj2>{WORD})\s+(?P<state_head>{WORD})", re.I,
)
FRONTED = re.compile(
    rf"(?P<when>when)\s+(?P<time_subject>{SUBJ})\s+(?P<time_verb>{WORD})\s+"
    rf"(?P<time_pp>(?:with|among|amongst)\s+{SPAN})\s+"
    rf"(?P<subject>{SUBJ})\s+(?P<manner>{WORD})\s+(?P<matrix>{WORD})\s+"
    rf"(?P<how>how)\s+(?P<degree_adverb>{WORD})\s+(?P<degree_adjective>{WORD})\s+"
    rf"(?P<inner>(?:my|your|his|her|its|our|their|the)\s+{WORD})\s+(?P<be>was|were)"
    rf"(?P<c1>,)\s+(?P<and>and)\s+(?P<last_subject>{SPAN})\s+"
    rf"(?P<last_verb>{WORD})\s+(?P<last_object>the\s+{WORD})\s+(?P<last_of>of)\s+(?P<last_theme>{SPAN})", re.I,
)


def temporal_source_match(text):
    if text.endswith("."):
        for pattern in (INTERPOSED, AFTER_CONNECTIVE, FRONTED):
            if match := pattern.fullmatch(text[:-1]):
                return match
    return None


def finite_temporal_span(text):
    """Return the proposed adjunct's exact span without claiming a parse."""
    m = temporal_source_match(text)
    if m is None:
        return None
    tail = "clock" if m.re is AFTER_CONNECTIVE else "time_pp"
    return m.start("when"), m.end(tail)


def plan_finite_temporal_scope(text):
    m = temporal_source_match(text)
    if m is None:
        return None
    specs, add, punct, _ = _specs()

    def piece(group, cat, kind="phrase", **features):
        add(cat, *m.span(group), kind, **features)

    def lex(group, cat, **features):
        piece(group, cat, "lexical-alternatives", **features)

    def verb(group, form, frame, **features):
        lex(group, "V", vform=form, subcat_member=frame, **features)

    def subject(group):
        piece(group, "NP", "subject-phrase", pronominal="true")

    def mark(group, cat="COMMA"):
        piece(group, cat, "source-punctuation")

    if m.re is INTERPOSED:
        lex("when", "CONJ", simultaneous="true")
        subject("subject")
        verb("matrix", "finite", "clausal", nonbase_surface="true")
        mark("c1")
        mark("c2")
        lex("that", "COMP-THAT")
        subject("inner")
        lex("be", "AUX-BE", vform="finite")
        lex("manner", "ADV")
        verb("part", "ed", "transitive")
        piece("respect", "PP", proof_rule="pp_degree")
    elif m.re is AFTER_CONNECTIVE:
        lex("when", "CONJ", temporal_incise="true")
        lex("connective", "ADV")
        for group in ("c1", "c2", "c3"):
            mark(group)
        for title, dot, name in (("title1", "dot1", "name1"), ("title2", "dot2", "name2")):
            lex(title, "TITLE", honorific="true")
            mark(dot, "ABBREVIATION-STOP")
            lex(name, "PROPER-NOUN")
        verb("time_verb", "finite", "intransitive", nonbase_surface="true")
        lex("place", "ADV")
        lex("about", "PREP")
        lex("hour", "NUM")
        lex("clock", "ADV")
        lex("det", "DET", definiteness="demonstrative", number="singular")
        lex("description", "ADJ")
        lex("be", "AUX-BE", vform="finite")
        verb("activity", "ing", "intransitive")
        piece("activity_pp", "PP", proof_rule="pp_prep_np")
        lex("state_in", "PREP")
        lex("state_det", "DET", number="singular")
        lex("intensity", "DEGREE")
        lex("state_adj1", "ADJ")
        lex("state_coord", "COORD", nominal_coordination="true")
        lex("state_adj2", "ADJ")
        lex("state_head", "N", number="singular")
    else:
        lex("when", "CONJ", temporal_incise="true")
        subject("subject")
        lex("manner", "ADV")
        verb("matrix", "finite", "transitive", nonbase_surface="true", relative_frame="degree_content")
        lex("how", "WH-NOM", wh_adverbial="true")
        lex("degree_adverb", "ADV")
        lex("degree_adjective", "ADJ")
        piece("inner", "NP", "subject-phrase")
        lex("be", "COPULA", vform="finite")
        mark("c1")
        lex("and", "COORD", nominal_coordination="true")
        piece("last_subject", "NP", "subject-phrase")
        verb("last_verb", "finite", "transitive", nonbase_surface="true")
        piece("last_object", "NP", proof_rule="np_det_n")
        lex("last_of", "PREP", nominal_complement="of")
        piece("last_theme", "NP")

    if m.re is not AFTER_CONNECTIVE:
        subject("time_subject")
        verb("time_verb", "finite", "prepositional", nonbase_surface="true")
        piece("time_pp", "PP", proof_rule="pp_prep_np")
    punct("SPEECH-STOP", len(text)-1, len(text))
    return sorted(specs, key=lambda row: row[1])
