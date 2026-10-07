"""Persistent multi-turn dialogue state over real composed cognitive stock."""

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
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    CognitiveArtifact,
    thaw_json,
)
from .contracts import ContractError, canonical_json
from .recursive_concept_system import (
    build_recursive_concept_registry,
    register_recursive_concept_types,
)
from .discourse_identity_system import register_discourse_identity_types
from .formal_composition import register_composition_types
from .hypothesis_system import register_hypothesis_types
from .knowledge_system import register_knowledge_types
from .low_level_system import register_low_level_types
from .soar_control_system import register_soar_control_types
from .temporal_system import register_temporal_types
from .transformation_learning import register_transformation_types


DIALOGUE_BUILD = "active-grounded-dialogue-gameboard"


def register_dialogue_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "dialogue-turn-content",
            "seman2/active/L3/dialogue-turn-content",
            3,
            allowed_producers=frozenset({"dialogue-interpreter"}),
            parent_types=frozenset({"situation-branch-set", "identity-beam"}),
            feedback_parent_types=frozenset(
                {"learned-transformation", "recursive-learned-concept"}
            ),
            required_native_fields=frozenset(
                {
                    "dialogue_ref", "turn_ref", "turn_index", "speaker_ref",
                    "act_candidates", "semantic_factors", "question_type",
                    "referent_ranking", "concept_context",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "raw_surface_accessed"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "dialogue-control-goal",
            "seman2/active/L4/dialogue-control-goal",
            4,
            allowed_producers=frozenset({"dialogue-gameboard"}),
            parent_types=frozenset(
                {
                    "dialogue-turn-content", "dialogue-state", "episode-memory",
                    "identity-beam", "temporal-memory", "discourse-memory",
                }
            ),
            required_native_fields=frozenset(
                {"goal_ref", "turn_ref", "move_kind", "active_qud_status", "operator_beam"}
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "soar-dialogue-decision",
            "seman2/active/L6/soar-dialogue-decision",
            6,
            allowed_producers=frozenset({"dialogue-gameboard"}),
            parent_types=frozenset({"dialogue-control-goal"}),
            required_native_fields=frozenset(
                {
                    "goal_ref", "turn_ref", "selected_operator_ref",
                    "compared_operator_refs", "soar_trace",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "persistent_store_copied_to_soar"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "dialogue-state",
            "seman2/active/L4/dialogue-state",
            4,
            allowed_producers=frozenset({"dialogue-gameboard"}),
            parent_types=frozenset(
                {
                    "dialogue-turn-content", "dialogue-state", "episode-memory",
                    "identity-beam", "temporal-memory", "discourse-memory",
                }
            ),
            feedback_parent_types=frozenset({"soar-dialogue-decision"}),
            required_native_fields=frozenset(
                {
                    "dialogue_ref", "turn_index", "active_qud_ref", "quds",
                    "proposals", "groundings", "repairs", "history",
                    "selected_operator_ref",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed"}
            ),
        )
    )


def build_dialogue_registry() -> ArtifactTypeRegistry:
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
    registry.freeze()
    return registry


class DialogueTurnInterpreter:
    """Derive pragmatic evidence only from L0 metadata and real L2/L3 stock."""

    def __init__(self, arena: ArtifactArena, *, maximum_referents: int = 8) -> None:
        if not 2 <= maximum_referents <= 32:
            raise ContractError("SYS-09: maximum_referents hors [2,32]")
        self.arena = arena
        self.maximum_referents = maximum_referents
        self._cache: dict[tuple[str, str, tuple[str, ...]], CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "maximum_referents": maximum_referents,
                    "question_evidence": "MRS-event-SF=ques",
                    "fragment_evidence": "ERG-unknown-plus-content",
                    "grounding_evidence": "MRS-affirmative-relation",
                    "repair_evidence": "MRS-negative-discourse-relation",
                }
            ).encode()
        ).hexdigest()

    def interpret(
        self,
        branch_set: CognitiveArtifact,
        identity_beam: CognitiveArtifact,
        *,
        learned_context: Iterable[CognitiveArtifact] = (),
    ) -> CognitiveArtifact:
        learned = tuple(sorted(learned_context, key=lambda row: row.artifact_id))
        key = (branch_set.artifact_id, identity_beam.artifact_id, tuple(row.artifact_id for row in learned))
        if key in self._cache:
            return self._cache[key]
        if branch_set.artifact_type != "situation-branch-set":
            raise ContractError("SYS-09: contenu exige une situation L3")
        if identity_beam.artifact_type != "identity-beam" or branch_set.artifact_id not in identity_beam.parent_ids:
            raise ContractError("SYS-09: beam d'identité incompatible")
        if any(row.artifact_type not in {"learned-transformation", "recursive-learned-concept"} for row in learned):
            raise ContractError("SYS-09: contexte conceptuel non L5")
        experience = self._experience(branch_set)
        experience_payload = thaw_json(experience.payload_native)
        required_metadata = {"dialogue_ref", "turn_index", "speaker_ref", "channel"}
        if required_metadata - set(experience_payload) or experience_payload["channel"] != "dialogue":
            raise ContractError("SYS-09: métadonnées dialogiques L0 absentes")
        started = time.perf_counter()
        candidates = tuple(
            self.arena.get(row["candidate_ref"])
            for row in thaw_json(branch_set.payload_native)["branches"]
        )
        evidence: dict[str, set[str]] = {
            "question": set(), "fragment": set(), "grounding": set(),
            "correction": set(), "assertion": set(),
        }
        semantic_factors: set[str] = set()
        question_types: set[str] = set()
        for candidate in candidates:
            payload = thaw_json(candidate.payload_native)
            predicates = {row["predicate"] for row in payload["relations"]}
            is_question = any(
                event["properties"].get("SF") == "ques" for event in payload["events"]
            )
            is_fragment = "unknown" in predicates and not is_question
            is_grounding = "_yes_a_1" in predicates
            is_correction = "_no_a_1" in predicates
            if is_question:
                evidence["question"].add(candidate.artifact_id)
                question_types.add(
                    "wh" if predicates & {"which_q", "_which_q", "loc_nonsp"} else "polar"
                )
            if is_fragment:
                evidence["fragment"].add(candidate.artifact_id)
            if is_grounding:
                evidence["grounding"].add(candidate.artifact_id)
            if is_correction:
                evidence["correction"].add(candidate.artifact_id)
            if not (is_question or is_fragment or is_grounding or is_correction):
                evidence["assertion"].add(candidate.artifact_id)
            for relation in payload["relations"]:
                prefix = "event-form" if relation["part_of_speech"] == "v" else "relation-form"
                semantic_factors.add(f"{prefix}:external:mrs:{relation['predicate']}")
        act_candidates = [
            {"act": name, "evidence_refs": sorted(refs), "parse_support": len(refs)}
            for name, refs in evidence.items()
            if refs
        ]
        if not act_candidates:
            raise ContractError("SYS-09: aucune hypothèse pragmatique depuis L2")
        beam_payload = thaw_json(identity_beam.payload_native)
        ranked: dict[str, dict[str, Any]] = {}
        for decision in beam_payload["decisions"]:
            for candidate in decision["candidates"]:
                if candidate["creates_new_identity"]:
                    continue
                score = candidate.get("rank_score", candidate["score"])
                current = ranked.get(candidate["identity_ref"])
                row = {
                    "identity_ref": candidate["identity_ref"],
                    "score": score,
                    "mention_ref": decision["mention_ref"],
                    "support_signals": candidate["support_signals"],
                }
                if current is None or score > current["score"]:
                    ranked[candidate["identity_ref"]] = row
        referent_ranking = sorted(
            ranked.values(), key=lambda row: (-row["score"], row["identity_ref"])
        )[: self.maximum_referents]
        concept_context = []
        for concept in learned:
            pattern = set(thaw_json(concept.payload_native)["structural_pattern"])
            matched = sorted(pattern & semantic_factors)
            concept_context.append(
                {
                    "concept_ref": concept.artifact_id,
                    "matched_factors": matched,
                    "applicable": bool(matched),
                    "reason_if_ignored": None if matched else "no-structural-factor-overlap",
                }
            )
        parents = (branch_set.artifact_id, identity_beam.artifact_id) + tuple(
            row.artifact_id for row in learned
        )
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="dialogue-turn-content",
                producer_id="dialogue-interpreter",
                producer_build=DIALOGUE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=branch_set.mode,
                session_id=branch_set.session_id,
                wave=max(self.arena.get(ref).wave + (1 if self.arena.get(ref).artifact_type in {"learned-transformation", "recursive-learned-concept"} else 0) for ref in parents),
                parent_ids=parents,
                observation_refs=branch_set.observation_refs,
                context_refs=(experience_payload["dialogue_ref"],),
                source_anchors=tuple(thaw_json(row) for row in branch_set.source_anchors),
                resource_cost={
                    "parse_candidates": len(candidates),
                    "referent_candidates": len(referent_ranking),
                    "concepts_examined": len(learned),
                },
                payload_native={
                    "dialogue_ref": experience_payload["dialogue_ref"],
                    "turn_ref": experience_payload["experience_ref"],
                    "turn_index": experience_payload["turn_index"],
                    "speaker_ref": experience_payload["speaker_ref"],
                    "act_candidates": act_candidates,
                    "semantic_factors": sorted(semantic_factors),
                    "question_type": (
                        next(iter(question_types)) if len(question_types) == 1
                        else "ambiguous" if question_types else None
                    ),
                    "referent_ranking": referent_ranking,
                    "concept_context": concept_context,
                },
                payload_projection={"truth_committed": False, "raw_surface_accessed": False},
                idempotency_key="dialogue-content:" + hashlib.sha256(canonical_json(key).encode()).hexdigest(),
            )
        )
        self._cache[key] = artifact
        return artifact

    def _experience(self, artifact: CognitiveArtifact) -> CognitiveArtifact:
        rows = [
            row for row in self.arena.ancestry(artifact.artifact_id)
            if row.artifact_type == "experience-occurrence"
        ]
        if len(rows) != 1:
            raise ContractError("SYS-09: expérience L0 dialogique introuvable")
        return rows[0]


