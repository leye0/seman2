"""Locative inversion and time-contrasted existential in literary narration."""
from __future__ import annotations

import re

from .dialogue_clause_plans import _specs
from .scoped_transfer_clauses import _NP, _PRON, _matrix, _v

INVERTED_EXTENT = "structural_locative_inversion_with_subject_participle"
EQUATIVE_DOUBT = "structural_contrastive_perfect_and_existential_equative"
_PERSON = r"[A-Z][a-z]+(?: +[A-Z][a-z]+){0,2}"
_INVERSION = re.compile(
    rf"(?P<subject>{_PRON}) +(?P<wore>wore|carried|displayed) +(?P<object>(?:a|an|the) +{_NP}?) +(?P<and>and) +"
    rf"(?P<location>(?:beneath|behind|under) +the +[a-z-]+), +(?P<participle>extending|hanging|falling) +"
    rf"(?P<path>down +(?P<poss>her|his|their|my|our) +(?:back|shoulders?|neck)), +(?P<be>were|are) +"
    rf"(?P<count>two|three|four) +(?P<items>braids|locks|curls|plaits) +(?P<of>of) +"
    rf"(?P<degree>very|rather) +(?P<first>thick|thin|fine|long), +"
    rf"(?P<manner>decidedly|noticeably|distinctly|unmistakably) +"
    rf"(?P<color>red|black|brown|golden|white|gray|grey) +(?P<hair>hair)(?P<stop>[.!])",
    re.IGNORECASE,
)
_RIVALRY = re.compile(
    rf"(?P<time>Previously|Formerly|Earlier) +(?P<subject>the +{_NP}?) +(?P<had>had) +"
    rf"(?P<been>been) +(?P<degree>rather|quite|very) +(?P<state>[a-z-]+), +"
    rf"(?P<but>but) +(?P<there>there) +(?P<was>was|is) +(?P<no>no) +(?P<longer>longer) +"
    rf"(?P<any>any) +(?P<doubt>doubt|question) +(?P<that>that) +(?P<rival>{_PERSON}) +"
    rf"(?P<be>was|is) +(?P<as>as) +(?P<attribute>determined|eager|anxious|ready) +"
    rf"(?P<to>to) +(?P<be2>be) +(?P<first>first|second|last) +(?P<where>in +{_NP}?) +"
    rf"(?P<as2>as) +(?P<other>{_PERSON}) +(?P<be3>was|is)(?P<stop>[.!])"
)
_POSSESSIVES = {
    "i": {"my"}, "he": {"his"}, "she": {"her"}, "it": {"its"},
    "we": {"our"}, "you": {"your"}, "they": {"their"},
}


