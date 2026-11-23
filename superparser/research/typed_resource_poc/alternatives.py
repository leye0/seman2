"""Grammar-motivated alternative attachment search independent of Stanza edges.

This generator does not consult Word.head / deprel, does not match complete
sentences or enumerate adjective lemmas. It recognizes a narrow head + optional
modifier + PP[to]/to-infinitive composition from grammatical token classes.
External resources support a *candidate*, not an asserted selected complement.
Unlike the initial read-only projections, candidates can recover relations
that are missing from the dependency parser's selected tree.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .core import TYPES, Word, classify_attestation, unify

# The constituent patterns are POS-based, not a list of surface words.
_NP_HEAD = frozenset(("NOUN", "PROPN", "PRON", "NUM"))
_NP_PREFIX = frozenset(("DET", "ADJ", "ADV", "NUM", "PART"))
_VERBAL_HEAD = frozenset(("VERB",))
_VERBAL_PREFIX = frozenset(("ADV", "PART"))
_BREAK = frozenset(("PUNCT", "CCONJ", "SCONJ"))


@dataclass(frozen=True)
class AttachmentCandidate:
    kind: str
    head: int
    dependent: int
    marker: int
    relation: str
    lexical_head_lemma: str
    head_features: Mapping[str, Any]
    unsatisfied_valence: Mapping[str, Any]
    external_attestation_count: int
    erg_compatible_types: tuple[str, ...]
    status: str
    rationale: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "head": self.head,
            "dependent": self.dependent,
            "marker": self.marker,
            "relation": self.relation,
            "lexical_head_lemma": self.lexical_head_lemma,
            "head_features": dict(self.head_features),
            "unsatisfied_valence": dict(self.unsatisfied_valence),
            "external_attestation_count": self.external_attestation_count,
            "erg_compatible_types": list(self.erg_compatible_types),
            "status": self.status,
            "rationale": list(self.rationale),
            "selected_complement_proven": False,
        }


def _phrase_head(words: Sequence[Word], start: int) -> tuple[str, int] | None:
    """Only identify a minimal NP or infinitival VP by its grammatical POS.

    A delimiter or unsupported phrase structure terminates the attempt.
    Crucially, dependency links are not inspected here.
    """
    if start >= len(words):
        return None
    i = start
    while i < len(words):
        w = words[i]
        if w.upos in _BREAK:
            return None
        if w.upos in _NP_HEAD:
            return "PP", w.id
        if w.upos in _VERBAL_HEAD:
            # Do not promote a finite verb to an infinitival complement.
            if "VerbForm=Fin" in w.features or "Mood=Ind" in w.features:
                return None
            return "INFINITIVE", w.id
        if w.upos not in _NP_PREFIX | _VERBAL_PREFIX:
            return None
        i += 1
    return None


def _erg_compatible(type_names: Sequence[str], category: str) -> tuple[str, ...]:
    """Coarse category compatibility, not an ERG derivation or a PREP=to proof.

    TDL lexical types often use aj_pp_* for adjective+PP and aj_vp_*
    / aj_cp_* for adjectival clausal complements.  The latter are not
    necessarily infinitives; record them only as weak compatibility.
    """
    prefixes = ("aj_pp_",) if category == "PP" else ("aj_vp_", "aj_cp_")
    return tuple(sorted({name for name in type_names
                         if any(name.startswith(prefix) for prefix in prefixes)}))


def propose_alternative_attachments(
    words: Sequence[Word],
    ud_train_evidence: Mapping[str, Any] | None = None,
    erg_lexemes: Mapping[str, Sequence[str]] | None = None,
) -> tuple[AttachmentCandidate, ...]:
    """Return local adjective attachment alternatives, independent of edges.

    We currently limit the head and the overt 'to' to adjacent tokens (after
    optional degree/other adverb modifiers). That is a declared scope of the
    head-complement schema, not a lexical/sentence-pattern exclusion.
    All unlicensed candidates remain hypotheses; no Stanza edge is rewritten.
    """
    if not words:
        return ()
    candidates: list[AttachmentCandidate] = []
    ud = ud_train_evidence or {}
    erg = erg_lexemes or {}
    for i, adj in enumerate(words):
        if adj.upos != "ADJ":
            continue
        j = i+1
        # A grammatically possible post-adjectival ADV is optional; it does
        # not consume or overwrite the adjective's unsatisfied COMPS feature.
        while j < len(words) and words[j].upos == "ADV":
            j += 1
        if j >= len(words) or words[j].lemma.casefold() != "to":
            continue
        marker = words[j]
        result = _phrase_head(words, j+1)
        if result is None:
            continue
        category, dependent = result
        # This subtype choice uses grammatical syntax, NOT the head lexeme.
        type_name = ("adjective-with-to-pp" if category == "PP"
                     else "adjective-with-to-infinitive")
        kind = ("adjective_to_pp_candidate" if category == "PP"
                else "adjective_to_infinitive_candidate")
        evidence = classify_attestation(adj.lemma, kind, ud)
        erg_types = _erg_compatible(erg.get(adj.lemma.casefold(), ()), category)
        # This is a lexical *candidate*. An attested UD dependency is evidence
        # of compatible surface realization, not proof of argument selection.
        if evidence["attestation_count"]:
            status = "externally_attested_candidate"
        elif erg_types:
            status = "erg_category_compatible_candidate"
        else:
            status = "unlicensed_structural_candidate"
        signature = TYPES.effective(type_name)
        head_features = unify(TYPES.effective("adjective"),
                              {"HEAD":{"pos":"ADJ","is_lexical":True}})
        candidates.append(AttachmentCandidate(
            kind=kind,
            head=adj.id,
            dependent=dependent,
            marker=marker.id,
            relation="obl_or_nmod" if category == "PP" else "xcomp",
            lexical_head_lemma=adj.lemma.casefold(),
            head_features=head_features,
            unsatisfied_valence=signature["VALENCE"],
            external_attestation_count=evidence["attestation_count"],
            erg_compatible_types=erg_types,
            status=status,
            rationale=(
                "typed_head_complement_schema",
                "independent_POS_constituent_recognition",
                "overt_to_marker",
                "HEAD_preserved",
                "valence_not_assumed_saturated",
            ),
        ))
    return tuple(candidates)


def evaluate_alternatives(
    gold: Sequence[Word],
    original: Sequence[Word],
    candidates: Sequence[AttachmentCandidate],
) -> dict[str, Any]:
    """Evaluate proposed edges, including ones not selected by Stanza.

    We use UD gold adjective attachments with marker 'to' as the reference,
    not a broader claim about argumenthood or semantics.
    """
    from .core import grammatical_observations

    def keys(words: Sequence[Word]) -> set[tuple[str, int, int]]:
        return {(o["kind"], o["head_id"], o["dependent_id"])
                for o in grammatical_observations(list(words))
                if o["kind"] in {"adjective_to_pp_candidate",
                                 "adjective_to_infinitive_candidate"}}

    gold_keys = keys(gold)
    original_keys = keys(original)
    proposed_keys = {(c.kind,c.head,c.dependent) for c in candidates}
    attested = {(c.kind,c.head,c.dependent) for c in candidates
                if c.status != "unlicensed_structural_candidate"}
    recovered = (proposed_keys - original_keys) & gold_keys
    false_additions = (proposed_keys - original_keys) - gold_keys
    supported_recovered = (attested - original_keys) & gold_keys
    supported_false = (attested - original_keys) - gold_keys
    return {
        "gold": len(gold_keys),
        "original_correct": len(original_keys & gold_keys),
        "original_predicted": len(original_keys),
        "proposed": len(proposed_keys),
        "proposed_correct": len(proposed_keys & gold_keys),
        "new_correct": len(recovered),
        "new_false": len(false_additions),
        "supported_new_correct": len(supported_recovered),
        "supported_new_false": len(supported_false),
        "gold_missing_in_all_candidates": len(gold_keys - (original_keys | proposed_keys)),
        "gold_recoveries": [list(x) for x in sorted(recovered)],
        "false_additions": [list(x) for x in sorted(false_additions)[:12]],
    }
