"""Exact, typed plan for a negative possession domain with an exception."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_negative_possession_with_locative_exception"
_PATTERN = re.compile(
    r"(?i)(?P<subject>i|you|he|she|it|we|they) +(?P<have>have|has|had) +"
    r"(?P<negative>nothing) +(?P<location>on (?:me|him|her|us|them|you|it)) +"
    r"(?P<exceptive>but) +(?P<exception>(?:a|an|the|my|your|his|her|our|their) +[^;!?]+)"
    r"(?P<stop>[.!])"
)


def plan_negative_possession_with_exception(text, components):
    host = next((c for c in components if c["id"] == "s0"), None)
    if (host is None or host["function"] != "matrix_clause"
            or (host["start"], host["end"]) != (0, len(text))):
        return None
    match = _PATTERN.fullmatch(text)
    if match is None or len(match["exception"].split()) > 14:
        return None
    subject, have = match["subject"].casefold(), match["have"].casefold()
    if have != "had" and (have == "has") != (subject in ("he", "she", "it")):
        return None
    specs, _, _, parts = _specs()
    parts(match, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("have", "V", "lexical-alternatives", {
            "vform": "finite", "lemma_in": "have", "subcat_member": "transitive",
        }),
        ("negative", "NP", "phrase", {"proof_rule": "np_indef_pron"}),
        ("location", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("exceptive", "EXCEPTIVE", "lexical", {"lemma_in": "but"}),
        ("exception", "NP", "phrase", {"demonstrated_full_nominal_proof": "true"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs
