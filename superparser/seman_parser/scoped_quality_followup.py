"""Prove selected predicates and speech acts on their original source spans."""

from __future__ import annotations

import re

from .additional_spoken_acts import _single_spoken_span
from .dialogue_clause_plans import _specs
from .scoped_quality_repairs import (
    PRON, REPORT, REPORT_LEMMAS, WORD, _alts, _lex, _phrase, _punct, _scoped, _subject,
)
from .scoped_transfer_clauses import _matrix, _v

BODY_PART = "structural_transitive_body_part_with_of_genitive"
MINIMUM_REPORT = "dialogue_structural_reported_minimum_measure"
INVERTED_REPORT = "dialogue_structural_reported_deictic_inversion"
TITLED_REPORT = "dialogue_structural_reported_titled_address"
CONTRAST = "structural_wh_nominal_comparison_exclamation"
DEAR_ADDRESS = "dialogue_structural_repeated_affective_address"
DEGREE_ECHO = "dialogue_structural_repeated_degree_reply"
FUSED_NEGATIVE = "dialogue_structural_fused_negative_modal_prepositional"
UNIVERSAL_OBJECT = "structural_universal_object_and_temporal_adverb"
CONTINUATION = "structural_consecutive_marker_and_continuative_particle"
MINOR_AND_PERFECT = "dialogue_structural_nominal_reply_then_perfect_question"
OBJECT_CONTROL = "structural_finite_object_control_with_oblique"
MOTION_PERFECT = "structural_past_perfect_intransitive_motion_goal"
RESUMED_PERMISSION = "dialogue_structural_acknowledgment_then_permission"
RECIPROCAL_AND_CONTROL = "structural_reciprocal_and_unable_infinitive"
LOCATIVE_CONTROL = "structural_initial_locative_with_subject_control"
HANDSHAKE = "structural_reciprocal_handshake_with_manner"


def _report(text, components, pattern, specs_for_body, stops=",!"):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None:
        return None
    stop, tag = evidence
    if text[stop] not in stops:
        return None
    body = pattern.fullmatch(text[1:stop])
    orig = text[tag["start"]:tag["end"]]
    reporter = re.fullmatch(rf"(?P<verb>{REPORT}) +(?P<speaker>[^,;!?]+)", orig)
    if body is None or reporter is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(body, 1, specs_for_body)
    mark("COMMA" if text[stop] == "," else "SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    speaker = (("speaker", "NP", "proper-phrase", {})
               if re.fullmatch(r"[A-Z][a-z]+ +[A-Z][a-z]+", reporter["speaker"])
               else _subject("speaker"))
    part(reporter, tag["start"], (
        _alts("verb", "V", vform="finite", lemma_in=REPORT_LEMMAS), speaker,
    ))
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs


def _standalone(text, components, regex, body, stops=".!"):
    evidence = _single_spoken_span(text, components)
    if evidence is None:
        return None
    stop, _ = evidence
    m = regex.fullmatch(text[1:stop])
    if m is None or text[stop] not in stops:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, body)
    mark("QMARK" if text[stop] == "?" else "SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


def _narrative(text, components, regex, body):
    m = regex.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (*body, _punct("stop", "SPEECH-STOP")))
    return specs


_BODY = re.compile(
    r"(?P<subject>.+?) +(?P<verb>took|held|seized|touched|grasped) +"
    r"(?P<det>the) +(?P<body>hand|arm|wrist|shoulder|face|leg) +"
    r"(?P<of>of) +(?P<owner>.+?)(?P<stop>\.)"
)


def plan_body_part(text, parts):
    return _narrative(text, parts, _BODY, (
        _subject("subject"), _alts("verb", "V", **_v("finite", "transitive")),
        _lex("det", "DET"), _lex("body", "N", number="singular"),
        _lex("of", "PREP", lemma_in="of"), _phrase("owner"),
    ))


_MEASURE = re.compile(
    r"(?P<bound>(?:A|An|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten) +"
    r"(?:day|week|month|year|hour|minute)s?) +(?P<min>at least)"
)


def plan_minimum_report(text, parts):
    return _report(text, parts, _MEASURE, (
        _phrase("bound"), _scoped("min", "DEGREE", minimum="true"),
    ), stops=",")


_INVERTED = re.compile(
    r"(?P<here>Here) +(?P<motion>come|go|run) +"
    r"(?P<postposed>[^,]+)(?P<comma>,) +(?P<address>sir|madam)"
)


def plan_inverted_report(text, parts):
    return _report(text, parts, _INVERTED, (
        _lex("here", "ADV"), _alts("motion", "V", **_v("finite", "intransitive", base_surface="true")),
        _phrase("postposed", number="plural"), _punct("comma", "COMMA"),
        _scoped("address", "VOCATIVE", honorific="true"),
    ), stops=",")


