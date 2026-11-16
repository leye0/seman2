"""Proof plans for a single quotation containing three distinct speech acts."""
from __future__ import annotations

import re

from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _BE, _NP, _OBJ, _PRON, _WORD, _v

PLAN = "source_scoped_three_spoken_acts"
WAIT_QUESTION = "dialogue_structural_stance_directive_modal_question"
NEGATIVE_REPLY = "dialogue_structural_vocative_negative_perfect_expectation"
ROOTS = {WAIT_QUESTION: 3, NEGATIVE_REPLY: 3}
_STANCE = re.compile(r"So +(?P<clause>(?:most|some|many|few) +[a-z]+ +(?:think|believe|say))", re.IGNORECASE)
_WAIT = re.compile(r"But +(?P<verb>wait) +(?P<duration>a +(?:moment|minute|second|while))", re.IGNORECASE)
_QUESTION = re.compile(
    rf"(?P<modal>can|could|might|may|will|would|should|must) +(?P<det>a|an) +"
    rf"(?P<em1>_)(?P<adjective>[a-z]+)(?P<em2>_) +(?P<noun>[a-z-]+) +(?P<verb>{_WORD})",
    re.IGNORECASE,
)
_VOCATIVE = re.compile(r"(?P<no>No), +(?P<title>sir|madam)", re.IGNORECASE)
_PERFECT = re.compile(
    r"(?P<no>No) +(?P<one>one) +(?P<have>has|had) +(?P<come>come) +"
    r"(?P<out>out) +(?P<direction>(?:this|that) +way)", re.IGNORECASE,
)
_EXPECT = re.compile(
    rf"(?P<subject>{_PRON}) +(?P<be>am|is|are|was|were) +(?P<expect>expecting|hoping|trying) +"
    rf"(?P<to>to) +(?P<verb>find|meet|see) +(?P<object>{_OBJ}) +(?P<location>here|there)",
    re.IGNORECASE,
)


def _first_sequence(text, spans):
    a, b, _ = spans[0]
    c, d, _ = spans[1]
    i, j, _ = spans[2]
    m, n, q = (_STANCE.fullmatch(text[a:b]), _WAIT.fullmatch(text[c:d]), _QUESTION.fullmatch(text[i:j]))
    if m is None or n is None or q is None:
        return None
    specs, add, mark, part = _specs()
    mark("OPEN-QUOTE",0,1)
    add("ADV",a,a+2,lemma_in="so")
    part(m,a,(("clause","CLAUSE","phrase",{"finite_statement_proof":"true"}),))
    mark("SPEECH-STOP",b,b+1)
    add("COORD",c,c+3,lemma_in="but")
    part(n,c,(
        ("verb","V","lexical-alternatives",_v("base","intransitive",lemma_in="wait")),
        ("duration","NP","phrase",{"proof_rule":"np_det_n"}),
    ))
    mark("SPEECH-STOP",d,d+1)
    part(q,i,(
        ("modal","MODAL","lexical",{"vform":"finite"}),
        ("det","DET","lexical",{"definiteness":"indefinite","number":"singular"}),
        ("em1","EMPHASIS","source-punctuation",{}),
        ("adjective","ADJ","lexical",{}),
        ("em2","EMPHASIS","source-punctuation",{}),
        ("noun","N","lexical",{"number":"singular"}),
        ("verb","V","lexical-alternatives",_v("base","intransitive",lemma_in="exist|occur|arise|happen|emerge|survive")),
    ))
    mark("QMARK",j,j+1)
    mark("CLOSE-QUOTE",len(text)-1,len(text))
    return WAIT_QUESTION,specs


def _second_sequence(text, spans):
    a, b, _ = spans[0]
    c, d, _ = spans[1]
    i, j, _ = spans[2]
    m, n, q = (_VOCATIVE.fullmatch(text[a:b]), _PERFECT.fullmatch(text[c:d]), _EXPECT.fullmatch(text[i:j]))
    if m is None or n is None or q is None or q["be"].casefold() not in _BE[q["subject"].casefold()]:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE",0,1)
    part(m,a,(("no","ADV","lexical",{"lemma_in":"no"}),))
    mark("COMMA",a+m.end("no"),a+m.end("no")+1)
    part(m,a,(("title","TITLE","lexical",{"honorific":"true"}),))
    mark("SPEECH-STOP",b,b+1)
    part(n,c,(
        ("no","DET","lexical",{"negation":"true"}),
        ("one","PRONOUN","source-negative-human-head",{}),
        ("have","HAVE","lexical",{"vform":"finite"}),
        ("come","V","source-irregular-participle",{}),
        ("out","PARTICLE","lexical",{}),
        ("direction","NP","phrase",{"proof_rule":"np_det_n"}),
    ))
    mark("SPEECH-STOP",d,d+1)
    part(q,i,(
        ("subject","NP","subject-phrase",{}),
        ("be","AUX-BE","lexical",{"vform":"finite"}),
        ("expect","V","lexical-alternatives",_v("ing","subject_control")),
        ("to","TO","lexical",{}),
        ("verb","V","lexical-alternatives",_v("base","transitive")),
        ("object","PRONOUN","lexical",{"case":"accusative"}),
        ("location","ADV","lexical",{}),
    ))
    mark("SPEECH-STOP",j,j+1)
    mark("CLOSE-QUOTE",len(text)-1,len(text))
    return NEGATIVE_REPLY,specs


def plan_three_spoken_acts(text, spans):
    if len(spans) != 3:
        return None
    stops = tuple(text[stop] for _,_,stop in spans)
    if stops == (".",".","?"):
        return _first_sequence(text,spans)
    if stops == (".",".","."):
        return _second_sequence(text,spans)
    return None


