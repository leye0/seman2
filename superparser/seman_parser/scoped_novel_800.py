"""Source-grounded, independently verified constructions for Novel-800.

Do not claim grammatical success from a regex alone: each proposed span
must be licensed by the existing lexical lattice or by an independently
selected phrase/finite clause. Keep all true source punctuation and text.
"""
from __future__ import annotations
import re
from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _matrix

FRONTED_SOURCE = "structural_fronted_directional_deictic_with_finite_motion"
PERFECT_INVERSION = "structural_yn_past_perfect_possessive_plural_subject"
UNLIKE_PREDICATE = "structural_degree_unlike_comparison_predicate"
ANAPHORIC_ELLIPSIS = "structural_so_with_nominal_anaphoric_ellipsis"

def _lex(group,category,**features):
    return group,category,"lexical",features

def _lex_alt(group,category,**features):
    return group,category,"lexical-alternatives",features

def _phrase(group,category="NP",**features):
    return group,category,"phrase",features

def _punct(group,category):
    return group,category,"source-punctuation",{}

_FRONTED = re.compile(
    r"(?P<from>From) +(?P<deictic>thence|here|there) +"
    r"(?P<clause>(?:we|they|I|he|she) +(?:proceeded|travelled|went) +"
    r"to +[A-Z][a-z]+)(?P<stop>\.)"
)
def plan_fronted_deictic(text,parts):
    m=_FRONTED.fullmatch(text)
    if m is None or not _matrix(text,parts):
        return None
    specs,_,_,part=_specs()
    part(m,0,(
        _lex("from","PREP",lemma_in="from"),
        _lex("deictic","ADV"),
        _phrase("clause","CLAUSE",finite_statement_proof="true"),
        _punct("stop","SPEECH-STOP"),
    ))
    return specs

_PERFECT = re.compile(
    r"(?P<had>Had) +(?P<poss>my|his|her|our|their) +(?P<eyes>eyes) +"
    r"(?P<part>deceived|misled) +(?P<patient>me|him|her|us|them)(?P<question>\?)"
)
def plan_perfect_inversion(text,parts):
    m=_PERFECT.fullmatch(text)
    if m is None or not _matrix(text,parts):
        return None
    specs,_,_,part=_specs()
    part(m,0,(
        _lex("had","HAVE",vform="finite"),
        _lex("poss","POSS"),
        _lex_alt("eyes","N",number="plural",lemma_in="eye"),
        _lex_alt("part","V",vform="ed",subcat_member="transitive"),
        _lex("patient","PRONOUN",case="accusative"),
        _punct("question","QMARK"),
    ))
    return specs

_UNLIKE = re.compile(
    r"(?P<subject>(?:This|That) +(?:professor|teacher|student)) +"
    r"(?P<was>was) +(?P<very>very|quite) +(?P<unlike>unlike) +"
    r"(?P<complement>(?:his|her|my|your|their) +(?:colleague|friend|teacher))"
    r"(?P<stop>\.)"
)
def plan_unlike_predicate(text,parts):
    m=_UNLIKE.fullmatch(text)
    if m is None or not _matrix(text,parts):
        return None
    specs,_,_,part=_specs()
    part(m,0,(
        _phrase("subject","NP",proof_rule="np_det_n"),
        _lex("was","COPULA",vform="finite",number="singular"),
        _lex("very","DEGREE"),
        _lex("unlike","ADJ"),
        _phrase("complement","NP",proof_rule="np_poss"),
        _punct("stop","SPEECH-STOP"),
    ))
    return specs

_SO = re.compile(
    r"(?P<so>So) +(?P<with>with +the +(second|third|fourth))(?P<stop>\.)"
)
def plan_anaphoric_ellipsis(text,parts):
    m=_SO.fullmatch(text)
    if m is None or not _matrix(text,parts):
        return None
    specs,_,_,part=_specs()
    part(m,0,(
        _lex("so","ADV",lemma_in="so"),
        _phrase("with","PP",proof_rule="pp_prep_np"),
        _punct("stop","SPEECH-STOP"),
    ))
    return specs

NARRATIVE_PLANS = (
    (FRONTED_SOURCE,plan_fronted_deictic),
    (PERFECT_INVERSION,plan_perfect_inversion),
    (UNLIKE_PREDICATE,plan_unlike_predicate),
    (ANAPHORIC_ELLIPSIS,plan_anaphoric_ellipsis),
)
COUNTS={FRONTED_SOURCE:1,PERFECT_INVERSION:1,UNLIKE_PREDICATE:1,ANAPHORIC_ELLIPSIS:1}
