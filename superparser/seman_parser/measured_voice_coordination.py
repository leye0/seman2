"""Bound the measure, two predicates and subject relative of a source clause."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

WORD = r"[A-Za-z][A-Za-z’'\-]*"
NOMINAL = rf"(?:(?:the|a|an|my|our|his|her|their|this|that|these|those)\s+)?{WORD}(?:\s+{WORD}){{0,2}}?"
PATTERN = re.compile(
    rf"(?P<subject>{NOMINAL})\s+(?P<aux>was|were|is|are)\s+(?P<participle>{WORD})\s+"
    rf"(?:(?P<article>a)\s+(?P<couple>couple)\s+(?P<of>of)|"
    rf"(?P<number>two|three|four|five|six|seven|eight|nine|ten|eleven|twelve))\s+(?P<unit>{WORD})\s+"
    rf"(?P<comparison>nearer|closer|farther|further)\s+"
    rf"(?:(?P<direction>to|from)\s+)?(?P<landmark>{NOMINAL})\s+"
    rf"(?P<and>and)\s+(?P<time>now|then)\s+(?P<active>{WORD})\s+"
    rf"(?P<antecedent>{NOMINAL})\s+(?P<relative>that)\s+(?P<modal>would|could|might|will)\s+"
    rf"(?P<degree>just|almost)\s+(?P<action>{WORD})\s+(?P<object>{NOMINAL})\s+"
    rf"(?P<side_preposition>on)\s+(?P<side>the\s+(?:east|west|north|south|left|right))(?P<stop>\.)",
    re.I,
)
NAMED_SUBJECT = re.compile(r"(?P<article>[Tt]he)\s+(?P<name>[A-Z][A-Z\-]+)")


def _match(text):
    match = PATTERN.fullmatch(text)
    if match is None:
        return None
    comparison = match["comparison"].casefold()
    preposition = (match["direction"] or "").casefold()
    if preposition not in {
        "nearer": ("", "to"), "closer": ("to",),
        "farther": ("from",), "further": ("from",),
    }[comparison]:
        return None
    return match


def measured_voice_spans(text):
    match = _match(text)
    if match:
        return (match.start("aux"), match.end("landmark")), (match.start("time"), match.start("stop"))


def measured_voice_plan(text, components):
    match = _match(text)
    if match is None:
        return None
    left, right = measured_voice_spans(text)
    if not all(any(c["function"] == "coordinate_predicate" and c["relation"] == "shared_subject"
                   and c["governor"] == "s0" and (c["start"], c["end"]) == span
                   for c in components) for span in (left, right)):
        return None
    specs, add, mark, _ = _specs()

    def lexical(group, category, **features):
        add(category, *match.span(group), "lexical-alternatives", **features)

    named = NAMED_SUBJECT.fullmatch(match["subject"])
    if named:
        offset = match.start("subject")
        for group, category in (("article", "DET"), ("name", "PROPER-NOUN")):
            a, b = named.span(group)
            add(category, offset + a, offset + b, "lexical-alternatives")
    else:
        add("NP", *match.span("subject"), "subject-phrase")
    lexical("aux", "AUX-BE", vform="finite")
    lexical("participle", "V", vform="ed", subcat_member="transitive",
            lemma_in="lay|push|move|pull|position|shift|bring|turn|steer")
    if match["number"]:
        lexical("number", "NUM")
    else:
        lexical("article", "DET", definiteness="indefinite", number="singular")
        lexical("couple", "N", lemma_in="couple", number="singular")
        lexical("of", "PREP", nominal_complement="of")
    lexical("unit", "N", number="plural", lemma_in="point|degree|mile|yard|metre|meter|foot|inch|kilometre|kilometer")
    lexical("comparison", "ADV", lemma_in=match["comparison"].casefold())
    if match["direction"]:
        lexical("direction", "PREP", lemma_in=match["direction"].casefold())
    for group in ("landmark", "antecedent", "object"):
        add("NP", *match.span(group), "phrase", simple_nominal_proof="true")
    lexical("and", "COORD", nominal_coordination="true", lemma_in="and")
    lexical("time", "ADV", lemma_in="now|then")
    lexical("active", "V", vform="finite", subcat_member="transitive", nonbase_surface="true")
    lexical("relative", "WH-PRONOUN", wh="true", lemma_in="that")
    lexical("modal", "MODAL", vform="finite")
    lexical("degree", "DEGREE")
    lexical("action", "V", vform="base", subcat_member="transitive",
            lemma_in="clear|pass|skirt|miss|avoid|round|bypass")
    lexical("side_preposition", "PREP", lemma_in="on")
    add("NP", *match.span("side"), "phrase", proof_rule="np_det_n")
    mark("SPEECH-STOP", *match.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
