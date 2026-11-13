"""Bounded source plans for finite predicates sharing an overt subject."""

from __future__ import annotations

import re

from .dialogue import quotation_boundaries
from .dialogue_clause_plans import _specs

ROOT = "structural_shared_subject_source_sentence"
WORD = r"[A-Za-z][A-Za-z’'\-]*"
SPAN = r"[^,;.!?()]+?"
PATTERNS = (
    ("reported", re.compile(
        rf"(?P<speaker>{WORD})\s+(?P<report>{WORD})\s+(?P<recipient>{WORD})\s+"
        rf"(?P<that>that)\s+(?P<subject>{WORD})\s+(?P<left>{SPAN})(?P<join>,)\s+"
        rf"(?P<and>and)\s+(?P<aux>{WORD})\s+(?P<progress>{WORD}ing)\s+"
        rf"(?P<particle>on)\s+(?P<manner>{SPAN})", re.I,
    )),
    ("concessive", re.compile(
        rf"(?P<subject>{SPAN})\s+(?P<left>had\s+{SPAN})(?P<join>,)\s+"
        rf"(?P<and>and)\s+(?P<though>though)\s+(?P<reduced>{WORD})(?P<aside>,)\s+"
        rf"(?P<copula>{WORD})\s+(?P<attribute>{SPAN})(?P<attrs>,)\s+"
        rf"(?P<also>and)\s+(?P<neg>not)\s+(?P<healthy>{WORD})\s+"
        rf"(?P<enough>enough)\s+(?P<to>to)\s+(?P<action>{WORD})\s+(?P<object>{SPAN})",
        re.I,
    )),
    ("temporal", re.compile(
        rf"(?P<subject>{SPAN})\s+(?P<first>{WORD})\s+(?P<cause>for\s+{SPAN})\s+"
        rf"(?P<when>when)\s+(?P<subordinate>{WORD})\s+(?P<seeing>{WORD})\s+"
        rf"(?P<seen>{SPAN})\s+(?P<origin>from\s+{SPAN})(?P<join>,)\s+"
        rf"(?P<and>and)\s+(?P<second>{WORD})\s+(?P<with>with\s+{SPAN})\s+"
        rf"(?P<theme>(?:the|a|an|their|his|her|our)\s+{SPAN})", re.I,
    )),
)


def plan_shared_subject_coordination(text):
    if not text.endswith(".") or "," not in text or quotation_boundaries(text):
        return None
    for family, pattern in PATTERNS:
        match = pattern.fullmatch(text[:-1])
        if match:
            break
    else:
        return None
    specs, add, mark, _ = _specs()

    def piece(group, category, kind="phrase", **features):
        start, end = match.span(group)
        add(category, start, end, kind, **features)

    def lexical(group, category, **features):
        piece(group, category, "lexical-alternatives", **features)

    def verb(group, form, frame, **features):
        lexical(group, "V", vform=form, subcat_member=frame, **features)

    def subject(group, **features):
        piece(group, "NP", "subject-phrase", **features)

    for comma in ("join", "aside", "attrs"):
        if comma in match.groupdict():
            piece(comma, "COMMA", "source-punctuation")
    lexical("and", "COORD", nominal_coordination="true")
    if family == "reported":
        subject("speaker", pronominal="true")
        verb("report", "finite", "clausal", selects_report_addressee="true")
        piece("recipient", "NP", pronominal="true")
        lexical("that", "COMP-THAT")
        subject("subject", pronominal="true")
        piece("left", "VP", vform="finite", voice="active", proof_rule="vp_transitive")
        lexical("aux", "AUX-BE", vform="finite")
        verb("progress", "ing", "intransitive", progress_particle_on="true")
        lexical("particle", "PARTICLE")
        piece("manner", "ADVP")
    elif family == "concessive":
        subject("subject")
        piece("left", "VP", vform="finite", voice="active", proof_rule="vp_adv")
        lexical("though", "CONJ", concessive="true")
        lexical("reduced", "ADJ")
        lexical("copula", "COPULA", vform="finite")
        piece("attribute", "ADJP")
        lexical("also", "COORD", nominal_coordination="true")
        lexical("neg", "NEG", negation="true")
        lexical("healthy", "ADJ")
        lexical("enough", "DEGREE")
        lexical("to", "TO")
        verb("action", "base", "transitive")
        piece("object", "NP")
    else:
        subject("subject")
        verb("first", "finite", "intransitive", nonbase_surface="true")
        piece("cause", "PP", proof_rule="pp_prep_np")
        lexical("when", "CONJ", temporal_incise="true")
        subject("subordinate", pronominal="true")
        verb("seeing", "finite", "transitive", nonbase_surface="true")
        piece("seen", "NP", proof_rule="np_det_n")
        piece("origin", "PP", proof_rule="pp_prep_np")
        verb("second", "finite", "transitive", nonbase_surface="true")
        piece("with", "PP", proof_rule="pp_prep_np")
        piece("theme", "NP")
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return sorted(specs, key=lambda spec: spec[1])
