"""Source-span plans for constructions missed by unconstrained rank one.

Each admitted span is proved against the original lexical lattice or a
ranked constituent. No source rewriting or corpus identifiers are used.
"""
from __future__ import annotations

import re

from .additional_spoken_acts import _single_spoken_span
from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _matrix, _v

MINIMIZER = "structural_negative_emphatic_minimizer"
MINOR_REPORT = "dialogue_structural_reported_minor_predication"
FREQUENCY_REPLY = "dialogue_structural_affirmative_frequency_reply"
APOSTROPHE = "structural_exclamative_apostrophe"
MANNER_QUESTION = "dialogue_structural_why_question_with_degree_manner"
MANNER_STATEMENT = "dialogue_structural_finite_degree_manner"
MODAL_PASSIVE = "dialogue_structural_simple_modal_passive_question"

WORD = r"[A-Za-z]+(?:-[A-Za-z]+)?"
PRON = r"I|[Ww]e|[Yy]ou|[Tt]hey|[Hh]e|[Ss]he|[Ii]t"
REPORT = r"said|cried|exclaimed|shouted|asked|replied|answered"
REPORT_LEMMAS = "say|cry|exclaim|shout|ask|reply|answer"


def _lex(group, cat, **features):
    return group, cat, "lexical", {"attested_reading": "true", **features}


def _alts(group, cat, **features):
    return group, cat, "lexical-alternatives", {"attested_reading": "true", **features}


def _scoped(group, cat, **features):
    return group, cat, "scoped-lexical", {"attested_reading": "true", **features}


def _phrase(group, cat="NP", **features):
    return group, cat, "phrase", features


def _subject(group):
    return group, "NP", "subject-phrase", {}


def _punct(group, cat):
    return group, cat, "source-punctuation", {}


_MINIMIZER = re.compile(
    rf"(?P<subject>.+?) +(?P<neg>never) +(?P<minimum>so +much +as) +"
    r"(?P<verb>[A-Za-z]+ed)(?P<stop>[.!])"
)


def plan_minimizer(text, parts):
    m = _MINIMIZER.fullmatch(text)
    if m is None or not _matrix(text, parts):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        _subject("subject"), _lex("neg", "DEGREE", negation="true"),
        _scoped("minimum", "DEGREE", emphatic_minimum="true"),
        _alts("verb", "V", **_v("finite", "intransitive", nonbase_surface="true")),
        _punct("stop", "SPEECH-STOP"),
    ))
    return specs


_SINGLE_ADJECTIVE = re.compile(rf"(?P<state>{WORD})")
_POLITE_REPLY = re.compile(r"(?P<answer>No|Yes), +(?P<address>sir|madam)")
_POSTPOSED_REPORT = re.compile(rf"(?P<verb>{REPORT}) +(?P<speaker>[^,;]+)")
_DEPICTIVE_REPORT = re.compile(
    rf"(?P<verb>{REPORT}) +(?P<speaker>[^,;]+)(?P<comma>,) +"
    rf"(?P<doing>{WORD}ing) +(?P<theme>[^,;]+?) +(?P<with>with) +"
    r"(?P<instrument>(?:my|his|her|their|our|your) +(?:finger|hand|palm|pen|brush|knife|chisel|stick))"
)


def plan_minor_report(text, parts):
    quote = _single_spoken_span(text, parts, reported=True)
    if quote is None:
        return None
    stop, tag = quote
    raw_reply = text[1:stop]
    reply = _POLITE_REPLY.fullmatch(raw_reply)
    adjective = _SINGLE_ADJECTIVE.fullmatch(raw_reply)
    if (not (reply or adjective) or text[stop] not in "!,"
            or not tag or tag["end"] != len(text) - 1):
        return None
    # Single-word answers like "No" are not accidentally read as adjectives.
    if not reply and raw_reply.casefold() in {"yes", "no", "aye", "oh", "ah"}:
        return None
    base = tag["start"]
    report_text = text[base:tag["end"]]
    depictive = _DEPICTIVE_REPORT.fullmatch(report_text)
    report = depictive or _POSTPOSED_REPORT.fullmatch(report_text)
    if not report:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    if reply:
        part(reply, 1, (
            _scoped("answer", "RESPONSE", polarity=(
                "negative" if reply["answer"] == "No" else "positive")),
        ))
        mark("COMMA", reply.end("answer") + 1, reply.end("answer") + 2)
        part(reply, 1, (_scoped("address", "VOCATIVE", honorific="true"),))
    else:
        part(adjective, 1, (_lex("state", "ADJ"),))
    mark("SPEECH-STOP" if text[stop] == "!" else "COMMA", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    part(report, base, (
        _alts("verb", "V", vform="finite", lemma_in=REPORT_LEMMAS),
        _subject("speaker"),
    ))
    if depictive:
        part(depictive, base, (
            _punct("comma", "COMMA"),
            _alts("doing", "V", **_v("ing", "transitive")),
            _phrase("theme", proof_rule="np_det_n"),
            _lex("with", "PREP", lemma_in="with"),
            _phrase("instrument", proof_rule="np_poss"),
        ))
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs


_FREQUENCY = re.compile(
    r"(?P<yes>Yes), +(?P<approx>almost|nearly) +(?P<every>every) +"
    r"(?P<period>day|night|week|month|year|hour|morning|evening)"
)


def plan_frequency_reply(text, parts):
    evidence = _single_spoken_span(text, parts)
    if evidence is None:
        return None
    stop, _ = evidence
    m = _FREQUENCY.fullmatch(text[1:stop])
    if m is None or text[stop] not in ".!":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (_scoped("yes", "RESPONSE", polarity="positive"),))
    mark("COMMA", m.end("yes") + 1, m.end("yes") + 2)
    part(m, 1, (
        _scoped("approx", "DEGREE", approximative="true"),
        _lex("every", "DET"), _lex("period", "N", number="singular"),
    ))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


