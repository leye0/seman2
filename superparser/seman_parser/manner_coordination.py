"""Source proposals for an interposed manner PP before a selected complement."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

WORD = r"[A-Za-z][A-Za-z’'\-]*"
SPAN = r"[^,;.!?()]+?"
# A period within a title belongs to its name, not to the utterance boundary.
NAME = rf"(?:[A-Z][a-z]*\.\s+)?[A-Z][\w’'-]*(?:\s+[A-Z][\w’'-]*)?"
QUESTION = re.compile(
    rf"(?P<subject>{WORD})\s+(?P<first>{WORD})\s+(?P<how1>how)\s+(?P<far>far)\s+"
    rf"(?P<locatee>{SPAN})\s+(?P<copula>{WORD})\s+(?P<from>from\s+{SPAN})(?P<semi>;)"
    rf"\s+(?P<and>and)(?P<open>,)\s+(?P<after>after)\s+(?P<activity>{WORD}ing\s+{SPAN})(?P<close>,)"
    rf"\s+(?P<second>{WORD})\s+(?P<manner>in\s+{SPAN}\s+(?:manner|voice|tone|fashion))\s+(?P<how2>how)\s+(?P<long>long)\s+"
    rf"(?P<durative>{NAME}|{WORD})\s+(?P<have>had|has|have)\s+(?P<been>been)\s+"
    rf"(?P<ing>{WORD}ing)\s+(?P<location>{WORD})",
    re.I,
)
NOMINAL = re.compile(
    rf"(?P<subject>{WORD})\s+(?P<first>{WORD})\s+(?P<manner>with\s+(?:{SPAN}\s+)?(?:attention|surprise|interest|delight|care|curiosity|patience|astonishment|pleasure|enthusiasm))\s+"
    rf"(?P<theme>(?:the|a|an|his|her|their|our)\s+{SPAN})\s+"
    rf"(?P<and>and)\s+(?P<second>{WORD})\s+(?P<at>at)\s+"
    rf"(?P<det>the)\s+(?P<names>{WORD})\s+(?P<of>of)\s+"
    rf"(?P<name1>{NAME})\s+(?P<name_and>and)\s+(?P<name2>{NAME})(?P<comma>,)\s+"
    rf"(?P<but>but)\s+(?P<without>without)\s+(?P<antecedent>{SPAN})\s+(?P<that>that)\s+"
    rf"(?:(?P<title>Mr|Mrs|Ms|Dr|M)(?P<abbrev>\.)\s+)?"
    rf"(?P<rel_subject>{WORD})\s+(?P<rel_vp>had\s+{WORD})",
    re.I,
)


def semicolon_coordination(components, initial_end, resumed_start, text_end):
    return any(
        right.get("function") == "coordinate_clause"
        and right.get("relation") == "coordination"
        and (right.get("start"), right.get("end")) == (resumed_start, text_end)
        and any(
            left.get("id") == right.get("governor")
            and left.get("function") == "matrix_clause"
            and (left.get("start"), left.get("end")) == (0, initial_end)
            for left in components
        )
        for right in components
    )


def manner_coordination_plan(text, components):
    if not text.endswith(".") or "," not in text:
        return None
    m = QUESTION.fullmatch(text[:-1])
    interrogative = m is not None
    if m is None:
        m = NOMINAL.fullmatch(text[:-1])
    if m is None:
        return None
    specs, add, mark, _ = _specs()

    def piece(group, category, kind="phrase", **features):
        add(category, *m.span(group), kind, **features)

    def lex(group, category, **features):
        piece(group, category, "lexical-alternatives", **features)

    def verb(group, frame, **features):
        lex(group, "V", vform="finite", subcat_member=frame,
            nonbase_surface="true", **features)

    piece("subject", "NP", "subject-phrase")
    piece("manner", "PP", proof_rule="pp_prep_np")
    lex("and", "COORD", nominal_coordination="true")
    if interrogative:
        if not semicolon_coordination(components, m.start("semi"), m.start("and"), len(text)):
            return None
        for field in ("open", "close"):
            piece(field, "COMMA", "source-punctuation")
        piece("semi", "SEMICOLON", "source-punctuation")
        for field in ("first", "second"):
            verb(field, "whether_clausal")
        for field in ("how1", "how2"):
            lex(field, "WH-NOM", wh_adverbial="true")
        lex("far", "ADV")
        lex("long", "ADV")
        piece("locatee", "NP")
        lex("copula", "COPULA", vform="finite")
        piece("from", "PP", proof_rule="pp_prep_np")
        lex("after", "PREP")
        piece("activity", "TRANSITIVE-PARTICIPIAL")
        piece("durative", "NP")
        lex("have", "HAVE", vform="finite")
        lex("been", "AUX-BE", vform="ed")
        lex("ing", "V", vform="ing", subcat_member="intransitive")
        lex("location", "ADV")
    else:
        verb("first", "transitive")
        piece("theme", "NP")
        verb("second", "prepositional")
        lex("at", "PREP")
        lex("det", "DET", number="plural")
        lex("names", "N", number="plural")
        lex("of", "PREP", nominal_complement="of")
        for field in ("name1", "name2"):
            piece(field, "NP", "proper-phrase")
        lex("name_and", "COORD", nominal_coordination="true")
        piece("comma", "COMMA", "source-punctuation")
        lex("but", "COORD", nominal_coordination="true")
        lex("without", "PREP")
        piece("antecedent", "NP", proof_rule="np_det_n")
        lex("that", "COMP-THAT")
        if m["title"]:
            if m["title"] == "M":
                piece("title", "TITLE", "source-title")
            else:
                lex("title", "TITLE", honorific="true")
            piece("abbrev", "ABBREVIATION-STOP", "source-punctuation")
        piece("rel_subject", "NP", "proper-phrase" if m["title"] else "subject-phrase")
        piece("rel_vp", "VP-GAP", gap="object", proof_rule="vp_gap_perfect_transitive")
    mark("SPEECH-STOP", len(text)-1, len(text))
    return sorted(specs, key=lambda item: item[1])
