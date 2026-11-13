"""Bounded source plans for interrupted turns and coordinated cleft dialogue.

These plans propose spans only. The existing lexical lattice, ranked phrase
proofs and declarative dialogue grammar decide whether each span is licensed.
"""
from __future__ import annotations

import re

from .dialogue import quotation_boundaries

NARRATIVE_TURN = "dialogue_structural_split_narrative_comparative"
CLEFT_TURN = "dialogue_structural_semicolon_cleft_conditional"


def _parts(components, *functions):
    return tuple(c for c in components if c.get("function") in functions)


def _specs():
    specs = []

    def add(category, a, b, kind="lexical", **features):
        specs.append((category, a, b, kind, features))

    def marks(category, a, b):
        add(category, a, b, "source-punctuation")

    def match_parts(match, offset, parts):
        for group, cat, kind, features in parts:
            a, b = match.span(group)
            add(cat, offset + a, offset + b, kind, **features)

    return specs, add, marks, match_parts


def narrative_comparative_plan(text, components):
    """A spoken discourse marker/address, a reporter, and a dashed aside.

    The aside is outside both quotations. The trailing comparative standard
    belongs to the spoken predication across an intervening time adjunct.
    """
    quotes = _parts(components, "direct_speech")
    tags = _parts(components, "reporting_clause")
    asides = _parts(components, "narratorial_parenthetical")
    turns = _parts(components, "split_direct_speech_turn")
    if (tuple(map(len, (quotes, tags, asides, turns))) != (2, 1, 1, 1)
            or _parts(components, "embedded_quotation")):
        return None
    q0, q1 = quotes
    tag, = tags
    aside, = asides
    turn, = turns
    if (q0.get("governor") != tag["id"]
            or q1.get("governor") != q0["id"]
            or q1.get("relation") != "resumption_of_split_speech"
            or tag.get("governor") != turn["id"]
            or aside.get("governor") != turn["id"]):
        return None
    b0, a1 = q0["end"], q1["start"]
    ta, tb = tag["start"], tag["end"]
    na, nb = aside["start"], aside["end"]
    if not (q0["start"] == 0 and q1["end"] == len(text)
            and 1 < b0 < ta < tb < na < nb < a1 < len(text) - 1):
        return None
    if [(q.start, q.end, q.side) for q in quotation_boundaries(text)] != [
        (0, 1, "open"), (b0 - 1, b0, "close"),
        (a1, a1 + 1, "open"), (len(text) - 1, len(text), "close"),
    ] or text[b0:ta].strip():
        return None
    left = re.fullmatch(r"\s*(--|—)\s*", text[tb:na])
    right = re.fullmatch(r"\s*(--|—)\s*", text[nb:a1])
    if not left or not right or left[1] != right[1]:
        return None
    opening = re.fullmatch(r"([A-Za-z]+)(,)\s+([^,]+)(,)", text[1:b0 - 1])
    narrative = re.fullmatch(
        r"([A-Za-z]+)\s+(.+?)\s+(as)\s+(.+)", text[na:nb], re.I,
    )
    resumption = re.fullmatch(
        r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
        r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
        r"([A-Za-z]+)\s+(than)\s+([A-Za-z]+)([.!?])",
        text[a1 + 1:-1], re.I,
    )
    if not opening or not narrative or not resumption:
        return None
    specs, add, mark, use = _specs()
    mark("OPEN-QUOTE", 0, 1)
    use(opening, 1, (
        (1, "ADV", "lexical", {"discourse_transition": "true"}),
        (2, "COMMA", "source-punctuation", {}),
        (3, "NP", "phrase", {}),
        (4, "COMMA", "source-punctuation", {}),
    ))
    mark("CLOSE-QUOTE", b0 - 1, b0)
    add("SPEECH-TAG", ta, tb, "phrase")
    mark("DASH", tb + left.start(1), tb + left.end(1))
    use(narrative, na, (
        (1, "COORD", "lexical", {"nominal_coordination": "true"}),
        (2, "CLAUSE", "phrase", {}),
        (3, "CONJ", "lexical", {"simultaneous": "true"}),
        (4, "CLAUSE", "phrase", {}),
    ))
    mark("DASH", nb + right.start(1), nb + right.end(1))
    mark("OPEN-QUOTE", a1, a1 + 1)
    use(resumption, a1 + 1, (
        (1, "NP", "phrase", {"pronominal": "true"}),
        (2, "MODAL", "lexical", {"vform": "finite"}),
        (3, "COPULA", "lexical", {"vform": "base"}),
        (4, "ADV", "lexical", {"comparative_modifier": "true"}),
        (5, "DEGREE", "lexical", {"comparative": "true"}),
        (6, "ADJ", "lexical", {}),
        (7, "ADV", "lexical", {"deictic_time": "true"}),
        (8, "PREP", "lexical", {"comparative": "true"}),
        (9, "ADJ", "lexical", {"usual_standard": "true"}),
        (10, "SPEECH-STOP", "source-punctuation", {}),
    ))
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return specs


