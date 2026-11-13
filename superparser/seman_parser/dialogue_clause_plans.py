"""Bounded source plans for complex dialogue and nested quotations.

These plans propose spans only. The existing lexical lattice, ranked phrase
proofs and declarative dialogue grammar decide whether each span is licensed.
"""
from __future__ import annotations

import re

from .dialogue import quotation_boundaries

PARENTHETICAL_MODAL = "structural_source_modal_coordination_with_parenthetical"
NARRATIVE_TURN = "dialogue_structural_split_narrative_comparative"
CLEFT_TURN = "dialogue_structural_semicolon_cleft_conditional"
NESTED_TEMPORAL_TURN = "dialogue_structural_nested_temporal_comparative"


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


def nested_temporal_comparative_plan(text, components):
    """Propose a direct-address when-clause with a supplementary relative.

    All commas and both quote pairs are printed. In particular the comma
    following the comparative does not end the initial when-clause.
    """
    quotes = _parts(components, "direct_speech")
    embedded = _parts(components, "embedded_quotation")
    n = len(text)
    if (len(quotes) != 1 or len(embedded) != 1
            or _parts(components, "reporting_clause", "split_direct_speech_turn",
                      "narratorial_parenthetical")
            or (quotes[0]["start"], quotes[0]["end"]) != (0, n)
            or embedded[0].get("governor") != quotes[0]["id"]
            or (embedded[0]["start"], embedded[0]["end"]) != (1, n - 1)
            or [(q.start, q.end, q.side) for q in quotation_boundaries(text)] != [
                (0, 1, "open"), (1, 2, "open"), (n - 2, n - 1, "close"),
                (n - 1, n, "close"),
            ]):
        return None
    # A source template proposes spans, not analyses. The lexical and
    # syntactic proofs below can reject any proposed split.
    match = re.fullmatch(
        r"(?P<when>when)\s+(?P<anchor>[A-Za-z]+)(?P<c1>,)\s+"
        r"(?P<relative>who)\s+(?P<relverb>[A-Za-z]+)\s+(?P<relobj>[A-Za-z]+)\s+"
        r"(?P<degree>so)\s+(?P<diff>[A-Za-z]+)\s+(?P<cmp>[A-Za-z]+)\s+"
        r"(?P<than>than)\s+(?P<standard>[A-Za-z]+)\s+"
        r"(?:(?P<pretime>ever)\s+(?P<latehave>[A-Za-z]+)|"
        r"(?P<earlyhave>[A-Za-z]+)\s+(?P<posttime>ever))\s+"
        r"(?P<participle>[A-Za-z]+)"
        r"(?P<c2>,)\s+(?P<focus>even)\s+(?P<innerwhen>when)\s+"
        r"(?P<concessive>[^,;.!?]+)(?P<c3>,)\s+"
        r"(?P<timeverb>[A-Za-z]+)\s+(?P<timeobj>[^,;.!?]+)(?P<c4>,)\s+"
        r"(?P<matrix>[^,;.!?]+)(?P<stop>\.)",
        text[2:-2], re.I,
    )
    if not match:
        return None
    specs, _, mark, use = _specs()
    mark("OPEN-QUOTE", 0, 1)
    mark("OPEN-QUOTE", 1, 2)
    use(match, 2, (
        ("when", "CONJ", "lexical", {"temporal_incise": "true"}),
        ("anchor", "NP", "phrase", {"pronominal": "true", "person": "2"}),
        ("c1", "COMMA", "source-punctuation", {}),
        ("relative", "WH-PRONOUN", "lexical", {"supplementary_subject_marker": "true"}),
        ("relverb", "V", "lexical-alternatives", {"vform": "finite", "subcat_member": "transitive"}),
        ("relobj", "PRONOUN", "lexical", {"case": "accusative"}),
        ("degree", "DEGREE", "lexical", {"scalar_degree": "true"}),
        ("diff", "ADV", "lexical", {"comparative_modifier": "true"}),
        ("cmp", "ADV", "lexical", {"manner_comparative": "true"}),
        ("than", "PREP", "lexical", {"comparative": "true"}),
        ("standard", "NP", "phrase", {"pronominal": "true"}),
        ("pretime" if match["pretime"] else "posttime",
         "ADV", "lexical", {"indefinite_time": "true"}),
        ("latehave" if match["latehave"] else "earlyhave",
         "HAVE", "lexical-alternatives", {"vform": "finite"}),
        ("participle", "V", "lexical", {"vform": "ed", "subcat_member": "transitive"}),
        ("c2", "COMMA", "source-punctuation", {}),
        ("focus", "ADV", "lexical", {"scalar_focus": "true"}),
        ("innerwhen", "CONJ", "lexical", {"temporal_incise": "true"}),
        ("concessive", "CLAUSE", "phrase", {}),
        ("c3", "COMMA", "source-punctuation", {}),
        ("timeverb", "V", "lexical-alternatives", {"vform": "finite", "subcat_member": "transitive"}),
        ("timeobj", "NP", "phrase", {}),
        ("c4", "COMMA", "source-punctuation", {}),
        ("matrix", "CLAUSE", "phrase", {}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    mark("CLOSE-QUOTE", n - 2, n - 1)
    mark("CLOSE-QUOTE", n - 1, n)
    return sorted(specs, key=lambda spec: spec[1])


def modal_parenthetical_plan(text, components):
    """A cognition comment between coordinated bare predicates of one modal."""
    asides = _parts(components, "parenthetical_candidate")
    if len(asides) != 1 or _parts(components, "direct_speech", "embedded_quotation"):
        return None
    a, b = asides[0]["start"], asides[0]["end"]
    if not (0 < a < b < len(text) and text[a] == "(" and text[b - 1] == ")"):
        return None
    left = re.fullmatch(r"([A-Za-z]+)\s+([A-Za-z]+)\s+([^(),;.!?]+?)\s*", text[:a])
    aside = re.fullmatch(r"([A-Za-z]+)\s+([A-Za-z]+)\s+(with\s+[^(),;.!?]+)", text[a + 1:b - 1], re.I)
    right = re.fullmatch(
        r"\s*(and)\s+([^(),;.!?]+?)\s+(when)\s+([^(),;.!?]+?)(\.)",
        text[b:], re.I,
    )
    if not (left and aside and right):
        return None
    specs, add, mark, use = _specs()
    use(left, 0, (
        (1, "NP", "phrase", {"pronominal": "true"}),
        (2, "MODAL", "lexical", {"vform": "finite"}),
        (3, "VP-NP", "phrase", {}),
    ))
    mark("OPEN-PAREN", a, a + 1)
    use(aside, a + 1, (
        (1, "NP", "phrase", {"pronominal": "true"}),
        (2, "V", "lexical-alternatives", {"vform": "finite", "subcat_member": "clausal"}),
        (3, "PP", "phrase", {}),
    ))
    mark("CLOSE-PAREN", b - 1, b)
    use(right, b, (
        (1, "COORD", "lexical", {"nominal_coordination": "true"}),
        (2, "VP-NP", "phrase", {}),
        (3, "CONJ", "lexical", {"temporal_incise": "true"}),
    ))
    start, end = (b + x for x in right.span(4))
    # A time-denoting final PP is a distinct adjunct of the embedded event.
    # Do not let the ordinary phrase parser prefer a false ditransitive.
    pp = re.search(
        r"\s+((?:in|at|on)\s+(?:the\s+)?"
        r"(?:morning|afternoon|evening|night|dawn|dusk|noon|midnight))$",
        text[start:end], re.I,
    )
    if pp:
        add("CLAUSE", start, start + pp.start(), "phrase")
        add("PP", start + pp.start(1), end, "phrase")
    else:
        add("CLAUSE", start, end, "phrase")
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs
