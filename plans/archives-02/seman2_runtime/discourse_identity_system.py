"""Identité et contextes discursifs depuis le stock MRS/L3/L4 réel."""

from __future__ import annotations

import hashlib
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
from .contracts import ContractError, canonical_json
from .developmental_core import ContextFrame, ContextKind, DevelopmentalCore
from .formal_composition import register_composition_types
from .hypothesis_system import register_hypothesis_types
from .identity_resolution import IdentityResolver, MentionOccurrence
from .knowledge_system import register_knowledge_types
from .low_level_system import register_low_level_types
from .temporal_system import register_temporal_types


DISCOURSE_BUILD = "active-contextual-identity-system"


def register_discourse_identity_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "identity-mention-candidate",
            "seman2/active/L2/identity-mention-candidate",
            2,
            allowed_producers=frozenset({"contextual-mention-extractor"}),
            parent_types=frozenset({"composed-candidate"}),
            required_native_fields=frozenset(
                {"source_candidate_ref", "mentions", "attributed_contexts", "propositions"}
            ),
            required_projection_fields=frozenset({"identity_committed", "truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "identity-beam",
            "seman2/active/L3/identity-beam",
            3,
            allowed_producers=frozenset({"contextual-identity-resolver"}),
            parent_types=frozenset(
                {"situation-branch-set", "identity-mention-candidate"}
            ),
            required_native_fields=frozenset(
                {"source_branch_set_ref", "mentions", "decisions", "propositions", "contexts"}
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "discourse-memory",
            "seman2/active/L4/discourse-memory",
            4,
            allowed_producers=frozenset({"contextual-identity-resolver"}),
            parent_types=frozenset(
                {"identity-beam", "episode-memory", "temporal-memory"}
            ),
            required_native_fields=frozenset(
                {
                    "identity_profiles",
                    "facets",
                    "contexts",
                    "ambiguous_mentions",
                    "world_propositions",
                    "attributed_propositions",
                    "dependency_refs",
                }
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed"}
            ),
        )
    )


def build_discourse_identity_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    register_composition_types(registry)
    register_hypothesis_types(registry)
    register_knowledge_types(registry)
    register_temporal_types(registry)
    register_discourse_identity_types(registry)
    registry.freeze()
    return registry


class ContextualMentionExtractor:
    def __init__(
        self,
        arena: ArtifactArena,
        *,
        world_context_ref: str,
    ) -> None:
        self.arena = arena
        self.world_context_ref = world_context_ref
        self._cache: dict[str, CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "input": "composed-candidate",
                    "mention_identity": "observation+utf8-span+referent-kind",
                    "attribution": "recursive-handle-complement-scope",
                }
            ).encode()
        ).hexdigest()

    def extract(self, candidate: CognitiveArtifact) -> CognitiveArtifact:
        if candidate.artifact_type != "composed-candidate":
            raise ContractError("SYS-06: extraction exige un candidat L2")
        if candidate.status is not ArtifactStatus.SUCCESS:
            raise ContractError("SYS-06: candidat L2 en échec non extractible")
        if candidate.artifact_id in self._cache:
            return self._cache[candidate.artifact_id]
        started = time.perf_counter()
        payload = thaw_json(candidate.payload_native)
        observation_ref = candidate.observation_refs[0]
        relations = payload["relations"]
        hcons = {row["high"]: row["low"] for row in payload["scope_constraints"]}
        relation_by_label: dict[str, list[dict[str, Any]]] = {}
        for relation in relations:
            relation_by_label.setdefault(relation["label"], []).append(relation)

        attributed_contexts: list[dict[str, Any]] = []
        variable_context: dict[str, str] = {}
        for relation in relations:
            source = {row["role_ref"]: row["source_value"] for row in relation["bindings"]}
            speaker_ref = source.get("ARG1")
            if relation["part_of_speech"] != "v" or not speaker_ref:
                continue
            target_handles = {
                row["source_value"]
                for row in relation["bindings"]
                if row["role_ref"].startswith("ARG")
                and row["role_ref"] not in {"ARG0", "ARG1"}
                and row["source_value"].startswith("h")
            }
            if not target_handles:
                continue
            embedded_labels, embedded_variables = self._walk_scoped_content(
                target_handles, hcons, relation_by_label
            )
            context_ref = self._context_ref(observation_ref, relation["span"])
            for variable in embedded_variables:
                variable_context[variable] = context_ref
            attributed_contexts.append(
                {
                    "context_ref": context_ref,
                    "kind": "attributed",
                    "attitude_form_ref": f"external:mrs:{relation['predicate']}",
                    "speaker_variable_refs": [speaker_ref],
                    "source_relation_refs": [relation["relation_ref"]],
                    "embedded_label": sorted(embedded_labels)[0],
                    "embedded_labels": sorted(embedded_labels),
                    "epistemic_status": "attributed-not-world",
                }
            )

        referent_properties = {
            row["mrs_variable"]: row["properties"] for row in payload["referents"]
        }
        mentions: list[dict[str, Any]] = []
        for variable, properties in sorted(referent_properties.items()):
            lexical = [
                relation
                for relation in relations
                if any(
                    row["role_ref"] == "ARG0" and row["source_value"] == variable
                    for row in relation["bindings"]
                )
                and (
                    relation["part_of_speech"] in {"n", "u"}
                    or relation["predicate"] in {"named", "pron"}
                )
            ]
            for relation in lexical:
                if relation["predicate"] == "named":
                    kind = "proper"
                    aliases = [relation["constant"]]
                elif relation["predicate"] == "pron":
                    kind = "pronoun"
                    aliases = [relation["surface_excerpt"]]
                else:
                    kind = self._nominal_kind(relations, variable)
                    aliases = [relation["surface_excerpt"], relation["predicate"]]
                aliases = sorted({str(value) for value in aliases if value})
                descriptors = sorted(
                    {
                        other["predicate"]
                        for other in relations
                        if other["part_of_speech"] == "a"
                        and any(
                            row["role_ref"] == "ARG1"
                            and row["source_value"] == variable
                            for row in other["bindings"]
                        )
                    }
                )
                span = relation["span"] or [0, 0]
                mention_ref = self._mention_ref(observation_ref, span)
                roles = sorted(
                    {
                        role_ref
                        for other in relations
                        if other["part_of_speech"] == "v"
                        for binding in other["bindings"]
                        if binding["source_value"] == variable
                        and binding["role_ref"] != "ARG0"
                        for role_ref in (
                            f"external:mrs:{other['predicate']}:{binding['role_ref']}",
                            f"grammatical-role:{binding['role_ref']}",
                        )
                    }
                )
                features = {
                    str(key): str(value) for key, value in properties.items()
                }
                mentions.append(
                    {
                        "mention_ref": mention_ref,
                        "observation_ref": observation_ref,
                        "variable_ref": variable,
                        "reference_kind": kind,
                        "surface_aliases": aliases,
                        "grammatical_features": sorted(features.items()),
                        "descriptor_refs": descriptors,
                        "role_refs": roles,
                        "span": span,
                        "context_ref": variable_context.get(
                            variable, self.world_context_ref
                        ),
                        "support_relation_refs": [relation["relation_ref"]],
                    }
                )

        propositions = []
        context_by_embedded_label = {
            row["embedded_label"]: row["context_ref"] for row in attributed_contexts
        }
        for state in payload["state_candidates"]:
            relation = next(
                row for row in relations if row["relation_ref"] == state["relation_ref"]
            )
            bearer_variable_ref = next(
                (
                    row["source_value"]
                    for row in relation["bindings"]
                    if row["role_ref"] == "ARG1"
                ),
                None,
            )
            context_ref = variable_context.get(
                bearer_variable_ref,
                context_by_embedded_label.get(
                    relation["label"], self.world_context_ref
                ),
            )
            propositions.append(
                {
                    "proposition_ref": f"proposition:{candidate.artifact_id}:{len(propositions)}",
                    "relation_form_ref": state["state_form_ref"],
                    "bearer_variable_ref": bearer_variable_ref,
                    "context_ref": context_ref,
                    "source_relation_ref": state["relation_ref"],
                    "surface_span": relation["span"],
                    "epistemic_status": (
                        "attributed" if context_ref != self.world_context_ref else "narrated-candidate"
                    ),
                }
            )

        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="identity-mention-candidate",
                producer_id="contextual-mention-extractor",
                producer_build=DISCOURSE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=candidate.mode,
                session_id=candidate.session_id,
                wave=candidate.wave,
                parent_ids=(candidate.artifact_id,),
                observation_refs=candidate.observation_refs,
                context_refs=tuple(
                    sorted(
                        {self.world_context_ref}
                        | {row["context_ref"] for row in attributed_contexts}
                    )
                ),
                source_anchors=tuple(thaw_json(row) for row in candidate.source_anchors),
                resource_cost={
                    "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
                    "mention_count": len(mentions),
                    "attributed_context_count": len(attributed_contexts),
                },
                payload_native={
                    "source_candidate_ref": candidate.artifact_id,
                    "mentions": mentions,
                    "attributed_contexts": attributed_contexts,
                    "propositions": propositions,
                },
                payload_projection={
                    "identity_committed": False,
                    "truth_committed": False,
                },
                idempotency_key=f"identity-mentions:{candidate.artifact_id}",
            )
        )
        self._cache[candidate.artifact_id] = artifact
        return artifact

    @staticmethod
    def _nominal_kind(relations: list[dict[str, Any]], variable: str) -> str:
        quantifiers = {
            row["predicate"]
            for row in relations
            if row["part_of_speech"] == "q"
            and any(
                binding["role_ref"] == "ARG0" and binding["source_value"] == variable
                for binding in row["bindings"]
            )
        }
        if quantifiers & {"_a_q", "udef_q"}:
            return "indefinite"
        if quantifiers & {"_the_q", "def_explicit_q"}:
            return "definite"
        return "nominal"

    @staticmethod
    def _mention_ref(observation_ref: str, span: list[int]) -> str:
        digest = hashlib.sha256(
            canonical_json([observation_ref, span]).encode()
        ).hexdigest()
        return f"mention:{digest[:24]}"

    @staticmethod
    def _context_ref(observation_ref: str, span: list[int] | None) -> str:
        digest = hashlib.sha256(
            canonical_json([observation_ref, span]).encode()
        ).hexdigest()
        return f"ctx:attributed:{digest[:24]}"

    @staticmethod
    def _walk_scoped_content(
        target_handles: set[str],
        hcons: dict[str, str],
        relation_by_label: dict[str, list[dict[str, Any]]],
    ) -> tuple[set[str], set[str]]:
        pending = [hcons.get(handle, handle) for handle in sorted(target_handles)]
        labels: set[str] = set()
        variables: set[str] = set()
        while pending:
            label = pending.pop()
            if label in labels:
                continue
            labels.add(label)
            for relation in relation_by_label.get(label, []):
                for binding in relation["bindings"]:
                    value = binding["source_value"]
                    if not binding["role_ref"].startswith("ARG"):
                        continue
                    if value.startswith("h"):
                        target = hcons.get(value, value)
                        if target not in labels:
                            pending.append(target)
                    elif value.startswith(("x", "i")):
                        variables.add(value)
        return labels, variables


