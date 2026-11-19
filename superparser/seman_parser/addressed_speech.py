"""Source spans for a turn with an overt right-edge vocative."""

from __future__ import annotations

import re

from .additional_spoken_acts import _single_spoken_span, postposed_comma_envelope
from .dialogue_clause_plans import _specs
from .scoped_novel_ladder import negative_proform_specs

ROOT = "dialogue_structural_reported_addressed_turn"
UNATTRIBUTED = "dialogue_structural_unattributed_addressed_turn"

# A possessive plus term of affection can follow a name inside the same
# address. An arbitrary possessive NP ("Clara my book") cannot do so.
_ENDEARMENT = re.compile(r"(?i)\bmy\s+(?:dear|darling|dearest)\Z")
_NAME = re.compile(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*")
_FORMAL_ADDRESS = frozenset({"sir", "madam"})


def _addressed_payload(text, stop, lattice, *, proform_only=False):
    comma = text.find(",", 1, stop)
    if comma <= 1 or text.find(",", comma + 1, stop) >= 0:
        return None
    head = text[1:comma]
    address = text[comma + 1:stop]
    if (head != head.strip() or not address[:1].isspace()
            or not address.strip() or address[-1].isspace()
            or any(mark in head + address for mark in ".;:!?")
            or len(head.split()) > 10):
        return None
    a = stop - len(address.lstrip())
    term = _ENDEARMENT.search(text, a, stop)
    name_end = len(text[:term.start()].rstrip()) if term else stop
    name_words = text[a:name_end].split()
    formal = term is None and text[a:stop].casefold() in _FORMAL_ADDRESS
    if not formal and (not 1 <= len(name_words) <= 3 or not all(
        _NAME.fullmatch(word) and word[0].isupper() for word in name_words
    )):
        return None

    specs, add, punct, _ = _specs()
    proform = negative_proform_specs(text, 1, comma)
    if proform:
        specs.extend(proform)
    elif proform_only:
        return None
    elif any(c.category == "ADV" and c.features.as_dict().get("discourse_transition") == "true"
             for c in lattice.covering(1, comma)):
        add("ADV", 1, comma, discourse_transition="true")
    else:
        add("VP-NP", 1, comma, "phrase", imperative_predicate_proof="true")
    punct("COMMA", comma, comma + 1)
    if formal:
        add("N", a, stop, "lexical-alternatives",
            attested_reading="true", lemma_in="|".join(sorted(_FORMAL_ADDRESS)))
    else:
        add("NP", a, name_end, "proper-phrase")
    if term is not None:
        add("NP", term.start(), stop, "phrase", proof_rule="np_poss")
    return specs


def plan_reported_addressed_turn(text, components, lattice):
    """Keep the turn head, vocative, and speaker proof independent."""
    found = postposed_comma_envelope(text, components)
    if found is None or text[-1] != ".":
        return None
    stop, opening, closing = found
    payload = _addressed_payload(text, stop, lattice)
    return [*opening, *payload, *closing] if payload else None


def plan_unattributed_addressed_turn(text, components, lattice):
    """A propositional reply can address someone without an overt reporter."""
    found = _single_spoken_span(text, components)
    if found is None or text[found[0]] not in ".!":
        return None
    stop, _ = found
    payload = _addressed_payload(text, stop, lattice, proform_only=True)
    if payload is None:
        return None
    specs, _, mark, _ = _specs()
    mark("OPEN-QUOTE", 0, 1)
    specs.extend(payload)
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs
