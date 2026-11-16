"""Source-scoped motion predications with nonfinite and locative supplements."""
from __future__ import annotations

import re

from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _NP, _PRON, _WORD, _matrix, _v

CARRY = "structural_shared_motion_with_object_participial_supplement"
RISE = "structural_temporal_particle_and_right_circumstance"
APPOSITIVE = "structural_semicolon_family_apposition_and_float_all"
_CARRY = re.compile(
    rf"(?P<subject>{_PRON}) +(?P<grasp>caught|picked|lifted|snatched|scooped) +(?P<up>up) +"
    rf"(?P<object>(?:the|a|an|his|her|their|my|our|your) +{_NP}?) +(?P<manner>[a-z]+ly), +"
    rf"(?P<and>and) +(?P<carry>carried|took|brought|passed) +(?P<it>it), +"
    rf"(?P<flare>flaring|glowing|burning|shining) +(?P<quality>red|white|blue|yellow|green|orange), +"
    rf"(?P<via>through +{_NP}?) +(?P<goal>into +{_NP})[.]",
    re.IGNORECASE,
)
_RISE = re.compile(
    rf"(?P<then>Then), +(?P<rise>getting|standing|rising) +(?P<up>up), +"
    rf"(?P<subject>{_PRON}) +(?P<move>went|walked|stepped|crossed|moved) +"
    rf"(?P<goal>to +{_NP}), +(?P<and>and) +(?P<with>with) +"
    rf"(?P<back>(?:his|her|their|my|our|your) +back) +(?P<facing>to +(?:me|him|her|us|them|you)) +"
    rf"(?P<right>began +to +{_NP})[.]",
    re.IGNORECASE,
)
_APPOSITIVE = re.compile(
    r"(?P<then>Then) +(?P<subject>[A-Z][a-z]+[’']s +(?:cousins|sisters|brothers|children|friends|relatives)), +"
    r"(?P<the>the) +(?P<name>[A-Z][a-z]+s) +(?P<origin>from +[A-Z][a-z]+), +"
    rf"(?P<arrived>came|arrived|returned); +(?P<they>they) +(?P<all>all) +"
    rf"(?P<move>crowded|climbed|piled|filed|scrambled) +(?P<goal>into +{_NP}), +"
    r"(?P<among>among) +(?P<bare>[a-z-]+) +(?P<and>and) +"
    r"(?P<other>[a-z-]+ +[a-z-]+s)[.]",
)


def _stop(text, mark):
    mark("SPEECH-STOP", len(text)-1, len(text))