_TITLE = rf"(?P<title>Master|Mister|Doctor|Captain|Miss) +(?P<name>[A-Z][a-z]+)"
_ECHO_ADDRESS = re.compile(rf"(?P<oh>Oh)(?P<c1>,) +(?P<indeed>indeed|truly)(?P<c2>,) +{_TITLE}")
_NOMINAL_ADDRESS = re.compile(
    rf"(?P<article>A|An) +(?P<attribute>{WORD}) +(?P<nominal>{WORD})(?P<c1>,) +{_TITLE}"
)


def plan_titled_report(text, parts):
    address = (_scoped("title", "TITLE", honorific="true"),
               ("name", "NP", "proper-phrase", {}))
    echo = _report(text, parts, _ECHO_ADDRESS, (
        _scoped("oh", "INTERJECTION", exclamative="true"), _punct("c1", "COMMA"),
        _lex("indeed", "ADV"), _punct("c2", "COMMA"), *address,
    ), stops=",")
    if echo:
        return echo
    return _report(text, parts, _NOMINAL_ADDRESS, (
        _lex("article", "DET", number="singular"), _lex("attribute", "ADJ"),
        _lex("nominal", "N", number="singular"), _punct("c1", "COMMA"), *address,
    ), stops="!")


_CONTRAST = re.compile(
    r"(?P<what>What) +(?P<article>a) +"
    r"(?P<noun>contrast|difference|distinction|gap|connection) +(?P<between>between) +"
    r"(?P<left>.+?) +(?P<and>and) +(?P<right>.+?)(?P<stop>!)"
)


def plan_contrast(text, parts):
    return _narrative(text, parts, _CONTRAST, (
        _lex("what", "WH-NOM", wh="true"), _lex("article", "DET", number="singular"),
        _lex("noun", "N", number="singular"), _lex("between", "PREP", lemma_in="between"),
        _phrase("left"), _lex("and", "COORD", lemma_in="and"), _phrase("right"),
    ))


_AFFECT = re.compile(r"(?P<first>Dear)(?P<comma>,) +(?P<second>dear) +(?P<name>[A-Z][a-z]+)")


def plan_affective_address(text, parts):
    return _standalone(text, parts, _AFFECT, (
        _lex("first", "ADJ"), _punct("comma", "COMMA"), _lex("second", "ADJ"),
        ("name", "NP", "proper-phrase", {}),
    ), stops="!")


def _two_beats(text, parts):
    speech = [p for p in parts if p.get("function") == "direct_speech"]
    if len(speech) != 1:
        return None
    q = speech[0]
    if (q["start"], q["end"], q["relation"]) != (0, len(text), "unattributed_speech"):
        return None
    acts = [p for p in parts if p.get("function") == "spoken_clause_candidate"
            and p.get("governor") == q["id"]]
    if len(acts) != 2:
        return None
    a, b = sorted(acts, key=lambda p: p["start"])
    if a["start"] != 1 or b["end"] != len(text) - 1 or text[a["end"]:b["start"]].strip():
        return None
    return a, b


_DEGREE_PAIR = re.compile(r"(?P<first>Very|Extremely|Exceedingly)! +(?P<second>(?P=first))!")


def plan_degree_echo(text, parts):
    if _two_beats(text, parts) is None:
        return None
    m = _DEGREE_PAIR.fullmatch(text[1:-1])
    if m is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        _scoped("first", "DEGREE", fragment_degree="true"),
        _scoped("second", "DEGREE", fragment_degree="true"),
    ))
    for g in ("first", "second"):
        mark("SPEECH-STOP", m.end(g) + 1, m.end(g) + 2)
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return specs


_CANNOT = re.compile(
    rf"(?P<subject>{PRON}) +(?P<can>can)(?P<not>not) +"
    rf"(?P<verb>{WORD}) +(?P<prep>for|on|to|with|upon) +(?P<object>.+?)"
)


def plan_fused_negative(text, parts):
    return _standalone(text, parts, _CANNOT, (
        _subject("subject"), ("can", "MODAL", "source-fused-modal", {}),
        ("not", "NEG", "source-fused-modal", {}),
        _alts("verb", "V", **_v("base", "prepositional", base_surface="true")),
        _lex("prep", "PREP"), _phrase("object"),
    ))


_UNIVERSAL = re.compile(
    r"(?P<subject>.+?) +(?P<verb>knew|understood|remembered|heard|saw|realized) +"
    r"(?P<object>all) +(?P<time>now|then|already)(?P<stop>\.)"
)


def plan_universal_object(text, parts):
    return _narrative(text, parts, _UNIVERSAL, (
        _subject("subject"), _alts("verb", "V", **_v("finite", "transitive")),
        _lex("object", "PRONOUN"), _lex("time", "ADV"),
    ))


