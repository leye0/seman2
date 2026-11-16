"""Bounded plans for independently licensed patterns in narrative sentences."""
from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

CAUSAL_PERFECT = "structural_causal_perfect_intransitive_with_pp"
NOMINAL_EXCLAMATION = "structural_name_modified_nominal_exclamation"
NEGATIVE_PROFORM = "structural_contrastive_negative_proform"
CONTRASTIVE_SERIES = "structural_shared_subject_contrastive_vp_series"

_WORD = r"[a-z][a-z’-]*"
_NP = rf"{_WORD}(?: +{_WORD}){{0,7}}"
_CAP_NP = re.compile(r"(?P<det>A[n]?|a[n]?) +(?P<name>[A-Z][a-z]+) +(?P<noun>[a-z][a-z-]*)!")
_CAUSAL = re.compile(
    rf"For +(?P<subject>{_NP}?) +(?P<have>had|have|has) +(?P<adv>[a-z]+ly) +"
    rf"(?P<verb>[a-z]+ed) +(?P<pp>(?:with|in|from|into|on|at|to) +{_NP})[.]",
    re.IGNORECASE,
)
_NONE = re.compile(r"But +(?P<proform>none) +(?P<verb>[a-z]+ed)[.]", re.IGNORECASE)
_SERIES = re.compile(
    rf"(?P<subject>I|he|she|we|they|you|it) +(?P<v1>{_WORD}) +(?P<np1>not +{_NP}), +"
    rf"(?P<but>but) +(?P<v2>come|comes|came|go|goes|went|walk|walks|walked|move|moves|moved) +"
    rf"(?P<adv>[a-z]+ly) +(?P<pp>(?:to|towards|toward|into|onto) +{_NP}), +"
    rf"(?P<and>and) +(?P<v3>{_WORD}) +(?P<np3>{_NP})[.]",
    re.IGNORECASE,
)


def _matrix(text, components):
    return (
        any(c.get("function") == "matrix_clause" and (c["start"], c["end"]) == (0, len(text))
            for c in components)
        and not any(c.get("function") in ("direct_speech", "reporting_clause") for c in components)
    )


def _v(form, frame, **extra):
    return {"vform": form, "subcat_member": frame, **extra}


