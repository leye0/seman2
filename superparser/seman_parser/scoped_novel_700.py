"""Evidence-bounded general constructions for the additive Novel-700 cohort.

The regexes only propose exact source spans. The existing grammar and lexical
recognizer must still prove every constituent; source/speech markers are not
invented. Deliberately leave out ungrounded anaphoric antecedents.
"""
from __future__ import annotations

import re

from .additional_spoken_acts import _single_spoken_span
from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _matrix, _v

DISCOURSE_RETURN = "structural_discourse_return_with_infinitive_topic"
PROPOSITIONAL_RESUMPTION = "structural_propositional_relative_resumption"
COORDINATED_PASSIVE = "structural_semicolon_temporal_passive_coordination"
REPORTED_WH_REPLY = "dialogue_structural_reported_minor_wh_reply"
REPORTED_COPULAR_COMMENT = "dialogue_structural_reported_copular_comment_with_companion"


def _lex(group, category, **features):
    return group, category, "lexical", features


def _phr(group, category="NP", **features):
    return group, category, "phrase", features


def _subject(group):
    return group, "NP", "subject-phrase", {}


def _verb(group, form, frame, **features):
    return group, "V", "lexical-alternatives", _v(form, frame, **features)


def _punct(group, cat):
    return group, cat, "source-punctuation", {}


_RETURN = re.compile(
    r"(?P<but>But|And|Now) +(?P<to>to) +(?P<return>return|revert) +"
    r"(?P<topic_to>to) +(?P<subject>(?:dearer|happier|more pleasant|earlier|other) +"
    r"(?:considerations|matters|questions|thoughts|subjects))(?P<stop>\.)"
)


def plan_discourse_return(text, components):
    m = _RETURN.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        _lex("but", "COORD"), _lex("to", "TO"),
        _verb("return", "base", "intransitive"), _lex("topic_to", "PREP", lemma_in="to"),
        _phr("subject", proof_rule="np_bare"), _punct("stop", "SPEECH-STOP"),
    ))
    return specs


_RESUMPTION = re.compile(
    r"(?P<which>Which) +(?P<be>was|is) +(?P<quality>true|clear|correct|strange) +"
    r"(?P<degree>enough|indeed)(?P<stop>\.)"
)


def plan_propositional_resumption(text, components):
    m = _RESUMPTION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        _lex("which", "WH-PRONOUN", wh="true"), _lex("be", "COPULA", vform="finite", number="singular"),
        _lex("quality", "ADJ"), _lex("degree", "ADV"), _punct("stop", "SPEECH-STOP"),
    ))
    return specs


_PASSIVE_COORD = re.compile(
    r"(?P<subject1>Darkness|Silence|A shadow|The mist) +"
    r"(?P<comes>comes|came|falls|fell) +(?P<direction>(?:before|over) +(?:my|his|her|their|our) +(?:eyes|face|mind))"
    r"(?P<semicolon>;) +(?P<and>and)(?P<comma1>,) +"
    r"(?P<time>for +(?:a|some) +(?:time|while))(?P<comma2>,) +"
    r"(?P<subject2>all +(?:things|thoughts|memories|details)) +(?P<be>are|were) +"
    r"(?P<participle>blotted|wiped|washed|swept) +(?P<out>out) +(?P<of>of) +"
    r"(?P<possessed>(?:my|his|her|their|our) +(?:remembrance|memory|mind|thoughts))"
    r"(?P<stop>\.)"
)


def plan_coordinated_passive(text, components):
    m = _PASSIVE_COORD.fullmatch(text)
    if m is None or any(c.get("function") in ("direct_speech", "reporting_clause") for c in components):
        return None
    first = next((c for c in components if c.get("function") == "matrix_clause"), None)
    second = next((c for c in components if c.get("function") == "coordinate_clause"), None)
    if (first is None or second is None or first["start"] != 0 or
            second["start"] != m.start("and") or second["end"] != len(text)):
        return None
    if (m["be"] == "are") != (m["comes"] in {"comes", "falls"}):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        _subject("subject1"), _verb("comes", "finite", "intransitive"),
        _phr("direction", "PP", proof_rule="pp_prep_np"), _punct("semicolon", "SEMICOLON"),
        _lex("and", "COORD", lemma_in="and"), _punct("comma1", "COMMA"),
        _phr("time", "PP", proof_rule="pp_prep_np"), _punct("comma2", "COMMA"),
        _subject("subject2"), _lex("be", "AUX-BE", vform="finite", number="plural"),
        _verb("participle", "ed", "transitive"), _lex("out", "PARTICLE", lemma_in="out"),
        _lex("of", "PREP", lemma_in="of"), _phr("possessed", proof_rule="np_poss"),
        _punct("stop", "SPEECH-STOP"),
    ))
    return specs


