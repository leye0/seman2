"""Source spans for an alternative introduced with a parenthetic cognition report."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _parts, _specs

ROOT = "structural_parenthetical_alternative_sentence"
WORD = r"[A-Za-z][A-Za-z'’\-]*"
PHRASE = r"[^(),;.!?]+?"
PREFIX = re.compile(r"(or)\s*", re.I)
ASIDE = re.compile(
    rf"(?P<so>so)\s+(?P<cognizer>{PHRASE})\s+(?P<cognition>{WORD})", re.I,
)
HOST = re.compile(
    rf"\s*(?P<subject>{PHRASE})\s+(?P<modal>might|may|could|would|can|will)\s+"
    rf"(?P<time>meanwhile|then|soon|later)\s+(?P<event>{WORD})\s+(?P<to>to)\s+"
    rf"(?P<first>{PHRASE})\s+(?P<and>and)\s+(?P<second>{PHRASE})(?P<stop>\.)", re.I,
)
TERMINATION = re.compile(
    rf"(?P<put>put)\s+(?P<end>an\s+end)\s+(?P<target_to>to)\s+"
    rf"(?P<target>{PHRASE})\s+(?P<duration>forever|permanently)", re.I,
)


def plan_parenthetical_alternative(text, components):
    """Propose exact spans only after preanalysis proves paired punctuation."""
    asides = _parts(components, "parenthetical_candidate")
    matrix = _parts(components, "matrix_clause")
    if (len(asides) != 1 or len(matrix) != 1
            or _parts(components, "direct_speech", "embedded_quotation")):
        return None
    mark, = asides
    a, b = mark["start"], mark["end"]
    if (mark["governor"] != matrix[0]["id"]
            or not 0 < a < b < len(text) or text[a] != "(" or text[b - 1] != ")"):
        return None
    prefix = PREFIX.fullmatch(text, 0, a)
    aside = ASIDE.fullmatch(text, a + 1, b - 1)
    host = HOST.fullmatch(text, b)
    if not (prefix and aside and host):
        return None
    specs, add, punct, _ = _specs()

    def piece(match, group, cat, kind="lexical-alternatives", **features):
        add(cat, *match.span(group), kind, **features)

    piece(prefix, 1, "COORD", nominal_coordination="true")
    punct("OPEN-PAREN", a, a + 1)
    piece(aside, "so", "ADV", lemma_in="so")
    piece(aside, "cognizer", "NP", "subject-phrase")
    piece(aside, "cognition", "V", vform="finite", subcat_member="clausal",
          nonbase_surface="true", alternative_frame="cognition")
    punct("CLOSE-PAREN", b - 1, b)
    piece(host, "subject", "NP", "subject-phrase", proof_rule="np_det_n")
    piece(host, "modal", "MODAL", vform="finite", modal="true")
    piece(host, "time", "ADV")
    piece(host, "event", "V", vform="base", subcat_member="intransitive",
          alternative_frame="occurrence")
    piece(host, "to", "TO")
    piece(host, "first", "VP-NP", "phrase", proof_rule="vp_bare_trans")
    piece(host, "and", "COORD", nominal_coordination="true")
    ending = TERMINATION.fullmatch(text, *host.span("second"))
    if ending:
        piece(ending, "put", "V", vform="base", subcat_member="prep_ditransitive",
              lemma_in="put")
        piece(ending, "end", "NP", "phrase", proof_rule="np_det_n")
        piece(ending, "target_to", "PREP", lemma_in="to")
        piece(ending, "target", "NP", "phrase")
        piece(ending, "duration", "ADV")
    else:
        piece(host, "second", "VP-NP", "phrase", proof_rule="vp_bare_trans")
    piece(host, "stop", "SPEECH-STOP", "source-punctuation")
    return specs
