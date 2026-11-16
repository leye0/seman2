"""Independent source proofs for negative inversion and interrupted speech."""
from __future__ import annotations

import re

from .additional_spoken_acts import _single_spoken_span
from .dialogue import quotation_boundaries
from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _NP, _PRON, _v

NOR_POSSESSION = "dialogue_structural_nor_inversion_with_restrictive_possession"
INTERRUPTED_CLOCK = "dialogue_structural_interrupted_narrative_with_reported_clock"
REPORTED_OPINION = "dialogue_structural_reported_negative_opinion_with_sort_relative"
_REPORT_VERBS = "say|remark|reply|observe|announce|add|whisper|murmur"
_NOR = re.compile(
    rf"(?P<nor>Nor), +(?P<having>having) +(?P<only>only) +(?P<first>[a-z-]+), +(?P<second>[a-z-]+),? +"
    rf"(?P<and>and) +(?P<third>[a-z-]+), +(?P<modal>can|could|would|will|might|may|should|must) +"
    rf"(?P<subject>(?:a|an|the) +{_NP}?) +(?P<have>have) +(?P<object>(?:a|an|the) +{_NP})",
    re.IGNORECASE,
)
_CLOCK = re.compile(
    rf"(?P<it>It)(?P<be>[’']s) +(?P<half>half)(?P<hyphen>-)(?P<past>past) +"
    r"(?P<hour>one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) +(?P<now>now)",
    re.IGNORECASE,
)
_INTERRUPTED = re.compile(
    rf"(?P<subject>{_PRON}) +(?P<look>looked|searched|glanced) +(?P<round>round|around) +"
    rf"(?P<target>for +{_NP}), +(?P<and>and)(?P<dash>—|--)",
    re.IGNORECASE,
)
_REPORT = re.compile(rf"(?P<verb>[a-z]+) +(?P<speaker>(?:the|a|an) +{_NP}|[A-Z][a-z]+)",re.IGNORECASE)
_OPINION = re.compile(
    rf"(?P<but>But) +(?P<subject>(?i:{_PRON})) +(?P<modal>should|would|could|might)"
    rf"(?P<neg>n[’']t) +(?P<think>think|suppose|believe) +(?P<descr>{_PRON}) +(?P<be>was|is) +"
    rf"(?P<the>the) +(?P<sort>sort|kind|type) +(?P<of>of) +(?P<domain>[a-z]+) +"
    r"(?P<relative_subject>[A-Z][a-z]+) +(?P<relative_modal>would|could|might) +(?P<relative_verb>like|love|choose|pick)"
)
_OPINION_TAG = re.compile(r"(?P<verb>[a-z]+) +(?P<speaker>[A-Z][a-z]+) +(?P<target>to +[A-Z][a-z]+)")


def plan_nor_possession(text, components):
    scoped = _single_spoken_span(text, components)
    if scoped is None or text[scoped[0]] != ".":
        return None
    stop, _ = scoped
    m = _NOR.fullmatch(text[1:stop])
    if m is None:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE",0,1)
    part(m,1,(("nor","COORD","lexical",{"negation":"true","inversion":"true"}),))
    mark("COMMA",1+m.end("nor"),2+m.end("nor"))
    part(m,1,(
        ("having","V","lexical-alternatives",_v("ing","transitive",lemma_in="have")),
        ("only","ADV","lexical",{"nominal_focus":"true"}),
        ("first","N","lexical",{}),
    ))
    mark("COMMA",1+m.end("first"),2+m.end("first"))
    part(m,1,(("second","N","lexical",{}),))
    if m.string[m.end("second")] == ",":
        mark("COMMA",1+m.end("second"),2+m.end("second"))
    part(m,1,(
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("third","N","lexical",{}),
    ))
    mark("COMMA",1+m.end("third"),2+m.end("third"))
    part(m,1,(
        ("modal","MODAL","lexical",{"vform":"finite"}),
        ("subject","NP","phrase",{"proof_rule":"np_det_n"}),
        ("have","V","lexical-alternatives",_v("base","transitive",lemma_in="have")),
        ("object","NP","phrase",{"proof_rule":"np_det_n"}),
    ))
    mark("SPEECH-STOP",stop,stop+1)
    mark("CLOSE-QUOTE",len(text)-1,len(text))
    return specs


def plan_interrupted_clock(text, components):
    by_id = {c.get("id"):c for c in components}
    q, r, qc = (by_id.get(i) for i in ("q0","r0","qc0_0"))
    if not (q and r and qc and q.get("function")=="direct_speech" and q.get("governor")=="r0"
            and r.get("function")=="reporting_clause" and r.get("governor")=="u0"
            and qc.get("governor")=="q0" and qc.get("function")=="spoken_clause_candidate"):
        return None
    a, b = q["start"], q["end"]
    if ((qc["start"], qc["end"]) != (a+1,b-1) or r["end"] != len(text)-1 or text[-1]!="."
            or text[b:r["start"]].strip() or text[b-2:b-1] != ","):
        return None
    if [(mark.start,mark.end,mark.side) for mark in quotation_boundaries(text)] != [
        (a,a+1,"open"), (b-1,b,"close"),
    ]:
        return None
    m, n, t = _INTERRUPTED.fullmatch(text[:a]), _CLOCK.fullmatch(text[a+1:b-2]), _REPORT.fullmatch(text[r["start"]:r["end"]])
    if m is None or n is None or t is None:
        return None
    specs, _, mark, part = _specs()
    part(m,0,(
        ("subject","NP","subject-phrase",{}),
        ("look","V","lexical-alternatives",_v("finite","intransitive",lemma_in="look|search|glance")),
        ("round","ADV","lexical",{}),
        ("target","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    mark("COMMA",m.end("target"),m.end("target")+1)
    part(m,0,(
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("dash","DASH","source-punctuation",{}),
    ))
    mark("OPEN-QUOTE",a,a+1)
    part(n,a+1,(
        ("it","PRONOUN","lexical",{"lemma_in":"it"}),
        ("be","COPULA","lexical",{"vform":"finite"}),
        ("half","DET","lexical",{"predeterminer":"fractional"}),
        ("hyphen","JOIN-HYPHEN","source-punctuation",{}),
        ("past","ADV","lexical",{"lemma_in":"past"}),
        ("hour","NUM","lexical",{}),
        ("now","ADV","lexical",{"lemma_in":"now"}),
    ))
    mark("COMMA",b-2,b-1)
    mark("CLOSE-QUOTE",b-1,b)
    part(t,r["start"],(
        ("verb","V","lexical-alternatives",_v("finite","clausal",lemma_in=_REPORT_VERBS)),
        ("speaker","NP","phrase",{}),
    ))
    mark("SPEECH-STOP",len(text)-1,len(text))
    return specs


def plan_reported_opinion(text,components):
    scoped = _single_spoken_span(text,components,reported=True)
    if scoped is None or text[scoped[0]] != ",":
        return None
    stop, r = scoped
    m, t = _OPINION.fullmatch(text[1:stop]), _OPINION_TAG.fullmatch(text[r["start"]:r["end"]])
    if m is None or t is None or m["descr"] not in ("he","she","it"):
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE",0,1)
    part(m,1,(
        ("but","COORD","lexical",{"lemma_in":"but"}),
        ("subject","NP","subject-phrase",{}),
        ("modal","MODAL","lexical",{"vform":"finite"}),
        ("neg","NEG","lexical",{"negation":"true"}),
        ("think","V","lexical-alternatives",_v("base","clausal",lemma_in="think|suppose|believe")),
        ("descr","NP","subject-phrase",{}),
        ("be","COPULA","lexical",{"vform":"finite"}),
        ("the","DET","lexical",{"definiteness":"definite"}),
        ("sort","N","lexical",{"number":"singular"}),
        ("of","PREP","lexical",{"lemma_in":"of"}),
        ("domain","N","lexical",{"number":"singular"}),
        ("relative_subject","NP","proper-phrase",{}),
        ("relative_modal","MODAL","lexical",{"vform":"finite"}),
        ("relative_verb","V","lexical-alternatives",_v("base","transitive",lemma_in="like|love|choose|pick")),
    ))
    mark("COMMA",stop,stop+1)
    mark("CLOSE-QUOTE",stop+1,stop+2)
    part(t,r["start"],(
        ("verb","V","lexical-alternatives",_v("finite","clausal",lemma_in=_REPORT_VERBS)),
        ("speaker","NP","proper-phrase",{}),
        ("target","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    mark("SPEECH-STOP",len(text)-1,len(text))
    return specs


REPORTED_INVERTED_CONTROL = "dialogue_structural_inverted_negative_extraposed_control_with_speaker_apposition"
_COPULAR_CONTROL = re.compile(
    rf"(?P<be>Is|Was) +(?P<neg>not) +(?P<subj>that|this) +(?P<degree>rather|quite|surely) +"
    rf"(?P<pred>(?:a|an) +[a-z-]+ +(?:thing|task|matter|problem|challenge)) +(?P<to1>to) +"
    rf"(?P<expect>expect|ask|require) +(?P<obj>her|him|them|us|you|me) +(?P<to2>to) +"
    rf"(?P<begin>begin|start|work) +(?P<prep>upon|on|with)"
)
_APPOSITIVE_TAG = re.compile(
    rf"(?P<report>[a-z]+) +(?P<speaker>[A-Z][a-z]+), +(?P<appos>(?:an|a) +{_NP})"
)


def plan_reported_inverted_control(text,components):
    scoped = _single_spoken_span(text,components,reported=True)
    if scoped is None or text[scoped[0]] != "?":
        return None
    stop,r = scoped
    m = _COPULAR_CONTROL.fullmatch(text[1:stop])
    t = _APPOSITIVE_TAG.fullmatch(text[r["start"]:r["end"]])
    if m is None or t is None or (m["begin"],m["prep"]) not in {
        ("begin","upon"),("begin","on"),("begin","with"),
        ("start","on"),("start","with"),("work","on"),
    }:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE",0,1)
    part(m,1,(
        ("be","COPULA","lexical",{"vform":"finite"}),
        ("neg","NEG","lexical",{"negation":"true"}),
        ("subj","PRONOUN","lexical",{"definiteness":"demonstrative"}),
        ("degree","ADV","lexical",{}),
        ("pred","NP","phrase",{"proof_rule":"np_det_n"}),
        ("to1","TO","lexical",{}),
        ("expect","V","lexical-alternatives",_v("base","object_control")),
        ("obj","PRONOUN","lexical",{"case":"accusative"}),
        ("to2","TO","lexical",{}),
        ("begin","V","lexical-alternatives",_v("base","prepositional")),
        ("prep","PREP","lexical",{}),
    ))
    mark("QMARK",stop,stop+1)
    mark("CLOSE-QUOTE",stop+1,stop+2)
    part(t,r["start"],(
        ("report","V","lexical-alternatives",_v("finite","clausal",lemma_in=_REPORT_VERBS)),
        ("speaker","NP","proper-phrase",{}),
    ))
    comma = r["start"]+t.end("speaker")
    mark("COMMA",comma,comma+1)
    part(t,r["start"],(("appos","NP","phrase",{"appositive_nominal_proof":"true"}),))
    mark("SPEECH-STOP",len(text)-1,len(text))
    return specs


HESITANT_ADMISSION = "dialogue_structural_elliptical_admission_with_concessive_trail"
_HESITATION = re.compile(
    rf"(?P<to>To) +(?P<tell>tell) +(?P<addressee>you) +(?P<truth>the +(?:truth|whole truth))(?P<dots1>\x2e{{3,5}}) +"
    rf"(?P<subject>{_PRON}) +(?P<hedge>hardly|scarcely) +(?P<believe>believe|credit) +(?P<object>it|that) +"
    rf"(?P<emphasis>myself|himself|herself|ourselves|themselves|yourself)(?P<dots2>\x2e{{3,5}}) +"
    r"(?P<and>And) +(?P<yet>yet)(?P<dots3>\x2e{3,5})",
    re.IGNORECASE,
)


def plan_elliptical_admission(text, components):
    q = next((c for c in components if c.get("id") == "q0" and c.get("function") == "direct_speech"), None)
    if not q or (q["start"],q["end"]) != (0,len(text)) or q.get("relation") != "unattributed_speech":
        return None
    if [(q.start,q.end,q.side) for q in quotation_boundaries(text)] != [
        (0,1,"open"),(len(text)-1,len(text),"close"),
    ]:
        return None
    m = _HESITATION.fullmatch(text[1:-1])
    if m is None or m["emphasis"].casefold() != {
        "i":"myself","he":"himself","she":"herself","we":"ourselves","they":"themselves","you":"yourself",
    }.get(m["subject"].casefold()):
        return None
    if m["subject"].casefold() in ("he","she"):
        return None  # only a finite bare present is licensed by this plan
    pieces = sorted((c["start"],c["end"]) for c in components
                    if c.get("function")=="spoken_clause_candidate" and c.get("governor")=="q0")
    if pieces != [(1,1+m.end("dots1")),
                  (1+m.start("subject"),1+m.end("dots2")),
                  (1+m.start("and"),1+m.end("dots3"))]:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-QUOTE",0,1)
    part(m,1,(
        ("to","TO","lexical",{}),
        ("tell","V","lexical-alternatives",_v("base","ditransitive",lemma_in="tell")),
        ("addressee","PRONOUN","lexical",{"lemma_in":"you"}),
        ("truth","NP","phrase",{"proof_rule":"np_det_n"}),
        ("dots1","ELLIPSIS-MARK","source-punctuation",{}),
        ("subject","NP","subject-phrase",{}),
        ("hedge","ADV","lexical",{}),
        ("believe","V","lexical-alternatives",_v("finite","transitive",lemma_in="believe|credit")),
        ("object","NP","phrase",{"proof_rule":"np_indef_pron"}),
        ("emphasis","PRONOUN","lexical",{"reflexive":"true"}),
        ("dots2","ELLIPSIS-MARK","source-punctuation",{}),
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("yet","ADV","lexical",{}),
        ("dots3","ELLIPSIS-MARK","source-punctuation",{}),
    ))
    mark("CLOSE-QUOTE",len(text)-1,len(text))
    return specs


REPORTED_REGRET = "dialogue_structural_reported_modal_perfect_with_stance"
_REGRET = re.compile(
    rf"(?P<subject>[A-Z][a-z]+) +(?P<modal>might|could|would) +(?P<just>just|at least) +"
    rf"(?P<have>have) +(?P<verb>smiled|laughed|waved|nodded) +"
    rf"(?P<target>at +(?:me|her|him|them|us|you)) +(?P<frequency>once|twice), +"
    r"(?P<speaker>I) +(?P<stance>think|suppose)"
)
_REGRET_TAG = re.compile(
    rf" *(?P<speaker>{_PRON}) +(?P<report>mourned|lamented) +(?P<recipient>to +[A-Z][a-z]+) +"
    r"(?P<time>(?:that|this) +(?:night|morning|afternoon|evening|day))"
)


def plan_reported_regret(text,components):
    # "Mourn" is not an unconditional speech verb. Require a balanced
    # adjacent quote-final comma, a pronoun, a named addressee and a time
    # adjunct before licensing the quotative frame.
    by_id = {c.get("id"):c for c in components}
    q, qc = by_id.get("q0"), by_id.get("qc0_0")
    if not q or not qc or q.get("function")!="direct_speech" or q["start"] != 0:
        return None
    b = q["end"]
    if (not 4 <= b < len(text) or text[b-2] != "," or text[-1] != "."
            or qc.get("governor") != "q0" or (qc["start"],qc["end"]) != (1,b-1)):
        return None
    if [(mark.start,mark.end,mark.side) for mark in quotation_boundaries(text)] != [
        (0,1,"open"),(b-1,b,"close"),
    ]:
        return None
    m,t = _REGRET.fullmatch(text[1:b-2]),_REGRET_TAG.fullmatch(text[b:-1])
    if m is None or t is None:
        return None
    specs,_,mark,part = _specs()
    mark("OPEN-QUOTE",0,1)
    part(m,1,(
        ("subject","NP","proper-phrase",{}),
        ("modal","MODAL","lexical",{"vform":"finite"}),
        ("just","ADV","lexical",{}),
        ("have","HAVE","lexical",{"vform":"base"}),
        ("verb","V","lexical-alternatives",_v("ed","intransitive",lemma_in="smile|laugh|wave|nod")),
        ("target","PP","phrase",{"proof_rule":"pp_prep_np"}),
        ("frequency","ADV","lexical",{}),
    ))
    mark("COMMA",1+m.end("frequency"),2+m.end("frequency"))
    part(m,1,(
        ("speaker","NP","subject-phrase",{}),
        ("stance","V","lexical-alternatives",_v("finite","clausal",lemma_in="think|suppose")),
    ))
    mark("COMMA",b-2,b-1)
    mark("CLOSE-QUOTE",b-1,b)
    part(t,b,(
        ("speaker","NP","subject-phrase",{}),
        ("report","V","lexical-alternatives",_v("finite","intransitive",lemma_in="mourn|lament")),
        ("recipient","PP","phrase",{"proof_rule":"pp_prep_np"}),
        ("time","NP","phrase",{"proof_rule":"np_det_n"}),
    ))
    mark("SPEECH-STOP",len(text)-1,len(text))
    return specs


SPLIT_SELF_IDENTIFICATION = "dialogue_structural_split_identification_with_reticent_reporter"
_RETICENT_REPORTER = re.compile(
    rf" *(?P<report>faltered|stammered|murmured) +(?P<det>the) +(?P<shrink>shrinking|trembling) +"
    rf"(?P<child>child|girl|boy), +(?P<not>not) +(?P<dare>daring) +(?P<to>to) +(?P<make>make) +"
    rf"(?P<stipulations>(?:any|further) +(?:stipulations|remarks|comments)) +"
    r"(?P<regarding>regarding) +(?P<article>the) +(?P<spelling>spelling|pronunciation) +(?P<thereof>thereof), *"
)
_AGE = re.compile(
    r"(?P<and>and) +(?P<i>I)(?P<be>[’']m) +"
    r"(?P<count>two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty) +"
    r"(?P<years>years) +(?P<old>old)"
)


def plan_split_self_identification(text, components):
    q = sorted((c for c in components if c.get("function") == "direct_speech"),key=lambda c:c["start"])
    if len(q)!=2 or q[0]["start"]!=0 or q[1]["end"]!=len(text):
        return None
    b,c = q[0]["end"],q[1]["start"]
    if text[b-2:b-1]!="," or text[-2:-1]!=".":
        return None
    if [(x.start,x.end,x.side) for x in quotation_boundaries(text)] != [
        (0,1,"open"),(b-1,b,"close"),(c,c+1,"open"),(len(text)-1,len(text),"close"),
    ]:
        return None
    if not re.fullmatch("[A-Z][a-z]+ [A-Z][a-z]+",text[1:b-2]):
        return None
    m,t = _RETICENT_REPORTER.fullmatch(text[b:c]),_AGE.fullmatch(text[c+1:-2])
    if m is None or t is None:
        return None
    specs,add,mark,part = _specs()
    mark("OPEN-QUOTE",0,1)
    add("NP",1,b-2,"phrase",proof_rule="np_name_seq2")
    mark("COMMA",b-2,b-1)
    mark("CLOSE-QUOTE",b-1,b)
    part(m,b,(
        ("report","V","lexical-alternatives",_v("finite","intransitive",lemma_in="falter|stammer|murmur")),
        ("det","DET","lexical",{"definiteness":"definite","number":"singular"}),
        ("shrink","V","lexical-alternatives",_v("ing","intransitive")),
        ("child","N","lexical",{"number":"singular"}),
    ))
    mark("COMMA",b+m.end("child"),b+m.end("child")+1)
    part(m,b,(
        ("not","NEG","lexical",{"negation":"true"}),
        ("dare","V","lexical-alternatives",_v("ing","subject_control",lemma_in="dare")),
        ("to","TO","lexical",{}),
        ("make","V","lexical-alternatives",_v("base","transitive",lemma_in="make")),
        ("stipulations","NP","phrase",{"proof_rule":"np_det_n","number":"plural"}),
        ("regarding","PREP","source-regarding-preposition",{}),
        ("article","DET","lexical",{"definiteness":"definite"}),
        ("spelling","N","lexical",{"number":"singular"}),
        ("thereof","ADV","lexical",{}),
    ))
    mark("COMMA",b+m.end("thereof"),b+m.end("thereof")+1)
    mark("OPEN-QUOTE",c,c+1)
    part(t,c+1,(
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("i","NP","subject-phrase",{}),
        ("be","COPULA","lexical",{"vform":"finite"}),
        ("count","NUM","lexical",{}),
        ("years","N","lexical",{"number":"plural"}),
        ("old","ADJ","lexical",{}),
    ))
    mark("SPEECH-STOP",len(text)-2,len(text)-1)
    mark("CLOSE-QUOTE",len(text)-1,len(text))
    return specs


DOUBLE_PERFECT_PERSPECTIVE = "dialogue_structural_reported_nested_perfect_and_past_perspective"
_PERSPECTIVE = re.compile(
    rf"(?P<speaker>I) +(?P<never>never) +(?P<would>would|could) +(?P<have>have) +"
    rf"(?P<think>thought|guessed|expected) +(?P<subject>{_PRON})(?P<modal>[’']d) +(?P<have2>have) +"
    rf"(?P<turn>turned) +(?P<out>out) +(?P<so>so) +(?P<well>well|badly) +"
    r"(?P<day>that (?:first|second) (?:day|night|morning|evening)) +"
    r"(?P<observer>I) +(?P<be>was) +(?P<place>here|there) +"
    r"(?P<elapsed>(?:one|two|three|four|five|six|seven|eight|nine|ten) (?:year|years|month|months|day|days)) +(?P<ago>ago)"
)
_TITLED_REPORT = re.compile(r"(?P<verb>[a-z]+) +(?P<speaker>(?:Mr|Mrs|Ms|Dr)[.] +[A-Z][a-z]+)")


def plan_double_perfect_perspective(text, components):
    scoped = _single_spoken_span(text,components,reported=True)
    if scoped is None or text[scoped[0]] != ",":
        return None
    stop,r = scoped
    m,t = _PERSPECTIVE.fullmatch(text[1:stop]),_TITLED_REPORT.fullmatch(text[r["start"]:r["end"]])
    if m is None or t is None:
        return None
    if (m["elapsed"].startswith("one ")) == m["elapsed"].endswith("s"):
        return None
    specs,_,mark,part = _specs()
    mark("OPEN-QUOTE",0,1)
    part(m,1,(
        ("speaker","NP","subject-phrase",{}),
        ("never","ADV","lexical",{}),
        ("would","MODAL","lexical",{"vform":"finite"}),
        ("have","HAVE","lexical",{"vform":"base"}),
        ("think","V","lexical-alternatives",_v("ed","clausal")),
        ("subject","NP","subject-phrase",{}),
        ("modal","MODAL","lexical",{"vform":"finite"}),
        ("have2","HAVE","lexical",{"vform":"base"}),
        ("turn","V","lexical-alternatives",_v("ed","intransitive",lemma_in="turn")),
        ("out","PARTICLE","lexical",{}),
        ("so","DEGREE","lexical",{"scalar_degree":"true"}),
        ("well","ADV","lexical",{}),
        ("day","NP","phrase",{"proof_rule":"np_det_n"}),
        ("observer","NP","subject-phrase",{}),
        ("be","COPULA","lexical",{"vform":"finite"}),
        ("place","ADV","lexical",{}),
        ("elapsed","NP","phrase",{"proof_rule":"np_num_n_time"}),
        ("ago","ADV","lexical",{}),
    ))
    mark("COMMA",stop,stop+1)
    mark("CLOSE-QUOTE",stop+1,stop+2)
    part(t,r["start"],(
        ("verb","V","lexical-alternatives",_v("finite","clausal",lemma_in=_REPORT_VERBS)),
        ("speaker","NP","proper-phrase",{}),
    ))
    mark("SPEECH-STOP",len(text)-1,len(text))
    return specs


HESITANT_RESUMPTION = "dialogue_structural_restart_after_hesitant_intercalated_report"
_RESTART_TAG = re.compile(
    rf" *(?P<report>said|muttered|whispered) +(?P<speaker>a +very +[a-z-]+ +(?:man|woman|boy|girl)), +"
    rf"(?P<making>making) +(?P<efforts>[a-z-]+ +efforts) +(?P<to>to) +(?P<action>relight|light) +"
    rf"(?P<object>(?:his|her) +(?:cigar|pipe)) +(?P<where>over +the +{_NP}); *"
)
_RESTART_CONTENT = re.compile(
    r"(?P<subject>that|this) +(?P<dots>[.] +[.] +[.]) +(?P<degree>very) +"
    r"(?P<attribute>clear|plain|simple|obvious) +(?P<indeed>indeed)"
)


def plan_hesitant_resumption(text,components):
    by_id = {c.get("id"):c for c in components}
    q,r,t,resumed = (by_id.get(i) for i in ("q0","r0","t0","q1"))
    if not (q and r and t and resumed and q["start"]==0 and resumed["end"]==len(text)
            and q.get("governor")=="r0" and resumed.get("governor")=="q0"
            and r.get("governor")=="t0" and t.get("function")=="split_direct_speech_turn"):
        return None
    b,c = q["end"],resumed["start"]
    if text[b-2:b-1]!="," or text[-2:-1]!=".":
        return None
    if [(mark.start,mark.end,mark.side) for mark in quotation_boundaries(text)] != [
        (0,1,"open"),(b-1,b,"close"),(c,c+1,"open"),(len(text)-1,len(text),"close"),
    ]:
        return None
    m,n = _RESTART_TAG.fullmatch(text[b:c]),_RESTART_CONTENT.fullmatch(text[c+1:-2])
    if m is None or n is None or text[1:b-2].casefold()!=n["subject"]:
        return None
    if (r["start"],r["end"]) != (b+m.start("report"),b+m.end("where")):
        return None
    specs,add,mark,part=_specs()
    mark("OPEN-QUOTE",0,1)
    add("PRONOUN",1,b-2,definiteness="demonstrative")
    mark("COMMA",b-2,b-1)
    mark("CLOSE-QUOTE",b-1,b)
    part(m,b,(
        ("report","V","lexical-alternatives",_v("finite","clausal",lemma_in=_REPORT_VERBS)),
        ("speaker","NP","phrase",{"proof_rule":"np_det_degree_n"}),
    ))
    mark("COMMA",b+m.end("speaker"),b+m.end("speaker")+1)
    part(m,b,(
        ("making","V","lexical-alternatives",_v("ing","transitive",lemma_in="make")),
        ("efforts","NP","phrase",{"proof_rule":"np_bare","number":"plural"}),
        ("to","TO","lexical",{}),
        ("action","V","lexical-alternatives",_v("base","transitive",lemma_in="relight|light")),
        ("object","NP","phrase",{"proof_rule":"np_poss"}),
        ("where","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    mark("SEMICOLON",b+m.end("where"),b+m.end("where")+1)
    mark("OPEN-QUOTE",c,c+1)
    part(n,c+1,(
        ("subject","PRONOUN","lexical",{"definiteness":"demonstrative"}),
        ("dots","SPACED-ELLIPSIS","source-punctuation",{}),
        ("degree","DEGREE","lexical",{}),
        ("attribute","ADJ","lexical",{}),
        ("indeed","ADV","lexical",{"postadjectival":"true"}),
    ))
    mark("SPEECH-STOP",len(text)-2,len(text)-1)
    mark("CLOSE-QUOTE",len(text)-1,len(text))
    return specs
