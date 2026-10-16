"""Non-mutating adapter for Seman2 LexicalCandidate; no runtime changes.

Seman2 already performs WordNet lemmatization and surface-morphology filtering.
A candidate may carry several sense IDs while having only one syntactic path.
Ask the prefix index about those sense IDs, without cloning the candidate.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from .compiler import Frame, PrefixIndex

_WN_VERB_ID = re.compile(r"^wn-(\d+)-v-(?:finite|base|ed|ing)$")


@dataclass(frozen=True, slots=True)
class CandidateHint:
    status: str  # ATTESTED, PREFIX, UNKNOWN: no grammatical rejection
    confidence: str  # sense_verified, lemma_only, none
    next_events: tuple[str, ...]
    matching_frames: tuple[Frame, ...]
    complete_frames: tuple[Frame, ...]


def predict_candidate(index: PrefixIndex, candidate: Any,
                      observed: Iterable[str] = ()) -> CandidateHint:
    """Query an already morphologically analyzed candidate (no side effects).

    Restricts to matched WordNet synsets when present. Otherwise returns
    strictly weak lemma-only hints, not a promise of sense compatibility.
    """
    if getattr(candidate, "category", None) != "V":
        return CandidateHint("UNKNOWN", "none", (), (), ())
    lemma = getattr(candidate, "lemma", "")
    seen = tuple(observed)
    offsets = set()
    for sense_id in getattr(candidate, "sense_ids", ()):
        found = _WN_VERB_ID.fullmatch(sense_id)
        if found:
            offsets.add(int(found.group(1)))
    if not offsets:
        p = index.predict(lemma, seen)
        return CandidateHint(p.status, "lemma_only" if p.matching_frames else "none",
                             p.next_events, p.matching_frames, p.complete_frames)
    matches = {}
    complete = {}
    next_events = set()
    for offset in sorted(offsets):
        p = index.predict(lemma, seen, synset_offset=offset)
        for frame in p.matching_frames:
            matches[(frame.class_id, frame.frame_id, frame.wordnet_keys)] = frame
        for frame in p.complete_frames:
            complete[(frame.class_id, frame.frame_id, frame.wordnet_keys)] = frame
        next_events.update(p.next_events)
    return CandidateHint("ATTESTED" if complete else "PREFIX" if matches else "UNKNOWN",
                         "sense_verified" if matches else "none",
                         tuple(sorted(next_events)), tuple(matches.values()), tuple(complete.values()))
