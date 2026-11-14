"""Propose source spans for relatives with an embedded argument gap."""

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

PREVENTIVE = re.compile(
    rf"(?P<frequency>{WORD})\s+(?P<subject>I|you|he|she|we|they)\s+"
    rf"(?P<matrix>{WORD})\s+(?P<with>with)\s+"
    rf"(?P<poss>my|your|his|her|our|their)\s+(?P<plural>{WORD})\s+"
    rf"(?P<part>{WORD})\s+(?P<passive_pp>on\s+{SPAN})(?P<c1>,)\s+"
    rf"(?P<control>{WORD}ing)\s+(?P<to>to)\s+(?P<action>{WORD})\s+"
    rf"(?P<object>me|him|her|us|them|you|it)\s+(?P<lest>lest)\s+"
    rf"(?P<prevent_subject>I|you|he|she|it|we|they)\s+(?P<modal>should)\s+"
    rf"(?P<prevent_verb>{WORD})\s+(?P<head>(?:the|a|an)\s+{SPAN})\s+"
    rf"(?P<which>which)\s+(?P<inner>I|you|he|she|we|they)\s+"
    rf"(?P<degree>so\s+much)\s+(?P<inner_control>{WORD})\s+"
    rf"(?P<inner_to>to)\s+(?P<bare>{WORD})", re.I,
)
STRANDED_SUPPLEMENT = re.compile(
    rf"(?P<subject>(?:the|a|an)\s+{SPAN})\s+(?P<aux>was|were)\s+"
    rf"(?P<matrix>{WORD}ing)\s+(?P<particle>down)(?P<c1>,)\s+"
    rf"(?P<depictive>as\s+{WORD}\s+as\s+{SPAN})(?P<c2>,)\s+"
    rf"(?P<ing>{WORD}ing)\s+(?P<of>of)\s+"
    rf"(?P<head>(?:the|a|an)\s+{SPAN})\s+"
    rf"(?P<inner>I|you|he|she|we|they)\s+(?P<have>had)\s+"
    rf"(?P<part>{WORD})\s+(?P<recipient>me|him|her|us|them|you)\s+"
    rf"(?P<to>to)(?P<c3>,)\s+(?P<apposition>the\s+{SPAN})", re.I,
)


def plan_embedded_relative_scope(text):
    if not text or text[-1] not in ".!":
        return None
    m = TRANSFER.fullmatch(text[:-1]) if text.endswith(".") else None
    family = "transfer"
    if m is None and text.endswith("."):
        m, family = AFTERTHOUGHT.fullmatch(text[:-1]), "afterthought"
    if m is None and text.endswith("."):
        m, family = PREVENTIVE.fullmatch(text[:-1]), "preventive"
    if m is None:
        m, family = STRANDED_SUPPLEMENT.fullmatch(text[:-1]), "stranded_supplement"
    if m is None:
        return None
    specs, add, punct, _ = _specs()

    def piece(group, cat, kind="phrase", **features):
        add(cat, *m.span(group), kind, **features)

    def lex(group, cat, **features):
        piece(group, cat, "lexical-alternatives", **features)

    def verb(group, form, frame, **features):
        lex(group, "V", vform=form, subcat_member=frame, **features)

    if family in ("transfer", "afterthought"):
        lex("that", "COMP-THAT")
        piece("inner", "NP", "subject-phrase", pronominal="true")
        lex("copula", "COPULA", vform="finite")
        piece("head", "NP", proof_rule="np_det_n")
        if family == "transfer":
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
    elif family == "preventive":
        lex("frequency", "ADV")
        piece("subject", "NP", "subject-phrase", pronominal="true")
        verb("matrix", "finite", "intransitive", nonbase_surface="true")
        lex("with", "PREP", supplementary_with="true")
        lex("poss", "POSS")
        lex("plural", "N", number="plural")
        verb("part", "ed", "transitive")
        piece("passive_pp", "PP", proof_rule="pp_prep_np")
        piece("c1", "COMMA", "source-punctuation")
        verb("control", "ing", "subject_control")
        lex("to", "TO")
        verb("action", "base", "transitive")
        piece("object", "NP", pronominal="true")
        piece("lest", "PREVENTIVE-CONJ", "source-preventive-conjunction")
        piece("prevent_subject", "NP", "subject-phrase", pronominal="true")
        lex("modal", "MODAL", vform="finite")
        verb("prevent_verb", "base", "transitive")
        piece("head", "NP", proof_rule="np_det_n")
        lex("which", "WH-REL-OBL", relative="true")
        piece("inner", "NP", "subject-phrase", pronominal="true")
        piece("degree", "ADVP", proof_rule="advp_degree_adv")
        verb("inner_control", "finite", "subject_control", nonbase_surface="true")
        lex("inner_to", "TO")
        verb("bare", "base", "transitive")
    else:
        piece("subject", "NP", "subject-phrase", proof_rule="np_det_n")
        lex("aux", "AUX-BE", vform="finite")
        verb("matrix", "ing", "intransitive", relative_frame="down_particle")
        lex("particle", "PARTICLE")
        piece("c1", "COMMA", "source-punctuation")
        piece("depictive", "ADJP", proof_rule="adj_as_as")
        piece("c2", "COMMA", "source-punctuation")
        verb("ing", "ing", "intransitive", relative_frame="of_topic")
        lex("of", "PREP", preposition_form="of")
        piece("head", "NP", proof_rule="np_det_n")
        piece("inner", "NP", "subject-phrase", pronominal="true")
        lex("have", "HAVE", vform="finite")
        verb("part", "ed", "transitive", relative_frame="directional_object")
        piece("recipient", "NP", pronominal="true")
        lex("to", "PREP")
        piece("c3", "COMMA", "source-punctuation")
        piece("apposition", "NP", proof_rule="np_det_n")
    punct("SPEECH-STOP", len(text)-1, len(text))
    return sorted(specs, key=lambda row: row[1])
