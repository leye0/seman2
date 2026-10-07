"""Factorisation minimale des candidats L2 en branches de situation L3."""

from __future__ import annotations

import hashlib
import time
from typing import Iterable

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
from .formal_composition import register_composition_types
from .low_level_system import register_low_level_types


HYPOTHESIS_BUILD = "active-factorized-hypothesis-manager"


def register_hypothesis_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "situation-branch-set",
            "seman2/active/L3/situation-branch-set",
            3,
            allowed_producers=frozenset({"hypothesis-manager"}),
            parent_types=frozenset({"composed-candidate"}),
            required_native_fields=frozenset(
                {
                    "observation_ref",
                    "candidate_refs",
                    "rejected_candidate_refs",
                    "branches",
                    "selected_ref",
                    "grouping_trace",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed"}
            ),
        )
    )


def build_situation_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    register_composition_types(registry)
    register_hypothesis_types(registry)
    registry.freeze()
    return registry


class HypothesisManager:
    def __init__(self, arena: ArtifactArena, *, maximum_branches: int = 8) -> None:
        if not 1 <= maximum_branches <= 64:
            raise ContractError("SYS-02: maximum_branches invalide")
        self.arena = arena
        self.maximum_branches = maximum_branches
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "maximum_branches": maximum_branches,
                    "selection": "none",
                    "factorization": "one-L2-context-per-branch",
                }
            ).encode()
        ).hexdigest()

    def group(self, candidates: Iterable[CognitiveArtifact]) -> CognitiveArtifact:
        started = time.perf_counter()
        rows = tuple(candidates)
        if not rows or len(rows) > self.maximum_branches:
            raise ContractError("SYS-02: nombre de branches vide ou hors budget")
        if any(row.artifact_type != "composed-candidate" for row in rows):
            raise ContractError("SYS-02: une branche exige des candidats L2")
        if len({row.artifact_id for row in rows}) != len(rows):
            raise ContractError("SYS-02: candidat L2 dupliqué")
        if len({row.session_id for row in rows}) != 1 or len({row.mode for row in rows}) != 1:
            raise ContractError("SYS-02: candidats de sessions ou modes différents")
        observation_refs = {ref for row in rows for ref in row.observation_refs}
        observation_ids = {
            self.arena.get(self.arena.get(row.parent_ids[0]).parent_ids[0]).artifact_id
            for row in rows
        }
        if len(observation_refs) != 1 or len(observation_ids) != 1:
            raise ContractError("SYS-02: candidats de plusieurs observations")
        observation_ref = next(iter(observation_refs))
        observation_id = next(iter(observation_ids))
        active_rows = tuple(row for row in rows if row.status is ArtifactStatus.SUCCESS)
        rejected_rows = tuple(row for row in rows if row.status is not ArtifactStatus.SUCCESS)
        payloads = [thaw_json(row.payload_native) for row in active_rows]
        branches = [
            {
                "branch_ref": f"branch:{row.artifact_id}",
                "candidate_ref": row.artifact_id,
                "context_ref": payload["context"]["context_ref"],
                "epistemic_status": "hypothesis",
                "constraint_status": "not-yet-evaluated",
                "selected": False,
                "factor_counts": {
                    "referents": len(payload["referents"]),
                    "events": len(payload["events"]),
                    "relations": len(payload["relations"]),
                    "state_candidates": len(payload["state_candidates"]),
                },
            }
            for row, payload in zip(active_rows, payloads, strict=True)
        ]
        rejected = [
            {
                "candidate_ref": row.artifact_id,
                "status": row.status.value,
                "reason": thaw_json(row.payload_native).get(
                    "failure_reason", "candidate not composable"
                ),
            }
            for row in rejected_rows
        ]
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        output_status = (
            ArtifactStatus.FAILURE
            if not active_rows
            else ArtifactStatus.PARTIAL
            if rejected_rows
            else ArtifactStatus.SUCCESS
        )
        return self.arena.publish(
            ArtifactProposal(
                artifact_type="situation-branch-set",
                producer_id="hypothesis-manager",
                producer_build=HYPOTHESIS_BUILD,
                configuration_digest=self.configuration_digest,
                mode=rows[0].mode,
                session_id=rows[0].session_id,
                wave=3,
                parent_ids=tuple(row.artifact_id for row in rows),
                observation_refs=(observation_ref,),
                context_refs=tuple(
                    payload["context"]["context_ref"] for payload in payloads
                ),
                source_anchors=tuple(thaw_json(row) for row in rows[0].source_anchors),
                resource_cost={
                    "wall_time_ms": elapsed_ms,
                    "candidate_count": len(rows),
                    "active_branch_count": len(active_rows),
                    "rejected_candidate_count": len(rejected_rows),
                    "branch_limit": self.maximum_branches,
                },
                payload_native={
                    "observation_ref": observation_id,
                    "candidate_refs": [row.artifact_id for row in rows],
                    "rejected_candidate_refs": [
                        row.artifact_id for row in rejected_rows
                    ],
                    "branches": branches,
                    "selected_ref": None,
                    "grouping_trace": [
                        {
                            "candidate_ref": row.artifact_id,
                            "effect": "branch-created"
                            if row.status is ArtifactStatus.SUCCESS
                            else "rejected-preserved",
                            "reason_if_rejected": next(
                                (
                                    item["reason"]
                                    for item in rejected
                                    if item["candidate_ref"] == row.artifact_id
                                ),
                                None,
                            ),
                        }
                        for row in rows
                    ],
                },
                payload_projection={
                    "truth_committed": False,
                    "world_update_performed": False,
                },
                status=output_status,
                losses=("no-admissible-L2-branch",) if not active_rows else (),
                idempotency_key=f"branch-set:{observation_ref}",
            )
        )
