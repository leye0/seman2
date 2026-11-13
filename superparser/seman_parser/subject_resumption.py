"""Source span proposals for a subject interrupted before its finite predicate.

The alternatives describe surface boundaries only. The shared assembler checks
each lexical reading and independently ranked phrase, then unifies one subject
and its resumed predicate. Supplement types keep their own scope and valency.
"""
from __future__ import annotations

import re

from .dialogue import quotation_boundaries
from .dialogue_clause_plans import _specs

ROOT = "structural_resumed_subject_utterance"
COORD_ROOT = "structural_resumed_subject_coordination"

# Named fields keep the spans, including punctuation, tied to their source.
# No corpus index, proper name, main verb or object identifies a construction.
W = r"[A-Za-z][A-Za-z'’\-]*"
S = r"[^,;.!?()]+?"
REL = rf"(?P<wh>which)\s+(?P<rs>{W})\s+(?P<rv>{W})"
COORD = r"(?P<and>and)"
PATTERNS = tuple((name, re.compile(pattern, re.I)) for name, pattern in (
    ("causal", rf"(?P<poss>{W})\s+(?P<n1>{W})(?P<c1>,)\s+(?P<n2>{W})(?P<c2>,)\s+{COORD}\s+(?P<n3>{W})(?P<open>,)\s+(?P<from>from)\s+(?P<adj>{W})\s+(?P<cause>{W})\s+(?P<to>to)\s+(?P<env1>{S})\s+(?P<env_and>and)\s+(?P<env2>{S})(?P<close>,)\s+(?P<vp>{S})"),
    ("concessive", rf"(?P<initial_subject>{W})\s+(?P<copula>{W})\s+(?P<frame>at the same time)\s+(?P<a1>{W})(?P<c1>,)\s+(?P<a2>{W})(?P<c2>,)\s+(?P<list_and>and)\s+(?P<a3>{W})(?P<boundary>,)\s+{COORD}\s+(?P<subject>{S})(?P<open>,)\s+(?P<though>though)\s+(?P<attr>{W})(?P<close>,)\s+(?P<vp>{S})"),
    ("relative", rf"(?P<subject>{S})(?P<open>,)\s+{REL}\s+(?P<manner>with\s+{S})(?P<close>,)\s+(?P<vp>{S})"),
    ("epistemic", rf"(?P<subject>{W})\s+(?P<emph>{W})(?P<open>,)\s+(?P<cognizer>{W})\s+(?P<cognition>{W})(?P<close>,)\s+(?P<link>{W})\s+(?P<degree>{W})\s+(?P<synthetic>{W})\s+{COORD}\s+(?P<more>more|less)\s+(?P<attribute>{W})\s+(?P<than>than)\s+(?P<standard>{W})\s+(?P<be>{W})\s+(?P<used>used)\s+(?P<strand>to)"),
    ("initial_participle", rf"(?P<subject>{W})\s+(?P<adv>{W})\s+(?P<ing>{W}ing)\s+(?P<ing_obj>{S})(?P<close>,)\s+(?P<vp1>{S})(?P<boundary>,)\s+{COORD}\s+(?P<vp2>{S})\s+(?P<by>by)\s+(?P<gerund>{W}ing)\s+(?P<gerund_obj>{W})\s+(?P<with>with)\s+(?P<head>{S})\s+{REL}"),
    ("medial_participle", rf"(?P<first_subject>{W})\s+(?P<first_v>{W})\s+(?P<first_object>{S})\s+(?P<origin>from\s+{S})(?P<boundary>,)\s+{COORD}\s+(?P<subject>{S})(?P<open>,)\s+(?P<frame>at the same time)\s+(?P<ing>{W}ing)\s+(?P<another>another)(?P<close>,)\s+(?P<give>{W})\s+(?P<recipient>{W})\s+(?P<theme>{S})\s+(?P<loc>across\s+{S})\s+(?P<wh>which)\s+(?P<rs>{W})\s+(?P<limiter>{W})\s+(?P<rv>{W})"),
    ("conditional", rf"(?P<subject>{S})(?P<open>,)\s+(?P<should>should)\s+(?P<condition_subject>{W})\s+(?P<condition_v>{W})\s+(?P<condition_obj>{W})(?P<close>,)\s+(?P<modal>{W})\s+(?P<keep>{W})\s+(?P<affected>{W})(?P<focus_open>,)\s+(?P<focus>at least)(?P<focus_close>,)\s+(?P<from>from)\s+(?P<gerund>{W}ing)\s+(?P<till>till|until)\s+(?P<far>far)\s+(?P<on>on)\s+(?P<time>in\s+{S})"),
))