class DialogueGameboard:
    """Append-only QUD, proposal, grounding and repair state controlled by Soar."""

    def __init__(
        self,
        arena: ArtifactArena,
        *,
        project_root: Path,
        beam_bound: int = 2,
        memory_limit_mib: int = 2_048,
        timeout_seconds: float = 30.0,
    ) -> None:
        if beam_bound != 2:
            raise ContractError("SYS-09: la preuve SML exige deux opérateurs")
        self.arena = arena
        self.project_root = Path(project_root)
        self.beam_bound = beam_bound
        self.memory_limit_mib = memory_limit_mib
        self.timeout_seconds = timeout_seconds
        self._cache: dict[tuple[str | None, str], tuple[CognitiveArtifact, CognitiveArtifact, CognitiveArtifact]] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "beam_bound": beam_bound,
                    "memory_limit_mib": memory_limit_mib,
                    "state": "append-only-QUD-proposal-grounding-repair",
                }
            ).encode()
        ).hexdigest()

    def advance(
        self,
        content: CognitiveArtifact,
        *,
        episode_memory: CognitiveArtifact,
        identity_beam: CognitiveArtifact,
        temporal_memory: CognitiveArtifact,
        discourse_memory: CognitiveArtifact,
        previous_state: CognitiveArtifact | None,
    ) -> tuple[CognitiveArtifact, CognitiveArtifact, CognitiveArtifact]:
        if content.artifact_type != "dialogue-turn-content":
            raise ContractError("SYS-09: contenu L3 réel requis")
        if episode_memory.artifact_type != "episode-memory" or identity_beam.artifact_type != "identity-beam":
            raise ContractError("SYS-09: épisode L4 et beam L3 réels requis")
        if temporal_memory.artifact_type != "temporal-memory" or discourse_memory.artifact_type != "discourse-memory":
            raise ContractError("SYS-09: mémoires temporelle et discursive L4 réelles requises")
        if previous_state is not None and previous_state.artifact_type != "dialogue-state":
            raise ContractError("SYS-09: état précédent invalide")
        key = (previous_state.artifact_id if previous_state else None, content.artifact_id)
        if key in self._cache:
            return self._cache[key]
        payload = thaw_json(content.payload_native)
        previous = self._empty_state(payload["dialogue_ref"]) if previous_state is None else thaw_json(previous_state.payload_native)
        if previous["dialogue_ref"] != payload["dialogue_ref"]:
            raise ContractError("SYS-09: mélange de dialogues")
        if previous_state is not None and payload["turn_index"] != previous["turn_index"] + 1:
            raise ContractError("SYS-09: ordre de tours non contigu")
        move_kind = self._move_kind(payload, previous)
        operator_beam = self._operator_beam(move_kind, previous, payload)
        goal_ref = "goal:dialogue:" + hashlib.sha256(
            canonical_json([key, move_kind, operator_beam]).encode()
        ).hexdigest()[:24]
        goal_parents = (
            content.artifact_id, episode_memory.artifact_id, identity_beam.artifact_id,
            temporal_memory.artifact_id, discourse_memory.artifact_id,
        ) + (
            (previous_state.artifact_id,) if previous_state else ()
        )
        goal = self.arena.publish(
            ArtifactProposal(
                artifact_type="dialogue-control-goal",
                producer_id="dialogue-gameboard",
                producer_build=DIALOGUE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=content.mode,
                session_id=content.session_id,
                wave=max(self.arena.get(ref).wave for ref in goal_parents),
                parent_ids=goal_parents,
                observation_refs=content.observation_refs,
                context_refs=content.context_refs,
                source_anchors=tuple(thaw_json(row) for row in content.source_anchors),
                resource_cost={"beam_bound": self.beam_bound},
                payload_native={
                    "goal_ref": goal_ref, "turn_ref": payload["turn_ref"],
                    "move_kind": move_kind,
                    "active_qud_status": self._active_qud_status(previous),
                    "operator_beam": operator_beam,
                },
                payload_projection={"truth_committed": False},
                idempotency_key=f"dialogue-goal:{goal_ref}",
            )
        )
        started = time.perf_counter()
        trace = self._run_soar(
            {
                "goal_ref": goal_ref,
                "turn_ref": payload["turn_ref"],
                "move_kind": move_kind,
                "active_qud_status": self._active_qud_status(previous),
                "operator_beam": operator_beam,
                "memory_limit_mib": self.memory_limit_mib,
            }
        )
        compared = {row["operator_ref"] for row in operator_beam}
        if set(trace["compared_operator_refs"]) != compared:
            raise ContractError("SYS-09: Soar n'a pas comparé tout le beam")
        if trace["selected_operator_ref"] != operator_beam[0]["operator_ref"]:
            raise ContractError("SYS-09: Soar n'a pas choisi l'opérateur compatible")
        decision = self.arena.publish(
            ArtifactProposal(
                artifact_type="soar-dialogue-decision",
                producer_id="dialogue-gameboard",
                producer_build=DIALOGUE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=content.mode,
                session_id=content.session_id,
                wave=goal.wave + 1,
                parent_ids=(goal.artifact_id,),
                observation_refs=content.observation_refs,
                context_refs=content.context_refs,
                source_anchors=tuple(thaw_json(row) for row in content.source_anchors),
                resource_cost={
                    "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
                    "projected_operators": len(operator_beam),
                    "memory_limit_mib": self.memory_limit_mib,
                },
                payload_native={
                    "goal_ref": goal_ref, "turn_ref": payload["turn_ref"],
                    "selected_operator_ref": trace["selected_operator_ref"],
                    "compared_operator_refs": trace["compared_operator_refs"],
                    "soar_trace": trace,
                },
                payload_projection={"truth_committed": False, "persistent_store_copied_to_soar": False},
                idempotency_key=f"soar-dialogue-decision:{goal.artifact_id}",
            )
        )
        updated = self._apply(previous, payload, move_kind, trace["selected_operator_ref"], content.artifact_id)
        state_parents = (
            content.artifact_id, episode_memory.artifact_id, identity_beam.artifact_id,
            temporal_memory.artifact_id, discourse_memory.artifact_id,
            decision.artifact_id,
        ) + (
            (previous_state.artifact_id,) if previous_state else ()
        )
        state = self.arena.publish(
            ArtifactProposal(
                artifact_type="dialogue-state",
                producer_id="dialogue-gameboard",
                producer_build=DIALOGUE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=content.mode,
                session_id=content.session_id,
                wave=max(self.arena.get(ref).wave + (1 if self.arena.get(ref).artifact_type == "soar-dialogue-decision" else 0) for ref in state_parents),
                parent_ids=state_parents,
                observation_refs=tuple(
                    sorted(set(content.observation_refs + (previous_state.observation_refs if previous_state else ())))
                ),
                context_refs=content.context_refs,
                source_anchors=self._source_anchors(self.arena.get(ref) for ref in state_parents),
                resource_cost={
                    "history_length": len(updated["history"]),
                    "qud_count": len(updated["quds"]),
                    "proposal_count": len(updated["proposals"]),
                },
                payload_native=updated,
                payload_projection={"truth_committed": False, "world_update_performed": False},
                idempotency_key=f"dialogue-state:{goal.artifact_id}",
            )
        )
        result = (goal, decision, state)
        self._cache[key] = result
        return result

    @staticmethod
    def _empty_state(dialogue_ref: str) -> dict[str, Any]:
        return {
            "dialogue_ref": dialogue_ref,
            "turn_index": -1,
            "active_qud_ref": None,
            "quds": [],
            "proposals": [],
            "groundings": [],
            "repairs": [],
            "history": [],
            "selected_operator_ref": None,
        }

    @staticmethod
    def _move_kind(payload: dict[str, Any], previous: dict[str, Any]) -> str:
        acts = {row["act"] for row in payload["act_candidates"]}
        if "correction" in acts:
            return "correction"
        if "grounding" in acts:
            return "grounding"
        if "question" in acts:
            return "clarification-question" if payload["question_type"] == "polar" and previous["active_qud_ref"] else "question"
        if "fragment" in acts and previous["active_qud_ref"]:
            return "answer-fragment"
        return "assertion"

    @staticmethod
    def _operator_beam(move_kind: str, previous: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
        selected = {
            "correction": "repair-active-content",
            "grounding": "ground-active-content",
            "clarification-question": "open-clarification-qud",
            "answer-fragment": "propose-fragment-answer",
            "assertion": "record-dialogue-assertion",
            "question": "change-qud" if previous["quds"] else "open-qud",
        }[move_kind]
        distractor = "maintain-current-dialogue-state"
        return [
            {"rank": 1, "operator_ref": selected, "score": 1.0, "compatible": True},
            {"rank": 2, "operator_ref": distractor, "score": 0.2, "compatible": False},
        ]

    @staticmethod
    def _active_qud_status(state: dict[str, Any]) -> str:
        active = state["active_qud_ref"]
        if active is None:
            return "none"
        return next(row["status"] for row in state["quds"] if row["qud_ref"] == active)

    def _apply(
        self,
        previous: dict[str, Any],
        payload: dict[str, Any],
        move_kind: str,
        operator_ref: str,
        content_ref: str,
    ) -> dict[str, Any]:
        state = json.loads(json.dumps(previous))
        turn_ref = payload["turn_ref"]
        active = state["active_qud_ref"]
        top_identity = payload["referent_ranking"][0]["identity_ref"] if payload["referent_ranking"] else None
        if move_kind in {"question", "clarification-question"}:
            if active is not None:
                prior = next(row for row in state["quds"] if row["qud_ref"] == active)
                if prior["status"] not in {"grounded", "closed"}:
                    prior["status"] = "suspended"
            qud_ref = "qud:" + hashlib.sha256(canonical_json([turn_ref, payload["semantic_factors"]]).encode()).hexdigest()[:24]
            focus = top_identity
            if move_kind == "clarification-question" and active is not None:
                parent = next(row for row in state["quds"] if row["qud_ref"] == active)
                focus = parent.get("focus_identity_ref") or focus
            state["quds"].append(
                {
                    "qud_ref": qud_ref,
                    "opened_by_turn_ref": turn_ref,
                    "parent_qud_ref": active if move_kind == "clarification-question" else None,
                    "question_type": payload["question_type"],
                    "signature": payload["semantic_factors"],
                    "focus_identity_ref": focus,
                    "referent_ranking": payload["referent_ranking"],
                    "status": "open",
                }
            )
            state["active_qud_ref"] = qud_ref
        elif move_kind == "answer-fragment":
            if active is None:
                raise ContractError("SYS-09: fragment sans QUD")
            proposal_ref = "proposal:" + hashlib.sha256(canonical_json([turn_ref, active]).encode()).hexdigest()[:24]
            state["proposals"].append(
                {
                    "proposal_ref": proposal_ref,
                    "qud_ref": active,
                    "turn_ref": turn_ref,
                    "content_ref": content_ref,
                    "speaker_ref": payload["speaker_ref"],
                    "referent_ranking": payload["referent_ranking"],
                    "proposed_identity_ref": top_identity,
                    "status": "pending-grounding",
                }
            )
            next(row for row in state["quds"] if row["qud_ref"] == active)["status"] = "answered-pending-grounding"
        elif move_kind == "grounding":
            pending = next((row for row in reversed(state["proposals"]) if row["status"] == "pending-grounding"), None)
            target_ref = pending["proposal_ref"] if pending else active
            if target_ref is None:
                raise ContractError("SYS-09: grounding sans contenu actif")
            if pending:
                pending["status"] = "grounded"
                qud = next(row for row in state["quds"] if row["qud_ref"] == pending["qud_ref"])
            else:
                qud = next(row for row in state["quds"] if row["qud_ref"] == active)
            qud["status"] = "grounded"
            state["groundings"].append(
                {
                    "grounding_ref": "grounding:" + hashlib.sha256(canonical_json([turn_ref, target_ref]).encode()).hexdigest()[:24],
                    "turn_ref": turn_ref,
                    "speaker_ref": payload["speaker_ref"],
                    "target_ref": target_ref,
                    "status": "accepted",
                }
            )
        elif move_kind == "correction":
            if active is None:
                raise ContractError("SYS-09: correction sans QUD active")
            qud = next(row for row in state["quds"] if row["qud_ref"] == active)
            old_ranking = qud["referent_ranking"]
            old_focus = qud["focus_identity_ref"]
            corrected = next((row for row in reversed(state["proposals"]) if row["qud_ref"] == active), None)
            if corrected:
                corrected["status"] = "corrected"
            qud["focus_identity_ref"] = top_identity
            qud["referent_ranking"] = payload["referent_ranking"]
            qud["status"] = "open-after-repair"
            state["repairs"].append(
                {
                    "repair_ref": "repair:" + hashlib.sha256(canonical_json([turn_ref, active]).encode()).hexdigest()[:24],
                    "turn_ref": turn_ref,
                    "qud_ref": active,
                    "corrected_proposal_ref": corrected["proposal_ref"] if corrected else None,
                    "old_focus_identity_ref": old_focus,
                    "new_focus_identity_ref": top_identity,
                    "ranking_before": old_ranking,
                    "ranking_after": payload["referent_ranking"],
                    "status": "applied-revisably",
                }
            )
        state["turn_index"] = payload["turn_index"]
        state["selected_operator_ref"] = operator_ref
        state["history"].append(
            {
                "turn_ref": turn_ref,
                "turn_index": payload["turn_index"],
                "speaker_ref": payload["speaker_ref"],
                "content_ref": content_ref,
                "move_kind": move_kind,
                "operator_ref": operator_ref,
            }
        )
        return state

    def _run_soar(self, request: dict[str, Any]) -> dict[str, Any]:
        worker = self.project_root / "seman2_runtime/workers/soar_dialogue_worker.py"
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
            raise ContractError("SYS-09: timeout du worker Soar") from exc
        if completed.returncode:
            raise ContractError(f"SYS-09: worker Soar en échec: {completed.stderr.strip()}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ContractError("SYS-09: sortie Soar non JSON") from exc

    @staticmethod
    def _source_anchors(rows: Iterable[CognitiveArtifact]) -> tuple[dict[str, Any], ...]:
        anchors = {
            canonical_json(thaw_json(anchor)): thaw_json(anchor)
            for row in rows
            for anchor in row.source_anchors
        }
        return tuple(anchors[key] for key in sorted(anchors))
