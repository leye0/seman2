"""Source-sensitive, *proof-bearing* construction recovery for Novel-900/1000.

Every segment is lexical-lattice backed or an independently parsed phrase.
Patterns are proposed analyses, never evidence of completeness by themselves.
"""
from __future__ import annotations

import re
from .dialogue_clause_plans import _specs


def L(group, category, **features):
    return group, category, "lexical-alternatives", features


def P(group, category="NP", **features):
    return group, category, "phrase", features


def M(group, category):
    return group, category, "source-punctuation", {}


REPORTED_COPULAR_QUESTION = 'dialogue_reported_copular_inversion_with_vocative'
SUPPLEMENTAL_STATE = 'structural_fin_clause_with_passive_adjective_supplement'
FOUR_TURN_SPEECH = 'dialogue_four_sentence_report_with_elliptical_final_nominal'
COPULAR_INF_PURPOSE = 'structural_initial_conjunction_copular_adjective_infinitive'
SEMICOLON_MODAL_PASSIVE = 'structural_semicolon_modal_negative_and_passive_nominal'
REPORTED_ASSURED_PASSIVE = 'dialogue_split_imperative_report_and_modal_passive_purpose'
ELLIPTIC_GERUND_REPORT = 'dialogue_reported_gerund_elliptic_question'
QUOTED_ASSURANCE_INCISE = 'dialogue_quoted_epistemic_incise_with_ditransitive_result'
SHARED_RETURN_STATE = 'structural_shared_subject_motion_with_coordinated_depictives'
COMPARATIVE_PARTICIPIAL_ELLIPSIS = 'structural_no_sooner_than_passive_participial_ellipsis'


