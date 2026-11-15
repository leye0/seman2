"""Surface boundaries for a fronted degree concession and its matrix host."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_degree_concessive_attitude"
WORD = r"[A-Za-z][A-Za-z’'\-]*"
PRON = "I|you|he|she|it|we|they"
PATTERN = re.compile(
    rf"(?P<however>however)\s+(?:(?P<much>much)\s+)?(?P<quality>{WORD})\s+"
    rf"(?P<front_subject>{PRON})\s+(?P<modal>may|might|can|could)\s+(?P<base>be)(?P<comma>,)\s+"
    rf"(?P<matrix_subject>{PRON})\s+(?P<copula>am|is|are|was|were)\s+(?P<attitude>{WORD})\s+"
    rf"(?P<that>that)\s+(?P<content_subject>{PRON})\s+(?P<have>have|has|had)\s+(?P<no>no)\s+"
    rf"(?P<entitlement>{WORD})\s+(?P<to>to)\s+(?P<action>{WORD})\s+(?P<theme>{WORD})\s+"
    rf"(?P<with>with)\s+(?P<standard>{WORD}(?:\s+{WORD}){{0,9}})(?P<stop>\.)",
    re.I,
)
# Scoped lexical selections, not global additions or replacements.
MUCH_QUALITIES = "astonished|alarmed|amazed|annoyed|concerned|distressed|disturbed|excited|impressed|puzzled|surprised|troubled|worried"
CONTENT_ADJECTIVES = "aware|certain|conscious|convinced|sure|sensible|mindful"
ENTITLEMENTS = "right|authority|permission|licence|license|entitlement"
WITH_NOMINALS = "agreement|compliance|cooperation|contact|disagreement|reconciliation|sympathy"


def degree_concession_spans(text):
    if m := PATTERN.fullmatch(text):
        return (0, m.start("comma")), m.span("attitude"), (m.start("that"), m.start("stop"))


def degree_concession_plan(text, components):
    m = PATTERN.fullmatch(text)
    if m is None:
        return None
    if not all(any(c["id"] == node and c["governor"] == governor
                   and (c["start"], c["end"]) == span for c in components)
               for (node, governor), span in zip((("gc0", "s0"), ("gc2", "s0"), ("gc1", "gc2")),
                                                degree_concession_spans(text))):
        return None
    specs, add, punct, _ = _specs()

    def lex(group, category, **features):
        add(category, *m.span(group), "lexical-alternatives", **features)

    lex("however", "ADV", lemma_in="however")
    if m["much"]:
        lex("much", "ADV", lemma_in="much")
        lex("quality", "ADJ", lemma_in=MUCH_QUALITIES)
    else:
        lex("quality", "ADJ")
    for group in ("front_subject", "matrix_subject", "content_subject"):
        add("NP", *m.span(group), "subject-phrase", pronominal="true")
    lex("modal", "MODAL", vform="finite")
    lex("base", "COPULA", vform="base", lemma_in="be")
    lex("copula", "COPULA", vform="finite", lemma_in="be")
    lex("attitude", "ADJ", lemma_in=CONTENT_ADJECTIVES)
    lex("that", "COMP-THAT")
    lex("have", "V", vform="finite", subcat_member="transitive", lemma_in="have")
    lex("no", "DET", negation="true", definiteness="negative", number="singular")
    lex("entitlement", "N", number="singular", lemma_in=ENTITLEMENTS)
    lex("to", "TO")
    lex("action", "V", vform="base", subcat_member="transitive")
    lex("theme", "N", number="singular", lemma_in=WITH_NOMINALS)
    lex("with", "PREP", lemma_in="with")
    add("NP", *m.span("standard"), "phrase")
    punct("COMMA", *m.span("comma"))
    punct("SPEECH-STOP", *m.span("stop"))
    return sorted(specs, key=lambda spec: spec[1])
