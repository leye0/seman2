"""Source lexical catalog: morphology plus separately projected sense data.

The syntax layer consumes only category/features and the syntactic projection
of frames. Semantic types and role mappings stay in this catalog so the
post-parse interpreter can resolve stable sense ids; they are never copied
into parser hypotheses.

Content words (N/V/ADJ/ADV) are served by WordNet: exhaustive coverage of
the English open class, no hand-made word lists. Closed-class function
words (DET/PRON/PREP/…) are a small grammatical inventory loaded as data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .features import FeatureStructure


@dataclass(frozen=True, slots=True)
class ArgumentSlot:
    """One subcategorization slot mapped to a semantic role."""

    syntactic: str  # e.g. "subject", "object", "iobj", "pp:for", "cp"
    semantic_role: str  # e.g. "AGENT", "THEME" — names come from data
    optional: bool = False
    features: FeatureStructure = field(default_factory=FeatureStructure.empty)

    def as_dict(self) -> dict[str, Any]:
        return {
            "syntactic": self.syntactic,
            "semantic_role": self.semantic_role,
            "optional": self.optional,
            "features": self.features.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class SenseFrame:
    """A subcategorization frame for one lexical sense."""

    frame_id: str
    slots: tuple[ArgumentSlot, ...]

    def required_slots(self) -> tuple[ArgumentSlot, ...]:
        return tuple(slot for slot in self.slots if not slot.optional)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.frame_id, "slots": [slot.as_dict() for slot in self.slots]}


@dataclass(frozen=True, slots=True)
class LexicalSense:
    """One sense of a lexical entry."""

    sense_id: str
    category: str  # grammatical category label, e.g. "V", "N"
    features: FeatureStructure = field(default_factory=FeatureStructure.empty)
    semantic_type: str | None = None
    frames: tuple[SenseFrame, ...] = ()
    particle: str | None = None
    score: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.sense_id,
            "category": self.category,
            "features": self.features.as_dict(),
            "semantic_type": self.semantic_type,
            "frames": [frame.as_dict() for frame in self.frames],
            "particle": self.particle,
            "score": self.score,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True, slots=True)
class LexicalEntry:
    """All known surface material for one lemma."""

    lemma: str
    surfaces: tuple[str, ...]
    senses: tuple[LexicalSense, ...]
    morphology: Mapping[str, str] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def sense(self, sense_id: str) -> LexicalSense:
        for candidate in self.senses:
            if candidate.sense_id == sense_id:
                return candidate
        raise KeyError(f"unknown sense {sense_id!r} for lemma {self.lemma!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "lemma": self.lemma,
            "surfaces": list(self.surfaces),
            "senses": [sense.as_dict() for sense in self.senses],
            "morphology": dict(self.morphology),
            "provenance": dict(self.provenance),
        }


def _parse_slot(raw: Mapping[str, Any]) -> ArgumentSlot:
    return ArgumentSlot(
        syntactic=str(raw["syntactic"]),
        semantic_role=str(raw["semantic_role"]),
        optional=bool(raw.get("optional", False)),
        features=FeatureStructure.build(dict(raw.get("features", {}))),
    )


def _parse_frame(raw: Mapping[str, Any]) -> SenseFrame:
    return SenseFrame(
        frame_id=str(raw.get("id", "frame")),
        slots=tuple(_parse_slot(row) for row in raw.get("slots", ())),
    )


def _parse_sense(raw: Mapping[str, Any]) -> LexicalSense:
    return LexicalSense(
        sense_id=str(raw.get("id", raw.get("sense_id", "sense"))),
        category=str(raw["category"]),
        features=FeatureStructure.build(dict(raw.get("features", {}))),
        semantic_type=raw.get("semantic_type"),
        frames=tuple(_parse_frame(row) for row in raw.get("frames", ())),
        particle=raw.get("particle"),
        score=float(raw.get("score", 0.0)),
        provenance=dict(raw.get("provenance", {})),
    )


def parse_entry(raw: Mapping[str, Any]) -> LexicalEntry:
    lemma = str(raw["lemma"])
    surfaces = tuple(str(item) for item in raw.get("surfaces", (lemma,)))
    return LexicalEntry(
        lemma=lemma,
        surfaces=surfaces,
        senses=tuple(_parse_sense(row) for row in raw.get("senses", ())),
        morphology={str(k): str(v) for k, v in dict(raw.get("morphology", {})).items()},
        provenance=dict(raw.get("provenance", {})),
    )


class Lexicon:
    """Surface and lemma indexes over lexical entries.

    Optionally backed by WordNet for open-class words: any English content
    word can be looked up exhaustively. Closed-class entries (function
    words) live in the static table. Both sources merge transparently.
    """

    __slots__ = ("entries", "_by_surface", "_by_lemma", "_by_morph", "_wordnet", "_cache", "_max_senses", "_irregular_vforms")

    def __init__(
        self,
        entries: Iterable[LexicalEntry] = (),
        *,
        wordnet: Any | None = None,
        max_senses: int = 2,
    ) -> None:
        self.entries: tuple[LexicalEntry, ...] = tuple(entries)
        self._by_surface: dict[str, list[LexicalEntry]] = {}
        self._by_lemma: dict[str, list[LexicalEntry]] = {}
        self._by_morph: dict[str, list[tuple[LexicalEntry, str]]] = {}
        self._wordnet = wordnet
        self._cache: dict[str, tuple[LexicalEntry, ...]] = {}
        self._max_senses = max_senses
        # Evidence belongs to the inflectional paradigm, not to a word's
        # grammatical role in a particular sentence. In WordNet, irregular
        # exceptions identify lemmas but not past vs past participle.
        # A documented paradigm may constrain this ambiguity for that form.
        self._irregular_vforms: dict[tuple[str, str], set[str]] = {}
        for entry in self.entries:
            for form, surfaces in entry.provenance.get("irregular_verb_forms", {}).items():
                if form not in {"finite", "ed"}:
                    raise ValueError(f"Unrecognized irregular verb vform: {form}")
                for surface in surfaces:
                    self._irregular_vforms.setdefault(
                        (surface.casefold(), entry.lemma.casefold()), set()
                    ).add(form)
            self._index(entry)

    def _index(self, entry: LexicalEntry) -> None:
        self._by_lemma.setdefault(entry.lemma, []).append(entry)
        for surface in entry.surfaces:
            self._by_surface.setdefault(surface.lower(), []).append(entry)
        for form, lemma in entry.morphology.items():
            self._by_morph.setdefault(form.lower(), []).append((entry, lemma))

    @property
    def has_wordnet(self) -> bool:
        return self._wordnet is not None

    def entries_for_lemma(self, lemma: str) -> Sequence[LexicalEntry]:
        """All entries for a lemma (function words + every WordNet POS)."""
        cached = self._cache.get(lemma)
        if cached is not None:
            return cached
        static = list(self._by_lemma.get(lemma, ()))
        built: list[LexicalEntry] = list(static)
        blockers = [
            entry for entry in static
            if not entry.provenance.get("merge_wordnet", False)
        ]
        if self._wordnet is not None:
            for entry in self._wordnet_entries(lemma):
                # Don't duplicate a static entry with the same POS.
                pos = entry.provenance.get("pos")
                if any(s.provenance.get("pos") == pos for s in blockers):
                    continue
                if any(s.lemma == entry.lemma and s.senses and entry.senses
                       and s.senses[0].category == entry.senses[0].category for s in blockers):
                    continue
                # Optional lexical countability declarations refine every noun
                # sense without replacing WordNet's sense inventory or morphology.
                if any(s.provenance.get("noun_countability") == "count"
                       for s in static):
                    entry = replace(entry, senses=tuple(
                        replace(sense, features=FeatureStructure.build({
                            **sense.features.as_dict(),
                            "bare_nominal": "false" if sense.features.as_dict().get("number") == "singular" else "true",
                        })) if sense.category == "N" else sense
                        for sense in entry.senses
                    ))
                built.append(entry)
                self._index(entry)
        self._cache[lemma] = tuple(built)
        return tuple(built)

    def by_lemma(self, lemma: str) -> LexicalEntry | None:
        found = self.entries_for_lemma(lemma)
        return found[0] if found else None

    def _wordnet_entries(self, word: str) -> list[LexicalEntry]:
        """Build lexical entries from WordNet for every open-class POS."""
        from .lexicon_from_wordnet import wordnet_entry
        from .wordnet import POS_ADJ, POS_ADV, POS_NOUN, POS_VERB

        out: list[LexicalEntry] = []
        for pos in (POS_NOUN, POS_VERB, POS_ADJ, POS_ADV):
            row = wordnet_entry(self._wordnet, word, pos, max_senses=self._max_senses)
            if row is not None:
                out.append(parse_entry(row))
        return out

    def lookup_surface(self, surface: str) -> Sequence[LexicalEntry]:
        key = surface.lower()
        found = list(self._by_surface.get(key, ()))
        # Merge local entries with every WordNet POS.  A local spelling must
        # not hide an additional open-class category needed by the lexical
        # bit vector (for example N|V).
        for entry in self.entries_for_lemma(key):
            if entry not in found:
                found.append(entry)
        for entry, _lemma, _category in self._resolve_lemma_candidates(key):
            if entry not in found:
                found.append(entry)
        return found

    def _resolve_lemma_candidates(self, surface: str) -> list[tuple[LexicalEntry, str, str | None]]:
        """Map a surface to (entry, lemma, category) morphology triples.

        WordNet exception tables are POS-specific.  Keeping that POS is
        essential: the verb exception ``said -> say`` must not manufacture
        the unrelated noun reading of ``say``.
        """
        out: list[tuple[LexicalEntry, str, str | None]] = []
        for entry, lemma in self._by_morph.get(surface, ()):
            out.append((entry, lemma, None))
        # Static morphology and WordNet exceptions are independent sources.
        # An irregular verb such as "did" may be an auxiliary in the local
        # inventory AND a lexical verb in WordNet; the local mapping must not
        # hide the POS-specific exception for its open-class reading.
        if self._wordnet is not None:
            from .wordnet import POS_ADJ, POS_ADV, POS_NOUN, POS_VERB

            categories = {
                POS_NOUN: "N", POS_VERB: "V", POS_ADJ: "ADJ", POS_ADV: "ADV",
            }
            for pos in (POS_NOUN, POS_VERB, POS_ADJ, POS_ADV):
                exceptions = self._wordnet.exceptions(pos)
                lemma = exceptions.get(surface)
                if lemma is None:
                    continue
                for entry in self.entries_for_lemma(lemma):
                    out.append((entry, lemma, categories[pos]))
        return out

    def lookup_morphology(self, surface: str) -> Sequence[tuple[LexicalEntry, LexicalSense, str]]:
        """Return (entry, sense, lemma) triples for a surface form.

        Sources, in order: static lexicon, WordNet exceptions, regular
        English suffix rules. No hand-written word lists.
        """
        out: list[tuple[LexicalEntry, LexicalSense, str]] = []
        lowered = surface.lower()
        seen: set[tuple[int, str, str | None]] = set()

        def _add(entry: LexicalEntry, lemma: str, category: str | None = None) -> None:
            # A construction-specific reading can attest an inflected
            # surface without attesting the rest of its paradigm.
            if (entry.provenance.get("exact_surface_only")
                    and lowered not in {form.casefold() for form in entry.surfaces}):
                return
            key = (id(entry), lemma, category)
            if key in seen:
                return
            seen.add(key)
            for sense in entry.senses:
                if category is not None and sense.category != category:
                    continue
                if (entry.provenance.get("source") == "wordnet"
                        and sense.category == "V"):
                    allowed = self._irregular_vforms.get((lowered, lemma.casefold()))
                    if allowed and sense.features.as_dict().get("vform") not in allowed:
                        continue
                out.append((entry, sense, lemma))

        # Exact spellings first.  Do not call ``lookup_surface`` here: that
        # convenience API also resolves morphological lemmas but returns
        # whole entries, which erases the POS attached to a WordNet exception.
        # The POS-preserving resolution immediately below handles inflections.
        exact = list(self._by_surface.get(lowered, ()))
        for entry in self.entries_for_lemma(lowered):
            if lowered in {surface.casefold() for surface in entry.surfaces} and entry not in exact:
                exact.append(entry)
        for entry in exact:
            _add(entry, entry.lemma)
        for entry, lemma, category in self._resolve_lemma_candidates(lowered):
            _add(entry, lemma, category)

        # Regular suffix stripping merges additional readings even when the
        # surface is already a lemma ("opened" is also a participle of "open").
        # An arbitrary closed-class form ("his", "of") must not spawn
        # unrelated open-class stems. But when the local morphology itself
        # attests the stem ("does" -> "do"), preserve independently licensed
        # WordNet verb inflections alongside AUX instead of erasing them.
        closed_class = _has_closed_class(out)
        attested_stems = {
            lemma.casefold() for _, lemma in self._by_morph.get(lowered, ())
        } if closed_class else set()
        if not closed_class or attested_stems:
            for suffix, cut, tag in (("ing", 3, "ing"), ("ed", 2, "ed"), ("s", 1, "s")):
                if len(lowered) <= len(suffix) + 1 or not lowered.endswith(suffix):
                    continue
                stem = lowered[: len(lowered) - cut]
                candidates = [stem, stem + "e"]
                # Only undo consonant doubling when doubling is actually
                # visible (``stopped -> stop``).  The old unconditional
                # truncation made ``asked`` generate the unrelated lemma
                # ``as`` and introduced spurious lexical paths.
                if len(stem) > 1 and stem[-1] == stem[-2]:
                    candidates.append(stem[:-1])
                if tag == "ed" and stem.endswith("i"):
                    candidates.append(stem[:-1] + "y")
                if tag == "s" and lowered.endswith("ies"):
                    candidates.append(lowered[:-3] + "y")
                if tag == "s" and lowered.endswith("es"):
                    # buses -> bus, boxes -> box, wishes -> wish.  The
                    # ordinary one-letter candidate still covers uses -> use.
                    candidates.append(lowered[:-2])
                for candidate in candidates:
                    if candidate == lowered or (closed_class and candidate not in attested_stems):
                        continue
                    for entry in self.entries_for_lemma(candidate):
                        for sense in entry.senses:
                            if _suffix_compatible(sense, tag) and (
                                not closed_class or sense.category == "V"
                            ):
                                out.append((entry, sense, entry.lemma))
        return out

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)


def _suffix_compatible(sense: LexicalSense, tag: str) -> bool:
    vform = sense.features.get("vform")
    if vform is not None:
        name = getattr(vform, "name", None)
        if name is None:
            return True
        if tag == "ing":
            return name == "ing"
        if tag == "ed":
            return name in {"finite", "ed"}
        if tag == "s":
            return name == "finite"
        return False
    number = sense.features.get("number")
    if number is not None:
        return tag == "s" and getattr(number, "name", None) == "plural"
    # Productive -ed/-ing stripping is verbal and productive -s stripping is
    # verbal or nominal.  It must not project every unrelated POS belonging
    # to the recovered lemma onto the inflected surface.
    return False


_CLOSED_CATEGORIES = {
    "DET", "PRONOUN", "POSS", "PREP", "PREP-BY", "COORD", "CONJ", "NEG",
    "AUX", "AUX-BE", "MODAL", "WH-PRONOUN", "WH-NOM", "COMP-THAT",
    "TO", "PARTICLE", "DEGREE", "EXPL", "NUM",
}


def _has_closed_class(hits: Sequence[tuple[LexicalEntry, LexicalSense, str]]) -> bool:
    return any(sense.category in _CLOSED_CATEGORIES for _, sense, _ in hits)


def load_lexicon(
    path: str | Path,
    *,
    wordnet_dict: str | Path | Any | None = None,
    max_senses: int = 2,
    supplemental_paths: Sequence[str | Path] = (),
) -> Lexicon:
    """Load the closed-class inventory from ``path``.

    If ``wordnet_dict`` is given (a dict directory or an open ``WordNet``),
    open-class words are served live from WordNet so coverage is
    exhaustive — no corpus-filtered word list.
    """
    entries: list[LexicalEntry] = []
    paths = (Path(path), *(Path(item) for item in supplemental_paths))
    for source_path in paths:
        if not source_path.exists():
            continue
        with source_path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{source_path}:{line_no}: invalid lexicon JSON: {exc}") from exc
                entries.append(parse_entry(raw))
    wordnet = None
    if wordnet_dict is not None:
        from .wordnet import WordNet, shared_wordnet

        if isinstance(wordnet_dict, WordNet):
            wordnet = wordnet_dict
        else:
            wordnet = shared_wordnet(wordnet_dict)
    return Lexicon(entries, wordnet=wordnet, max_senses=max_senses)


def load_lexicon_rows(rows: Iterable[Mapping[str, Any]]) -> Lexicon:
    return Lexicon(parse_entry(row) for row in rows)
