"""Adaptation non destructive des sorties formelles vers le nouveau cœur.

Chaque analyse MRS candidate reçoit son propre contexte hypothétique. Les
prédicats et rôles externes sont conservés comme formes attribuées; l'adaptateur
ne résout ni l'identité finale, ni la vérité, ni le sens lexical.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .cognitive_artifacts import CognitiveArtifact, thaw_json
from .contracts import ContractError
from .developmental_core import (
    ContextFrame,
    ContextKind,
    DevelopmentalCore,
    EpistemicState,
    EventOccurrence,
    FormFactor,
    IdentityAnchor,
    Polarity,
    RelationOccurrence,
    RoleBinding,
)


@dataclass(frozen=True)
class AnalysisContribution:
    contribution_id: str
    experience_ref: str
    producer: str
    formalism: str
    source_anchors: tuple[dict, ...]
    projected_factor_refs: tuple[str, ...]
    applicability: str
    losses: tuple[str, ...]
    native_artifact_ref: str


@dataclass(frozen=True)
class AdaptedSemanticBundle:
    semantic_artifact_ref: str
    context_ref: str
    contribution: AnalysisContribution
    identity_refs: tuple[str, ...]
    relation_refs: tuple[str, ...]
    event_refs: tuple[str, ...]
    distributed_form_refs: tuple[str, ...]


def adapt_semantic_artifacts(
    core: DevelopmentalCore,
    artifacts: Iterable[CognitiveArtifact],
    *,
    parent_context_ref: str,
    temporal_index: int,
) -> tuple[AdaptedSemanticBundle, ...]:
    if parent_context_ref not in core.universe.contexts:
        raise ContractError("adaptateur formel: contexte parent absent")
    bundles = [
        adapt_semantic_artifact(
            core,
            artifact,
            parent_context_ref=parent_context_ref,
            temporal_index=temporal_index,
        )
        for artifact in artifacts
    ]
    return tuple(bundles)


def adapt_semantic_artifact(
    core: DevelopmentalCore,
    artifact: CognitiveArtifact,
    *,
    parent_context_ref: str,
    temporal_index: int,
) -> AdaptedSemanticBundle:
    if artifact.artifact_type != "semantic-structure":
        raise ContractError(
            f"adaptateur formel: semantic-structure attendu, reçu {artifact.artifact_type}"
        )
    if parent_context_ref not in core.universe.contexts:
        raise ContractError("adaptateur formel: contexte parent absent")
    if temporal_index < 0:
        raise ContractError("adaptateur formel: index temporel négatif")

    native = thaw_json(artifact.payload_native)
    for required in ("entities", "events", "predicates", "mrs_index"):
        if required not in native:
            raise ContractError(f"adaptateur formel: champ absent {required}")

    context_ref = f"ctx:analysis:{artifact.artifact_id}"
    core.universe.add_context(
        ContextFrame(
            context_id=context_ref,
            kind=ContextKind.HYPOTHETICAL,
            parent_context_ref=parent_context_ref,
            support_refs=(artifact.artifact_id,),
        )
    )

    aliases: dict[str, set[str]] = {}
    for predicate in native["predicates"]:
        constant = predicate.get("constant")
        argument_zero = predicate.get("arguments", {}).get("ARG0")
        if constant and argument_zero:
            aliases.setdefault(argument_zero, set()).add(str(constant))

    variable_refs: dict[str, str] = {}
    identity_refs = []
    for entity in native["entities"]:
        variable = str(entity["id"])
        identity_ref = f"identity:{artifact.artifact_id}:{variable}"
        variable_refs[variable] = identity_ref
        core.universe.add_identity(
            IdentityAnchor(
                identity_id=identity_ref,
                origin_context_ref=context_ref,
                support_refs=(artifact.artifact_id,),
                surface_aliases=tuple(sorted(aliases.get(variable, ()))),
            )
        )
        identity_refs.append(identity_ref)

    for event in native["events"]:
        variable = str(event["id"])
        variable_refs[variable] = f"event-node:{artifact.artifact_id}:{variable}"

    def value_ref(raw: object) -> str:
        value = str(raw)
        return variable_refs.get(value, f"mrs-value:{artifact.artifact_id}:{value}")

    relation_refs = []
    event_refs = []
    form_refs = []
    for index, predicate in enumerate(native["predicates"]):
        relation_ref = f"relation:{artifact.artifact_id}:{index}"
        relation_form_ref = f"external:mrs:{predicate['predicate']}"
        bindings = tuple(
            RoleBinding(
                role_ref=f"external:mrs-role:{role}",
                value_ref=value_ref(target),
            )
            for role, target in sorted(predicate.get("arguments", {}).items())
        )
        if predicate.get("constant"):
            bindings += (
                RoleBinding(
                    role_ref="external:mrs-role:CARG",
                    value_ref=f"surface-constant:{predicate['constant']}",
                ),
            )
        if not bindings:
            bindings = (
                RoleBinding("external:mrs-role:ANCHOR", artifact.artifact_id),
            )
        core.universe.add_relation(
            RelationOccurrence(
                relation_occurrence_id=relation_ref,
                relation_form_ref=relation_form_ref,
                bindings=bindings,
                context_ref=context_ref,
                temporal_index=temporal_index,
                polarity=Polarity.POSITIVE,
                modality="analysis-candidate",
                attribution_ref=None,
                support_refs=(artifact.artifact_id,),
                contradiction_refs=(),
                epistemic_state=EpistemicState.HYPOTHESIS,
            )
        )
        relation_refs.append(relation_ref)

        form_ref = f"form:{relation_ref}"
        factors = [
            FormFactor(
                factor_ref=f"{relation_ref}:predicate",
                value_ref=relation_form_ref,
                context_ref=context_ref,
                role_ref="predicate",
                support_refs=(artifact.artifact_id,),
            )
        ]
        factors.extend(
            FormFactor(
                factor_ref=f"{relation_ref}:binding:{binding_index}",
                value_ref=binding.value_ref,
                context_ref=context_ref,
                role_ref=binding.role_ref,
                position=binding_index,
                support_refs=(artifact.artifact_id,),
            )
            for binding_index, binding in enumerate(bindings)
        )
        core.encode_form(form_ref, factors)
        core.memory.remember(
            relation_ref,
            kind="relation-candidate",
            features=(relation_form_ref, *(f"role:{row.role_ref}" for row in bindings)),
            context_refs=(context_ref,),
            support_refs=(artifact.artifact_id,),
        )
        form_refs.append(form_ref)

        arg0 = predicate.get("arguments", {}).get("ARG0")
        if arg0 == native["mrs_index"] or (
            str(arg0).startswith("e") and str(arg0) == str(native["mrs_index"])
        ):
            event_ref = f"event:{artifact.artifact_id}:{arg0}"
            core.universe.add_event(
                EventOccurrence(
                    event_id=event_ref,
                    event_form_ref=relation_form_ref,
                    bindings=bindings,
                    context_ref=context_ref,
                    temporal_index=temporal_index,
                    support_refs=(artifact.artifact_id, relation_ref),
                    epistemic_state=EpistemicState.HYPOTHESIS,
                )
            )
            event_refs.append(event_ref)

    contribution = AnalysisContribution(
        contribution_id=f"contribution:{artifact.artifact_id}",
        experience_ref=(
            artifact.observation_refs[0]
            if artifact.observation_refs
            else artifact.artifact_id
        ),
        producer=artifact.producer_id,
        formalism="MRS-projection",
        source_anchors=tuple(thaw_json(row) for row in artifact.source_anchors),
        projected_factor_refs=tuple(relation_refs),
        applicability="applicable",
        losses=tuple(artifact.losses),
        native_artifact_ref=artifact.artifact_id,
    )
    return AdaptedSemanticBundle(
        semantic_artifact_ref=artifact.artifact_id,
        context_ref=context_ref,
        contribution=contribution,
        identity_refs=tuple(identity_refs),
        relation_refs=tuple(relation_refs),
        event_refs=tuple(event_refs),
        distributed_form_refs=tuple(form_refs),
    )

