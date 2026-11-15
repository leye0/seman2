"""Bounded span proposals for an adversative inverted object-control question."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_adversative_inverted_object_control"
WORD = r"[A-Za-z][A-Za-z'’\-]*"
NP = r"""[^,;.!?()"“”]+?"""
SUBJECT = r"I|you|he|she|it|we|they"
FRAME = re.compile(
    rf"(?P<left>{NP})(?P<c1>,)\s+(?P<yet>yet|but)\s+"
    rf"(?P<modal>can|could|may|might|should|would|will|must)\s+"
    rf"(?P<subject>{SUBJECT})\s+(?P<verb>{WORD})\s+"
    rf"(?P<one>one|someone|somebody|anyone|anybody)\s+"
    rf"(?P<so1>so)\s+(?:(?P<degree>{WORD})\s+)?(?P<attr1>{WORD})(?P<c2>,)\s+"
    rf"(?P<so2>so)\s+(?P<attr2>{WORD})\s+(?P<of1>of)\s+"
    rf"(?P<head>(?:every|any|no|the)\s+{WORD})\s+(?P<of2>of)\s+"
    rf"(?P<content>{NP})(?P<c3>,)\s+"
    rf"(?P<to>to)\s+(?P<inf>{WORD})(?P<qmark>\?)", re.I,
)


def inverted_control_spans(text):
    match = FRAME.fullmatch(text)
    if match is None:
        return None
    return (
        (match.start("modal"), match.end("qmark")),
        (match.start("one"), match.end("content")),
    )


def plan_inverted_object_control(text, components):
    match = FRAME.fullmatch(text)
    if match is None:
        return None
    question, nominal = inverted_control_spans(text)
    nodes = {c["id"]: c for c in components}
    for key, parent, func, span in (
        ("iq0", "s0", "interrogative_conjunct_candidate", question),
        ("iq1", "iq0", "supplemented_object_candidate", nominal),
    ):
        c = nodes.get(key, {})
        if (c.get("start"), c.get("end"), c.get("governor"), c.get("function")) != (
            *span, parent, func,
        ):
            return None

    specs, add, punct, _ = _specs()

    def piece(group, category, kind="lexical-alternatives", **features):
        add(category, *match.span(group), kind, **features)

    piece("left", "CLAUSE", "phrase", proof_rule="clause_np_vp", finite_statement_proof="true")
    for comma in ("c1", "c2", "c3"):
        punct("COMMA", *match.span(comma))
    piece("yet", "COORD", nominal_coordination="true", lemma_in=match["yet"].casefold())
    piece("modal", "MODAL", vform="finite", modal="true")
    piece("subject", "NP", "subject-phrase", pronominal="true")
    piece("verb", "V", vform="base", subcat_member="object_control")
    if match["one"].casefold() == "one":
        piece("one", "NUM", lemma_in="one")
    else:
        piece("one", "INDEF-PRONOUN", number="singular")
    for marker in ("so1", "so2"):
        piece(marker, "DEGREE", scalar_degree="true")
    if match["degree"]:
        piece("degree", "ADV")
    piece("attr1", "ADJ")
    piece("attr2", "ADJ", control_adjective_of="true")
    for group in ("of1", "of2"):
        piece(group, "PREP", nominal_complement="of")
    piece("head", "NP", "phrase", proof_rule="np_det_n")
    piece("content", "NP", "phrase", simple_nominal_proof="true")
    piece("to", "TO")
    piece("inf", "V", vform="base", subcat_member="intransitive")
    punct("QMARK", *match.span("qmark"))
    return sorted(specs, key=lambda row: row[1])
