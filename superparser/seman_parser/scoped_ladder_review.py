"""Constituent witnesses for selected-tree repairs in the frozen novel ladder."""
from __future__ import annotations

import re

from .additional_spoken_acts import _single_spoken_span
from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _matrix, _v

RIDDEN_MEANS = "structural_transitive_travel_with_mounted_means"
TIMED_DECISION = "structural_decision_with_timed_controlled_journey"
SHARED_GAZE = "structural_shared_subject_speaking_then_expectant_gaze"
TIMED_REPORT = "structural_recipient_and_reported_future_with_day_relative"
REACTION_TIME = "structural_temporal_reaction_and_adversative_content"
NAUTICAL_CALL = "dialogue_structural_reported_nautical_call"
CERTAIN_NEGATION = "structural_epistemic_stance_with_finite_do_negation"
REACTION_DEGREE = "structural_preposed_trigger_with_graded_reaction"
REPORTED_SURE = "dialogue_structural_reported_adjectival_certainty_with_complement"
ENDED_STATE = "structural_ended_state_with_temporal_and_discourse_adjuncts"
POSSIBILITY_QUESTION = "dialogue_structural_modal_question_with_extraposed_possibility"

_PRON = r"I|We|You|He|She|They"
_LOWER_PRON = r"I|you|he|she|we|they"
_NOM = r"(?:(?:a|an|the|my|your|his|her|our|their|some|another) +)?[a-z][a-z-]+(?: +[a-z][a-z-]+){0,2}"
_NAME = r"[A-Z][a-z]+(?: +[A-Z][a-z]+)?"
_SUBJECT = rf"(?:{_PRON}|{_NAME}|(?:The|My|Our|Their) +[a-z][a-z-]+)"
_STOP = r"(?P<stop>[.!])"


def _parts(match, items, offset=0):
    specs, _, _, part = _specs()
    part(match, offset, items)
    return specs


def _marked():
    return (
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    )


_RIDDEN = re.compile(
    rf"(?P<subject>{_SUBJECT}) +(?P<action>performed|covered|completed|made|travelled|traveled) +"
    r"(?P<object>the +(?:first|second|last|next|final) +(?:part|stage|leg|stretch) +of +"
    r"(?:my|your|his|her|our|their|the) +(?:journey|trip|route|expedition|tour)) +"
    r"(?P<on>on) +(?P<mount>horseback)" + _STOP
)


def plan_ridden_means(text, components):
    m = _RIDDEN.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("subject", "NP", "subject-phrase", {}),
        ("action", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("object", "NP", "phrase", {"proof_rule": "np_det_n_of"}),
        ("on", "PREP", "lexical", {"lemma_in": "on"}),
        ("mount", "N", "lexical", {"lemma_in": "horseback"}),
        *_marked(),
    ))


_TIMED_DECISION = re.compile(
    rf"(?P<subject>{_SUBJECT}) +(?P<consequence>accordingly|therefore|then) +"
    r"(?P<decision>determined|decided|resolved) +(?P<to>to) +"
    r"(?P<action>commence|begin|start|resume) +"
    r"(?P<object>(?:my|your|his|her|our|their|the) +(?:journey|trip|march|voyage|expedition))"
    r"(?: +(?P<direction>(?:towards?|to) +(?:the +)?[A-Za-z][a-z-]+))? +"
    r"(?P<at>at) +(?:(?P<det>the) +(?P<boundary>expiration|end|close) +(?P<of>of) +"
    r"(?P<interval>(?:another|the|a) +[a-z]+)|(?P<time>dawn|noon|midnight))"
    + _STOP
)


def plan_timed_decision(text, components):
    m = _TIMED_DECISION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("consequence", "ADV", "lexical", {}),
        ("decision", "V", "scoped-lexical", _v("finite", "subject_control")),
        ("to", "TO", "lexical", {}),
        ("action", "V", "lexical-alternatives", _v("base", "transitive")),
        ("object", "NP", "phrase", {"grounded_object_proof": "true"}),
    ))
    if m["direction"] is not None:
        part(m, 0, (("direction", "PP", "phrase", {"proof_rule": "pp_prep_np"}),))
    part(m, 0, (("at", "PREP", "lexical", {"lemma_in": "at"}),))
    if m["boundary"] is not None:
        part(m, 0, (
            ("det", "DET", "lexical", {}),
            ("boundary", "N", "lexical", {"number": "singular"}),
            ("of", "PREP", "lexical", {"nominal_complement": "of"}),
            ("interval", "NP", "phrase", {}),
        ))
    else:
        part(m, 0, (("time", "N", "lexical", {"number": "singular"}),))
    part(m, 0, _marked())
    return specs


_GAZE = re.compile(
    rf"(?P<subject>{_SUBJECT}) +(?P<ended>finished|stopped|ceased) +"
    r"(?P<speaking>speaking|talking|reading|writing) +(?P<and>and) +"
    r"(?P<fixed>fixed|set|turned) +(?P<look>(?:his|her|their|my|our) +(?:look|looks|eyes|gaze)) +"
    r"(?P<target>(?:on|upon|toward|towards) +(?:me|him|her|them|us|you)) +"
    r"(?P<expecting>in) +(?P<det>the) +(?P<expectation>expectation|hope|anticipation) +"
    r"(?P<of>of) +(?P<expected>(?:a|an|the) +(?:reply|answer|response|signal))" + _STOP
)


def plan_shared_gaze(text, components):
    m = _GAZE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("subject", "NP", "subject-phrase", {}),
        ("ended", "V", "scoped-lexical", _v("finite", "gerund")),
        ("speaking", "V", "lexical-alternatives", _v("ing", "intransitive")),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("fixed", "V", "lexical-alternatives", _v("finite", "transitive")),
        ("look", "NP", "phrase", {"proof_rule": "np_poss"}),
        ("target", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("expecting", "PREP", "lexical", {"lemma_in": "in"}),
        ("det", "DET", "lexical", {}),
        ("expectation", "N", "lexical", {"number": "singular"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("expected", "NP", "phrase", {"proof_rule": "np_det_n"}),
        *_marked(),
    ))


_TIMED_REPORT = re.compile(
    rf"(?P<speaker>{_SUBJECT}) +(?P<then>then|later|previously) +(?P<told>told|informed|assured) +"
    r"(?P<recipient>me|us|him|her|them|you) +(?P<that>that) +"
    rf"(?P<actor>{_LOWER_PRON}|{_NAME}) +(?P<modal>would|should|might|could) +"
    rf"(?P<action>commence|begin|resume|finish|start|deliver|read) +(?P<object>{_NOM}) +"
    r"(?P<day>the +(?:next|following|previous) +(?:day|morning|evening|week)) +"
    r"(?P<when>when) +(?P<available>I|he|she|we|they|you) +"
    r"(?P<available_modal>would|should|could|might) +(?P<be>be) +"
    r"(?:(?P<available_at>at) +(?P<location>leisure|home)|(?P<state>free|ready|available|present))" + _STOP
)


def plan_timed_report(text, components):
    m = _TIMED_REPORT.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("speaker", "NP", "subject-phrase", {}),
        ("then", "ADV", "lexical", {}),
        ("told", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "tell|inform|assure"}),
        ("recipient", "NP", "phrase", {}),
        ("that", "COMP-THAT", "lexical", {}),
        ("actor", "NP", "subject-phrase", {}),
        ("modal", "MODAL", "lexical", {}),
        ("action", "V", "lexical-alternatives", _v("base", "transitive")),
        ("object", "NP", "phrase", {"grounded_object_proof": "true"}),
        ("day", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("when", "CONJ", "lexical", {"lemma_in": "when"}),
        ("available", "NP", "subject-phrase", {}),
        ("available_modal", "MODAL", "lexical", {}),
        ("be", "COPULA", "lexical", {"vform": "base"}),
    ))
    if m["location"] is not None:
        part(m, 0, (
            ("available_at", "PREP", "lexical", {"lemma_in": "at"}),
            ("location", "N", "lexical", {}),
        ))
    else:
        part(m, 0, (("state", "ADJ", "lexical", {}),))
    part(m, 0, _marked())
    return specs


_TEMPORAL_REACTION = re.compile(
    rf"(?P<subject>{_SUBJECT}) +(?P<reaction>shuddered|trembled|shivered|winced) +"
    r"(?P<when>when) +(?P<thinker>I|he|she|they|we|you) +(?P<cognition>thought|heard|learned|learnt) +"
    r"(?P<about>of|about) +(?P<det>the) +(?P<quality>[a-z][a-z-]+) +"
    r"(?P<effect>consequences|results|effects|risks) +(?P<of>of) +"
    r"(?P<cause>(?:my|your|his|her|our|their|the) +[a-z][a-z-]+)"
    r"(?P<comma>,) +(?P<but>but) +(?P<feeler>I|he|she|they|we|you) +"
    r"(?P<felt>felt|thought|believed|realized) +(?P<that>that) +"
    r"(?P<there>there) +(?P<existence>was|is) +(?P<pivot>some +[a-z][a-z-]+) +"
    r"(?P<context>in +(?:my|your|his|her|our|their|the) +[a-z][a-z-]+)" + _STOP
)


def plan_reaction_time(text, components):
    m = _TEMPORAL_REACTION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("subject", "NP", "subject-phrase", {}),
        ("reaction", "V", "lexical-alternatives", _v("finite", "intransitive")),
        ("when", "CONJ", "lexical", {"lemma_in": "when"}),
        ("thinker", "NP", "subject-phrase", {}),
        ("cognition", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "think|hear|learn"}),
        ("about", "PREP", "lexical", {}),
        ("det", "DET", "lexical", {}),
        ("quality", "ADJ", "lexical", {}),
        ("effect", "N", "lexical", {"number": "plural"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("cause", "NP", "phrase", {"grounded_object_proof": "true"}),
        ("comma", "COMMA", "source-punctuation", {}),
        ("but", "COORD", "lexical", {"lemma_in": "but"}),
        ("feeler", "NP", "subject-phrase", {}),
        ("felt", "V", "lexical-alternatives", _v("finite", "clausal")),
        ("that", "COMP-THAT", "lexical", {}),
        ("there", "EXPL", "lexical", {"lemma_in": "there"}),
        ("existence", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("pivot", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("context", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        *_marked(),
    ))


_CERTAIN = re.compile(
    rf"(?P<stance>Certainly|Undoubtedly|Surely|Obviously) +(?P<subject>I|he|she|we|they|you) +"
    r"(?P<did>did) +(?P<not>not) +(?P<event>[a-z][a-z-]+) +"
    rf"(?P<object>{_NOM})" + _STOP
)


def plan_certain_negation(text, components):
    m = _CERTAIN.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("stance", "ADV", "lexical", {}),
        ("subject", "NP", "subject-phrase", {}),
        ("did", "AUX", "lexical", {"vform": "finite", "lemma_in": "do"}),
        ("not", "NEG", "lexical", {"negation": "true"}),
        ("event", "V", "lexical-alternatives", _v("base", "transitive")),
        ("object", "NP", "phrase", {"grounded_object_proof": "true"}),
        *_marked(),
    ))


_REACTION_DEGREE = re.compile(
    rf"(?P<at>At) +(?P<owner>{_NAME})['’]s +(?P<quality>[a-z][a-z-]+) +"
    r"(?P<trigger>salute|greeting|remark|question|reply|warning) +(?P<subject>he|she|I|they|we|you) +"
    r"(?P<degree>somewhat|slightly|visibly|a little) +(?P<event>flushed|blushed|reddened|trembled|startled)"
    + _STOP
)


def plan_reaction_degree(text, components):
    m = _REACTION_DEGREE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, add, _, part = _specs()
    part(m, 0, (
        ("at", "PREP", "lexical", {"lemma_in": "at"}),
        ("owner", "NP", "subject-phrase", {}),
    ))
    add("POSS", m.end("owner"), m.end("owner") + 2, "lexical", genitive_clitic="true")
    part(m, 0, (
        ("quality", "ADJ", "lexical", {}),
        ("trigger", "N", "lexical", {"number": "singular"}),
        ("subject", "NP", "subject-phrase", {}),
        ("degree", "ADV", "lexical", {}),
        ("event", "V", "lexical-alternatives", _v("finite", "intransitive")),
        *_marked(),
    ))
    return specs


_ENDED = re.compile(
    rf"(?P<subject>It|The +(?>[a-z][a-z-]+)) +(?P<be>was|is) +(?P<state>over|finished|ended) +"
    r"(?P<at>at) +(?P<last>last) *(?P<comma>,) +(?P<stance>however|though)" + _STOP
)


def plan_ended_state(text, components):
    m = _ENDED.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("subject", "NP", "subject-phrase", {}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("state", "ADJ", "scoped-lexical", {"ended_state": "true"}),
        ("at", "PREP", "lexical", {"lemma_in": "at"}),
        ("last", "ADJ", "lexical", {"lemma_in": "last"}),
        ("comma", "COMMA", "source-punctuation", {}),
        ("stance", "ADV", "lexical", {}),
        *_marked(),
    ))