def cleft_conditional_plan(text, components):
    """A zero-relativizer subject cleft coordinated with a conditional claim."""
    quotes = _parts(components, "direct_speech")
    coords = _parts(components, "coordinate_clause")
    if (len(quotes) != 1 or len(coords) != 1
            or _parts(components, "embedded_quotation", "reporting_clause")
            or (quotes[0]["start"], quotes[0]["end"]) != (0, len(text))
            or [(q.start, q.end, q.side) for q in quotation_boundaries(text)] != [
                (0, 1, "open"), (len(text) - 1, len(text), "close")
            ]):
        return None
    split = coords[0]["start"]
    semicolon = text.rfind(";", 1, split)
    if semicolon < 0 or text[semicolon + 1:split].strip():
        return None
    cleft = re.fullmatch(
        r"(it)(['’]s|\s+is)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
        r"([A-Za-z]+)\s+([^,;]+?)\s+(when)\s+([^,;]+)",
        text[1:semicolon], re.I,
    )
    coordinated = re.fullmatch(
        r"(and)\s+(till|until)\s+(then)\s+([A-Za-z]+)"
        r"(['’]ll|\s+[A-Za-z]+)\s+([A-Za-z]+)\s+([^,;]+)(,)\s+"
        r"(if)\s+([A-Za-z]+)\s+(have|has|had)\s+(to)\s+"
        r"([A-Za-z]+)\s+([^,;]+?)\s+(with\s+[^,;]+?)([.!?])",
        text[split:-1], re.I,
    )
    if not cleft or not coordinated:
        return None
    specs, add, mark, use = _specs()
    mark("OPEN-QUOTE", 0, 1)
    use(cleft, 1, (
        (1, "PRONOUN", "lexical", {"person": "3", "number": "singular", "gender": "neuter"}),
        (3, "PRONOUN", "lexical", {"case": "accusative"}),
        (4, "MODAL", "lexical", {"vform": "finite"}),
        (5, "V", "lexical", {"vform": "base", "subcat_member": "transitive"}),
        (6, "NP", "phrase", {}),
        (7, "CONJ", "lexical", {"temporal_incise": "true"}),
        (8, "CLAUSE", "phrase", {}),
    ))
    add("COPULA", 1 + cleft.end(2) - len(cleft[2].lstrip()),
        1 + cleft.end(2), vform="finite")
    mark("SEMICOLON", semicolon, semicolon + 1)
    use(coordinated, split, (
        (1, "COORD", "lexical", {"nominal_coordination": "true"}),
        (2, "PREP", "lexical", {}),
        (3, "ADV", "lexical", {"deictic_time": "true"}),
        (4, "NP", "phrase", {"pronominal": "true"}),
        (6, "V", "lexical", {"vform": "base", "subcat_member": "transitive"}),
        (7, "NP", "phrase", {}),
        (8, "COMMA", "source-punctuation", {}),
        (9, "CONJ", "lexical", {"complementizer": "conditional"}),
        (10, "NP", "phrase", {"pronominal": "true"}),
        (11, "HAVE", "lexical-alternatives", {"vform": "finite"}),
        (12, "TO", "lexical", {}),
        (13, "V", "lexical", {
            "vform": "base", "subcat_member": "transitive", "material_application": "true",
        }),
        (14, "NP", "phrase", {}),
        (15, "PP", "phrase", {}),
        (16, "SPEECH-STOP", "source-punctuation", {}),
    ))
    add("MODAL", split + coordinated.end(5) - len(coordinated[5].lstrip()),
        split + coordinated.end(5), vform="finite")
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return sorted(specs, key=lambda spec: spec[1])
