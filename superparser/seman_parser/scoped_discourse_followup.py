"""Bounded proofs for a telling pseudocleft and a measured past event."""
from __future__ import annotations

import re

from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _BE, _NP, _OBJ, _PRON, _matrix, _v

TELLING = "dialogue_structural_telling_pseudocleft_with_vocative_condition"
ELAPSED = "structural_finite_intransitive_with_deictic_elapsed_time"
_PERSON = r"[A-Z][a-z]+(?: +[A-Z][a-z]+){0,2}"
_COUNT = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[1-9][0-9]?"
_UNIT = r"day|week|month|year|hour|minute"
_WANT = re.compile(
    rf"(?P<demo>That|This) +(?P<be>is|was) +(?P<what>what) +(?P<speaker>I|we) +"
    rf"(?P<want>want|wanted|mean|meant|intended) +(?P<to>to) +(?P<tell>tell) +(?P<target>{_OBJ}), +"
    rf"(?P<vocative>{_PERSON}), +(?P<if>if) +(?P<giver>you)(?: *(?P<modal>will|would|could|[’']ll)) +"
    rf"(?P<ever>ever) +(?P<give>give) +(?P<recipient>me|us) +(?P<chance>a +chance) +"
    rf"(?P<to2>to) +(?P<get>get) +(?P<word>a +word) +(?P<in>in) +(?P<edgewise>edgewise|edgeways)"
)
_PROGRESSIVE = re.compile(
    rf"(?P<subject>{_PRON}) +(?P<be>am|is|are|was|were) +(?P<talk>talking|speaking) +"
    rf"(?P<topic>about +(?:{_OBJ}|{_PERSON}))", re.IGNORECASE,
)
_TIME = re.compile(
    rf"(?P<subject>(?:The|the) +{_NP}?|{_PERSON}|(?i:{_PRON})) +"
    rf"(?P<verb>vanished|disappeared|arrived|returned|died|left|came|departed|moved|happened) +"
    rf"(?P<count>{_COUNT}) +(?P<unit>{_UNIT})(?P<plural>s)? +(?P<ago>ago)(?P<stop>[.!])"
)