def plan_causal_perfect(text, components):
    match = _CAUSAL.fullmatch(text)
    if match is None or not _matrix(text, components):
        return None
    specs, add, marks, parts = _specs()
    add("COORD", 0, 3, causal_coordination="true")
    parts(match, 0, (
        ("subject", "NP", "phrase", {}),
        ("have", "HAVE", "lexical", {"vform": "finite"}),
        ("adv", "ADV", "lexical", {}),
        ("verb", "V", "lexical-alternatives", _v("ed", "intransitive")),
        ("pp", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    marks("SPEECH-STOP", len(text) - 1, len(text))
    return specs


def plan_nominal_exclamation(text, components):
    match = _CAP_NP.fullmatch(text)
    if match is None or any(c.get("function") == "direct_speech" for c in components):
        return None
    specs, _, marks, parts = _specs()
    parts(match, 0, (
        ("det", "DET", "lexical", {"definiteness": "indefinite", "number": "singular"}),
        ("name", "PROPER-NOUN", "lexical", {}),
        ("noun", "N", "lexical", {"number": "singular"}),
    ))
    marks("EXCL", len(text) - 1, len(text))
    return specs


def plan_negative_proform(text, components):
    match = _NONE.fullmatch(text)
    if match is None or not _matrix(text, components):
        return None
    specs, add, marks, parts = _specs()
    add("COORD", 0, 3, lemma_in="but")
    parts(match, 0, (
        ("proform", "NP", "source-negative-proform", {}),
        ("verb", "V", "lexical-alternatives", _v("finite", "intransitive")),
    ))
    marks("SPEECH-STOP", len(text) - 1, len(text))
    return specs


def plan_contrastive_series(text, components):
    match = _SERIES.fullmatch(text)
    if match is None or not _matrix(text, components):
        return None
    specs, add, marks, parts = _specs()
    parts(match, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("v1", "V", "lexical-alternatives", _v("finite", "transitive")),
        ("np1", "NP", "phrase", {}),
    ))
    marks("COMMA", match.end("np1"), match.end("np1") + 1)
    parts(match, 0, (
        ("but", "COORD", "lexical", {"lemma_in": "but"}),
        ("v2", "V", "lexical-alternatives", _v("finite", "intransitive")),
        ("adv", "ADV", "lexical", {}),
        ("pp", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    marks("COMMA", match.end("pp"), match.end("pp") + 1)
    parts(match, 0, (
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("v3", "V", "lexical-alternatives", _v("finite", "transitive")),
        ("np3", "NP", "phrase", {}),
    ))
    marks("SPEECH-STOP", len(text) - 1, len(text))
    return specs


PROGRESSIVE_REPORT = "structural_shared_subject_report_with_sentential_relative"
PROGRESSIVE_PERCEPTION = "structural_particle_action_and_progressive_perception"
REPORT_PLAN = "source_scoped_narrative_progressive_content"
_PRON = r"i|he|she|it|we|you|they"
_OBJ = r"me|him|her|it|us|you|them"
# Separate the lexical frame of the reporting predicate from that of the
# progressive. A local adverb, spoken recipient, or a PP is not its subject.
_REPORT = re.compile(
    rf"(?P<subject>{_NP}?) +(?P<see>{_WORD} +(?:at|into|towards?) +{_NP}?) +(?P<and>and), +"
    rf"(?P<manner>with +{_NP}), +(?P<tell>told|tell|tells) +(?P<recipient>{_OBJ}) +"
    rf"(?P<subj2>{_PRON}) +(?P<be>am|is|are|was|were) +(?P<ing>[a-z]+ing) +"
    rf"(?P<oblique>(?:from|at|for|to) +{_NP}), +(?P<relprep>at) +(?P<which>which) +"
    rf"(?P<relative>(?:{_PRON}) +{_WORD} +[a-z]+ly)[.]",
    re.IGNORECASE,
)
_PERCEPTION = re.compile(
    rf"(?P<then>Then) +(?P<subject>{_PRON}) +(?P<turn>turned|turns|turn) +(?P<over>over) +"
    rf"(?P<object>(?:the|his|her|their|my|our|your) +{_WORD} +[a-z]+ing +{_NP}), +(?P<and>and) +"
    rf"(?P<observer>{_PRON}) +(?P<see>saw|see|sees|noticed|notice|notices) +"
    rf"(?P<subj2>{_PRON}) +(?P<be>am|is|are|was|were) +(?P<ing>looking|staring|gazing|peering) +"
    rf"(?P<oblique>(?:at|into|through|towards?) +{_NP})[.]",
    re.IGNORECASE,
)
_RESULTATIVE = re.compile(
    rf"(?P<but>But) +(?P<subject>{_PRON}) +(?P<go>went|goes|go) +(?P<away>away) +"
    rf"(?P<manner>[a-z]+ly), +(?P<leave>leaving) +(?P<result_subject>[A-Z][a-z]+|{_OBJ}) +"
    rf"(?P<alone>alone) +(?P<to>to) +(?P<action>{_WORD}) +"
    rf"(?P<object>(?:the|a|an|my|your|his|her|our|their) +{_NP}?) +(?P<adjunct>with +{_NP})[.]"
)
RESULTATIVE_PURPOSE = "structural_departure_with_resultative_purpose"
_BE = {
    "i": {"am", "was"}, "he": {"is", "was"}, "she": {"is", "was"},
    "it": {"is", "was"}, "we": {"are", "were"}, "you": {"are", "were"},
    "they": {"are", "were"},
}


def _progressive_specs(parts, match, *, lemmas):
    if match["be"].casefold() not in _BE[match["subj2"].casefold()]:
        return False
    parts(match, 0, (
        ("subj2", "NP", "subject-phrase", {}),
        ("be", "AUX-BE", "lexical", {"vform": "finite"}),
        ("ing", "V", "lexical-alternatives", _v("ing", "prepositional", lemma_in=lemmas)),
        ("oblique", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    return True


def _subject_agrees(subject, verb, bare, inflected):
    return ((verb == inflected) == (subject in ("he", "she", "it"))
            if verb in (bare, inflected) else True)


def plan_report_with_relative(text, components):
    match = _REPORT.fullmatch(text)
    if match is None or not _matrix(text, components):
        return None
    subject, tell = (match[k].casefold() for k in ("subject", "tell"))
    if tell == "tell" and subject not in ("i", "you", "we", "they"):
        return None
    if subject in _BE and not _subject_agrees(subject, tell, "tell", "tells"):
        return None
    specs, add, marks, parts = _specs()
    parts(match, 0, (
        ("subject", "NP", "phrase", {}),
        ("see", "VP", "phrase", {"proof_rule": "vp_prepositional", "vform": "finite"}),
    ))
    add("COORD", match.start("and"), match.end("and"), lemma_in="and")
    marks("COMMA", match.end("and"), match.end("and") + 1)
    parts(match, 0, (("manner", "PP", "phrase", {"proof_rule": "pp_prep_np"}),))
    marks("COMMA", match.end("manner"), match.end("manner") + 1)
    parts(match, 0, (
        ("tell", "V", "lexical-alternatives", _v("finite", "clausal", lemma_in="tell")),
        ("recipient", "PRONOUN", "lexical", {"case": "accusative"}),
    ))
    if not _progressive_specs(parts, match, lemmas="suffer|look|stare|gaze|peer|wait"):
        return None
    marks("COMMA", match.end("oblique"), match.end("oblique") + 1)
    parts(match, 0, (
        ("relprep", "PREP", "lexical", {}),
        ("which", "WH-PRONOUN", "lexical", {}),
        ("relative", "CLAUSE", "phrase", {"proof_rule": "clause_np_vp"}),
    ))
    marks("SPEECH-STOP", len(text) - 1, len(text))
    return specs


def plan_perception_after_particle(text, components):
    match = _PERCEPTION.fullmatch(text)
    if match is None or not _matrix(text, components):
        return None
    for group, verb, bare, inflected in (
        ("subject", "turn", "turn", "turns"), ("observer", "see", "see", "sees"),
        ("observer", "see", "notice", "notices"),
    ):
        if not _subject_agrees(match[group].casefold(), match[verb].casefold(), bare, inflected):
            return None
    specs, _, marks, parts = _specs()
    parts(match, 0, (
        ("then", "ADV", "lexical", {"deictic_time": "true"}),
        ("subject", "NP", "subject-phrase", {}),
        ("turn", "V", "lexical-alternatives", _v("finite", "transitive", lemma_in="turn")),
        ("over", "PARTICLE", "lexical", {}),
        ("object", "NP", "phrase", {"proof_rule": "np_part_ing"}),
    ))
    marks("COMMA", match.end("object"), match.end("object") + 1)
    parts(match, 0, (
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("observer", "NP", "subject-phrase", {}),
        ("see", "V", "lexical-alternatives", _v("finite", "clausal", lemma_in="see|notice")),
    ))
    if not _progressive_specs(parts, match, lemmas="look|stare|gaze|peer"):
        return None
    marks("SPEECH-STOP", len(text) - 1, len(text))
    return specs


def plan_departure_resultative(text, components):
    match = _RESULTATIVE.fullmatch(text)
    if match is None or not _matrix(text, components):
        return None
    if not _subject_agrees(match["subject"], match["go"], "go", "goes"):
        return None
    specs, _, marks, parts = _specs()
    parts(match, 0, (
        ("but", "COORD", "lexical", {"lemma_in": "but"}),
        ("subject", "NP", "subject-phrase", {}),
        ("go", "V", "lexical-alternatives", _v("finite", "intransitive", lemma_in="go")),
        ("away", "PARTICLE", "lexical", {}),
        ("manner", "ADV", "lexical", {}),
    ))
    marks("COMMA", match.end("manner"), match.end("manner") + 1)
    parts(match, 0, (
        ("leave", "V", "lexical-alternatives", _v("ing", "complex_transitive", lemma_in="leave")),
        ("result_subject", "NP", "phrase", {}),
        ("alone", "ADJ", "lexical", {}),
        ("to", "TO", "lexical", {}),
        ("action", "V", "lexical-alternatives", _v("base", "transitive")),
        ("object", "NP", "phrase", {}),
        ("adjunct", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    marks("SPEECH-STOP", len(text) - 1, len(text))
    return specs


PARENTHETICAL_PURPOSE = "structural_parenthesized_purpose_and_shared_attempt"
_OUTER_PURPOSE = re.compile(
    rf"\((?P<subject>The +[A-Z][a-z]+), +(?P<to1>to) +(?P<show>show|demonstrate|prove) +(?P<that>that) +"
    rf"(?P<subj2>{_PRON}) +(?P<be>was|were) +(?P<neg>not) +(?P<state>[a-z-]+), +"
    r"(?P<help>helped) +(?P<self>himself|herself|themselves) +(?P<resource>to +(?:a|an|some|the) +[a-z-]+) +"
    rf"(?P<and>and) +(?P<try>tried|attempted) +(?P<to2>to) +(?P<action>light|read|use|eat) +"
    r"(?P<object>it) +(?P<condition>uncut|unlit|unopened|unwashed|raw)[.]\)"
)
_REFLEXIVES = {"he": "himself", "she": "herself", "they": "themselves"}


def plan_parenthesized_purpose(text, components):
    m = _OUTER_PURPOSE.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if not any(c.get("function") == "parenthetical_candidate" and c.get("governor") == "s0"
               and (c["start"], c["end"]) == (0, len(text)) for c in components):
        return None
    subj = m["subj2"]
    if _REFLEXIVES.get(subj) != m["self"] or m["be"] not in _BE[subj]:
        return None
    specs, _, mark, part = _specs()
    mark("OPEN-PAREN",0,1)
    part(m,0,(("subject","NP","phrase",{"proof_rule":"np_det_n"}),))
    mark("COMMA",m.end("subject"),m.end("subject")+1)
    part(m,0,(
        ("to1","TO","lexical",{}),
        ("show","V","lexical-alternatives",_v("base","clausal")),
        ("that","COMP-THAT","lexical",{}),
        ("subj2","NP","subject-phrase",{}),
        ("be","COPULA","lexical",{"vform":"finite"}),
        ("neg","NEG","lexical",{"negation":"true"}),
        ("state","ADJ","lexical",{}),
    ))
    mark("COMMA",m.end("state"),m.end("state")+1)
    part(m,0,(
        ("help","V","lexical-alternatives",_v("finite","transitive",lemma_in="help")),
        ("self","PRONOUN","lexical",{"reflexive":"true"}),
        ("resource","PP","phrase",{"proof_rule":"pp_prep_np"}),
        ("and","COORD","lexical",{"lemma_in":"and"}),
        ("try","V","lexical-alternatives",_v("finite","subject_control",lemma_in="try|attempt")),
        ("to2","TO","lexical",{}),
        ("action","V","lexical-alternatives",_v("base","transitive")),
        ("object","NP","phrase",{"proof_rule":"np_indef_pron"}),
        ("condition","ADJ","lexical",{}),
    ))
    mark("SPEECH-STOP",len(text)-2,len(text)-1)
    mark("CLOSE-PAREN",len(text)-1,len(text))
    return specs


DASH_REFORMULATION = "structural_nominal_reformulation_with_shared_infinitival_complement"
_REFORMULATION = re.compile(
    rf"(?P<in>In) +(?P<writing>writing|setting|taking) +(?P<it>it) +(?P<particle>down) +"
    rf"(?P<subject>I) +(?P<feel>feel|felt|realize|realized) +(?P<manner>with +only +too +much +[a-z-]+) +"
    rf"(?P<left>the +(?P<anchor>inadequacy|inability|failure) +of +{_NP}?)"
    rf"(?P<dash1>—|--)(?P<and>and), +(?P<above>above +all), +"
    rf"(?P<right>my +own +(?P=anchor))(?P<dash2>—|--)(?P<to>to) +"
    rf"(?P<verb>express|describe|capture|convey) +(?P<object>(?:its|their|the) +{_NP})[.]"
)


def plan_dash_reformulation(text,components):
    m = _REFORMULATION.fullmatch(text)
    if m is None or not _matrix(text,components) or m["dash1"]!=m["dash2"]:
        return None
    specs,_,mark,part = _specs()
    part(m,0,(
        ("in","PREP","lexical",{}),
        ("writing","V","lexical-alternatives",_v("ing","transitive")),
        ("it","NP","phrase",{"proof_rule":"np_indef_pron"}),
        ("particle","PARTICLE","lexical",{}),
        ("subject","NP","subject-phrase",{}),
        ("feel","V","lexical-alternatives",_v("finite","transitive")),
        ("manner","PP","phrase",{"proof_rule":"pp_prep_np"}),
        ("left","NP","phrase",{}),
        ("dash1","DASH","source-punctuation",{}),
        ("and","COORD","lexical",{"lemma_in":"and"}),
    ))
    mark("COMMA",m.end("and"),m.end("and")+1)
    part(m,0,(("above","ADV","lexical",{}),))
    mark("COMMA",m.end("above"),m.end("above")+1)
    part(m,0,(
        ("right","NP","phrase",{"proof_rule":"np_poss"}),
        ("dash2","DASH","source-punctuation",{}),
        ("to","TO","lexical",{}),
        ("verb","V","lexical-alternatives",_v("base","transitive")),
        ("object","NP","phrase",{}),
    ))
    mark("SPEECH-STOP",len(text)-1,len(text))
    return specs