_CONTINUATION = re.compile(
    r"(?P<so>So) +(?P<subject>.+?) +(?P<verb>went|walked|moved|carried|pressed) +"
    r"(?P<on>on)(?P<stop>\.)"
)


def plan_continuation(text, parts):
    return _narrative(text, parts, _CONTINUATION, (
        _scoped("so", "ADV", discourse_transition="true"), _subject("subject"),
        _alts("verb", "V", **_v("finite", "intransitive", nonbase_surface="true")),
        _lex("on", "PARTICLE", lemma_in="on"),
    ))


_NOMINAL = re.compile(rf"(?P<article>A|An) +(?P<adj>{WORD}) +(?P<noun>{WORD})\.")
_PERFECT_QUESTION = re.compile(
    rf"(?P<subject>I|[Ww]e|[Yy]ou|[Tt]hey) +(?P<have>have) +"
    rf"(?P<verb>{WORD}) +(?P<object>.+?)\?"
)


def plan_minor_and_perfect(text, parts):
    acts = _two_beats(text, parts)
    if acts is None:
        return None
    a, b = acts
    nominal = _NOMINAL.fullmatch(text[a["start"]:a["end"]])
    question = _PERFECT_QUESTION.fullmatch(text[b["start"]:b["end"]])
    if nominal is None or question is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(nominal, a["start"], (
        _lex("article", "DET", number="singular"), _lex("adj", "ADJ"),
        _lex("noun", "N", number="singular"),
    ))
    mark("SPEECH-STOP", a["end"] - 1, a["end"])
    part(question, b["start"], (
        _subject("subject"), _lex("have", "HAVE", vform="finite"),
        _alts("verb", "V", **_v("ed", "transitive")), _phrase("object"),
    ))
    mark("QMARK", b["end"] - 1, b["end"])
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return specs


_CTRL = re.compile(
    rf"(?P<subject>.+?) +(?P<time>now|then|immediately) +"
    rf"(?P<control>called|asked|told|ordered|invited|instructed|urged) +"
    rf"(?P<patient>me|him|her|us|them|you) +(?P<to>to) +"
    rf"(?P<action>{WORD}) +(?P<prep>at|to|for|on|with|upon) +(?P<object>.+?)(?P<stop>\.)"
)


def plan_object_control(text, parts):
    return _narrative(text, parts, _CTRL, (
        _subject("subject"), _lex("time", "ADV"),
        _scoped("control", "V", **_v("finite", "object_control")),
        _phrase("patient", proof_rule="np_indef_pron"), _lex("to", "TO"),
        _alts("action", "V", **_v("base", "prepositional", base_surface="true")),
        _lex("prep", "PREP"), _phrase("object"),
    ))


_WALK = re.compile(
    rf"(?P<subject>.+?) +(?P<had>had) +(?P<motion>{WORD}) +"
    r"(?P<direction>away|back|down|up) +(?P<to>to) +(?P<goal>.+?)(?P<stop>\.)"
)


def plan_motion_perfect(text, parts):
    return _narrative(text, parts, _WALK, (
        _subject("subject"), _lex("had", "HAVE", vform="finite"),
        _alts("motion", "V", **_v("ed", "intransitive", lemma_in="walk|run|move|go|hurry|march|step|rush")),
        _lex("direction", "ADV"), _lex("to", "PREP", lemma_in="to"), _phrase("goal"),
    ))


_ACK = re.compile(r"(?P<yes>Good|Fine|Excellent)(?P<comma>,)")
_PERMISSION = re.compile(
    rf"(?P<and>and) +(?P<time>now|then) +(?P<may>may) +"
    rf"(?P<subject>{PRON}) +(?P<verb>{WORD})(?P<stop>\?)"
)


def plan_resumed_permission(text, parts):
    by_id = {p["id"]: p for p in parts}
    q0, q1, tag = (by_id.get(i) for i in ("q0", "q1", "r0"))
    if not (q0 and q1 and tag and q0["governor"] == tag["id"]
            and q1["relation"] == "resumption_of_split_speech"
            and tag["evidence"] == "intercalated_reporting_clause"
            and q0["start"] == 0 and q1["end"] == len(text)):
        return None
    ack = _ACK.fullmatch(text[1:q0["end"] - 1])
    permission = _PERMISSION.fullmatch(text[q1["start"] + 1:q1["end"] - 1])
    reporting = re.fullmatch(rf"(?P<verb>{REPORT}) +(?P<speaker>{PRON})", text[tag["start"]:tag["end"]])
    if not (ack and permission and reporting):
        return None
    extra = text[tag["end"]:q1["start"]]
    if not re.fullmatch(r", +", extra):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(ack, 1, (_scoped("yes", "RESPONSE", polarity="positive"), _punct("comma", "COMMA")))
    mark("CLOSE-QUOTE", q0["end"] - 1, q0["end"])
    part(reporting, tag["start"], (
        _alts("verb", "V", vform="finite", lemma_in=REPORT_LEMMAS), _subject("speaker"),
    ))
    mark("COMMA", tag["end"], tag["end"] + 1)
    mark("OPEN-QUOTE", q1["start"], q1["start"] + 1)
    part(permission, q1["start"] + 1, (
        _lex("and", "COORD", lemma_in="and"), _lex("time", "ADV"),
        _lex("may", "MODAL", vform="finite"), _subject("subject"),
        _alts("verb", "V", **_v("base", "intransitive", base_surface="true")),
        _punct("stop", "QMARK"),
    ))
    mark("CLOSE-QUOTE", q1["end"] - 1, q1["end"])
    return specs