_QUOTED_POSSIBLE = re.compile(
    r"(?P<modal>Can|Could|Might|May) +(?P<it>it) +(?P<be>be) +"
    r"(?P<attribute>possible|likely|conceivable) +(?P<that>that) +"
    r"(?P<content>[^,;.!?]+)"
)
_NAUTICAL = re.compile(r"(?P<command>Avast|Halt|Stop)(?P<comma>,) +(?P<there>there|now)")
_REPORT = re.compile(rf"(?P<report>said|cried|shouted|answered|exclaimed|replied) +(?P<speaker>I|he|she|{_NAME})")
_QUOTED_CERTAINTY = re.compile(
    r"(?P<subject>I|He|She|They|We|You) +(?P<be>am|is|are|was|were) +"
    r"(?P<attribute>sure|certain|convinced) +(?P<of>of) +(?P<object>it|this|that)"
)
_AGREEMENT = {
    "I": {"am", "was"}, "he": {"is", "was"}, "she": {"is", "was"},
    "you": {"are", "were"}, "we": {"are", "were"}, "they": {"are", "were"},
}


def plan_possibility_question(text, components):
    evidence = _single_spoken_span(text, components)
    if evidence is None or text[evidence[0]] != "?":
        return None
    stop, _ = evidence
    m = _QUOTED_POSSIBLE.fullmatch(text[1:stop])
    if m is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("modal", "MODAL", "lexical", {}),
        ("it", "NP", "phrase", {"pronominal": "true"}),
        ("be", "COPULA", "lexical", {"vform": "base"}),
        ("attribute", "ADJ", "lexical", {}),
        ("that", "COMP-THAT", "lexical", {}),
        ("content", "CLAUSE", "phrase", {"finite_statement_proof": "true"}),
    ))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


def plan_nautical_call(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != "!":
        return None
    stop, reporter = evidence
    m = _NAUTICAL.fullmatch(text[1:stop])
    r = _REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("command", "INTERJECTION", "scoped-lexical", {"exclamative": "true"}),
        ("comma", "COMMA", "source-punctuation", {}),
        ("there", "ADV", "lexical", {}),
    ))
    return _reported_tail(specs, mark, part, text, stop, reporter, r)


def _reported_tail(specs, mark, part, text, stop, reporter, match):
    mark("COMMA" if text[stop] == "," else "SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    part(match, reporter["start"], (
        ("report", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "say|cry|shout|answer|exclaim|reply"}),
        ("speaker", "NP", "subject-phrase", {}),
    ))
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs


def plan_reported_sure(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != ",":
        return None
    stop, reporter = evidence
    m = _QUOTED_CERTAINTY.fullmatch(text[1:stop])
    r = _REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None or m["be"] not in _AGREEMENT[m["subject"] if m["subject"] == "I" else m["subject"].lower()]:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("subject", "NP", "subject-phrase", {}),
        ("be", "COPULA", "lexical", {"vform": "finite"}),
        ("attribute", "ADJ", "lexical", {}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("object", "NP", "phrase", {}),
    ))
    return _reported_tail(specs, mark, part, text, stop, reporter, r)


ALARM_INVERSION = "structural_transitive_stimulus_adversative_and_minimizer_inversion"
TOPIC_RELATIVE = "structural_repeated_speech_topic_with_local_supplementary_relative"
COORDINATED_SIGHT = "structural_coordinated_subject_with_local_passive_relative_and_raising"
STIRRED_ATTITUDE = "structural_initial_trigger_and_particle_resulting_attitude"
OATH_REPORT = "dialogue_structural_presentational_move_with_reporting_oath"

_ALARM = re.compile(
    r"(?P<poss>My|His|Her|Their|Our) +(?P<first>[a-z][a-z-]+) +(?P<and>and) +"
    r"(?P<second>[a-z][a-z-]+) +(?P<stimulus>appearance|expression|behaviour|behavior|conduct) +"
    r"(?P<caused>awoke|aroused|caused|provoked) +(?P<quality>[a-z][a-z-]+) +"
    r"(?P<response>alarm|anxiety|concern|fear)(?P<comma1>,) +(?P<but>but) +"
    r"(?P<respondent>I|he|she|they|we|you) +(?P<answered>answered|asked) +"
    r"(?P<no>no) +(?P<question>questions?)(?P<comma2>,) +(?P<scarcely>scarcely|hardly|rarely) +"
    r"(?P<did>did) +(?P<suppressed>I|he|she|they|we|you) +(?P<spoke>speak|talk|reply|answer)"
    + _STOP
)


def plan_alarm_inversion(text, components):
    m = _ALARM.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("poss", "POSS", "lexical", {"anaphor": "true"}),
        ("first", "ADJ", "lexical", {}),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("second", "ADJ", "lexical", {}),
        ("stimulus", "N", "lexical", {"number": "singular"}),
        ("caused", "V", "scoped-lexical", _v("finite", "transitive")),
        ("quality", "ADJ", "lexical", {}),
        ("response", "N", "lexical", {"number": "singular"}),
        ("comma1", "COMMA", "source-punctuation", {}),
        ("but", "COORD", "lexical", {"lemma_in": "but"}),
        ("respondent", "NP", "subject-phrase", {}),
        ("answered", "V", "lexical-alternatives", _v("finite", "transitive")),
        ("no", "DET", "lexical", {"lemma_in": "no"}),
        ("question", "N", "lexical", {}),
        ("comma2", "COMMA", "source-punctuation", {}),
        ("scarcely", "ADV", "lexical", {}),
        ("did", "AUX", "lexical", {"vform": "finite", "lemma_in": "do"}),
        ("suppressed", "NP", "subject-phrase", {}),
        ("spoke", "V", "lexical-alternatives", _v("base", "intransitive")),
        *_marked(),
    ))


_TOPIC_RELATIVE = re.compile(
    rf"(?P<speaker>{_SUBJECT}) +(?P<talked>talked|spoke) +(?P<of1>of|about) +(?P<place>{_NAME})"
    r"(?P<comma1>,) +(?P<which>which) +(?P<visitor>I|he|she|we|they|you) +"
    r"(?P<modal>would|should|might|could) +(?P<soon>soon|later|eventually) +"
    r"(?P<visit>visit|see|reach)(?P<comma2>,) +(?P<of2>of|about) +"
    rf"(?P<name1>{_NAME}) +(?P<and>and) +(?P<name2>{_NAME})(?P<semi>;) +"
    r"(?P<but>but) +(?P<stimulus>(?:these|those|his|her|their) +(?:words|remarks|comments)) +"
    r"(?P<only>only) +(?P<elicited>drew|elicited) +(?P<effect>[a-z][a-z-]+ +(?:groans|sighs|laughs)) +"
    r"(?P<from>from) +(?P<source>me|him|her|us|them|you)" + _STOP
)


def plan_topic_relative(text, components):
    m = _TOPIC_RELATIVE.fullmatch(text)
    if m is None or m["of1"] != m["of2"] or any(c.get("function") == "direct_speech" for c in components):
        return None
    if not any(c.get("function") == "matrix_clause" and c["end"] == m.start("semi") for c in components):
        return None
    if not any(c.get("function") == "coordinate_clause" and c["start"] == m.start("but") for c in components):
        return None
    return _parts(m, (
        ("speaker", "NP", "subject-phrase", {}),
        ("talked", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "talk|speak"}),
        ("of1", "PREP", "lexical", {"lemma_in": "of|about"}),
        ("place", "NP", "phrase", {"proof_rule": "np_proper"}),
        ("comma1", "COMMA", "source-punctuation", {}),
        ("which", "WH-PRONOUN", "lexical", {"wh": "true"}),
        ("visitor", "NP", "subject-phrase", {}),
        ("modal", "MODAL", "lexical", {}),
        ("soon", "ADV", "lexical", {}),
        ("visit", "V", "lexical-alternatives", _v("base", "transitive")),
        ("comma2", "COMMA", "source-punctuation", {}),
        ("of2", "PREP", "lexical", {"lemma_in": "of|about"}),
        ("name1", "NP", "phrase", {"proof_rule": "np_proper"}),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("name2", "NP", "phrase", {"proof_rule": "np_proper"}),
        ("semi", "SEMICOLON", "source-punctuation", {}),
        ("but", "COORD", "lexical", {"lemma_in": "but"}),
        ("stimulus", "NP", "subject-phrase", {}),
        ("only", "ADV", "lexical", {}),
        ("elicited", "V", "lexical-alternatives", _v("finite", "transitive")),
        ("effect", "NP", "phrase", {"proof_rule": "np_bare"}),
        ("from", "PREP", "lexical", {"lemma_in": "from"}),
        ("source", "NP", "phrase", {}),
        *_marked(),
    ))


_COORDINATED_SIGHT = re.compile(
    r"(?P<first>The +[^,;.?!]{2,40})(?P<comma1>,) +(?P<second>the +[^,;.?!]{2,35})"
    r"(?P<comma2>,) +(?P<and>and) +(?P<det>every|each) +"
    r"(?P<sight>sight|view|scene|prospect) +(?P<granted>afforded|provided|offered) +"
    r"(?P<by>by) +(?P<region>(?:these|those|the) +[^,;.?!]{2,35}) +"
    r"(?P<seem>seem|appear) +(?P<still>still) +(?P<to>to) +(?P<have>have) +"
    r"(?P<the>the) +(?P<power>power|capacity|ability) +(?P<of>of) +"
    r"(?P<elevating>elevating|lifting|raising|drawing) +"
    r"(?P<person>(?:my|his|her|our|their|your) +[a-z][a-z-]+) +"
    r"(?P<source>from +(?:the +)?[a-z][a-z-]+)" + _STOP
)