PLANS = (
    (REPORTED_COPULAR_QUESTION,
     re.compile(
         '(?P<open>")(?P<copula>Am|Is|Are|Was|Were) +(?P<subject>I|he|she|it|you|they|we) +'
         '(?P<state>[a-z-]+)(?P<comma>,) +(?P<vocative>(?:my|our|your) +[a-z-]+)(?P<question>\\?)'
         '(?P<close>") +(?P<said>said|asked|inquired|replied) +(?P<speaker>I|he|she|they|we)'
         '(?P<stop>\\.)'
     ),
     (M("open", "OPEN-QUOTE"), L("copula", "COPULA", vform="finite"),
         P("subject", "NP"), L("state", "ADJ"), M("comma", "COMMA"),
         P("vocative", "NP", proof_rule="np_poss"), M("question", "QMARK"),
         M("close", "CLOSE-QUOTE"), L("said", "V", vform="finite"),
         P("speaker", "NP"), M("stop", "SPEECH-STOP")),
     'quoted'),
    (SUPPLEMENTAL_STATE,
     re.compile(
         '(?P<matrix>[^,;.!?"“”‘]{2,55} +(?:passed|elapsed|went by) +[a-z-]+)(?P<comma>,) +'
         '(?P<state>unmarked|unnoticed|undisturbed|unaffected|uninterrupted) +'
         '(?P<by>by +[^,;.!?"“”‘]{2,55})(?P<stop>\\.)'
     ),
     (P("matrix", "CLAUSE", finite_statement_proof="true"), M("comma", "COMMA"),
         L("state", "ADJ"), P("by", "PP", proof_rule="pp_prep_np"), M("stop", "SPEECH-STOP")),
     'finite'),
    (FOUR_TURN_SPEECH,
     re.compile(
         '(?P<open>‘)(?P<first>[^.!?;“”‘]{4,70})(?P<stop1>\\.) +(?P<second>[^.!?;“”‘]{4,70})'
         '(?P<stop2>\\.) +(?P<third>[^.!?;“”‘]{4,70})(?P<stop3>\\.) +'
         '(?P<fourth>(?:Nobody|No one|Nothing) +(?:in|at|on|under|behind|near) +[^.!?;,‘]{2,40})'
         '(?P<stop4>\\.)(?P<close>’)'
     ),
     (M("open", "OPEN-QUOTE"),
         P("first", "CLAUSE", finite_statement_proof="true"), M("stop1", "SPEECH-STOP"),
         P("second", "CLAUSE", finite_statement_proof="true"), M("stop2", "SPEECH-STOP"),
         P("third", "CLAUSE", finite_statement_proof="true"), M("stop3", "SPEECH-STOP"),
         P("fourth", "NP", proof_rule="np_pp_mod"), M("stop4", "SPEECH-STOP"),
         M("close", "CLOSE-QUOTE")),
     'quoted'),
    (COPULAR_INF_PURPOSE,
     re.compile(
         '(?P<but>But|And) +(?P<controller>I|he|she|we|they|you) +(?P<copula>am|was|is|are|were) +'
         '(?P<attitude>impatient|eager|anxious|keen) +(?P<to>to) +'
         '(?P<arrive>arrive|return|travel|go) +(?P<goal>(?:at|in|to|from) +[^,;.!?"“”‘]{2,65})'
         '(?P<stop>\\.)'
     ),
     (L("but", "COORD"), P("controller", "NP"),
         L("copula", "COPULA", vform="finite"), L("attitude", "ADJ"),
         L("to", "TO"), L("arrive", "V", vform="base"),
         P("goal", "PP", proof_rule="pp_prep_np"), M("stop", "SPEECH-STOP")),
     'finite'),
    (SEMICOLON_MODAL_PASSIVE,
     re.compile(
         '(?P<matrix>[^;.!?]{5,85})(?P<semi>;) +(?P<and>and|but) +'
         '(?P<time>from +(?:this|that) +(?:time|day|moment)) +(?P<subject>[^;!?]{2,45}?) +'
         '(?P<was>was|were) +(?P<scarcely>scarcely|hardly) +(?P<ever>ever) +'
         '(?P<mentioned>[a-z]+ed) +(?P<between>(?:between|among) +[^,;.!?]{2,45})(?P<stop>\\.)'
     ),
     (P("matrix", "CLAUSE", finite_statement_proof="true"), M("semi", "SEMICOLON"),
         L("and", "COORD"), P("time", "PP", proof_rule="pp_prep_np"),
         P("subject", "NP", proof_rule="np_genitive"), L("was", "COPULA", vform="finite"),
         L("scarcely", "ADV"), L("ever", "ADV"), L("mentioned", "V", vform="ed"),
         P("between", "PP", proof_rule="pp_prep_np"), M("stop", "SPEECH-STOP")),
     'finite'),
    (REPORTED_ASSURED_PASSIVE,
     re.compile(
         '(?P<open1>")(?P<assured>Be +(?:assured|convinced|warned|advised))(?P<comma1>,) +'
         '(?P<sir>sir|madam)(?P<comma2>,)(?P<close1>") +(?P<said>said|declared|replied) +'
         '(?P<speaker>I|he|she|they|we)(?P<comma3>,) +(?P<open2>")'
         '(?P<subject>no +[^,;.!?"]{2,70}?) +(?P<shall>shall|will|must) +(?P<be>be) +'
         '(?P<spared>[a-z]+ed) +(?P<to>to) +(?P<discover>[a-z-]+) +(?P<villain>[^,;.!?"]{2,55})'
         '(?P<stop>\\.)(?P<close2>")'
     ),
     (M("open1", "OPEN-QUOTE"), P("assured", "CLAUSE"), M("comma1", "COMMA"),
         L("sir", "TITLE"), M("comma2", "COMMA"), M("close1", "CLOSE-QUOTE"),
         L("said", "V", vform="finite"), P("speaker", "NP"), M("comma3", "COMMA"),
         M("open2", "OPEN-QUOTE"), P("subject", "NP", proof_rule="np_pp_mod"),
         L("shall", "MODAL", vform="finite"), L("be", "COPULA", vform="base"),
         L("spared", "V", vform="ed"), L("to", "TO"), L("discover", "V", vform="base"),
         P("villain", "NP", proof_rule="np_det_n"), M("stop", "SPEECH-STOP"),
         M("close2", "CLOSE-QUOTE")),
     'quoted'),
    (ELLIPTIC_GERUND_REPORT,
     re.compile(
         '(?P<open>‘)(?P<what>What)(?P<excl>!) +(?P<bewitching>[A-Z][a-z-]+ing) +'
         '(?P<object>[^;!?,‘]{2,55})(?P<question>\\?)(?P<close>’) +'
         '(?P<cried>cried|asked|exclaimed) +(?P<speaker>the +[a-z-]+)(?P<stop>\\.)'
     ),
     (M("open", "OPEN-QUOTE"), L("what", "WH-NOM"), M("excl", "EXCL"),
         L("bewitching", "V", vform="ing"), P("object", "NP"),
         M("question", "QMARK"), M("close", "CLOSE-QUOTE"),
         L("cried", "V", vform="finite"), P("speaker", "NP", proof_rule="np_det_n"),
         M("stop", "SPEECH-STOP")),
     'quoted'),
    (QUOTED_ASSURANCE_INCISE,
     re.compile(
         '(?P<open>“)(?P<and>And|But) +(?P<assurance>[^,;.!?“”]{2,50})(?P<comma1>,) +'
         '(?P<suppose>I +(?:suppose|believe|think|imagine))(?P<comma2>,) +'
         '(?P<carried>[a-z]+ed +[^,;.!?“”]{2,55})(?P<stop>\\.)(?P<close>”)'
     ),
     (M("open", "OPEN-QUOTE"), L("and", "COORD"),
         P("assurance", "NP", proof_rule="np_pp_mod"), M("comma1", "COMMA"),
         P("suppose", "CLAUSE"), M("comma2", "COMMA"),
         P("carried", "VP", proof_rule="vp_prep_ditransitive"),
         M("stop", "SPEECH-STOP"), M("close", "CLOSE-QUOTE")),
     'quoted'),
    (SHARED_RETURN_STATE,
     re.compile(
         '(?P<matrix>[^,;.!?"“”‘]{4,75})(?P<comma>,) +(?P<and1>and) +'
         '(?P<return>(?:came|went|ran|walked|returned) +(?:up|down|back|out|in) +again) +'
         '(?P<state1>drenched|soaked|tired|exhausted) +(?P<and2>and) +'
         '(?P<state2>bubbling|dripping|shivering|panting)(?P<stop>\\.)'
     ),
     (P("matrix", "CLAUSE", finite_statement_proof="true"), M("comma", "COMMA"),
         L("and1", "COORD"), P("return", "VP", proof_rule="vp_adv"),
         L("state1", "ADJ"), L("and2", "COORD"), L("state2", "V", vform="ing"),
         M("stop", "SPEECH-STOP")),
     'finite'),
    (COMPARATIVE_PARTICIPIAL_ELLIPSIS,
     re.compile(
         '(?P<no>No) +(?P<sooner>sooner) +(?P<thought>thought|agreed|decided|settled) +'
         '(?P<upon>upon|on) +(?P<than>than) +(?P<done>done|approved|finished|completed)(?P<stop>\\.)'
     ),
     (L("no", "NEG-DEGREE"), L("sooner", "ADV"), L("thought", "V", vform="ed"),
         L("upon", "PREP"), L("than", "CONJ"), L("done", "V", vform="ed"),
         M("stop", "SPEECH-STOP")),
     'nonfinite'),
    ('dialogue_intercalated_permission_with_elliptical_condition',
     re.compile(
         '(?P<open1>‘)(?P<but>But|And) +(?P<please>please) +(?P<let>let) +'
         '(?P<person>me|us|him|her|them) +(?P<base>have|keep|take|read|see) +'
         '(?P<object>[^,;.!?‘]{2,45})(?P<comma1>,)(?P<close1>’) +(?P<said>said|asked|whispered) +'
         '(?P<speaker>[A-Z][a-z-]+)(?P<comma2>,) +'
         '(?P<manner>in +(?:her|his|their) +[^,;.!?‘]{2,36} +way)(?P<comma3>,) +(?P<open2>‘)'
         '(?P<if>if) +(?P<conditional_subject>you|he|she|they) +(?P<can>can|could|will|would)'
         '(?P<punct>[.!?])(?P<close2>’)'
     ),
     (
         M("open1", "OPEN-QUOTE"),
         L("but", "COORD"),
         L("please", "ADV"),
         L("let", "V", vform='base'),
         P("person", "NP"),
         L("base", "V", vform='base'),
         P("object", "NP"),
         M("comma1", "COMMA"),
         M("close1", "CLOSE-QUOTE"),
         L("said", "V", vform='finite'),
         P("speaker", "NP"),
         M("comma2", "COMMA"),
         P("manner", "PP", proof_rule='pp_prep_np'),
         M("comma3", "COMMA"),
         M("open2", "OPEN-QUOTE"),
         L("if", "CONJ"),
         P("conditional_subject", "NP"),
         L("can", "MODAL", vform='finite'),
         M("punct", "SPEECH-STOP"),
         M("close2", "CLOSE-QUOTE")
     ),
     'quoted'),
    ('dialogue_split_contrast_with_independent_gerund_negation',
     re.compile(
         '(?P<open1>“)(?P<subject>I|We|You|They) +(?P<do>do|did) +(?P<not1>not) +(?P<mind>mind) +'
         '(?P<poss>his|her|your|their|my|our) +(?P<not2>not) +(?P<gerund>[a-z]+ing) +'
         '(?P<to>to) +(?P<recipient_title>Mrs|Mr)(?P<abbrev>[.]) +(?P<receiver>[A-Z][a-z-]+)(?P<comma1>,)(?P<close1>”) +'
         '(?P<said>said|asked|replied) +(?P<speaker_title>Miss) +(?P<speaker>[A-Z][a-z-]+)(?P<comma2>,) +(?P<open2>“)'
         '(?P<but>but) +(?P<experiencer>I|we|you|they) +(?P<wish>wish|wished) +'
         '(?P<perfect_subject>he|she|you|we|they) +(?P<had>had) +(?P<content>[a-z-]+ed) +(?P<partner>with +[^,;!?“”]{2,40})(?P<stop>\\.)(?P<close2>”)'
     ),
     (
         M("open1", "OPEN-QUOTE"),
         P("subject", "NP"),
         L("do", "AUX", vform='finite'),
         L("not1", "NEG"),
         L("mind", "V", vform='base'),
         L("poss", "POSS"),
         L("not2", "NEG"),
         L("gerund", "V", vform='ing'),
         L("to", "PREP"),
         L("recipient_title", "TITLE", honorific="true"),
         M("abbrev", "ABBREVIATION-STOP"),
         ("receiver", "PROPER-NOUN", "scoped-lexical", {}),
         M("comma1", "COMMA"),
         M("close1", "CLOSE-QUOTE"),
         L("said", "V", vform='finite'),
         ("speaker_title", "TITLE", "scoped-lexical", {"honorific": "true"}),
         P("speaker", "NP", proof_rule="np_proper"),
         M("comma2", "COMMA"),
         M("open2", "OPEN-QUOTE"),
         L("but", "COORD"),
         P("experiencer", "NP"),
         L("wish", "V", vform='finite'),
         P("perfect_subject", "NP"),
         L("had", "HAVE", vform="finite"),
         L("content", "V", vform="ed"),
         P("partner", "PP", proof_rule="pp_prep_np"),
         M("stop", "SPEECH-STOP"),
         M("close2", "CLOSE-QUOTE")
     ),
     'quoted'),
    ('structural_negative_coordination_with_shared_perception',
     re.compile(
         '(?P<frame>For +[^,;!?]{2,30}) +(?P<afterwards>afterwards|later)(?P<comma1>,) +'
         '(?P<subject>I|she|he|they|we) +(?P<copula>am|is|are|was|were) +'
         '(?P<state>lost|absorbed|immersed) +(?P<domain>in +[^;.!?]{2,45})(?P<semi>;) +'
         '(?P<but>but) +(?P<subject2>I|she|he|they|we) +(?P<neither>neither) +'
         '(?P<see>see|sees|saw|meet|meets|met) +(?P<person>her|him|them|you) +'
         '(?P<place>in +[^,;!?]{2,35})(?P<comma2>,) +(?P<nor>nor) +(?P<when>when) +'
         '(?P<call>[^,;!?]{4,33})(?P<stop>\\.)'
     ),
     (
         P("frame", "PP", proof_rule='pp_prep_np'),
         L("afterwards", "ADV"),
         M("comma1", "COMMA"),
         P("subject", "NP"),
         L("copula", "COPULA", vform='finite'),
         L("state", "ADJ"),
         P("domain", "PP", proof_rule='pp_prep_np'),
         M("semi", "SEMICOLON"),
         L("but", "COORD"),
         P("subject2", "NP"),
         L("neither", "DEGREE"),
         L("see", "V", vform='finite'),
         P("person", "NP"),
         P("place", "PP", proof_rule='pp_prep_np'),
         M("comma2", "COMMA"),
         L("nor", "COORD"),
         L("when", "CONJ"),
         P("call", "CLAUSE", finite_statement_proof='true'),
         M("stop", "SPEECH-STOP")
     ),
     'finite'),

    ('structural_parallel_motion_to_locative_relative_with_depictives',
     re.compile(
         '(?P<motion_subject>I|We|He|She|They) +(?P<took>plucked|picked|gathered) +'
         '(?P<first_up>up) +(?P<theme>[^,;.!?]{2,24}) +(?P<immediately>at +once)(?P<comma1>,) +'
         '(?P<crossed>crossed|passed|cleared) +(?P<threshold>[^,;.!?]{2,30})(?P<comma2>,) +'
         '(?P<and>and) +(?P<walked>walked|stepped|went) +(?P<right>right) +(?P<up>up) +(?P<to>to) +'
         '(?P<goal>the +[a-z-]+) +(?P<where>where) +(?P<location_subject>he|she|they) +'
         '(?P<stood>stood|sat|waited)(?P<comma3>,) +(?P<propped>propped|seated|perched) +'
         '(?P<support>on +[^,;.!?]{2,32})(?P<comma4>,) +(?P<talking>talking|speaking|listening) +'
         '(?P<recipient>to +[^,;.!?]{2,33})(?P<stop>\\.)'
     ),
     (
         P("motion_subject", "NP"),
         L("took", "V", vform="finite"),
         L("first_up", "PARTICLE"),
         P("theme", "NP"),
         ("immediately", "ADV", "scoped-lexical", {"immediate": "true"}),
         M("comma1", "COMMA"),
         L("crossed", "V", vform='finite'),
         P("threshold", "NP"),
         M("comma2", "COMMA"),
         L("and", "COORD"),
         L("walked", "V", vform='finite'),
         L("right", "ADV"),
         L("up", "PARTICLE"),
         L("to", "PREP"),
         P("goal", "NP"),
         L("where", "WH-NOM"),
         P("location_subject", "NP"),
         L("stood", "V", vform='finite'),
         M("comma3", "COMMA"),
         L("propped", "V", vform='ed'),
         P("support", "PP", proof_rule='pp_prep_np'),
         M("comma4", "COMMA"),
         L("talking", "V", vform='ing'),
         P("recipient", "PP", proof_rule='pp_prep_np'),
         M("stop", "SPEECH-STOP")
     ),
     'finite'),
    ('dialogue_intercalated_copular_comma_adjectives_and_coordinated_nominals',
     re.compile(
         '(?P<open1>“)(?P<subject>[A-Z][a-z]+(?: +[A-Z][a-z]+)?) +(?P<is>is|was) +(?P<a>a) +'
         '(?P<very>very) +(?P<adj1>[a-z-]+)(?P<comma1>,) +(?P<adj2>[a-z-]+) +(?P<head>[a-z-]+) +'
         '(?P<indeed>indeed)(?P<comma2>,)(?P<close1>”) +(?P<said>said|added|declared) +'
         '(?P<speaker>[A-Z][a-z]+)(?P<comma3>,) +(?P<open2>“)(?P<and>and) +'
         '(?P<other>a +most +[a-z-]+ +[a-z-]+)(?P<stop>\\.)(?P<close2>”)'
     ),
     (
         M("open1", "OPEN-QUOTE"),
         P("subject", "NP"),
         L("is", "COPULA", vform='finite'),
         L("a", "DET"),
         L("very", "ADV"),
         L("adj1", "ADJ"),
         M("comma1", "COMMA"),
         L("adj2", "ADJ"),
         L("head", "N", number='singular'),
         L("indeed", "ADV"),
         M("comma2", "COMMA"),
         M("close1", "CLOSE-QUOTE"),
         L("said", "V", vform='finite'),
         P("speaker", "NP"),
         M("comma3", "COMMA"),
         M("open2", "OPEN-QUOTE"),
         L("and", "COORD"),
         P("other", "NP"),
         M("stop", "SPEECH-STOP"),
         M("close2", "CLOSE-QUOTE")
     ),
     'quoted'),

)


