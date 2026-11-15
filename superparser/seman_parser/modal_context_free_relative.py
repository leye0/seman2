"""Keep distinct social settings on a modal copula and a fused relative."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_modal_context_free_relative"
W = r"[A-Za-z][A-Za-z'’\-]*"
POSS = r"my|your|his|her|our|their"
SUBJ = r"I|you|he|she|we|they"
KIN = r"mother|father|uncle|aunt|sister|brother|parents|daughter|son|cousin|wife|husband"
PATTERN = re.compile(
    rf"(?P<but>but)(?P<comma>,)\s+(?P<stance>perhaps|possibly|maybe)\s+(?P<subject>{SUBJ})\s+"
    rf"(?P<modal>could|can|might|would)\s+(?P<not>not)\s+(?P<in>in)\s+"
    rf"(?P<presence>(?:{POSS})\s+(?:{KIN})['’]s\s+presence)\s+(?P<base>be)\s+"
    rf"(?P<what>what)\s+(?P<inner>{SUBJ})\s+(?P<was>am|is|are|was|were)\s+"
    rf"(?P<before>before)\s+(?P<poss>{POSS})\s+(?P<relative1>{KIN})\s+"
    rf"(?P<and>and)\s+(?P<relative2>{KIN})(?P<stop>\.)", re.I,
)


def plan_modal_context(text, components):
    m = PATTERN.fullmatch(text)
    if (m is None or not any(c["id"] == "s0" and c["start"] == 0 and c["end"] == len(text)
                            and c["function"] == "matrix_clause" for c in components)):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    lex("but", "COORD", lemma_in="but")
    punct("COMMA", *m.span("comma"))
    lex("stance", "ADV")
    for group in ("subject", "inner"):
        add("NP", *m.span(group), "subject-phrase", pronominal="true")
    lex("modal", "MODAL", vform="finite")
    lex("not", "NEG", negation="true")
    lex("in", "PREP", lemma_in="in")
    add("NP", *m.span("presence"), "phrase", proof_rule="np_genitive")
    lex("base", "COPULA", lemma_in="be", vform="base")
    lex("what", "WH-NOM", lemma_in="what", free_relative="true", wh="true")
    lex("was", "COPULA", lemma_in="be", vform="finite")
    lex("before", "PREP", lemma_in="before")
    lex("poss", "POSS")
    lex("relative1", "N")
    lex("and", "COORD", lemma_in="and", nominal_coordination="true")
    lex("relative2", "N")
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