def plan_coordinated_sight(text, components):
    m = _COORDINATED_SIGHT.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("first", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("comma1", "COMMA", "source-punctuation", {}),
        ("second", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("comma2", "COMMA", "source-punctuation", {}),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("det", "DET", "lexical", {}),
        ("sight", "N", "lexical", {"number": "singular"}),
        ("granted", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("by", "PREP-BY", "lexical", {}),
        ("region", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("seem", "V", "scoped-lexical", _v("finite", "raising", lemma_in="seem|appear")),
        ("still", "ADV", "lexical", {}),
        ("to", "TO", "lexical", {}),
        ("have", "HAVE", "lexical", {"vform": "base"}),
        ("the", "DET", "lexical", {}),
        ("power", "N", "lexical", {"number": "singular"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("elevating", "V", "lexical-alternatives", _v("ing", "transitive")),
        ("person", "NP", "phrase", {"proof_rule": "np_poss"}),
        ("source", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        *_marked(),
    ))


_ATTITUDE = re.compile(
    r"(?P<but>But) +(?P<trigger>at +(?:my|your|his|her|our|their) +(?:last|first|next) +(?:words|remarks)) +"
    r"(?P<subject>I|he|she|we|they|you) +(?P<perk>perked|brightened) +(?P<up>up) +"
    r"(?P<into>into) +(?P<a>a) +(?P<kind>kind|sort) +(?P<of>of) +"
    r"(?P<quality>[a-z][a-z-]+) +(?P<state>slyness|cheerfulness|alertness|interest|animation)"
    + _STOP
)


def plan_stirred_attitude(text, components):
    m = _ATTITUDE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("but", "COORD", "lexical", {"lemma_in": "but"}),
        ("trigger", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("subject", "NP", "subject-phrase", {}),
        ("perk", "V", "lexical-alternatives", _v("finite", "intransitive")),
        ("up", "PARTICLE", "lexical", {"lemma_in": "up"}),
        ("into", "PREP", "lexical", {"lemma_in": "into"}),
        ("a", "DET", "lexical", {"number": "singular"}),
        ("kind", "N", "lexical", {"number": "singular"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("quality", "ADJ", "lexical", {}),
        ("state", "N", "lexical", {"number": "singular"}),
        *_marked(),
    ))


_PRESENTATIONAL = re.compile(r"(?P<then>Then|Well) +(?P<here>here) +(?P<goes>goes)")
_OATH_REPORT = re.compile(
    rf"{_REPORT.pattern} +(?P<with>with) +(?P<oath>(?:an|a) +(?:oath|curse|swearword))"
)


def plan_oath_report(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != "!":
        return None
    stop, reporter = evidence
    m = _PRESENTATIONAL.fullmatch(text[1:stop])
    r = _OATH_REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("then", "ADV", "lexical", {}),
        ("here", "ADV", "lexical", {}),
        ("goes", "V", "lexical-alternatives", _v("finite", "intransitive", number="singular")),
    ))
    mark("SPEECH-STOP", stop, stop+1)
    mark("CLOSE-QUOTE", stop+1, stop+2)
    part(r, reporter["start"], (
        ("report", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "say|cry|shout|answer|exclaim|reply"}),
        ("speaker", "NP", "subject-phrase", {}),
        ("with", "PREP", "lexical", {"lemma_in": "with"}),
        ("oath", "NP", "phrase", {"proof_rule": "np_det_n"}),
    ))
    mark("SPEECH-STOP", len(text)-1, len(text))
    return specs


EXCEPTED_SOUND = "structural_negative_existential_with_coordinated_pivot_and_sound_exception"
TWO_MINOR_ACTS = "dialogue_structural_reported_assurance_and_degree_evaluation"
TRIPLE_PASSIVE = "structural_semicolon_inventory_with_two_passive_states"
ADJECTIVAL_ECHO = "dialogue_structural_elliptical_adjective_question_with_vocative"
NAMED_COURT = "structural_wh_identification_of_named_court"
NAMED_VOCATIVE = "dialogue_structural_report_with_titled_vocative_and_full_name"
BELIEF_VOCATIVE = "dialogue_structural_transitive_belief_with_vocative_and_titled_reporter"
MODAL_RESTORATION = "dialogue_structural_modal_particle_restoration_with_duration"
INVERTED_EFFECT = "structural_fronted_scalar_predicate_with_inverted_effect"

_SOUND = re.compile(
    r"(?P<there>There) +(?P<be>was|is) +(?P<not>not) +(?P<first>a) +(?P<person>soul|person) +"
    r"(?P<moving>stirring|moving) +(?P<nor>nor) +(?P<second>a) +(?P<sound>sound|noise) +"
    r"(?P<except>beside|besides|except) +(?P<det>the) +(?P<noises>noise|noises|sound|sounds|rustle) +"
    r"(?P<of>of) +(?P<source>(?:the|a) +[a-z][a-z-]+)" + _STOP
)


def plan_excepted_sound(text, components):
    m = _SOUND.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("there", "EXPL", "lexical", {"expletive": "true"}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("not", "NEG", "lexical", {"negation": "true"}),
        ("first", "DET", "lexical", {"number": "singular"}),
        ("person", "N", "lexical", {"number": "singular"}),
        ("moving", "V", "lexical-alternatives", _v("ing", "intransitive")),
        ("nor", "COORD", "lexical", {"lemma_in": "nor"}),
        ("second", "DET", "lexical", {"number": "singular"}),
        ("sound", "N", "lexical", {"number": "singular"}),
        ("except", "PREP", "scoped-lexical", {"lemma_in": "beside|besides|except"}),
        ("det", "DET", "lexical", {}),
        ("noises", "N", "lexical", {}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("source", "NP", "phrase", {"proof_rule": "np_det_n"}),
        *_marked(),
    ))


_ASSURANCE = re.compile(
    r"(?P<to>To) +(?P<be>be) +(?P<sure>sure)(?P<comma>,) +(?P<address>boy|girl|sir|madam)"
    r"(?P<semi>;) +(?P<degree>quite|absolutely|entirely) +(?P<right>right|correct|true)"
)


def plan_two_minor_acts(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != ",":
        return None
    stop, reporter = evidence
    m = _ASSURANCE.fullmatch(text[1:stop])
    r = _REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("to", "TO", "lexical", {}),
        ("be", "COPULA", "lexical", {"vform": "base"}),
        ("sure", "ADJ", "lexical", {}),
        ("comma", "COMMA", "source-punctuation", {}),
        ("address", "N", "lexical", {"number": "singular"}),
        ("semi", "SEMICOLON", "source-punctuation", {}),
        ("degree", "ADV", "lexical", {}),
        ("right", "ADJ", "lexical", {}),
    ))
    return _reported_tail(specs, mark, part, text, stop, reporter, r)


_PASSIVE_INVENTORY = re.compile(
    r"(?P<one>(?:The|A) +[a-z][a-z-]+) +(?P<be1>was) +(?P<manner1>newly|freshly|recently) +"
    r"(?P<state1>painted|washed|varnished|polished)(?P<semi1>;) +"
    r"(?P<two>the +[a-z][a-z-]+) +(?P<had>had) +(?P<object>[^,;.!?]+)(?P<semi2>;) +"
    r"(?P<three>the +[a-z][a-z-]+) +(?P<be2>was) +(?P<manner2>cleanly|smoothly|freshly|carefully) +"
    r"(?P<state2>sanded|polished|swept|scrubbed|washed)" + _STOP
)


def plan_triple_passive(text, components):
    m = _PASSIVE_INVENTORY.fullmatch(text)
    if m is None or any(c.get("function") == "direct_speech" for c in components):
        return None
    spans = [(c["start"], c["end"]) for c in components
             if c.get("function") in ("matrix_clause", "independent_clause")]
    if spans != [(0, m.start("semi1")), (m.start("two"), m.start("semi2")), (m.start("three"), len(text))]:
        return None
    return _parts(m, (
        ("one", "NP", "phrase", {"proof_rule": "np_det_n", "number": "singular"}),
        ("be1", "AUX-BE", "lexical", {"vform": "finite"}),
        ("manner1", "ADV", "lexical", {}),
        ("state1", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("semi1", "SEMICOLON", "source-punctuation", {}),
        ("two", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("had", "HAVE", "lexical", {"vform": "finite"}),
        ("object", "NP", "phrase", {"proof_rule": "np_bare"}),
        ("semi2", "SEMICOLON", "source-punctuation", {}),
        ("three", "NP", "phrase", {"proof_rule": "np_det_n", "number": "singular"}),
        ("be2", "AUX-BE", "lexical", {"vform": "finite"}),
        ("manner2", "ADV", "lexical", {}),
        ("state2", "V", "lexical-alternatives", _v("ed", "transitive")),
        *_marked(),
    ))


_ECHO = re.compile(
    r"(?P<predicate>Cross|Angry|Upset|Worried|Sorry)(?P<comma>,) +"
    r"(?P<address>my +(?:love|dear|dearest|friend|child))"
)


def plan_adjectival_echo(text, components):
    evidence = _single_spoken_span(text, components)
    if evidence is None or text[evidence[0]] != "?":
        return None
    stop, _ = evidence
    m = _ECHO.fullmatch(text[1:stop])
    if m is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("predicate", "ADJ", "lexical", {}),
        ("comma", "COMMA", "source-punctuation", {}),
        ("address", "NP", "phrase", {"proof_rule": "np_poss"}),
    ))
    mark("SPEECH-STOP", stop, stop+1)
    mark("CLOSE-QUOTE", stop+1, stop+2)
    return specs


_COURT_WH = re.compile(
    r"(?P<what>What) +(?P<copula>was|is) +(?P<det>the) +"
    r"(?P<court>Arches|Chancery|Consistory)(?P<question>\?)"
)


def plan_named_court(text, components):
    m = _COURT_WH.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("what", "WH-NOM", "lexical", {}),
        ("copula", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("det", "DET", "lexical", {"number": "singular", "definiteness": "definite"}),
        ("court", "PROPER-NOUN", "scoped-lexical", {"institution": "court"}),
        ("question", "SPEECH-STOP", "source-punctuation", {}),
    ))


_TITLED_VOCATIVE = re.compile(
    r"(?P<subject>He|She) +(?P<be>is|was) +(?P<a>a|an) +"
    r"(?P<role>partaker|participant|recipient|witness) +(?P<of>of) +(?P<domain>[a-z][a-z-]+) +"
    r"(?P<at>at) +(?P<present>present|first)(?P<comma>,) +"
    r"(?P<title>Master|Miss|Captain|Doctor) +(?P<address>[A-Z][a-z]+)"
)
_FULL_REPORT = re.compile(
    r"(?P<report>said|replied|answered|exclaimed) +(?P<name>[A-Z][a-z]+) +(?P<family>[A-Z][a-z]+)"
)
_TITLED_REPORT = re.compile(
    r"(?P<report>said|replied|answered|exclaimed) +(?P<title>Master|Miss|Captain|Doctor) +"
    r"(?P<family>[A-Z][a-z]+)"
)
_BELIEF_VOCATIVE = re.compile(
    r"(?P<subject>I|We) +(?P<believe>believe|trust) +(?P<object>you|him|her|them)(?P<comma>,) +"
    r"(?P<address>my +(?:pet|love|dear|friend|child))"
)


def plan_named_vocative(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != ",":
        return None
    stop, reporter = evidence
    m = _TITLED_VOCATIVE.fullmatch(text[1:stop])
    r = _FULL_REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None or _TITLED_REPORT.fullmatch(r[0]):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("subject", "NP", "subject-phrase", {}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("a", "DET", "lexical", {"number": "singular"}),
        ("role", "N", "lexical", {"number": "singular"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("domain", "N", "lexical", {}),
        ("at", "PREP", "lexical", {"lemma_in": "at"}),
        ("present", "ADJ", "lexical", {}),
        ("comma", "COMMA", "source-punctuation", {}),
        ("title", "TITLE", "scoped-lexical", {"honorific": "true"}),
        ("address", "PROPER-NOUN", "lexical", {}),
    ))
    mark("COMMA", stop, stop+1)
    mark("CLOSE-QUOTE", stop+1, stop+2)
    part(r, reporter["start"], (
        ("report", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "say|reply|answer|exclaim"}),
        ("name", "PROPER-NOUN", "lexical", {}),
        ("family", "PROPER-NOUN", "lexical", {}),
    ))
    mark("SPEECH-STOP", len(text)-1, len(text))
    return specs


def plan_belief_vocative(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != ",":
        return None
    stop, reporter = evidence
    m = _BELIEF_VOCATIVE.fullmatch(text[1:stop])
    r = _TITLED_REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("subject", "NP", "subject-phrase", {}),
        ("believe", "V", "lexical-alternatives", _v("finite", "transitive")),
        ("object", "NP", "phrase", {}),
        ("comma", "COMMA", "source-punctuation", {}),
        ("address", "NP", "phrase", {"proof_rule": "np_poss"}),
    ))
    mark("COMMA", stop, stop+1)
    mark("CLOSE-QUOTE", stop+1, stop+2)
    part(r, reporter["start"], (
        ("report", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "say|reply|answer|exclaim"}),
        ("title", "TITLE", "scoped-lexical", {"honorific": "true"}),
        ("family", "PROPER-NOUN", "lexical", {}),
    ))
    mark("SPEECH-STOP", len(text)-1, len(text))
    return specs


_RESTORATION = re.compile(
    r"(?P<cause>(?:A +little|The|Some) +[^,;.!?]{2,36}) +(?P<modal>would|should|could|might) +"
    r"(?P<set>set) +(?P<affected>me|him|her|us|them|you) +(?P<up>up) +"
    r"(?P<duration>forever|for +(?:life|good|the +day|the +week))"
)


def plan_modal_restoration(text, components):
    evidence = _single_spoken_span(text, components)
    if evidence is None or text[evidence[0]] != ".":
        return None
    stop, _ = evidence
    m = _RESTORATION.fullmatch(text[1:stop])
    if m is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        ("cause", "NP", "subject-phrase", {}),
        ("modal", "MODAL", "lexical", {}),
        ("set", "V", "lexical-alternatives", _v("base", "transitive")),
        ("affected", "NP", "phrase", {}),
        ("up", "PARTICLE", "lexical", {"lemma_in": "up"}),
        ("duration", "ADV" if m["duration"] == "forever" else "PP",
         "lexical" if m["duration"] == "forever" else "phrase", {}),
    ))
    mark("SPEECH-STOP", stop, stop+1)
    mark("CLOSE-QUOTE", stop+1, stop+2)
    return specs


