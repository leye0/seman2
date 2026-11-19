"""Compose a source-grounded minor utterance with an independently proved tag."""
from __future__ import annotations

import re

from .additional_spoken_acts import _single_spoken_span

ROOT = "dialogue_structural_reported_modified_fragment"


def plan_reported_fragment(text, components, lattice):
    """Propose exact spans for a modified adjective or a negated adverb.

    Both are verb-free spoken acts. The source layer identifies the
    reporter, but the existing speech-tag grammar must still prove it.
    """
    found = _single_spoken_span(text, components, reported=True)
    if found is None:
        return None
    stop, reporter = found
    if text[stop] != "," or not text[stop + 2:reporter["start"]].isspace():
        return None
    words = list(re.finditer(r"[^\s]+", text[1:stop]))
    if len(words) != 2 or words[0].start() != 0 or words[1].end() + 1 != stop:
        return None
    first, second = [(m.start() + 1, m.end() + 1) for m in words]
    negated = any(c.category == "NEG" and c.features.as_dict().get("negation") == "true"
                  for c in lattice.covering(*first))

    def literal(category, p):
        return category, p, p + 1, "source-punctuation", {}

    checked = {"attested_reading": "true"}
    return [
        literal("OPEN-QUOTE", 0),
        ("NEG" if negated else "DEGREE", *first, "scoped-lexical", checked),
        ("ADV" if negated else "ADJ", *second, "lexical-alternatives", checked),
        literal("COMMA", stop), literal("CLOSE-QUOTE", stop + 1),
        ("SPEECH-TAG", reporter["start"], reporter["end"], "phrase",
         {"simple_reporting_tag_proof": "true"}),
        literal("SPEECH-STOP", reporter["end"]),
    ]