_APOSTROPHE = re.compile(rf"(?P<o>O) +(?P<quality>{WORD}) +(?P<address>{WORD})(?P<stop>!)")


def plan_apostrophe(text, parts):
    m = _APOSTROPHE.fullmatch(text)
    if m is None or not _matrix(text, parts):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        _scoped("o", "INTERJECTION", apostrophe="true"),
        _lex("quality", "ADJ"),
        _phrase("address", proof_rule="np_bare"),
        _punct("stop", "SPEECH-STOP"),
    ))
    return specs


_DEGREE_QUERY = re.compile(
    rf"(?P<why>Why) +(?P<aux>do|does|did) +(?P<subject>{PRON}) +"
    rf"(?P<verb>{WORD}) +(?P<object>me|him|her|us|them|you|it) +"
    rf"(?P<degree>so|too|very|quite) +(?P<manner>{WORD})"
)
_DEGREE_STATEMENT = re.compile(
    rf"(?P<subject>I|[Ww]e|[Yy]ou|[Tt]hey) +(?P<verb>{WORD}) +"
    rf"(?P<degree>uncommonly|remarkably|unusually|exceptionally|incredibly) +"
    rf"(?P<manner>{WORD})"
)


def plan_manner_question(text, parts):
    evidence = _single_spoken_span(text, parts)
    if evidence is None:
        return None
    stop, _ = evidence
    m = _DEGREE_QUERY.fullmatch(text[1:stop])
    if m is None or text[stop] != "?":
        return None
    third = m["subject"].casefold() in {"he", "she", "it"}
    if (m["aux"] == "does" and not third) or (m["aux"] == "do" and third):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        _lex("why", "WH-NOM", wh="true"), _lex("aux", "AUX", vform="finite"),
        _subject("subject"), _alts("verb", "V", **_v("base", "transitive")),
        _phrase("object", proof_rule="np_indef_pron"),
        _lex("degree", "DEGREE"), _lex("manner", "ADV"),
    ))
    mark("QMARK", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


def plan_manner_statement(text, parts):
    evidence = _single_spoken_span(text, parts)
    if evidence is None:
        return None
    stop, _ = evidence
    m = _DEGREE_STATEMENT.fullmatch(text[1:stop])
    if m is None or text[stop] not in ".!":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        _subject("subject"), _alts("verb", "V", **_v("finite", "intransitive", base_surface="true")),
        _lex("degree", "ADV"), _lex("manner", "ADV"),
    ))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


_PASSIVE = re.compile(
    rf"(?P<modal>Will|Would|Can|Could|Should|Must|Might|May) +"
    rf"(?P<subject>.+?) +(?P<be>be) +(?P<participle>{WORD})"
)


def plan_modal_passive(text, parts):
    evidence = _single_spoken_span(text, parts)
    if evidence is None:
        return None
    stop, _ = evidence
    m = _PASSIVE.fullmatch(text[1:stop])
    if m is None or text[stop] != "?":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        _lex("modal", "MODAL", vform="finite"), _subject("subject"),
        _scoped("be", "AUX-BE", vform="base"),
        _alts("participle", "V", **_v("ed", "transitive")),
    ))
    mark("QMARK", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


SPOKEN = (
    (MINOR_REPORT, plan_minor_report),
    (FREQUENCY_REPLY, plan_frequency_reply),
    (MANNER_QUESTION, plan_manner_question),
    (MANNER_STATEMENT, plan_manner_statement),
    (MODAL_PASSIVE, plan_modal_passive),
)
NARRATIVE = ((MINIMIZER, plan_minimizer), (APOSTROPHE, plan_apostrophe))
CLAUSE_COUNTS = {MINIMIZER: 1, APOSTROPHE: 0, MINOR_REPORT: 0,
                 FREQUENCY_REPLY: 0, MANNER_QUESTION: 1,
                 MANNER_STATEMENT: 1, MODAL_PASSIVE: 1}