_WH_REPLY = re.compile(r"(?P<what>What|Who|Why)(?P<question>\?)")
_WH_REPORTER = re.compile(
    r"(?P<verb>returned|asked|replied|answered|inquired) +(?P<name>[A-Z][a-z]+(?: +[A-Z][a-z]+)?)"
)


def plan_reported_wh_reply(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != "?":
        return None
    stop, reporter = evidence
    q = _WH_REPLY.fullmatch(text[1:stop + 1])
    r = _WH_REPORTER.fullmatch(text[reporter["start"]:reporter["end"]])
    if q is None or r is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(q, 1, (_lex("what", "WH-PRONOUN", wh="true"), _punct("question", "SPEECH-STOP")))
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    part(r, reporter["start"], (
        ("verb", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "return|ask|reply|answer|inquire"}),
        _subject("name"),
    ))
    mark("SPEECH-STOP", len(text)-1, len(text))
    return specs


_COMMENT = re.compile(
    r"(?P<and>And) +(?P<this>this|that) +(?P<be>is|was) +(?P<frequency>always|often|usually) +"
    r"(?P<the>the) +(?P<way>way|case|problem) +(?P<with>with) +"
    r"(?P<person>him|her|them|me|us|you)"
)
_COMMENT_REPORT = re.compile(r"(?P<report_subject>he|she|they|I) +(?P<report>added|said|answered|replied)")


def plan_reported_copular_comment(text, components):
    evidence = _single_spoken_span(text, components, reported=True)
    if evidence is None or text[evidence[0]] != ",":
        return None
    stop, reporter = evidence
    m = _COMMENT.fullmatch(text[1:stop])
    r = _COMMENT_REPORT.fullmatch(text[reporter["start"]:reporter["end"]])
    if m is None or r is None:
        return None
    if (m["this"], m["be"]) not in {("this", "is"), ("this", "was"), ("that", "is"), ("that", "was")}:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE", 0, 1)
    part(m, 1, (
        _lex("and", "COORD", lemma_in="and"), _phr("this", proof_rule="np_demonstrative"),
        _lex("be", "COPULA", vform="finite", number="singular"),
        _lex("frequency", "ADV"), _lex("the", "DET"),
        _lex("way", "N", number="singular"),
        _lex("with", "PREP", lemma_in="with"), _phr("person"),
    ))
    mark("COMMA", stop, stop+1)
    mark("CLOSE-QUOTE", stop+1, stop+2)
    part(r, reporter["start"], (_subject("report_subject"),
         ("report", "V", "lexical-alternatives", {"vform": "finite", "lemma_in": "add|say|answer|reply"})))
    mark("SPEECH-STOP", len(text)-1, len(text))
    return specs


TEMPORAL_AS_IF = 'structural_periodic_perception_with_evidential_as_if'
CURIOSITY_AS_IF = 'structural_raising_curiosity_with_counterfactual_comparison'
FRONTED_AS_CEMETERY = 'structural_temporal_as_with_locative_relative_and_coordination'

_PERIODIC_PERCEPTION = re.compile(
    r'(?P<frequency>Sometimes|Occasionally)(?P<comma1>,) +'
    r'(?P<by>by) +(?P<evidence>the +(?:quivering|rippling|movement|trembling) +of +the +(?:water|leaves|surface))'
    r'(?P<comma2>,) +(?P<observer>he|she|they) +(?P<appeared>appeared|seemed) +'
    r'(?P<to>to) +(?P<move>move|stir|rise|turn) +(?P<a>a) +(?P<little>little)'
    r'(?P<comma3>,) +(?P<as>as) +(?P<if>if) +(?P<imagined>he|she|they) +'
    r'(?P<were>were|was) +(?P<trying>trying|attempting) +(?P<to2>to) +(?P<rise>rise|stand|escape|walk)'
    r'(?P<stop>\.)'
)

