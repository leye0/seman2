"""Standalone typed-feature research primitives, with no Seman2 grammar dispatch.

No word lists from the Novel corpus are used to construct a rule.  A source
attestation may propose a lexical class; it may never certify a parse.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class TypeDef:
    name: str
    parents: tuple[str, ...]
    constraints: Mapping[str, Any]


class TypeConflict(ValueError):
    pass


class TypeHierarchy:
    """Small HPSG-inspired multiple-inheritance lattice with feature unification.

    Deliberately NOT an implementation of ERG or HPSG.  It accepts a limited
    subset of typed signatures and reports conflicting claims rather than
    silently choosing a preferred lexical reading.
    """

    def __init__(self, definitions: Iterable[TypeDef]):
        self.definitions = {d.name: d for d in definitions}
        self._memo: dict[str, dict[str, Any]] = {}

    def effective(self, name: str, visiting: frozenset[str] = frozenset()) -> dict[str, Any]:
        if name in self._memo:
            return dict(self._memo[name])
        if name in visiting:
            raise TypeConflict("Cycle in type hierarchy: " + name)
        if name not in self.definitions:
            raise KeyError(name)
        definition = self.definitions[name]
        traits: dict[str, Any] = {}
        for parent in definition.parents:
            traits = unify(traits, self.effective(parent, visiting | {name}))
        traits = unify(traits, definition.constraints)
        self._memo[name] = traits
        return dict(traits)


def unify(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(value, Mapping) and isinstance(merged[key], Mapping):
            merged[key] = unify(merged[key], value)
        elif value != merged[key]:
            raise TypeConflict(f"Feature clash for {key}: {merged[key]!r} vs {value!r}")
    return merged


TYPES = TypeHierarchy([
    TypeDef("sign", (), {}),
    TypeDef("lexical-head", ("sign",), {"HEAD": {"is_lexical": True}}),
    TypeDef("adjective", ("lexical-head",), {"HEAD": {"pos": "ADJ"}}),
    TypeDef("adjective-with-pp", ("adjective",), {"VALENCE": {"category": "PP"}}),
    TypeDef("adjective-with-to-pp", ("adjective-with-pp",),
            {"VALENCE": {"preposition": "to"}}),
    TypeDef("adjective-with-to-infinitive", ("adjective",),
            {"VALENCE": {"category": "INFINITIVE", "marker": "to"}}),
    TypeDef("adjective-with-extraposed-infinitival-subject", ("adjective",),
            {"EXTRAPOSED_SUBJECT": {"category": "INFINITIVE", "marker": "to"},
             "VALENCE": {}}),
    TypeDef("adjective-modifying-adverb", ("lexical-head",),
            {"HEAD": {"pos": "ADV"}, "MODIFIES": "ADJ"}),
    TypeDef("degree-adverb", ("adjective-modifying-adverb",),
            {"DEGREE": True}),
])


@dataclass(frozen=True)
class Word:
    id: int
    text: str
    lemma: str
    upos: str
    head: int
    deprel: str
    features: str = ""

    @property
    def rel(self) -> str:
        return self.deprel.split(":")[0]


def validate_dependency_tree(words: list[Word]) -> tuple[bool, str]:
    if not words:
        return False, "empty"
    index = {w.id: w for w in words}
    if len(index) != len(words) or any(w.id <= 0 for w in words):
        return False, "duplicate_or_invalid_ids"
    if sum(w.head == 0 for w in words) != 1:
        return False, "not_exactly_one_root"
    for w in words:
        if w.head and w.head not in index:
            return False, "dangling_head"
        reached = {w.id}
        cursor = w
        while cursor.head:
            if cursor.head in reached:
                return False, "cycle"
            reached.add(cursor.head)
            cursor = index[cursor.head]
    return True, "valid"


def grammatical_observations(words: list[Word]) -> list[dict[str, Any]]:
    """Extract evidence about grammatical relations, not word co-occurrence.

    UD `obl` plus a case marker is a *candidate* adjectival PP attachment,
    not proof that the PP is selected rather than an adjunct.
    """
    children: dict[int, list[Word]] = defaultdict(list)
    for w in words:
        children[w.head].append(w)
    observed: list[dict[str, Any]] = []
    for head in words:
        if head.upos != "ADJ":
            continue
        for child in children[head.id]:
            if child.rel == "advmod" and child.upos == "ADV":
                observed.append({"kind": "adjective_adverb_modification",
                                 "head": head.lemma.lower(), "dependent": child.lemma.lower(),
                                 "head_id": head.id, "dependent_id": child.id})
            if child.rel in {"obl", "nmod"}:
                markers = [m for m in children[child.id] if m.rel == "case"
                           and m.lemma.lower() == "to"]
                if markers:
                    observed.append({"kind": "adjective_to_pp_candidate",
                                     "head": head.lemma.lower(), "dependent": child.lemma.lower(),
                                     "head_id": head.id, "dependent_id": child.id,
                                     "marker_id": markers[0].id})
            if child.rel == "xcomp":
                markers = [m for m in children[child.id] if m.rel == "mark"
                           and m.lemma.lower() == "to"]
                if markers:
                    observed.append({"kind": "adjective_to_infinitive_candidate",
                                     "head": head.lemma.lower(), "dependent": child.lemma.lower(),
                                     "head_id": head.id, "dependent_id": child.id,
                                     "marker_id": markers[0].id})
    return observed


def induce_evidence(conllu_text: str) -> dict[str, Any]:
    """Learn lexical trait hypotheses ONLY from an external UD training split."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[dict[str, str]]] = defaultdict(list)
    sentence: list[Word] = []
    sent_id = ""

    def consume() -> None:
        if not sentence:
            return
        valid, _ = validate_dependency_tree(sentence)
        if not valid:
            return
        for obs in grammatical_observations(sentence):
            key = obs["kind"]
            lemma = obs["head"]
            counts[key][lemma] += 1
            if len(examples[key]) < 600 and len([e for e in examples[key] if e["lemma"] == lemma]) < 2:
                examples[key].append({"lemma": lemma, "sentence": sent_id,
                                      "dependent": obs["dependent"]})

    for line in conllu_text.splitlines():
        if not line:
            consume()
            sentence = []
            sent_id = ""
            continue
        if line.startswith("# sent_id = "):
            sent_id = line.split("=", 1)[1].strip()
            continue
        if line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) != 10 or not cols[0].isdigit():
            continue
        if not cols[6].isdigit():
            continue
        sentence.append(Word(id=int(cols[0]), text=cols[1], lemma=cols[2],
                             upos=cols[3], head=int(cols[6]), deprel=cols[7],
                             features=cols[5]))
    consume()
    return {
        "source": "UD_English-EWT_train_only",
        "patterns": {k: dict(v) for k, v in sorted(counts.items())},
        "examples": dict(examples),
        "counts": {k: sum(v.values()) for k, v in counts.items()},
    }


def classify_attestation(lemma: str, observed_kind: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    count = evidence.get("patterns", {}).get(observed_kind, {}).get(lemma.lower(), 0)
    # These are counts of attested dependencies, not estimates of grammaticality.
    return {"attestation_count": count, "level": "attested" if count else "unattested",
            "source": evidence.get("source"), "negative_evidence": False}


def nonwhitespace_coverage(text: str, spans: Iterable[tuple[int, int]]) -> bool:
    covered = bytearray(len(text))
    for start, end in spans:
        if 0 <= start <= end <= len(text):
            covered[start:end] = b"\x01" * (end - start)
    return all(ch.isspace() or covered[i] for i, ch in enumerate(text))


def source_sha(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()