def plan_carry(text, components):
    m = _CARRY.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m,0,(
        ("subject","NP","subject-phrase",{}),
        ("grasp","V","lexical-alternatives",_v("finite","transitive",lemma_in="catch|pick|lift|snatch|scoop")),
        ("up","PARTICLE","lexical",{}),
        ("object","NP","phrase",{"proof_rule":"np_det_n"}),
        ("manner","ADV","lexical",{}),
    ))
    mark("COMMA",m.end("manner"),m.end("manner")+1)
    part(m,0,(
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("carry","V","lexical-alternatives",_v("finite","transitive",lemma_in="carry|take|bring|pass")),
        ("it","NP","phrase",{"proof_rule":"np_indef_pron"}),
    ))
    mark("COMMA",m.end("it"),m.end("it")+1)
    part(m,0,(
        ("flare","V","lexical-alternatives",_v("ing","intransitive",lemma_in="flare|glow|burn|shine")),
        ("quality","ADJ","lexical",{}),
    ))
    mark("COMMA",m.end("quality"),m.end("quality")+1)
    part(m,0,(
        ("via","PP","phrase",{"proof_rule":"pp_prep_np"}),
        ("goal","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    _stop(text,mark)
    return specs


def plan_rise(text, components):
    m = _RISE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if m["back"].split()[0].casefold() not in {
        "i": {"my"}, "he": {"his"}, "she": {"her"}, "it": {"its"},
        "we": {"our"}, "you": {"your"}, "they": {"their"},
    }[m["subject"].casefold()]:
        return None
    specs, _, mark, part = _specs()
    part(m,0,(("then","ADV","lexical",{"deictic_time":"true"}),))
    mark("COMMA",m.end("then"),m.end("then")+1)
    part(m,0,(
        ("rise","V","lexical-alternatives",_v("ing","intransitive",lemma_in="get|stand|rise")),
        ("up","PARTICLE","lexical",{}),
    ))
    mark("COMMA",m.end("up"),m.end("up")+1)
    part(m,0,(
        ("subject","NP","subject-phrase",{}),
        ("move","V","lexical-alternatives",_v("finite","intransitive",lemma_in="go|walk|step|cross|move")),
        ("goal","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    mark("COMMA",m.end("goal"),m.end("goal")+1)
    part(m,0,(
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("with","PREP","lexical",{"lemma_in":"with"}),
        ("back","NP","phrase",{"proof_rule":"np_poss"}),
        ("facing","PP","phrase",{"proof_rule":"pp_prep_np"}),
        ("right","VP","phrase",{"proof_rule":"vp_to_inf","vform":"finite"}),
    ))
    _stop(text,mark)
    return specs


def plan_family_apposition(text, components):
    m = _APPOSITIVE.fullmatch(text)
    if m is None:
        return None
    semi = m.end("arrived")
    if not all(
        any(c.get("function") == function and c.get("governor") == parent
            and (c["start"],c["end"]) == span for c in components)
        for function,parent,span in (
            ("matrix_clause", "u0",(0,semi)),
            ("independent_clause","s0",(m.start("they"),len(text))),
        )
    ):
        return None
    specs, _, mark, part = _specs()
    part(m,0,(
        ("then","ADV","lexical",{"deictic_time":"true"}),
        ("subject","NP","phrase",{"proof_rule":"np_genitive","number":"plural"}),
    ))
    mark("COMMA",m.end("subject"),m.end("subject")+1)
    part(m,0,(
        ("the","DET","lexical",{"definiteness":"definite"}),
        ("name","N","lexical",{"number":"plural"}),
        ("origin","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    mark("COMMA",m.end("origin"),m.end("origin")+1)
    part(m,0,(("arrived","V","lexical-alternatives",_v("finite","intransitive",lemma_in="come|arrive|return")),))
    mark("SEMICOLON",m.end("arrived"),m.end("arrived")+1)
    part(m,0,(
        ("they","NP","subject-phrase",{}),
        ("all","PRONOUN","lexical",{"lemma_in":"all"}),
        ("move","V","lexical-alternatives",_v("finite","intransitive",lemma_in="crowd|climb|pile|file|scramble")),
        ("goal","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    mark("COMMA",m.end("goal"),m.end("goal")+1)
    part(m,0,(
        ("among","PREP","lexical",{}),
        ("bare","N","lexical",{}),
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("other","NP","phrase",{"number":"plural"}),
    ))
    _stop(text,mark)
    return specs


PARTITIVE_LOCATION = "structural_partitive_passive_relative_and_position"
_PARTITIVE = re.compile(
    rf"(?P<subject>{_PRON}) +(?P<take>took|picked|chose|selected) +(?P<one>one) +(?P<of>of) +"
    rf"(?P<set>the +{_NP}?) +(?P<rel>that|which) +(?P<be>were) +"
    rf"(?P<scatter>scattered|distributed|placed|spread) +(?P<where>(?:about|around|throughout) +{_NP}), +"
    rf"(?P<and>and) +(?P<place>set|placed|put) +(?P<it>it) +(?P<goal>in front of +{_NP}), +"
    rf"(?P<with>with) +(?P<count>two|three|four) +(?P<body>[a-z]+s) +(?P<surface>on +{_NP})[.]",
    re.IGNORECASE,
)


def plan_partitive_location(text, components):
    m = _PARTITIVE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m,0,(
        ("subject","NP","subject-phrase",{}),
        ("take","V","lexical-alternatives",_v("finite","transitive",lemma_in="take|pick|choose|select",nonbase_surface="true")),
        ("one","NUM","lexical",{}),
        ("of","PREP","lexical",{"lemma_in":"of"}),
        ("set","NP","phrase",{"proof_rule":"np_det_n","number":"plural"}),
        ("rel","WH-PRONOUN","lexical",{}),
        ("be","AUX-BE","lexical",{"vform":"finite","number":"plural"}),
        ("scatter","V","lexical-alternatives",_v("ed","transitive",lemma_in="scatter|distribute|place|spread")),
        ("where","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    mark("COMMA",m.end("where"),m.end("where")+1)
    part(m,0,(
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("place","V","lexical-alternatives",_v("finite","transitive",lemma_in="set|place|put")),
        ("it","NP","phrase",{"proof_rule":"np_indef_pron"}),
        ("goal","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    mark("COMMA",m.end("goal"),m.end("goal")+1)
    part(m,0,(
        ("with","PREP","lexical",{"lemma_in":"with"}),
        ("count","NUM","lexical",{}),
        ("body","N","lexical",{"number":"plural"}),
        ("surface","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    _stop(text,mark)
    return specs


SPELLING_RESULT = "structural_competitive_particle_and_object_result"
_SPELLING = re.compile(
    rf"(?P<subject>[A-Z][a-z]+ [A-Z][a-z]+) +(?P<spell>spelled|spelt) +(?P<her>him|her|them) +(?P<down>down) +"
    rf"(?P<class>in +class) +(?P<and>and) +(?P<leave>left) +(?P<object>him|her|them) +"
    rf"(?P<clear>clear|far|well) +(?P<state>out +of +sight) +(?P<domain>in +{_NP})[.]"
)


def plan_competitive_result(text, components):
    m = _SPELLING.fullmatch(text)
    if m is None or not _matrix(text, components) or m["her"] != m["object"]:
        return None
    specs, _, mark, part = _specs()
    part(m,0,(
        ("subject","NP","phrase",{"proof_rule":"np_name_seq2"}),
        ("spell","V","lexical-alternatives",_v("finite","transitive",lemma_in="spell")),
        ("her","PRONOUN","lexical",{"case":"accusative"}),
        ("down","PARTICLE","lexical",{}),
        ("class","PP","phrase",{"proof_rule":"pp_prep_np"}),
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("leave","V","lexical-alternatives",_v("finite","complex_transitive",lemma_in="leave")),
        ("object","PRONOUN","lexical",{"case":"accusative"}),
        ("clear","ADV","lexical",{}),
        ("state","ADV","lexical",{}),
        ("domain","PP","phrase",{"proof_rule":"pp_prep_np"}),
    ))
    _stop(text,mark)
    return specs


CAUSATIVE_RESPONSE = "structural_sound_apposition_with_intercalated_causative_controller"
_CAUSATIVE = re.compile(
    rf"(?P<source>[A-Z][a-z]+ [A-Z][a-z]+) +(?P<manner>[a-z]+ly) +(?P<sound>laughed|shouted|cried|coughed)"
    rf"(?P<dash>--|—)(?P<event>a +sound) +(?P<which>which) +(?P<cause>caused|prompted) +"
    rf"(?P<controller>[A-Z][a-z]+), +(?P<waiting>waiting|standing|sitting) +"
    rf"(?P<emotion>in +[a-z-]+ +(?:anxiety|fear|alarm|distress|silence)) +"
    rf"(?P<location>in +the +[a-z-]+) +(?P<outside>outside|upstairs|downstairs), +"
    rf"(?P<to>to) +(?P<action>give|utter|heave) +(?P<object>(?:a|an) +{_NP})[.]"
)


def plan_causative_response(text, components):
    m = _CAUSATIVE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m,0,(
        ("source","NP","phrase",{"proof_rule":"np_name_seq2"}),
        ("manner","ADV","lexical",{}),
        ("sound","V","lexical-alternatives",_v("finite","intransitive",lemma_in="laugh|shout|cry|cough")),
        ("dash","DASH","source-punctuation",{}),
        ("event","NP","phrase",{"proof_rule":"np_det_n"}),
        ("which","WH-PRONOUN","lexical",{}),
        ("cause","V","lexical-alternatives",_v("finite","object_control",lemma_in="cause|prompt")),
        ("controller","NP","proper-phrase",{}),
    ))
    mark("COMMA",m.end("controller"),m.end("controller")+1)
    part(m,0,(
        ("waiting","V","lexical-alternatives",_v("ing","intransitive",lemma_in="wait|stand|sit")),
        ("emotion","PP","phrase",{"proof_rule":"pp_prep_np"}),
        ("location","PP","phrase",{"proof_rule":"pp_prep_np"}),
        ("outside","ADV","lexical",{}),
    ))
    mark("COMMA",m.end("outside"),m.end("outside")+1)
    part(m,0,(
        ("to","TO","lexical",{}),
        ("action","V","lexical-alternatives",_v("base","transitive")),
        ("object","NP","phrase",{}),
    ))
    _stop(text,mark)
    return specs


COORDINATED_PARTICIPLES = "structural_coordinated_accidental_actions_with_temporal_boundary"
_ACCIDENTAL = re.compile(
    rf"(?P<subject>[A-Z][a-z]+) +(?P<main>lighted|lit|started|opened) +(?P<object>the +{_NP}), +"
    rf"(?P<first>oversetting|upsetting|overturning|knocking) +(?P<first_object>the +{_NP}?) +(?P<and>and) +"
    rf"(?P<second>using) +(?P<up>up) +(?P<half>half) +(?P<article>a) +(?P<dozen>dozen) +"
    rf"(?P<units>[a-z-]+s) +(?P<before>before) +(?P<poss>her|his|their) +"
    rf"(?P<shaking>shaking|trembling) +(?P<hands>hands|fingers) +(?P<modal>could|would) +"
    rf"(?P<act>accomplish|finish|complete) +(?P<task>the +{_NP})[.]"
)


def plan_accidental_participles(text, components):
    m = _ACCIDENTAL.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, mark, part = _specs()
    part(m,0,(
        ("subject","NP","proper-phrase",{}),
        ("main","V","lexical-alternatives",_v("finite","transitive",lemma_in="light|start|open")),
        ("object","NP","phrase",{"proof_rule":"np_det_n"}),
    ))
    mark("COMMA",m.end("object"),m.end("object")+1)
    part(m,0,(
        ("first","V","lexical-alternatives",_v("ing","transitive",lemma_in="overset|upset|overturn|knock")),
        ("first_object","NP","phrase",{"proof_rule":"np_det_n"}),
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("second","V","lexical-alternatives",_v("ing","transitive",lemma_in="use")),
        ("up","PARTICLE","lexical",{}),
        ("half","DET","lexical",{"predeterminer":"fractional"}),
        ("article","DET","lexical",{"definiteness":"indefinite"}),
        ("dozen","N","lexical",{"number":"singular"}),
        ("units","N","lexical",{"number":"plural"}),
        ("before","CONJ","lexical",{"lemma_in":"before"}),
        ("poss","POSS","lexical",{}),
        ("shaking","V","lexical-alternatives",_v("ing","intransitive",lemma_in="shake|tremble")),
        ("hands","N","lexical",{"number":"plural"}),
        ("modal","MODAL","lexical",{"vform":"finite"}),
        ("act","V","lexical-alternatives",_v("base","transitive")),
        ("task","NP","phrase",{"proof_rule":"np_det_n"}),
    ))
    _stop(text,mark)
    return specs