_RECIPROCAL = re.compile(
    rf"(?P<subject>They|We) +(?P<first>looked|glanced|stared|spoke) +"
    rf"(?P<prep>at|to) +(?P<reciprocal>one another|each other) +(?P<and>and) +"
    rf"(?P<were>were) +(?P<unable>unable) +(?P<to>to) +(?P<reply>{WORD})(?P<stop>\.)"
)


def plan_reciprocal_and_control(text, parts):
    return _narrative(text, parts, _RECIPROCAL, (
        _subject("subject"), _alts("first", "V", **_v("finite", "prepositional")),
        _lex("prep", "PREP"), _scoped("reciprocal", "RECIPROCAL-PRONOUN", reciprocal="true"),
        _lex("and", "COORD", lemma_in="and"), _lex("were", "COPULA", vform="finite", number="plural"),
        _lex("unable", "ADJ"), _lex("to", "TO"),
        _alts("reply", "V", **_v("base", "intransitive", base_surface="true")),
    ))


_LOCATIVE_CTRL = re.compile(
    rf"(?P<at>In|At|Inside|Outside) +(?P<place>(?:this|that|the) +{WORD}) +"
    rf"(?P<subject>{PRON}) +(?P<control>chanced|happened|managed|ventured) +"
    rf"(?P<to>to) +(?P<action>{WORD}) +(?P<object>.+?)(?P<stop>\.)"
)


def plan_locative_control(text, parts):
    return _narrative(text, parts, _LOCATIVE_CTRL, (
        _lex("at", "PREP"), _phrase("place", proof_rule="np_det_n"), _subject("subject"),
        _scoped("control", "V", **_v("finite", "subject_control")),
        _lex("to", "TO"), _alts("action", "V", **_v("base", "transitive", base_surface="true")),
        _phrase("object"),
    ))


_HANDSHAKE = re.compile(
    r"(?P<subject>We|They) +(?P<shook>shook) +(?P<hands>hands) +"
    r"(?P<manner>heartily|warmly|firmly|cordially|briefly)(?P<stop>\.)"
)


def plan_handshake(text, parts):
    return _narrative(text, parts, _HANDSHAKE, (
        _subject("subject"), _alts("shook", "V", **_v("finite", "transitive")),
        _scoped("hands", "N", number="plural", body_part="true"), _lex("manner", "ADV"),
    ))


SPOKEN = ((MINIMUM_REPORT, plan_minimum_report), (INVERTED_REPORT, plan_inverted_report),
          (TITLED_REPORT, plan_titled_report), (DEAR_ADDRESS, plan_affective_address),
          (DEGREE_ECHO, plan_degree_echo), (FUSED_NEGATIVE, plan_fused_negative),
          (MINOR_AND_PERFECT, plan_minor_and_perfect), (RESUMED_PERMISSION, plan_resumed_permission))
NARRATIVE = ((BODY_PART, plan_body_part), (CONTRAST, plan_contrast),
             (UNIVERSAL_OBJECT, plan_universal_object), (CONTINUATION, plan_continuation),
             (OBJECT_CONTROL, plan_object_control), (MOTION_PERFECT, plan_motion_perfect),
             (RECIPROCAL_AND_CONTROL, plan_reciprocal_and_control), (LOCATIVE_CONTROL, plan_locative_control),
             (HANDSHAKE, plan_handshake))
COUNTS = {MINIMUM_REPORT: 0, INVERTED_REPORT: 1, TITLED_REPORT: 0,
          DEAR_ADDRESS: 0, DEGREE_ECHO: 0, FUSED_NEGATIVE: 1, MINOR_AND_PERFECT: 1,
          BODY_PART: 1, CONTRAST: 0, UNIVERSAL_OBJECT: 1, CONTINUATION: 1,
          OBJECT_CONTROL: 1, MOTION_PERFECT: 1, RESUMED_PERMISSION: 1,
          RECIPROCAL_AND_CONTROL: 2, LOCATIVE_CONTROL: 1, HANDSHAKE: 1}