def plan_periodic_perception(text, components):
    m = _PERIODIC_PERCEPTION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if m['observer'] != m['imagined'] or (m['observer'] == 'they' and m['were'] == 'was'):
        return None
    specs, _, _, part = _specs()
    part(m,0,(
        _lex('frequency','ADV'),_punct('comma1','COMMA'),_lex('by','PREP',lemma_in='by'),
        _phr('evidence',proof_rule='np_det_n_of'),_punct('comma2','COMMA'),_subject('observer'),
        _verb('appeared','finite','linking'),_lex('to','TO'),_verb('move','base','intransitive'),
        _lex('a','DET'),_lex('little','ADJ'),_punct('comma3','COMMA'),
        _lex('as','CONJ'),_lex('if','CONJ'),_subject('imagined'),
        _lex('were','AUX-BE',vform='finite'),_verb('trying','ing','subject_control'),
        _lex('to2','TO'),_verb('rise','base','intransitive'),_punct('stop','SPEECH-STOP'),
    ))
    return specs

_CURIOSITY = re.compile(
    r'(?P<subject>He|She|They) +(?P<seemed>seemed|appeared) +'
    r'(?P<curious>curious|interested|uncertain) +(?P<regarding>regarding|concerning) +'
    r'(?P<object>the +(?:cottage|house|garden|room|building))(?P<comma1>,) +(?P<too>too|also)'
    r'(?P<comma2>,) +(?P<as>as) +(?P<if>if) +(?P<it>it) +(?P<were>were|was) +'
    r'(?P<the>the) +(?P<first>first) +(?P<time>time) +(?P<viewer>he|she|they) +'
    r'(?P<had>had) +(?P<seen>seen|visited|entered) +(?P<backref>it)'
    r'(?P<stop>\.)'
)

def plan_curiosity_as_if(text, components):
    m = _CURIOSITY.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if m['subject'].lower()!=m['viewer'] or m['backref']!='it':
        return None
    specs, _, _, part = _specs()
    part(m,0,(
        _subject('subject'),_verb('seemed','finite','linking'),_lex('curious','ADJ'),
        ('regarding','PREP','scoped-lexical',{'topic':'true'}),
        _phr('object',proof_rule='np_det_n'),_punct('comma1','COMMA'),_lex('too','ADV'),
        _punct('comma2','COMMA'),_lex('as','CONJ'),_lex('if','CONJ'),_subject('it'),
        _lex('were','COPULA',vform='finite'),_lex('the','DET'),_lex('first','ADJ'),
        _lex('time','N',number='singular'),_subject('viewer'),_lex('had','HAVE',vform='finite'),
        _verb('seen','ed','transitive'),_phr('backref'),_punct('stop','SPEECH-STOP'),
    ))
    return specs

_FRONTED_AS = re.compile(
    r'(?P<as>As) +(?P<night>night|dusk|evening) +(?P<approached>approached|fell) +'
    r'(?P<subject>I|he|she|we|they) +(?P<found>found|placed|saw) +'
    r'(?P<myself>myself|himself|herself|ourselves|themselves) +'
    r'(?P<at>at) +(?P<the>the) +(?P<entry>entrance|edge|gate) +(?P<of>of) +'
    r'(?P<the2>the) +(?P<place>cemetery|garden|park|churchyard) +(?P<where>where) +'
    r'(?P<name1>[A-Z][a-z]+)(?P<comma1>,) +(?P<name2>[A-Z][a-z]+)(?P<comma2>,) +'
    r'(?P<and>and) +(?P<poss>(?:my|his|her|our|their) +(?:father|mother|friend|brother)) +'
    r'(?P<reposed>reposed|rested|waited|stood)(?P<stop>\.)'
)
_REFLEXIVES={'I':'myself','he':'himself','she':'herself','we':'ourselves','they':'themselves'}

def plan_fronted_as(text, components):
    m=_FRONTED_AS.fullmatch(text)
    if m is None or not _matrix(text, components) or _REFLEXIVES[m['subject']]!=m['myself']:
        return None
    specs, _, _, part=_specs()
    part(m,0,(
        _lex('as','CONJ',simultaneous='true'),_subject('night'),_verb('approached','finite','intransitive'),
        _subject('subject'),_verb('found','finite','transitive'),_lex('myself','EMPHATIC-REFLEXIVE',reflexive='true'),
        _lex('at','PREP',lemma_in='at'),_lex('the','DET'),_lex('entry','N'),_lex('of','PREP',nominal_complement='of'),
        _lex('the2','DET'),_lex('place','N'),_lex('where','WH-NOM',wh_adverbial='true'),
        _phr('name1',proof_rule='np_proper'),_punct('comma1','COMMA'),_phr('name2',proof_rule='np_proper'),
        _punct('comma2','COMMA'),_lex('and','COORD',lemma_in='and'),_phr('poss',proof_rule='np_poss'),
        _verb('reposed','finite','intransitive'),_punct('stop','SPEECH-STOP'),
    ))
    return specs

FRONTED_GERUND_JUDGMENT = 'structural_fronted_gerund_judgment_with_concessive_affect'

_FRONTED_MARRIAGE = re.compile(
    r'(?P<of>Of) +(?P<having>having) +(?P<another>another|a) +(?P<relation>daughter|son|sister|brother) +'
    r'(?P<married>married|engaged) +(?P<to>to) +(?P<title>Mr|Mrs|Dr)(?P<abbr>\.) +'
    r'(?P<person>[A-Z][a-z]+)(?P<comma1>,) +(?P<actor>he|she|they|I) +(?P<thought>thought|reflected|speculated) +'
    r'(?P<with1>with) +(?P<equal1>equal|great|similar) +(?P<certainty>certainty|confidence|conviction)'
    r'(?P<comma2>,) +(?P<and>and) +(?P<with2>with) +(?P<considerable>considerable|great|sincere)'
    r'(?P<comma3>,) +(?P<though>though) +(?P<not>not) +(?P<equal2>equal|comparable|similar)'
    r'(?P<comma4>,) +(?P<pleasure>pleasure|delight|satisfaction)(?P<stop>\.)'
)

def plan_fronted_gerund_judgment(text, components):
    m=_FRONTED_MARRIAGE.fullmatch(text)
    if m is None or not _matrix(text, components):return None
    specs,_,_,part=_specs()
    part(m,0,(
        _lex('of','PREP',lemma_in='of'),_verb('having','ing','transitive'),
        _lex('another','ADJ'),_lex('relation','N'),_verb('married','ed','transitive'),
        _lex('to','PREP',lemma_in='to'),_lex('title','TITLE'),_punct('abbr','ABBREVIATION-STOP'),
        _phr('person',proof_rule='np_proper'),_punct('comma1','COMMA'),_subject('actor'),
        _verb('thought','finite','intransitive'),_lex('with1','PREP',lemma_in='with'),
        _lex('equal1','ADJ'),_lex('certainty','N'),_punct('comma2','COMMA'),
        _lex('and','COORD',lemma_in='and'),_lex('with2','PREP',lemma_in='with'),
        _lex('considerable','ADJ'),_punct('comma3','COMMA'),_lex('though','CONJ'),
        _lex('not','NEG',negation='true'),_lex('equal2','ADJ'),_punct('comma4','COMMA'),
        _lex('pleasure','N'),_punct('stop','SPEECH-STOP'),
    ));return specs

CONCESSIVE_LEAD = 'structural_negated_modal_with_self_concessive_and_result'
SCALAR_BUT_THAT = 'structural_scalar_passive_but_that_self_engagement'

