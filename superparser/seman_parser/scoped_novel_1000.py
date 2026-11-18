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

    ('dialogue_surprise_question_with_negative_partitive',
     re.compile(
         '(?P<open>“)(?P<what>What)(?P<comma>,) +(?P<none>none) +(?P<of>of) +'
         '(?P<set>you|them|us|the +[a-z-]+)(?P<question>\\?)(?P<close>”)'
     ),
     (
         M("open", "OPEN-QUOTE"),
         L("what", "WH-NOM"),
         M("comma", "COMMA"),
         ("none", "PRONOUN", "scoped-lexical", {}),
         L("of", "PREP"),
         P("set", "NP"),
         M("question", "QMARK"),
         M("close", "CLOSE-QUOTE")
     ),
     'quoted'),
    ('dialogue_assertion_and_fronted_negative_modal_after_dismissal',
     re.compile(
         '(?P<open>")(?P<begone>Begone|Away)(?P<excl>!) +(?P<matrix>I +do +[^;!?"]{3,42})'
         '(?P<semi>;) +(?P<never>never) +(?P<will>will|shall|would) +'
         '(?P<subject>I|you|she|he|we|they) +(?P<create>create|make|find|see) +'
         '(?P<another>another) +(?P<like>like) +'
         '(?P<comparison>yourself|himself|herself|him|her|you)(?P<comma>,) +'
         '(?P<equal>equal|similar|comparable) +(?P<domain>in +[^,;.!?"]{2,42})(?P<stop>\\.)'
         '(?P<close>")'
     ),
     (
         M("open", "OPEN-QUOTE"),
         ("begone", "INTERJECTION", "scoped-lexical", {}),
         M("excl", "EXCL"),
         P("matrix", "CLAUSE", finite_statement_proof='true'),
         M("semi", "SEMICOLON"),
         L("never", "DEGREE"),
         L("will", "MODAL", vform='finite'),
         P("subject", "NP"),
         L("create", "V", vform='base'),
         ("another", "PRONOUN", "scoped-lexical", {}),
         L("like", "PREP"), ("comparison", "PRONOUN", "scoped-lexical", {}),
         M("comma", "COMMA"),
         L("equal", "ADJ"),
         P("domain", "PP"),
         M("stop", "SPEECH-STOP"),
         M("close", "CLOSE-QUOTE")
     ),
     'quoted'),
    ('dialogue_perfect_location_duration_and_followup_question',
     re.compile(
         '(?P<open>“)(?P<sister>(?:My|Our|Your|His|Her) +(?:[a-z-]+ +)?[a-z-]+) +'
         '(?P<has>has|have) +(?P<been>been) +(?P<town>in +[^,;.!?“”]{2,30}?) +'
         '(?P<months>these +(?:two|three|four|five|six|seven|eight|nine) +(?:days|weeks|months|years))'
         '(?P<stop>\\.) +(?P<have>Have|Has) +(?P<you>you|he|she|they|we) +(?P<never>never) +'
         '(?P<happened>happened|managed) +(?P<to>to) +(?P<see>see|meet|find) +'
         '(?P<her>her|him|them|us) +(?P<there>there|here)(?P<question>\\?)(?P<close>”)'
     ),
     (
         M("open", "OPEN-QUOTE"),
         P("sister", "NP", proof_rule='np_poss'),
         L("has", "HAVE", vform='finite'),
         L("been", "COPULA", vform='ed'),
         P("town", "PP", proof_rule='pp_prep_np'),
         P("months", "NP", proof_rule='np_det_n'),
         M("stop", "SPEECH-STOP"),
         L("have", "HAVE", vform='finite'),
         P("you", "NP"),
         L("never", "DEGREE"),
         L("happened", "V", vform='ed'),
         L("to", "TO"),
         L("see", "V", vform='base'),
         P("her", "NP"),
         L("there", "ADV"),
         M("question", "QMARK"),
         M("close", "CLOSE-QUOTE")
     ),
     'quoted'),

    ('dialogue_conditional_copular_ellipsis_and_temporal_comparison',
     re.compile(
         '(?P<open>“)(?P<subject>I|We|You) +(?P<should>should|would|could) +(?P<be>be) +'
         '(?P<feeling>[a-z-]+) +(?P<indeed>indeed)(?P<comma>,) +(?P<if>if) +(?P<it>it|that) +'
         '(?P<were>were)(?P<stop1>\\.) +(?P<friends_subject>We|You|They) +(?P<past>were) +'
         '(?P<always>always) +(?P<quality>good|close|dear) +(?P<friends>[a-z-]+)(?P<semi>;) +'
         '(?P<and>and|but) +(?P<now>now) +(?P<current_subject>we|you|they) +(?P<are>are) +'
         '(?P<better>better)(?P<stop2>\\.)(?P<close>”)'
     ),
     (
         M("open", "OPEN-QUOTE"),
         P("subject", "NP"),
         L("should", "MODAL", vform='finite'),
         L("be", "COPULA", vform='base'),
         L("feeling", "ADJ"),
         L("indeed", "ADV"),
         M("comma", "COMMA"),
         L("if", "CONJ"),
         P("it", "NP"),
         L("were", "COPULA", vform='finite'),
         M("stop1", "SPEECH-STOP"),
         P("friends_subject", "NP"),
         L("past", "COPULA", vform='finite'),
         L("always", "ADV"),
         L("quality", "ADJ"), L("friends", "N", number="plural"),
         M("semi", "SEMICOLON"),
         L("and", "COORD"),
         L("now", "ADV"),
         P("current_subject", "NP"),
         L("are", "COPULA", vform='finite'),
         L("better", "ADJ"),
         M("stop2", "SPEECH-STOP"),
         M("close", "CLOSE-QUOTE")
     ),
     'quoted'),
    ('structural_continuative_particle_and_negative_gerund_supplement',
     re.compile(
         '(?P<then>Then|Later) +(?P<subject>I|we|you|he|she|they) +(?P<went>went) +(?P<on>on) +'
         '(?P<manner>softly|calmly|quietly|steadily) +(?P<playing>[a-z-]+ing)(?P<comma>,) +'
         '(?P<but>but) +(?P<without>without) +(?P<removing>[a-z-]+ing) +(?P<theme>[^,;.!?]{2,24}) +'
         '(?P<from>from +[^,;.!?]{2,25})(?P<stop>\\.)'
     ),
     (
         L("then", "ADV"),
         P("subject", "NP"),
         L("went", "V", vform='finite'),
         L("on", "PARTICLE"),
         L("manner", "ADV"),
         L("playing", "V", vform='ing'),
         M("comma", "COMMA"),
         L("but", "COORD"),
         L("without", "PREP"),
         L("removing", "V", vform='ing'),
         P("theme", "NP"),
         P("from", "PP", proof_rule='pp_prep_np'),
         M("stop", "SPEECH-STOP")
     ),
     'finite'),

    ('structural_temporal_locative_antecedent_and_future_departure',
     re.compile(
         '(?P<when>When) +(?P<earlier>[^,;.!?]{4,45})(?P<comma1>,) +(?P<subject>[A-Z][a-z-]+) +'
         '(?P<return>returned|went) +(?P<companion>with +[^,;!?]{3,40}?) +(?P<to1>to) +'
         '(?P<destination>[A-Z][a-z-]+)(?P<comma2>,) +(?P<from>from) +(?P<whence>whence) +'
         '(?P<relative_subject>they|we) +(?P<were>were) +(?P<to2>to) +(?P<set>set) +(?P<out>out) +'
         '(?P<early>early|late) +(?P<day>the +next +(?:day|morning|evening))(?P<stop>\\.)'
     ),
     (
         L("when", "CONJ"),
         P("earlier", "CLAUSE", finite_statement_proof='true'),
         M("comma1", "COMMA"),
         P("subject", "NP", proof_rule='np_proper'),
         L("return", "V", vform='finite'),
         P("companion", "PP", proof_rule='pp_prep_np'),
         L("to1", "PREP"),
         P("destination", "NP", proof_rule='np_proper'),
         M("comma2", "COMMA"),
         L("from", "PREP"),
         L("whence", "ADV"),
         P("relative_subject", "NP"),
         L("were", "COPULA", vform='finite'),
         L("to2", "TO"),
         L("set", "V", vform='base'),
         L("out", "PARTICLE"),
         L("early", "ADV"),
         P("day", "NP", proof_rule='np_det_n'),
         M("stop", "SPEECH-STOP")
     ),
     'finite'),

    ('structural_coordinated_restoration_with_parallel_gerund_means',
     re.compile('(?P<subject>We|They|I|He|She) +(?P<therefore>accordingly|immediately|quickly) +(?P<bring>brought|carried) +(?P<theme1>him|her|them|us) +(?P<back>back) +(?P<goal1>to +[^,;.!?]{3,35}?) +(?P<and1>and) +(?P<restore>restored|returned) +(?P<theme2>him|her|them|us) +(?P<goal2>to +[^,;.!?]{3,35}?) +(?P<by>by) +(?P<gerund1>rubbing|washing|treating) +(?P<patient>him|her|them|us) +(?P<instrument>with +[^,;.!?]{3,35}?) +(?P<and2>and) +(?P<gerund2>forcing|persuading|urging) +(?P<controller>him|her|them|us) +(?P<to>to) +(?P<action>swallow|drink|eat) +(?P<quantity>[^,;.!?]{3,35})(?P<stop>\\.)'),
     (
         P("subject", "NP"),
         L("therefore", "ADV"),
         L("bring", "V", vform='finite'),
         P("theme1", "NP"),
         L("back", "ADV"),
         P("goal1", "PP", proof_rule='pp_prep_np'),
         L("and1", "COORD"),
         L("restore", "V", vform='finite'),
         P("theme2", "NP"),
         P("goal2", "PP", proof_rule='pp_prep_np'),
         L("by", "PREP"),
         L("gerund1", "V", vform='ing'),
         P("patient", "NP"),
         P("instrument", "PP", proof_rule='pp_prep_np'),
         L("and2", "COORD"),
         L("gerund2", "V", vform='ing'),
         P("controller", "NP"),
         L("to", "TO"),
         L("action", "V", vform='base'),
         P("quantity", "NP"),
         M("stop", "SPEECH-STOP")
     ),
     'finite'),

    ('structural_locative_coordination_with_active_and_passive_relatives',
     re.compile('(?P<spire>The +[a-z-]+) +(?P<of1>of) +(?P<place>[A-Z][a-z-]+) +(?P<shine>shone|gleamed|stood) +(?P<under>under|below) +(?P<woods>the +[a-z-]+) +(?P<that>that) +(?P<surround>surrounded|sheltered|encircled) +(?P<it1>it) +(?P<and>and) +(?P<range>the +(?:range|ridge|line)) +(?P<of2>of) +(?P<mountain1>mountain|hill|peak) +(?P<above>above) +(?P<mountain2>mountain|hill|peak) +(?P<by>by) +(?P<which>which) +(?P<it2>it) +(?P<was>was) +(?P<overhung>overhung|enclosed|sheltered|overshadowed)(?P<stop>\\.)'),
     (
         P("spire", "NP", proof_rule='np_det_n'),
         L("of1", "PREP"),
         P("place", "NP", proof_rule='np_proper'),
         L("shine", "V", vform='finite'),
         L("under", "PREP"),
         P("woods", "NP", proof_rule='np_det_n'),
         L("that", "WH-PRONOUN"),
         L("surround", "V", vform='finite'),
         P("it1", "NP"),
         L("and", "COORD"),
         P("range", "NP", proof_rule='np_det_n'),
         L("of2", "PREP"),
         L("mountain1", "N"),
         L("above", "PREP"),
         L("mountain2", "N"),
         L("by", "PREP"),
         L("which", "WH-NOM"),
         P("it2", "NP"),
         L("was", "COPULA", vform='finite'),
         L("overhung", "V", vform='ed'),
         M("stop", "SPEECH-STOP")
     ),
     'finite'),

    ('structural_nor_inversion_with_without_nominal_coordination',
     re.compile(
         '(?P<emoter>I|We|You|He|She|They) +(?P<affect>feel|felt|seem|seemed) +(?P<still>yet|still) +'
         '(?P<state>parched|frozen|shaken|numb) +(?P<cause>with +[^,;.!?]{2,35})(?P<comma>,) +(?P<nor>nor) +'
         '(?P<can>can|could|will|would) +(?P<thinker>I|we|you|he|she|they|it) +'
         '(?P<reflect>reflect|think|dwell) +(?P<topic>(?:on|upon) +[^,;.!?]{2,35}) +(?P<without>without) +'
         '(?P<gerund>shuddering|trembling|shaking) +(?P<and>and) +(?P<nominal>agony|fear|horror|dread)'
         '(?P<end>\\.)'

     ),
     (
         P('emoter', 'NP'),
         L('affect', 'V', vform='finite'),
         L('still', 'ADV'),
         L('state', 'ADJ'),
         P('cause', 'PP', proof_rule='pp_prep_np'),
         M('comma', 'COMMA'),
         L('nor', 'COORD'),
         L('can', 'MODAL', vform='finite'),
         P('thinker', 'NP'),
         L('reflect', 'V', vform='base'),
         P('topic', 'PP', proof_rule='pp_prep_np'),
         L('without', 'PREP'),
         L('gerund', 'V', vform='ing'),
         L('and', 'COORD'),
         L('nominal', 'N'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),
    ('structural_inverted_conditional_with_nominal_apposition',
     re.compile(
         '(?P<should>Should) +(?P<plan>(?:the|his|her|their) +[^,;.!?]{5,48}?) +(?P<prove>prove|turn) +'
         '(?P<state>feasible|practical|possible|successful)(?P<comma1>,) +(?P<person>[A-Z][a-z]+)'
         '(?P<comma2>,) +(?P<already>already) +(?P<doubly>doubly|virtually|almost) +'
         '(?P<role>(?:a|an) +[a-z-]+)(?P<comma3>,) +(?P<would>would|will|could) +(?P<neg>not) +'
         '(?P<hesitate>hesitate|dare) +(?P<to>to) +(?P<adopt>adopt|accept|support|approve) +'
         '(?P<object>it|them|him|her)(?P<end>\\.)'

     ),
     (
         L('should', 'MODAL', vform='finite'),
         P('plan', 'NP', proof_rule='np_relative_obj'),
         L('prove', 'V', vform='base'),
         L('state', 'ADJ'),
         M('comma1', 'COMMA'),
         L('person', 'PROPER-NOUN'),
         M('comma2', 'COMMA'),
         L('already', 'ADV'),
         L('doubly', 'ADV'),
         P('role', 'NP', proof_rule='np_det_n'),
         M('comma3', 'COMMA'),
         L('would', 'MODAL', vform='finite'),
         L('neg', 'NEG'),
         L('hesitate', 'V', vform='base'),
         L('to', 'TO'),
         L('adopt', 'V', vform='base'),
         P('object', 'NP'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),
    ('structural_existential_nominal_contrast_with_shared_head',
     re.compile(
         '(?P<but>But) +(?P<there>there) +(?P<was>was) +(?P<no>no) +(?P<sign>sign|trace|hint) +(?P<of1>of) +'
         '(?P<positive_phase>(?:reawakening|returning|dawning)) +(?P<positive>[a-z-]+) +(?P<bearers>(?:in|among) +[^,;.!?]{2,35})(?P<comma1>,) +'
         '(?P<rather>rather)(?P<comma2>,) +(?P<indeed>indeed)(?P<comma3>,) +(?P<of2>of) +'
         '(?P<negative_phase>(?:growing|rising|mounting)) +(?P<negative>[a-z-]+) +(?P<cause>(?:at|over) +[^,;.!?]{2,50})(?P<end>\\.)'

     ),
     (
         L('but', 'COORD'),
         L('there', 'EXPL'),
         L('was', 'COPULA', vform='finite'),
         L('no', 'DET'),
         L('sign', 'N'),
         L('of1', 'PREP'),
         L('positive_phase', 'V', vform='ing'),
         L('positive', 'N'),
         P('bearers', 'PP', proof_rule='pp_prep_np'),
         M('comma1', 'COMMA'),
         L('rather', 'ADV'),
         M('comma2', 'COMMA'),
         L('indeed', 'ADV'),
         M('comma3', 'COMMA'),
         L('of2', 'PREP'),
         L('negative_phase', 'V', vform='ing'),
         L('negative', 'N'),
         P('cause', 'PP', proof_rule='pp_prep_np'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),
    ('structural_equative_simile_with_passive_measure',
     re.compile(
         '(?P<sound>(?:The|Their) +[^,;.!?]{3,70}?) +(?P<were>were|was) +(?P<as1>as) +'
         '(?P<state>hushed|muted|quiet)(?P<comma>,) +(?P<as2>as) +(?P<if>if) +(?P<location>the +[a-z-]+) +'
         '(?P<had>had) +(?P<been>been) +(?P<strewn>strewn|covered|lined) +'
         '(?P<depth>(?:that|this) +(?:depth|thickness)) +(?P<material>with +[^,;.!?]{2,35})(?P<end>\\.)'

     ),
     (
         P('sound', 'NP', proof_rule='np_pp_mod'),
         L('were', 'COPULA', vform='finite'),
         L('as1', 'EQUATIVE-AS'),
         L('state', 'ADJ'),
         M('comma', 'COMMA'),
         L('as2', 'CONJ'),
         L('if', 'CONJ'),
         P('location', 'NP', proof_rule='np_det_n'),
         L('had', 'HAVE', vform='finite'),
         L('been', 'COPULA', vform='ed'),
         L('strewn', 'V', vform='ed'),
         P('depth', 'NP', proof_rule='np_det_n'),
         P('material', 'PP', proof_rule='pp_prep_np'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),
    ('dialogue_epistemic_modal_content_with_titled_vocative',
     re.compile(
         '(?P<open>‘)(?P<thinker>I|We|You|He|She) +(?P<should>should|would|could) +'
         '(?P<think>think|imagine|expect|believe) +(?P<actor>YOU|you|he|she|they) +'
         '(?P<would>would|will|might) +(?P<come>come|return|go|enter) +(?P<goal>(?:into|to) +[^,;.!?]{2,35}) +'
         '(?P<eventually>at +(last|length))(?P<comma>,) +(?P<title>Master|Miss) +(?P<addressee>[A-Z][a-z]+)'
         '(?P<bang>!)(?P<close>’)'

     ),
     (
         M('open', 'OPEN-QUOTE'),
         P('thinker', 'NP'),
         L('should', 'MODAL', vform='finite'),
         L('think', 'V', vform='base'),
         P('actor', 'NP'),
         L('would', 'MODAL', vform='finite'),
         L('come', 'V', vform='base'),
         P('goal', 'PP', proof_rule='pp_prep_np'),
         P('eventually', 'PP', proof_rule='pp_prep_np'),
         M('comma', 'COMMA'),
         ('title', 'TITLE', "scoped-lexical", {'honorific': 'true'}),
         P('addressee', 'NP', proof_rule='np_proper'),
         M('bang', 'EXCL'),
         M('close', 'CLOSE-QUOTE'),
     ),
     'quoted'),
    ('structural_fronted_comparison_set_with_predicative_superlative',
     re.compile(
         '(?P<set>Of +all +[^,;.!?]{2,58})(?P<comma>,) +(?P<experience>this +[^,;.!?]{4,35}?) +(?P<on>on) +'
         '(?P<part>the +part) +(?P<of>of) +(?P<person>[A-Z][a-z]+(?: +[A-Z][a-z]+)?) +'
         '(?P<appeared>appeared|seemed) +(?P<det>the) +(?P<worst>worst|best)(?P<end>\\.)'

     ),
     (
         P('set', 'PP', proof_rule='pp_prep_np'),
         M('comma', 'COMMA'),
         P('experience', 'NP'),
         L('on', 'PREP'),
         P('part', 'NP', proof_rule='np_det_n'),
         L('of', 'PREP'),
         P('person', 'NP'),
         L('appeared', 'V', vform='finite'),
         L('det', 'DET'),
         L('worst', 'ADJ'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),

    ('dialogue_exclamation_with_shared_subject_postposed_report',
     re.compile(
         '(?P<open>")(?P<exclaim>Si-lence|Silence|Hush)(?P<bang>!)(?P<close>") +(?P<agent>he|she|they) +'
         '(?P<report>roared|shouted|cried) +(?P<and>and) +(?P<look>looked|stared|glared) +'
         '(?P<around>(?:about|around) +[^,;.!?]{2,35}) +(?P<degree>positively|exactly|quite) +'
         '(?P<comparison>like +[^,;.!?]{2,35})(?P<end>\\.)'

     ),
     (
         M('open', 'OPEN-QUOTE'),
         ('exclaim', 'INTERJECTION', "scoped-lexical", {}),
         M('bang', 'EXCL'),
         M('close', 'CLOSE-QUOTE'),
         P('agent', 'NP'),
         L('report', 'V', vform='finite'),
         L('and', 'COORD'),
         L('look', 'V', vform='finite'),
         P('around', 'PP', proof_rule='pp_prep_np'),
         L('degree', 'ADV'),
         P('comparison', 'PP', proof_rule='pp_prep_np'),
         M('end', 'SPEECH-STOP'),
     ),
     'quoted'),
    ('dialogue_dialectal_identity_reprise_with_negative_perfect',
     re.compile(
         '(?P<open>")(?P<subject>I)(?P<am>\'m) +(?P<qual>poor|old|honest) +(?P<name>[A-Z][a-z]+ +[A-Z][a-z]+)'
         '(?P<comma>,) +(?P<echo>I) +(?P<am2>am)(?P<semi>;) +(?P<and>and) +(?P<subject2>I) +(?P<have>have)'
         "(?P<negative>n't) +(?P<spoken>spoke|spoken|talked) +(?P<partner>with +[^,;.!?]{2,35}) +"
         '(?P<duration>these +(?:two|three|four|five) +(?:years|months|weeks))(?P<end>\\.)(?P<close>")'

     ),
     (
         M('open', 'OPEN-QUOTE'),
         P('subject', 'NP'),
         L('am', 'COPULA', vform='finite'),
         L('qual', 'ADJ'),
         P('name', 'NP', proof_rule='np_name_seq2'),
         M('comma', 'COMMA'),
         P('echo', 'NP'),
         L('am2', 'COPULA', vform='finite'),
         M('semi', 'SEMICOLON'),
         L('and', 'COORD'),
         P('subject2', 'NP'),
         L('have', 'HAVE', vform='finite'),
         L('negative', 'NEG'),
         ('spoken', 'V', "scoped-lexical", {'vform': 'ed'}),
         P('partner', 'PP', proof_rule='pp_prep_np'),
         P('duration', 'NP', proof_rule='np_det_n'),
         M('end', 'SPEECH-STOP'),
         M('close', 'CLOSE-QUOTE'),
     ),
     'quoted'),
    ('dialogue_reported_polite_instruction_with_elliptic_target',
     re.compile(
         '(?P<open>")(?P<title>Mr|Mrs)(?P<dot>\\.) +(?P<address>[A-Z][a-z]+)(?P<comma1>,) +'
         '(?P<will>will|would|could) +(?P<you>you) +(?P<please>please) +(?P<pick>pick) +(?P<me>me|us) +'
         '(?P<off>off) +(?P<one>one) +(?P<of>of) +(?P<set>(?:these|those) +[a-z-]+)(?P<comma2>,) +'
         '(?P<sir>sir|madam)(?P<qmark>\\?) +(?P<target>[A-Z][a-z]+)(?P<comma3>,) +(?P<if>if) +'
         '(?P<possible>possible)(?P<comma4>,)(?P<close>") +(?P<said>said|asked|replied) +'
         '(?P<speaker>the +[a-z-]+)(?P<end>\\.)'

     ),
     (
         M('open', 'OPEN-QUOTE'),
         L('title', 'TITLE', honorific='true'),
         M('dot', 'ABBREVIATION-STOP'),
         P('address', 'NP', proof_rule='np_proper'),
         M('comma1', 'COMMA'),
         L('will', 'MODAL', vform='finite'),
         P('you', 'NP'),
         L('please', 'ADV'),
         L('pick', 'V', vform='base'),
         P('me', 'NP'),
         L('off', 'PARTICLE'),
         L('one', 'NUM'),
         L('of', 'PREP'),
         P('set', 'NP'),
         M('comma2', 'COMMA'),
         L('sir', 'TITLE'),
         M('qmark', 'QMARK'),
         ('target', 'PROPER-NOUN', "scoped-lexical", {'number': 'singular', 'person': '3'}),
         M('comma3', 'COMMA'),
         L('if', 'CONJ'),
         L('possible', 'ADJ'),
         M('comma4', 'COMMA'),
         M('close', 'CLOSE-QUOTE'),
         L('said', 'V', vform='finite'),
         P('speaker', 'NP', proof_rule='np_det_n'),
         M('end', 'SPEECH-STOP'),
     ),
     'quoted'),
    ('dialogue_fused_modal_stance_and_passive_negative_tag',
     re.compile(
         '(?P<open>“)(?P<but>But)(?P<comma1>,) +(?P<dear>(?:my|our) +[a-z-]+)(?P<comma2>,) +'
         '(?P<subject>(?:your|her|his) +[a-z-]+) +(?P<can>can)(?P<first_not>not) +'
         '(?P<spare>spare|lend|release) +(?P<object>the +[a-z-]+)(?P<comma3>,) +(?P<stance_subject>I) +'
         '(?P<am>am) +(?P<sure>sure|certain)(?P<stop>\\.) +(?P<patient>They) +(?P<passive>are) +'
         '(?P<wanted>wanted|needed|required) +(?P<location>(?:in|at) +[^,;.!?]{2,35})(?P<comma4>,) +'
         '(?P<address>(?:Mr|Mrs)\\. +[A-Z][a-z]+)(?P<comma5>,) +(?P<tag>are) +(?P<tag_subject>they) +'
         '(?P<tag_neg>not)(?P<qmark>\\?)(?P<close>”)'

     ),
     (
         M('open', 'OPEN-QUOTE'),
         L('but', 'COORD'),
         M('comma1', 'COMMA'),
         P('dear', 'NP', proof_rule='np_poss'),
         M('comma2', 'COMMA'),
         P('subject', 'NP', proof_rule='np_poss'),
         ('can', 'MODAL', 'source-fused-modal', {}),
         ('first_not', 'NEG', 'source-fused-modal', {}),
         L('spare', 'V', vform='base'),
         P('object', 'NP', proof_rule='np_det_n'),
         M('comma3', 'COMMA'),
         P('stance_subject', 'NP'),
         L('am', 'COPULA', vform='finite'),
         L('sure', 'ADJ'),
         M('stop', 'SPEECH-STOP'),
         P('patient', 'NP'),
         L('passive', 'COPULA', vform='finite'),
         L('wanted', 'V', vform='ed'),
         P('location', 'PP', proof_rule='pp_prep_np'),
         M('comma4', 'COMMA'),
         P('address', 'NP', proof_rule='np_honorific_abbreviation'),
         M('comma5', 'COMMA'),
         L('tag', 'COPULA', vform='finite'),
         P('tag_subject', 'NP'),
         L('tag_neg', 'NEG'),
         M('qmark', 'QMARK'),
         M('close', 'CLOSE-QUOTE'),
     ),
     'quoted'),
    ('structural_shared_agent_with_independent_genitive_destinations',
     re.compile(
         '(?P<subject>He|She|They|We|I) +(?P<joined>joined|met) +(?P<theme>them|her|him|us) +(?P<on>on) +'
         '(?P<poss>their|his|her|our) +(?P<entry>entering|leaving) +(?P<site>the +[a-z-]+)(?P<comma1>,) +'
         '(?P<and>and) +(?P<escort>attended|accompanied|escorted) +(?P<theme2>them|her|him|us) +(?P<to>to) +'
         "(?P<poss2>their|his|her|our) +(?P<relative>aunt|uncle|sister|brother)(?P<gen>['’]s) +"
         '(?P<where>where) +(?P<poss3>his|her|their|our) +(?P<regret>regret|sorrow|grief) +(?P<and2>and) +'
         '(?P<other>vexation|disappointment|anger)(?P<comma2>,) +(?P<and3>and) +'
         '(?P<concern>the +(?:concern|anxiety|astonishment)) +(?P<of>of) +'
         '(?P<everybody>everybody|everyone|all)(?P<comma3>,) +(?P<was>was|were) +(?P<well>well|thoroughly) +'
         '(?P<talked>talked) +(?P<over>over)(?P<end>\\.)'

     ),
     (
         P('subject', 'NP'),
         L('joined', 'V', vform='finite'),
         P('theme', 'NP'),
         L('on', 'PREP'),
         L('poss', 'POSS'),
         L('entry', 'V', vform='ing'),
         P('site', 'NP', proof_rule='np_det_n'),
         M('comma1', 'COMMA'),
         L('and', 'COORD'),
         L('escort', 'V', vform='finite'),
         P('theme2', 'NP'),
         L('to', 'PREP'),
         L('poss2', 'POSS'),
         L('relative', 'N'),
         L('gen', 'POSS', lemma_in="'s-poss"),
         L('where', 'WH-NOM'),
         L('poss3', 'POSS'),
         L('regret', 'N'),
         L('and2', 'COORD'),
         L('other', 'N'),
         M('comma2', 'COMMA'),
         L('and3', 'COORD'),
         P('concern', 'NP', proof_rule='np_det_n'),
         L('of', 'PREP'),
         P('everybody', 'NP'),
         M('comma3', 'COMMA'),
         L('was', 'COPULA', vform='finite'),
         L('well', 'ADV'),
         L('talked', 'V', vform='ed'),
         L('over', 'PARTICLE'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),
    ('structural_shared_subject_order_with_genitive_shop_and_intensifier',
     re.compile(
         '(?P<subject>I|He|She|We|They) +(?P<acted>acted) +(?P<on>on) +(?P<title>Mrs|Mr)(?P<dot>\\.) +'
         "(?P<name>[A-Z][a-z]+)(?P<gen1>['’]s) +(?P<advice>opinion|advice|suggestion)(?P<comma>,) +"
         '(?P<and>and) +(?P<gave>gave|placed) +(?P<order>the +(?:order|request)) +(?P<at>at) +(?P<det>the) +'
         "(?P<compound>pastry|coffee|shoe)(?P<hyphen>-)(?P<shop>cook|maker|seller)(?P<gen2>['’]s) +"
         '(?P<self>myself|herself|himself|themselves|ourselves)(?P<end>\\.)'

     ),
     (
         P('subject', 'NP'),
         L('acted', 'V', vform='finite'),
         L('on', 'PREP'),
         L('title', 'TITLE'),
         M('dot', 'ABBREVIATION-STOP'),
         L('name', 'PROPER-NOUN'),
         L('gen1', 'POSS', lemma_in="'s-poss"),
         L('advice', 'N'),
         M('comma', 'COMMA'),
         L('and', 'COORD'),
         L('gave', 'V', vform='finite'),
         P('order', 'NP', proof_rule='np_det_n'),
         L('at', 'PREP'),
         L('det', 'DET'),
         L('compound', 'N'),
         M('hyphen', 'JOIN-HYPHEN'),
         L('shop', 'N'),
         L('gen2', 'POSS', lemma_in="'s-poss"),
         L('self', 'EMPHATIC-REFLEXIVE'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),
    ('structural_elliptic_genitive_location_and_emphatic_simile',
     re.compile(
         '(?P<subject>I|He|She|We|They) +(?P<was>was|were) +(?P<always>always) +'
         '(?P<state>punctual|regular|early|prompt) +(?P<location>at +[^,;.!?]{2,35})(?P<semi>;) +(?P<at>at) +'
         "(?P<det>the) +(?P<doctor>Doctor|Lawyer|Merchant)(?P<gen>['’]s) +(?P<too>too)(?P<colon>:) +"
         '(?P<and>and) +(?P<subject2>I|he|she|we|they) +(?P<really>really|indeed) +(?P<did>did) +'
         '(?P<work>work|labour|toil)(?P<comma1>,) +(?P<as>as) +'
         '(?P<expression>the +(?:common|usual) +(?:expression|saying|phrase)) +(?P<is>is)(?P<comma2>,) +'
         '(?P<simile>like +[^,;.!?]{2,35})(?P<end>\\.)'

     ),
     (
         P('subject', 'NP'),
         L('was', 'COPULA', vform='finite'),
         L('always', 'ADV'),
         L('state', 'ADJ'),
         P('location', 'PP', proof_rule='pp_prep_np'),
         M('semi', 'SEMICOLON'),
         L('at', 'PREP'),
         L('det', 'DET'),
         L('doctor', 'N'),
         L('gen', 'POSS', lemma_in="'s-poss"),
         L('too', 'ADV'),
         M('colon', 'COLON'),
         L('and', 'COORD'),
         P('subject2', 'NP'),
         L('really', 'ADV'),
         L('did', 'AUX', vform='finite'),
         L('work', 'V', vform='base'),
         M('comma1', 'COMMA'),
         L('as', 'CONJ'),
         P('expression', 'NP'),
         L('is', 'COPULA', vform='finite'),
         M('comma2', 'COMMA'),
         P('simile', 'PP', proof_rule='pp_prep_np'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),
    ('structural_perspective_with_coordinated_relatives_and_stranded_gap',
     re.compile(
         '(?P<of>Of) +(?P<topic>this|that|it) +(?P<subject>she|he|they) +(?P<was>was|were) +'
         '(?P<fully>perfectly|entirely|quite) +(?P<unaware>unaware|ignorant)(?P<semi>;) +'
         '(?P<view>to +[^,;.!?]{2,35}) +(?P<subject2>he|she|they) +(?P<was2>was|were) +(?P<only>only) +'
         '(?P<man>the +(?:man|woman|person)) +(?P<who1>who) +(?P<made>made) +'
         '(?P<self>himself|herself|themselves) +(?P<agreeable>agreeable|welcome|pleasant) +'
         '(?P<nowhere>nowhere)(?P<comma>,) +(?P<and>and) +(?P<who2>who) +(?P<had>had) +(?P<not>not) +'
         '(?P<think>thought|considered|judged) +(?P<target>her|him|them) +'
         '(?P<handsome>handsome|pleasant|pretty|agreeable) +(?P<enough>enough) +(?P<to>to) +'
         '(?P<dance>dance|talk|work) +(?P<with>with)(?P<end>\\.)'

     ),
     (
         L('of', 'PREP'),
         P('topic', 'NP'),
         P('subject', 'NP'),
         L('was', 'COPULA', vform='finite'),
         L('fully', 'ADV'),
         L('unaware', 'ADJ'),
         M('semi', 'SEMICOLON'),
         P('view', 'PP', proof_rule='pp_prep_np'),
         P('subject2', 'NP'),
         L('was2', 'COPULA', vform='finite'),
         L('only', 'ADV'),
         P('man', 'NP', proof_rule='np_det_n'),
         L('who1', 'WH-NOM'),
         L('made', 'V', vform='finite'),
         L('self', 'PRONOUN', reflexive='true'),
         L('agreeable', 'ADJ'),
         L('nowhere', 'ADV'),
         M('comma', 'COMMA'),
         L('and', 'COORD'),
         L('who2', 'WH-NOM'),
         L('had', 'HAVE', vform='finite'),
         L('not', 'NEG'),
         L('think', 'V', vform='ed'),
         P('target', 'NP'),
         L('handsome', 'ADJ'),
         L('enough', 'DEGREE'),
         L('to', 'TO'),
         L('dance', 'V', vform='base'),
         L('with', 'PREP'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),

    ('documentary_postscript_initials_signature',
     re.compile(
         '(?P<initial1>[A-Z])(?P<dot1>\\.) +(?P<initial2>[A-Z])(?P<dot2>\\.)'

     ),
     (
         ('initial1', 'PROPER-NOUN', 'source-document-initial', {}),
         M('dot1', 'ABBREVIATION-STOP'),
         ('initial2', 'PROPER-NOUN', 'source-document-initial', {}),
         M('dot2', 'ABBREVIATION-STOP'),
     ),
     'documentary'),
    ('documentary_narrator_resumption_before_date',
     re.compile(
         '(?P<narrator>[A-Z][a-z]+)(?P<comma>,) +(?P<in>in) +(?P<continuation>continuation)(?P<end>\\.)'

     ),
     (
         L('narrator', 'PROPER-NOUN'),
         M('comma', 'COMMA'),
         L('in', 'PREP'),
         L('continuation', 'N'),
         M('end', 'SPEECH-STOP'),
     ),
     'documentary'),

    ('structural_fronted_direction_with_finite_motion',
     re.compile(
         '(?P<direction>Away|Off|Home) +(?P<subject>we|they|he|she|I|you) +'
         '(?P<motion>went|ran|rode|walked|hurried)(?P<end>\\.)'

     ),
     (
         L('direction', 'ADV'),
         P('subject', 'NP'),
         L('motion', 'V', vform='finite'),
         M('end', 'SPEECH-STOP'),
     ),
     'finite'),
    ('dialogue_negative_copular_stance_vocative_tag_with_reporter_adjunct',
     re.compile(
         "(?P<open>‘)(?P<subject>You) +(?P<negative_be>an[’']t|aren[’']t|ain[’']t) +"
         '(?P<state>cross|angry|ready|tired|upset)(?P<comma1>,) +(?P<thinker>I) +'
         '(?P<stance>suppose|imagine|think)(?P<comma2>,) +(?P<addressee>[A-Z][a-z]+)(?P<comma3>,) +'
         '(?P<tag>are) +(?P<tag_you>you)(?P<question>\\?)(?P<close>’) +(?P<report>said|asked|inquired) +'
         '(?P<speaker>I|he|she)(?P<comma4>,) +(?P<after>after) +(?P<position>sitting|standing|waiting) +'
         '(?P<depictive>quiet|silent|still) +(?P<duration>for +[^,;.!?]{2,30})(?P<end>\\.)'

     ),
     (
         M('open', 'OPEN-QUOTE'),
         P('subject', 'NP'),
         ('negative_be', 'COPULA', "scoped-lexical", {'vform': 'finite', 'negation': 'true'}),
         L('state', 'ADJ'),
         M('comma1', 'COMMA'),
         P('thinker', 'NP'),
         L('stance', 'V', vform='finite'),
         M('comma2', 'COMMA'),
         P('addressee', 'NP', proof_rule='np_proper'),
         M('comma3', 'COMMA'),
         L('tag', 'COPULA', vform='finite'),
         P('tag_you', 'NP'),
         M('question', 'QMARK'),
         M('close', 'CLOSE-QUOTE'),
         L('report', 'V', vform='finite'),
         P('speaker', 'NP'),
         M('comma4', 'COMMA'),
         L('after', 'PREP'),
         L('position', 'V', vform='ing'),
         L('depictive', 'ADJ'),
         P('duration', 'PP', proof_rule='pp_prep_np'),
         M('end', 'SPEECH-STOP'),
     ),
     'quoted'),

)


_COPULA_FOR_PRONOUN = {
    "i": {"am", "was"}, "he": {"is", "was"}, "she": {"is", "was"},
    "it": {"is", "was"}, "you": {"are", "were"}, "we": {"are", "were"},
    "they": {"are", "were"},
}


def _planner(root, pattern, layout, kind):
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
        if groups.get("happened"):
            plural = groups["you"].lower() in ("you", "we", "they")
            if groups["have"].lower() != ("have" if plural else "has"):
                return None
        quotes = [c for c in parts if c.get("function") == "direct_speech"]
        if kind == "documentary":
            function = ("postscript_signature_candidate"
                        if root == "documentary_postscript_initials_signature"
                        else "dated_narrator_resumption_candidate")
            if not any(c.get("function") == function and (c["start"], c["end"]) == (0, len(text))
                       for c in parts):
                return None
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


NARRATIVE_PLANS = tuple((rule, _planner(rule, pattern, layout, kind))
                        for rule, pattern, layout, kind in PLANS if kind != "quoted")
SPOKEN_PLANS = tuple((rule, _planner(rule, pattern, layout, kind))
                     for rule, pattern, layout, kind in PLANS if kind == "quoted")
COUNTS = {rule: 0 if kind == "documentary" else 1 for rule, _, _, kind in PLANS}
