"""Source spans for declarative perfect inversion licensed by never or nor."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_negative_perfect_inversion"
WORD = r"[A-Za-z][A-Za-z'’\-]*"
PRON = r"I|you|he|she|it|we|they"
NP = r"""[^,;.!?()"“”]+?"""

NEVER = re.compile(
    rf"(?P<first>never)(?P<c1>,)\s+(?:(?P<second>never)(?P<c2>,)\s+)?"
    rf"(?P<have>had)\s+(?P<subject>{PRON})\s+(?P<verb>{WORD})\s+(?P<object>{NP})\s+"
    rf"(?P<so>so)\s+(?P<adv1>{WORD})\s+(?P<coord>and)\s+(?P<adv2>{WORD})(?P<c3>,)\s+"
    rf"(?P<as>as)\s+(?P<standard_subject>{PRON})\s+(?P<standard_verb>{WORD})\s+"
    rf"(?P<standard_object>me|you|him|her|it|us|them)\s+"
    rf"(?P<when>(?:that|this)\s+(?:night|day|evening|morning|afternoon|week|year))(?P<stop>\.)",
    re.I,
)
NOR = re.compile(
    rf"(?P<focus>at\s+least)(?P<c1>,)\s+(?P<coord>and)\s+(?P<finally>at\s+last)(?P<c2>,)\s+"
    rf"(?P<left_subject>{PRON})\s+(?P<be>am|is|are|was|were)\s+(?P<off>off)\s+"
    rf"(?P<place>{NP})(?P<c3>,)\s+(?P<nor>nor)\s+"
    rf"(?P<have>had)\s+(?P<subject>{PRON})\s+(?P<verb>{WORD})\s+"
    rf"(?P<origin>thence|hence|therefrom)\s+(?P<state>{WORD})(?P<stop>\.)", re.I,
)


def _match(text):
    return NEVER.fullmatch(text) or NOR.fullmatch(text)


def negative_perfect_span(text):
    match = _match(text)
    if match is None:
        return None
    start = match.start("nor") if match.re is NOR else match.start("first")
    return start, match.start("stop")


def plan_negative_perfect(text, components):
    match = _match(text)
    if match is None:
        return None
    span = negative_perfect_span(text)
    if not any(c["function"] == "negative_inversion_candidate" and c["governor"] == "s0"
               and (c["start"], c["end"]) == span for c in components):
        return None
    specs, add, punct, _ = _specs()

    def piece(group, cat, kind="lexical-alternatives", **features):
        add(cat, *match.span(group), kind, **features)

    def subject(group):
        piece(group, "NP", "subject-phrase", pronominal="true")

    def verb(group, valence, form, **features):
        piece(group, "V", vform=form, subcat_member=valence, **features)

    for comma in ("c1", "c2", "c3"):
        if match[comma]:
            punct("COMMA", *match.span(comma))
    punct("SPEECH-STOP", *match.span("stop"))
    piece("coord", "COORD", nominal_coordination="true", lemma_in="and")
    piece("have", "HAVE", vform="finite")
    subject("subject")
    if match.re is NOR:
        for group, lemma in (("focus", "at least"), ("finally", "at last")):
            # The source matcher admits whitespace; the multiword lattice
            # itself must contain the complete conventional expression.
            piece(group, "ADV", lemma_in=lemma)
        subject("left_subject")
        piece("be", "COPULA", vform="finite", lemma_in="be")
        # The closed lexicon exposes off as a particle. Select its local
        # prepositional reading only with the overt governed nominal.
        piece("off", "PREP", "negative-off-preposition")
        piece("place", "NP", "phrase", simple_nominal_proof="true")
        piece("nor", "COORD", negation="true", inversion="true")
        verb("verb", "intransitive", "ed", inversion_frame="motion")
        piece("origin", "ADV")
        piece("state", "ADJ", inversion_frame="motion_depictive")
    else:
        for group in ("first", "second"):
            if match[group]:
                piece(group, "DEGREE", negation="true", inversion="true")
        verb("verb", "transitive", "ed")
        piece("object", "NP", "phrase", simple_nominal_proof="true")
        piece("so", "DEGREE", scalar_degree="true")
        piece("adv1", "ADV")
        piece("adv2", "ADV")
        piece("as", "EQUATIVE-AS", degree="true")
        subject("standard_subject")
        verb("standard_verb", "transitive", "finite", nonbase_surface="true")
        if match["standard_object"].casefold() in ("you", "it"):
            piece("standard_object", "PRONOUN", lemma_in=match["standard_object"].casefold())
        else:
            piece("standard_object", "PRONOUN", case="accusative")
        piece("when", "NP", "phrase", proof_rule="np_det_n", definiteness="demonstrative")
    return sorted(specs, key=lambda row: row[1])
