"""Source plans for the additive novel cohort, with independently proven parts."""
from __future__ import annotations

import re

from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _matrix, _v
from .additional_spoken_acts import _single_spoken_span

FRONTED_PRECIPITATION = "structural_fronted_onset_with_precipitation_subject"
_PRECIPITATION = re.compile(
    r"(?P<onset>Suddenly|Abruptly) +(?P<det>a|the) +"
    r"(?P<intensity>[a-z][a-z-]+) +(?P<weather>storm|shower|downpour) +"
    r"(?P<of>of) +(?P<precipitation>rain|hail|snow|sleet) +"
    r"(?P<event>descended|fell)(?P<stop>[.!])"
)


def plan_fronted_precipitation(text, components):
    """A fronted onset modifier and a precipitation PP inside the subject."""
    match = _PRECIPITATION.fullmatch(text)
    if match is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(match, 0, (
        ("onset", "ADV", "lexical", {}),
        ("det", "DET", "lexical", {"number": "singular"} if match["det"] != "the" else {}),
        ("intensity", "ADJ", "lexical", {}),
        ("weather", "N", "lexical", {"number": "singular"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("precipitation", "N", "lexical", {"number": "singular"}),
        ("event", "V", "lexical-alternatives", _v("finite", "intransitive")),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


POSTPOS_QUALITY = "structural_copular_nominal_with_integrated_postpositive_quality"

_POSTPOS = re.compile(
    r"(?P<subject>(?i:it|he|she|this|that)) +"
    r"(?P<copula>is|was) +"
    r"(?P<nominal>(?:a|an|the) +[a-z][a-z-]*) +"
    r"(?P<degree>terrifically|utterly|deeply|strikingly|unusually|remarkably|exceedingly|quite|nearly|almost|virtually) +"
    r"(?P<quality>[a-z][a-z-]+)(?P<stop>[.!])"
)


def plan_postpositive_quality(text, components):
    """Independent copular NP, with the degree phrase inside that NP."""
    m = _POSTPOS.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("copula", "COPULA", "lexical", {"vform": "finite"}),
        ("nominal", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("degree", "ADV", "lexical", {}),
        ("quality", "ADJ", "lexical", {}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


FRAMED_RESULT = "structural_framed_continuation_and_graded_result_state"
_RESULT = re.compile(
    r"(?P<frame>In +the +mean(?: +time|time)) +"
    r"(?P<worker>I|he|she|we|they|you) +(?P<continued>worked|read|walked|pressed|struggled) +"
    r"(?P<particle>on), +(?P<and>and) +"
    r"(?P<affected>(?:my|your|his|her|our|their|the) +[a-z][a-z-]*) +"
    r"(?P<be>was|were|is|are) +(?P<already>already|now) +"
    r"(?P<degree>considerably|substantially|very|rather|remarkably|quite) +"
    r"(?P<state>advanced|tired|weary|exhausted|weak|strong|firm|steady)(?P<stop>[.!])"
)


def plan_framed_result(text, components):
    """Continuation particle and the second subject's graded predication."""
    m = _RESULT.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("frame", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("worker", "NP", "subject-phrase", {}),
        ("continued", "V", "lexical-alternatives", _v("finite", "intransitive")),
        ("particle", "PARTICLE", "lexical", {"lemma_in": "on"}),
    ))
    mark("COMMA", m.end("particle"), m.end("particle") + 1)
    part(m, 0, (
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("affected", "NP", "subject-phrase", {}),
        ("be", "COPULA", "lexical-alternatives", {"vform": "finite",
                                             "number": "singular" if m["be"] in ("was", "is") else "plural"}),
        ("already", "ADV", "lexical", {}),
        ("degree", "ADV", "lexical", {}),
        ("state", "ADJ", "lexical", {}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


NEGATIVE_EQUATIVE = "structural_negative_do_inversion_with_equative_nominal"
_NEGATIVE = re.compile(
    r"(?P<never>Never) +(?P<did>did) +(?P<subject>I|you|he|she|we|they) +"
    r"(?P<verb>behold|see|observe|witness) +(?P<object>(?:a|an|the) +[a-z][a-z-]*) +"
    r"(?P<so>so) +(?P<quality>[a-z][a-z-]+) +(?P<as>as) +"
    r"(?P<standard>(?:his|her|my|their|its|our|the) +[a-z][a-z-]*), +"
    r"(?P<of>of) +(?P<such>such) +(?P<first>[a-z][a-z-]+) +(?P<yet>yet) +"
    r"(?P<second>[a-z][a-z-]+) +(?P<noun>[a-z][a-z-]+)(?P<stop>[.!])"
)


def plan_negative_equative(text, components):
    """Negative declarative inversion with a postnominal scalar comparison."""
    m = _NEGATIVE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("never", "DEGREE", "lexical", {"negation": "true", "inversion": "true"}),
        ("did", "AUX", "lexical", {"vform": "finite", "lemma_in": "do"}),
        ("subject", "NP", "subject-phrase", {}),
        ("verb", "V", "lexical-alternatives", _v("base", "transitive")),
        ("object", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("so", "DEGREE", "lexical", {"equative_so": "true"}),
        ("quality", "ADJ", "lexical", {}),
        ("as", "EQUATIVE-AS", "lexical", {"degree": "true"}),
        ("standard", "NP", "phrase", {"simple_nominal_proof": "true"}),
    ))
    mark("COMMA", m.end("standard"), m.end("standard") + 1)
    part(m, 0, (
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("such", "DEGREE", "lexical", {"lemma_in": "such"}),
        ("first", "ADJ", "lexical", {}),
        ("yet", "COORD", "lexical", {"adversative": "true"}),
        ("second", "ADJ", "lexical", {}),
        ("noun", "N", "lexical", {"number": "singular"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


VOCATIVE_COMPARISON = "structural_vocative_with_incised_experiential_comparison"
_VOCATIVE = re.compile(
    r"(?P<vocative>(?:My|Your|Our) +(?:beloved|dear|dearest|good|old) +"
    r"(?:sister|brother|friend|father|mother|child)), +"
    r"(?P<subject>the +[^,;.!?]{7,90}? +of +(?:your|my|our|their|his|her) +[^,;.!?]{2,50}?) +"
    r"(?P<be>is|was), +(?P<incise>in +(?:prospect|retrospect|principle|fact|theory|practice)), +"
    r"(?P<degree>more|less) +(?P<quality>[a-z][a-z-]+) +(?P<to>to) +"
    r"(?P<experiencer>me|you|him|her|us|them) +(?P<than>than) +"
    r"(?P<standard>(?:my|your|their|his|her|our) +[^,;.!?]{2,35})(?P<stop>[.!])"
)


def plan_vocative_comparison(text, components):
    m = _VOCATIVE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (("vocative", "NP", "phrase", {"proof_rule": "np_poss"}),))
    mark("COMMA", m.end("vocative"), m.end("vocative") + 1)
    part(m, 0, (
        ("subject", "NP", "phrase", {"proof_rule": "np_det_n_of", "number": "singular"}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
    ))
    mark("COMMA", m.end("be"), m.end("be") + 1)
    part(m, 0, (("incise", "PP", "phrase", {"proof_rule": "pp_prep_np"}),))
    mark("COMMA", m.end("incise"), m.end("incise") + 1)
    part(m, 0, (
        ("degree", "DEGREE", "lexical", {"comparative": "true"}),
        ("quality", "ADJ", "lexical", {}),
        ("to", "PREP", "lexical", {"lemma_in": "to"}),
        ("experiencer", "PRONOUN", "lexical", {"reflexive": "false"}),
        ("than", "PREP", "lexical", {"comparative": "true"}),
        ("standard", "NP", "phrase", {"proof_rule": "np_poss"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


BARE_PASSIVE_RECIPIENT = "structural_contrast_with_control_and_bare_passive_recipient"
_BARE_RECIPIENT = re.compile(
    r"(?P<subject>I|He|She|We|They|You) +(?P<fear>feared|dreaded) +"
    r"(?P<threat>the +[^,;.!?]{3,70}), +(?P<yet>yet) +(?P<controller>I|he|she|we|they|you) +"
    r"(?P<be>was|were) +(?P<unable>unable) +(?P<to>to) +(?P<action>overcome|conquer|master) +"
    r"(?P<aversion>(?:my|your|his|her|our|their) +(?:repugnance|aversion|reluctance|objection)) +"
    r"(?P<toward>to) +(?P<task>the +[a-z][a-z-]*) +(?P<which>which) +"
    r"(?P<aux>was|were) +(?P<assigned>enjoined|assigned|prescribed|allotted) +"
    r"(?P<recipient>me|him|her|us|them|you)(?P<stop>[.!])"
)
_WAS = {"I", "he", "she"}


def plan_bare_passive_recipient(text, components):
    """Keep the relative's theme and the overt dative pronoun distinct."""
    m = _BARE_RECIPIENT.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if (m["be"] == "was") != (m["controller"] in _WAS):
        return None
    possessor = {"I": "my", "he": "his", "she": "her", "you": "your", "we": "our", "they": "their"}
    if m["aversion"].partition(" ")[0] != possessor[m["controller"]]:
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("fear", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("threat", "NP", "phrase", {"proof_rule": "np_det_n_of"}),
    ))
    mark("COMMA", m.end("threat"), m.end("threat") + 1)
    part(m, 0, (
        ("yet", "COORD", "lexical", {"adversative": "true"}),
        ("controller", "NP", "subject-phrase", {}),
        ("be", "COPULA", "lexical-alternatives", {"vform": "finite"}),
        ("unable", "ADJ", "lexical", {}),
        ("to", "TO", "lexical", {}),
        ("action", "V", "lexical-alternatives", _v("base", "transitive")),
        ("aversion", "NP", "phrase", {"proof_rule": "np_poss"}),
        ("toward", "PREP", "lexical", {"lemma_in": "to"}),
        ("task", "NP", "phrase", {"proof_rule": "np_det_n", "number": "singular" if m["aux"] == "was" else "plural"}),
        ("which", "WH-REL-OBL", "lexical", {"relative": "true"}),
        ("aux", "AUX-BE", "lexical", {"vform": "finite", "number": "singular" if m["aux"] == "was" else "plural"}),
        ("assigned", "V", "lexical-alternatives", _v("ed", "prep_ditransitive")),
        ("recipient", "PRONOUN", "lexical", {"reflexive": "false"} if m["recipient"] == "you" else {"case": "accusative"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


MOTION_SPEECH = "structural_motion_with_immediate_time_and_speech_supplement"
_MOTION = re.compile(
    r"(?P<subject>I|He|She|We|They|You) +(?P<motion>ran|rushed|hurried|walked|went|came|returned) +"
    r"(?P<destination>to +(?:him|her|them|me|you|us|the +[a-z][a-z-]*)) +"
    r"(?P<time>at +once|immediately|right +away), +(?P<speech>calling|crying|shouting|speaking) +"
    r"(?P<addressee>to +(?:him|her|them|me|you|us|(?:my|your|his|her|our|their|the) +[a-z][a-z-]*))"
    r"(?P<stop>[.!])"
)


def plan_motion_speech(text, components):
    m = _MOTION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("motion", "V", "lexical-alternatives", _v("finite", "intransitive", nonbase_surface="true")),
        ("destination", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("time", "ADV", "lexical", {}),
    ))
    mark("COMMA", m.end("time"), m.end("time") + 1)
    part(m, 0, (
        ("speech", "V", "lexical-alternatives", _v("ing", "intransitive")),
        ("addressee", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


PARALLEL_GROUPS = "structural_overt_parallel_assignment_with_elliptical_groups"
_GROUPS = re.compile(
    r"(?P<first>(?:The|the) +[a-z][a-z-]*) +(?P<and1>and) +(?P<second>[A-Z][a-z]+) +"
    r"(?P<and2>and) +(?P<third>I|[A-Z][a-z]+) +(?P<for>for) +(?P<one>one); +"
    r"(?P<fourth>the +[a-z][a-z-]*), +(?P<fifth>[A-Z][a-z]+), +(?P<and3>and) +"
    r"(?P<sixth>[A-Z][a-z]+) +(?P<upon>upon|on|for) +(?P<the>the) +(?P<other>other)(?P<stop>[.!])"
)


def plan_parallel_groups(text, components):
    """Two overt nominal lists with contrasted elliptical assignment PPs."""
    m = _GROUPS.fullmatch(text)
    if m is None or any(c.get("function") == "direct_speech" for c in components):
        return None
    spans = {(c.get("start"), c.get("end")) for c in components
             if c.get("id") in {"s0", "s1"}}
    if spans != {(0, m.end("one")), (m.start("fourth"), len(text))}:
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("first", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("and1", "COORD", "lexical", {"nominal_coordination": "true"}),
        ("second", "PROPER-NOUN", "lexical", {}),
        ("and2", "COORD", "lexical", {"nominal_coordination": "true"}),
        ("third", "NP", "subject-phrase" if m["third"] == "I" else "proper-phrase", {}),
        ("for", "PREP", "lexical", {"lemma_in": "for"}),
        ("one", "NUM", "lexical", {}),
    ))
    mark("SEMICOLON", m.end("one"), m.end("one") + 1)
    part(m, 0, (("fourth", "NP", "phrase", {"proof_rule": "np_det_n"}),))
    mark("COMMA", m.end("fourth"), m.end("fourth") + 1)
    part(m, 0, (("fifth", "PROPER-NOUN", "lexical", {}),))
    mark("COMMA", m.end("fifth"), m.end("fifth") + 1)
    part(m, 0, (
        ("and3", "COORD", "lexical", {"nominal_coordination": "true"}),
        ("sixth", "PROPER-NOUN", "lexical", {}),
        ("upon", "PREP", "lexical", {}),
        ("the", "DET", "lexical", {"definiteness": "definite"}),
        ("other", "ADJ", "lexical", {}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


EXPERIENTIAL_EXISTENTIAL = "structural_experiential_existential_with_explanatory_participant"
_EXISTENTIAL = re.compile(
    r"(?P<for1>For) +(?P<perspective>me|him|her|us|them|you), +(?P<focus>at +least), +"
    r"(?P<there>there) +(?P<was>was|is) +(?P<no>no) +(?P<secret>secret|mystery|doubt) +"
    r"(?P<topic>about +(?:the|this|that) +[a-z][a-z-]*), +"
    r"(?P<for2>for) +(?P<subject>I|he|she|we|they|you) +(?P<be>was|were|is|are), +"
    r"(?P<qualification>in +a +way|in +a +sense), +"
    r"(?P<role>(?:a|the) +(?:sharer|participant|partner)) +"
    r"(?P<shared>in +(?:my|your|his|her|our|their|the) +[a-z][a-z-]*)(?P<stop>[.!])"
)


def plan_experiential_existential(text, components):
    m = _EXISTENTIAL.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    agreement = {"I": ("was",), "he": ("was", "is"), "she": ("was", "is"),
                 "you": ("were", "are"), "we": ("were", "are"), "they": ("were", "are")}
    if m["be"] not in agreement[m["subject"]] or m["subject"] in {"we", "they"}:
        # Here the complement is overtly singular, not a distributive plural.
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("for1", "PREP", "lexical", {"lemma_in": "for"}),
        ("perspective", "PRONOUN", "lexical", {"reflexive": "false"}),
        ("focus", "ADV", "lexical", {"lemma_in": "at least"}),
        ("there", "EXPL", "lexical", {"expletive": "true"}),
        ("was", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("no", "DET", "lexical", {"negation": "true", "number": "singular"}),
        ("secret", "N", "lexical", {"number": "singular"}),
        ("topic", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("for2", "COORD", "lexical", {"causal_coordination": "true"}),
        ("subject", "NP", "subject-phrase", {}),
        ("be", "COPULA", "lexical", {"vform": "finite"}),
        ("qualification", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("role", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("shared", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    for name in ("perspective", "focus", "topic", "be", "qualification"):
        mark("COMMA", m.end(name), m.end(name) + 1)
    return sorted(specs, key=lambda spec: spec[1])


MINOR_NEGATIVE = "structural_negative_degree_minor_response"
_NEGATIVE_RESPONSE = re.compile(r"(?P<not>Not) +(?P<degree>at +all|in +the +least|by +any +means)(?P<stop>[.!])")


def plan_minor_negative(text, components):
    m = _NEGATIVE_RESPONSE.fullmatch(text)
    if m is None or not any(
        c.get("function") == "minor_utterance" and c.get("relation") == "dialogue_response"
        and (c["start"], c["end"]) == (0, len(text)) for c in components
    ):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("not", "NEG", "lexical", {"negation": "true"}),
        ("degree", "ADV", "lexical", {}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


TOPICAL_POSSESSION = "structural_demonstrative_object_topicalization_with_lexical_possession"
_TOPICAL_POSSESSION = re.compile(
    r"(?P<det>That|This) +(?P<topic>[a-z][a-z-]*) +(?P<subject>I|we|you|he|she|they) +"
    r"(?P<never>never) +(?P<had>had|have|has)(?P<stop>[.!])"
)


def plan_topical_possession(text, components):
    m = _TOPICAL_POSSESSION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if ((m["had"] == "has" and m["subject"] not in {"he", "she"})
            or (m["had"] == "have" and m["subject"] in {"he", "she"})):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("det", "DET", "lexical", {"definiteness": "demonstrative", "number": "singular"}),
        ("topic", "N", "lexical", {"number": "singular"}),
        ("subject", "NP", "subject-phrase", {}),
        ("never", "DEGREE", "lexical", {"negation": "true"}),
        ("had", "V", "lexical-alternatives", _v("finite", "transitive", lemma_in="have")),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


NUMERIC_VOCATIVE = "dialogue_structural_numeric_vocative_with_reporter_participle"
_NUMERIC_ADDRESS = re.compile(
    r"(?P<marker>Well|Indeed|Yes), +(?P<tens>Twenty|Thirty|Forty|Fifty|Sixty|Seventy|Eighty|Ninety) +"
    r"(?P<ones>One|Two|Three|Four|Five|Six|Seven|Eight|Nine)"
)
_NUMERIC_REPORT = re.compile(
    r"(?P<report>said|remarked|replied) +(?P<speaker>(?:Mr\.|Mrs\.|Dr\.|Miss) +[A-Z][a-z]+), +"
    r"(?P<manner>[a-z]+ly) +(?P<gesture>admiring|watching|eyeing|observing) +(?P<target>him|her|them|me|us)"
)


def plan_numeric_vocative(text, components):
    scope = _single_spoken_span(text, components, reported=True)
    if scope is None:
        return None
    stop, reporter = scope
    speech = _NUMERIC_ADDRESS.fullmatch(text[1:stop])
    base = reporter["start"]
    narration = _NUMERIC_REPORT.fullmatch(text[base:reporter["end"]])
    if speech is None or narration is None or text[stop] != ",":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(speech, 1, (("marker", "ADV", "lexical", {}),))
    mark("COMMA", 1 + speech.end("marker"), 2 + speech.end("marker"))
    part(speech, 1, (("tens", "NUM", "lexical", {}), ("ones", "NUM", "lexical", {})))
    mark("COMMA", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    part(narration, base, (
        ("report", "V", "lexical-alternatives", _v("finite", "clausal", nonbase_surface="true")),
        ("speaker", "NP", "proper-phrase", {}),
    ))
    comma = base + narration.end("speaker")
    mark("COMMA", comma, comma + 1)
    part(narration, base, (
        ("manner", "ADV", "lexical", {}),
        ("gesture", "V", "lexical-alternatives", _v("ing", "transitive")),
        ("target", "PRONOUN", "lexical", {"case": "accusative"}),
    ))
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs


AMOUNT_RESTART = "dialogue_structural_question_restarts_with_extraposed_amount"
_AMOUNT = re.compile(
    r"(?P<wh1>What) +(?P<modal1>should|could) +(?P<subject1>you|he|she|they)\s*(?P<dash1>--|—)\s*"
    r"(?P<wh2>what) +(?P<modal2>should|could) +(?P<subject2>I|we)\s*(?P<dash2>--|—)\s*"
    r"(?P<how>how) +(?P<much>much) +(?P<ought>ought) +(?P<subject3>I|we) +(?P<to>to)\s*(?P<dash3>--|—)\s*"
    r"(?P<wh3>what) +(?P<would>would|might|could) +(?P<it>it) +(?P<be>be) +(?P<right>right|proper|fair) +"
    r"(?P<to2>to) +(?P<pay>pay) +(?P<payee>the +[a-z][a-z-]*), +(?P<if>if) +"
    r"(?P<you>you) +(?P<please>please)"
)


def plan_amount_restart(text, components):
    scope = _single_spoken_span(text, components)
    if scope is None or text[scope[0]] != "?":
        return None
    stop, _ = scope
    m = _AMOUNT.fullmatch(text[1:stop])
    if m is None or m["subject2"] != m["subject3"]:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    for i in (1, 2):
        part(m, 1, (
            (f"wh{i}", "WH-NOM", "lexical", {"wh": "true"}),
            (f"modal{i}", "MODAL", "lexical", {"vform": "finite"}),
            (f"subject{i}", "NP", "subject-phrase", {}),
            (f"dash{i}", "DASH", "source-punctuation", {}),
        ))
    part(m, 1, (
        ("how", "WH-NOM", "lexical", {"wh_adverbial": "true"}),
        ("much", "ADV", "lexical", {}),
        ("ought", "MODAL", "scoped-lexical", {"vform": "finite", "selects_to": "true"}),
        ("subject3", "NP", "subject-phrase", {}),
        ("to", "TO", "lexical", {}),
        ("dash3", "DASH", "source-punctuation", {}),
        ("wh3", "WH-NOM", "lexical", {"wh": "true"}),
        ("would", "MODAL", "lexical", {"vform": "finite"}),
        ("it", "EXTRAPOSITION-IT", "lexical", {"extraposition_it": "true"}),
        ("be", "COPULA", "lexical", {"vform": "base"}),
        ("right", "ADJ", "lexical", {}),
        ("to2", "TO", "lexical", {}),
        ("pay", "V", "lexical-alternatives", _v("base", "ditransitive", lemma_in="pay")),
        ("payee", "NP", "phrase", {"proof_rule": "np_det_n"}),
    ))
    comma = 1 + m.end("payee")
    mark("COMMA", comma, comma + 1)
    part(m, 1, (
        ("if", "CONJ", "lexical", {"complementizer": "conditional"}),
        ("you", "NP", "subject-phrase", {}),
        ("please", "V", "lexical", {"vform": "finite", "polite_formula": "true"}),
    ))
    mark("QMARK", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


APPREHENSIVE_GAZE = "structural_shared_subject_apprehension_and_gaze_with_possessive_reference"
_GAZE = re.compile(
    r"(?P<subject>I|He|She|We|They|You) +(?P<felt>felt) +(?P<apprehensive>apprehensive|afraid|uneasy|certain) +"
    r"(?P<that>that) +(?P<involved>I|he|she|we|they|you) +(?P<be>was|were) +"
    r"(?P<scope>personally|directly|deeply) +(?P<attribute>interested|involved|concerned) +"
    r"(?P<topic>in +(?:this|that|the) +[a-z][a-z-]*), +(?P<and>and) +(?P<sought>sought) +"
    r"(?P<sought_np>(?:(?:Mr\.|Mrs\.|Dr\.|Miss) +)?[A-Z][a-z]+[’']s +(?:eye|gaze|look)) +"
    r"(?P<as>as) +(?P<it>it) +(?P<landed>lighted|fell|settled|rested) +(?P<on>on|upon) +"
    r"(?P<possessor>mine|yours|his|hers|ours|theirs)(?P<stop>[.!])"
)


def plan_apprehensive_gaze(text, components):
    m = _GAZE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if (m["be"] == "was") != (m["involved"] in _WAS):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("felt", "V", "lexical-alternatives", _v("finite", "linking", lemma_in="feel")),
        ("apprehensive", "ADJ", "lexical", {}),
        ("that", "COMP-THAT", "lexical", {}),
        ("involved", "NP", "subject-phrase", {}),
        ("be", "COPULA", "lexical", {"vform": "finite",
          "number": "singular" if m["be"] == "was" else "plural"} if m["involved"] != "you" else
         {"vform": "finite", "person": "2"}),
        ("scope", "ADV", "lexical", {}),
        ("attribute", "ADJ", "lexical", {}),
        ("topic", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("COMMA", m.end("topic"), m.end("topic") + 1)
    part(m, 0, (
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("sought", "V", "lexical-alternatives", _v("finite", "transitive", lemma_in="seek")),
        ("sought_np", "NP", "phrase", {"proof_rule": "np_genitive"}),
        ("as", "CONJ", "lexical", {"simultaneous": "true"}),
        ("it", "PRONOUN", "lexical", {"lemma_in": "it"}),
        ("landed", "V", "lexical-alternatives", _v("finite", "intransitive", nonbase_surface="true")),
        ("on", "PREP", "lexical", {}),
        ("possessor", "POSS-PROFORM", "scoped-lexical", {"independent_possessive": "true"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


FACTIVE_GESTURE = "dialogue_structural_negated_knowledge_with_factive_all_and_gesture"
_FACTIVE = re.compile(
    r"(?P<speaker>I|We) +(?P<do>do)(?P<not>n[’']t) +(?P<know>know|remember) +(?P<all>all) +"
    r"(?P<actor>I|we|you|they) +(?P<have>have|had) +(?P<done>done|said|written|made), +"
    r"(?P<circumstance>in +(?:my|our|your|their) +[a-z][a-z-]*)"
)
_FACTIVE_REPORT = re.compile(
    r"(?P<report>said|remarked|replied) +(?P<speaker>(?:Mr\.|Mrs\.|Dr\.|Miss) +[A-Z][a-z]+), +"
    r"(?P<gesture>putting|holding|stretching) +(?P<out>out) +(?P<body>(?P<poss>his|her|their) +(?P<body_n>hands|arms)), +"
    r"(?P<as>as) +(?P<if>if) +(?P<to>to) +(?P<purpose>deprecate|prevent|forestall|avoid) +"
    r"(?P<target>(?:my|your|his|her|our|their|the) +[a-z][a-z-]*)"
)


def plan_factive_gesture(text, components):
    scope = _single_spoken_span(text, components, reported=True)
    if scope is None or text[scope[0]] != ",":
        return None
    stop, reporter = scope
    speech = _FACTIVE.fullmatch(text[1:stop])
    base = reporter["start"]
    tag = _FACTIVE_REPORT.fullmatch(text[base:reporter["end"]])
    if speech is None or tag is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(speech, 1, (
        ("speaker", "NP", "subject-phrase", {}),
        ("do", "AUX", "lexical", {"vform": "finite"}),
        ("not", "NEG", "lexical", {"negation": "true"}),
        ("know", "V", "lexical-alternatives", _v("base", "transitive")),
        ("all", "PRONOUN", "lexical", {"anaphor": "false"}),
        ("actor", "NP", "subject-phrase", {}),
        ("have", "HAVE", "lexical", {"vform": "finite"}),
        ("done", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("circumstance", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("COMMA", 1 + speech.end("done"), 2 + speech.end("done"))
    mark("COMMA", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    part(tag, base, (
        ("report", "V", "lexical-alternatives", _v("finite", "clausal", nonbase_surface="true")),
        ("speaker", "NP", "proper-phrase", {}),
        ("gesture", "V", "lexical-alternatives", _v("ing", "transitive", lemma_in="put|hold|stretch")),
        ("out", "PARTICLE", "lexical", {}),
        ("poss", "POSS", "lexical", {}),
        ("body_n", "N", "lexical", {"number": "plural"}),
        ("as", "CONJ", "lexical", {"degree": "true"}),
        ("if", "CONJ", "lexical", {"complementizer": "conditional"}),
        ("to", "TO", "lexical", {}),
        ("purpose", "V", "lexical-alternatives", _v("base", "transitive")),
        ("target", "NP", "phrase", {"simple_nominal_proof": "true"}),
    ))
    for name in ("speaker", "body"):
        pos = base + tag.end(name)
        mark("COMMA", pos, pos + 1)
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return sorted(specs, key=lambda spec: spec[1])


CLOCK_STATUS = "structural_clock_time_relative_and_reflexive_status_report"
_CLOCK_STATUS = re.compile(
    r"(?P<discourse>So|Thus|Accordingly), +(?P<at>at) +"
    r"(?P<hour>one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) +(?P<clock>o[’']clock) +"
    r"(?P<period>(?:that|this) +(?P<period_n>evening|afternoon|morning)), +"
    r"(?P<which>which) +(?P<be>was|is) +(?P<one>one) +(?P<of>of) +(?P<the>the) +"
    r"(?P<timing>early|late|regular) +(?P<class>[a-z][a-z-]*) +(?P<collection>evenings|afternoons|mornings), +"
    r"(?P<subject>I|he|she|we|you|they) +(?P<report>announced|presented|declared) +"
    r"(?P<self>myself|himself|herself|ourselves|yourself|themselves) +(?P<as>as) +"
    r"(?P<status>ready|available|prepared|willing), +(?P<to>to) +(?P<addressee>[A-Z][a-z]+)(?P<stop>[.!])"
)


def plan_clock_status(text, components):
    m = _CLOCK_STATUS.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    selves = {"I": "myself", "he": "himself", "she": "herself", "we": "ourselves", "you": "yourself",
              "they": "themselves"}
    if selves[m["subject"]] != m["self"] or m["period_n"] + "s" != m["collection"]:
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("discourse", "ADV", "lexical", {}),
        ("at", "PREP", "lexical", {"lemma_in": "at"}),
        ("hour", "NUM", "lexical", {}),
        ("clock", "ADV", "lexical", {}),
        ("period", "NP", "phrase", {"proof_rule": "np_det_n", "definiteness": "demonstrative"}),
        ("which", "WH-REL-OBL", "lexical", {"relative": "true"}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("one", "NUM", "lexical", {}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("the", "DET", "lexical", {"definiteness": "definite", "number": "plural"}),
        ("timing", "ADJ", "lexical", {}),
        ("class", "N", "lexical", {"number": "singular"}),
        ("collection", "N", "lexical", {"number": "plural"}),
        ("subject", "NP", "subject-phrase", {}),
        ("report", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("self", "EMPHATIC-REFLEXIVE", "lexical", {"reflexive": "true"}),
        ("as", "PREP", "lexical", {"lemma_in": "as"}),
        ("status", "ADJ", "lexical", {}),
        ("to", "PREP", "lexical", {"lemma_in": "to"}),
        ("addressee", "NP", "proper-phrase", {}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    for name in ("discourse", "period", "collection", "status"):
        mark("COMMA", m.end(name), m.end(name) + 1)
    return sorted(specs, key=lambda spec: spec[1])


GENITIVE_WHERE = "structural_referential_locative_independent_genitive_where_relative"
_GENITIVE_WHERE = re.compile(
    r"(?P<it>It) +(?P<was>was|is) +(?P<at>at) +(?P<title>Sir|Lady|Lord|Doctor) +"
    r"(?P<given>[A-Z][a-z]+) +(?P<surname>[A-Z][a-z]+)(?P<poss>[’']s), +"
    r"(?P<where>where) +(?P<group>(?:a|the) +(?:large|small|considerable|little) +"
    r"(?P<group_head>party|crowd|company|committee|group)) +"
    r"(?P<be>were|was|are|is) +(?P<gathered>assembled|gathered|convened)(?P<stop>[.!])"
)


def plan_genitive_where(text, components):
    m = _GENITIVE_WHERE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    # British notional agreement licenses plural BE with the collective
    # nominal here. No wider relaxation of third-person agreement is made.
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("it", "PRONOUN", "lexical", {"lemma_in": "it"}),
        ("was", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("at", "PREP", "lexical", {"lemma_in": "at"}),
        ("title", "TITLE", "lexical", {"honorific": "true"}),
        ("given", "PROPER-NOUN", "lexical", {}),
        ("surname", "PROPER-NOUN", "lexical", {}),
        ("poss", "POSS", "lexical", {"genitive_clitic": "true"}),
        ("where", "WH-NOM", "lexical", {"wh_adverbial": "true"}),
        ("group", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("be", "AUX-BE", "lexical", {"vform": "finite", "number": "plural" if m["be"] in ("were", "are") else "singular"}),
        ("gathered", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    comma = m.end("poss")
    mark("COMMA", comma, comma + 1)
    return sorted(specs, key=lambda spec: spec[1])


ANTICIPATORY_MEANS = "structural_semicolon_temporal_evaluation_with_controlled_means"
_ANTICIPATION = re.compile(
    r"(?P<disc>So|Thus|Indeed), +(?P<period>the +(?:close|end|beginning|start) +of +"
    r"(?:every|each|the) +(?:week|month|day|year)) +(?P<be>was|is) +"
    r"(?P<evaluation>a +(?:delicious|pleasant|happy|welcome|delightful|joyful) +time) +"
    r"(?P<for>for +(?:me|him|her|us|them|you)); +(?P<and>and) +"
    r"(?P<subject>I|he|she|we|they|you) +(?P<get>got|passed|went) +"
    r"(?P<through>through) +(?P<remainder>the +rest +of +the +(?:week|month|day|year)) +"
    r"(?P<by>by) +(?P<look>looking) +(?P<forward>forward) +"
    r"(?P<target>to +(?:it|him|her|them|the +[a-z][a-z-]*))(?P<stop>[.!])"
)


def plan_anticipatory_means(text, components):
    m = _ANTICIPATION.fullmatch(text)
    if m is None or any(c.get("function") == "direct_speech" for c in components):
        return None
    spans = {(c.get("start"), c.get("end")) for c in components if c.get("id") in {"s0", "s1"}}
    if spans != {(0, m.end("for")), (m.start("and"), len(text))}:
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("disc", "ADV", "lexical", {}),
        ("period", "NP", "phrase", {"proof_rule": "np_det_n_of"}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("evaluation", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("for", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("subject", "NP", "subject-phrase", {}),
        ("get", "V", "lexical-alternatives", _v("finite", "prepositional", nonbase_surface="true")),
        ("through", "PREP", "lexical", {"lemma_in": "through"}),
        ("remainder", "NP", "phrase", {"proof_rule": "np_det_n_of"}),
        ("by", "PREP-BY", "lexical", {"lemma_in": "by"}),
        ("look", "V", "lexical-alternatives", _v("ing", "prepositional", lemma_in="look")),
        ("forward", "ADV", "lexical", {"lemma_in": "forward"}),
        ("target", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    mark("COMMA", m.end("disc"), m.end("disc") + 1)
    mark("SEMICOLON", m.end("for"), m.end("for") + 1)
    return sorted(specs, key=lambda spec: spec[1])


EMOTIVE_REBUKE = "structural_emotive_perfect_relative_with_rebuke_reason"
_REBUKE = re.compile(
    r"(?P<subject>(?:(?:Miss|Mr\.|Mrs\.|Dr\.) +)?[A-Z][a-z]+) +"
    r"(?P<manner>warmly|bitterly|deeply|strongly) +(?P<resented>resented|regretted|deplored) +"
    r"(?P<offense>the +(?:indignity|insult|offense|injury)) +(?P<recipient>he|she|they|we|you|I) +"
    r"(?P<had>had) +(?P<received>received|suffered|endured), +(?P<in>in) +"
    r"(?P<rebuke>an? +(?:expostulation|argument|altercation|discussion|dispute)) +"
    r"(?P<interlocutor>with +(?:her|his|their|my|your|the) +[a-z][a-z-]*) +"
    r"(?P<for>for) +(?P<talk>talking|speaking|writing) +(?P<such>such) +"
    r"(?P<words>nonsense|rubbish|trash)(?P<stop>[.!])"
)


def plan_emotive_rebuke(text, components):
    m = _REBUKE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "proper-phrase", {}),
        ("manner", "ADV", "lexical", {}),
        ("resented", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("offense", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("recipient", "NP", "subject-phrase", {}),
        ("had", "HAVE", "lexical", {"vform": "finite"}),
        ("received", "V", "lexical-alternatives", _v("ed", "transitive")),
    ))
    mark("COMMA", m.end("received"), m.end("received") + 1)
    part(m, 0, (
        ("in", "PREP", "lexical", {"lemma_in": "in"}),
        ("rebuke", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("interlocutor", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("for", "PREP", "lexical", {"lemma_in": "for"}),
        ("talk", "V", "lexical-alternatives", _v("ing", "transitive")),
        ("such", "DEGREE", "lexical", {}),
        ("words", "N", "lexical", {"number": "singular"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


CONCESSIVE_AFFECT = "structural_reduced_concessive_and_affective_subject_supplement"
_CONCESSIVE_AFFECT = re.compile(
    r"(?P<subject>(?:(?:Mr\.|Mrs\.|Dr\.|Miss) +)?[A-Z][a-z]+), +"
    r"(?P<all>all) +(?P<affect>amazement|astonishment|surprise|confusion), +"
    r"(?P<though>though|although) +(?P<flattered>flattered|honoured|honored|pleased) +"
    r"(?P<by>by) +(?P<having>having) +(?P<det>a|an) +(?P<guest>guest|visitor|companion) +"
    r"(?P<of>of) +(?P<such>such) +(?P<attribute>high|great|considerable) +"
    r"(?P<importance>importance|rank|distinction), +"
    r"(?P<received>received|welcomed|greeted) +(?P<person>him|her|them|us) +"
    r"(?P<manner>with +the +(?:utmost|greatest) +(?:politeness|courtesy|respect|kindness))(?P<stop>[.!])"
)


def plan_concessive_affect(text, components):
    m = _CONCESSIVE_AFFECT.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "proper-phrase", {}),
        ("all", "ADV", "lexical", {"lemma_in": "all"}),
        ("affect", "N", "lexical", {"number": "singular"}),
        ("though", "CONJ", "lexical", {"concessive": "true"}),
        ("flattered", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("by", "PREP-BY", "lexical", {}),
        ("having", "V", "lexical-alternatives", _v("ing", "transitive", lemma_in="have")),
        ("det", "DET", "lexical", {"number": "singular"}),
        ("guest", "N", "lexical", {"number": "singular"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("such", "DEGREE", "lexical", {}),
        ("attribute", "ADJ", "lexical", {}),
        ("importance", "N", "lexical", {"number": "singular"}),
        ("received", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("person", "PRONOUN", "lexical", {"case": "accusative"}),
        ("manner", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    for name in ("subject", "affect", "importance"):
        mark("COMMA", m.end(name), m.end(name) + 1)
    return sorted(specs, key=lambda spec: spec[1])


DISPATCH_PURPOSES = "structural_dispatch_with_two_subject_controlled_purposes"
_DISPATCH = re.compile(
    r"(?P<subject>[A-Z][a-z]+) +(?P<degree>most|very) +(?P<manner>[a-z]+ly) +"
    r"(?P<consent>consented|agreed|assented), +(?P<and>and) +"
    r"(?P<messenger>(?:an?|the) +[a-z][a-z-]*) +(?P<be>was|is) +"
    r"(?P<sent>dispatched|sent) +(?P<destination>to +[A-Z][a-z]+) +(?P<to>to) +"
    r"(?P<acquaint>acquaint|familiarize|familiarise) +(?P<informed>the +[a-z][a-z-]*) +"
    r"(?P<topic>with +(?:his|her|their|our|the) +[a-z][a-z-]*) +(?P<and2>and) +"
    r"(?P<bring>bring|carry|take) +(?P<back>back) +(?P<material>(?:a|the) +"
    r"(?:supply|bundle|load|parcel) +of +[a-z][a-z-]*)(?P<stop>[.!])"
)


def plan_dispatch_purposes(text, components):
    m = _DISPATCH.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    mark("COMMA", m.end("consent"), m.end("consent") + 1)
    part(m, 0, (
        ("subject", "PROPER-NOUN", "lexical", {}),
        ("degree", "ADV", "lexical", {}),
        ("manner", "ADV", "lexical", {}),
        ("consent", "V", "scoped-lexical", _v("finite", "intransitive", nonbase_surface="true")),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("messenger", "NP", "phrase", {"proof_rule": "np_det_n", "number": "singular"}),
        ("be", "AUX-BE", "lexical", {"vform": "finite", "number": "singular"}),
        ("sent", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("destination", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("to", "TO", "lexical", {}),
        ("acquaint", "V", "lexical-alternatives", _v("base", "prep_ditransitive")),
        ("informed", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("topic", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("and2", "COORD", "lexical", {"lemma_in": "and"}),
        ("bring", "V", "lexical-alternatives", _v("base", "transitive")),
        ("back", "PARTICLE", "lexical", {}),
        ("material", "NP", "phrase", {"proof_rule": "np_det_n_of"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return sorted(specs, key=lambda spec: spec[1])


MODAL_GERUND_CONTRAST = "structural_shared_subject_modal_gerund_contrasted_with_reactive_progressive"
_HARDLY_HELP = re.compile(
    r"(?P<subject>[A-Z][a-z]+) +(?P<could>could|can) +(?P<hardly>hardly|scarcely) +(?P<help>help) +"
    r"(?P<reaction>laughing|smiling|staring) +(?P<at>at) +"
    r"(?P<so>so) +(?P<adjective>[a-z][a-z-]*) +(?P<a>a|an) +(?P<stimulus>[a-z][a-z-]*); +"
    r"(?P<yet>yet) +(?P<was>was|is) +(?P<intensity>really|quite|deeply|very) +"
    r"(?P<vexed>vexed|angry|upset|annoyed|troubled) +(?P<that>that) +"
    r"(?P<agent>(?:her|his|their|the) +[a-z][a-z-]*) +(?P<modal>should|would) +"
    r"(?P<be>be) +(?P<always>always|constantly|continually) +(?P<giving>giving|offering) +"
    r"(?P<recipient>him|her|them|me|us) +(?P<such>such) +(?P<det>a|an) +"
    r"(?P<epithet>[a-z][a-z-]*)(?P<stop>[.!])"
)


def plan_modal_gerund_contrast(text, components):
    m = _HARDLY_HELP.fullmatch(text)
    if m is None or any(c.get("function") == "direct_speech" for c in components):
        return None
    spans = {(c.get("start"), c.get("end")) for c in components if c.get("id") in {"s0", "s1"}}
    if spans != {(0, m.end("stimulus")), (m.start("yet"), len(text))}:
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "PROPER-NOUN", "lexical", {}),
        ("could", "MODAL", "lexical", {"vform": "finite"}),
        ("hardly", "ADV", "lexical", {}),
        ("help", "V", "lexical-alternatives", _v("base", "gerund_complement")),
        ("reaction", "V", "lexical-alternatives", _v("ing", "prepositional")),
        ("at", "PREP", "lexical", {"lemma_in": "at"}),
        ("so", "DEGREE", "lexical", {"prenominal_indefinite_degree": "true"}),
        ("adjective", "ADJ", "lexical", {}),
        ("a", "DET", "lexical", {"number": "singular"}),
        ("stimulus", "N", "lexical", {"number": "singular"}),
        ("yet", "COORD", "lexical", {"adversative": "true"}),
        ("was", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("intensity", "ADV", "lexical", {}),
        ("vexed", "ADJ", "lexical", {}),
        ("that", "COMP-THAT", "lexical", {}),
        ("agent", "NP", "subject-phrase", {}),
        ("modal", "MODAL", "lexical", {"vform": "finite"}),
        ("be", "AUX-BE", "lexical", {"lemma_in": "be"}),
        ("always", "ADV", "lexical", {}),
        ("giving", "V", "lexical-alternatives", _v("ing", "ditransitive")),
        ("recipient", "PRONOUN", "lexical", {"case": "accusative"}),
        ("such", "DEGREE", "lexical", {}),
        ("det", "DET", "lexical", {"number": "singular"}),
        ("epithet", "N", "lexical", {"number": "singular"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    mark("SEMICOLON", m.end("stimulus"), m.end("stimulus") + 1)
    return sorted(specs, key=lambda spec: spec[1])


DOCUMENT_RELATIVE = "structural_fronted_motion_to_document_part_with_passive_locative_relative"
_DOCUMENT_RELATIVE = re.compile(
    r"(?P<when>When) +(?P<reader>I|he|she|we|they|you) +(?P<came>came|went|returned) +(?P<to>to) +"
    r"(?P<part>(?:that|this) +(?:part|section|passage)) +(?P<of>of) +"
    r"(?P<document>the +(?:letter|book|report|account)) +(?P<in>in) +(?P<which>which) +"
    r"(?P<group>(?:her|his|my|our|their|the) +(?:family|household|company|party)) +"
    r"(?P<be>was|were) +(?P<mentioned>mentioned|described|discussed) +"
    r"(?P<in2>in) +(?P<terms>terms) +(?P<of2>of) +(?P<such>such) +(?P<adj1>[a-z][a-z-]*), +"
    r"(?P<yet>yet) +(?P<adj2>[a-z][a-z-]*) +(?P<reproach>reproach|criticism|censure), +"
    r"(?P<affect>(?:her|his|my|our|their) +sense) +(?P<of3>of) +"
    r"(?P<specific>shame|guilt|embarrassment|humiliation) +(?P<was>was|is) +"
    r"(?P<state>severe|acute|intense|strong|great)(?P<stop>[.!])"
)


def plan_document_relative(text, components):
    m = _DOCUMENT_RELATIVE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if not any(c.get("function") == "adverbial_subordinate_clause"
               and c["start"] == 0 for c in components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("when", "CONJ", "lexical", {"temporal_incise": "true"}),
        ("reader", "NP", "subject-phrase", {}),
        ("came", "V", "lexical-alternatives", _v("finite", "prepositional", nonbase_surface="true")),
        ("to", "PREP", "lexical", {"lemma_in": "to"}),
        ("part", "NP", "phrase", {"proof_rule": "np_det_n", "definiteness": "demonstrative"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("document", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("in", "PREP", "lexical", {"lemma_in": "in"}),
        ("which", "WH-REL-OBL", "lexical", {"relative": "true"}),
        ("group", "NP", "phrase", {"simple_nominal_proof": "true"}),
        ("be", "AUX-BE", "lexical", {"vform": "finite", "number": "plural" if m["be"] == "were" else "singular"}),
        ("mentioned", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("in2", "PREP", "lexical", {"lemma_in": "in"}),
        ("terms", "N", "lexical", {"number": "plural"}),
        ("of2", "PREP", "lexical", {"nominal_complement": "of"}),
        ("such", "DEGREE", "lexical", {}),
        ("adj1", "ADJ", "lexical", {}),
        ("yet", "COORD", "lexical", {"adversative": "true"}),
        ("adj2", "ADJ", "lexical", {}),
        ("reproach", "N", "lexical", {"number": "singular"}),
        ("affect", "NP", "phrase", {"proof_rule": "np_poss", "number": "singular"}),
        ("of3", "PREP", "lexical", {"nominal_complement": "of"}),
        ("specific", "N", "lexical", {"number": "singular"}),
        ("was", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("state", "ADJ", "lexical", {}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    for name in ("adj1", "reproach"):
        mark("COMMA", m.end(name), m.end(name) + 1)
    return sorted(specs, key=lambda spec: spec[1])


PURPOSE_THEN = "structural_shared_subject_purpose_then_finite_sequence"
_PURPOSE_THEN = re.compile(
    r"(?P<subject>I|He|She|We|They|You) +(?P<paused>paused|stopped|waited) +"
    r"(?P<to>to) +(?P<collect>collect|compose|steady|prepare) +"
    r"(?P<self>myself|himself|herself|ourselves|themselves|yourself) +(?P<and>and) +"
    r"(?P<then>then) +(?P<entered>entered|crossed|approached|left) +"
    r"(?P<destination>the +[a-z][a-z-]*)(?P<stop>[.!])"
)
_REFLEXIVES = {"I": "myself", "he": "himself", "she": "herself", "we": "ourselves",
              "you": "yourself", "they": "themselves"}


def plan_purpose_then(text, components):
    m = _PURPOSE_THEN.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    person = "I" if m["subject"] == "I" else m["subject"].casefold()
    if _REFLEXIVES[person] != m["self"]:
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("paused", "V", "lexical-alternatives", _v("finite", "intransitive", nonbase_surface="true")),
        ("to", "TO", "lexical", {}),
        ("collect", "V", "lexical-alternatives", _v("base", "transitive")),
        ("self", "EMPHATIC-REFLEXIVE", "lexical", {"reflexive": "true"}),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("then", "ADV", "lexical", {"lemma_in": "then"}),
        ("entered", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("destination", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


RECALL_PROGRESSIVE = "structural_imperative_recall_with_negated_progressive_content"
_RECALL = re.compile(
    r"(?P<remember>Remember|Recall), +(?P<subject>I|he|she|we|they|you) +(?P<am>am|is|are|was|were) +"
    r"(?P<not>not) +(?P<recording>recording|describing|reporting|writing) +"
    r"(?P<object>the +[a-z][a-z-]* +of +(?:a|an|the) +[a-z][a-z-]*)(?P<stop>[.!])"
)


def plan_recall_progressive(text, components):
    m = _RECALL.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    agreement = {"I": {"am", "was"}, "he": {"is", "was"}, "she": {"is", "was"},
                 "you": {"are", "were"}, "we": {"are", "were"}, "they": {"are", "were"}}
    if m["am"] not in agreement[m["subject"]]:
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (("remember", "V", "lexical-alternatives", _v("base", "clausal")),))
    mark("COMMA", m.end("remember"), m.end("remember") + 1)
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("am", "COPULA", "lexical-alternatives", {"vform": "finite"}),
        ("not", "NEG", "lexical", {"negation": "true"}),
        ("recording", "V", "lexical-alternatives", _v("ing", "transitive")),
        ("object", "NP", "phrase", {"proof_rule": "np_det_n_of"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


TEMPORAL_SHARED_MODAL = "structural_fronted_temporal_with_shared_modal_and_infinitival_control"
_WHEN_MODAL = re.compile(
    r"(?P<when>When) +(?P<time_subject>reason|courage|hope|strength|clarity|calm) +"
    r"(?P<returned>returned|came|failed), +(?P<subject>I|he|she|we|they|you) +"
    r"(?P<modal>would|could|might) +(?P<first>remonstrate|protest|object|explain) +"
    r"(?P<and>and) +(?P<second>endeavour|endeavor|try|attempt) +(?P<to>to) +"
    r"(?P<action>inspire|encourage|move|persuade) +(?P<affected>me|him|her|them|us) +"
    r"(?P<oblique>with +(?:(?:a|the) +)?[a-z][a-z-]*)(?P<stop>[.!])"
)


def plan_temporal_shared_modal(text, components):
    m = _WHEN_MODAL.fullmatch(text)
    if m is None or not _matrix(text, components) or not any(
        c.get("function") == "adverbial_subordinate_clause"
        and (c["start"], c["end"]) == (0, m.end("returned")) for c in components
    ):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("when", "CONJ", "lexical", {"temporal_incise": "true"}),
        ("time_subject", "NP", "subject-phrase", {}),
        ("returned", "V", "lexical-alternatives", _v("finite", "intransitive", nonbase_surface="true")),
    ))
    mark("COMMA", m.end("returned"), m.end("returned") + 1)
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("modal", "MODAL", "lexical", {"vform": "finite"}),
        ("first", "V", "scoped-lexical", _v("base", "intransitive")),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("second", "V", "lexical-alternatives", _v("base", "subject_control")),
        ("to", "TO", "lexical", {}),
        ("action", "V", "scoped-lexical", _v("base", "prep_ditransitive")),
        ("affected", "PRONOUN", "lexical", {"case": "accusative"}),
        ("oblique", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


INTERPOSED_MANNER = "structural_fronted_temporal_transitive_with_interposed_manner"
_INTERPOSED_MANNER = re.compile(
    r"(?P<while>While) +(?P<observer>(?:my|his|her|their|our|the) +[a-z][a-z-]*) +"
    r"(?P<observed_v>contemplated|examined|observed|considered) +"
    r"(?P<manner>with +an? +[a-z][a-z-]* +and +[a-z][a-z-]* +(?:spirit|mind|mood|air)) +"
    r"(?P<observed>the +[^,;.!?]{2,55} +of +[a-z][a-z-]*), +"
    r"(?P<subject>I|he|she|we|they|you) +(?P<delighted>delighted|rejoiced) +(?P<in>in) +"
    r"(?P<activity>investigating|exploring|considering|discussing) +"
    r"(?P<goal>(?:their|his|her|my|our|the) +[a-z][a-z-]*)(?P<stop>[.!])"
)


def plan_interposed_manner(text, components):
    m = _INTERPOSED_MANNER.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("while", "CONJ", "lexical", {"lemma_in": "while"}),
        ("observer", "NP", "subject-phrase", {}),
        ("observed_v", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("manner", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("observed", "NP", "phrase", {"proof_rule": "np_det_n_of"}),
    ))
    mark("COMMA", m.end("observed"), m.end("observed") + 1)
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("delighted", "V", "lexical-alternatives", _v("finite", "prepositional", nonbase_surface="true")),
        ("in", "PREP", "lexical", {"lemma_in": "in"}),
        ("activity", "V", "lexical-alternatives", _v("ing", "transitive")),
        ("goal", "NP", "phrase", {"simple_nominal_proof": "true"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


PERFECT_LOCATED_MOTION = "structural_perfect_motion_with_locative_modifier_of_destination"
_PERFECT_MOTION = re.compile(
    r"(?P<subject>[A-Z][a-z]+) +(?P<had>had) +(?P<motion>hastened|hurried|rushed|raced|walked) +"
    r"(?P<to>to) +(?P<destination>the +(?:chair|bench|stool|seat)) +"
    r"(?P<location>(?:before|beside|near|by) +the +(?:fire|hearth|door|window))(?P<stop>[.!])"
)


def plan_perfect_located_motion(text, components):
    m = _PERFECT_MOTION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("subject", "NP", "proper-phrase", {}),
        ("had", "HAVE", "lexical", {"vform": "finite"}),
        ("motion", "V", "lexical-alternatives", _v("ed", "intransitive")),
        ("to", "PREP", "lexical", {"lemma_in": "to"}),
        ("destination", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("location", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


COPULAR_COMPARED_RELATIVE = "structural_copular_classification_with_comparison_and_supplementary_relative"
_COMPARED_RELATIVE = re.compile(
    r"(?P<subject>It|This|That) +(?P<be>was|is), +(?P<stance>in fact|in truth|indeed), +"
    r"(?P<classification>(?:a|an|the) +[a-z][a-z-]*(?: +[a-z][a-z-]*)?), +"
    r"(?P<like>like) +(?P<standard>that|the one) +"
    r"(?P<observer>I|he|she|we|you|they) +(?P<observed_aspect>had) +"
    r"(?P<observed>[a-z][a-z-]*) +(?P<earlier>before|earlier|previously), +"
    r"(?P<which>which) +(?P<motion_aspect>had) +(?P<motion>drifted|floated|sailed|moved|rolled) +"
    r"(?P<direction>(?:towards?|to) +(?:(?:the|a|an) +)?[a-z][a-z-]*) +"
    r"(?P<time>(?:in|during) +the +[a-z][a-z-]*) +"
    r"(?P<support>on +(?:a|an|the) +[a-z][a-z-]*(?: +[a-z][a-z-]*){0,2}(?: +of +[a-z][a-z-]*)?)"
    r"(?P<stop>[.!])"
)


def plan_copular_compared_relative(text, components):
    """Keep the comparison standard and the outer relative antecedent distinct."""
    m = _COMPARED_RELATIVE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "phrase", {"pronominal": "true"} if m["subject"] == "It" else {}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
    ))
    mark("COMMA", m.end("be"), m.end("be") + 1)
    part(m, 0, (("stance", "ADV", "lexical", {}),))
    mark("COMMA", m.end("stance"), m.end("stance") + 1)
    part(m, 0, (("classification", "NP", "phrase", {"proof_rule": "np_det_n"}),))
    mark("COMMA", m.end("classification"), m.end("classification") + 1)
    part(m, 0, (
        ("like", "PREP", "lexical", {"comparison": "true"}),
        ("standard", "NP", "phrase", {"proof_rule": "np_demonstrative" if m["standard"] == "that" else "np_det_n"}),
        ("observer", "NP", "subject-phrase", {}),
        ("observed_aspect", "HAVE", "lexical", {"vform": "finite"}),
        ("observed", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("earlier", "ADV", "lexical", {}),
    ))
    mark("COMMA", m.end("earlier"), m.end("earlier") + 1)
    part(m, 0, (
        ("which", "WH-PRONOUN", "lexical", {"wh": "true"}),
        ("motion_aspect", "HAVE", "lexical", {"vform": "finite"}),
        ("motion", "V", "lexical-alternatives", _v("ed", "intransitive")),
        ("direction", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("time", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("support", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


MODAL_PERFECT_CONCESSION = "structural_inverted_modal_perfect_concession_with_capacity_infinitive"
_PERFECT_CONCESSION = re.compile(
    r"(?P<degree>[A-Z][a-z-]+) +(?P<as>as) +(?P<modal>must|might|may|could|would) +"
    r"(?P<have>have) +(?P<be>been) +(?P<bearer>(?:my|your|his|her|their|our|the) +[a-z][a-z-]*), +"
    r"(?P<subject>[A-Z][a-z]+|he|she|they|I|you|we) +(?P<had>had) +(?P<det>the) +"
    r"(?P<capacity>strength|courage|presence) +(?P<of>of) +(?P<domain>mind|character|conviction) +"
    r"(?P<to>to) +(?P<action>[a-z][a-z-]+) +(?P<object>it|him|her|them|me|us|you)(?P<stop>[.!])"
)


def plan_modal_perfect_concession(text, components):
    """Fronted predicative adjective in a concessive as-clause, not equative as."""
    m = _PERFECT_CONCESSION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("degree", "ADJ", "lexical", {}),
        ("as", "CONJ", "lexical", {"degree": "true"}),
        ("modal", "MODAL", "lexical", {"vform": "finite"}),
        ("have", "HAVE", "lexical", {"vform": "base"}),
        ("be", "COPULA", "lexical", {"vform": "ed"}),
        ("bearer", "NP", "phrase", {"simple_nominal_proof": "true"}),
    ))
    mark("COMMA", m.end("bearer"), m.end("bearer") + 1)
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("had", "V", "lexical-alternatives", _v("finite", "transitive", lemma_in="have")),
        ("det", "DET", "lexical", {"definiteness": "definite", "number": "singular"}),
        ("capacity", "N", "lexical", {"number": "singular"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("domain", "N", "lexical", {"number": "singular"}),
        ("to", "TO", "lexical", {}),
        ("action", "V", "lexical-alternatives", _v("base", "transitive")),
        ("object", "PRONOUN", "lexical", {"reflexive": "false"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


INCISED_EXISTENTIAL_CONTENT = "structural_incised_copular_proposition_with_modal_perfect_existential"
_EXISTENTIAL_CONTENT = re.compile(
    r"(?P<subject>(?:My|His|Her|Our|Their|Your|The) +(?:impression|belief|conclusion|opinion)) +"
    r"(?P<be>is|was), +(?P<time>after +(?:many|several|some|a +few) +(?:years|months|days|hours) +"
    r"of +[a-z][a-z-]*), +(?P<that>that) +(?P<there>there) +(?P<never>never) +"
    r"(?P<modal>can|could|may|might|must) +(?P<have>have) +(?P<been>been) +"
    r"(?P<pivot>anybody|any +[a-z][a-z-]*) +(?P<domain>in +the +[a-z][a-z-]*) +"
    r"(?P<who>who) +(?P<action>[a-z][a-z-]*) +(?P<manner>worse|better)(?P<stop>[.!])"
)


def plan_incised_existential_content(text, components):
    """The proposition is the copular attribute; the relative restricts its pivot."""
    m = _EXISTENTIAL_CONTENT.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "phrase", {"number": "singular", "simple_nominal_proof": "true"}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
    ))
    mark("COMMA", m.end("be"), m.end("be") + 1)
    part(m, 0, (("time", "PP", "phrase", {"proof_rule": "pp_prep_np"}),))
    mark("COMMA", m.end("time"), m.end("time") + 1)
    part(m, 0, (
        ("that", "COMP-THAT", "lexical", {}),
        ("there", "EXPL", "lexical", {"expletive": "true"}),
        ("never", "DEGREE", "lexical", {"negation": "true"}),
        ("modal", "MODAL", "lexical", {"vform": "finite"}),
        ("have", "HAVE", "lexical", {"vform": "base"}),
        ("been", "COPULA", "lexical", {"vform": "ed"}),
        ("pivot", "NP", "phrase", {"proof_rule": "np_det_n" if " " in m["pivot"] else "np_indef_pron"}),
        ("domain", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("who", "WH-PRONOUN", "lexical", {"wh": "true"}),
        ("action", "V", "lexical-alternatives", _v("finite", "intransitive", nonbase_surface="true")),
        ("manner", "ADV", "lexical", {"manner_comparative": "true"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


FREQUENCY_CONTRAST = "structural_frequency_alternative_and_adversative_perception"
_FREQUENCY_CONTRAST = re.compile(
    r"(?P<first>Once|Twice) +(?P<or>or) +(?P<second>twice|thrice) +(?P<observer>I|we|she|he|you|they) +"
    r"(?P<modal>could|can|might|would) +(?P<perceive>[a-z][a-z-]*) +"
    r"(?P<perceived>(?:a|an|the) +[a-z][a-z-]* +[a-z][a-z-]*); +(?P<but>but) +"
    r"(?P<generalization>in +general|usually|mostly) +(?P<subject>[A-Z][a-z]+|I|we|she|he|you|they) +"
    r"(?P<manner>[a-z]+ly) +(?P<did>did) +(?P<not>not) +(?P<action>hear|listen|look|speak|answer)"
    r"(?P<stop>[.!])"
)


def plan_frequency_contrast(text, components):
    """A disjunction of frequency adverbs modifies the first of two clauses."""
    m = _FREQUENCY_CONTRAST.fullmatch(text)
    if m is None or m["first"].casefold() == m["second"]:
        return None
    spans = {(c["function"], c["start"], c["end"]) for c in components}
    if ("matrix_clause", 0, m.end("perceived")) not in spans or (
        "coordinate_clause", m.start("but"), len(text)
    ) not in spans or any(c.get("function") == "direct_speech" for c in components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("first", "ADV", "lexical", {}),
        ("or", "COORD", "lexical", {"lemma_in": "or"}),
        ("second", "ADV", "lexical", {}),
        ("observer", "NP", "subject-phrase", {}),
        ("modal", "MODAL", "lexical", {"vform": "finite"}),
        ("perceive", "V", "lexical-alternatives", _v("base", "transitive")),
        ("perceived", "NP", "phrase", {"proof_rule": "np_det_n"}),
    ))
    mark("SEMICOLON", m.end("perceived"), m.end("perceived") + 1)
    part(m, 0, (
        ("but", "COORD", "lexical", {"lemma_in": "but"}),
        ("generalization", "ADV", "lexical", {}),
        ("subject", "NP", "subject-phrase", {}),
        ("manner", "ADV", "lexical", {}),
        ("did", "AUX", "lexical", {"lemma_in": "do", "vform": "finite"}),
        ("not", "NEG", "lexical", {"negation": "true"}),
        ("action", "V", "lexical-alternatives", _v("base", "intransitive")),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


DEPICTIVE_FINITE_PURPOSE = "structural_sequential_coordination_with_depictive_and_finite_purpose"
_DEPICTIVE_PURPOSE = re.compile(
    r"(?P<subject>[A-Z][a-z]+|I|He|She|We|You|They) +(?P<received>received|accepted|acknowledged) +"
    r"(?P<object>(?:my|your|his|her|their|our|the) +[a-z][a-z-]*) +(?P<among>amongst|among) +"
    r"(?P<group>(?:the|these|those) +[a-z][a-z-]*), +(?P<and>and) +(?P<then>then), +"
    r"(?P<state>sick|tired|weary|ashamed|afraid) +(?P<cause>of +(?:the|this|that|their|his|her) +[a-z][a-z-]*), +"
    r"(?P<took>took) +(?P<refuge>refuge|shelter) +"
    r"(?P<location>in +(?:the|my|your|his|her|their|our) +(?:own +)?[a-z][a-z-]*), +"
    r"(?P<that>that) +(?P<actor>I|he|she|we|you|they) +(?P<modal>might|could) +"
    r"(?P<purpose>think|rest|sleep|reflect|read) +(?P<manner>with +[a-z][a-z-]*)(?P<stop>[.!])"
)


def plan_depictive_finite_purpose(text, components):
    """A shared subject continues across a supplement and a finite purpose."""
    m = _DEPICTIVE_PURPOSE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("received", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("object", "NP", "phrase", {"simple_nominal_proof": "true"}),
        ("among", "PREP", "scoped-lexical", {"lemma_in": "among|amongst"}),
        ("group", "NP", "phrase", {"proof_rule": "np_det_n"}),
    ))
    mark("COMMA", m.end("group"), m.end("group") + 1)
    part(m, 0, (
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("then", "ADV", "lexical", {"lemma_in": "then"}),
    ))
    mark("COMMA", m.end("then"), m.end("then") + 1)
    part(m, 0, (
        ("state", "ADJ", "lexical", {}),
        ("cause", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("COMMA", m.end("cause"), m.end("cause") + 1)
    part(m, 0, (
        ("took", "V", "lexical-alternatives", _v("finite", "transitive", lemma_in="take")),
        ("refuge", "N", "lexical", {"number": "singular"}),
        ("location", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("COMMA", m.end("location"), m.end("location") + 1)
    part(m, 0, (
        ("that", "COMP-THAT", "lexical", {}),
        ("actor", "NP", "subject-phrase", {}),
        ("modal", "MODAL", "lexical", {"vform": "finite"}),
        ("purpose", "V", "lexical-alternatives", _v("base", "intransitive")),
        ("manner", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


EMPHATIC_OBJECT_RELATIVE = "structural_emphatic_transitive_with_nominal_object_gap_relative"
_EMPHATIC_OBJECT_RELATIVE = re.compile(
    r"(?P<subject>I|He|She|They|We|You) +(?P<emphasis>indeed|certainly|really) +"
    r"(?P<verb>[a-z][a-z-]*) +(?P<object>the +[a-z][a-z-]*(?: +[a-z][a-z-]*)?) +"
    r"(?P<relative_subject>I|he|she|we|you|they) +(?P<relative_verb>[a-z][a-z-]*)(?P<stop>[.!])"
)


def plan_emphatic_object_relative(text, components):
    """Make the missing object of a restrictive relative the overt NP head."""
    m = _EMPHATIC_OBJECT_RELATIVE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("emphasis", "ADV", "lexical", {}),
        ("verb", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("object", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("relative_subject", "NP", "subject-phrase", {}),
        ("relative_verb", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


EMBEDDED_DURATION_RELATIVE = "structural_copular_event_nominal_with_embedded_relative_duration"
_EMBEDDED_DURATION_RELATIVE = re.compile(
    r"(?P<subject>This|That|It) +(?P<be>was|is) +"
    r"(?P<classification>the +(?:beginning|onset|commencement|start)) +(?P<of>of) +"
    r"(?P<antecedent>(?:a|an|the) +[a-z][a-z-]*(?: +[a-z][a-z-]*)?) +(?P<which>which|that) +"
    r"(?P<verb>confined|detained|troubled|afflicted|prevented|kept|stopped|delayed) +"
    r"(?P<affected>me|him|her|us|them|you) +"
    r"(?P<duration>for +(?:several|many|two|three|four|five|six|seven) +(?:hours|days|weeks|months|years))"
    r"(?P<stop>[.!])"
)


def plan_embedded_duration_relative(text, components):
    """Duration belongs to the relative event, whose subject is the lower NP."""
    m = _EMBEDDED_DURATION_RELATIVE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("subject", "NP", "phrase", {"proof_rule": "np_indef_pron" if m["subject"] == "It" else "np_demonstrative"}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("classification", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("antecedent", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("which", "WH-PRONOUN", "lexical", {"wh": "true"}),
        ("verb", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("affected", "PRONOUN", "lexical", {"reflexive": "false"}),
        ("duration", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


REPORTED_EXCLAMATION_VOCATIVE = "dialogue_structural_exclamation_with_vocative_and_attribution"
_EXCLAMATION_VOCATIVE = re.compile(r"(?P<outcry>Oh|Ah|Alas), +(?P<addressee>[A-Z][a-z]+)")
_EXCLAMATION_REPORT = re.compile(r"(?P<report>said|cried|exclaimed|shouted) +(?P<speaker>he|she|[A-Z][a-z]+)")


def plan_reported_exclamation_vocative(text, components):
    """An emotional interjection and a vocative, not a nominal exclamation."""
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None:
        return None
    stop, reporter = evidence
    m = _EXCLAMATION_VOCATIVE.fullmatch(text[1:stop])
    r = _EXCLAMATION_REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None or text[stop] != "!":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (("outcry", "INTERJECTION", "scoped-lexical", {"exclamative": "true"}),))
    mark("COMMA", 1 + m.end("outcry"), 2 + m.end("outcry"))
    part(m, 1, (("addressee", "NP", "proper-phrase", {}),))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    part(r, reporter["start"], (
        ("report", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "say|cry|exclaim|shout"}),
        ("speaker", "NP", "subject-phrase", {}),
    ))
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs


QUOTED_NEGATIVE_REPRISE = "dialogue_structural_negative_response_with_degree_reprise"
_NEGATIVE_REPRISE = re.compile(r"(?P<response>No), +(?P<neg>not) +(?P<degree>at +all|in +the +least|by +any +means)")


def plan_quoted_negative_reprise(text, components):
    """Preserve both the answer particle and its intensified negative reprise."""
    evidence = _single_spoken_span(text, components)
    if evidence is None:
        return None
    stop, _ = evidence
    m = _NEGATIVE_REPRISE.fullmatch(text[1:stop])
    if m is None or text[stop] not in ".!" or not any(c.get("function") == "minor_utterance" for c in components):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (("response", "RESPONSE", "scoped-lexical", {"polarity": "negative"}),))
    mark("COMMA", 1 + m.end("response"), 2 + m.end("response"))
    part(m, 1, (("neg", "NEG", "lexical", {"negation": "true"}), ("degree", "ADV", "lexical", {})))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


REPORTED_MODAL_CONFIRMATION = "dialogue_structural_reported_negative_modal_confirmation_question"
_MODAL_CONFIRMATION = re.compile(
    r"(?P<subject>I|You|We|They|He|She|It) +(?P<modal>wo|could|would|should|might|must|need)"
    r"(?P<neg>n['’]t) +(?P<predicate>[a-z][a-z-]*)"
)
_MANNER_REPORT = re.compile(
    r"(?P<speaker>I|he|she|we|they|you|[A-Z][a-z]+) +(?P<report>inquired|asked|whispered|replied) +(?P<manner>[a-z]+ly)"
)


def plan_reported_modal_confirmation(text, components):
    """Keep negative modal contraction and its reporter in separate clauses."""
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None:
        return None
    stop, reporter = evidence
    m = _MODAL_CONFIRMATION.fullmatch(text[1:stop])
    r = _MANNER_REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None or text[stop] != "?":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("subject", "NP", "subject-phrase", {}),
        ("modal", "MODAL", "scoped-lexical", {"vform": "finite", "modal": "true"}),
        ("neg", "NEG", "lexical", {"negation": "true"}),
        ("predicate", "V", "lexical-alternatives", _v("base", "intransitive")),
    ))
    mark("QMARK", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    part(r, reporter["start"], (
        ("speaker", "NP", "subject-phrase", {}),
        ("report", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "inquire|ask|whisper|reply"}),
        ("manner", "ADV", "lexical", {}),
    ))
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs


REPORT_COPULAR_ELLIPSIS = "structural_reported_copular_ellipsis_with_reporting_manner"
_REPORT_COPULAR_ELLIPSIS = re.compile(
    r"(?P<subject>[A-Z][a-z]+|I|He|She|They|We|You) +(?P<report>replied|answered|responded|remarked) +"
    r"(?P<degree>very|quite|most) +(?P<manner>[a-z]+ly) +(?P<that>that) +"
    r"(?P<embedded>I|he|she|it|you|we|they) +(?P<copula>was|were|am|is|are)(?P<stop>[.!])"
)


def plan_report_copular_ellipsis(text, components):
    """Report manner scopes outside the that-clause and its unrecovered predicate."""
    m = _REPORT_COPULAR_ELLIPSIS.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if m["copula"] not in _COPULAR_AGREEMENT[m["embedded"]]:
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("report", "V", "lexical-alternatives", _v("finite", "clausal", nonbase_surface="true")),
        ("degree", "DEGREE", "lexical", {}),
        ("manner", "ADV", "lexical", {}),
        ("that", "COMP-THAT", "lexical", {}),
        ("embedded", "NP", "subject-phrase", {}),
        ("copula", "COPULA", "lexical", {"vform": "finite"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


AFFIRMATIVE_TOTALITY = "dialogue_structural_affirmative_reply_with_address_and_totality"
_AFFIRMATIVE_TOTALITY = re.compile(r"(?P<yes>Yes), +(?P<address>ma['’]am|madam|sir), +(?P<all>all)")


def plan_affirmative_totality(text, components):
    """Keep address separate from the polarity and the elliptical answer."""
    evidence = _single_spoken_span(text, components)
    if evidence is None or not any(c.get("function") == "minor_utterance" for c in components):
        return None
    stop, _ = evidence
    m = _AFFIRMATIVE_TOTALITY.fullmatch(text[1:stop])
    if m is None or text[stop] not in ".!":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (("yes", "RESPONSE", "scoped-lexical", {"polarity": "positive"}),))
    mark("COMMA", 1 + m.end("yes"), 2 + m.end("yes"))
    part(m, 1, (("address", "VOCATIVE", "scoped-lexical", {"honorific": "true"}),))
    mark("COMMA", 1 + m.end("address"), 2 + m.end("address"))
    part(m, 1, (("all", "PRONOUN", "lexical", {"lemma_in": "all"}),))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


NEGATIVE_PROPOSITIONAL_REPLY = "dialogue_structural_negative_reply_with_propositional_not"
_NEGATIVE_PROPOSITIONAL_REPLY = re.compile(
    r"(?P<no>No), +(?P<subject>I|we|they|you) +(?P<belief>believe|think|suppose|expect|hope) +(?P<not>not)"
)


def plan_negative_propositional_reply(text, components):
    """Clause-final not stands for a negative answer to preceding content."""
    evidence = _single_spoken_span(text, components)
    if evidence is None or not any(c.get("function") == "minor_utterance" for c in components):
        return None
    stop, _ = evidence
    m = _NEGATIVE_PROPOSITIONAL_REPLY.fullmatch(text[1:stop])
    if m is None or text[stop] not in ".!":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (("no", "RESPONSE", "scoped-lexical", {"polarity": "negative"}),))
    mark("COMMA", 1 + m.end("no"), 2 + m.end("no"))
    part(m, 1, (
        ("subject", "NP", "subject-phrase", {}),
        ("belief", "V", "lexical-alternatives", _v("finite", "clausal")),
        ("not", "NEG", "lexical", {"negation": "true"}),
    ))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


REPORTED_INTERJECTION = "dialogue_structural_reported_standalone_interjection"


def plan_reported_interjection(text, components):
    """An attested singleton interjection is the whole reportable speech act."""
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None:
        return None
    stop, reporter = evidence
    if text[stop] != "!" or text[1:stop].casefold() not in {"alas", "ah", "oh", "avast"}:
        return None
    r = _EXCLAMATION_REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if r is None:
        return None
    specs, add, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    add("INTERJECTION", 1, stop, "scoped-lexical", exclamative="true")
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    part(r, reporter["start"], (
        ("report", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "say|cry|exclaim|shout"}),
        ("speaker", "NP", "subject-phrase", {}),
    ))
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs


NEGATED_GRADED_RESPONSE = "structural_response_then_negated_graded_copular_predication"
_COPULAR_AGREEMENT = {"I": {"am", "was"}, "he": {"is", "was"}, "she": {"is", "was"}, "it": {"is", "was"},
                      "you": {"are", "were"}, "we": {"are", "were"}, "they": {"are", "were"}}
_NEGATED_GRADED_RESPONSE = re.compile(
    r"(?P<response>No); +(?P<subject>I|he|she|it|we|you|they) +(?P<be>am|is|are|was|were) +"
    r"(?P<neg>not) +(?P<degree>so|too|that|very) +(?P<quality>[a-z][a-z-]+)(?P<stop>[.!])"
)


def plan_negated_graded_response(text, components):
    """A separate No is elaborated by an overtly negative finite clause."""
    m = _NEGATED_GRADED_RESPONSE.fullmatch(text)
    if m is None or m["be"] not in _COPULAR_AGREEMENT[m["subject"]]:
        return None
    spans = {(c["function"], c["start"], c["end"]) for c in components}
    if ("matrix_clause", 0, m.end("response")) not in spans or (
        "independent_clause", m.start("subject"), len(text)
    ) not in spans or any(c.get("function") == "direct_speech" for c in components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (("response", "RESPONSE", "scoped-lexical", {"polarity": "negative"}),))
    mark("SEMICOLON", m.end("response"), m.end("response") + 1)
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("be", "COPULA", "lexical", {"vform": "finite"}),
        ("neg", "NEG", "lexical", {"negation": "true"}),
        ("degree", "DEGREE", "lexical", {}),
        ("quality", "ADJ", "lexical", {}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


PHONATION_PASSIVE_CAUSE = "structural_passive_phonation_with_causal_with_phrase"
_PASSIVE_PHONATION = re.compile(
    r"(?P<subject>(?:My|Her|His|Their|Our|The) +(?:voice|speech|words)) +"
    r"(?P<be>was|were) +(?P<verb>suffocated|choked|muffled|smothered|stifled) +"
    r"(?P<cause>with +(?:(?:his|her|my|their|the) +)?(?:sobs|tears|emotion|grief|weeping))(?P<stop>[.!])"
)


def plan_passive_phonation(text, components):
    """Causal with in a passive of suppressed vocal production."""
    m = _PASSIVE_PHONATION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    number = "plural" if m["subject"].endswith(" words") else "singular"
    if (m["be"] == "were") != (number == "plural"):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("subject", "NP", "phrase", {"simple_nominal_proof": "true"}),
        ("be", "AUX-BE", "lexical", {"vform": "finite", "number": number}),
        ("verb", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("cause", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs
