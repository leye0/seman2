"""Composition générique de contributions MRS L1 en candidats internes L2."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import Any

from delphin import predicate
from delphin.codecs import simplemrs

from .cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactStatus,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    CognitiveArtifact,
    thaw_json,
)
from .contracts import ContractError, canonical_json
from .low_level_system import ClosedAnalysisLedger, register_low_level_types


COMPOSER_BUILD = "active-generic-mrs-composer"


@dataclass(frozen=True)
class ClosedCompositionBatch:
    source_ledger_digest: str
    candidate_ids: tuple[str, ...]
    successful_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]
    closed: bool
    batch_digest: str

    def integrity_payload(self) -> dict[str, Any]:
        return {
            "source_ledger_digest": self.source_ledger_digest,
            "candidate_ids": list(self.candidate_ids),
            "successful_candidate_ids": list(self.successful_candidate_ids),
            "rejected_candidate_ids": list(self.rejected_candidate_ids),
            "closed": self.closed,
        }

    def recompute_digest(self) -> str:
        return hashlib.sha256(
            canonical_json(self.integrity_payload()).encode()
        ).hexdigest()

    def validate_integrity(self) -> None:
        if not self.closed:
            raise ContractError("SYS-02: batch L2 non fermé")
        if not self.source_ledger_digest or not self.candidate_ids:
            raise ContractError("SYS-02: batch L2 incomplet")
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ContractError("SYS-02: candidat dupliqué dans le batch")
        successful = set(self.successful_candidate_ids)
        rejected = set(self.rejected_candidate_ids)
        if successful & rejected or successful | rejected != set(self.candidate_ids):
            raise ContractError("SYS-02: partition du batch L2 invalide")
        if tuple(ref for ref in self.candidate_ids if ref in successful) != (
            self.successful_candidate_ids
        ):
            raise ContractError("SYS-02: ordre des succès L2 incohérent")
        if tuple(ref for ref in self.candidate_ids if ref in rejected) != (
            self.rejected_candidate_ids
        ):
            raise ContractError("SYS-02: ordre des rejets L2 incohérent")
        if self.recompute_digest() != self.batch_digest:
            raise ContractError("SYS-02: digest du batch L2 invalide")

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_ledger_digest": self.source_ledger_digest,
            "candidate_ids": list(self.candidate_ids),
            "successful_candidate_ids": list(self.successful_candidate_ids),
            "rejected_candidate_ids": list(self.rejected_candidate_ids),
            "closed": self.closed,
            "batch_digest": self.batch_digest,
        }


def register_composition_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "composed-candidate",
            "seman2/active/L2/composed-candidate",
            2,
            allowed_producers=frozenset({"generic-mrs-composer"}),
            parent_types=frozenset({"analysis-contribution"}),
            required_native_fields=frozenset(
                {
                    "source_analysis_ref",
                    "context",
                    "referents",
                    "events",
                    "identity_candidates",
                    "facet_candidates",
                    "relations",
                    "state_candidates",
                    "proposition",
                    "scope_constraints",
                    "individual_constraints",
                    "composition_trace",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed", "branch_selected"}
            ),
        )
    )


def build_composition_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    register_composition_types(registry)
    registry.freeze()
    return registry


class GenericMRSComposer:
    """Adapte la structure MRS sans règle portant sur un lexème particulier."""

    def __init__(self, arena: ArtifactArena) -> None:
        self.arena = arena
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "formalism": "MRS",
                    "variable_sorts": ["x", "i", "e", "h"],
                    "state_pos": ["a"],
                    "selection": "none",
                }
            ).encode()
        ).hexdigest()

    def compose_ledger(
        self, ledger: ClosedAnalysisLedger
    ) -> tuple[ClosedCompositionBatch, tuple[CognitiveArtifact, ...]]:
        ledger.validate_integrity()
        contributions = tuple(
            self.arena.get(identifier) for identifier in ledger.contribution_ids
        )
        if not contributions or any(
            row.artifact_type != "analysis-contribution" for row in contributions
        ):
            raise ContractError("SYS-02: ledger sans contributions L1 valides")
        observations = tuple(
            self.arena.get(identifier) for identifier in ledger.observation_ids
        )
        if any(row.artifact_type != "observation" for row in observations):
            raise ContractError("SYS-02: ledger sans observations L0 valides")
        if len({row.session_id for row in observations + contributions}) != 1:
            raise ContractError("SYS-02: ledger mélangeant plusieurs sessions")
        if len({row.mode for row in observations + contributions}) != 1:
            raise ContractError("SYS-02: ledger mélangeant plusieurs modes")
        for route in ledger.route_decisions:
            observation_id = route["observation_ref"]
            for contribution_id in route["contribution_refs"]:
                contribution = self.arena.get(contribution_id)
                if contribution.parent_ids != (observation_id,):
                    raise ContractError(
                        "SYS-02: contribution L1 rattachée à la mauvaise observation"
                    )
        candidates = tuple(self.compose(row) for row in contributions)
        successful = tuple(
            row.artifact_id for row in candidates if row.status is ArtifactStatus.SUCCESS
        )
        rejected = tuple(
            row.artifact_id for row in candidates if row.status is not ArtifactStatus.SUCCESS
        )
        payload = {
            "source_ledger_digest": ledger.ledger_digest,
            "candidate_ids": [row.artifact_id for row in candidates],
            "successful_candidate_ids": list(successful),
            "rejected_candidate_ids": list(rejected),
            "closed": True,
        }
        digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        batch = ClosedCompositionBatch(
            ledger.ledger_digest,
            tuple(row.artifact_id for row in candidates),
            successful,
            rejected,
            True,
            digest,
        )
        batch.validate_integrity()
        return batch, candidates

    def compose(self, contribution: CognitiveArtifact) -> CognitiveArtifact:
        started = time.perf_counter()
        if contribution.artifact_type != "analysis-contribution":
            raise ContractError("SYS-02: le compositeur exige une contribution L1")
        native = thaw_json(contribution.payload_native)
        mrs_text = native.get("native_result", {}).get("mrs")
        if contribution.status is ArtifactStatus.FAILURE or not mrs_text:
            return self._failure(contribution, "MRS native absente")
        try:
            mrs = simplemrs.decode(mrs_text)
        except Exception as exc:
            return self._failure(contribution, f"MRS invalide: {exc}")

        context_ref = f"context:analysis:{contribution.artifact_id}"
        observation = self.arena.get(contribution.parent_ids[0])
        observation_surface = thaw_json(observation.payload_native)["surface"]

        def variable_ref(value: str) -> str:
            if value in mrs.variables:
                return f"candidate:{contribution.artifact_id}:variable:{value}"
            if value.startswith("h"):
                return f"candidate:{contribution.artifact_id}:handle:{value}"
            return f"literal:{value}"

        referents = []
        events = []
        for variable, properties in sorted(mrs.variables.items()):
            sort = variable[0]
            item = {
                "candidate_ref": variable_ref(variable),
                "mrs_variable": variable,
                "sort": sort,
                "properties": dict(sorted(properties.items())),
                "context_ref": context_ref,
            }
            if sort == "e":
                events.append(item)
            elif sort in {"x", "i"}:
                referents.append(item)

        relations = []
        states = []
        quantifier_refs = []
        scope_operator_refs = []
        for index, ep in enumerate(mrs.rels):
            relation_ref = f"candidate:{contribution.artifact_id}:relation:{index}"
            try:
                lemma, part_of_speech, sense = predicate.split(ep.predicate)
            except ValueError:
                lemma, part_of_speech, sense = ep.predicate, None, None
            bindings = [
                {
                    "role_ref": role,
                    "source_value": value,
                    "value_ref": variable_ref(value),
                }
                for role, value in sorted(ep.args.items())
            ]
            span = list(ep.lnk.data) if ep.lnk is not None and ep.lnk.data else None
            span_valid = bool(
                span
                and len(span) == 2
                and 0 <= span[0] <= span[1] <= len(observation_surface)
            )
            relation = {
                "relation_ref": relation_ref,
                "predicate": ep.predicate,
                "lemma": lemma,
                "part_of_speech": part_of_speech,
                "sense": sense,
                "label": ep.label,
                "constant": ep.carg,
                "bindings": bindings,
                "span": span,
                "span_valid": span_valid,
                "surface_excerpt": observation_surface[span[0] : span[1]]
                if span_valid
                else None,
                "context_ref": context_ref,
            }
            relations.append(relation)
            if part_of_speech == "q":
                quantifier_refs.append(relation_ref)
            if ep.predicate in {"neg", "possible", "necessary"}:
                scope_operator_refs.append(relation_ref)
            if part_of_speech == "a":
                arguments = dict(ep.args)
                states.append(
                    {
                        "state_candidate_ref": f"candidate:{contribution.artifact_id}:state:{index}",
                        "state_form_ref": f"external:mrs:{ep.predicate}",
                        "bearer_ref": variable_ref(arguments["ARG1"])
                        if "ARG1" in arguments
                        else None,
                        "event_ref": variable_ref(arguments["ARG0"])
                        if "ARG0" in arguments
                        else None,
                        "relation_ref": relation_ref,
                        "context_ref": context_ref,
                    }
                )

        referent_refs = {row["candidate_ref"] for row in referents}
        identity_candidates = []
        facet_candidates = []
        for referent in referents:
            supporting_relations = [
                relation["relation_ref"]
                for relation in relations
                if any(
                    binding["value_ref"] == referent["candidate_ref"]
                    for binding in relation["bindings"]
                )
            ]
            identity_candidates.append(
                {
                    "identity_candidate_ref": (
                        f"candidate:{contribution.artifact_id}:identity:"
                        f"{referent['mrs_variable']}"
                    ),
                    "referent_ref": referent["candidate_ref"],
                    "status": "context-local-unresolved",
                    "supporting_relation_refs": supporting_relations,
                    "context_ref": context_ref,
                }
            )
        for relation in relations:
            arg0 = next(
                (
                    binding["value_ref"]
                    for binding in relation["bindings"]
                    if binding["role_ref"] == "ARG0"
                ),
                None,
            )
            if arg0 in referent_refs:
                facet_candidates.append(
                    {
                        "facet_candidate_ref": (
                            f"candidate:{contribution.artifact_id}:facet:"
                            f"{len(facet_candidates)}"
                        ),
                        "bearer_ref": arg0,
                        "form_ref": f"external:mrs:{relation['predicate']}",
                        "relation_ref": relation["relation_ref"],
                        "context_ref": context_ref,
                    }
                )

        payload: dict[str, Any] = {
            "source_analysis_ref": contribution.artifact_id,
            "context": {
                "context_ref": context_ref,
                "kind": "analysis-candidate",
                "epistemic_status": "hypothesis",
            },
            "referents": referents,
            "events": events,
            "identity_candidates": identity_candidates,
            "facet_candidates": facet_candidates,
            "relations": relations,
            "state_candidates": states,
            "proposition": {
                "top_handle": mrs.top,
                "index_ref": variable_ref(mrs.index) if mrs.index else None,
                "quantifier_relation_refs": quantifier_refs,
                "scope_operator_relation_refs": scope_operator_refs,
                "scope_status": "underspecified"
                if len(quantifier_refs) > 1 and mrs.hcons
                else "constrained",
                "scope_alternatives_committed": 0,
                "asserted": False,
            },
            "scope_constraints": [
                {
                    "high": row.hi,
                    "relation": str(row.relation),
                    "low": row.lo,
                }
                for row in mrs.hcons
            ],
            "individual_constraints": [
                {
                    "left": row.left,
                    "relation": str(row.relation),
                    "right": row.right,
                }
                for row in mrs.icons
            ],
            "composition_trace": [
                {
                    "native_ep_index": index,
                    "relation_ref": relation["relation_ref"],
                    "native_predicate": relation["predicate"],
                    "native_constant": relation["constant"],
                    "native_bindings": relation["bindings"],
                    "native_span": relation["span"],
                    "span_valid": relation["span_valid"],
                }
                for index, relation in enumerate(relations)
            ],
        }
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return self.arena.publish(
            ArtifactProposal(
                artifact_type="composed-candidate",
                producer_id="generic-mrs-composer",
                producer_build=COMPOSER_BUILD,
                configuration_digest=self.configuration_digest,
                mode=contribution.mode,
                session_id=contribution.session_id,
                wave=2,
                parent_ids=(contribution.artifact_id,),
                observation_refs=contribution.observation_refs,
                context_refs=(context_ref,),
                source_anchors=tuple(thaw_json(row) for row in contribution.source_anchors),
                resource_cost={
                    "wall_time_ms": elapsed_ms,
                    "native_relations": len(relations),
                    "referents": len(referents),
                    "events": len(events),
                },
                payload_native=payload,
                payload_projection={
                    "truth_committed": False,
                    "world_update_performed": False,
                    "branch_selected": False,
                },
                status=ArtifactStatus.SUCCESS,
                idempotency_key=f"compose:{contribution.artifact_id}",
            )
        )

    def _failure(self, contribution: CognitiveArtifact, reason: str) -> CognitiveArtifact:
        return self.arena.publish(
            ArtifactProposal(
                artifact_type="composed-candidate",
                producer_id="generic-mrs-composer",
                producer_build=COMPOSER_BUILD,
                configuration_digest=self.configuration_digest,
                mode=contribution.mode,
                session_id=contribution.session_id,
                wave=2,
                parent_ids=(contribution.artifact_id,),
                observation_refs=contribution.observation_refs,
                source_anchors=tuple(thaw_json(row) for row in contribution.source_anchors),
                resource_cost={"source_status": contribution.status.value},
                payload_native={
                    "source_analysis_ref": contribution.artifact_id,
                    "context": {},
                    "referents": [],
                    "events": [],
                    "identity_candidates": [],
                    "facet_candidates": [],
                    "relations": [],
                    "state_candidates": [],
                    "proposition": {"asserted": False},
                    "scope_constraints": [],
                    "individual_constraints": [],
                    "composition_trace": [],
                    "failure_reason": reason,
                },
                payload_projection={
                    "truth_committed": False,
                    "world_update_performed": False,
                    "branch_selected": False,
                },
                status=ArtifactStatus.FAILURE,
                losses=("no-L2-composition",),
                idempotency_key=f"compose-failure:{contribution.artifact_id}",
            )
        )
