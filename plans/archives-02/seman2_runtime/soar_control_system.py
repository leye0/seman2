"""Contrôle exécutif Soar borné sur le stock cognitif réel L3/L4."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Iterable

from .cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactStatus,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    CognitiveArtifact,
    thaw_json,
)
from .cognitive_memory import CognitiveMemory, MemoryPolicy, RetrievalRequest
from .contracts import ContractError, canonical_json
from .discourse_identity_system import register_discourse_identity_types
from .formal_composition import register_composition_types
from .hypothesis_system import register_hypothesis_types
from .knowledge_system import register_knowledge_types
from .low_level_system import register_low_level_types
from .temporal_system import register_temporal_types


CONTROL_BUILD = "active-real-soar-bounded-control"


def register_soar_control_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "control-goal",
            "seman2/active/L4/control-goal",
            4,
            allowed_producers=frozenset({"control-goal-builder"}),
            parent_types=frozenset({"identity-beam"}),
            required_native_fields=frozenset(
                {"goal_ref", "mention_ref", "resolution_status", "candidate_beam", "retrieval_features"}
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "retrieval-result",
            "seman2/active/L4/retrieval-result",
            4,
            allowed_producers=frozenset({"bounded-cognitive-retrieval"}),
            parent_types=frozenset(
                {"control-goal", "episode-memory", "temporal-memory", "discourse-memory"}
            ),
            required_native_fields=frozenset(
                {"goal_ref", "depth", "request", "hits", "indexed_counts", "work_units"}
            ),
            required_projection_fields=frozenset({"raw_source_accessed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "soar-control-decision",
            "seman2/active/L6/soar-control-decision",
            6,
            allowed_producers=frozenset({"soar-executive"}),
            parent_types=frozenset({"control-goal", "retrieval-result", "identity-beam"}),
            required_native_fields=frozenset(
                {
                    "goal_ref",
                    "initial_operator",
                    "final_operator",
                    "selected_candidate_ref",
                    "compared_candidate_refs",
                    "retrieval_result_ref",
                    "soar_trace",
                    "working_memory_projection",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "persistent_store_copied_to_soar"}
            ),
        )
    )


def build_soar_control_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    register_composition_types(registry)
    register_hypothesis_types(registry)
    register_knowledge_types(registry)
    register_temporal_types(registry)
    register_discourse_identity_types(registry)
    register_soar_control_types(registry)
    registry.freeze()
    return registry


class ControlGoalBuilder:
    def __init__(self, arena: ArtifactArena, *, beam_bound: int = 2) -> None:
        if not 2 <= beam_bound <= 8:
            raise ContractError("SYS-07: beam_bound hors [2,8]")
        self.arena = arena
        self.beam_bound = beam_bound
        self._cache: dict[str, CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json({"beam_bound": beam_bound, "source": "ambiguous-pronoun"}).encode()
        ).hexdigest()

    def build(self, identity_beam: CognitiveArtifact) -> CognitiveArtifact:
        if identity_beam.artifact_type != "identity-beam":
            raise ContractError("SYS-07: le but exige un vrai identity-beam L3")
        if identity_beam.artifact_id in self._cache:
            return self._cache[identity_beam.artifact_id]
        payload = thaw_json(identity_beam.payload_native)
        mentions = {row["mention_ref"]: row for row in payload["mentions"]}
        alternatives = [
            row
            for row in payload["decisions"]
            if row["status"] == "ambiguous"
            and row["reference_kind"] == "pronoun"
            and len([c for c in row["candidates"] if not c["creates_new_identity"]]) >= 2
        ]
        if not alternatives:
            raise ContractError("SYS-07: aucune impasse référentielle réelle dans le beam")
        decision = alternatives[-1]
        mention = mentions[decision["mention_ref"]]
        existing = [c for c in decision["candidates"] if not c["creates_new_identity"]]
        existing.sort(key=lambda row: (-row.get("rank_score", row["score"]), row["candidate_ref"]))
        active = existing[: self.beam_bound]
        features = [
            *(f"role:{role}" for role in mention["role_refs"] if role.startswith("grammatical-role:")),
            *(f"feature:{key}={value}" for key, value in mention["grammatical_features"]),
        ]
        required = []
        if dict(mention["grammatical_features"]).get("GEND") == "n":
            required.append("reference-class:nominal")
        goal_ref = "goal:resolve-reference:" + hashlib.sha256(
            canonical_json([identity_beam.artifact_id, mention["mention_ref"]]).encode()
        ).hexdigest()[:24]
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="control-goal",
                producer_id="control-goal-builder",
                producer_build=CONTROL_BUILD,
                configuration_digest=self.configuration_digest,
                mode=identity_beam.mode,
                session_id=identity_beam.session_id,
                wave=identity_beam.wave,
                parent_ids=(identity_beam.artifact_id,),
                observation_refs=identity_beam.observation_refs,
                context_refs=(decision["context_ref"],),
                source_anchors=tuple(thaw_json(row) for row in identity_beam.source_anchors),
                resource_cost={"beam_bound": self.beam_bound, "available_candidates": len(existing)},
                payload_native={
                    "goal_ref": goal_ref,
                    "mention_ref": mention["mention_ref"],
                    "resolution_status": decision["status"],
                    "candidate_beam": [
                        {
                            "rank": index,
                            "candidate_ref": row["candidate_ref"],
                            "identity_ref": row["identity_ref"],
                            "score": row.get("rank_score", row["score"]),
                        }
                        for index, row in enumerate(active, 1)
                    ],
                    "inactive_candidate_refs": [row["candidate_ref"] for row in existing[self.beam_bound :]],
                    "retrieval_features": {"anchor": features, "required": required},
                },
                payload_projection={"truth_committed": False},
                status=ArtifactStatus.PARTIAL,
                idempotency_key=f"control-goal:{identity_beam.artifact_id}",
            )
        )
        self._cache[identity_beam.artifact_id] = artifact
        return artifact


class BoundedCognitiveRetrieval:
    def __init__(self, arena: ArtifactArena, *, maximum_results: int = 2) -> None:
        if not 1 <= maximum_results <= 8:
            raise ContractError("SYS-07: maximum_results hors [1,8]")
        self.arena = arena
        self.maximum_results = maximum_results
        self._cache: dict[tuple[str, int, tuple[str, ...]], CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json({"maximum_results": maximum_results, "raw_source_access": False}).encode()
        ).hexdigest()

    def retrieve(
        self,
        goal: CognitiveArtifact,
        *,
        episode_memories: Iterable[CognitiveArtifact],
        temporal_memory: CognitiveArtifact,
        discourse_memory: CognitiveArtifact,
        depth: int,
    ) -> CognitiveArtifact:
        episodes = tuple(episode_memories)
        if goal.artifact_type != "control-goal" or depth < 1:
            raise ContractError("SYS-07: but L4 et profondeur positive requis")
        if not episodes or any(row.artifact_type != "episode-memory" for row in episodes):
            raise ContractError("SYS-07: épisodes L4 réels requis")
        if temporal_memory.artifact_type != "temporal-memory" or discourse_memory.artifact_type != "discourse-memory":
            raise ContractError("SYS-07: mémoires temporelle et discursive L4 requises")
        parents = (goal.artifact_id,) + tuple(row.artifact_id for row in episodes) + (
            temporal_memory.artifact_id,
            discourse_memory.artifact_id,
        )
        key = (goal.artifact_id, depth, parents)
        if key in self._cache:
            return self._cache[key]
        started = time.perf_counter()
        memory = CognitiveMemory(
            MemoryPolicy(focal_capacity=self.maximum_results, peripheral_capacity=64)
        )
        for episode in episodes:
            payload = thaw_json(episode.payload_native)
            item = payload["memory_item"]
            memory.remember(
                episode.artifact_id,
                kind="episode",
                features=item["features"],
                context_refs=episode.context_refs,
                support_refs=(episode.artifact_id,),
                activation=0.5,
                distinctiveness=0.5,
                utility=0.25,
            )
        temporal_payload = thaw_json(temporal_memory.payload_native)
        for network in temporal_payload["networks"]:
            memory.remember(
                network["network_ref"],
                kind="temporal-network",
                features=tuple(
                    sorted({f"event:{frame['event_form_ref']}" for frame in network["frames"]})
                ) or ("temporal-network:empty",),
                context_refs=temporal_memory.context_refs,
                support_refs=(temporal_memory.artifact_id,),
                activation=0.4,
                distinctiveness=0.4,
                utility=0.2,
            )
        discourse_payload = thaw_json(discourse_memory.payload_native)
        mention_observations: dict[str, str] = {}
        for parent_ref in discourse_memory.parent_ids:
            parent = self.arena.get(parent_ref)
            if parent.artifact_type != "identity-beam":
                continue
            for mention in thaw_json(parent.payload_native)["mentions"]:
                mention_observations[mention["mention_ref"]] = mention["observation_ref"]
        episodes_by_observation = {
            ref: episode
            for episode in episodes
            for ref in episode.observation_refs
        }
        temporal_networks_by_observation: dict[str, list[dict[str, Any]]] = {}
        for network in temporal_payload["networks"]:
            analysis = self.arena.get(network["source_analysis_ref"])
            for observation_ref in analysis.observation_refs:
                temporal_networks_by_observation.setdefault(observation_ref, []).append(network)
        latest = max(row["last_temporal_index"] for row in discourse_payload["identity_profiles"])
        for profile in discourse_payload["identity_profiles"]:
            kinds = set(profile["reference_kind_evidence"])
            features = {
                *(f"alias:{value.casefold()}" for value in profile["surface_aliases"]),
                *(f"role:{value}" for value in profile["role_refs"]),
                *(f"feature:{key}={value}" for key, value in profile["grammatical_features"]),
                *(f"reference-kind:{value}" for value in kinds),
                *(
                    f"descriptor:{value}"
                    for values in profile["descriptor_evidence_by_context"].values()
                    for value in values
                ),
            }
            if kinds & {"definite", "indefinite", "nominal"}:
                features.add("reference-class:nominal")
            if "proper" in kinds:
                features.add("reference-class:proper")
            profile_observations = {
                mention_observations[ref]
                for ref in profile["mention_refs"]
                if ref in mention_observations
            }
            supporting_episodes = {
                episodes_by_observation[ref].artifact_id
                for ref in profile_observations
                if ref in episodes_by_observation
            }
            supporting_networks = [
                network
                for ref in profile_observations
                for network in temporal_networks_by_observation.get(ref, [])
            ]
            features.update(
                f"event:{frame['event_form_ref']}"
                for network in supporting_networks
                for frame in network["frames"]
            )
            distance = max(0, latest - profile["last_temporal_index"])
            activation = min(
                1.0,
                max(0.2, 0.75 - 0.15 * distance)
                + 0.03 * len(supporting_episodes)
                + 0.01 * len(supporting_networks),
            )
            utility = min(
                1.0,
                0.15
                + 0.05 * len(profile["mention_refs"])
                + 0.02 * len(supporting_networks),
            )
            memory.remember(
                profile["identity_ref"],
                kind="identity-profile",
                features=features,
                context_refs=profile["context_refs"],
                support_refs=(
                    discourse_memory.artifact_id,
                    temporal_memory.artifact_id,
                    *sorted(supporting_episodes),
                    *profile["mention_refs"],
                ),
                activation=activation,
                distinctiveness=0.6,
                utility=utility,
            )
        goal_payload = thaw_json(goal.payload_native)
        request = RetrievalRequest(
            goal_ref=goal_payload["goal_ref"],
            anchor_features=tuple(goal_payload["retrieval_features"]["anchor"]),
            required_features=tuple(goal_payload["retrieval_features"]["required"]),
            context_refs=goal.context_refs,
            requested_kinds=("identity-profile",),
            maximum_results=self.maximum_results,
        )
        hits = memory.retrieve(request)
        if not hits:
            raise ContractError("SYS-07: approfondissement sans résultat cognitif")
        anchors = {
            canonical_json(thaw_json(anchor)): thaw_json(anchor)
            for parent in parents
            for anchor in self.arena.get(parent).source_anchors
        }
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="retrieval-result",
                producer_id="bounded-cognitive-retrieval",
                producer_build=CONTROL_BUILD,
                configuration_digest=self.configuration_digest,
                mode=goal.mode,
                session_id=goal.session_id,
                wave=max(self.arena.get(parent).wave for parent in parents),
                parent_ids=parents,
                observation_refs=tuple(sorted({ref for parent in parents for ref in self.arena.get(parent).observation_refs})),
                context_refs=goal.context_refs,
                source_anchors=tuple(anchors[value] for value in sorted(anchors)),
                resource_cost={
                    "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
                    "indexed_items": len(memory.as_dict()["items"]),
                    "returned_hits": len(hits),
                },
                payload_native={
                    "goal_ref": goal_payload["goal_ref"],
                    "depth": depth,
                    "request": {
                        "anchor_features": list(request.anchor_features),
                        "required_features": list(request.required_features),
                        "requested_kinds": list(request.requested_kinds),
                        "maximum_results": request.maximum_results,
                    },
                    "hits": [
                        {
                            "rank": index,
                            "content_ref": hit.content_ref,
                            "score": hit.score,
                            "tier": hit.tier.value,
                            "matched_features": list(hit.matched_features),
                            "support_refs": list(memory.get(hit.content_ref).support_refs),
                            "influence_factors": {
                                "episode_support_count": len(
                                    [
                                        ref
                                        for ref in memory.get(hit.content_ref).support_refs
                                        if ref in {episode.artifact_id for episode in episodes}
                                    ]
                                ),
                                "temporal_memory_support": temporal_memory.artifact_id
                                in memory.get(hit.content_ref).support_refs,
                                "discourse_memory_support": discourse_memory.artifact_id
                                in memory.get(hit.content_ref).support_refs,
                                "activation": memory.get(hit.content_ref).activation,
                                "utility": memory.get(hit.content_ref).utility,
                            },
                            "explanation": hit.explanation,
                        }
                        for index, hit in enumerate(hits, 1)
                    ],
                    "indexed_counts": {
                        "episodes": len(episodes),
                        "temporal_networks": len(temporal_payload["networks"]),
                        "identity_profiles": len(discourse_payload["identity_profiles"]),
                    },
                    "work_units": len(memory.as_dict()["items"]),
                },
                payload_projection={"raw_source_accessed": False},
                idempotency_key=f"retrieval:{goal.artifact_id}:depth:{depth}",
            )
        )
        self._cache[key] = artifact
        return artifact


class SoarExecutive:
    def __init__(
        self,
        arena: ArtifactArena,
        *,
        project_root: Path,
        beam_bound: int = 2,
        memory_limit_mib: int = 2048,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.arena = arena
        self.project_root = Path(project_root)
        self.beam_bound = beam_bound
        self.memory_limit_mib = memory_limit_mib
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {"beam_bound": beam_bound, "memory_limit_mib": memory_limit_mib, "protocol": "two-cycle-SML"}
            ).encode()
        ).hexdigest()

    def decide(
        self,
        goal: CognitiveArtifact,
        retrieval_service: BoundedCognitiveRetrieval,
        *,
        identity_beam: CognitiveArtifact,
        episode_memories: Iterable[CognitiveArtifact],
        temporal_memory: CognitiveArtifact,
        discourse_memory: CognitiveArtifact,
    ) -> tuple[CognitiveArtifact, CognitiveArtifact]:
        if goal.artifact_type != "control-goal" or identity_beam.artifact_id not in goal.parent_ids:
            raise ContractError("SYS-07: but et beam réel incompatibles")
        if goal.artifact_id in self._cache:
            decision = self._cache[goal.artifact_id]
            retrieval = self.arena.get(thaw_json(decision.payload_native)["retrieval_result_ref"])
            return retrieval, decision
        payload = thaw_json(goal.payload_native)
        started = time.perf_counter()
        common = {
            "goal_ref": payload["goal_ref"],
            "resolution_status": payload["resolution_status"],
            "beam_bound": self.beam_bound,
            "active_candidates": payload["candidate_beam"],
            "memory_limit_mib": self.memory_limit_mib,
        }
        request = self._run_cycle({**common, "phase": "initial"})
        if request.get("action") != "request-retrieval" or request.get("next_depth") != 1:
            raise ContractError("SYS-07: Soar n'a pas demandé l'approfondissement attendu")
        retrieval = retrieval_service.retrieve(
            goal,
            episode_memories=episode_memories,
            temporal_memory=temporal_memory,
            discourse_memory=discourse_memory,
            depth=1,
        )
        retrieval_payload = thaw_json(retrieval.payload_native)
        final = self._run_cycle(
            {
                **common,
                "phase": "retrieved",
                "retrieval": {
                "result_ref": retrieval.artifact_id,
                "depth": retrieval_payload["depth"],
                "hits": retrieval_payload["hits"],
                },
            }
        )
        active_refs = [row["candidate_ref"] for row in payload["candidate_beam"]]
        inactive_refs = payload["inactive_candidate_refs"]
        wm = final["working_memory"]
        if any(ref not in wm for ref in active_refs) or any(ref in wm for ref in inactive_refs):
            raise ContractError("SYS-07: projection de working memory non bornée")
        if set(final["compared_candidate_refs"]) != set(active_refs):
            raise ContractError("SYS-07: décision Soar sans tous les candidats projetés")
        parents = (goal.artifact_id, retrieval.artifact_id, identity_beam.artifact_id)
        anchors = {
            canonical_json(thaw_json(anchor)): thaw_json(anchor)
            for parent in parents
            for anchor in self.arena.get(parent).source_anchors
        }
        decision = self.arena.publish(
            ArtifactProposal(
                artifact_type="soar-control-decision",
                producer_id="soar-executive",
                producer_build=CONTROL_BUILD,
                configuration_digest=self.configuration_digest,
                mode=goal.mode,
                session_id=goal.session_id,
                wave=max(self.arena.get(parent).wave for parent in parents),
                parent_ids=parents,
                observation_refs=goal.observation_refs,
                context_refs=goal.context_refs,
                source_anchors=tuple(anchors[key] for key in sorted(anchors)),
                resource_cost={
                    "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
                    "projected_candidates": len(active_refs),
                    "projected_hits": len(thaw_json(retrieval.payload_native)["hits"]),
                    "memory_limit_mib": self.memory_limit_mib,
                },
                payload_native={
                    "goal_ref": payload["goal_ref"],
                    "initial_operator": request,
                    "final_operator": final["action"],
                    "selected_candidate_ref": final["selected_candidate_ref"],
                    "compared_candidate_refs": final["compared_candidate_refs"],
                    "retrieval_result_ref": retrieval.artifact_id,
                    "soar_trace": final,
                    "working_memory_projection": {
                        "active_candidate_refs": active_refs,
                        "inactive_candidate_refs": inactive_refs,
                        "retrieval_hit_refs": [row["content_ref"] for row in thaw_json(retrieval.payload_native)["hits"]],
                        "beam_bound": self.beam_bound,
                        "working_memory_sha256": final["working_memory_sha256"],
                    },
                },
                payload_projection={
                    "truth_committed": False,
                    "persistent_store_copied_to_soar": False,
                },
                idempotency_key=f"soar-decision:{goal.artifact_id}",
            )
        )
        self._cache[goal.artifact_id] = decision
        return retrieval, decision

    def _run_cycle(self, request: dict[str, Any]) -> dict[str, Any]:
        worker = self.project_root / "seman2_runtime/workers/soar_goal_worker.py"
        command = [str(self.project_root / ".venv/bin/python"), str(worker)]
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                env=os.environ.copy(),
                input=json.dumps(request),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContractError("SYS-07: timeout du worker Soar") from exc
        if completed.returncode != 0:
            raise ContractError(
                f"SYS-07: worker Soar en échec: {completed.stderr.strip()}"
            )
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ContractError("SYS-07: sortie Soar non JSON") from exc
