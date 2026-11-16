"""Source-backed overt coordination with a fronted right-conjunct PP."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_coordinated_clauses_with_right_initial_pp"
_PRONOUN = r"I|you|he|she|it|we|they"
_SPAN = re.compile(
    rf"(?P<left>(?:{_PRONOUN}) +[^,;:.!?()]+)(?P<c1>,) +"
    rf"(?P<coord>and|but|or)(?P<c2>,) +"
    rf"(?P<pp>(?:in|on|at|with|without|under|over|by|after|before) +[^,;:.!?()]+)"
    rf"(?P<c3>,) +(?P<right>(?:{_PRONOUN}) +[^,;:.!?()]+)(?P<stop>[.!])",
    re.IGNORECASE,
)
# Standard separable transitive verb/particle frames. Lexical finite verb,
# literal particle and complete nominal object must each also be proven.
_PARTICLES = {
    "up": "take|pick|lift|hold|raise|put|bring",
    "down": "put|take|pull|bring|set|lay",
    "off": "turn|take|pull|switch|cut",
    "on": "turn|put|switch",
}
_PATTERNS = "|".join(_PARTICLES)
_PARTICLE = re.compile(
    rf"(?i)(?P<subject>{_PRONOUN}) +(?P<verb>[a-z]+) +"
    rf"(?P<particle>{_PATTERNS}) +(?P<object>(?:a|an|the|this|that|my|your|his|her|our|their) +.+)"
)


def _right_is_pp_candidate(text):
    # After/before followed immediately by a personal pronoun may introduce
    # a finite clause rather than a PP. Leave those to a different proof.
    return re.match(rf"(?i)^(?:after|before) +(?:{_PRONOUN})\b", text) is None


def source_spans(text):
    match = _SPAN.fullmatch(text)
    if match is None or not _right_is_pp_candidate(match["pp"]):
        return None
    return tuple(match.span(group) for group in ("left", "right", "pp"))


def plan_coordination_with_initial_pp(text, components):
    match = _SPAN.fullmatch(text)
    if match is None or not _right_is_pp_candidate(match["pp"]):
        return None
    if not all(
        any(c["id"] == name and c["governor"] == governor
            and (c["start"], c["end"]) == match.span(group)
            for c in components)
        for name, governor, group in (
            ("rc0", "s0", "left"), ("rc1", "rc0", "right"), ("rcp", "rc1", "pp"),
        )
    ):
        return None
    specs, add, mark, _ = _specs()
    # Before trying an ordinary rank-one clause, preserve an overt separable
    # particle. Otherwise "He took up the lamp" can make "He took" the NP.
    left = _PARTICLE.fullmatch(match["left"])
    if left is None:
        add("CLAUSE", *match.span("left"), "phrase", finite_statement_proof="true")
    else:
        add("NP", *left.span("subject"), "subject-phrase")
        add("V", *left.span("verb"), "lexical-alternatives", vform="finite",
            subcat_member="transitive", lemma_in=_PARTICLES[left["particle"].casefold()])
        add("PARTICLE", *left.span("particle"), "lexical")
        add("NP", *left.span("object"), "phrase", grounded_object_proof="true")
    mark("COMMA", *match.span("c1"))
    add("COORD", *match.span("coord"), "lexical", lemma_in=match["coord"].casefold())
    mark("COMMA", *match.span("c2"))
    add("PP", *match.span("pp"), "phrase", proof_rule="pp_prep_np")
    mark("COMMA", *match.span("c3"))
    add("CLAUSE", *match.span("right"), "phrase", finite_statement_proof="true")
    mark("SPEECH-STOP", *match.span("stop"))
    return specs
