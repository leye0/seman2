"""Source plan for two causal nominals under a single passive by-phrase."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _parts, _specs

ROOT = "structural_adversative_shared_by_sentence"
CHUNK = r"""[^,;.!?()"“”]+?"""
WORD = r"[A-Za-z][A-Za-z'’\-]*"

ADVERSATIVE = re.compile(
    rf"(?P<left>{CHUNK})(?P<comma>,)\s+(?:(?P<clausal_and>and)\s+)?"
    rf"(?P<contrast>yet|but)\s+(?P<passive>{CHUNK})\s+"
    rf"(?P<both>both)\s+(?P<by>by)\s+(?P<first>{CHUNK})\s+"
    rf"(?P<and>and)\s+(?P<second>{CHUNK})(?P<stop>\.)", re.I,
)
NOUN_CONTENT = re.compile(
    rf"(?P<head>(?:the|a|an)\s+{WORD})\s+(?P<of>of)\s+(?P<content>{CHUNK})", re.I,
)


def shared_by_match(text):
    return ADVERSATIVE.fullmatch(text)


def plan_shared_by_coordination(text, components):
    match = shared_by_match(text)
    if (match is None or len(_parts(components, "matrix_clause")) != 1
            or _parts(components, "direct_speech", "embedded_quotation")):
        return None
    by_phrase = _parts(components, "shared_preposition_candidate")
    if not any((c["start"], c["end"]) == (match.start("both"), match.end("second"))
               and c["governor"] == "s0" for c in by_phrase):
        return None

    specs, add, punct, _ = _specs()

    def piece(group, cat, kind="lexical-alternatives", **features):
        add(cat, *match.span(group), kind, **features)

    piece("left", "CLAUSE", "phrase", proof_rule="clause_np_vp")
    punct("COMMA", *match.span("comma"))
    if match["clausal_and"] and match["contrast"].casefold() != "yet":
        return None
    if match["clausal_and"]:
        piece("clausal_and", "COORD", nominal_coordination="true")
    if match["contrast"].casefold() == "yet":
        piece("contrast", "COORD", adversative="true")
    else:
        piece("contrast", "COORD", lemma_in="but", nominal_coordination="true")
    piece("passive", "CLAUSE", "phrase", voice="passive", proof_rule="clause_passive",
          passive_cause_proof="true")
    piece("both", "DET", quantifier="both", number="plural")
    piece("by", "PREP-BY", lemma_in="by")
    for group in ("first", "second"):
        start, end = match.span(group)
        nominal = NOUN_CONTENT.fullmatch(text, start, end)
        if nominal:
            add("NP", *nominal.span("head"), "phrase", proof_rule="np_det_n")
            add("PREP", *nominal.span("of"), "lexical-alternatives", nominal_complement="of")
            add("NP", *nominal.span("content"), "phrase", simple_nominal_proof="true")
        else:
            add("NP", start, end, "phrase", simple_nominal_proof="true")
    piece("and", "COORD", nominal_coordination="true")
    punct("SPEECH-STOP", *match.span("stop"))
    return sorted(specs, key=lambda row: row[1])
