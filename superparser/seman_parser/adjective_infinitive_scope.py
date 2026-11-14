"""Keep a selected adjectival infinitive inside its finite predicate."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_adjective_infinitive_sentence"
WORD = r"[A-Za-z][A-Za-z’'\-]*"
SPAN = r"[^,;.!?()]+?"
NAME = rf"(?:(?:Mr|Mrs|Ms|Dr)\.\s+)?{WORD}"
COORDINATED = re.compile(
    rf"(?P<first>{NAME})\s+(?P<subject_and>and)\s+(?P<second>(?:her|his|their|our|my|your)\s+{WORD})\s+"
    rf"(?P<limiter>scarcely|hardly|barely)\s+(?P<prior>{SPAN})(?P<comma1>,)\s+"
    rf"(?P<except>except)\s+(?P<except_to>to)\s+(?P<exception>{SPAN})(?P<comma2>,)\s+"
    rf"(?P<and>and)\s+(?P<copula>{WORD})\s+(?P<stance>{WORD})\s+(?P<adj>{WORD})\s+"
    rf"(?P<to>to)\s+(?P<verb>{WORD})\s+(?P<object>{SPAN})\s+"
    rf"(?P<exclusive_to>to)\s+(?P<reflexive>ourselves|yourselves|themselves)",
    re.I,
)
PARATACTIC = re.compile(
    rf"(?P<subject>{WORD})\s+(?P<copula>{WORD})\s+(?P<adj>{WORD})\s+(?P<to>to)\s+"
    rf"(?P<verb>{WORD})\s+(?P<object>{SPAN})(?P<semi>;)"
    rf"\s+(?P<det>a)\s+(?P<num>{WORD})\s+(?P<noun>{WORD})\s+(?P<next_vp>{SPAN})(?P<comma>,)"
    rf"\s+(?P<and>and)\s+(?P<last>{SPAN})", re.I,
)


def plan_adjective_infinitive_scope(text, components):
    if not text.endswith(".") or "," not in text:
        return None
    match = COORDINATED.fullmatch(text[:-1])
    is_coordination = match is not None
    if match is None:
        match = PARATACTIC.fullmatch(text[:-1])
    if match is None:
        return None

    specs, add, punct, _ = _specs()

    def piece(group, category, kind="phrase", **features):
        add(category, *match.span(group), kind, **features)

    def lexical(group, category, **features):
        piece(group, category, "lexical-alternatives", **features)

    def mark(group, category="COMMA"):
        piece(group, category, "source-punctuation")

    lexical("copula", "COPULA", vform="finite")
    piece("adj", "ADJ", "adjective-infinitive-valency")
    lexical("to", "TO")
    lexical("verb", "V", vform="base", subcat_member="transitive")
    piece("object", "NP")
    lexical("and", "COORD", nominal_coordination="true")
    if is_coordination:
        piece("first", "NP", "proper-phrase")
        lexical("subject_and", "COORD", nominal_coordination="true")
        piece("second", "NP", proof_rule="np_poss")
        lexical("limiter", "ADV")
        piece("prior", "VP", "resumed-finite-phrase", vform="finite", voice="active",
              proof_rule="vp_transitive")
        mark("comma1")
        lexical("except", "EXCEPTIVE", exceptive_purpose="true")
        lexical("except_to", "TO")
        piece("exception", "VP-NP", voice="active", vform="base")
        mark("comma2")
        lexical("stance", "ADV")
        lexical("exclusive_to", "PREP")
        lexical("reflexive", "PRONOUN", number="plural", reflexive="true",
                person={"ourselves": "1", "yourselves": "2", "themselves": "3"}[match["reflexive"].casefold()])
    else:
        initial_end = match.start("semi")
        resumed_start = match.start("det")
        if not any(
            right.get("function") == "independent_clause"
            and right.get("relation") == "parataxis"
            and (right.get("start"), right.get("end")) == (resumed_start, len(text))
            and any(left.get("id") == right.get("governor")
                    and left.get("function") == "matrix_clause"
                    and (left.get("start"), left.get("end")) == (0, initial_end)
                    for left in components)
            for right in components
        ):
            return None
        piece("subject", "NP", "subject-phrase")
        mark("semi", "SEMICOLON")
        lexical("det", "DET", definiteness="indefinite")
        lexical("num", "NUM")
        lexical("noun", "N", number="plural")
        piece("next_vp", "VP", "resumed-finite-phrase", vform="finite", voice="active")
        mark("comma")
        piece("last", "CLAUSE", proof_rule="clause_np_vp")
    punct("SPEECH-STOP", len(text)-1, len(text))
    return sorted(specs, key=lambda spec: spec[1])