def plan_inverted_extent(text, components):
    m = _INVERSION.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    if m["poss"].casefold() not in _POSSESSIVES[m["subject"].casefold()]:
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("wore", "V", "lexical-alternatives", _v("finite", "transitive", nonbase_surface="true")),
        ("object", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("location", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("COMMA", m.end("location"), m.end("location") + 1)
    part(m, 0, (
        ("participle", "V", "lexical-alternatives", _v("ing", "intransitive")),
        ("path", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("COMMA", m.end("path"), m.end("path") + 1)
    part(m, 0, (
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "plural"}),
        ("count", "NUM", "lexical", {}),
        ("items", "N", "lexical", {"number": "plural"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("degree", "DEGREE", "lexical", {}),
        ("first", "ADJ", "lexical", {}),
    ))
    mark("COMMA", m.end("first"), m.end("first") + 1)
    part(m, 0, (
        ("manner", "ADV", "lexical", {}),
        ("color", "ADJ", "lexical", {}),
        ("hair", "N", "lexical", {}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


def plan_existential_equative(text, components):
    m = _RIVALRY.fullmatch(text)
    if m is None or not _matrix(text, components) or m["be"] != m["be3"]:
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("time", "ADV", "lexical", {}),
        ("subject", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("had", "HAVE", "lexical", {"vform": "finite"}),
        ("been", "COPULA", "lexical", {"vform": "ed"}),
        ("degree", "ADV", "lexical", {}),
        ("state", "ADJ", "lexical", {}),
    ))
    mark("COMMA", m.end("state"), m.end("state") + 1)
    part(m, 0, (
        ("but", "COORD", "lexical", {"lemma_in": "but"}),
        ("there", "EXPL", "lexical", {"expletive": "true"}),
        ("was", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("no", "NEG-DEGREE", "lexical", {"temporal_negation": "true"}),
        ("longer", "ADV", "lexical", {}),
        ("any", "DET", "lexical", {}),
        ("doubt", "N", "lexical", {"number": "singular"}),
        ("that", "COMP-THAT", "lexical", {}),
        ("rival", "NP", "proper-phrase", {}),
        ("be", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("as", "EQUATIVE-AS", "lexical", {"degree": "true"}),
        ("attribute", "ADJ", "lexical", {}),
        ("to", "TO", "lexical", {}),
        ("be2", "COPULA", "lexical", {"vform": "base"}),
        ("first", "ADJ", "lexical", {}),
        ("where", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("as2", "CONJ", "lexical", {"degree": "true"}),
        ("other", "NP", "proper-phrase", {}),
        ("be3", "COPULA", "lexical", {"vform": "finite", "number": "singular"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


EMPHATIC_NARRATIVE = "structural_emphasized_three_predicate_narrative"
_EMPHATIC_SERIES = re.compile(
    rf"(?P<mark>_)(?P<subject>(?:The +{_NP}?|{_PERSON})) +(?P<pause>paused|stopped|waited), +"
    rf"(?P<put>put|placed) +(?P<stowed>(?:his|her|their) +[a-z-]+) +"
    rf"(?P<inside>into +(?:his|her|their) +[a-z-]+), +(?P<and>and) +"
    rf"(?P<silently>[a-z]+ly) +(?P<place>placed|set|laid) +"
    rf"(?P<count>two|three|four) +(?P<attribute>[a-z-]+) +(?P<theme>[a-z-]+s), +"
    rf"(?P<not>not) +(?P<unlike>unlike) +(?P<degree>very|rather) +"
    rf"(?P<appearance1>[a-z-]+) +(?P<appearance2>[a-z-]+) +(?P<kind>[a-z-]+s), +"
    rf"(?P<where>(?:on|upon) +{_NP})(?P<stop>[.!])(?P<close>_)?",
    re.IGNORECASE,
)


def plan_emphatic_narrative(text, components):
    m = _EMPHATIC_SERIES.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    # An incomplete visible pair is admissible only when the original
    # paragraph attested its closing mark beyond the sentence.
    if not m["close"] and not any(c.get("function") == "typographic_emphasis"
                 and (c["start"], c["end"]) == (0, len(text))
                 and c.get("relation") == "begin_and_continue"
                 for c in components):
        return None
    if m["stowed"].split()[0].casefold() != m["inside"].split()[1].casefold():
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("mark", "EMPHASIS", "source-punctuation", {}),
        ("subject", "NP", "phrase", {}),
        ("pause", "V", "lexical-alternatives", _v("finite", "intransitive")),
    ))
    mark("COMMA", m.end("pause"), m.end("pause") + 1)
    part(m, 0, (
        ("put", "V", "lexical-alternatives", _v("finite", "prep_ditransitive")),
        ("stowed", "NP", "phrase", {"proof_rule": "np_poss"}),
        ("inside", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("COMMA", m.end("inside"), m.end("inside") + 1)
    part(m, 0, (
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("silently", "ADV", "lexical", {}),
        ("place", "V", "lexical-alternatives", _v("finite", "prep_ditransitive")),
        ("count", "NUM", "lexical", {}),
        ("attribute", "ADJ", "lexical", {}),
        ("theme", "N", "lexical", {"number": "plural"}),
    ))
    mark("COMMA", m.end("theme"), m.end("theme") + 1)
    part(m, 0, (
        ("not", "NEG", "lexical", {"negation": "true"}),
        ("unlike", "ADJ", "lexical", {}),
        ("degree", "DEGREE", "lexical", {}),
        ("appearance1", "ADJ", "lexical", {}),
        ("appearance2", "ADJ", "lexical", {}),
        ("kind", "N", "lexical", {"number": "plural"}),
    ))
    mark("COMMA", m.end("kind"), m.end("kind") + 1)
    part(m, 0, (
        ("where", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    if m["close"]:
        mark("EMPHASIS", *m.span("close"))
    return specs


EMPHASIS_CLOSURE = "structural_finite_clause_with_paragraph_emphasis_closure"


def plan_emphasis_closure(text, components):
    if not _matrix(text, components) or not text.endswith(("._", "!_")):
        return None
    emphasis = [c for c in components if c.get("function") == "typographic_emphasis"
                and (c["start"], c["end"]) == (0, len(text))]
    if len(emphasis) != 1 or emphasis[0].get("relation") not in (
        "closed_emphasis", "continuation_and_close",
    ):
        return None
    start = 1 if text.startswith("_") else 0
    if bool(start) != (emphasis[0]["relation"] == "closed_emphasis"):
        return None
    # Use an independently complete finite clause, never a phrase or
    # generic minor utterance. Interior emphasis needs its own proof.
    if not 4 <= len(text[start:-2].split()) <= 18 or "_" in text[start:-2]:
        return None
    specs, add, mark, _ = _specs()
    if start:
        mark("EMPHASIS", 0, 1)
    add("CLAUSE", start, len(text) - 2, "phrase", emphasis_finite_proof="true")
    mark("SPEECH-STOP", len(text) - 2, len(text) - 1)
    mark("EMPHASIS", len(text) - 1, len(text))
    return specs


EXPLAINED_QUOTED_THEME = "structural_coordination_with_passive_request_and_quoted_theme_relative"
_WITH_QUOTED_THEME = re.compile(
    rf"(?P<subject>(?:The|the) +{_NP}?) +(?P<want>wanted) +(?P<demo>that|this) +"
    rf"(?P<explain>explained|described|repeated) +(?P<recipient>to +(?:him|her|them|me|us|you)), +"
    rf"(?P<and>and) +(?P<speaker>the +{_NP}?) +(?P<report>volunteered|offered|gave) +"
    rf"(?P<account>(?:a|an|the) +[a-z-]+ +(?:account|description|explanation)) +(?P<of>of) +(?P<the>the) +"
    rf"(?P<open>[“\"])(?P<adjective>[a-z-]+) +(?P<first>[a-z-]+) +(?P<join>and) +(?P<second>[a-z-]+)(?P<close>[”\"]) +"
    rf"(?P<witness>{_PRON}) +(?P<aux>had) +(?P<seen>witnessed|seen|observed) +"
    r"(?:(?P<time>the previous day|the previous week|that morning|that day)|"
    r"(?P<day1>that) +(?P<day2>day) +(?P<week>week))(?P<stop>[.!])",
    re.IGNORECASE,
)


def plan_explained_quoted_theme(text, components):
    m = _WITH_QUOTED_THEME.fullmatch(text)
    if m is None or (m["open"], m["close"]) not in (("“", "”"), ('"', '"')):
        return None
    quote_span = (m.start("open"), m.end("close"))
    if not any(c.get("id") == "q0" and c.get("function") == "direct_speech"
               and (c["start"], c["end"]) == quote_span for c in components):
        return None
    if not any(c.get("id") == "s0" and c.get("function") == "matrix_clause"
               and (c["start"], c["end"]) == (0, len(text)) for c in components):
        return None
    specs, _, mark, part = _specs()
    part(m, 0, (
        ("subject", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("want", "V", "lexical-alternatives", _v("finite", "object_control", lemma_in="want")),
        ("demo", "PRONOUN", "lexical", {"definiteness": "demonstrative"}),
        ("explain", "V", "lexical-alternatives", _v("ed", "transitive")),
        ("recipient", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
    ))
    mark("COMMA", m.end("recipient"), m.end("recipient") + 1)
    part(m, 0, (
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("speaker", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("report", "V", "lexical-alternatives", _v("finite", "transitive")),
        ("account", "NP", "phrase", {"proof_rule": "np_det_n"}),
        ("of", "PREP", "lexical", {"nominal_complement": "of"}),
        ("the", "DET", "lexical", {"definiteness": "definite"}),
        ("open", "OPEN-QUOTE", "source-punctuation", {}),
        ("adjective", "ADJ", "lexical", {}),
        ("first", "N", "lexical", {"number": "singular"}),
        ("join", "COORD", "lexical", {"lemma_in": "and"}),
        ("second", "N", "lexical", {"number": "singular"}),
        ("close", "CLOSE-QUOTE", "source-punctuation", {}),
        ("witness", "NP", "subject-phrase", {}),
        ("aux", "HAVE", "lexical", {"vform": "finite"}),
        ("seen", "V", "lexical-alternatives", _v("ed", "transitive")),
    ))
    if m["time"]:
        part(m, 0, (("time", "NP", "phrase", {"proof_rule": "np_det_n"}),))
    else:
        part(m, 0, (
            ("day1", "DET", "lexical", {"definiteness": "demonstrative"}),
            ("day2", "N", "lexical", {}),
            ("week", "N", "lexical", {}),
        ))
    mark("SPEECH-STOP", *m.span("stop"))
    return specs


PERCEIVED_ATTEMPT = "structural_perceived_coordinated_attempt_with_result_goal"
_OBSERVED = re.compile(
    rf"(?P<observer>(?i:{_PRON}|the +[a-z][a-z-]*)) +(?P<perception>found|saw|observed|discovered) +"
    rf"(?P<left>{_PERSON}) +(?P<and>and) +(?P<right>{_PERSON}) +"
    r"(?P<manner>[a-z]+ly) +(?P<attempt>trying|attempting|striving) +(?P<to>to) +"
    rf"(?P<action>restore|bring|pull|return|take) +(?P<patient>{_PERSON}|him|her|them) +"
    r"(?P<goal>to +(?:(?:the|a) +)?(?:consciousness|safety|health|shore|surface|life|room))(?P<stop>[.!])"
)


def plan_perceived_attempt(text, components):
    """The coordinated participants control the participle and its infinitive."""
    m = _OBSERVED.fullmatch(text)
    if m is None or not _matrix(text, components) or m["left"] == m["right"]:
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("observer", "NP", "subject-phrase", {}),
        ("perception", "V", "lexical-alternatives",
         _v("finite", "clausal", lemma_in="find|see|observe|discover", nonbase_surface="true")),
        ("left", "NP", "proper-phrase", {}),
        ("and", "COORD", "lexical", {"nominal_coordination": "true", "lemma_in": "and"}),
        ("right", "NP", "proper-phrase", {}),
        ("manner", "ADV", "lexical", {}),
        ("attempt", "V", "lexical-alternatives", _v("ing", "subject_control")),
        ("to", "TO", "lexical", {}),
        ("action", "V", "lexical-alternatives", _v("base", "prep_ditransitive")),
        ("patient", "NP", "proper-phrase" if m["patient"][0].isupper() else "phrase", {}),
        ("goal", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs


GENITIVE_ORIGIN = "structural_motion_with_genitive_origin_and_coordinated_accountability"
_ORIGIN = re.compile(
    rf"(?P<subject>(?i:{_PRON})) +(?P<move>came|went|returned|walked) +(?P<home>home) +"
    rf"(?P<from>from) +(?P<owner>(?:Mr\.|Mrs\.|Dr\.|Miss) +{_PERSON}|{_PERSON})"
    rf"(?P<genitive>[’']s) +(?P<and>and) +(?P<call>called) +(?P<questioned>{_PERSON}|him|her|them)"
    r" +(?P<account>to +account)(?P<stop>[.!])"
)


def plan_genitive_origin(text, components):
    """Preserve the independent genitive without inventing a possessed noun."""
    m = _ORIGIN.fullmatch(text)
    if m is None or not _matrix(text, components):
        return None
    specs, _, _, part = _specs()
    part(m, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("move", "V", "lexical-alternatives",
         _v("finite", "intransitive", lemma_in="come|go|return|walk", nonbase_surface="true")),
        ("home", "ADV", "lexical", {"lemma_in": "home"}),
        ("from", "PREP", "lexical", {"lemma_in": "from"}),
        ("owner", "NP", "proper-phrase", {}),
        ("genitive", "POSS", "lexical", {"genitive_clitic": "true"}),
        ("and", "COORD", "lexical", {"lemma_in": "and"}),
        ("call", "V", "lexical-alternatives", _v("finite", "prep_ditransitive", lemma_in="call")),
        ("questioned", "NP", "proper-phrase" if m["questioned"][0].isupper() else "phrase", {}),
        ("account", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs
