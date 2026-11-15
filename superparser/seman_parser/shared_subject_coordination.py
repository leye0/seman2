"""Bounded source plans for finite predicates sharing an overt subject."""

from __future__ import annotations

import re

from .dialogue import quotation_boundaries
from .dialogue_clause_plans import _specs
from .manner_coordination import manner_coordination_plan, semicolon_coordination
from .measured_voice_coordination import measured_voice_plan

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
    ("semicolon_supplement", re.compile(
        rf"(?P<frame>here|there|then|now)\s+(?P<subject>{WORD})\s+(?P<first>{WORD})(?P<semi>;)"
        rf"\s+(?P<and>and)\s+(?P<part1>{WORD}ing\s+{SPAN})(?P<join>,)\s+"
        rf"(?P<part_and>and)\s+(?P<part2>{WORD}ing\s+{SPAN})(?P<aside>,)\s+"
        rf"(?P<link>{WORD})\s+(?P<as>as)\s+(?P<if>if)\s+"
        rf"(?P<inner_subject>{WORD})\s+(?P<modal1>{WORD})\s+"
        rf"(?P<be1>be)\s+(?P<passive1>{WORD})(?P<contrast>,)\s+"
        rf"(?P<but>but)\s+(?P<modal2>{WORD})\s+(?P<negative>{WORD})\s+"
        rf"(?P<be2>be)\s+(?P<passive2>{WORD})", re.I,
    )),
)


def plan_shared_subject_coordination(text, components=()):
    if "," not in text:
        return measured_voice_plan(text, components)
    if not text.endswith(".") or quotation_boundaries(text):
        return None
    for family, pattern in PATTERNS:
        match = pattern.fullmatch(text[:-1])
        if match:
            break
    else:
        return manner_coordination_plan(text, components)
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

    for comma in ("join", "aside", "attrs", "contrast"):
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
    elif family == "temporal":
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
    else:
        if not semicolon_coordination(components, match.start("semi"),
                                      match.start("and"), len(text)):
            return None
        piece("semi", "SEMICOLON", "source-punctuation")
        lexical("frame", "ADV")
        subject("subject", pronominal="true")
        verb("first", "finite", "intransitive", nonbase_surface="true")
        piece("part1", "TRANSITIVE-PARTICIPIAL")
        lexical("part_and", "COORD", nominal_coordination="true")
        piece("part2", "TRANSITIVE-PARTICIPIAL")
        verb("link", "finite", "linking", nonbase_surface="true",
             lemma_in="appear|feel|look|seem|smell|sound|taste")
        lexical("as", "CONJ", degree="true")
        lexical("if", "CONJ", complementizer="conditional")
        subject("inner_subject", pronominal="true")
        for n in ("1", "2"):
            lexical("modal" + n, "MODAL", vform="finite")
            verb("be" + n, "base", "linking", lemma_in="be")
            verb("passive" + n, "ed", "transitive")
        lexical("but", "COORD", nominal_coordination="true")
        lexical("negative", "DEGREE", negation="true")
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return sorted(specs, key=lambda spec: spec[1])