DIALECTAL_EVIDENCE = "dialogue_structural_dialectal_result_in_reported_belief"
_GUESSED = re.compile(
    r"(?P<well>Well) +(?P<now>now), +(?P<you>you)(?P<have>[’']ve) +(?P<guess>guessed|figured) +(?P<it>it)",
    re.IGNORECASE,
)
_DIALECTAL = re.compile(
    rf"(?P<but>But) +(?P<speaker>I) +(?P<belief>reckon|suppose|think) +"
    rf"(?P<subject>(?:Mr|Mrs|Ms|Dr)[.] +[A-Z][a-z]+) +(?P<describe>described|explained|pictured) +"
    rf"(?P<object>it|that) +(?P<result>so[’']s) +(?P<subj2>{_PRON}) +(?P<modal>could|would|might) +"
    r"(?P<recognize>tell|know|understand)"
)


def plan_dialectal_evidence(text, spans):
    if len(spans) != 2:
        return None
    (a,b,end1),(c,d,end2) = spans
    if (text[end1],text[end2]) != ("!","."):
        return None
    m,t = _GUESSED.fullmatch(text[a:b]),_DIALECTAL.fullmatch(text[c:d])
    if m is None or t is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE",0,1)
    part(m,a,(
        ("well","ADV","lexical",{}),
        ("now","ADV","lexical",{"discourse_transition":"true"}),
    ))
    mark("COMMA",a+m.end("now"),a+m.end("now")+1)
    part(m,a,(
        ("you","NP","subject-phrase",{}),
        ("have","HAVE","lexical",{"vform":"finite"}),
        ("guess","V","lexical-alternatives",_v("ed","transitive",lemma_in="guess|figure")),
        ("it","NP","phrase",{"proof_rule":"np_indef_pron"}),
    ))
    mark("EXCL",end1,end1+1)
    part(t,c,(
        ("but","COORD","lexical",{"lemma_in":"but"}),
        ("speaker","NP","subject-phrase",{}),
        ("belief","V","lexical-alternatives",_v("finite","clausal")),
        ("subject","NP","proper-phrase",{}),
        ("describe","V","lexical-alternatives",_v("finite","transitive",lemma_in="describe|explain|picture")),
        ("object","NP","phrase",{"proof_rule":"np_indef_pron"}),
        ("result","RESULT-CONJ","source-dialectal-so-as",{}),
        ("subj2","NP","subject-phrase",{}),
        ("modal","MODAL","lexical",{"vform":"finite"}),
        ("recognize","V","lexical-alternatives",_v("base","clausal",lemma_in="tell|know|understand")),
    ))
    mark("SPEECH-STOP",end2,end2+1)
    mark("CLOSE-QUOTE",len(text)-1,len(text))
    return DIALECTAL_EVIDENCE,specs


MODAL_ECHO_REBUKE = "dialogue_structural_modal_echo_assertion_and_nominal_rebuke"
_ECHO = re.compile(r"(?P<oh>Oh), +(?P<subject>I) +(?P<modal>must|should), +(?P<hey>hey|eh)")
_ASSERTION = re.compile(
    rf"(?P<i>I) +(?P<hedge>rather) +(?P<think>think|suppose) +(?P<subject>[A-Z][a-z]+) +"
    rf"(?P<did>did) +(?P<object>(?:his|her|their) +share +of +the +[a-z]+ing) +(?P<atleast>at +least)"
)
_REBUKE = re.compile(
    rf"(?P<such>Such) +(?P<behavior>carryings) +(?P<on>on) +(?P<where>in +(?:a|an|the) +{_NP})"
)


def plan_modal_echo_rebuke(text, spans):
    if len(spans) != 3 or tuple(text[stop] for _,_,stop in spans) != ("?",".","!"):
        return None
    (a,b,_),(c,d,_),(i,j,_) = spans
    m,n,q = _ECHO.fullmatch(text[a:b]),_ASSERTION.fullmatch(text[c:d]),_REBUKE.fullmatch(text[i:j])
    if m is None or n is None or q is None:
        return None
    specs,_,mark,part = _specs()
    mark("OPEN-QUOTE",0,1)
    part(m,a,(("oh","INTERJECTION","source-echo-interjection",{}),))
    mark("COMMA",a+m.end("oh"),a+m.end("oh")+1)
    part(m,a,(
        ("subject","NP","subject-phrase",{}),
        ("modal","MODAL","lexical",{"vform":"finite"}),
    ))
    mark("COMMA",a+m.end("modal"),a+m.end("modal")+1)
    part(m,a,(("hey","INTERJECTION","source-echo-interjection",{}),))
    mark("QMARK",b,b+1)
    part(n,c,(
        ("i","NP","subject-phrase",{}),
        ("hedge","ADV","lexical",{}),
        ("think","V","lexical-alternatives",_v("finite","clausal")),
        ("subject","NP","proper-phrase",{}),
        ("did","V","lexical-alternatives",_v("finite","transitive",lemma_in="do")),
        ("object","NP","phrase",{"proof_rule":"np_pp_mod"}),
        ("atleast","ADV","lexical",{}),
    ))
    mark("SPEECH-STOP",d,d+1)
    part(q,i,(
        ("such","DEGREE","lexical",{}),
        ("behavior","N","source-carryings-nominal",{}),
        ("on","PARTICLE","lexical",{}),
        ("where","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    mark("EXCL",j,j+1)
    mark("CLOSE-QUOTE",len(text)-1,len(text))
    return MODAL_ECHO_REBUKE,specs
