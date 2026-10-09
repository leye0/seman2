"""Reference links — identity, non-identity and structural sharing.

Base contract: ``plans/coreference-guide.md``. A link never claims world
knowledge; it only records what the grammatical form licenses.

Kinds
-----
SAME_REF           the construction forces one referent (under the analysis)
MAYBE_REF          an explicit marker allows a match without proving it
DIFFERENT_REF      a construction forces a distinction
NO_LINK            nothing in the form justifies a correspondence
ASSERTED_IDENTITY  the text asserts identity (aka, apposition), ≠ grammar
BOUND_VARIABLE     quantifier binding (every student … their)
SHARED_ARGUMENT    one argument syntactically shared by two predicates
TYPE_ANAPHORA      nominal category reuse (one/ones), not individual identity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class ReferenceKind(str, Enum):
    SAME_REF = "SAME_REF"
    MAYBE_REF = "MAYBE_REF"
    DIFFERENT_REF = "DIFFERENT_REF"
    NO_LINK = "NO_LINK"
    ASSERTED_IDENTITY = "ASSERTED_IDENTITY"
    BOUND_VARIABLE = "BOUND_VARIABLE"
    SHARED_ARGUMENT = "SHARED_ARGUMENT"
    TYPE_ANAPHORA = "TYPE_ANAPHORA"


@dataclass(frozen=True, slots=True)
class ReferenceLink:
    """One licensed relation between two referring expressions.

    ``source`` is the anaphor / dependent side; ``target`` the antecedent
    or head. ``None`` target means unresolved (external or NO_LINK).
    """

    source: str
    target: str | None
    kind: ReferenceKind
    rule_id: str
    parse_id: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind.value,
            "rule_id": self.rule_id,
            "parse_id": self.parse_id,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class RefFamily:
    """One REF family from the guide."""

    family_id: str
    name: str
    priority: str  # P0 | P1 | P2 | OUT
    description: str


# §7 of the guide — the standing inventory.
REF_FAMILIES: tuple[RefFamily, ...] = (
    RefFamily("REF-01", "Pronoms réfléchis locaux", "P0", "Binding: himself/themselves ↔ local antecedent"),
    RefFamily("REF-02", "Relatifs explicites", "P0", "who/whom/which/that ↔ antecedent of the relative"),
    RefFamily("REF-03", "Relatifs à argument implicite", "P0", "Reduced/zero relative: gap = antecedent"),
    RefFamily("REF-04", "Sujets et objets syntaxiquement partagés", "P0", "Coordination / gapping shares an argument"),
    RefFamily("REF-05", "Contraintes locales de non-identité", "P0", "Binding-theory exclusion (John saw him)"),
    RefFamily("REF-06", "Pronoms personnels et possessifs", "P0", "he/she/it/they + possessives: MAYBE_REF"),
    RefFamily("REF-07", "Répétition lexicale exacte", "P0", "Same head lemma, no synonymy"),
    RefFamily("REF-08", "Normalisation morphologique", "P0", "Lemma-normalized repetition"),
    RefFamily("REF-09", "Références inconnues et externes", "P0", "No textual antecedent → NO_LINK"),
    RefFamily("REF-10", "Détection des pronoms explétifs", "P0", "it/there expletive → NO_LINK"),
    RefFamily("REF-11", "Appositions identificatrices", "P1", "John, my brother → ASSERTED_IDENTITY"),
    RefFamily("REF-12", "Intensificateurs réfléchis", "P1", "John himself → ASSERTED / emphasis"),
    RefFamily("REF-13", "Démonstratifs", "P1", "this/that/these/those as anaphors"),
    RefFamily("REF-14", "Ordinals, former/latter", "P1", "the former/the latter/the first"),
    RefFamily("REF-15", "Groupes pluriels et collectifs", "P1", "both/all three/the two"),
    RefFamily("REF-16", "Marqueurs explicites d'identité", "P1", "aka, named, same person as"),
    RefFamily("REF-17", "Marqueurs explicites de différence", "P1", "another, different, someone else"),
    RefFamily("REF-18", "Première et deuxième personne", "P1", "I/we/you need a speaker anchor"),
    RefFamily("REF-19", "Liaison de variables quantifiées", "P1", "every student … their/themselves"),
    RefFamily("REF-20", "Ellipses nominales", "P2", "one/ones → TYPE_ANAPHORA"),
    RefFamily("REF-21", "Ellipses verbales et propositionnelles", "P2", "so/do/VP ellipsis"),
    RefFamily("REF-22", "Contrôle et montée", "P2", "John tried to leave / seems to sleep"),
    RefFamily("REF-23", "Références à événements et propositions", "P2", "this/that over a clause"),
    RefFamily("REF-24", "Cataphores", "P2", "Forward reference"),
    RefFamily("REF-25", "Anaphores associatives", "OUT", "Bridging — outside the parser"),
)

FAMILY_BY_ID = {f.family_id: f for f in REF_FAMILIES}


@dataclass
class ReferenceReport:
    """Links produced for one parse or one sentence."""

    links: list[ReferenceLink] = field(default_factory=list)
    parse_id: str = ""

    def add(self, link: ReferenceLink) -> None:
        self.links.append(link)

    def by_kind(self, kind: ReferenceKind) -> list[ReferenceLink]:
        return [lk for lk in self.links if lk.kind == kind]

    def by_family(self, family_id: str) -> list[ReferenceLink]:
        return [lk for lk in self.links if lk.rule_id.startswith(family_id)]

    def as_dict(self) -> dict[str, Any]:
        return {"parse_id": self.parse_id, "links": [lk.as_dict() for lk in self.links]}

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for lk in self.links:
            counts[lk.kind.value] = counts.get(lk.kind.value, 0) + 1
        parts = [f"{k}={v}" for k, v in sorted(counts.items())]
        return f"{len(self.links)} links ({', '.join(parts) or 'none'})"