_INVERTED_EFFECT = re.compile(
    r"(?P<degree>Widely|Markedly|Quite|Entirely) +(?P<attribute>different|distinct|otherwise) +"
    r"(?P<be>was|is) +(?P<the>the) +(?P<effect>effect|result|outcome) +(?P<of>of) +"
    rf"(?P<cause>{_NOM})" + _STOP
)


def plan_inverted_effect(text, components):
    m = _INVERTED_EFFECT.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        ("degree", "ADV", "lexical", {}),
        ("attribute", "ADJ", "lexical", {}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("the", "DET", "lexical", {"number": "singular"}),
        ("effect", "N", "lexical", {"number": "singular"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("cause", "NP", "phrase", {"grounded_object_proof": "true"}),
        *_marked(),
    ))


COMPARATIVE_EXTRAPOSITION = "structural_evaluative_comparison_with_extraposed_infinitive"
FOCUSED_CLEFT = "structural_additive_cleft_with_local_subject_gap"
EVENT_RELATIVE = "structural_event_relative_with_resultative_placement"
SHARED_CONTACT = "structural_shared_subject_contact_with_local_degree_and_body_site"
SCENE_LOCATION = "structural_temporal_scene_with_nested_location"
FRONTED_PERCEPTION = "structural_fronted_perception_object_with_temporal_incise"
CONDITIONAL_HOPE = "dialogue_structural_condition_over_controlled_attitude"
CONDITIONAL_EVALUATION = "dialogue_structural_condition_over_gerund_ground"


def _a(group, category, **features):
    return group, category, "lexical", features


def _b(group, category, form, frame=None, **features):
    return group, category, "lexical-alternatives", (
        _v(form, frame, **features) if frame else {"vform": form, **features}
    )


def _scoped(group, category, **features):
    return group, category, "scoped-lexical", features


def _p(group, category="NP", **features):
    return group, category, "phrase", features


def _subject(group):
    return group, "NP", "subject-phrase", {}


def _punct(group, category="COMMA"):
    return group, category, "source-punctuation", {}


_COMPARATIVE_EXTRAPOSITION = re.compile(
    r"(?P<it>It) +(?P<be>was|is) +(?P<as1>as) +(?P<attribute>good|pleasant|strange|surprising) +"
    rf"(?P<as2>as) +(?P<benchmark>{_NOM}) +(?P<to>to) +(?P<action>see|watch|hear|meet|read) +"
    rf"(?P<object>him|her|them|you|me|us|{_NOM})" + _STOP
)


def plan_comparative_extraposition(text, components):
    m = _COMPARATIVE_EXTRAPOSITION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _a("it", "EXTRAPOSITION-IT", lemma_in="it"), _a("be", "COPULA", vform="finite", number="singular"),
        _a("as1", "CONJ", lemma_in="as", degree="true"), _a("attribute", "ADJ"),
        _a("as2", "PREP", lemma_in="as"), _p("benchmark", proof_rule="np_det_n"),
        _a("to", "TO"), _b("action", "V", "base", "transitive"), _p("object"), *_marked(),
    ))


_FOCUSED_CLEFT = re.compile(
    r"(?P<and>And|But) +(?P<it>it) +(?P<be>was|is) +(?P<not>not) +(?P<only>only) +"
    rf"(?P<focus>we|she|he|they|I) +(?P<of>of) +(?P<group>{_NOM}) +"
    rf"(?P<who>who) +(?P<event>perceived|noticed|saw|recognized|heard|felt) +(?P<object>{_NOM})" + _STOP
)


def plan_focused_cleft(text, components):
    m = _FOCUSED_CLEFT.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _a("and", "COORD"), _a("it", "EXTRAPOSITION-IT", lemma_in="it"), _a("be", "COPULA", vform="finite", number="singular"),
        _a("not", "NEG", negation="true"), _a("only", "ADV", lemma_in="only"),
        _subject("focus"), _a("of", "PREP", nominal_complement="of"),
        _p("group", proof_rule="np_det_n"), _a("who", "WH-PRONOUN", lemma_in="who", wh="true"),
        _b("event", "V", "finite", "transitive"), _p("object", grounded_object_proof="true"), *_marked(),
    ))


_EVENT_RELATIVE = re.compile(
    r"(?P<but>But|And) +(?P<as>as) +(?P<things>things|events) +(?P<fell>fell|turned) +(?P<out>out), +"
    r"(?P<subject>(?:my|his|her|our|their|the) +[a-z-]+(?: +[a-z-]+)?) +"
    r"(?P<dies>died|collapsed|fainted|departed) +(?P<degree>quite|very|rather) +(?P<manner>suddenly|unexpectedly|quietly) +"
    r"(?P<time>that +(?:evening|morning|night|day))(?P<comma2>,) +(?P<which>which) +"
    r"(?P<put>put|set) +(?P<object>(?:all|the) +other +[a-z-]+) +"
    r"(?P<on>on) +(?P<side>one side)" + _STOP
)


def plan_event_relative(text, components):
    m = _EVENT_RELATIVE.fullmatch(text)
    if m is None or not _matrix(text, components) or (m["fell"], m["out"]) not in {("fell", "out"), ("turned", "out")}:
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        _a("but", "COORD"), _scoped("as", "CONJ", lemma_in="as", temporal="true"), _subject("things"),
        _scoped("fell", "V", **_v("finite", "intransitive", tense="past", lemma_in="fall|turn")), _a("out", "PARTICLE", lemma_in="out"),
    ))
    mark("COMMA", m.end("out"), m.end("out") + 1)
    part(m, 0, (
        _subject("subject"), _b("dies", "V", "finite", "intransitive"),
        _a("degree", "ADV"), _a("manner", "ADV"), _p("time", proof_rule="np_det_n"), _punct("comma2"),
        _a("which", "WH-PRONOUN", lemma_in="which", wh="true"), _b("put", "V", "finite", "transitive"),
        _p("object"), _a("on", "PREP", lemma_in="on"), _p("side"), *_marked(),
    ))
    return specs


_SHARED_CONTACT = re.compile(
    r"(?P<then>Then|Thereupon) +(?P<subject>he|she|they|we|I) +"
    r"(?P<first>kissed|held|hugged|embraced) +(?P<object1>me|him|her|you|them|us) +"
    r"(?P<degree>more and more|again and again)(?P<comma>,) +(?P<and>and) +"
    r"(?P<second>clasped|held|grasped|caught) +(?P<object2>me|him|her|you|them|us) +"
    r"(?P<round>round|around) +(?P<site>the +(?:neck|waist|wrist|arm|shoulders))" + _STOP
)


def plan_shared_contact(text, components):
    m = _SHARED_CONTACT.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _a("then", "ADV"), _subject("subject"), _b("first", "V", "finite", "transitive"),
        _p("object1"), _a("degree", "ADV"), _punct("comma"), _a("and", "COORD", lemma_in="and"),
        _b("second", "V", "finite", "transitive"),
        _p("object2"), _a("round", "PREP", lemma_in="round|around"), _p("site", proof_rule="np_det_n"), *_marked(),
    ))


_SCENE_LOCATION = re.compile(
    r"(?P<it>It) +(?P<be>is|was) +(?P<a>a) +(?P<season>summer|winter|spring|autumn) +(?P<time>evening|morning|afternoon|night)"
    r"(?P<comma1>,) +(?P<down>down|up) +(?P<in>in) +(?P<scene>a +[a-z-]+ +[a-z-]+)(?P<comma2>,) +"
    rf"(?P<at>at) +(?P<the>the) +(?P<spot>corner|edge|side|foot) +(?P<of>of) +(?P<landmark>{_NOM})" + _STOP
)


def plan_scene_location(text, components):
    m = _SCENE_LOCATION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _scoped("it", "EXPL", lemma_in="it", scene_setting="true"), _a("be", "COPULA", vform="finite", number="singular"),
        _a("a", "DET", number="singular"), _a("season", "N"), _a("time", "N", number="singular"), _punct("comma1"), _a("down", "ADV"), _a("in", "PREP", lemma_in="in"),
        _p("scene", proof_rule="np_det_n"), _punct("comma2"), _a("at", "PREP", lemma_in="at"),
        _a("the", "DET", number="singular"), _a("spot", "N", number="singular"),
        _a("of", "PREP", nominal_complement="of"), _p("landmark", grounded_object_proof="true"), *_marked(),
    ))


_FRONTED_PERCEPTION = re.compile(
    r"(?P<det>The) +(?P<focus>expression|look|tone|sound) +(?P<of>of) +"
    r"(?P<source>(?:his|her|their|your) +[a-z-]+)(?P<comma1>,) +"
    r"(?P<as>as) +(?P<their>they|we) +(?P<both>both) +(?P<looked>looked|turned|glanced) +"
    r"(?P<direction>(?:towards?|at) +(?:me|her|him|them|you|us))(?P<comma2>,) +"
    rf"(?P<feeler>{_LOWER_PRON}) +(?P<felt>felt|judged|considered|found) +(?P<to>to) +(?P<be>be) +"
    r"(?P<degree>very|quite|rather) +(?P<attribute>touching|strange|moving|familiar|odd)" + _STOP
)


def plan_fronted_perception(text, components):
    m = _FRONTED_PERCEPTION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _a("det", "DET"), _a("focus", "N", number="singular"), _a("of", "PREP", nominal_complement="of"),
        _p("source", proof_rule="np_poss"), _punct("comma1"), _scoped("as", "CONJ", lemma_in="as", temporal="true"),
        _subject("their"), _scoped("both", "ADV", quantifier="both"), _b("looked", "V", "finite"),
        _p("direction", "PP", proof_rule="pp_prep_np"), _punct("comma2"),
        _subject("feeler"), _scoped("felt", "V", **_v("finite", "object_raising", tense="past")),
        _a("to", "TO"), _a("be", "COPULA", vform="base"), _a("degree", "ADV"), _a("attribute", "ADJ"), *_marked(),
    ))


_CONDITIONAL_HOPE = re.compile(
    r"(?P<if>If) +(?P<subject1>(?:my|your|his|her|our|their) +[a-z-]+) +"
    r"(?P<be1>are|were) +(?P<attribute1>silly|wrong|unwise|foolish)(?P<comma>,) +"
    rf"(?P<subject2>{_LOWER_PRON}) +(?P<modal>must|should|may|might) +(?P<hope>hope) +"
    r"(?P<to>to) +(?P<be2>be) +(?P<always>always|still) +(?P<attribute2>sensible|aware|mindful) +"
    r"(?P<of>of) +(?P<object>it|that|this)"
)


_CONDITIONAL_EVALUATION = re.compile(
    rf"(?P<subject>{_PRON}) +(?P<be>is|was|are|were|am) +(?P<characterization>a +"
    r"(?:great|real|complete|terrible) +(?:fool|idiot|coward)) +(?P<for>for) +"
    r"(?P<action>going|walking|running|turning) +(?P<away>away)(?P<comma>,) +"
    rf"(?P<if>if) +(?P<liker>{_LOWER_PRON}) +(?P<liked>liked|loved|trusted|respected) +(?P<object>him|her|them|me|you|us)"
)


def _plain_spoken(text, components, pattern, items):
    evidence = _single_spoken_span(text, components)
    if evidence is None:
        return None
    stop, _ = evidence
    m = pattern.fullmatch(text[1:stop])
    if m is None or text[stop] != ".":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, items)
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


def plan_conditional_hope(text, components):
    return _plain_spoken(text, components, _CONDITIONAL_HOPE, (
        _a("if", "CONJ", lemma_in="if"), _p("subject1", proof_rule="np_poss"),
        _a("be1", "COPULA", vform="finite", number="plural"), _a("attribute1", "ADJ"), _punct("comma"),
        _subject("subject2"), _a("modal", "MODAL"), _b("hope", "V", "base", "subject_control"),
        _a("to", "TO"), _a("be2", "COPULA", vform="base"), _a("always", "ADV"),
        _a("attribute2", "ADJ"), _a("of", "PREP", nominal_complement="of"), _p("object"),
    ))


