"""Source plans for A; B, and C with three independently licensed predicates."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_semicolon_finite_triplet"
WORD = r"[A-Za-z][A-Za-z'’\-]*"
NP = r"""[^,;.!?()"“”]+?"""
PRON = r"I|you|he|she|it|we|they"
OBJ = r"me|you|him|her|it|us|them"
NAME = r"[A-Z][A-Za-z'’\-]*"
SHELL = re.compile(
    rf"(?P<left>[^;]+?)(?P<semicolon>;)\s+(?P<middle>{NP})(?P<comma>,)\s+"
    rf"(?P<and>and)\s+(?P<right>{NP})(?P<stop>\.)", re.I,
)
SOUND_LEFT = re.compile(
    rf"(?P<subject>{PRON})\s+(?P<verb>{WORD})\s+(?P<pp>on\s+{NP})\s+"
    rf"(?P<duration>{WORD})\s+(?P<adv_and>and)\s+(?P<manner>{WORD})", re.I,
)
ECHO_MIDDLE = re.compile(rf"(?P<subject>{NP})\s+(?P<verb>{WORD})\s+(?P<object>{OBJ})", re.I)
PERCEPTION_RIGHT = re.compile(
    rf"(?P<subject>{PRON})\s+(?P<verb>{WORD})\s+(?P<as>as)\s+(?P<if>if)\s+"
    rf"(?:(?P<all>all)\s+)?(?P<inner>{NP})\s+(?P<inner_v>{WORD})\s+(?P<object>{OBJ})\s+"
    rf"(?P<with>with)\s+(?P<manner1>{NP})\s+(?P<np_and>and)\s+(?P<manner2>{NP})", re.I,
)
PREVENTION_LEFT = re.compile(
    rf"(?P<title>Mr|Mrs|Ms|Dr)(?P<dot>\.)\s+(?P<name>{NAME})\s+"
    rf"(?P<be>was|is)\s+(?P<verb>{WORD})\s+(?P<gerund>{WORD})\s+"
    rf"(?P<by>by)\s+(?P<entrance>the\s+{WORD})\s+(?P<of>of)\s+"
    rf"(?P<carrier>the\s+{WORD})\s+(?P<with>with)\s+(?P<message>a\s+{WORD})\s+"
    rf"(?P<for>for)\s+(?P<recipient_title>Miss)\s+(?P<recipient>{NAME})",
)
SOURCE_MIDDLE = re.compile(
    rf"(?P<subject>{PRON})\s+(?P<verb>{WORD})\s+(?P<from>from)\s+(?P<origin>{NP})", re.I,
)
WAIT_RIGHT = re.compile(
    rf"(?P<subject>the\s+{WORD})\s+(?P<verb>{WORD})\s+(?P<for>for)\s+(?P<object>{NP})", re.I,
)


def _match(text):
    shell = SHELL.fullmatch(text)
    if shell is None:
        return None
    for patterns in (
        (SOUND_LEFT, ECHO_MIDDLE, PERCEPTION_RIGHT),
        (PREVENTION_LEFT, SOURCE_MIDDLE, WAIT_RIGHT),
    ):
        matches = tuple(pattern.fullmatch(text, *shell.span(group))
                        for pattern, group in zip(patterns, ("left", "middle", "right")))
        if all(matches):
            return (shell, *matches)
    return None


def semicolon_triplet_spans(text):
    """The comma after B is only a proposed boundary within the post-semicolon unit."""
    match = _match(text)
    if match is None:
        return None
    shell = match[0]
    return shell.span("middle"), shell.span("right")


def plan_semicolon_triplet(text, components):
    match = _match(text)
    if match is None:
        return None
    shell, left, middle, right = match
    nodes = {c["id"]: c for c in components}
    if any(c["function"] in ("direct_speech", "embedded_quotation") for c in components):
        return None
    for key, parent, category, span in (
        ("s0", "u0", "matrix_clause", shell.span("left")),
        ("s1", "s0", "independent_clause", (middle.start(), len(text))),
        ("st0", "s1", "finite_conjunct_candidate", middle.span()),
        ("st1", "st0", "finite_conjunct_candidate", right.span()),
    ):
        c = nodes.get(key, {})
        if (c.get("start"), c.get("end"), c.get("governor"), c.get("function")) != (
            *span, parent, category,
        ):
            return None

    specs, add, punct, _ = _specs()

    def lex(m, group, cat, **features):
        add(cat, *m.span(group), "lexical-alternatives", **features)

    def phrase(m, group, cat, rule=None):
        add(cat, *m.span(group), "phrase", **({"proof_rule": rule} if rule else {}))

    def subject(m, group="subject", **features):
        add("NP", *m.span(group), "subject-phrase", **features)

    def verb(m, group, frame, *, form="finite", scope=None):
        features = {"vform": form, "subcat_member": frame}
        if form == "finite":
            features["nonbase_surface"] = "true"
        if scope:
            features["triplet_frame"] = scope
        lex(m, group, "V", **features)

    def coord(m, group):
        lex(m, group, "COORD", nominal_coordination="true", lemma_in="and")

    def object_pronoun(m):
        # The lexicon leaves invariant it/you unmarked for case.
        surface = m["object"].casefold()
        lex(m, "object", "PRONOUN", **(
            {"lemma_in": surface} if surface in ("it", "you") else {"case": "accusative"}
        ))

    def prep(m, group):
        lex(m, group, "PREP", lemma_in=group)

    punct("SEMICOLON", *shell.span("semicolon"))
    punct("COMMA", *shell.span("comma"))
    coord(shell, "and")
    punct("SPEECH-STOP", *shell.span("stop"))
    if left.re is SOUND_LEFT:
        subject(left, pronominal="true")
        verb(left, "verb", "prepositional", scope="sound")
        phrase(left, "pp", "PP", "pp_prep_np")
        lex(left, "duration", "ADV", triplet_frame="duration")
        coord(left, "adv_and")
        lex(left, "manner", "ADV")
        subject(middle, proof_rule="np_det_n")
        verb(middle, "verb", "transitive", scope="echo")
        object_pronoun(middle)
        subject(right, pronominal="true")
        verb(right, "verb", "clausal", scope="perception")
        lex(right, "as", "ADV", lemma_in="as")
        lex(right, "if", "CONJ", complementizer="conditional")
        # Export the lexical subject of an overt all-quantified nominal.
        # An isolated proof of "all hell" ranks an analysis headed by all.
        if right["all"]:
            lex(right, "all", "DET", definiteness="universal")
        subject(right, "inner")
        verb(right, "inner_v", "transitive")
        object_pronoun(right)
        prep(right, "with")
        phrase(right, "manner1", "NP")
        coord(right, "np_and")
        phrase(right, "manner2", "NP")
    else:
        lex(left, "title", "TITLE", honorific="true")
        punct("ABBREVIATION-STOP", *left.span("dot"))
        lex(left, "name", "PROPER-NOUN")
        lex(left, "be", "AUX-BE", vform="finite", lemma_in="be")
        verb(left, "verb", "transitive", form="ed", scope="preventive")
        verb(left, "gerund", "intransitive", form="ing")
        lex(left, "by", "PREP-BY", lemma_in="by")
        for group in ("entrance", "carrier", "message"):
            phrase(left, group, "NP", "np_det_n")
        for group in ("of", "with", "for"):
            prep(left, group)
        add("TITLE", *left.span("recipient_title"), "temporal-source-form", honorific="true")
        lex(left, "recipient", "PROPER-NOUN")
        subject(middle, pronominal="true")
        verb(middle, "verb", "prepositional", scope="source_motion")
        prep(middle, "from")
        phrase(middle, "origin", "NP")
        subject(right, proof_rule="np_det_n")
        verb(right, "verb", "prepositional", scope="waiting")
        prep(right, "for")
        phrase(right, "object", "NP")
    return sorted(specs, key=lambda row: row[1])