class ContextualIdentityEngine:
    def __init__(
        self,
        arena: ArtifactArena,
        *,
        world_context_ref: str = "ctx:sys-06:world",
        discourse_ref: str = "discourse:sys-06",
    ) -> None:
        self.arena = arena
        self.world_context_ref = world_context_ref
        self.discourse_ref = discourse_ref
        self.core = DevelopmentalCore(vector_dimension=256)
        self.core.universe.add_context(
            ContextFrame(world_context_ref, ContextKind.NARRATED)
        )
        self.resolver = IdentityResolver(self.core)
        self.mention_to_identity: dict[str, str] = {}
        self.identity_roles: dict[str, set[str]] = {}
        self.identity_reference_kinds: dict[str, set[str]] = {}
        self.identity_descriptors: dict[tuple[str, str], set[str]] = {}
        self.variable_identity_by_observation: dict[tuple[str, str], str] = {}
        self.beams: list[CognitiveArtifact] = []
        self._beam_cache: dict[str, CognitiveArtifact] = {}
        self._memory_cache: dict[tuple[str, ...], CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "world_context_ref": world_context_ref,
                    "discourse_ref": discourse_ref,
                    "pronoun_selection": "none-without-margin",
                    "parse_deduplication": "mention_ref",
                }
            ).encode()
        ).hexdigest()

    def resolve_observation(
        self,
        branch_set: CognitiveArtifact,
        mention_artifacts: Iterable[CognitiveArtifact],
        *,
        temporal_index: int,
    ) -> CognitiveArtifact:
        if branch_set.artifact_type != "situation-branch-set":
            raise ContractError("SYS-06: résolution exige une situation L3")
        if branch_set.artifact_id in self._beam_cache:
            return self._beam_cache[branch_set.artifact_id]
        rows = tuple(mention_artifacts)
        if not rows or any(row.artifact_type != "identity-mention-candidate" for row in rows):
            raise ContractError("SYS-06: candidats de mention L2 requis")
        situation = thaw_json(branch_set.payload_native)
        expected = {row["candidate_ref"] for row in situation["branches"]}
        actual = {
            thaw_json(row.payload_native)["source_candidate_ref"] for row in rows
        }
        if expected != actual:
            raise ContractError("SYS-06: couverture incomplète des parses L2")
        started = time.perf_counter()
        payloads = [thaw_json(row.payload_native) for row in rows]
        merged_mentions = self._merge_mentions(payloads)
        contexts = self._merge_contexts(payloads)

        # Les mentions du contexte raconté, dont les locuteurs, sont résolues
        # avant de créer les espaces attribués.
        decisions: list[dict[str, Any]] = []
        for mention in sorted(
            (row for row in merged_mentions if row["context_ref"] == self.world_context_ref),
            key=lambda row: (row["span"], row["mention_ref"]),
        ):
            decisions.append(self._resolve_mention(mention, temporal_index))

        observation_ref = branch_set.observation_refs[0]
        for context in contexts:
            speaker_identity = next(
                (
                    self.variable_identity_by_observation[(observation_ref, variable)]
                    for variable in context["speaker_variable_refs"]
                    if (observation_ref, variable)
                    in self.variable_identity_by_observation
                ),
                None,
            )
            if speaker_identity is None:
                raise ContractError(
                    "SYS-06: locuteur attribuant non résolu: "
                    f"observation={observation_ref}, "
                    f"variables={context['speaker_variable_refs']}, "
                    f"connues={sorted(self.variable_identity_by_observation)}"
                )
            self.core.universe.add_context(
                ContextFrame(
                    context["context_ref"],
                    ContextKind.ATTRIBUTED,
                    parent_context_ref=self.world_context_ref,
                    attribution_ref=speaker_identity,
                    support_refs=tuple(context["source_relation_refs"]),
                )
            )
            context["attribution_identity_ref"] = speaker_identity

        for mention in sorted(
            (row for row in merged_mentions if row["context_ref"] != self.world_context_ref),
            key=lambda row: (row["span"], row["mention_ref"]),
        ):
            decisions.append(self._resolve_mention(mention, temporal_index))

        propositions = self._merge_propositions(payloads, merged_mentions)
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="identity-beam",
                producer_id="contextual-identity-resolver",
                producer_build=DISCOURSE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=branch_set.mode,
                session_id=branch_set.session_id,
                wave=max(branch_set.wave, *(row.wave for row in rows)),
                parent_ids=(branch_set.artifact_id,) + tuple(row.artifact_id for row in rows),
                observation_refs=branch_set.observation_refs,
                context_refs=tuple(
                    sorted({self.world_context_ref} | {row["context_ref"] for row in contexts})
                ),
                source_anchors=tuple(thaw_json(row) for row in branch_set.source_anchors),
                resource_cost={
                    "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
                    "parse_count": len(rows),
                    "deduplicated_mentions": len(merged_mentions),
                },
                payload_native={
                    "source_branch_set_ref": branch_set.artifact_id,
                    "mentions": merged_mentions,
                    "decisions": decisions,
                    "propositions": propositions,
                    "contexts": contexts,
                },
                payload_projection={"truth_committed": False},
                idempotency_key=f"identity-beam:{branch_set.artifact_id}",
            )
        )
        self.beams.append(artifact)
        self._beam_cache[branch_set.artifact_id] = artifact
        return artifact

    def finalize(
        self,
        *,
        episode_memories: Iterable[CognitiveArtifact],
        temporal_memory: CognitiveArtifact,
    ) -> CognitiveArtifact:
        episodes = tuple(episode_memories)
        if not self.beams or any(row.artifact_type != "episode-memory" for row in episodes):
            raise ContractError("SYS-06: mémoire discursive exige beams et épisodes L4")
        if temporal_memory.artifact_type != "temporal-memory":
            raise ContractError("SYS-06: mémoire temporelle L4 requise")
        parents = tuple(row.artifact_id for row in self.beams + list(episodes)) + (
            temporal_memory.artifact_id,
        )
        if parents in self._memory_cache:
            return self._memory_cache[parents]
        started = time.perf_counter()
        beam_payloads = [thaw_json(row.payload_native) for row in self.beams]
        propositions = [row for payload in beam_payloads for row in payload["propositions"]]
        ambiguous = [
            decision
            for payload in beam_payloads
            for decision in payload["decisions"]
            if decision["status"] == "ambiguous"
        ]
        contexts = [
            {
                "context_ref": ref,
                "kind": context.kind.value,
                "parent_context_ref": context.parent_context_ref,
                "attribution_ref": context.attribution_ref,
                "support_refs": list(context.support_refs),
            }
            for ref, context in sorted(self.core.universe.contexts.items())
        ]
        profiles = [
            {
                "identity_ref": row.identity_ref,
                "mention_refs": list(row.mention_refs),
                "surface_aliases": list(row.surface_aliases),
                "context_refs": list(row.context_refs),
                "grammatical_features": [list(item) for item in row.grammatical_features],
                "role_refs": sorted(self.identity_roles.get(row.identity_ref, set())),
                "reference_kind_evidence": sorted(
                    self.identity_reference_kinds.get(row.identity_ref, set())
                ),
                "descriptor_evidence_by_context": {
                    context_ref: sorted(values)
                    for (identity_ref, context_ref), values in sorted(
                        self.identity_descriptors.items()
                    )
                    if identity_ref == row.identity_ref
                },
                "last_temporal_index": row.last_temporal_index,
            }
            for row in sorted(self.resolver.profiles.values(), key=lambda row: row.identity_ref)
        ]
        facets = [
            {
                "facet_ref": row.facet_id,
                "identity_ref": row.identity_ref,
                "context_ref": row.context_ref,
                "active_role_refs": list(row.active_role_refs),
                "support_refs": list(row.support_refs),
                "temporal_start": row.temporal_start,
            }
            for row in sorted(self.core.universe.facets.values(), key=lambda row: row.facet_id)
        ]
        anchors = {
            canonical_json(thaw_json(anchor)): thaw_json(anchor)
            for parent in parents
            for anchor in self.arena.get(parent).source_anchors
        }
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="discourse-memory",
                producer_id="contextual-identity-resolver",
                producer_build=DISCOURSE_BUILD,
                configuration_digest=self.configuration_digest,
                mode=self.beams[0].mode,
                session_id=self.beams[0].session_id,
                wave=max(self.arena.get(parent).wave for parent in parents),
                parent_ids=parents,
                observation_refs=tuple(ref for row in self.beams for ref in row.observation_refs),
                context_refs=tuple(row["context_ref"] for row in contexts),
                source_anchors=tuple(anchors[key] for key in sorted(anchors)),
                resource_cost={
                    "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
                    "identity_count": len(profiles),
                    "ambiguous_mention_count": len(ambiguous),
                },
                payload_native={
                    "identity_profiles": profiles,
                    "facets": facets,
                    "contexts": contexts,
                    "ambiguous_mentions": ambiguous,
                    "world_propositions": [
                        row for row in propositions if row["context_ref"] == self.world_context_ref
                    ],
                    "attributed_propositions": [
                        row for row in propositions if row["context_ref"] != self.world_context_ref
                    ],
                    "dependency_refs": {
                        "episode_memory_refs": [row.artifact_id for row in episodes],
                        "temporal_memory_ref": temporal_memory.artifact_id,
                    },
                },
                payload_projection={
                    "truth_committed": False,
                    "world_update_performed": False,
                },
                status=ArtifactStatus.PARTIAL if ambiguous else ArtifactStatus.SUCCESS,
                idempotency_key="discourse-memory:" + hashlib.sha256(
                    canonical_json(parents).encode()
                ).hexdigest(),
            )
        )
        self._memory_cache[parents] = artifact
        return artifact

    def _resolve_mention(self, mention: dict[str, Any], temporal_index: int) -> dict[str, Any]:
        occurrence = MentionOccurrence(
            mention_ref=mention["mention_ref"],
            context_ref=mention["context_ref"],
            discourse_ref=self.discourse_ref,
            temporal_index=temporal_index,
            surface_aliases=tuple(mention["surface_aliases"]),
            grammatical_features=tuple(tuple(row) for row in mention["grammatical_features"]),
            role_refs=tuple(mention["role_refs"]),
            support_refs=tuple(mention["support_artifact_refs"]),
        )
        decision = self.resolver.propose(occurrence)
        candidates = [
            {
                "candidate_ref": row.candidate_ref,
                "identity_ref": row.identity_ref,
                "score": row.score,
                "support_signals": list(row.support_signals),
                "conflict_signals": list(row.conflict_signals),
                "creates_new_identity": row.creates_new_identity,
            }
            for row in decision.candidates
        ]
        selected_ref = decision.selected_candidate_ref
        status = decision.status
        rationale = decision.rationale
        if mention["reference_kind"] == "indefinite":
            selected_ref = next(
                row["candidate_ref"] for row in candidates if row["creates_new_identity"]
            )
            status = "indefinite-introduction"
            rationale = "indefinite grammatical introduction selects a new candidate identity"
        elif mention["reference_kind"] == "proper" and not any(
            "surface-alias-match" in row["support_signals"]
            for row in candidates
            if not row["creates_new_identity"]
        ):
            selected_ref = next(
                row["candidate_ref"] for row in candidates if row["creates_new_identity"]
            )
            status = "proper-name-introduction"
            rationale = "unseen proper-name form introduces a new candidate identity"
        elif mention["reference_kind"] == "pronoun":
            candidates = self._rank_pronoun_candidates(
                candidates,
                temporal_index,
                set(mention["role_refs"]),
                dict(mention["grammatical_features"]),
            )
            selected_ref = None
            status = "ambiguous"
            rationale = "continuity ranks antecedents but evidence does not authorize identity commitment"
        elif mention["descriptor_refs"]:
            candidates = self._rank_descriptor_candidates(
                candidates,
                context_ref=mention["context_ref"],
                descriptor_refs=set(mention["descriptor_refs"]),
            )
            best = candidates[0]
            runner_up_score = candidates[1]["rank_score"] if len(candidates) > 1 else 0.0
            if (
                best["rank_score"] >= self.resolver.policy.selection_threshold
                and best["rank_score"] - runner_up_score
                >= self.resolver.policy.selection_margin
            ):
                selected_ref = best["candidate_ref"]
                status = "decisive-candidate"
                rationale = (
                    "contextual descriptor evidence and grammatical evidence "
                    "provide sufficient support and margin"
                )
            else:
                selected_ref = None
                status = "ambiguous"
                rationale = (
                    "descriptor evidence remains compatible with multiple identities"
                )

        selected_identity = None
        if selected_ref is not None:
            profile = self.resolver.commit(decision, candidate_ref=selected_ref)
            selected_identity = profile.identity_ref
            self.mention_to_identity[mention["mention_ref"]] = selected_identity
            self.identity_roles.setdefault(selected_identity, set()).update(
                mention["role_refs"]
            )
            self.identity_reference_kinds.setdefault(selected_identity, set()).add(
                mention["reference_kind"]
            )
            self.identity_descriptors.setdefault(
                (selected_identity, mention["context_ref"]), set()
            ).update(mention["descriptor_refs"])
            for variable in mention["variable_refs"]:
                self.variable_identity_by_observation[
                    (mention["observation_ref"], variable)
                ] = selected_identity
        return {
            "mention_ref": mention["mention_ref"],
            "reference_kind": mention["reference_kind"],
            "context_ref": mention["context_ref"],
            "candidates": candidates,
            "selected_candidate_ref": selected_ref,
            "selected_identity_ref": selected_identity,
            "status": status,
            "rationale": rationale,
        }

    def _rank_pronoun_candidates(
        self,
        candidates: list[dict[str, Any]],
        temporal_index: int,
        current_roles: set[str],
        current_features: dict[str, str],
    ) -> list[dict[str, Any]]:
        ranked = []
        for candidate in candidates:
            row = dict(candidate)
            if candidate["creates_new_identity"]:
                adjustment = -0.40
                signal = "pronoun-discourages-new-identity"
            else:
                profile = self.resolver.profiles[candidate["identity_ref"]]
                distance = max(0, temporal_index - profile.last_temporal_index)
                adjustment = max(0.0, 0.15 - 0.05 * distance)
                signal = f"graded-discourse-recency:{distance}"
                if current_roles & self.identity_roles.get(
                    candidate["identity_ref"], set()
                ):
                    adjustment += 0.15
                    signal += "+role-continuity"
                gender = current_features.get("GEND")
                known_kinds = self.identity_reference_kinds.get(
                    candidate["identity_ref"], set()
                )
                if gender in {"m", "f"}:
                    kind_adjustment = 0.12 if "proper" in known_kinds else -0.12
                    signal += "+gendered-reference-kind-continuity"
                    adjustment += kind_adjustment
                elif gender == "n":
                    kind_adjustment = (
                        0.12
                        if known_kinds & {"indefinite", "definite", "nominal"}
                        else -0.12
                    )
                    signal += "+neuter-reference-kind-continuity"
                    adjustment += kind_adjustment
            row["continuity_adjustment"] = adjustment
            row["rank_score"] = max(0.0, min(1.0, candidate["score"] + adjustment))
            row["support_signals"] = candidate["support_signals"] + [signal]
            ranked.append(row)
        return sorted(ranked, key=lambda row: (-row["rank_score"], row["candidate_ref"]))

    def _rank_descriptor_candidates(
        self,
        candidates: list[dict[str, Any]],
        *,
        context_ref: str,
        descriptor_refs: set[str],
    ) -> list[dict[str, Any]]:
        ranked = []
        for candidate in candidates:
            row = dict(candidate)
            if candidate["creates_new_identity"]:
                adjustment = -0.20
                signals = ["definite-description-discourages-new-identity"]
                conflicts: list[str] = []
            else:
                identity_ref = candidate["identity_ref"]
                known = set(
                    self.identity_descriptors.get((identity_ref, context_ref), set())
                )
                # A description learned in the narrated world can identify the
                # bearer inside an attributed context, but new attributed
                # properties are stored only in that attributed context.
                if context_ref != self.world_context_ref:
                    known.update(
                        self.identity_descriptors.get(
                            (identity_ref, self.world_context_ref), set()
                        )
                    )
                overlap = sorted(known & descriptor_refs)
                conflicts = sorted(known - descriptor_refs) if known and not overlap else []
                adjustment = 0.35 if overlap else (-0.25 if conflicts else 0.0)
                signals = [f"descriptor-match:{value}" for value in overlap]
                if not signals:
                    signals = ["no-contextual-descriptor-match"]
            row["descriptor_adjustment"] = adjustment
            row["rank_score"] = max(0.0, min(1.0, candidate["score"] + adjustment))
            row["support_signals"] = candidate["support_signals"] + signals
            row["conflict_signals"] = candidate["conflict_signals"] + [
                f"descriptor-conflict:{value}" for value in conflicts
            ]
            ranked.append(row)
        return sorted(ranked, key=lambda row: (-row["rank_score"], row["candidate_ref"]))

    def _merge_mentions(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for payload in payloads:
            source_candidate = payload["source_candidate_ref"]
            for mention in payload["mentions"]:
                row = merged.setdefault(
                    mention["mention_ref"],
                    {
                        **mention,
                        "reference_kind_candidates": [],
                        "variable_refs": [],
                        "support_candidate_refs": [],
                        "support_artifact_refs": [],
                        "alternative_count": 0,
                    },
                )
                row["reference_kind_candidates"].append(mention["reference_kind"])
                row["variable_refs"].append(mention["variable_ref"])
                row["support_candidate_refs"].append(source_candidate)
                row["support_artifact_refs"].append(source_candidate)
                row["alternative_count"] += 1
                row["surface_aliases"] = sorted(
                    set(row["surface_aliases"]) | set(mention["surface_aliases"])
                )
                row["descriptor_refs"] = sorted(
                    set(row["descriptor_refs"]) | set(mention["descriptor_refs"])
                )
                row["role_refs"] = sorted(
                    set(row["role_refs"]) | set(mention["role_refs"])
                )
                row.setdefault("context_candidates", []).append(
                    mention["context_ref"]
                )
        for row in merged.values():
            for key in (
                "reference_kind_candidates",
                "variable_refs",
                "support_candidate_refs",
                "support_artifact_refs",
            ):
                row[key] = sorted(set(row[key]))
            row["reference_kind"] = (
                row["reference_kind_candidates"][0]
                if len(row["reference_kind_candidates"]) == 1
                else "ambiguous-form"
            )
            row["context_candidates"] = sorted(
                set(row.get("context_candidates", [row["context_ref"]]))
            )
            attributed = [
                ref
                for ref in row["context_candidates"]
                if ref != self.world_context_ref
            ]
            if len(attributed) == 1:
                row["context_ref"] = attributed[0]
        return [merged[key] for key in sorted(merged, key=lambda ref: (merged[ref]["span"], ref))]

    @staticmethod
    def _merge_contexts(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for payload in payloads:
            for context in payload["attributed_contexts"]:
                row = rows.setdefault(context["context_ref"], dict(context))
                row["speaker_variable_refs"] = sorted(
                    set(row["speaker_variable_refs"])
                    | set(context["speaker_variable_refs"])
                )
                row["source_relation_refs"] = sorted(
                    set(row["source_relation_refs"])
                    | set(context["source_relation_refs"])
                )
                row["embedded_labels"] = sorted(
                    set(row.get("embedded_labels", [row["embedded_label"]]))
                    | set(context.get("embedded_labels", [context["embedded_label"]]))
                )
        return [rows[key] for key in sorted(rows)]

    def _merge_propositions(
        self, payloads: list[dict[str, Any]], mentions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        mention_by_variable = {
            variable: mention["mention_ref"]
            for mention in mentions
            for variable in mention["variable_refs"]
        }
        alternatives = []
        for payload in payloads:
            for proposition in payload["propositions"]:
                row = dict(proposition)
                row["bearer_mention_ref"] = mention_by_variable.get(
                    row.pop("bearer_variable_ref")
                )
                alternatives.append(row)
        attributed_by_surface: dict[str, set[str]] = {}
        for row in alternatives:
            if row["context_ref"] == self.world_context_ref:
                continue
            key = canonical_json([row["relation_form_ref"], row["surface_span"]])
            attributed_by_surface.setdefault(key, set()).add(row["context_ref"])

        rows = {}
        for row in alternatives:
            surface_key = canonical_json(
                [row["relation_form_ref"], row["surface_span"]]
            )
            scoped_contexts = attributed_by_surface.get(surface_key, set())
            if row["context_ref"] == self.world_context_ref and len(scoped_contexts) == 1:
                row["context_ref"] = next(iter(scoped_contexts))
                row["epistemic_status"] = "attributed"
            key = canonical_json(
                [row["relation_form_ref"], row["bearer_mention_ref"], row["context_ref"]]
            )
            rows[key] = row
        return [rows[key] for key in sorted(rows)]
