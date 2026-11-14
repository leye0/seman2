"""Source spans for relatives attached to an internal nominal, not the clause."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

_WORD = r"[A-Za-z][A-Za-z’'\-]*"
_NP = r"[^,;.!?()]+?"
_SUBJECT = r"I|you|he|she|it|we|they"
PARTITIVE = re.compile(
    rf"(?P<subject>{_SUBJECT})\s+(?P<perfect>had)\s+(?P<neg>never)\s+"
    rf"(?P<verb>{_WORD})\s+(?P<of>of)\s+"
    rf"(?P<poss>my|your|his|her|its|our|their)\s+(?P<having>having)\s+"
    rf"(?P<held>{_WORD})\s+(?P<det>any|some|many|several)\s+(?P<set>{_WORD})"
    rf"(?P<c1>,)\s+(?P<except>except)\s+(?P<first_det>a|an)\s+(?P<first>{_WORD})\s+"
    rf"(?P<coord>and)\s+(?P<second>{_WORD})(?P<c2>,)\s+"
    rf"(?P<both>both)\s+(?P<rel_of>of)\s+(?P<whom>whom)\s+"
    rf"(?P<rel_have>had)\s+(?P<be>been)\s+(?P<adj>{_WORD})\s+"
    rf"(?P<duration>(?:many|several|few)"
    rf"\s+(?:days|weeks|months|years|decades))", re.I,
)
COORDINATED = re.compile(
    rf"(?P<subject>{_SUBJECT})\s+(?P<verb>{_WORD})\s+"
    rf"(?P<outer>the\s+{_WORD})\s+(?P<of>of)\s+"
    rf"(?P<inner>(?:my|your|his|her|its|our|their)\s+{_WORD})(?P<c1>,)\s+"
    rf"(?P<wh1>which)\s+(?P<rel_subject>{_SUBJECT})\s+"
    rf"(?P<action>{_WORD})\s+(?P<emphatic>myself|yourself|himself|herself|itself|ourselves|yourselves|themselves)"
    rf"\s+(?P<locative>upstairs|downstairs|inside|outside)\s+"
    rf"(?P<in>in)\s+(?P<place>{_NP})(?P<c2>,)\s+(?P<coord>and)\s+"
    rf"(?P<wh2>which)(?P<c3>,)\s+(?P<before>before)\s+(?P<time>{_NP})(?P<c4>,)\s+"
    rf"(?P<copula>was|were)\s+(?P<nothing>nothing)\s+(?P<but>but)\s+(?P<predicate>{_NP})", re.I,
)


def plan_nominal_relative_supplement(text):
    if not text.endswith("."):
        return None
    match = PARTITIVE.fullmatch(text[:-1]) or COORDINATED.fullmatch(text[:-1])
    if match is None:
        return None
    specs, add, punct, _ = _specs()

    def piece(group, cat, kind="phrase", **features):
        add(cat, *match.span(group), kind, **features)

    def lex(group, cat, **features):
        piece(group, cat, "lexical-alternatives", **features)

    def verb(group, form, frame, **features):
        lex(group, "V", vform=form, subcat_member=frame, **features)

    def comma(group):
        piece(group, "COMMA", "source-punctuation")

    piece("subject", "NP", "subject-phrase", pronominal="true")
    lex("of", "PREP", preposition_form="of")
    lex("coord", "COORD", nominal_coordination="true")
    comma("c1")
    comma("c2")
    if match.re is PARTITIVE:
        lex("perfect", "HAVE", vform="finite")
        lex("neg", "DEGREE", negation="true")
        verb("verb", "ed", "prepositional", relative_frame="report_of")
        lex("poss", "POSS")
        lex("having", "HAVE", vform="ing", perfect="true")
        verb("held", "ed", "transitive", relative_frame="possess")
        lex("det", "DET")
        lex("set", "N", number="plural")
        lex("except", "EXCEPTIVE", exception_marker="true")
        lex("first_det", "DET", number="singular")
        lex("first", "N", number="singular", relative_frame="human_nominal")
        lex("second", "N", number="singular", relative_frame="human_nominal")
        lex("both", "DET", quantifier="both", number="plural")
        lex("rel_of", "PREP", preposition_form="of")
        lex("whom", "WH-REL-OBL", relative="true")
        lex("rel_have", "HAVE", vform="finite")
        lex("be", "COPULA", vform="ed")
        lex("adj", "ADJ")
        piece("duration", "NP", proof_rule="np_det_n", number="plural")
    else:
        verb("verb", "finite", "transitive")
        piece("outer", "NP", proof_rule="np_det_n")
        piece("inner", "NP", proof_rule="np_poss")
        lex("wh1", "WH-REL-OBL", relative="true")
        piece("rel_subject", "NP", "subject-phrase", pronominal="true")
        verb("action", "finite", "transitive", nonbase_surface="true")
        lex("emphatic", "EMPHATIC-REFLEXIVE", gender_matches=match.group("rel_subject").casefold())
        lex("locative", "ADV")
        lex("in", "PREP")
        piece("place", "NP")
        lex("wh2", "WH-REL-OBL", relative="true")
        comma("c3")
        lex("before", "PREP")
        piece("time", "NP")
        comma("c4")
        lex("copula", "COPULA", vform="finite")
        lex("nothing", "INDEF-PRONOUN")
        lex("but", "EXCEPTIVE")
        piece("predicate", "NP")
    punct("SPEECH-STOP", len(text)-1, len(text))
    return sorted(specs, key=lambda row: row[1])
