"""Compose a source-grounded minor utterance with an independently proved tag."""
from __future__ import annotations

import re

from .additional_spoken_acts import postposed_comma_envelope

ROOT = "dialogue_structural_reported_modified_fragment"


def plan_reported_fragment(text, components, lattice):
    """Propose exact spans for a modified adjective or a negated adverb.

    Both are verb-free spoken acts. The source layer identifies the
    reporter, but the existing speech-tag grammar must still prove it.
    """
    found = postposed_comma_envelope(text, components)
    if found is None:
        return None
    stop, opening, closing = found
    words = list(re.finditer(r"[^\s]+", text[1:stop]))
    if len(words) != 2 or words[0].start() != 0 or words[1].end() + 1 != stop:
        return None
    first, second = [(m.start() + 1, m.end() + 1) for m in words]
    negated = any(c.category == "NEG" and c.features.as_dict().get("negation") == "true"
                  for c in lattice.covering(*first))

    checked = {"attested_reading": "true"}
    return [
        *opening,
        ("NEG" if negated else "DEGREE", *first, "scoped-lexical", checked),
        ("ADV" if negated else "ADJ", *second, "lexical-alternatives", checked),
        *closing,
    ]