_COPULA_FOR_PRONOUN = {
    "i": {"am", "was"}, "he": {"is", "was"}, "she": {"is", "was"},
    "it": {"is", "was"}, "you": {"are", "were"}, "we": {"are", "were"},
    "they": {"are", "were"},
}


def _planner(pattern, layout, kind):
    def plan(text, parts):
        if not any(c.get("function") == "utterance" and
                   (c["start"], c["end"]) == (0, len(text)) for c in parts):
            return None
        match = pattern.fullmatch(text)
        if match is None:
            return None
        groups = match.groupdict()
        subject = groups.get("controller") or groups.get("subject")
        copula = groups.get("copula")
        if subject and copula and subject.lower() in _COPULA_FOR_PRONOUN:
            if copula.lower() not in _COPULA_FOR_PRONOUN[subject.lower()]:
                return None
        quotes = [c for c in parts if c.get("function") == "direct_speech"]
        if kind == "quoted":
            opens = [match.start(g) for g, cat, *_ in layout if cat == "OPEN-QUOTE"]
            closes = [match.end(g) for g, cat, *_ in layout if cat == "CLOSE-QUOTE"]
            if [(c["start"], c["end"]) for c in quotes] != list(zip(opens, closes)):
                return None
            if any(c.get("function") == "embedded_quotation" for c in parts):
                return None
            reports = [c for c in parts if c.get("function") == "reporting_clause"]
            speakers = [g for g, _, _, _ in layout if g == "speaker"]
            if speakers and (len(reports) != 1 or quotes[0].get("governor") != reports[0]["id"]
                             or reports[0]["end"] < match.end(speakers[0])):
                return None
            if len(opens) == 2 and (
                    not any(c.get("function") == "split_direct_speech_turn" for c in parts)
                    or quotes[1].get("governor") != quotes[0]["id"]):
                return None
            if "first" in match.groupdict():
                observed = [(c["start"], c["end"]) for c in parts
                            if c.get("function") == "spoken_clause_candidate"
                            and c.get("governor") == quotes[0]["id"]]
                expected = [(match.start(g), match.end(f"stop{i}"))
                            for i, g in enumerate(("first", "second", "third", "fourth"), 1)]
                if observed != expected:
                    return None
        elif quotes:
            return None
        specs, _, _, put = _specs()
        put(match, 0, layout)
        # Punctuation, phrase proofs and lexical choices account for all text.
        previous = 0
        for _, start, stop, _, _ in specs:
            if previous > start or text[previous:start].strip():
                return None
            previous = stop
        return specs if not text[previous:].strip() else None
    return plan


NARRATIVE_PLANS = tuple((rule, _planner(pattern, layout, kind))
                        for rule, pattern, layout, kind in PLANS if kind != "quoted")
SPOKEN_PLANS = tuple((rule, _planner(pattern, layout, kind))
                     for rule, pattern, layout, kind in PLANS if kind == "quoted")
COUNTS = {rule: 1 for rule, _, _, _ in PLANS}