def plan_subject_resumption(text):
    """Return one bounded plan for an unquoted, comma-marked source clause."""
    if not text.endswith(".") or text.count(",") < 2 or quotation_boundaries(text):
        return None
    for family, pattern in PATTERNS:
        match = pattern.fullmatch(text[:-1])
        if match:
            break
    else:
        return None
    specs, add, mark, _ = _specs()

    def piece(group, cat, kind="phrase", **features):
        a, b = match.span(group)
        add(cat, a, b, kind, **features)

    def lex(group, cat, **features):
        piece(group, cat, "lexical-alternatives", **features)

    def comma(group):
        piece(group, "COMMA", "source-punctuation")

    def verb(group, form, frame):
        lex(group, "V", vform=form, subcat_member=frame)

    def subject(group, **features):
        piece(group, "NP", "subject-phrase", **features)

    def relative():
        lex("wh", "WH-REL-OBL", relative="true")
        subject("rs", pronominal="true")
        if "limiter" in match.groupdict():
            lex("limiter", "ADV")
        if "limiter" in match.groupdict():
            lex("rv", "V", vform="finite", subcat_member="transitive",
                nonbase_surface="true")
        else:
            verb("rv", "finite", "transitive")

    for name in ("open", "close", "boundary", "c1", "c2", "focus_open", "focus_close"):
        if name in match.groupdict():
            comma(name)
    if "and" in match.groupdict():
        lex("and", "COORD", nominal_coordination="true")
    if "subject" in match.groupdict():
        subject("subject")
    if family == "causal":
        lex("poss", "POSS")
        for name in ("n1", "n2", "n3", "cause"):
            if name == "n3":
                # The list can end in either a singular or plural noun;
                # prefer the overt inflection over a singular homograph.
                piece(name, "N", "nominal-lexical")
            else:
                lex(name, "N")
        lex("from", "PREP")
        lex("adj", "ADJ")
        lex("to", "PREP")
        piece("env1", "NP")
        lex("env_and", "COORD", nominal_coordination="true")
        piece("env2", "NP")
        piece("vp", "VP", vform="finite", voice="passive", proof_rule="vp_pp")
    elif family == "concessive":
        subject("initial_subject", pronominal="true")
        lex("copula", "COPULA", vform="finite")
        piece("frame", "PP", proof_rule="pp_prep_np")
        for name in ("a1", "a2", "a3", "attr"):
            lex(name, "ADJ")
        lex("list_and", "COORD", nominal_coordination="true")
        lex("though", "CONJ", concessive="true")
        piece("vp", "VP", vform="finite", proof_rule="vp_cop_neg_adj")
    elif family == "relative":
        relative()
        piece("manner", "PP", proof_rule="pp_prep_np")
        piece("vp", "VP", "resumed-finite-phrase", vform="finite")
    elif family == "epistemic":
        lex("emph", "EMPHATIC-REFLEXIVE", reflexive="true", gender_matches=match["subject"].casefold())
        subject("cognizer", pronominal="true")
        verb("cognition", "finite", "clausal")
        verb("link", "finite", "linking")
        lex("degree", "ADV")
        lex("synthetic", "ADJ", degree_comparative="true")
        lex("more", "DEGREE", comparative="true")
        lex("attribute", "ADJ")
        lex("than", "PREP", comparative="true")
        subject("standard", pronominal="true")
        lex("be", "COPULA", vform="finite")
        lex("used", "ADJ", accustomed_predicate="true")
        lex("strand", "PREP")
    elif family == "initial_participle":
        lex("adv", "ADV")
        verb("ing", "ing", "transitive")
        piece("ing_obj", "NP")
        piece("vp1", "VP", vform="finite", proof_rule="vp_wh_embed")
        piece("vp2", "VP", vform="finite", proof_rule="vp_prep_ditransitive")
        lex("by", "PREP")
        verb("gerund", "ing", "prep_ditransitive")
        piece("gerund_obj", "NP", pronominal="true")
        lex("with", "PREP")
        piece("head", "NP")
        relative()
    elif family == "medial_participle":
        subject("first_subject", pronominal="true")
        verb("first_v", "finite", "transitive")
        piece("first_object", "NP")
        piece("origin", "PP", proof_rule="pp_prep_np")
        piece("frame", "PP", proof_rule="pp_prep_np")
        verb("ing", "ing", "transitive")
        lex("another", "INDEF-PRONOUN", nominal_substitute="true")
        verb("give", "finite", "ditransitive")
        piece("recipient", "NP", pronominal="true")
        piece("theme", "NP")
        piece("loc", "PP", proof_rule="pp_prep_np")
        relative()
    else:
        lex("should", "MODAL", vform="finite")
        subject("condition_subject")
        verb("condition_v", "base", "transitive")
        piece("condition_obj", "NP", pronominal="true")
        lex("modal", "MODAL", vform="finite")
        lex("keep", "V", vform="base", selects_from_gerund="true")
        piece("affected", "NP", pronominal="true")
        lex("focus", "ADV")
        lex("from", "PREP")
        verb("gerund", "ing", "intransitive")
        lex("till", "PREP")
        lex("far", "ADV")
        lex("on", "ADV")
        piece("time", "PP", proof_rule="pp_prep_np")
    mark("SPEECH-STOP", len(text) - 1, len(text))
    root = COORD_ROOT if family in ("concessive", "medial_participle") else ROOT
    return sorted(specs, key=lambda item: item[1]), root
