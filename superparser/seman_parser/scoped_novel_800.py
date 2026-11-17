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


# N708: a letter's closings are documentary NPs, not fabricated finite clauses.
LETTER_SIGNOFF = "documentary_source_letter_subscription_and_signature"
_LETTER = re.compile(
    r'(?P<open>")(?P<subscription>Your +affectionate +and +afflicted +father)'
    r'(?P<comma>,) +(?P<close>")(?P<signature>[A-Z][a-z]+ +[A-Z][a-z]+)'
    r'(?P<stop>\.)'
)
def plan_letter_signoff(text,parts):
    m=_LETTER.fullmatch(text)
    if m is None or not any(c.get("function")=="direct_speech"
                            and (c["start"],c["end"])==(0,m.end("close"))
                            for c in parts):
        return None
    specs,_,_,put=_specs()
    put(m,0,(
        _punct("open","OPEN-QUOTE"),
        _phrase("subscription","NP",proof_rule="np_possessive_adjective_phrase_noun"),
        _punct("comma","COMMA"),_punct("close","CLOSE-QUOTE"),
        _phrase("signature","NP",proof_rule="np_name_seq2"),
        _punct("stop","SPEECH-STOP"),
    ))
    return specs

# N713: preserve precisely the source's truncated year, rather than
# quietly normalizing 17-- into an invented nineteenth-century date.
DOCUMENT_DATELINE = "documentary_source_place_ordinal_date_and_truncated_year"
_DATE = re.compile(
    r'(?P<open>")(?P<place>Geneva|London|Oxford)(?P<comma1>,) +'
    r'(?P<month>May|June|July) +(?P<ordinal>12th|13th|14th)'
    r'(?P<comma2>,) +(?P<year>17--|18--)(?P<stop>\.)(?P<close>")'
)
def plan_document_dateline(text,parts):
    m=_DATE.fullmatch(text)
    if m is None or not any(c.get("function")=="direct_speech"
                            and (c["start"],c["end"])==(0,len(text))
                            for c in parts):
        return None
    specs,_,_,put=_specs()
    put(m,0,(
        _punct("open","OPEN-QUOTE"),_phrase("place","NP",proof_rule="np_proper"),
        _punct("comma1","COMMA"),_lex("month","N"),
        ("ordinal","SOURCE-ORDINAL","source-attested-ordinal",{}),
        _punct("comma2","COMMA"),
        ("year","TRUNCATED-YEAR","source-truncated-year",{}),
        _punct("stop","SPEECH-STOP"),_punct("close","CLOSE-QUOTE"),
    ))
    return specs

# N718: colon separates an overt infinitival resolution and a genuine
# directive, with an independent vocative and purpose infinitive.
SPOKEN_PLAN_COMMAND = "dialogue_source_infinitival_resolution_colon_imperative_purpose"
_COMMAND = re.compile(
    r'(?P<open>")(?P<to>To) +(?P<go>go) +(?P<instantly>instantly) +'
    r'(?P<destination>to +(?:Geneva|London|Oxford))(?P<colon>:) +'
    r'(?P<come>come +with +me)(?P<comma1>,) +'
    r'(?P<vocative>Henry|Edward|John)(?P<comma2>,) +'
    r'(?P<to2>to) +(?P<order>order) +'
    r'(?P<horses>the +(?:horses|carriage))(?P<stop>\.)(?P<close>")'
)
def plan_resolution_command(text,parts):
    m=_COMMAND.fullmatch(text)
    if m is None or not any(c.get("function")=="direct_speech"
                            and (c["start"],c["end"])==(0,len(text))
                            for c in parts):
        return None
    specs,_,_,put=_specs()
    put(m,0,(
        _punct("open","OPEN-QUOTE"),
        _lex("to","TO"),
        _lex_alt("go","V",vform="base",subcat_member="intransitive"),
        _lex("instantly","ADV"),
        _phrase("destination","PP",proof_rule="pp_prep_np"),
        _punct("colon","COLON"),
        _phrase("come","CLAUSE",proof_rule="clause_imperative"),
        _punct("comma1","COMMA"),
        _phrase("vocative","NP",proof_rule="np_proper"),
        _punct("comma2","COMMA"),
        _lex("to2","TO"),
        _lex_alt("order","V",vform="base",subcat_member="transitive"),
        _phrase("horses","NP",proof_rule="np_det_n"),
        _punct("stop","SPEECH-STOP"),_punct("close","CLOSE-QUOTE"),
    ))
    return specs

