"""Typed, atomically composed adjective projections over independently parsed trees.

A dependency tree is *evidence* for where to attempt an operation. This module
does not assert that Stanza's dependency is right, or that an observed PP is
necessarily selected rather than an adjunct. It preserves lexical heads and
keeps grammatical operations independent of word identities.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .core import TYPES, Word, classify_attestation, unify


@dataclass(frozen=True)
class Operation:
    kind: str
    head: int
    dependent: int
    marker: int | None
    basis: str


@dataclass(frozen=True)
class AdjectiveProjection:
    lexical_head_id: int
    lexical_head_lemma: str
    features: Mapping[str, Any]
    operations: tuple[Operation, ...]
    lexical_hypotheses: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "lexical_head_id": self.lexical_head_id,
            "lexical_head_lemma": self.lexical_head_lemma,
            "features": dict(self.features),
            "operations": [
                {"kind": o.kind, "head": o.head, "dependent": o.dependent,
                 "marker": o.marker, "basis": o.basis}
                for o in self.operations
            ],
            "lexical_hypotheses": list(self.lexical_hypotheses),
        }


def compose_adjective_projections(
    words: Sequence[Word],
    ud_train_evidence: Mapping[str, Any] | None = None,
    erg_lexemes: Mapping[str, Sequence[str]] | None = None,
) -> tuple[AdjectiveProjection, ...]:
    """Compose a typed adjective phrase without inspecting lexeme spellings.

    Prepositions/infinitives are distinguished by *dependencies* and their
    marker's grammatical function; `to` itself is only an overt marker of the
    requested construction, never a hidden lexical allowlist.
    """
    children: dict[int, list[Word]] = defaultdict(list)
    for child in words:
        children[child.head].append(child)
    words_by_id = {word.id: word for word in words}
    projections = []
    for adjective in words:
        if adjective.upos != "ADJ":
            continue
        features = TYPES.effective("adjective")
        operations: list[Operation] = []
        hypotheses: list[Mapping[str, Any]] = []
        for dependent in sorted(children[adjective.id], key=lambda w: w.id):
            if dependent.upos == "ADV" and dependent.rel == "advmod":
                operations.append(Operation("head_modifier", adjective.id, dependent.id,
                                            None, "UD:advmod(ADV->ADJ)"))
                # Extending the phrase with an ADV must preserve HEAD. Not all
                # modifiers are degree modifiers, so do not add DEGREE.
                features = unify(features, {"HEAD": {"pos": "ADJ", "is_lexical": True}})
                continue
            marker = next((m for m in children[dependent.id]
                           if m.lemma.lower() == "to" and
                           ((dependent.rel in {"obl","nmod"} and m.rel == "case")
                            or (dependent.rel == "xcomp" and m.rel == "mark"))), None)
            if marker is None:
                continue
            if dependent.rel in {"obl","nmod"}:
                kind, type_name, symbol = (
                    "head_pp_attachment_candidate", "adjective-with-to-pp",
                    "adjective_to_pp_candidate"
                )
            elif dependent.rel == "xcomp":
                kind, type_name, symbol = (
                    "head_infinitival_attachment_candidate",
                    "adjective-with-to-infinitive",
                    "adjective_to_infinitive_candidate"
                )
            else:
                continue
            op = Operation(kind, adjective.id, dependent.id, marker.id,
                           "UD:" + dependent.deprel + "+" + marker.deprel)
            operations.append(op)
            attestation = classify_attestation(
                adjective.lemma, symbol, ud_train_evidence or {})
            hypotheses.append({
                "type": type_name,
                "head": adjective.id,
                "dependent": dependent.id,
                "marker": marker.id,
                "signature": TYPES.effective(type_name),
                "ud_train_attestation": attestation,
                "erg_lexical_types": list((erg_lexemes or {}).get(
                    adjective.lemma.lower(), ()))[:10],
                # A relation plus a word's lexical inventory does not
                # resolve PP argument vs adjunct or adjective word sense.
                "status": "candidate_not_licensed",
                "selected_complement_proven": False,
            })
            # A complement hypothesis does not erase the head's identity or
            # imply that an optional lexical valence has been saturated.
            features = unify(features, {"HEAD": {"pos": "ADJ", "is_lexical": True}})
        if operations:
            projections.append(AdjectiveProjection(
                lexical_head_id=adjective.id,
                lexical_head_lemma=adjective.lemma.lower(),
                features=features,
                operations=tuple(operations),
                lexical_hypotheses=tuple(hypotheses),
            ))
    return tuple(projections)


def composition_gold_keys(words: Sequence[Word]) -> set[tuple[str, int, int]]:
    """Operations tracked by the POC, including the overt dependency head."""
    return {(o.kind, o.head, o.dependent)
            for p in compose_adjective_projections(words) for o in p.operations}