def plan_conditional_evaluation(text, components):
    return _plain_spoken(text, components, _CONDITIONAL_EVALUATION, (
        _subject("subject"), _a("be", "COPULA", vform="finite"), _p("characterization", proof_rule="np_det_n"),
        _a("for", "PREP", lemma_in="for"), _b("action", "V", "ing", "intransitive"), _a("away", "PARTICLE", lemma_in="away"),
        _punct("comma"), _a("if", "CONJ", lemma_in="if"), _subject("liker"),
        _b("liked", "V", "finite", "transitive"), _p("object"),
    ))


QUOTED_CONDITION_THEN_ACTION = "dialogue_structural_quoted_condition_then_narrative_placement"
REPORTED_COORDINATE_NEGATION = "dialogue_structural_reported_distinct_negations_and_deictic_clause"

_QUOTED_CONDITION_THEN_ACTION = re.compile(
    rf"(?P<now>Now)(?P<comma1>,) +(?P<then>then)(?P<comma2>,) +(?P<if>if) +(?P<actor>{_NAME}) +"
    r"(?P<be>is|was) +(?P<attribute>agreeable|willing|ready)(?P<comma3>,) +"
    rf"(?P<we>we|he|she|they|you|I)(?P<modal>['’]ll) +(?P<open>open|read|examine|unseal) +(?P<object>{_NOM})"
)
_NARRATED_PLACEMENT = re.compile(
    r"(?P<and>and) +(?P<subject>he|she|we|they|I) +(?P<laid>laid|placed|set|put) +(?P<theme>it|them) +"
    r"(?P<before>before) +(?P<anchor>him|her|me|us|them|you) +(?P<on>on) +"
    r"(?P<surface>the +(?:table|desk|floor|bench|shelf))" + _STOP
)


def plan_quoted_condition_then_action(text, components):
    by_function = {c["function"]: c for c in components}
    q = by_function.get("direct_speech")
    later = by_function.get("coordinate_clause")
    if (
        not q or not later or q["start"] != 0 or q["relation"] != "unattributed_speech"
        or "reporting_clause" in by_function or later["end"] != len(text)
        or not re.fullmatch(r";\s*", text[q["end"]:later["start"]])
    ):
        return None
    end = q["end"]
    main = _QUOTED_CONDITION_THEN_ACTION.fullmatch(text[1:end - 1])
    other = _NARRATED_PLACEMENT.fullmatch(text[later["start"]:])
    if main is None or other is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(main, 1, (
        _a("now", "ADV"), _punct("comma1"), _a("then", "ADV"), _punct("comma2"), _a("if", "CONJ", lemma_in="if"),
        _subject("actor"), _a("be", "COPULA", vform="finite", number="singular"), _a("attribute", "ADJ"),
        _punct("comma3"), _subject("we"), _a("modal", "MODAL"), _b("open", "V", "base", "transitive"),
        _p("object", grounded_object_proof="true"),
    ))
    mark("CLOSE-QUOTE", end - 1, end)
    mark("SEMICOLON", end, end + 1)
    part(other, later["start"], (
        _a("and", "COORD", lemma_in="and"), _subject("subject"), _b("laid", "V", "finite", "transitive"),
        _p("theme"), _a("before", "PREP", lemma_in="before"), _p("anchor"),
        _a("on", "PREP", lemma_in="on"), _p("surface", proof_rule="np_det_n"), *_marked(),
    ))
    return specs


_REPORTED_COORDINATE_NEGATION = re.compile(
    r"(?P<subject1>I)(?P<be>['’]m) +(?P<not1>not) +(?P<state>strong|brave|bold|ready) +(?P<enough>enough)"
    r"(?P<comma1>,) +(?P<and1>and) +(?P<subject2>I) +(?P<do>do)(?P<not2>n['’]t) +"
    rf"(?P<attitude>like|want|trust|enjoy) +(?P<object>{_NOM})(?P<semi>;) +(?P<and2>and) +"
    r"(?P<there>there) +(?P<subject3>he|she|they) +(?P<state3>lies|stands|sits|waits|lie|stand|sit|wait)"
    r"(?P<comma2>,) +(?P<for>for) +(?P<object3>me|him|her|us|them|you)"
)


def plan_reported_coordinate_negation(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != ",":
        return None
    stop, reporter = evidence
    m = _REPORTED_COORDINATE_NEGATION.fullmatch(text[1:stop])
    r = _REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None or (m["subject3"] == "they") == m["state3"].endswith("s"):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        _subject("subject1"), _a("be", "COPULA", vform="finite"),
        _a("not1", "NEG", negation="true"), _a("state", "ADJ"), _a("enough", "ADV"),
        _punct("comma1"), _a("and1", "COORD", lemma_in="and"), _subject("subject2"),
        _a("do", "AUX", vform="finite", lemma_in="do"), _a("not2", "NEG", negation="true"),
        _b("attitude", "V", "base", "transitive"), _p("object", grounded_object_proof="true"),
        _punct("semi", "SEMICOLON"), _a("and2", "COORD", lemma_in="and"), _a("there", "ADV", lemma_in="there"),
        _subject("subject3"), _b("state3", "V", "finite", "intransitive"), _punct("comma2"),
        _a("for", "PREP", lemma_in="for"), _p("object3"),
    ))
    return _reported_tail(specs, mark, part, text, stop, reporter, r)


SHARED_START_CONTROL = "structural_shared_start_control_with_bounded_retreat"
PERCEPTION_AND_REPLY = "structural_perception_small_clause_and_independent_reply"
REPORTED_NOMINAL_SERIES = "structural_reported_copular_series_with_local_relations"
EXISTENTIAL_RELATIVE_FOCUS = "structural_negative_existential_stranded_relative_and_focus"
TWO_QUESTIONS_PASSIVE = "dialogue_structural_two_wh_questions_then_modal_perfect_passive"
PARTITIVE_PASSAGE = "structural_persistent_boundary_and_partitive_passage"
REPORTED_NEGATIVE_VOCATIVE = "dialogue_structural_reported_negative_response_with_vocative"

_SHARED_START = re.compile(
    r"(?P<instantly>Instantly|Immediately) +(?P<actor>I|he|she|we|they) +(?P<start>began|started) +"
    r"(?P<to>to) +(?P<first>extricate|free|disentangle) +(?P<self>myself|himself|herself|ourselves|themselves) +"
    r"(?P<and>and) +(?P<second>crawl|creep|walk|run) +(?P<back>back) +(?P<again>again)(?P<comma1>,) +"
    r"(?P<with>with) +(?P<what>what) +(?P<first_measure>speed|care|effort) +(?P<and2>and) +"
    r"(?P<second_measure>silence|caution|quiet) +(?P<manager>I|he|she|we|they) +(?P<could>could) +"
    r"(?P<manage>manage|muster)(?P<comma2>,) +(?P<direction>to|toward|towards) +"
    r"(?P<the>the) +(?P<more>more) +(?P<attribute>open|sheltered|quiet) +(?P<part>portion|part|section) +"
    rf"(?P<of>of) +(?P<place>{_NOM})" + _STOP
)


def plan_shared_start_control(text, components):
    m = _SHARED_START.fullmatch(text)
    if (
        m is None or not _matrix(text, components) or m["actor"] != m["manager"]
        or {"I": "myself", "he": "himself", "she": "herself", "we": "ourselves", "they": "themselves"}[m["actor"]] != m["self"]
    ):
        return None
    return _parts(m, (
        _a("instantly", "ADV"), _subject("actor"), _b("start", "V", "finite", "subject_control"),
        _a("to", "TO"), _b("first", "V", "base", "transitive"), _a("self", "PRONOUN", reflexive="true"),
        _a("and", "COORD", lemma_in="and"), _b("second", "V", "base", "intransitive"),
        _a("back", "PARTICLE", lemma_in="back"), _a("again", "ADV"), _punct("comma1"),
        _a("with", "PREP", lemma_in="with"), _a("what", "WH-PRONOUN", wh="true"),
        _a("first_measure", "N"), _a("and2", "COORD", lemma_in="and"), _a("second_measure", "N"),
        _subject("manager"), _a("could", "MODAL"), _b("manage", "V", "base", "transitive"), _punct("comma2"),
        _a("direction", "PREP"), _a("the", "DET"), _a("more", "ADV"), _a("attribute", "ADJ"),
        _a("part", "N"), _a("of", "PREP", nominal_complement="of"), _p("place", proof_rule="np_det_n"), *_marked(),
    ))


_PERCEPTION_AND_REPLY = re.compile(
    rf"(?P<first>{_SUBJECT}) +(?P<thought>thought|imagined|considered) +(?P<object>him|her|them|you|me|us) +"
    r"(?P<looked>looking|seeming) +(?P<as1>as) +(?P<attribute>villainous|innocent|weary|pale|lively) +"
    r"(?P<as2>as) +(?P<ever>ever)(?P<comma>,) +(?P<and>and) +"
    rf"(?P<second>{_LOWER_PRON}|{_NAME}) +(?P<replied>replied|answered|said) +(?P<that>that) +"
    rf"(?P<third>{_LOWER_PRON}|{_NAME}) +(?P<saw>saw|noticed|found) +(?P<no>no) +"
    r"(?P<change>change|difference|alteration) +(?P<in>in) +(?P<affected>him|her|them|you|me|us)" + _STOP
)


def plan_perception_and_reply(text, components):
    m = _PERCEPTION_AND_REPLY.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _subject("first"), _b("thought", "V", "finite"), _p("object"), _b("looked", "V", "ing", "linking"),
        _a("as1", "CONJ", lemma_in="as", degree="true"), _a("attribute", "ADJ"), _a("as2", "PREP", lemma_in="as"),
        _a("ever", "ADV"), _punct("comma"), _a("and", "COORD", lemma_in="and"), _subject("second"),
        _b("replied", "V", "finite"), _a("that", "COMP-THAT"), _subject("third"),
        _b("saw", "V", "finite", "transitive"), _a("no", "DET", negation="true"), _a("change", "N", number="singular"),
        _a("in", "PREP", lemma_in="in"), _p("affected"), *_marked(),
    ))


_REPORTED_NOMINAL_SERIES = re.compile(
    rf"(?P<speaker>{_SUBJECT}) +(?P<said>said|declared|insisted) +(?P<person>{_LOWER_PRON}|{_NAME}) +"
    r"(?P<be>was|is) +(?P<first>(?:my|his|her|our|their) +(?:dearest|closest|best|oldest) +friend)(?P<comma1>,) +"
    r"(?P<det1>the) +(?P<role1>protector|guardian|teacher|mentor) +(?P<of1>of) +"
    r"(?P<time1>(?:my|his|her|our|their) +(?:boyhood|girlhood|youth|childhood|adolescence))(?P<comma2>,) +"
    r"(?P<and>and) +(?P<det2>the) +(?P<role2>companion|friend|partner|supporter) +(?P<of2>of) +"
    r"(?P<time2>(?:my|his|her|our|their) +(?:prime|adulthood|old age|maturity|manhood|womanhood))" + _STOP
)


def plan_reported_nominal_series(text, components):
    m = _REPORTED_NOMINAL_SERIES.fullmatch(text)
    if m is None or not _matrix(text, components) or m["person"] in {"I", "you", "we", "they"}:
        return None
    return _parts(m, (
        _subject("speaker"), _b("said", "V", "finite"), _subject("person"),
        _a("be", "COPULA", vform="finite", number="singular"), _p("first", proof_rule="np_poss"),
        _punct("comma1"), _a("det1", "DET"), _a("role1", "N"), _a("of1", "PREP", nominal_complement="of"),
        _p("time1", proof_rule="np_poss"), _punct("comma2"), _a("and", "COORD", lemma_in="and"),
        _a("det2", "DET"), _a("role2", "N"), _a("of2", "PREP", nominal_complement="of"),
        _p("time2", proof_rule="np_poss"), *_marked(),
    ))


