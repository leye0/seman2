"""Bound a comparative gap, a delayed wh-complement and a conjecture."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_comparative_content_coordination"
WORD = r"[A-Za-z][A-Za-z'’\-]*"
SUBJ = r"I|you|he|she|we|they"
PATTERN = re.compile(
    rf"(?P<knower>{SUBJ})\s+(?P<know>{WORD})\s+(?P<no>no)\s+(?P<more>more)\s+"
    rf"(?P<than>than)\s+(?P<standard>{SUBJ})\s+(?P<do>did|do|does)(?P<leftcomma>,)\s+"
    rf"(?P<where>where)\s+(?P<mover>{SUBJ})\s+(?P<be>am|is|are|was|were)\s+"
    rf"(?P<motion>{WORD})(?P<rightcomma>,)\s+(?P<but>but)\s+"
    rf"(?P<thinker>{SUBJ})\s+(?P<think>{WORD})\s+(?P<holder>{SUBJ})\s+"
    rf"(?P<have>have|has|had)\s+(?P<theme>{WORD}(?:\s+{WORD}){{0,5}}?)\s+"
    rf"(?P<form>{WORD})\s+(?P<out>out)\s+(?P<in>in)\s+"
    rf"(?P<poss>my|your|his|her|our|their)\s+(?P<mind>mind)(?P<stop>\.)",
    re.I,
)
# Each listed lexical pair has an independent constructional reading.
SHAPING = "shape|map|sketch|plan|work|figure|think"
MOTION = "go|head|travel|drive|walk|run|fly|sail|ride|move|wander"


def comparative_content_spans(text):
    if m := PATTERN.fullmatch(text):
        return (
            (0, m.start("rightcomma")), (m.start("than"), m.end("do")),
            (m.start("where"), m.end("motion")), (m.start("thinker"), m.start("stop")),
        )
    return None


def plan_comparative_content(text, components):
    m = PATTERN.fullmatch(text)
    if m is None:
        return None
    nodes = {node["id"]: node for node in components}
    for node, gov, span in zip(
        ("kc0", "kc1", "kc2", "kc3"), ("s0", "kc0", "kc0", "s0"),
        comparative_content_spans(text),
    ):
        c = nodes.get(node, {})
        if (c.get("governor"), c.get("start"), c.get("end")) != (gov, *span):
            return None

    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    for group in ("knower", "standard", "mover", "thinker", "holder"):
        add("NP", *m.span(group), "subject-phrase", pronominal="true")
    for group, lemmas in (("know", "know|learn|understand"),
                          ("think", "think|believe|suppose|imagine")):
        lex(group, "V", lemma_in=lemmas, subcat_member="clausal",
            vform="finite", nonbase_surface="true")
    lex("no", "ADV", lemma_in="no")
    lex("more", "DEGREE", comparative="true", lemma_in="more")
    lex("than", "CONJ", infinitival_comparison_marker="true", lemma_in="than")
    # Raw auxiliary Do lacks person/number on some lexical candidates.
    # Read overt present agreement instead of inheriting it from a rule.
    if m["do"].casefold() != "did" and (
        (m["do"].casefold() == "does") != (m["standard"].casefold() in {"he", "she"})
    ):
        return None
    lex("do", "AUX", vform="finite")
    lex("where", "WH-NOM", wh_adverbial="true", lemma_in="where")
    lex("be", "COPULA", vform="finite", lemma_in="be")
    lex("motion", "V", vform="ing", lemma_in=MOTION, subcat_member="intransitive")
    lex("but", "COORD", lemma_in="but")
    if m["have"].casefold() != "had" and (
        (m["have"].casefold() == "has") != (m["holder"].casefold() in {"he", "she"})
    ):
        return None
    lex("have", "V", vform="finite", lemma_in="have", subcat_member="transitive")
    add("NP", *m.span("theme"), "phrase", proof_rule="np_det_n")
    lex("form", "V", vform="ed", lemma_in=SHAPING, subcat_member="transitive")
    lex("out", "PARTICLE", lemma_in="out")
    lex("in", "PREP", lemma_in="in")
    lex("poss", "POSS")
    lex("mind", "N", lemma_in="mind", number="singular")
    for group in ("leftcomma", "rightcomma"):
        punct("COMMA", *m.span(group))
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