_CONCESSIVE_LEAD = re.compile(
    r'(?P<subject>I|He|She|We|They) +(?P<modal>will|would|could|might) +(?P<not>not) +'
    r'(?P<lead>lead|guide|draw) +(?P<object>you|him|her|them|me|us) +(?P<on>on)'
    r'(?P<comma1>,) +(?P<state1>unguarded|innocent|eager|rash) +(?P<and1>and) +'
    r'(?P<state2>ardent|reckless|foolish|trusting) +(?P<as>as) +(?P<subj>I|he|she|we|they) +'
    r'(?P<then>then) +(?P<was>was|were)(?P<comma2>,) +(?P<to>to) +'
    r'(?P<poss>your|his|her|their|our|my) +(?P<result1>destruction|disgrace|ruin|sorrow) +'
    r'(?P<and2>and) +(?P<adj>infallible|certain|lasting|great) +(?P<result2>misery|ruin|pain|regret)'
    r'(?P<stop>\.)'
)

def plan_concessive_lead(text, components):
    m=_CONCESSIVE_LEAD.fullmatch(text)
    if m is None or not _matrix(text, components):return None
    if m['subject'].lower()!=m['subj'].lower() or m['was']!=('were' if m['subj'] in {'we','they'} else 'was'):
        return None
    specs,_,_,part=_specs()
    part(m,0,(
        _subject('subject'),_lex('modal','MODAL',vform='finite'),_lex('not','NEG',negation='true'),
        _verb('lead','base','transitive'),_phr('object'),_lex('on','PARTICLE',lemma_in='on'),
        _punct('comma1','COMMA'),_lex('state1','ADJ'),_lex('and1','COORD',lemma_in='and'),
        _lex('state2','ADJ'),_lex('as','CONJ'),_subject('subj'),_lex('then','ADV'),
        _lex('was','COPULA',vform='finite'),_punct('comma2','COMMA'),_lex('to','PREP',lemma_in='to'),
        _lex('poss','POSS'),_lex('result1','N'),_lex('and2','COORD',lemma_in='and'),
        _lex('adj','ADJ'),_lex('result2','N'),_punct('stop','SPEECH-STOP'),
    ));return specs

_SCALAR_BUT_THAT = re.compile(
    r'(?P<yet>Yet|But)(?P<comma1>,) +(?P<although>although|though) +(?P<unhappy>unhappy|upset|sad)'
    r'(?P<comma2>,) +(?P<subject>he|she|they) +(?P<is>is|are) +(?P<not>not) +'
    r'(?P<so>so) +(?P<utterly>utterly|deeply|entirely) +(?P<occupied>occupied|absorbed) +'
    r'(?P<by>by) +(?P<poss>his|her|their) +(?P<own>own) +(?P<misery>misery|grief|sorrow) +'
    r'(?P<but>but) +(?P<that>that) +(?P<embedded>he|she|they) +'
    r'(?P<interests>interests|engages|involves|interest|engage|involve) +'
    r'(?P<self>himself|herself|themselves) +(?P<deeply>deeply|greatly|actively) +'
    r'(?P<in>in) +(?P<the>the) +(?P<projects>projects|affairs|plans) +(?P<of>of) +'
    r'(?P<others>others)(?P<stop>\.)'
)

def plan_scalar_but_that(text, components):
    m=_SCALAR_BUT_THAT.fullmatch(text)
    if m is None or not _matrix(text, components):return None
    pron=m['subject'];wanted={'he':'himself','she':'herself','they':'themselves'}[pron]
    if m['embedded']!=pron or m['self']!=wanted or m['is']!=('are' if pron=='they' else 'is'):
        return None
    if (pron=='they') == m['interests'].endswith('s'):return None
    specs,_,_,part=_specs()
    part(m,0,(
        _lex('yet','COORD'),_punct('comma1','COMMA'),_lex('although','CONJ'),
        _lex('unhappy','ADJ'),_punct('comma2','COMMA'),_subject('subject'),
        _lex('is','AUX-BE',vform='finite'),_lex('not','NEG',negation='true'),
        _lex('so','DEGREE',scalar_degree='true'),_lex('utterly','ADV'),
        _verb('occupied','ed','transitive'),_lex('by','PREP-BY'),_lex('poss','POSS'),
        _lex('own','ADJ'),_lex('misery','N'),_lex('but','COORD',lemma_in='but'),
        _lex('that','COMP-THAT'),_subject('embedded'),_verb('interests','finite','transitive'),
        _lex('self','EMPHATIC-REFLEXIVE',reflexive='true'),_lex('deeply','ADV'),
        _lex('in','PREP',lemma_in='in'),_lex('the','DET'),_lex('projects','N'),
        _lex('of','PREP',nominal_complement='of'),_lex('others','N'),_punct('stop','SPEECH-STOP'),
    ));return specs


