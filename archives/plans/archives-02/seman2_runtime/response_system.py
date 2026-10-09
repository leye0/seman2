"""Autobiographical response planning over real lower-layer cognitive stock."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable

from .cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    CognitiveArtifact,
    thaw_json,
)
from .contracts import ContractError, canonical_json
from .dialogue_system import register_dialogue_types
from .discourse_identity_system import register_discourse_identity_types
from .formal_composition import register_composition_types
from .hypothesis_system import register_hypothesis_types
from .knowledge_system import register_knowledge_types
from .low_level_system import register_low_level_types, sha256_file
from .recursive_concept_system import register_recursive_concept_types
from .soar_control_system import register_soar_control_types
from .temporal_system import register_temporal_types
from .transformation_learning import register_transformation_types


RESPONSE_BUILD = "active-autobiographical-response-system"
_PUNCTUATION = re.compile(r"^[\s.,!?;:'\"“”‘’]+|[\s.,!?;:'\"“”‘’]+$")


def register_response_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "internal-memory-retrieval",
            "seman2/active/L5/internal-memory-retrieval",
            5,
            allowed_producers=frozenset({"autobiographical-retriever"}),
            parent_types=frozenset(
                {
                    "dialogue-turn-content", "dialogue-state", "episode-memory",
                    "identity-beam", "temporal-memory", "discourse-memory",
                }
            ),
            required_native_fields=frozenset(
                {
                    "question_ref", "query_frame", "epistemic_status",
                    "answer_candidates", "support_paths", "memory_scope_refs",
                    "qualification",
                }
            ),
            required_projection_fields=frozenset(
                {"raw_source_accessed", "external_source_consulted", "truth_committed"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "response-control-goal",
            "seman2/active/L6/response-control-goal",
            6,
            allowed_producers=frozenset({"response-controller"}),
            parent_types=frozenset(
                {"internal-memory-retrieval", "dialogue-state", "discourse-memory"}
            ),
            required_native_fields=frozenset(
                {"goal_ref", "retrieval_ref", "epistemic_status", "operator_beam"}
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "soar-response-decision",
            "seman2/active/L6/soar-response-decision",
            6,
            allowed_producers=frozenset({"response-controller"}),
            parent_types=frozenset({"response-control-goal"}),
            required_native_fields=frozenset(
                {
                    "goal_ref", "selected_operator_ref", "compared_operator_refs",
                    "soar_trace",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "persistent_store_copied_to_soar"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "communicative-plan",
            "seman2/active/L6/communicative-plan",
            6,
            allowed_producers=frozenset({"response-controller"}),
            parent_types=frozenset(
                {"internal-memory-retrieval", "dialogue-state", "soar-response-decision"}
            ),
            required_native_fields=frozenset(
                {
                    "question_ref", "intent", "epistemic_status", "qualification",
                    "content", "evidence_refs", "explanation_path",
                    "selected_operator_ref",
                }
            ),
            required_projection_fields=frozenset(
                {"surface_text_present", "external_source_consulted", "truth_committed"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "realized-turn",
            "seman2/active/L7/realized-turn",
            7,
            allowed_producers=frozenset({"simplenlg-realizer"}),
            parent_types=frozenset({"communicative-plan"}),
            required_native_fields=frozenset(
                {
                    "plan_ref", "surface", "surface_sha256", "backend",
                    "backend_sha256", "covered_plan_fields", "added_content",
                }
            ),
            required_projection_fields=frozenset(
                {"content_selected", "truth_committed"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "reingested-experience",
            "seman2/active/L0/reingested-experience",
            0,
            allowed_producers=frozenset({"generated-turn-gateway"}),
            feedback_parent_types=frozenset({"realized-turn"}),
            required_native_fields=frozenset(
                {
                    "experience_ref", "source_ref", "source_kind", "sequence_index",
                    "source_sha256", "dialogue_ref", "speaker_ref", "turn_index",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "reingested-observation",
            "seman2/active/L0/reingested-observation",
            0,
            allowed_producers=frozenset({"generated-turn-gateway"}),
            parent_types=frozenset({"reingested-experience"}),
            required_native_fields=frozenset(
                {"experience_ref", "surface", "span_start", "span_end", "span_unit", "surface_sha256"}
            ),
        )
    )


def build_response_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    register_composition_types(registry)
    register_hypothesis_types(registry)
    register_knowledge_types(registry)
    register_transformation_types(registry)
    register_temporal_types(registry)
    register_discourse_identity_types(registry)
    register_soar_control_types(registry)
    register_recursive_concept_types(registry)
    register_dialogue_types(registry)
    register_response_types(registry)
    registry.freeze()
    return registry


def _bindings(relation: dict[str, Any]) -> dict[str, str]:
    return {row["role_ref"]: row["source_value"] for row in relation["bindings"]}


def _clean_surface(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _PUNCTUATION.sub("", value)
    return cleaned or None


def _nominal_form(
    relations: list[dict[str, Any]],
    referents: list[dict[str, Any]],
    variable: str,
) -> dict[str, str | None]:
    nouns = [
        row for row in relations
        if row["part_of_speech"] == "n" and _bindings(row).get("ARG0") == variable
    ]
    if not nouns:
        raise ContractError(f"SYS-10: aucun nom MRS pour {variable}")
    noun = sorted(nouns, key=lambda row: row["relation_ref"])[0]
    noun_surface = _clean_surface(noun["surface_excerpt"]) or noun["lemma"]
    determiners = [
        row for row in relations
        if row["part_of_speech"] == "q" and _bindings(row).get("ARG0") == variable
    ]
    determiner = None
    for row in determiners:
        surface = _clean_surface(row["surface_excerpt"])
        if surface and surface.lower() not in {noun_surface.lower(), "where"}:
            determiner = surface.lower()
            break
    phrase = f"{determiner} {noun_surface}" if determiner else noun_surface
    referent = next(
        (row for row in referents if row["mrs_variable"] == variable), None
    )
    number = "pl" if referent and referent["properties"].get("NUM") == "pl" else "sg"
    return {
        "predicate": noun["predicate"],
        "phrase": phrase,
        "head": noun["lemma"],
        "specifier": determiner,
        "number": number,
    }


class AutobiographicalRetriever:
    """Find location answers in accessible L4 episodes via their L2 ancestry."""

    def __init__(self, arena: ArtifactArena, *, maximum_memories: int = 32) -> None:
        if not 1 <= maximum_memories <= 256:
            raise ContractError("SYS-10: maximum_memories hors budget")
        self.arena = arena
        self.maximum_memories = maximum_memories
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "query": "MRS-loc_nonsp-event-or-entity-frame",
                    "match": "predicate-and-argument-role-identity",
                    "memory_input": "accessible-L4-episodes-only",
                    "maximum_memories": maximum_memories,
                }
            ).encode()
        ).hexdigest()
        self._cache: dict[tuple[str, tuple[str, ...]], CognitiveArtifact] = {}

    def retrieve(
        self,
        content: CognitiveArtifact,
        state: CognitiveArtifact,
        *,
        episode_memories: Iterable[CognitiveArtifact],
        identity_beam: CognitiveArtifact,
        temporal_memory: CognitiveArtifact,
        discourse_memory: CognitiveArtifact,
    ) -> CognitiveArtifact:
        memories = tuple(episode_memories)
        if not memories or len(memories) > self.maximum_memories:
            raise ContractError("SYS-10: portée mémoire vide ou hors budget")
        if any(row.artifact_type != "episode-memory" for row in memories):
            raise ContractError("SYS-10: retrieval exige des épisodes L4")
        if content.artifact_type != "dialogue-turn-content" or state.artifact_type != "dialogue-state":
            raise ContractError("SYS-10: question comprise et état dialogique requis")
        if identity_beam.artifact_type != "identity-beam":
            raise ContractError("SYS-10: beam d'identité réel requis")
        if temporal_memory.artifact_type != "temporal-memory" or discourse_memory.artifact_type != "discourse-memory":
            raise ContractError("SYS-10: mémoires temporelle et discursive réelles requises")
        if content.parent_ids[0] not in {row.artifact_id for row in self.arena.ancestry(state.artifact_id)}:
            raise ContractError("SYS-10: contenu et gameboard incompatibles")
        if len({row.session_id for row in memories + (content, state, identity_beam, temporal_memory, discourse_memory)}) != 1:
            raise ContractError("SYS-10: mélange de biographies")
        key = (content.artifact_id, tuple(row.artifact_id for row in memories))
        if key in self._cache:
            return self._cache[key]
        query_candidates = self._active_candidates(content.parent_ids[0])
        query_frames = [self._query_frame(row) for row in query_candidates]
        query_frames = [row for row in query_frames if row is not None]
        if not query_frames:
            raise ContractError("SYS-10: question locative non dérivable du stock L2")
        query_frame = sorted(query_frames, key=canonical_json)[0]

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        support_paths: list[dict[str, Any]] = []
        for memory in memories:
            for candidate in self._memory_candidates(memory):
                for answer in self._match_location(query_frame, candidate):
                    answer_key = (answer["preposition"], answer["object_phrase"].lower())
                    item = grouped.setdefault(
                        answer_key,
                        {
                            "preposition": answer["preposition"],
                            "object_predicate": answer["object_predicate"],
                            "object_phrase": answer["object_phrase"],
                            "object_form": answer["object_form"],
                            "support_episode_refs": set(),
                            "support_candidate_refs": set(),
                        },
                    )
                    item["support_episode_refs"].add(memory.artifact_id)
                    item["support_candidate_refs"].add(candidate.artifact_id)
                    support_paths.append(
                        {
                            "episode_ref": memory.artifact_id,
                            "situation_ref": memory.parent_ids[0],
                            "candidate_ref": candidate.artifact_id,
                            "matched_event_predicate": query_frame["event_predicate"],
                            "matched_subject_predicate": query_frame["subject_predicate"],
                            "location_relation_ref": answer["location_relation_ref"],
                            "answer_predicate": answer["object_predicate"],
                        }
                    )
        candidates = []
        for (preposition, object_phrase), item in sorted(grouped.items()):
            candidates.append(
                {
                    "answer_ref": "answer:" + hashlib.sha256(
                        canonical_json([preposition, object_phrase]).encode()
                    ).hexdigest()[:24],
                    "preposition": item["preposition"],
                    "object_predicate": item["object_predicate"],
                    "object_phrase": item["object_phrase"],
                    "object_form": item["object_form"],
                    "support_episode_refs": sorted(item["support_episode_refs"]),
                    "support_candidate_refs": sorted(item["support_candidate_refs"]),
                    "confidence": 1.0,
                }
            )
        if not candidates:
            status, qualification = "unknown", "no-accessible-internal-path"
        elif len(candidates) == 1:
            status, qualification = "supported", "single-structurally-matched-location"
        else:
            status, qualification = "ambiguous", "multiple-incompatible-accessible-locations"
        parents = (
            content.artifact_id, state.artifact_id, identity_beam.artifact_id,
            temporal_memory.artifact_id, discourse_memory.artifact_id,
            *(row.artifact_id for row in memories),
        )
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="internal-memory-retrieval",
                producer_id="autobiographical-retriever",
                producer_build=RESPONSE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=content.mode,
                session_id=content.session_id,
                wave=max(self.arena.get(ref).wave for ref in parents),
                parent_ids=parents,
                observation_refs=content.observation_refs,
                context_refs=content.context_refs,
                source_anchors=tuple(thaw_json(row) for row in content.source_anchors),
                resource_cost={"memories_examined": len(memories), "answer_bound": 8},
                payload_native={
                    "question_ref": thaw_json(content.payload_native)["turn_ref"],
                    "query_frame": query_frame,
                    "epistemic_status": status,
                    "answer_candidates": candidates,
                    "support_paths": sorted(support_paths, key=canonical_json),
                    "memory_scope_refs": [row.artifact_id for row in memories],
                    "qualification": qualification,
                },
                payload_projection={
                    "raw_source_accessed": False,
                    "external_source_consulted": False,
                    "truth_committed": False,
                },
                idempotency_key="memory-retrieval:" + hashlib.sha256(canonical_json(key).encode()).hexdigest(),
            )
        )
        self._cache[key] = artifact
        return artifact

    def _active_candidates(self, situation_ref: str) -> tuple[CognitiveArtifact, ...]:
        situation = self.arena.get(situation_ref)
        if situation.artifact_type != "situation-branch-set":
            raise ContractError("SYS-10: contenu sans situation L3")
        return tuple(
            self.arena.get(row["candidate_ref"])
            for row in thaw_json(situation.payload_native)["branches"]
        )

    def _memory_candidates(self, memory: CognitiveArtifact) -> tuple[CognitiveArtifact, ...]:
        situation = self.arena.get(memory.parent_ids[0])
        if situation.artifact_type != "situation-branch-set":
            raise ContractError("SYS-10: épisode sans situation L3")
        return tuple(
            self.arena.get(row["candidate_ref"])
            for row in thaw_json(situation.payload_native)["branches"]
        )

    @staticmethod
    def _query_frame(candidate: CognitiveArtifact) -> dict[str, Any] | None:
        candidate_payload = thaw_json(candidate.payload_native)
        relations = candidate_payload["relations"]
        location = next((row for row in relations if row["predicate"] == "loc_nonsp"), None)
        if location is None:
            return None
        target = _bindings(location).get("ARG1")
        if target is None:
            return None
        event = next(
            (row for row in relations if row["part_of_speech"] == "v" and _bindings(row).get("ARG0") == target),
            None,
        )
        subject = _bindings(event).get("ARG1") if event else target
        if subject is None:
            return None
        try:
            subject_form = _nominal_form(
                relations, candidate_payload["referents"], subject
            )
        except ContractError:
            return None
        return {
            "question_candidate_ref": candidate.artifact_id,
            "location_relation_ref": location["relation_ref"],
            "event_predicate": event["predicate"] if event else None,
            "event_lemma": event["lemma"] if event else "be",
            "subject_predicate": subject_form["predicate"],
            "subject_phrase": subject_form["phrase"],
            "subject_form": subject_form,
        }

    @staticmethod
    def _match_location(query: dict[str, Any], candidate: CognitiveArtifact) -> tuple[dict[str, Any], ...]:
        candidate_payload = thaw_json(candidate.payload_native)
        relations = candidate_payload["relations"]
        matches = []
        for location in relations:
            loc_bindings = _bindings(location)
            if location["part_of_speech"] != "p" or "ARG1" not in loc_bindings or "ARG2" not in loc_bindings:
                continue
            target = loc_bindings["ARG1"]
            if query["event_predicate"] is None:
                subject = target
            else:
                event = next(
                    (
                        row for row in relations
                        if row["predicate"] == query["event_predicate"]
                        and _bindings(row).get("ARG0") == target
                    ),
                    None,
                )
                if event is None:
                    continue
                subject = _bindings(event).get("ARG1")
            if subject is None:
                continue
            try:
                subject_form = _nominal_form(
                    relations, candidate_payload["referents"], subject
                )
                object_form = _nominal_form(
                    relations, candidate_payload["referents"], loc_bindings["ARG2"]
                )
            except ContractError:
                continue
            if subject_form["predicate"] != query["subject_predicate"]:
                continue
            matches.append(
                {
                    "location_relation_ref": location["relation_ref"],
                    "preposition": location["lemma"],
                    "object_predicate": object_form["predicate"],
                    "object_phrase": object_form["phrase"],
                    "object_form": object_form,
                }
            )
        return tuple(matches)


class ResponseController:
    def __init__(
        self,
        arena: ArtifactArena,
        *,
        project_root: Path,
        memory_limit_mib: int = 2_048,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.arena = arena
        self.project_root = Path(project_root)
        self.memory_limit_mib = memory_limit_mib
        self.timeout_seconds = timeout_seconds
        self.configuration_digest = hashlib.sha256(
            canonical_json({"beam_bound": 2, "policy": "epistemic-status-compatible"}).encode()
        ).hexdigest()
        self._cache: dict[str, tuple[CognitiveArtifact, CognitiveArtifact, CognitiveArtifact]] = {}

    def plan(
        self,
        retrieval: CognitiveArtifact,
        state: CognitiveArtifact,
        discourse_memory: CognitiveArtifact,
    ) -> tuple[CognitiveArtifact, CognitiveArtifact, CognitiveArtifact]:
        if retrieval.artifact_type != "internal-memory-retrieval":
            raise ContractError("SYS-10: planification exige un retrieval interne")
        if state.artifact_type != "dialogue-state" or discourse_memory.artifact_type != "discourse-memory":
            raise ContractError("SYS-10: planification exige les états L4 réels")
        if retrieval.artifact_id in self._cache:
            return self._cache[retrieval.artifact_id]
        payload = thaw_json(retrieval.payload_native)
        status = payload["epistemic_status"]
        selected_by_status = {
            "supported": "operator:answer-supported",
            "unknown": "operator:acknowledge-ignorance",
            "ambiguous": "operator:request-clarification",
        }
        if status not in selected_by_status:
            raise ContractError(f"SYS-10: statut épistémique non géré {status}")
        selected = selected_by_status[status]
        foil = {
            "supported": "operator:acknowledge-ignorance",
            "unknown": "operator:fabricate-answer",
            "ambiguous": "operator:answer-without-disambiguation",
        }[status]
        operator_beam = [
            {"rank": 1, "operator_ref": selected, "score": 1.0, "compatible": True},
            {"rank": 2, "operator_ref": foil, "score": 0.0, "compatible": False},
        ]
        goal_ref = "goal:response:" + hashlib.sha256(retrieval.artifact_id.encode()).hexdigest()[:24]
        goal = self.arena.publish(
            ArtifactProposal(
                artifact_type="response-control-goal",
                producer_id="response-controller",
                producer_build=RESPONSE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=retrieval.mode,
                session_id=retrieval.session_id,
                wave=max(retrieval.wave, state.wave, discourse_memory.wave),
                parent_ids=(retrieval.artifact_id, state.artifact_id, discourse_memory.artifact_id),
                observation_refs=retrieval.observation_refs,
                context_refs=retrieval.context_refs,
                source_anchors=tuple(thaw_json(row) for row in retrieval.source_anchors),
                resource_cost={"beam_bound": 2},
                payload_native={
                    "goal_ref": goal_ref,
                    "retrieval_ref": retrieval.artifact_id,
                    "epistemic_status": status,
                    "operator_beam": operator_beam,
                },
                payload_projection={"truth_committed": False},
                idempotency_key=f"response-goal:{retrieval.artifact_id}",
            )
        )
        trace = self._run_soar(
            {
                "goal_ref": goal_ref,
                "retrieval_ref": retrieval.artifact_id,
                "epistemic_status": status,
                "operator_beam": operator_beam,
                "memory_limit_mib": self.memory_limit_mib,
            }
        )
        compared = {row["operator_ref"] for row in operator_beam}
        if set(trace["compared_operator_refs"]) != compared or trace["selected_operator_ref"] != selected:
            raise ContractError("SYS-10: décision Soar incompatible avec le beam")
        decision = self.arena.publish(
            ArtifactProposal(
                artifact_type="soar-response-decision",
                producer_id="response-controller",
                producer_build=RESPONSE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=retrieval.mode,
                session_id=retrieval.session_id,
                wave=goal.wave,
                parent_ids=(goal.artifact_id,),
                observation_refs=retrieval.observation_refs,
                context_refs=retrieval.context_refs,
                source_anchors=tuple(thaw_json(row) for row in retrieval.source_anchors),
                resource_cost={"cycles": 1, "memory_limit_mib": self.memory_limit_mib},
                payload_native={
                    "goal_ref": goal_ref,
                    "selected_operator_ref": trace["selected_operator_ref"],
                    "compared_operator_refs": trace["compared_operator_refs"],
                    "soar_trace": trace,
                },
                payload_projection={
                    "truth_committed": False,
                    "persistent_store_copied_to_soar": False,
                },
                idempotency_key=f"soar-response:{goal_ref}",
            )
        )
        content = self._plan_content(payload)
        evidence = sorted(
            {ref for row in payload["answer_candidates"] for ref in row["support_episode_refs"]}
        )
        plan = self.arena.publish(
            ArtifactProposal(
                artifact_type="communicative-plan",
                producer_id="response-controller",
                producer_build=RESPONSE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=retrieval.mode,
                session_id=retrieval.session_id,
                wave=max(retrieval.wave, state.wave, decision.wave),
                parent_ids=(retrieval.artifact_id, state.artifact_id, decision.artifact_id),
                observation_refs=retrieval.observation_refs,
                context_refs=retrieval.context_refs,
                source_anchors=tuple(thaw_json(row) for row in retrieval.source_anchors),
                resource_cost={"answer_candidates": len(payload["answer_candidates"])},
                payload_native={
                    "question_ref": payload["question_ref"],
                    "intent": content["intent"],
                    "epistemic_status": status,
                    "qualification": payload["qualification"],
                    "content": content,
                    "evidence_refs": evidence,
                    "explanation_path": [retrieval.artifact_id, *evidence, decision.artifact_id],
                    "selected_operator_ref": selected,
                },
                payload_projection={
                    "surface_text_present": False,
                    "external_source_consulted": False,
                    "truth_committed": False,
                },
                idempotency_key=f"communicative-plan:{retrieval.artifact_id}",
            )
        )
        result = (goal, decision, plan)
        self._cache[retrieval.artifact_id] = result
        return result

    @staticmethod
    def _plan_content(payload: dict[str, Any]) -> dict[str, Any]:
        query = payload["query_frame"]
        candidates = payload["answer_candidates"]
        status = payload["epistemic_status"]
        if status == "supported":
            answer = candidates[0]
            return {
                "intent": "answer-location",
                "subject": query["subject_form"],
                "verb": query["event_lemma"],
                "preposition": answer["preposition"],
                "object": answer["object_form"],
                "answer_ref": answer["answer_ref"],
            }
        if status == "ambiguous":
            if len(candidates) != 2:
                raise ContractError("SYS-10: clarification bornée à deux alternatives")
            return {
                "intent": "request-location-clarification",
                "subject": query["subject_form"],
                "copula": "be",
                "coordinator": "or",
                "options": [
                    {"preposition": row["preposition"], "object": row["object_form"]}
                    for row in candidates
                ],
                "answer_refs": [row["answer_ref"] for row in candidates],
            }
        return {
            "intent": "acknowledge-ignorance",
            "subject": "I",
            "verb": "know",
            "negated": True,
            "answer_refs": [],
        }

    def _run_soar(self, request: dict[str, Any]) -> dict[str, Any]:
        worker = self.project_root / "seman2_runtime/workers/soar_response_worker.py"
        try:
            completed = subprocess.run(
                [str(self.project_root / ".venv/bin/python"), str(worker)],
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
            raise ContractError("SYS-10: timeout du worker Soar") from exc
        if completed.returncode:
            raise ContractError(f"SYS-10: worker Soar en échec: {completed.stderr.strip()}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ContractError("SYS-10: sortie Soar non JSON") from exc


class SimpleNLGRealizer:
    def __init__(self, arena: ArtifactArena, *, project_root: Path, timeout_seconds: float = 30.0) -> None:
        self.arena = arena
        self.project_root = Path(project_root)
        self.timeout_seconds = timeout_seconds
        self.jar = self.project_root / ".local/opt/simplenlg/SimpleNLG-4.5.0.jar"
        self.source = self.project_root / "seman2_runtime/workers/Seman2SimpleNLGRealizer.java"
        if not self.jar.is_file() or not self.source.is_file():
            raise ContractError("SYS-10: SimpleNLG ou son adaptateur absent")
        self.backend_sha256 = sha256_file(self.jar)
        self.configuration_digest = hashlib.sha256(
            canonical_json({"jar_sha256": self.backend_sha256, "adapter_sha256": sha256_file(self.source)}).encode()
        ).hexdigest()
        self._temporary = tempfile.TemporaryDirectory(prefix="seman2-sys10-nlg-")
        compiled = subprocess.run(
            ["javac", "--release", "17", "-cp", str(self.jar), "-d", self._temporary.name, str(self.source)],
            cwd=self.project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout_seconds,
            check=False,
        )
        if compiled.returncode:
            self._temporary.cleanup()
            raise ContractError(f"SYS-10: compilation SimpleNLG impossible: {compiled.stderr.strip()}")
        self._cache: dict[str, CognitiveArtifact] = {}

    def realize(self, plan: CognitiveArtifact) -> CognitiveArtifact:
        if plan.artifact_type != "communicative-plan":
            raise ContractError("SYS-10: SimpleNLG exige un plan L6")
        if plan.artifact_id in self._cache:
            return self._cache[plan.artifact_id]
        payload = thaw_json(plan.payload_native)
        content = payload["content"]
        intent = payload["intent"]
        if intent == "answer-location":
            subject = content["subject"]
            obj = content["object"]
            arguments = [
                intent,
                subject["head"], subject["specifier"] or "-", subject["number"],
                content["verb"], content["preposition"],
                obj["head"], obj["specifier"] or "-", obj["number"],
            ]
            covered = ["intent", "subject", "verb", "preposition", "object"]
        elif intent == "acknowledge-ignorance":
            arguments = [intent, content["subject"], content["verb"]]
            covered = ["intent", "subject", "verb", "negated"]
        elif intent == "request-location-clarification":
            if content.get("coordinator") != "or" or len(content["options"]) != 2:
                raise ContractError("SYS-10: plan de clarification incomplet")
            subject = content["subject"]
            arguments = [
                intent,
                subject["head"], subject["specifier"] or "-", subject["number"],
                content["copula"], content["coordinator"],
            ]
            for option in content["options"]:
                obj = option["object"]
                arguments.extend(
                    [option["preposition"], obj["head"], obj["specifier"] or "-", obj["number"]]
                )
            covered = ["intent", "subject", "copula", "coordinator", "options"]
        else:
            raise ContractError(f"SYS-10: intention non réalisable {intent}")
        completed = subprocess.run(
            ["java", "-cp", f"{self._temporary.name}:{self.jar}", "Seman2SimpleNLGRealizer", *arguments],
            cwd=self.project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode:
            raise ContractError(f"SYS-10: SimpleNLG en échec: {completed.stderr.strip()}")
        surface = completed.stdout.strip()
        if not surface or "\n" in surface:
            raise ContractError("SYS-10: surface SimpleNLG invalide")
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="realized-turn",
                producer_id="simplenlg-realizer",
                producer_build="SimpleNLG-4.5.0",
                configuration_digest=self.configuration_digest,
                mode=plan.mode,
                session_id=plan.session_id,
                wave=plan.wave,
                parent_ids=(plan.artifact_id,),
                observation_refs=plan.observation_refs,
                context_refs=plan.context_refs,
                source_anchors=tuple(thaw_json(row) for row in plan.source_anchors),
                resource_cost={"processes": 1, "timeout_seconds": self.timeout_seconds},
                payload_native={
                    "plan_ref": plan.artifact_id,
                    "surface": surface,
                    "surface_sha256": hashlib.sha256(surface.encode()).hexdigest(),
                    "backend": "SimpleNLG-4.5.0",
                    "backend_sha256": self.backend_sha256,
                    "covered_plan_fields": covered,
                    "added_content": [],
                },
                payload_projection={"content_selected": False, "truth_committed": False},
                idempotency_key=f"realized-turn:{plan.artifact_id}",
            )
        )
        self._cache[plan.artifact_id] = artifact
        return artifact


class GeneratedTurnGateway:
    def __init__(self, arena: ArtifactArena) -> None:
        self.arena = arena
        self.configuration_digest = hashlib.sha256(b"generated-turn-feedback-L7-to-L0").hexdigest()
        self._cache: dict[str, tuple[CognitiveArtifact, CognitiveArtifact]] = {}

    def reingest(
        self,
        realized: CognitiveArtifact,
        *,
        dialogue_ref: str,
        turn_index: int,
        sequence_index: int,
    ) -> tuple[CognitiveArtifact, CognitiveArtifact]:
        if realized.artifact_type != "realized-turn" or realized.mode != "chatbot":
            raise ContractError("SYS-10: seul un tour L7 chatbot peut être réingéré")
        if realized.artifact_id in self._cache:
            return self._cache[realized.artifact_id]
        payload = thaw_json(realized.payload_native)
        surface = payload["surface"]
        digest = payload["surface_sha256"]
        experience_ref = f"generated:{realized.artifact_id}"
        experience = self.arena.publish(
            ArtifactProposal(
                artifact_type="reingested-experience",
                producer_id="generated-turn-gateway",
                producer_build=RESPONSE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=realized.mode,
                session_id=realized.session_id,
                wave=realized.wave + 1,
                parent_ids=(realized.artifact_id,),
                observation_refs=(experience_ref,),
                context_refs=(dialogue_ref,),
                resource_cost={"surface_bytes": len(surface.encode())},
                payload_native={
                    "experience_ref": experience_ref,
                    "source_ref": realized.artifact_id,
                    "source_kind": "generated-dialogue-turn",
                    "sequence_index": sequence_index,
                    "source_sha256": digest,
                    "dialogue_ref": dialogue_ref,
                    "speaker_ref": "speaker:system",
                    "turn_index": turn_index,
                },
                payload_projection={"content_interpreted": False, "truth_committed": False},
                idempotency_key=f"reingested-experience:{realized.artifact_id}",
            )
        )
        observation = self.arena.publish(
            ArtifactProposal(
                artifact_type="reingested-observation",
                producer_id="generated-turn-gateway",
                producer_build=RESPONSE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=realized.mode,
                session_id=realized.session_id,
                wave=experience.wave,
                parent_ids=(experience.artifact_id,),
                observation_refs=(experience_ref,),
                context_refs=(dialogue_ref,),
                resource_cost={"surface_bytes": len(surface.encode())},
                payload_native={
                    "experience_ref": experience_ref,
                    "surface": surface,
                    "span_start": 0,
                    "span_end": len(surface.encode()),
                    "span_unit": "utf8-byte-in-generated-turn",
                    "surface_sha256": digest,
                },
                payload_projection={"surface_preserved": True, "truth_committed": False},
                idempotency_key=f"reingested-observation:{realized.artifact_id}",
            )
        )
        self._cache[realized.artifact_id] = (experience, observation)
        return experience, observation
