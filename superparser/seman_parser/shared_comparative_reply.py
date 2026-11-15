"""Source spans for a shared subject followed by a comparative reply."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_shared_comparative_reply"
W = r"[A-Za-z][A-Za-z'’\-]*"
POSS = r"my|your|his|her|our|their"
PATTERN = re.compile(
    rf"(?P<title>Mr|Mrs|Ms|Dr)(?P<dot>\.)\s+(?P<name>{W})\s+(?P<consider>{W})\s+"
    rf"(?P<it>it)\s+(?P<need>necessary|wise|prudent|expedient|advisable|proper)\s+(?P<to>to)\s+"
    rf"(?P<prepare>{W})\s+(?P<either>either)\s+(?P<left>(?:{POSS})\s+{W})\s+"
    rf"(?P<or>or)\s+(?P<right>(?:{POSS})\s+{W})(?P<c1>,)\s+"
    rf"(?P<manner>by\s+degrees|with\s+care|with\s+caution)(?P<c2>,)\s+"
    rf"(?P<and>and)\s+(?P<said>{W})(?P<c3>,)\s+(?P<degree>sooner|earlier|later)\s+"
    rf"(?P<than>than)\s+(?P<expecter>he|she)\s+(?P<had>had)\s+(?P<expect>{W})\s+"
    rf"(?P<time>yesterday|earlier|before)(?P<stop>\.)", re.I,
)


def plan_comparative_reply(text, components):
    m = PATTERN.fullmatch(text)
    if (m is None or not m["name"][0].isupper()
            or not any(node["id"] == "s0" and node["start"] == 0 and node["end"] == len(text)
                       and node["function"] == "matrix_clause" for node in components)):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    lex("title", "TITLE", honorific="true")
    punct("ABBREVIATION-STOP", *m.span("dot"))
    lex("name", "PROPER-NOUN")
    lex("consider", "V", vform="finite", nonbase_surface="true",
        lemma_in="consider|judge|deem|find|think", subcat_member="complex_transitive")
    lex("it", "EXTRAPOSITION-IT", extraposition_it="true")
    lex("need", "ADJ")
    lex("to", "TO")
    lex("prepare", "V", vform="base", lemma_in="prepare|warn|alert|notify|inform",
        subcat_member="transitive")
    lex("either", "ADV", lemma_in="either")
    for group in ("left", "right"):
        add("NP", *m.span(group), "phrase", proof_rule="np_poss")
    lex("or", "COORD", lemma_in="or", nominal_coordination="true")
    add("PP", *m.span("manner"), "phrase", proof_rule="pp_prep_np")
    lex("and", "COORD", lemma_in="and", nominal_coordination="true")
    lex("said", "V", vform="finite", nonbase_surface="true",
        lemma_in="say|reply|answer|respond", subcat_member="clausal")
    lex("degree", "ADV", lemma_in="sooner|earlier|later|early|late")
    lex("than", "CONJ", infinitival_comparison_marker="true", lemma_in="than")
    add("NP", *m.span("expecter"), "subject-phrase", pronominal="true")
    lex("had", "HAVE", vform="finite")
    lex("expect", "V", vform="ed", lemma_in="expect|anticipate|predict", subcat_member="transitive")
    lex("time", "ADV")
    for group in ("c1", "c2", "c3"):
        punct("COMMA", *m.span(group))
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