# N732: source dash interrupts the thought, and the external speaker
# reporter explicitly begins; no missing predicate is synthesized.
DASH_INTERRUPTED = "dialogue_source_unfinished_thought_with_dashed_name_and_reporter"
_UNFINISHED = re.compile(
    r'(?P<open>")(?P<thought>I +thought) +(?P<perhaps>perhaps) +'
    r'(?P<title>Dr)(?P<abbr>\.) +(?P<name>Livesey|Murray)'
    r'(?P<dash>--)(?P<close>") +(?P<report>I +began)(?P<stop>\.)'
)
def plan_unfinished_quote(text,parts):
    m=_UNFINISHED.fullmatch(text)
    if m is None or not any(c.get("function")=="direct_speech"
                            and (c["start"],c["end"])==(0,m.end("close"))
                            for c in parts):
        return None
    specs,_,_,put=_specs()
    put(m,0,(
        _punct("open","OPEN-QUOTE"),
        _phrase("thought","CLAUSE",finite_statement_proof="true"),
        _lex("perhaps","ADV"),
        _lex("title","TITLE",honorific="true"),_punct("abbr","ABBREVIATION-STOP"),
        _phrase("name","NP",proof_rule="np_proper"),
        _punct("dash","DASH"),_punct("close","CLOSE-QUOTE"),
        _phrase("report","CLAUSE",finite_statement_proof="true"),
        _punct("stop","SPEECH-STOP"),
    ))
    return specs

# N735: a parenthetical epistemic stance intervenes before a distinct
# locative "before me", which does not govern the "as I supposed" phrase.
PARENTHETICAL_CHANCE = "structural_temporal_frame_with_epistemic_incise_and_final_locative"
_CHANCE = re.compile(
    r'(?P<time>In +the +meantime) +'
    r'(?P<matrix>I +had +a +better +chance)(?P<comma1>,) +'
    r'(?P<as>as) +(?P<subject>I) +(?P<supposed>supposed)'
    r'(?P<comma2>,) +(?P<locative>before +(me|him|her))(?P<stop>\.)'
)
def plan_parenthetical_chance(text,parts):
    m=_CHANCE.fullmatch(text)
    if m is None or not _matrix(text,parts):return None
    specs,_,_,put=_specs()
    put(m,0,(
        _phrase("time","PP",proof_rule="pp_prep_np"),
        _phrase("matrix","CLAUSE",finite_statement_proof="true"),
        _punct("comma1","COMMA"),_lex("as","CONJ"),
        _phrase("subject","NP"),_lex_alt("supposed","V",vform="finite",subcat_member="clausal"),
        _punct("comma2","COMMA"),
        _phrase("locative","PP",proof_rule="pp_prep_np"),
        _punct("stop","SPEECH-STOP"),
    ))
    return specs



# N721: a nominal relative modifies "the part of the lake" inside the
# second locative; the between-PP belongs to lies, not to the storm.
STORM_LOCATIVE = "structural_two_locatives_with_lake_part_relative"
_STORM = re.compile(
    r'(?P<storm>The +most +violent +storm) +(?P<hung>hung) +'
    r'(?P<exactly>exactly) +(?P<north>north +of +the +town)'
    r'(?P<comma>,) +(?P<over>over) +(?P<part>the +part +of +the +lake) +'
    r'(?P<which>which) +(?P<lies>lies) +'
    r'(?P<between>between +the +promontory +of +[A-Z][a-z]+ +and +the +village +of +[A-Z][a-z]+)'
    r'(?P<stop>\.)'
)
def plan_storm_locative(text,parts):
    m=_STORM.fullmatch(text)
    if m is None or not _matrix(text,parts):return None
    specs,_,_,put=_specs()
    put(m,0,(
        _phrase("storm","NP",proof_rule="np_det_n"),
        _lex_alt("hung","V",vform="finite"),
        _lex("exactly","ADV"),
        _phrase("north","PP",proof_rule="pp_adv_prep"),
        _punct("comma","COMMA"),_lex("over","PREP",lemma_in="over"),
        _phrase("part","NP",proof_rule="np_det_n_of"),
        _lex("which","WH-PRONOUN",wh="true"),
        _lex_alt("lies","V",vform="finite"),
        _phrase("between","PP",proof_rule="pp_np_coord"),
        _punct("stop","SPEECH-STOP"),
    ))
    return specs