_EXISTENTIAL_RELATIVE_FOCUS = re.compile(
    r"(?P<there>There) +(?P<be>was|is) +(?P<no>no) +(?P<other>other) +"
    r"(?P<thing>question|problem|obstacle|answer) +(?P<that>that) +(?P<knower>I|he|she|we|they|you) +"
    r"(?P<knew>knew|heard) +(?P<of>of) +(?P<domain>in +the +(?:world|town|country|city|village))(?P<comma>,) +"
    rf"(?P<and>and) +(?P<only>only) +(?P<actor>{_NAME}|{_LOWER_PRON}) +"
    r"(?P<could>could|can|would|might) +(?P<give>give|provide|find|know) +(?P<the>the) +"
    r"(?P<answer>answer|solution|response) +(?P<to>to) +(?P<object>it|this|that)" + _STOP
)


def plan_existential_relative_focus(text, components):
    m = _EXISTENTIAL_RELATIVE_FOCUS.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _a("there", "EXPL", expletive="true"), _a("be", "COPULA", vform="finite", number="singular"),
        _a("no", "DET", negation="true"), _a("other", "ADJ"), _a("thing", "N", number="singular"),
        _a("that", "COMP-THAT"), _subject("knower"), _b("knew", "V", "finite"),
        _a("of", "PREP", lemma_in="of"), _p("domain", "PP", proof_rule="pp_prep_np"),
        _punct("comma"), _a("and", "COORD", lemma_in="and"), _a("only", "ADV", lemma_in="only"),
        _subject("actor"), _a("could", "MODAL"), _b("give", "V", "base", "transitive"),
        _a("the", "DET"), _a("answer", "N", number="singular"), _a("to", "PREP", lemma_in="to"), _p("object"),
        *_marked(),
    ))


_TWO_QUESTIONS_PASSIVE = re.compile(
    r"(?P<then>Then|Well)(?P<comma1>,) +(?P<who1>who) +(?P<taught>taught|helped|trained) +"
    r"(?P<object1>you|him|her|them|me|us)(?P<q1>\?) +(?P<who2>who|Who) +"
    r"(?P<attended>attended|listened) +(?P<to>to) +(?P<object2>you|him|her|them|me|us)(?P<q2>\?) +"
    r"(?P<without>Without) +(?P<role>a +(?:governess|tutor|teacher|guardian))(?P<comma2>,) +"
    rf"(?P<person>{_LOWER_PRON}) +(?P<must>must|might|could) +(?P<have>have) +"
    r"(?P<been>been) +(?P<neglected>neglected|ignored|forgotten|overlooked)"
)


def plan_two_questions_passive(text, components):
    q = next((c for c in components if c["function"] == "direct_speech"), None)
    if q is None or q["start"] != 0 or q["end"] != len(text) or q["relation"] != "unattributed_speech":
        return None
    m = _TWO_QUESTIONS_PASSIVE.fullmatch(text[1:-2])
    if m is None or text[-2] != ".":
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        _a("then", "ADV"), _punct("comma1"), _a("who1", "WH-PRONOUN", wh="true"),
        _b("taught", "V", "finite", "transitive"), _p("object1"), _punct("q1", "SPEECH-STOP"),
        _a("who2", "WH-PRONOUN", wh="true"), _b("attended", "V", "finite"),
        _a("to", "PREP", lemma_in="to"), _p("object2"), _punct("q2", "SPEECH-STOP"),
        _a("without", "PREP", lemma_in="without"), _p("role", proof_rule="np_det_n"), _punct("comma2"),
        _subject("person"), _a("must", "MODAL"), _a("have", "HAVE", vform="base"),
        _a("been", "AUX-BE", vform="ed"), _b("neglected", "V", "ed", "transitive"),
    ))
    mark("SPEECH-STOP", len(text)-2, len(text)-1)
    mark("CLOSE-QUOTE", len(text)-1, len(text))
    return specs


_PARTITIVE_PASSAGE = re.compile(
    r"(?P<the1>The) +(?P<modifier>park|garden|field|yard) +(?P<fence>paling|fence|wall|hedge) +(?P<be>was|is) +"
    r"(?P<still>still) +(?P<boundary>the +(?:boundary|border|limit)) +(?P<side>on one side)(?P<comma>,) +"
    rf"(?P<and>and) +(?P<actor>{_LOWER_PRON}|{_NAME}) +(?P<soon>soon|then|quickly) +"
    r"(?P<passed>passed|crossed|entered) +(?P<one>one) +(?P<of>of) +"
    r"(?P<det_gates>the) +(?P<gates>gates|doors|barriers|entrances) +(?P<direction>into +the +(?:ground|garden|field|yard|park))"
    + _STOP
)


def plan_partitive_passage(text, components):
    m = _PARTITIVE_PASSAGE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _a("the1", "DET"), _a("modifier", "N"), _a("fence", "N", number="singular"),
        _a("be", "COPULA", vform="finite", number="singular"), _a("still", "ADV"),
        _p("boundary", proof_rule="np_det_n"), _p("side", "PP", proof_rule="pp_prep_np"),
        _punct("comma"), _a("and", "COORD", lemma_in="and"), _subject("actor"), _a("soon", "ADV"),
        _b("passed", "V", "finite", "transitive"), _scoped("one", "PRONOUN", number="singular", partitive_quantifier="true"),
        _a("of", "PREP", nominal_complement="of"), _a("det_gates", "DET", number="plural"), _a("gates", "N", number="plural"),
        _p("direction", "PP", proof_rule="pp_prep_np"), *_marked(),
    ))


_NEGATIVE_VOCATIVE = re.compile(r"(?P<no>No)(?P<comma>,) +(?P<address>father|mother|sir|madam|uncle|aunt)")
_QUIET_INTERRUPTION = re.compile(rf"(?P<speaker>{_NAME}) +(?P<report>interposed)")


def plan_reported_negative_vocative(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != ",":
        return None
    stop, reporter = evidence
    m = _NEGATIVE_VOCATIVE.fullmatch(text[1:stop])
    r = _QUIET_INTERRUPTION.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (_scoped("no", "INTERJECTION", lemma_in="no", negation="true"), _punct("comma"), _a("address", "N")))
    mark("COMMA", stop, stop+1)
    mark("CLOSE-QUOTE", stop+1, stop+2)
    part(r, reporter["start"], (_subject("speaker"), _scoped("report", "V", vform="finite", lemma_in="interpose")))
    mark("SPEECH-STOP", len(text)-1, len(text))
    return specs


EXISTENTIAL_AND_REMAINDER = "structural_existential_inventory_with_cardinal_remainder"
REACTION_RESULT = "structural_scalar_passive_result_and_counteraction"
NEGATED_MISGIVING = "structural_negated_misgiving_with_extraposed_evaluation"
REPORTED_THREE_ACTS = "dialogue_structural_free_relative_then_reaction_and_topic_question"

_EXISTENTIAL_REMAINDER = re.compile(
    r"(?P<but>But|And) +(?P<there>there) +(?P<were>were) +(?P<all>all) +"
    r"(?P<pivot>(?:my|our|your|his|her|their) +(?:stores|supplies|provisions|tools)) +"
    r"(?P<location>at +the +(?:bottom|top|entrance|side))(?P<comma1>,) +(?P<and>and) +"
    r"(?P<to>to) +(?P<make>make) +(?P<things>things|matters) +(?P<worse>worse)(?P<comma2>,) +"
    r"(?P<only>only) +(?P<count>one|two|three|four|five|six) +(?P<guns>[a-z-]+) +"
    r"(?P<out>out) +(?P<of>of) +(?P<total>two|three|four|five|six|seven|eight|nine|ten) +"
    r"(?P<remain>remained) +(?P<in>in) +(?P<a>a) +(?P<state>state|condition) +"
    r"(?P<for>for) +(?P<use>service|use|work)" + _STOP
)
_CARDINALS = {word: number for number, word in enumerate(
    "one two three four five six seven eight nine ten".split(), 1
)}


def plan_existential_and_remainder(text, components):
    m = _EXISTENTIAL_REMAINDER.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _a("but", "COORD"), _a("there", "EXPL", expletive="true"), _a("were", "COPULA", vform="finite", number="plural"),
        _a("all", "DET", number="plural"), _p("pivot", proof_rule="np_poss"),
        _p("location", "PP", proof_rule="pp_prep_np"), _punct("comma1"), _a("and", "COORD", lemma_in="and"),
        _a("to", "TO"), _b("make", "V", "base", "transitive"), _a("things", "N", number="plural"), _a("worse", "ADJ"),
        _punct("comma2"), _a("only", "ADV", lemma_in="only"),
        _scoped("count", "CARDINAL", numeric_cardinal="true"),
        _a("guns", "N", number="singular" if m["count"] == "one" else "plural"),
        _a("out", "PARTICLE", lemma_in="out"), _a("of", "PREP", lemma_in="of"),
        _scoped("total", "CARDINAL", numeric_cardinal="true"), _b("remain", "V", "finite"),
        _a("in", "PREP", lemma_in="in"), _a("a", "DET", number="singular"), _a("state", "N", number="singular"),
        _a("for", "PREP", lemma_in="for"), _a("use", "N"), *_marked(),
    ))


_REACTION_RESULT = re.compile(
    r"(?P<subject>I|He|She) +(?P<was>was) +(?P<so>so) +(?P<much>much) +"
    r"(?P<startled>startled|alarmed|frightened) +(?P<that>that) +(?P<actor>I|he|she) +"
    r"(?P<struggled>struggled|tried|attempted) +(?P<to>to) +(?P<withdraw>withdraw|escape|retreat)(?P<comma>,) +"
    rf"(?P<but>but) +(?P<puller>{_NOM}) +(?P<pulled>pulled|dragged|drew) +(?P<object>me|him|her) +"
    r"(?P<close>close) +(?P<up>up) +(?P<to2>to) +(?P<anchor>him|her|me) +"
    r"(?P<with>with) +(?P<a>a) +(?P<single>single|sudden|quick) +(?P<action>action|movement|motion) +"
    rf"(?P<of>of) +(?P<body>{_NOM})" + _STOP
)


def plan_reaction_result(text, components):
    m = _REACTION_RESULT.fullmatch(text)
    if m is None or not _matrix(text, components) or m["subject"].lower() != m["actor"].lower():
        return None
    return _parts(m, (
        _subject("subject"), _a("was", "AUX-BE", vform="finite", number="singular"),
        _a("so", "DEGREE"), _a("much", "ADV"), _b("startled", "V", "ed", "transitive"),
        _a("that", "COMP-THAT"), _subject("actor"), _scoped("struggled", "V", **_v("finite", "subject_control")),
        _a("to", "TO"), _b("withdraw", "V", "base", "intransitive"), _punct("comma"), _a("but", "COORD", lemma_in="but"),
        _p("puller", proof_rule="np_det_n"), _b("pulled", "V", "finite", "transitive"), _p("object"),
        _a("close", "ADV"), _a("up", "PARTICLE", lemma_in="up"), _a("to2", "PREP", lemma_in="to"), _p("anchor"),
        _a("with", "PREP", lemma_in="with"), _a("a", "DET", number="singular"), _a("single", "ADJ"),
        _a("action", "N", number="singular"), _a("of", "PREP", nominal_complement="of"),
        _p("body", proof_rule="np_poss"), *_marked(),
    ))


_NEGATED_MISGIVING = re.compile(
    r"(?P<subject>I|He|She) +(?P<was>was) +(?P<troubled>troubled|burdened|disturbed) +(?P<with>with) +"
    r"(?P<no>no) +(?P<misgiving>misgiving|doubt|fear|concern) +(?P<that>that) +(?P<it>it) +"
    r"(?P<be>was|is) +(?P<attribute>young|unwise|wrong|unkind) +(?P<in>in) +(?P<judge>me|him|her) +"
    rf"(?P<to>to) +(?P<action>respond|reply|react) +(?P<target>to +{_NOM})" + _STOP
)


def plan_negated_misgiving(text, components):
    m = _NEGATED_MISGIVING.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _subject("subject"), _a("was", "AUX-BE", vform="finite", number="singular"),
        _b("troubled", "V", "ed", "transitive"), _a("with", "PREP", lemma_in="with"),
        _a("no", "DET", negation="true"), _a("misgiving", "N", number="singular"),
        _a("that", "COMP-THAT"), _a("it", "EXTRAPOSITION-IT", lemma_in="it"), _a("be", "COPULA", vform="finite", number="singular"),
        _a("attribute", "ADJ"), _a("in", "PREP", lemma_in="in"), _p("judge"), _a("to", "TO"),
        _b("action", "V", "base"), _p("target", "PP", proof_rule="pp_prep_np"), *_marked(),
    ))