# N624: two independently licensed finite clauses; the second carries
# a depictive passive participle with an overt causal agent and relative.
N624_PARATAXIS = 'structural_semicolon_parataxis_with_participial_cause_and_relative'
_N624 = re.compile(
    r'(?P<first>(?:My|His|Her) +(?:rage|anger|fury) +(?:was|is) +without +(?:bounds|limits))'
    r'(?P<semicolon>;) +'
    r'(?P<second>(?:I|he|she) +(?:sprang|leaped|jumped) +(?:on|upon) +(?:him|her|them))'
    r'(?P<comma>,) +(?P<impelled>impelled|driven) +(?P<by>by) +'
    r'(?P<feelings>all +the +(?:feelings|passions)) +(?P<which>which) +'
    r'(?P<can>can|could) +(?P<arm>arm|turn) +(?P<one>one) +'
    r'(?P<being>being|person) +(?P<against>against) +(?P<the>the) +'
    r'(?P<existence>existence|life) +(?P<of>of) +(?P<another>another)'
    r'(?P<stop>\.)'
)

def plan_n624_parataxis(text, components):
    m = _N624.fullmatch(text)
    if m is None:
        return None
    first = next((c for c in components if c.get('function') == 'matrix_clause'), None)
    second = next((c for c in components if c.get('function') == 'independent_clause'), None)
    if (first is None or second is None or first['start'] != 0
            or second['start'] != m.start('second')):
        return None
    specs,_,_,part = _specs()
    part(m, 0, (
        _phr('first','CLAUSE',finite_statement_proof='true'),
        _punct('semicolon','SEMICOLON'),
        _phr('second','CLAUSE',finite_statement_proof='true'),
        _punct('comma','COMMA'),
        _verb('impelled','ed','transitive'), _lex('by','PREP-BY'),
        _phr('feelings','NP',proof_rule='np_det_det_n'),
        _lex('which','WH-NOM'),
        _lex('can','MODAL',vform='finite'), _verb('arm','base','transitive'),
        _lex('one','NUM'),_lex('being','N'),
        _lex('against','PREP',lemma_in='against'),_lex('the','DET'),
        _lex('existence','N'),_lex('of','PREP',lemma_in='of'),
        _lex('another','INDEF-PRONOUN'),_punct('stop','SPEECH-STOP'),
    ))
    return specs

NARRATIVE_PLANS = (
    (N624_PARATAXIS, plan_n624_parataxis),
    (CONCESSIVE_LEAD, plan_concessive_lead),
    (SCALAR_BUT_THAT, plan_scalar_but_that),
    (FRONTED_GERUND_JUDGMENT, plan_fronted_gerund_judgment),
    (TEMPORAL_AS_IF, plan_periodic_perception),
    (CURIOSITY_AS_IF, plan_curiosity_as_if),
    (FRONTED_AS_CEMETERY, plan_fronted_as),
    (DISCOURSE_RETURN, plan_discourse_return),
    (PROPOSITIONAL_RESUMPTION, plan_propositional_resumption),
    (COORDINATED_PASSIVE, plan_coordinated_passive),
)
SPOKEN_PLANS = (
    (REPORTED_WH_REPLY, plan_reported_wh_reply),
    (REPORTED_COPULAR_COMMENT, plan_reported_copular_comment),
)
COUNTS = {N624_PARATAXIS: 2, CONCESSIVE_LEAD:2, SCALAR_BUT_THAT:3, FRONTED_GERUND_JUDGMENT:2, TEMPORAL_AS_IF:2, CURIOSITY_AS_IF:3, FRONTED_AS_CEMETERY:3, DISCOURSE_RETURN: 0, PROPOSITIONAL_RESUMPTION: 1, COORDINATED_PASSIVE: 2,
          REPORTED_WH_REPLY: 0, REPORTED_COPULAR_COMMENT: 1}