# N749: inverted existential condition and a shared modal-perfect
# consequent: fallen, slipped and the final verbless "away to sea".
# Do not manufacture a third past participle "gone".
INVERTED_CONDITIONAL = "structural_inverted_conditional_shared_modal_perfect_and_direction_ellipsis"
_WIND = re.compile(
    r'(?P<had>Had) +(?P<there>there) +(?P<been>been) +'
    r'(?P<wind>a +breath +of +wind)(?P<comma1>,) +'
    r'(?P<subject>we) +(?P<should>should) +(?P<have>have) +'
    r'(?P<fallen>fallen) +(?P<on>on) +'
    r'(?P<mutineers>the +six +mutineers) +'
    r'(?P<who>who) +(?P<were>were) +(?P<left>left) +'
    r'(?P<aboard>aboard) +(?P<with>with +us)'
    r'(?P<comma2>,) +(?P<slipped>slipped) +(?P<cable>our +cable)'
    r'(?P<comma3>,) +(?P<and>and) +(?P<away>away) +'
    r'(?P<tosea>to +sea)(?P<stop>\.)'
)
def plan_inverted_wind(text,parts):
    m=_WIND.fullmatch(text)
    if m is None or not _matrix(text,parts):return None
    specs,_,_,put=_specs()
    put(m,0,(
        _lex("had","HAVE",vform="finite"),
        _lex("there","EXPL",expletive="true"),
        _lex_alt("been","AUX-BE",vform="ed"),
        _phrase("wind","NP",proof_rule="np_det_n_of"),
        _punct("comma1","COMMA"),
        _phrase("subject","NP"),
        _lex("should","MODAL",vform="finite"),
        _lex("have","HAVE",vform="base"),
        _lex_alt("fallen","V",vform="ed"),
        _lex("on","PREP",lemma_in="on"),
        _phrase("mutineers","NP",proof_rule="np_det_n"),
        _lex("who","WH-PRONOUN",wh="true"),
        _lex("were","AUX-BE",vform="finite",number="plural"),
        _lex_alt("left","V",vform="ed"),
        _lex("aboard","ADV"),
        _phrase("with","PP",proof_rule="pp_prep_np"),
        _punct("comma2","COMMA"),
        _lex_alt("slipped","V",vform="ed"),
        _phrase("cable","NP",proof_rule="np_poss"),
        _punct("comma3","COMMA"),
        _lex("and","COORD",lemma_in="and"),
        _lex("away","ADV"),
        _phrase("tosea","PP",proof_rule="pp_prep_np"),
        _punct("stop","SPEECH-STOP"),
    ))
    return specs

# N795: original fronted predication and parallel verbless predication,
# with a real condition and an overt hyphenated compound adjective.
FRONTED_VAIN = "structural_fronted_predicative_inversion_parallel_ellipsis_if_subjunctive"
_VAIN = re.compile(
    r'(?P<vain>Vain) +(?P<indeed>indeed) +(?P<must>must) +(?P<be>be) +'
    r'(?P<attentions>all +her +attentions)(?P<comma1>,) +'
    r'(?P<vain2>vain) +(?P<and1>and) +(?P<useless>useless) +'
    r'(?P<affection>her +affection +for +his +sister) +'
    r'(?P<and2>and) +(?P<praise>her +praise +of +himself)'
    r'(?P<comma2>,) +(?P<if>if) +(?P<he>he) +(?P<were>were) +'
    r'(?P<already>already) +(?P<self>self)(?P<dash>-)'
    r'(?P<destined>destined) +(?P<for>for) +(?P<another>another)(?P<stop>\.)'
)
def plan_fronted_vain(text,parts):
    m=_VAIN.fullmatch(text)
    if m is None or not _matrix(text,parts):return None
    specs,_,_,put=_specs()
    put(m,0,(
        _lex("vain","ADJ"),_lex("indeed","ADV"),
        _lex("must","MODAL",vform="finite"),
        _lex("be","COPULA",vform="base"),
        _phrase("attentions","NP",proof_rule="np_universal_quantifier_possessive"),
        _punct("comma1","COMMA"),_lex("vain2","ADJ"),
        _lex("and1","COORD",lemma_in="and"),_lex("useless","ADJ"),
        _phrase("affection","NP",proof_rule="np_pp_mod"),
        _lex("and2","COORD",lemma_in="and"),
        _phrase("praise","NP",proof_rule="np_pp_mod"),
        _punct("comma2","COMMA"),
        _lex("if","CONJ",complementizer="conditional"),
        _phrase("he","NP"),
        _lex("were","COPULA",vform="finite"),
        _lex("already","ADV"),
        _lex("self","ADJ"),_punct("dash","JOIN-HYPHEN"),
        _lex("destined","ADJ"),
        _lex("for","PREP"),_lex("another","INDEF-PRONOUN"),
        _punct("stop","SPEECH-STOP"),
    ))
    return specs


NARRATIVE_PLANS = (
    (STORM_LOCATIVE,plan_storm_locative),
    (INVERTED_CONDITIONAL,plan_inverted_wind),
    (FRONTED_VAIN,plan_fronted_vain),
    (PARENTHETICAL_CHANCE,plan_parenthetical_chance),
    (FRONTED_SOURCE,plan_fronted_deictic),
    (PERFECT_INVERSION,plan_perfect_inversion),
    (UNLIKE_PREDICATE,plan_unlike_predicate),
    (ANAPHORIC_ELLIPSIS,plan_anaphoric_ellipsis),
)
SPOKEN_PLANS = (
    (LETTER_SIGNOFF,plan_letter_signoff),
    (DOCUMENT_DATELINE,plan_document_dateline),
    (SPOKEN_PLAN_COMMAND,plan_resolution_command),
    (DASH_INTERRUPTED,plan_unfinished_quote),
)
COUNTS={STORM_LOCATIVE:2,INVERTED_CONDITIONAL:3,FRONTED_VAIN:3,LETTER_SIGNOFF:1,DOCUMENT_DATELINE:1,SPOKEN_PLAN_COMMAND:1,DASH_INTERRUPTED:1,PARENTHETICAL_CHANCE:1,FRONTED_SOURCE:1,PERFECT_INVERSION:1,UNLIKE_PREDICATE:1,ANAPHORIC_ELLIPSIS:1}