_REPORTED_THREE_ACTS = re.compile(
    r"(?P<subject>This +(?:account|letter|paper|message)) +(?P<then>then) +(?P<be>is) +"
    rf"(?P<what>what) +(?P<receiver>{_LOWER_PRON}) +(?P<has>has|have) +(?P<received>received|heard|obtained) +"
    r"(?P<from>from) +(?P<source>(?:(?P<title>Mr|Mrs|Dr)\.|(?P<title_bare>Miss)) +(?P<surname>[A-Z][a-z]+)|[A-Z][a-z]+)(?P<stop1>\.) +"
    r"(?P<i>I) +(?P<am>am) +(?P<attribute>satisfied|convinced|content)(?P<stop2>\.) +"
    rf"(?P<but>But|And) +(?P<what2>what) +(?P<does>does|did) +(?P<speaker>{_LOWER_PRON}) +(?P<say>say|mention) +"
    rf"(?P<of>of|about) +(?P<topic>{_NOM})(?P<stop3>\?)"
)


def plan_reported_three_acts(text, components):
    q = next((c for c in components if c["function"] == "direct_speech"), None)
    parts = [c for c in components if c["function"] == "spoken_clause_candidate"]
    if not q or (q["start"], q["end"], q["relation"]) != (0, len(text), "unattributed_speech") or len(parts) != 3:
        return None
    m = _REPORTED_THREE_ACTS.fullmatch(text[1:-1])
    if m is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        _p("subject", proof_rule="np_det_n"), _a("then", "ADV"), _a("be", "COPULA", vform="finite", number="singular"),
        _a("what", "WH-NOM", free_relative="true"), _subject("receiver"), _a("has", "HAVE", vform="finite"),
        _b("received", "V", "ed", "transitive"), _a("from", "PREP", lemma_in="from"),
    ))
    if m["surname"] is None:
        part(m, 1, (("source", "NP", "proper-phrase", {}),))
    else:
        title = "title" if m["title"] else "title_bare"
        part(m, 1, (_scoped(title, "TITLE", honorific="true"),))
        if title == "title":
            mark("ABBREVIATION-STOP", m.end(title) + 1, m.end(title) + 2)
        part(m, 1, (_a("surname", "PROPER-NOUN"),))
    part(m, 1, (
        _punct("stop1", "SPEECH-STOP"), _subject("i"),
        _a("am", "COPULA", vform="finite"), _a("attribute", "ADJ"), _punct("stop2", "SPEECH-STOP"),
        _a("but", "COORD"), _a("what2", "WH-PRONOUN", wh="true"), _a("does", "AUX", vform="finite", lemma_in="do"),
        _subject("speaker"), _b("say", "V", "base"), _a("of", "PREP"), _p("topic", proof_rule="np_det_n"),
        _punct("stop3", "SPEECH-STOP"),
    ))
    mark("CLOSE-QUOTE", len(text)-1, len(text))
    return specs


CONCESSIVE_NEGATIVE_OBSERVATION = "structural_negative_perfect_concession_and_perceived_attempt"
RESUMED_EXCLAMATIVE = "structural_left_dislocated_consequence_and_resumptive_exclamation"

_CONCESSIVE_NEGATIVE = re.compile(
    r"(?P<subject>They|We|You|He|She|I) +(?P<had>had) +(?P<never>never) +(?P<minimum>so much as) +"
    r"(?P<looked>looked|glanced) +(?P<direction>at|toward|towards) +"
    r"(?P<regarded>(?:our|your|their|his|her|my) +(?:fallen|injured|wounded) +(?:comrade|companion|friend))(?P<comma1>,) +"
    rf"(?P<though>though|although) +(?P<subject2>{_LOWER_PRON}) +(?P<was>was|were) +"
    r"(?P<not>not) +(?P<state>dead|asleep|unconscious)(?P<comma2>,) +(?P<and>and) +"
    rf"(?P<observer>{_LOWER_PRON}) +(?P<could>could|might) +(?P<see>see|hear|watch) +"
    r"(?P<object>him|her|them|you|me|us) +(?P<trying>trying|attempting|struggling) +(?P<to>to) +"
    r"(?P<crawl>crawl|creep|walk|run) +(?P<away>away)" + _STOP
)


def plan_concessive_negative(text, components):
    m = _CONCESSIVE_NEGATIVE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if m["was"] != ("were" if m["subject2"] in {"we", "they", "you"} else "was"):
        return None
    return _parts(m, (
        _subject("subject"), _a("had", "HAVE", vform="finite"), _a("never", "DEGREE", negation="true"),
        _scoped("minimum", "DEGREE", emphatic_minimum="true"), _b("looked", "V", "ed"),
        _a("direction", "PREP", lemma_in="at|toward"), _p("regarded", proof_rule="np_poss"), _punct("comma1"),
        _scoped("though", "CONJ", concessive="true"), _subject("subject2"), _a("was", "COPULA", vform="finite"),
        _a("not", "NEG", negation="true"), _a("state", "ADJ"), _punct("comma2"),
        _a("and", "COORD", lemma_in="and"), _subject("observer"), _a("could", "MODAL"),
        _b("see", "V", "base", "transitive"), _p("object"),
        _scoped("trying", "V", **_v("ing", "subject_control")), _a("to", "TO"),
        _b("crawl", "V", "base", "intransitive"), _a("away", "PARTICLE", lemma_in="away"), *_marked(),
    ))


_RESUMED_EXCLAMATIVE = re.compile(
    r"(?P<the>The) +(?P<consequence>mischief|harm|damage) +(?P<of>of) +"
    r"(?P<cause1>neglect|silence|carelessness) +(?P<and>and) +(?P<quality>mistaken|constant|blind) +"
    r"(?P<cause2>indulgence|lenience|approval) +(?P<toward>toward|towards) +"
    r"(?P<such>such) +(?P<a>a) +(?P<girl>girl|boy|child|person)(?P<dash>--|—) *(?P<oh>oh|Oh)(?P<excl>!) +"
    rf"(?P<how>how|How) +(?P<degree>acutely|keenly|deeply) +(?P<did>did) +(?P<subject>{_LOWER_PRON}) +"
    r"(?P<now>now|then) +(?P<felt>feel|regret|sense) +(?P<it>it)(?P<stop>!)"
)


def plan_resumed_exclamative(text, components):
    m = _RESUMED_EXCLAMATIVE.fullmatch(text)
    if m is None or any(c["function"] in {"direct_speech", "reporting_clause"} for c in components):
        return None
    return _parts(m, (
        _a("the", "DET"), _a("consequence", "N", number="singular"), _a("of", "PREP", nominal_complement="of"),
        _a("cause1", "N"), _a("and", "COORD", lemma_in="and"), _a("quality", "ADJ"), _a("cause2", "N"),
        _a("toward", "PREP", lemma_in="toward"), _a("such", "DEGREE"), _a("a", "DET", number="singular"),
        _a("girl", "N", number="singular"), _punct("dash", "DASH"), _scoped("oh", "INTERJECTION", deictic_exclamation="true"),
        _punct("excl", "SPEECH-STOP"), _a("how", "WH-NOM", wh_adverbial="true"), _a("degree", "ADV"), _a("did", "AUX", vform="finite", lemma_in="do"),
        _subject("subject"), _a("now", "ADV"), _b("felt", "V", "base", "transitive"), _p("it"), *_marked(),
    ))


EMBEDDED_FEELING_COMPARISON = "structural_embedded_feeling_with_temporal_perception_and_equative"
CAUSATIVE_EVIDENTIAL_PURPOSE = "structural_causative_with_evidential_incise_and_depictive_purpose"
PASSIVE_KNOWLEDGE_EXCEPTION = "structural_domain_fronted_perfect_passive_with_free_relative_exception"
SPLIT_REPORTED_PLEASURE = "dialogue_structural_split_reported_pleasure_with_control_and_hope"

_FEELING_COMPARISON = re.compile(
    rf"(?P<subject>{_SUBJECT}) +(?P<modal>may|might|can|could) +"
    r"(?P<imagine>imagine|guess|understand) +(?P<how>how) +"
    rf"(?P<feeler>{_LOWER_PRON}) +(?P<felt>felt) +(?P<when>when) +"
    rf"(?P<hearer>{_LOWER_PRON}) +(?P<heard>heard|saw|watched) +"
    r"(?P<perceived>(?:this|that|the) +(?:[a-z-]+ +){0,3}[a-z-]+) +"
    r"(?P<addressing>addressing|greeting|entreating|comforting) +"
    rf"(?P<addressed>another|me|him|her|them|us|you|{_NOM}) +"
    r"(?P<in>in) +(?P<the>the) +(?P<very>very) +(?P<same>same) +"
    r"(?P<words>words|phrases|terms) +(?P<of>of) +(?P<register>[a-z-]+) +"
    rf"(?P<as>as) +(?P<speaker>{_LOWER_PRON}) +(?P<had>had) +(?P<used>used) +"
    r"(?P<to>to) +(?P<recipient>me|him|her|us|them|you|myself|yourself|ourselves)"
    + _STOP
)


def plan_embedded_feeling_comparison(text, components):
    m = _FEELING_COMPARISON.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _subject("subject"), _a("modal", "MODAL"), _b("imagine", "V", "base", "clausal"),
        _a("how", "WH-NOM", wh_adverbial="true"), _subject("feeler"),
        _scoped("felt", "V", **_v("finite", "intransitive", tense="past")),
        _a("when", "CONJ"), _subject("hearer"), _b("heard", "V", "finite", "transitive"),
        _p("perceived", simple_nominal_proof="true"),
        _b("addressing", "V", "ing", "transitive"),
        (_scoped("addressed", "LADDER-INDEF-PRON", indefinite="true") if m["addressed"] == "another" else _p("addressed")),
        _a("in", "PREP", lemma_in="in"), _a("the", "DET", number="plural"),
        _a("very", "DEGREE"), _a("same", "ADJ"), _a("words", "N", number="plural"),
        _a("of", "PREP", nominal_complement="of"), _a("register", "N"),
        _a("as", "EQUATIVE-AS", degree="true"), _subject("speaker"),
        _a("had", "HAVE", vform="finite"), _b("used", "V", "ed", "transitive"),
        _a("to", "PREP", lemma_in="to"), _p("recipient"), *_marked(),
    ))


_CAUSATIVE_PURPOSE = re.compile(
    r"(?P<causer>(?:The|A|My|Their) +(?:[a-z-]+ +){0,2}[a-z-]+) +"
    r"(?P<made>made|let) +(?P<causee>him|her|them|me|us|you) +"
    r"(?P<say>say|repeat|read) +(?P<whole>all) +(?P<this>this|that)"
    r"(?P<c1>,) +(?P<knower>I|he|she|we|they) +(?P<knew>knew|believed|suspected)(?P<c2>,) +"
    r"(?P<to>to) +(?P<exhibit>exhibit|show|present) +(?P<exhibited>him|her|them|me|us|you) +"
    r"(?P<to2>to) +(?P<recipient>me|him|her|us|them|you) +"
    r"(?P<in>in) +(?P<light>the +(?>light|manner|guise)) +"
    rf"(?P<indicater>{_LOWER_PRON}) +(?P<had>had) +(?P<indicated>indicated|described|suggested) +"
    r"(?P<on>on) +(?P<night>the +(?:night|evening|morning|day)) +"
    rf"(?P<when>when) +(?P<actor>{_LOWER_PRON}) +(?P<acted>[a-z-]+) +(?P<affected>{_NOM})"
    + _STOP
)