def plan_telling_pseudocleft(text, spans):
    if len(spans) != 2 or any(text[end] != "." for _, _, end in spans):
        return None
    (a, b, _), (c, d, _) = spans
    m, n = _WANT.fullmatch(text[a:b]), _PROGRESSIVE.fullmatch(text[c:d])
    if m is None or n is None or n["be"].casefold() not in _BE[n["subject"].casefold()]:
        return None
    # The giving recipient controls the nominal infinitive. In this narrow
    # construction that recipient is the speaker, not the vocative or giver.
    if (m["speaker"], m["recipient"]) not in (("I", "me"), ("we", "us")):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, a, (
        ("demo", "PRONOUN", "lexical", {"definiteness": "demonstrative"}),
        ("be", "COPULA", "lexical", {"vform": "finite"}),
        ("what", "WH-NOM", "lexical", {"free_relative": "true"}),
        ("speaker", "NP", "subject-phrase", {}),
        ("want", "V", "lexical-alternatives", _v("finite", "subject_control")),
        ("to", "TO", "lexical", {}),
        ("tell", "V", "lexical-alternatives", _v("base", "ditransitive", lemma_in="tell")),
        ("target", "PRONOUN", "lexical", {"reflexive": "false"}),
    ))
    mark("COMMA", a + m.end("target"), a + m.end("target") + 1)
    part(m, a, (("vocative", "NP", "proper-phrase", {}),))
    mark("COMMA", a + m.end("vocative"), a + m.end("vocative") + 1)
    part(m, a, (
        ("if", "CONJ", "lexical", {"complementizer": "conditional"}),
        ("giver", "NP", "subject-phrase", {}),
        ("modal", "MODAL", "lexical", {"vform": "finite"}),
        ("ever", "ADV", "lexical", {"indefinite_time": "true"}),
        ("give", "V", "lexical-alternatives", _v("base", "ditransitive", lemma_in="give")),
        ("recipient", "PRONOUN", "lexical", {"case": "accusative"}),
        ("chance", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("to2", "TO", "lexical", {}),
        ("get", "V", "lexical-alternatives", _v("base", "transitive", lemma_in="get")),
        ("word", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("in", "PARTICLE", "lexical", {}),
        ("edgewise", "ADV", "lexical", {}),
    ))
    mark("SPEECH-STOP", b, b + 1)
    part(n, c, (
        ("subject", "NP", "subject-phrase", {}),
        ("be", "AUX-BE", "lexical", {"vform": "finite"}),
        ("talk", "V", "lexical-alternatives", _v("ing", "prepositional", lemma_in="talk|speak")),
        ("topic", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("SPEECH-STOP", d, d + 1)
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return TELLING, specs


def plan_elapsed_event(text, components):
    m = _TIME.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    plural = m["count"] not in ("one", "1")
    if plural != bool(m["plural"]):
        return None
    specs, add, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "phrase", {}),
        ("verb", "V", "lexical-alternatives", _v(
            "finite", "intransitive",
            lemma_in="vanish|disappear|arrive|return|die|leave|come|depart|move|happen",
        )),
        ("count", "NUM", "lexical", {}),
    ))
    add("N", m.start("unit"), m.end("plural") if plural else m.end("unit"),
        number="plural" if plural else "singular")
    part(m, 0, (("ago", "ADV", "lexical", {"lemma_in": "ago"}),))
    mark("SPEECH-STOP", *m.span("stop"))
    return specs


EMPHATIC_MODAL_CONTRAST = "dialogue_structural_emphatic_modal_polarity_contrast"
_ABILITY = re.compile(
    rf"(?P<subject>{_PRON}) +(?P<open>_)(?P<modal>can)(?P<close>_) +"
    rf"(?P<move>move|walk|travel|wander) +(?P<about>about) +(?P<first>in +{_NP}), +"
    rf"(?P<but>but) +(?P<right>{_PRON}) +(?P<can>can)(?P<not>not) +"
    rf"(?P<move2>move|walk|travel|wander) +(?P<about2>about) +(?P<second>in +{_NP})",
    re.IGNORECASE,
)


def plan_emphatic_modal_contrast(text, components):
    from .additional_spoken_acts import _single_spoken_span

    source = _single_spoken_span(text, components)
    if source is None or text[source[0]] not in ".!":
        return None
    stop, _ = source
    m = _ABILITY.fullmatch(text[1:stop])
    if m is None or m["subject"].casefold() != m["right"].casefold() or m["move"] != m["move2"]:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("subject", "NP", "subject-phrase", {}),
        ("open", "EMPHASIS", "source-punctuation", {}),
        ("modal", "MODAL", "lexical", {"vform": "finite"}),
        ("close", "EMPHASIS", "source-punctuation", {}),
        ("move", "V", "lexical-alternatives", _v("base", "intransitive")),
        ("about", "ADV", "lexical", {}),
        ("first", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("COMMA", 1 + m.end("first"), 2 + m.end("first"))
    part(m, 1, (
        ("but", "COORD", "lexical", {"lemma_in": "but"}),
        ("right", "NP", "subject-phrase", {}),
        ("can", "MODAL", "source-fused-modal", {}),
        ("not", "NEG", "source-fused-modal", {}),
        ("move2", "V", "lexical-alternatives", _v("base", "intransitive")),
        ("about2", "ADV", "lexical", {}),
        ("second", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return specs


REPORTED_EMPHATIC_OPINIONS = "dialogue_structural_reported_ellipsis_and_emphatic_state"
_OPINION_ELLIPSIS = re.compile(
    rf"(?P<source>{_PERSON}) +(?P<told>told) +(?P<hearer>{_OBJ}) +"
    rf"(?P<subject>{_PRON}) +(?P<do>did|does|do)"
)
_OPINION_STATE = re.compile(
    rf"(?P<source>{_PERSON}) +(?P<said>said|reported|claimed) +(?P<subject>{_PRON}) +"
    rf"(?P<be>am|is|are|was|were) +(?P<open>_)(?P<state>infatuated|obsessed|smitten|enchanted)"
    rf"(?P<close>_) +(?P<target>with +(?:{_OBJ}|{_PERSON}))"
)


def plan_reported_emphatic_opinions(text, spans):
    if len(spans) != 2 or any(text[end] != "." for _, _, end in spans):
        return None
    (a, b, _), (c, d, _) = spans
    m, n = _OPINION_ELLIPSIS.fullmatch(text[a:b]), _OPINION_STATE.fullmatch(text[c:d])
    if m is None or n is None or n["be"] not in _BE[n["subject"]]:
        return None
    if m["do"] != "did" and (m["do"] == "does") != (m["subject"] in ("he", "she", "it")):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, a, (
        ("source", "NP", "proper-phrase", {}),
        ("told", "V", "lexical-alternatives", _v("finite", "clausal", lemma_in="tell")),
        ("hearer", "PRONOUN", "lexical", {"reflexive": "false"}),
        ("subject", "NP", "subject-phrase", {}),
        ("do", "AUX", "lexical", {"vform": "finite", "lemma_in": "do|did"}),
    ))
    mark("SPEECH-STOP", b, b + 1)
    part(n, c, (
        ("source", "NP", "proper-phrase", {}),
        ("said", "V", "lexical-alternatives", _v("finite", "clausal")),
        ("subject", "NP", "subject-phrase", {}),
        ("be", "COPULA", "lexical", {"vform": "finite"}),
        ("open", "EMPHASIS", "source-punctuation", {}),
        ("state", "ADJ", "lexical", {}),
        ("close", "EMPHASIS", "source-punctuation", {}),
        ("target", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("SPEECH-STOP", d, d + 1)
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return REPORTED_EMPHATIC_OPINIONS, specs


EXTRAPOSED_PASSIVE_REPORT = "dialogue_structural_extraposed_evaluation_of_passive_fact"
EMPHATIC_QUESTION_TURN = "dialogue_structural_split_vocative_emphatic_question"
_EVALUATION = re.compile(
    rf"(?P<now>Now), +(?P<it>it) +(?P<be>is|was) +(?P<degree>very|quite|rather) +"
    rf"(?P<evaluation>remarkable|surprising|astonishing|strange) +(?P<that>that) +"
    rf"(?P<subject>this|that|it) +(?P<aux>is|was) +(?P<so>so) +(?P<manner>[a-z]+ly) +"
    rf"(?P<verb>[a-z]+ed)"
)
_EVALUATOR = re.compile(
    rf"(?P<report>continued|said|observed|replied|remarked) +(?P<speaker>(?:[Tt]he +(?i:{_NP})|{_PERSON})), +"
    rf"(?P<manner>with +{_NP})"
)
_CALL = re.compile(rf"(?P<interjection>Oh), +(?P<address>{_PERSON})")
_REPORT_WITH_GESTURE = re.compile(
    rf"(?P<report>cried|asked|said|exclaimed) +(?P<speaker>{_PERSON}), +"
    rf"(?P<gesture>clasping|wringing|folding|raising) +(?P<hands>(?:his|her|their) +hands)"
)
_EMPHATIC_QUESTION = re.compile(
    rf"(?P<do>[Dd]o|[Dd]oes|[Dd]id) +(?P<subject>{_PRON}) +(?P<open>_)"
    rf"(?P<verb>love|trust|know|like|believe)(?P<close>_) +(?P<object>{_OBJ})"
)


def plan_extraposed_passive_report(text, components):
    from .additional_spoken_acts import _single_spoken_span

    source = _single_spoken_span(text, components, reported=True)
    if source is None or text[source[0]] != ",":
        return None
    stop, tag = source
    m, n = _EVALUATION.fullmatch(text[1:stop]), _EVALUATOR.fullmatch(text[tag["start"]:tag["end"]])
    if m is None or n is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (("now", "ADV", "lexical", {"discourse_transition": "true"}),))
    mark("COMMA", 1 + m.end("now"), 2 + m.end("now"))
    part(m, 1, (
        ("it", "EXTRAPOSITION-IT", "lexical", {}),
        ("be", "COPULA", "lexical", {"vform": "finite"}),
        ("degree", "DEGREE", "lexical", {}),
        ("evaluation", "ADJ", "lexical", {}),
        ("that", "COMP-THAT", "lexical", {}),
        ("subject", "PRONOUN", "lexical", {}),
        ("aux", "AUX-BE", "lexical", {"vform": "finite"}),
        ("so", "DEGREE", "lexical", {"scalar_degree": "true"}),
        ("manner", "ADV", "lexical", {}),
        ("verb", "V", "lexical-alternatives", _v("ed", "transitive")),
    ))
    mark("COMMA", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    t = tag["start"]
    part(n, t, (
        ("report", "V", "lexical-alternatives", {"vform": "finite"}),
        ("speaker", "NP", "phrase", {}),
    ))
    mark("COMMA", t + n.end("speaker"), t + n.end("speaker") + 1)
    part(n, t, (("manner", "PP", "phrase", {"proof_rule": "pp_prep_np"}),))
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs


def plan_emphatic_question_turn(text, plan):
    # The regular intercalation gate already verified exact source quote,
    # governor, speaker tag and comma offsets for this split turn.
    if plan is None:
        return None
    first, second, (a, b), comma = plan
    if text[second.stop] != "?":
        return None
    m, n, q = (
        _CALL.fullmatch(text[first.start:first.end]),
        _REPORT_WITH_GESTURE.fullmatch(text[a:b]),
        _EMPHATIC_QUESTION.fullmatch(text[second.start:second.end]),
    )
    if m is None or n is None or q is None:
        return None
    aux = q["do"].casefold()
    if aux != "did" and (aux == "does") != (q["subject"] in ("he", "she", "it")):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, first.start, (("interjection", "INTERJECTION", "source-echo-interjection", {}),))
    offset = first.start + m.end("interjection")
    mark("COMMA", offset, offset + 1)
    part(m, first.start, (("address", "NP", "proper-phrase", {}),))
    mark("COMMA", first.stop, first.stop + 1)
    mark("CLOSE-QUOTE", first.stop + 1, first.stop + 2)
    part(n, a, (
        ("report", "V", "lexical-alternatives", {"vform": "finite"}),
        ("speaker", "NP", "proper-phrase", {}),
    ))
    mark("COMMA", a + n.end("speaker"), a + n.end("speaker") + 1)
    part(n, a, (
        ("gesture", "V", "lexical-alternatives", _v("ing", "transitive")),
        ("hands", "NP", "phrase", {"proof_rule": "np_poss"}),
    ))
    mark("COMMA", comma, comma + 1)
    mark("OPEN-QUOTE", second.start - 1, second.start)
    part(q, second.start, (
        ("do", "AUX", "lexical", {"vform": "finite"}),
        ("subject", "NP", "subject-phrase", {}),
        ("open", "EMPHASIS", "source-punctuation", {}),
        ("verb", "V", "lexical-alternatives", _v("base", "transitive")),
        ("close", "EMPHASIS", "source-punctuation", {}),
        ("object", "PRONOUN", "lexical", {"reflexive": "false"}),
    ))
    mark("QMARK", second.stop, second.stop + 1)
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return specs


CONDITIONAL_VERSE = "dialogue_structural_verse_conditional_with_exceptive_subject"
_VERSE = re.compile(
    r"(?P<if>If) +(?P<you>you) +(?P<love>love|trust|remember) +(?P<me>me|us) +"
    r"(?P<as>as) +(?P<i>I|we) +(?P<love2>love|trust|remember) +(?P<you2>you)"
    r"(?P<line> )(?P<nothing>Nothing) +(?P<but>but) +(?P<exception>[a-z-]+) +"
    r"(?P<modal>can|could|will|would) +(?P<part>part|separate|divide) +(?P<us>us) +(?P<two>two)"
)


def plan_conditional_verse(text, components):
    from .additional_spoken_acts import _single_spoken_span

    scope = _single_spoken_span(text, components)
    if scope is None or text[scope[0]] not in ".!":
        return None
    stop, _ = scope
    m = _VERSE.fullmatch(text[1:stop])
    if m is None or m["love"] != m["love2"]:
        return None
    if (m["me"], m["i"]) not in (("me", "I"), ("us", "we")):
        return None
    if not any(c.get("function") == "typographic_line_break"
               and (c["start"], c["end"]) == (1 + m.start("line"), 1 + m.end("line"))
               and c.get("evidence") == "original_newline_followed_by_indentation"
               for c in components):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("if", "CONJ", "lexical", {"complementizer": "conditional"}),
        ("you", "NP", "subject-phrase", {}),
        ("love", "V", "lexical-alternatives", _v("finite", "transitive")),
        ("me", "PRONOUN", "lexical", {"case": "accusative"}),
        ("as", "CONJ", "lexical", {"degree": "true"}),
        ("i", "NP", "subject-phrase", {}),
        ("love2", "V", "lexical-alternatives", _v("finite", "transitive")),
        ("you2", "PRONOUN", "lexical", {"reflexive": "false"}),
        ("nothing", "INDEF-PRONOUN", "lexical", {"lemma_in": "nothing"}),
        ("but", "EXCEPTIVE", "lexical", {}),
        ("exception", "N", "lexical", {"number": "singular"}),
        ("modal", "MODAL", "lexical", {"vform": "finite"}),
        ("part", "V", "lexical-alternatives", _v("base", "transitive")),
        ("us", "PRONOUN", "lexical", {"case": "accusative", "number": "plural"}),
        ("two", "NUM", "lexical", {}),
    ))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return specs
