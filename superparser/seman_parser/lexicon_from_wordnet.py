"""Import WordNet lexical entries into the seman_parser lexicon format.

Words come from whatever corpus you feed in (token stream, frequency list,
a text file). Their POS, morphology and sense types come from WordNet.
Nothing is hand-listed here except the closed-class function words that
WordNet does not cover as a parser lexicon.

This module is corpus-agnostic: run it on any text, not one specific book.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .wordnet import (
    POS_ADJ,
    POS_ADV,
    POS_NOUN,
    POS_VERB,
    WordNet,
    WordNetSynset,
)

# WordNet lexicographer file -> semantic type in our DAG.
# This is a resource mapping, not a list of words.
LEXNAME_TO_TYPE: Mapping[str, str] = {
    "noun.Tops": "REFERENTIAL",
    "noun.act": "EVENT",
    "noun.animal": "PHYSICAL-OBJECT",
    "noun.artifact": "ARTIFACT",
    "noun.attribute": "ATTRIBUTE",
    "noun.body": "BODY-PART",
    "noun.cognition": "INFORMATION",
    "noun.communication": "INFORMATION",
    "noun.event": "EVENT",
    "noun.feeling": "STATE",
    "noun.food": "SUBSTANCE",
    "noun.group": "ORGANIZATION",
    "noun.location": "LOCATION",
    "noun.motive": "STATE",
    "noun.object": "PHYSICAL-OBJECT",
    "noun.person": "PERSON",
    "noun.phenomenon": "PHYSICAL-OBJECT",
    "noun.plant": "PHYSICAL-OBJECT",
    "noun.possession": "REFERENTIAL",
    "noun.process": "EVENT",
    "noun.quantity": "NUMBER",
    "noun.relation": "REFERENTIAL",
    "noun.shape": "PHYSICAL-OBJECT",
    "noun.state": "STATE",
    "noun.substance": "SUBSTANCE",
    "noun.time": "TIME",
    "verb.body": "EVENT",
    "verb.change": "EVENT",
    "verb.cognition": "EVENT",
    "verb.communication": "EVENT",
    "verb.competition": "EVENT",
    "verb.consumption": "EVENT",
    "verb.contact": "EVENT",
    "verb.creation": "EVENT",
    "verb.emotion": "EVENT",
    "verb.motion": "EVENT",
    "verb.perception": "EVENT",
    "verb.possession": "EVENT",
    "verb.social": "EVENT",
    "verb.stative": "STATE",
    "verb.weather": "EVENT",
    "adj.all": "ATTRIBUTE",
    "adj.pert": "ATTRIBUTE",
    "adj.ppl": "ATTRIBUTE",
    "adv.all": "MANNER",
}

# WordNet verb frame numbers -> syntactic slot -> semantic role.
# Frame numbers are from frames.vrb; the mapping is structural, not lexical.
VERB_FRAME_SLOTS: Mapping[int, tuple[tuple[str, str], ...]] = {
    1: (("subject", "AGENT"),),
    2: (("subject", "AGENT"),),
    3: (("subject", "AGENT"),),
    4: (("subject", "AGENT"), ("prep_object", "THEME")),
    5: (("subject", "AGENT"), ("object", "THEME"), ("predicate", "ATTRIBUTE")),
    6: (("subject", "AGENT"), ("predicate", "ATTRIBUTE")),
    7: (("subject", "EXPERIENCER"), ("predicate", "ATTRIBUTE")),
    8: (("subject", "EXPERIENCER"), ("object", "THEME")),
    9: (("subject", "AGENT"), ("object", "THEME")),
    10: (("subject", "EXPERIENCER"),),
    11: (("subject", "AGENT"), ("object", "THEME")),
    12: (("subject", "AGENT"), ("prep_object", "AFFECTED")),
    13: (("subject", "AGENT"), ("prep_object", "AFFECTED")),
    # frames.vrb: 14 = "Somebody ----s somebody something"; 15 instead
    # contains a prepositional recipient ("something to somebody").
    14: (("subject", "AGENT"), ("iobj", "RECIPIENT"), ("object", "THEME")),
    15: (("subject", "AGENT"), ("object", "THEME"), ("prep_object", "RECIPIENT")),
    16: (("subject", "AGENT"), ("object", "THEME"), ("prep_object", "SOURCE")),
    17: (("subject", "AGENT"), ("object", "THEME"), ("prep_object", "INSTRUMENT")),
    18: (("subject", "AGENT"), ("object", "THEME"), ("prep_object", "COMPLEMENT")),
    19: (("subject", "AGENT"), ("object", "THEME"), ("prep_object", "LOCATION")),
    20: (("subject", "AGENT"), ("object", "THEME"), ("prep_object", "COMPLEMENT")),
    21: (("subject", "AGENT"), ("object", "THEME"), ("prep_object", "COMPLEMENT")),
    22: (("subject", "AGENT"), ("prep_object", "COMPLEMENT")),
    23: (("subject", "AGENT"), ("object", "THEME")),
    24: (("subject", "AGENT"), ("object", "THEME"), ("to_inf", "COMPLEMENT")),
    25: (("subject", "EXPERIENCER"), ("object", "THEME"), ("bare_inf", "COMPLEMENT")),
    26: (("subject", "EXPERIENCER"), ("clause", "COMPLEMENT")),
    27: (("subject", "AGENT"), ("prep_object", "RECIPIENT")),
    28: (("subject", "AGENT"), ("to_inf", "COMPLEMENT")),
    29: (("subject", "AGENT"), ("whether_inf", "COMPLEMENT")),
    30: (("subject", "AGENT"), ("object", "THEME"), ("gerund", "COMPLEMENT")),
    31: (("subject", "AGENT"), ("object", "THEME"), ("prep_object", "INSTRUMENT")),
    32: (("subject", "AGENT"), ("bare_inf", "COMPLEMENT")),
    33: (("subject", "AGENT"), ("gerund", "COMPLEMENT")),
    34: (("subject", "AGENT"), ("clause", "COMPLEMENT")),
    35: (("subject", "AGENT"), ("to_inf", "COMPLEMENT")),
}

WN_POS_TO_CATEGORY = {
    POS_NOUN: "N",
    POS_VERB: "V",
    POS_ADJ: "ADJ",
    POS_ADV: "ADV",
}


@dataclass
class ImportStats:
    requested: int = 0
    found: int = 0
    missing: int = 0
    by_pos: Counter = None  # type: ignore[assignment]
    missing_words: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.by_pos = Counter()
        self.missing_words = []


def wordnet_entry(
    wordnet: WordNet,
    lemma: str,
    pos: str,
    *,
    max_senses: int = 4,
) -> dict[str, Any] | None:
    """One lexicon row for a lemma + WordNet POS, or None if unknown."""
    entries = wordnet.lookup(lemma, pos)
    if not entries:
        return None
    entry = entries[0]
    wordnet.load_data(pos)
    synsets: list[WordNetSynset] = []
    for offset in entry.synset_offsets:
        synset = wordnet.synset(offset, pos)
        if synset is not None:
            synsets.append(synset)
        if len(synsets) >= max_senses:
            break
    if not synsets:
        return None

    category = WN_POS_TO_CATEGORY.get(pos, "N")
    surfaces = sorted(_all_forms(wordnet, lemma, pos))
    if not surfaces:
        surfaces = [lemma]

    # Base sense features per POS; verbs expand into vform variants below.
    senses: list[dict[str, Any]] = []
    for index, synset in enumerate(synsets):
        semantic_type = LEXNAME_TO_TYPE.get(synset.lex_file, "REFERENTIAL")
        frames = _frames_from_synset(synset)
        score = round(1.0 - index * 0.05, 3)
        provenance = {
            "source": "wordnet",
            "offset": synset.offset,
            "lex_file": synset.lex_file,
            "gloss": synset.gloss[:120],
        }
        if pos == POS_VERB:
            for vform, vform_score in _VFORMS:
                feature_map = {"vform": vform}
                senses.append(
                    {
                        "id": f"wn-{synset.offset}-{pos}-{vform}",
                        "category": category,
                        "features": feature_map,
                        "semantic_type": semantic_type,
                        "frames": frames,
                        "score": round(score * vform_score, 3),
                        "provenance": provenance,
                    }
                )
        elif pos == POS_NOUN:
            for number, number_score in (("singular", 1.0), ("plural", 0.95)):
                senses.append(
                    {
                        "id": f"wn-{synset.offset}-{pos}-{number}",
                        "category": category,
                        "features": {"number": number},
                        "semantic_type": semantic_type,
                        "frames": [],
                        "score": round(score * number_score, 3),
                        "provenance": provenance,
                    }
                )
        else:
            senses.append(
                {
                    "id": f"wn-{synset.offset}-{pos}",
                    "category": category,
                    "features": {},
                    "semantic_type": semantic_type,
                    "frames": [],
                    "score": score,
                    "provenance": provenance,
                }
            )

    morphology = {s: lemma for s in surfaces if s != lemma}
    return {
        "lemma": lemma,
        "surfaces": surfaces,
        "senses": senses,
        "morphology": morphology,
        "provenance": {"source": "wordnet", "pos": pos},
    }


# Morphological slot variants for verbs — regular grammar, not a word list.
_VFORMS: tuple[tuple[str, float], ...] = (
    ("finite", 1.0),
    ("base", 0.92),
    ("ed", 0.9),
    ("ing", 0.9),
)


def _all_forms(wordnet: WordNet, lemma: str, pos: str) -> set[str]:
    """WordNet irregulars + regular English inflection rules."""
    forms = set(wordnet.morphological_forms(lemma, pos))
    forms.add(lemma)
    forms |= regular_inflections(lemma, pos)
    return forms


def regular_inflections(lemma: str, pos: str) -> set[str]:
    """Regular English inflection — a rule, not a list.

    Covers the productive patterns (-(e)s, -ing, -ed, y->ies/ied, doubling)
    and leaves irregulars to WordNet's exception files.
    """
    word = lemma.replace("_", " ").lower()
    out: set[str] = set()
    if len(word) < 2:
        return out

    if pos == POS_NOUN:
        out.add(_plural_noun(word))
    elif pos == POS_VERB:
        out.add(_third_person(word))
        out.add(_gerund(word))
        out.add(_past(word))
    elif pos == POS_ADJ:
        out.add(_comparative(word))
        out.add(_superlative(word))
    return {f for f in out if f and f != word}


def _plural_noun(word: str) -> str:
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith("f"):
        return word[:-1] + "ves"
    return word + "s"


def _third_person(word: str) -> str:
    return _plural_noun(word) if word.endswith(("s", "x", "z", "ch", "sh", "o")) else word + "s"


def _gerund(word: str) -> str:
    if word.endswith("ie"):
        return word[:-2] + "ying"
    if word.endswith("e") and not word.endswith(("ee", "oe", "ye")):
        return word[:-1] + "ing"
    if _needs_doubling(word):
        return word + word[-1] + "ing"
    return word + "ing"


def _past(word: str) -> str:
    if word.endswith("e"):
        return word + "d"
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ied"
    if _needs_doubling(word):
        return word + word[-1] + "ed"
    return word + "ed"


def _comparative(word: str) -> str:
    if len(word) <= 2:
        return word + "er"
    if word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ier"
    return word + "er"


def _superlative(word: str) -> str:
    if len(word) <= 2:
        return word + "est"
    if word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "iest"
    return word + "est"


def _needs_doubling(word: str) -> bool:
    """Double a final consonant only for monosyllabic CVC words.

    ``stop -> stopped`` but ``open -> opened``. Polysyllabic stress is
    unknown, so we stay conservative; irregulars come from WordNet.
    """
    if len(word) < 3:
        return False
    if word[-1] not in "bcdfglmnprstvz":
        return False
    if word[-2] not in "aeiou":
        return False
    # Exactly one vowel group => likely monosyllabic.
    vowel_groups = 0
    previous_was_vowel = False
    for char in word:
        is_vowel = char in "aeiou"
        if is_vowel and not previous_was_vowel:
            vowel_groups += 1
        previous_was_vowel = is_vowel
    return vowel_groups == 1


def _frames_from_synset(synset: WordNetSynset) -> list[dict[str, Any]]:
    """Keep WordNet sentence frames as alternatives, never one union."""
    frames: list[dict[str, Any]] = []
    seen_frames: set[int] = set()
    for frame in synset.frames:
        if frame.frame_number in seen_frames:
            continue
        seen_frames.add(frame.frame_number)
        slots = [
            {"syntactic": syntactic, "semantic_role": role}
            for syntactic, role in VERB_FRAME_SLOTS.get(frame.frame_number, ())
        ]
        if slots:
            frames.append({
                "id": f"wn-{synset.offset}-frame-{frame.frame_number}",
                "slots": slots,
            })
    return frames


def import_words(
    wordnet: WordNet,
    words: Iterable[str],
    *,
    max_senses: int = 3,
    pos_filter: Sequence[str] | None = None,
) -> tuple[list[dict[str, Any]], ImportStats]:
    """Build lexicon rows for the given words. POS comes from WordNet.

    Inflected corpus forms are linked back to their WordNet lemma through
    the exception files, so ``children`` contributes the ``child`` entry
    with ``children`` as a surface. No hand-written morphology.
    """
    stats = ImportStats()
    wanted_pos = tuple(pos_filter or (POS_NOUN, POS_VERB, POS_ADJ, POS_ADV))
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    # surface -> extra surface forms collected for a lemma+pos
    extra_surfaces: dict[tuple[str, str], set[str]] = {}

    # Build reverse exception tables once: surface -> lemma, per POS.
    reverse_exc: dict[str, dict[str, str]] = {}
    for pos in wanted_pos:
        table: dict[str, str] = {}
        for surface, lemma in wordnet.exceptions(pos).items():
            table[surface] = lemma
        reverse_exc[pos] = table

    for raw in words:
        word = raw.lower().strip()
        if not word or len(word) < 2 or word.isdigit():
            continue
        stats.requested += 1
        found_any = False
        for pos in wanted_pos:
            # Resolve inflected form -> base lemma via WordNet exceptions.
            base = reverse_exc[pos].get(word, word)
            key = (base, pos)
            if key in seen:
                extra_surfaces.setdefault(key, set()).add(word)
                found_any = True
                continue
            row = wordnet_entry(wordnet, base, pos, max_senses=max_senses)
            if row is None:
                continue
            seen.add(key)
            extra_surfaces.setdefault(key, set()).add(word)
            rows.append(row)
            stats.found += 1
            stats.by_pos[WN_POS_TO_CATEGORY.get(pos, pos)] += 1
            found_any = True
        if not found_any:
            stats.missing += 1
            stats.missing_words.append(word)

    # Attach observed corpus surfaces to their lemma rows.
    for row in rows:
        key = (row["lemma"], row["provenance"].get("pos"))
        extras = extra_surfaces.get(key, set())
        surfaces = set(row.get("surfaces", []))
        morph = dict(row.get("morphology", {}))
        for surface in extras:
            surfaces.add(surface)
            if surface != row["lemma"]:
                morph[surface] = row["lemma"]
        row["surfaces"] = sorted(surfaces)
        row["morphology"] = morph

    return rows, stats


def words_from_text(text: str) -> list[str]:
    """Tokens of a text, in order, lowercased. No filtering by list."""
    import re

    return re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())


def words_from_corpus(path: str | Path) -> list[str]:
    return words_from_text(Path(path).read_text(encoding="utf-8"))


def build_lexicon(
    words: Iterable[str],
    *,
    wordnet_dict: str | Path,
    max_senses: int = 3,
) -> tuple[list[dict[str, Any]], ImportStats]:
    wordnet = WordNet(wordnet_dict)
    return import_words(wordnet, words, max_senses=max_senses)


def write_lexicon(rows: Sequence[Mapping[str, Any]], path: str | Path) -> None:
    path = Path(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
