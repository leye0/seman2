"""Gold coreference chains for novel sentences 1–10 (extract_sentences indices 0–9).

Each chain lists referring expressions of one discourse entity as
``(sentence_index, surface, occurrence)`` where ``occurrence`` disambiguates
repeated surfaces inside the same sentence (0-based).

Only clear identity coreference is annotated. Generic/episodic NPs without a
later anaphor are omitted — they do not test linking.
"""

from __future__ import annotations

# Sentence 0 is the title "A year on Maple Street"; no coreference there.
GOLD_CHAINS: dict[str, list[tuple[int, str, int]]] = {
    "maya": [
        (2, "Maya", 0),
        (3, "She", 0),
        (4, "her", 0),
        (8, "Maya", 0),
        (8, "her", 0),  # an adult reminded her
        (8, "her", 1),  # her part of the table
        (9, "she", 0),
    ],
    "home": [
        (6, "home", 0),
        (7, "home", 0),
    ],
    "place": [
        (5, "A place", 0),
        (5, "it", 0),
    ],
    "family_cat": [
        (8, "family cat", 0),
        (8, "cat", 0),
    ],
}

# Singleton referents (kept for recall of single-mention entities if needed).
GOLD_SINGLETONS: dict[str, list[tuple[int, str, int]]] = {
    "september": [(1, "September", 0)],
    "school": [(1, "school", 0)],
    "cafeteria": [(2, "cafeteria", 0)],
    "sign": [(2, "sign", 0)],
    "teacher": [(4, "teacher", 0)],
    "desk": [(4, "desk", 0)],
    "mom": [(7, "Mom", 0)],
    "dad": [(7, "Dad", 0)],
    "eli": [(7, "Eli", 0)],
    "adult": [(8, "adult", 0)],
}


def all_gold() -> dict[str, list[tuple[int, str, int]]]:
    out = dict(GOLD_CHAINS)
    out.update(GOLD_SINGLETONS)
    return out