def plan_causative_evidential_purpose(text, components):
    m = _CAUSATIVE_PURPOSE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    return _parts(m, (
        _p("causer", simple_nominal_proof="true"),
        _scoped("made", "V", **_v("finite", "object_control", tense="past")),
        _p("causee"), _b("say", "V", "base", "transitive"),
        _a("whole", "DET", definiteness="universal"), _p("this"), _punct("c1"), _subject("knower"),
        _b("knew", "V", "finite", "clausal"), _punct("c2"),
        _a("to", "TO"), _b("exhibit", "V", "base", "transitive"), _p("exhibited"),
        _a("to2", "PREP", lemma_in="to"), _p("recipient"), _a("in", "PREP", lemma_in="in"),
        _p("light", proof_rule="np_det_n"), _subject("indicater"), _a("had", "HAVE", vform="finite"),
        _b("indicated", "V", "ed", "transitive"), _a("on", "PREP", lemma_in="on"),
        _p("night", proof_rule="np_det_n"), _a("when", "CONJ"), _subject("actor"),
        _b("acted", "V", "finite", "transitive", nonbase_surface="true"),
        _p("affected", grounded_object_proof="true"), *_marked(),
    ))


_KNOWLEDGE_EXCEPTION = re.compile(
    rf"(?P<of>Of) +(?P<domain>(?:his|her|their|our|your) +(?:former|early|previous|private) +{_NOM}) +"
    r"(?P<nothing>nothing|little) +(?P<had>had) +(?P<been>been) +(?P<known>known|learned|recorded) +"
    rf"(?P<in>in) +(?P<place>{_NAME}) +(?P<but>but|except) +(?P<what>what) +"
    r"(?P<teller>he|she|they) +(?P<told>told|said|mentioned) +(?P<self>himself|herself|themselves)"
    + _STOP
)


def plan_passive_knowledge_exception(text, components):
    m = _KNOWLEDGE_EXCEPTION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if m["self"] != {"he": "himself", "she": "herself", "they": "themselves"}[m["teller"]]:
        return None
    return _parts(m, (
        _a("of", "PREP", lemma_in="of"), _p("domain", proof_rule="np_poss"),
        _p("nothing"), _a("had", "HAVE", vform="finite"), _a("been", "AUX-BE", vform="ed"),
        _b("known", "V", "ed", "transitive"), _a("in", "PREP", lemma_in="in"),
        ("place", "NP", "proper-phrase", {}), _scoped("but", "PREP", exceptive="true"),
        _a("what", "WH-NOM", free_relative="true"), _subject("teller"),
        _b("told", "V", "finite", "transitive"),
        _a("self", "EMPHATIC-REFLEXIVE", reflexive="true"),
        _a("self", "PRONOUN", reflexive="true"), *_marked(),
    ))


_PLEASURE_FIRST = re.compile(
    r"(?P<in>In) +(?P<activity>nursing|helping|visiting|comforting) +"
    rf"(?P<kin>(?:your|his|her|their) +[a-z-]+) +(?P<speaker>I) +(?P<am>am) +"
    r"(?P<sure>sure|certain|confident) +(?P<pleased>you|he|she|they) +"
    r"(?P<have>have|has) +(?P<pleasure>pleasure|delight|satisfaction)(?P<comma>,)"
)
_PLEASURE_TAG = re.compile(rf"(?P<said>said|replied|added) +(?P<reporter>{_NAME})")
_PLEASURE_SECOND = re.compile(
    r"(?P<and>and) +(?P<speaker>I) +(?P<hope>hope|trust) +(?P<it>it) +"
    r"(?P<modal>will|would|may|might) +(?P<be>be) +(?P<soon>soon|gradually|shortly) +"
    r"(?P<increased>increased|renewed|restored|doubled) +(?P<by>by) +"
    r"(?P<seeing>seeing|finding) +(?P<patient>her|him|them|you) +"
    r"(?P<degree>quite|completely|fully) +(?P<well>well|recovered|content)" + _STOP
)


def plan_split_reported_pleasure(text, components):
    """Validate original quote/tag adjacency before composing either speech part."""
    quotes = [c for c in components if c["function"] == "direct_speech"]
    tags = [c for c in components if c["function"] == "reporting_clause"]
    turns = [c for c in components if c["function"] == "split_direct_speech_turn"]
    if len(quotes) != 2 or len(tags) != 1 or len(turns) != 1:
        return None
    head, tail = quotes
    tag, = tags
    turn, = turns
    end = head["end"]
    resume = tail["start"]
    start_tag, end_tag = tag["start"], tag["end"]
    if (
        head["start"] != 0 or tail["end"] != len(text)
        or head.get("governor") != tag["id"] or tail.get("governor") != head["id"]
        or tail.get("relation") != "resumption_of_split_speech" or tag.get("governor") != turn["id"]
        or not (1 < end <= start_tag < end_tag < resume < len(text) - 1)
        or text[end:start_tag].strip() or text[end_tag:resume].strip() != ";"
    ):
        return None
    first = _PLEASURE_FIRST.fullmatch(text[1:end - 1])
    report = _PLEASURE_TAG.fullmatch(text[start_tag:end_tag])
    second = _PLEASURE_SECOND.fullmatch(text[resume + 1:-1])
    if first is None or report is None or second is None:
        return None
    if first["have"] != ("has" if first["pleased"] in {"he", "she"} else "have"):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(first, 1, (
        _a("in", "PREP", lemma_in="in"), _b("activity", "V", "ing", "transitive"),
        _p("kin", proof_rule="np_poss"), _subject("speaker"), _a("am", "COPULA", vform="finite"),
        _a("sure", "ADJ"), _subject("pleased"), _a("have", "HAVE", vform="finite"),
        _a("pleasure", "N", number="singular"), _punct("comma"),
    ))
    mark("CLOSE-QUOTE", end - 1, end)
    part(report, start_tag, (
        _b("said", "V", "finite", "clausal"), ("reporter", "NP", "proper-phrase", {}),
    ))
    semi = text.index(";", end_tag, resume)
    mark("SEMICOLON", semi, semi + 1)
    mark("OPEN-QUOTE", resume, resume + 1)
    part(second, resume + 1, (
        _a("and", "COORD", lemma_in="and"), _subject("speaker"), _b("hope", "V", "base", "clausal"),
        _p("it"), _a("modal", "MODAL"), _scoped("be", "AUX-BE", vform="base", voice="passive"),
        _a("soon", "ADV"), _b("increased", "V", "ed", "transitive"), _a("by", "PREP-BY"),
        _b("seeing", "V", "ing", "transitive"), _p("patient"),
        _a("degree", "ADV"), _scoped("well", "ADJ", depictive_state="true"), *_marked(),
    ))
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return specs


NARRATIVE_PLANS = (
    (EMBEDDED_FEELING_COMPARISON, plan_embedded_feeling_comparison),
    (CAUSATIVE_EVIDENTIAL_PURPOSE, plan_causative_evidential_purpose),
    (PASSIVE_KNOWLEDGE_EXCEPTION, plan_passive_knowledge_exception),
    (CONCESSIVE_NEGATIVE_OBSERVATION, plan_concessive_negative),
    (RESUMED_EXCLAMATIVE, plan_resumed_exclamative),
    (EXISTENTIAL_AND_REMAINDER, plan_existential_and_remainder),
    (REACTION_RESULT, plan_reaction_result),
    (NEGATED_MISGIVING, plan_negated_misgiving),
    (SHARED_START_CONTROL, plan_shared_start_control),
    (PERCEPTION_AND_REPLY, plan_perception_and_reply),
    (REPORTED_NOMINAL_SERIES, plan_reported_nominal_series),
    (EXISTENTIAL_RELATIVE_FOCUS, plan_existential_relative_focus),
    (PARTITIVE_PASSAGE, plan_partitive_passage),
    (COMPARATIVE_EXTRAPOSITION, plan_comparative_extraposition),
    (FOCUSED_CLEFT, plan_focused_cleft),
    (EVENT_RELATIVE, plan_event_relative),
    (SHARED_CONTACT, plan_shared_contact),
    (SCENE_LOCATION, plan_scene_location),
    (FRONTED_PERCEPTION, plan_fronted_perception),
    (EXCEPTED_SOUND, plan_excepted_sound),
    (TRIPLE_PASSIVE, plan_triple_passive),
    (NAMED_COURT, plan_named_court),
    (INVERTED_EFFECT, plan_inverted_effect),
    (ALARM_INVERSION, plan_alarm_inversion),
    (TOPIC_RELATIVE, plan_topic_relative),
    (COORDINATED_SIGHT, plan_coordinated_sight),
    (STIRRED_ATTITUDE, plan_stirred_attitude),
    (RIDDEN_MEANS, plan_ridden_means),
    (TIMED_DECISION, plan_timed_decision),
    (SHARED_GAZE, plan_shared_gaze),
    (TIMED_REPORT, plan_timed_report),
    (REACTION_TIME, plan_reaction_time),
    (CERTAIN_NEGATION, plan_certain_negation),
    (REACTION_DEGREE, plan_reaction_degree),
    (ENDED_STATE, plan_ended_state),
)
SPEECH_SEQUENCE_PLANS = (
    (SPLIT_REPORTED_PLEASURE, plan_split_reported_pleasure),
    (TWO_QUESTIONS_PASSIVE, plan_two_questions_passive),
    (REPORTED_THREE_ACTS, plan_reported_three_acts),
)
SPEECH_PLANS = (
    (REPORTED_NEGATIVE_VOCATIVE, plan_reported_negative_vocative),
    (QUOTED_CONDITION_THEN_ACTION, plan_quoted_condition_then_action),
    (REPORTED_COORDINATE_NEGATION, plan_reported_coordinate_negation),
    (CONDITIONAL_HOPE, plan_conditional_hope),
    (CONDITIONAL_EVALUATION, plan_conditional_evaluation),
    (TWO_MINOR_ACTS, plan_two_minor_acts),
    (ADJECTIVAL_ECHO, plan_adjectival_echo),
    (NAMED_VOCATIVE, plan_named_vocative),
    (BELIEF_VOCATIVE, plan_belief_vocative),
    (MODAL_RESTORATION, plan_modal_restoration),
    (OATH_REPORT, plan_oath_report),
    (NAUTICAL_CALL, plan_nautical_call),
    (REPORTED_SURE, plan_reported_sure),
    (POSSIBILITY_QUESTION, plan_possibility_question),
)
CLAUSE_COUNTS = {
    EMBEDDED_FEELING_COMPARISON: 4, CAUSATIVE_EVIDENTIAL_PURPOSE: 4,
    PASSIVE_KNOWLEDGE_EXCEPTION: 2, SPLIT_REPORTED_PLEASURE: 4,
    CONCESSIVE_NEGATIVE_OBSERVATION: 3, RESUMED_EXCLAMATIVE: 1,
    EXISTENTIAL_AND_REMAINDER: 2, REACTION_RESULT: 3, NEGATED_MISGIVING: 2, REPORTED_THREE_ACTS: 3,
    SHARED_START_CONTROL: 2, PERCEPTION_AND_REPLY: 3, REPORTED_NOMINAL_SERIES: 2,
    EXISTENTIAL_RELATIVE_FOCUS: 3, TWO_QUESTIONS_PASSIVE: 3, PARTITIVE_PASSAGE: 2,
    REPORTED_NEGATIVE_VOCATIVE: 0,
    QUOTED_CONDITION_THEN_ACTION: 3, REPORTED_COORDINATE_NEGATION: 3,
    COMPARATIVE_EXTRAPOSITION: 1, FOCUSED_CLEFT: 2, EVENT_RELATIVE: 3,
    SHARED_CONTACT: 1, SCENE_LOCATION: 1, FRONTED_PERCEPTION: 2,
    CONDITIONAL_HOPE: 2, CONDITIONAL_EVALUATION: 2,
    EXCEPTED_SOUND: 1, TRIPLE_PASSIVE: 3, NAMED_COURT: 1, INVERTED_EFFECT: 1,
    TWO_MINOR_ACTS: 0, ADJECTIVAL_ECHO: 0, NAMED_VOCATIVE: 1, BELIEF_VOCATIVE: 1, MODAL_RESTORATION: 1,
    ALARM_INVERSION: 3, TOPIC_RELATIVE: 3, COORDINATED_SIGHT: 1, STIRRED_ATTITUDE: 1, OATH_REPORT: 1,
    **dict.fromkeys((RIDDEN_MEANS, TIMED_DECISION, SHARED_GAZE, CERTAIN_NEGATION,
                     REACTION_DEGREE, ENDED_STATE, REPORTED_SURE), 1),
    TIMED_REPORT: 3, REACTION_TIME: 4, NAUTICAL_CALL: 0, POSSIBILITY_QUESTION: 2,
}
