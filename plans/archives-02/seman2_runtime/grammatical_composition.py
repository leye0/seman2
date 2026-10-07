"""Composition grammaticale générique de prédications depuis une MRS projetée."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Mapping

from .cognitive_artifacts import CognitiveArtifact, thaw_json
from .contracts import ContractError, canonical_json
from .developmental_core import RoleBinding
from .semantic_admission import (
    EvidenceOccurrence,
    EvidencePolarity,
    SemanticAdmissionLedger,
    SemanticCandidate,
)


@dataclass(frozen=True)
class ComposedPropositionCandidate:
    composition_ref: str
    composition_kind: str
    semantic_candidate: SemanticCandidate
    source_semantic_ref: str
    experience_ref: str
    supporting_predicate_indexes: tuple[int, ...]
    genericity: str
    selected: bool = False


class MRSGrammaticalComposer:
    """Applique des patrons grammaticaux, jamais des fonctions par lexème."""

    def compose(
        self,
        artifact: CognitiveArtifact,
        *,
        target_context_ref: str,
    ) -> tuple[ComposedPropositionCandidate, ...]:
        if artifact.artifact_type != "semantic-structure":
            raise ContractError("composition grammaticale: semantic-structure requis")
        native = thaw_json(artifact.payload_native)
        predicates = tuple(native.get("predicates", ()))
        experience_ref = (
            artifact.observation_refs[0]
            if artifact.observation_refs
            else artifact.artifact_id
        )
        by_arg0: dict[str, list[tuple[int, Mapping[str, object]]]] = {}
        for index, predicate in enumerate(predicates):
            arg0 = predicate.get("arguments", {}).get("ARG0")
            if arg0:
                by_arg0.setdefault(str(arg0), []).append((index, predicate))

        results: list[ComposedPropositionCandidate] = []
        for copula_index, predicate in enumerate(predicates):
            if predicate.get("predicate") != "_be_v_id":
                continue
            arguments = predicate.get("arguments", {})
            subject_variable = arguments.get("ARG1")
            complement_variable = arguments.get("ARG2")
            if not subject_variable or not complement_variable:
                continue
            subject_nominals = _predicates_of_kind(
                by_arg0.get(str(subject_variable), ()), "noun"
            )
            complement_nominals = _predicates_of_kind(
                by_arg0.get(str(complement_variable), ()), "noun"
            )
            complement_adjectives = _predicates_of_kind(
                by_arg0.get(str(complement_variable), ()), "adjective"
            )
            for subject_index, subject in subject_nominals:
                for complement_index, complement in complement_nominals:
                    results.append(
                        _class_candidate(
                            artifact,
                            experience_ref,
                            target_context_ref,
                            subject["predicate"],
                            complement["predicate"],
                            (copula_index, subject_index, complement_index),
                        )
                    )
            for complement_index, complement in complement_adjectives:
                results.append(
                    _property_candidate(
                        artifact,
                        experience_ref,
                        target_context_ref,
                        str(subject_variable),
                        complement["predicate"],
                        (copula_index, complement_index),
                    )
                )

        # Certaines analyses adjectivales portent directement ARG1 sans copule.
        index_variable = str(native.get("mrs_index", ""))
        for adjective_index, predicate in enumerate(predicates):
            if _predicate_kind(str(predicate.get("predicate", ""))) != "adjective":
                continue
            arguments = predicate.get("arguments", {})
            subject_variable = arguments.get("ARG1")
            if not subject_variable or str(arguments.get("ARG0")) != index_variable:
                continue
            results.append(
                _property_candidate(
                    artifact,
                    experience_ref,
                    target_context_ref,
                    str(subject_variable),
                    predicate["predicate"],
                    (adjective_index,),
                )
            )

        deduplicated = {row.composition_ref: row for row in results}
        return tuple(deduplicated[key] for key in sorted(deduplicated))

    def register_evidence(
        self,
        ledger: SemanticAdmissionLedger,
        compositions: Iterable[ComposedPropositionCandidate],
    ) -> None:
        for composition in compositions:
            candidate = composition.semantic_candidate
            ledger.register_candidate(candidate)
            evidence_ref = _stable_ref(
                "composition-evidence",
                {
                    "candidate_ref": candidate.candidate_ref,
                    "experience_ref": composition.experience_ref,
                    "analysis_ref": composition.source_semantic_ref,
                    "composition_ref": composition.composition_ref,
                },
            )
            ledger.observe(
                EvidenceOccurrence(
                    evidence_ref=evidence_ref,
                    candidate_ref=candidate.candidate_ref,
                    experience_ref=composition.experience_ref,
                    analysis_ref=composition.source_semantic_ref,
                    source_ref=composition.source_semantic_ref,
                    polarity=EvidencePolarity.SUPPORT,
                    weight=1.0,
                    evidence_kind="grammar-composition",
                )
            )


def _class_candidate(
    artifact: CognitiveArtifact,
    experience_ref: str,
    target_context_ref: str,
    subject_predicate: str,
    complement_predicate: str,
    predicate_indexes: tuple[int, ...],
) -> ComposedPropositionCandidate:
    bindings = (
        RoleBinding("subject", f"concept-form:external:mrs:{subject_predicate}"),
        RoleBinding("class", f"concept-form:external:mrs:{complement_predicate}"),
    )
    candidate_ref = _stable_ref(
        "semantic-candidate",
        {
            "relation_form_ref": "relation:kind-of",
            "bindings": [
                {"role_ref": row.role_ref, "value_ref": row.value_ref}
                for row in bindings
            ],
            "context_scope_ref": target_context_ref,
        },
    )
    semantic = SemanticCandidate(
        candidate_ref,
        "relation:kind-of",
        bindings,
        target_context_ref,
    )
    composition_ref = _stable_ref(
        "composition",
        {
            "source_semantic_ref": artifact.artifact_id,
            "candidate_ref": candidate_ref,
            "predicate_indexes": predicate_indexes,
        },
    )
    return ComposedPropositionCandidate(
        composition_ref,
        "copular-class-predication",
        semantic,
        artifact.artifact_id,
        experience_ref,
        predicate_indexes,
        "generic-reading-candidate",
    )


def _property_candidate(
    artifact: CognitiveArtifact,
    experience_ref: str,
    target_context_ref: str,
    subject_variable: str,
    property_predicate: str,
    predicate_indexes: tuple[int, ...],
) -> ComposedPropositionCandidate:
    bindings = (
        RoleBinding(
            "bearer", f"identity:{artifact.artifact_id}:{subject_variable}"
        ),
        RoleBinding("property", f"property-form:external:mrs:{property_predicate}"),
    )
    candidate_ref = _stable_ref(
        "semantic-candidate",
        {
            "relation_form_ref": "relation:has-property",
            "bindings": [
                {"role_ref": row.role_ref, "value_ref": row.value_ref}
                for row in bindings
            ],
            "context_scope_ref": target_context_ref,
        },
    )
    semantic = SemanticCandidate(
        candidate_ref,
        "relation:has-property",
        bindings,
        target_context_ref,
    )
    composition_ref = _stable_ref(
        "composition",
        {
            "source_semantic_ref": artifact.artifact_id,
            "candidate_ref": candidate_ref,
            "predicate_indexes": predicate_indexes,
        },
    )
    return ComposedPropositionCandidate(
        composition_ref,
        "property-ascription",
        semantic,
        artifact.artifact_id,
        experience_ref,
        predicate_indexes,
        "particular-reading",
    )


def _predicates_of_kind(
    rows: Iterable[tuple[int, Mapping[str, object]]], kind: str
) -> tuple[tuple[int, Mapping[str, object]], ...]:
    return tuple(
        (index, row)
        for index, row in rows
        if _predicate_kind(str(row.get("predicate", ""))) == kind
    )


def _predicate_kind(predicate: str) -> str:
    if "_n_" in predicate:
        return "noun"
    if "_a_" in predicate:
        return "adjective"
    if "_v_" in predicate:
        return "verb"
    if predicate.endswith("_q") or predicate == "udef_q":
        return "quantifier"
    return "other"


def _stable_ref(prefix: str, content: Mapping[str, object]) -> str:
    digest = hashlib.sha256(canonical_json(content).encode()).hexdigest()
    return f"{prefix}:{digest[:24]}"

