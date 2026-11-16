"""Personal body-part instruments on overt deictic pointing events."""

from __future__ import annotations

import re

from .dialogue_clause_plans import _specs

ROOT = "structural_pointing_to_target_with_body_instrument"
_PATTERN = re.compile(
    r"(?i)(?P<subject>i|you|he|she|it|we|they) +(?P<verb>point|points|pointed) +"
    r"(?P<target>to +(?:the|a|an|this|that|his|her|their|my|our|your) +[a-z-]+(?: +[a-z-]+){0,3}?) +"
    r"(?P<instrument>with +(?P<poss>my|your|his|her|its|our|their) +"
    r"(?:(?:right|left|index) +)?(?:finger|thumb|hand|arm))(?P<stop>[.!])"
)
_EXPECTED_POSSESSIVE = {
    "i": "my", "you": "your", "he": "his", "she": "her",
    "it": "its", "we": "our", "they": "their",
}


def plan_pointing_instrument(text, components):
    match = _PATTERN.fullmatch(text)
    if match is None:
        return None
    subject = match["subject"].casefold()
    verb = match["verb"].casefold()
    if (match["poss"].casefold() != _EXPECTED_POSSESSIVE[subject]
            or (verb != "pointed" and (verb == "points") != (subject in ("he", "she", "it")))):
        return None
    # A full source matrix, not an isolated quote, relative or fragment.
    if not any(c["id"] == "s0" and c["function"] == "matrix_clause"
               and (c["start"], c["end"]) == (0, len(text)) for c in components):
        return None
    specs, _, _, parts = _specs()
    parts(match, 0, (
        ("subject", "NP", "subject-phrase", {}),
        ("verb", "V", "lexical-alternatives", {
            "vform": "finite", "lemma_in": "point", "subcat_member": "prepositional",
        }),
        ("target", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("instrument", "PP", "phrase", {"proof_rule": "pp_prep_np"}),
        ("stop", "SPEECH-STOP", "source-punctuation", {}),
    ))
    return specs
