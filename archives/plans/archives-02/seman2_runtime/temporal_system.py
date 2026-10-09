"""Temps relationnel formel sur candidats MRS réellement composés."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Iterable

import z3

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
from .hypothesis_system import register_hypothesis_types
from .knowledge_system import register_knowledge_types
from .low_level_system import register_low_level_types


TEMPORAL_BUILD = "active-relational-temporal-system"


def register_temporal_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "temporal-analysis",
            "seman2/active/L3/temporal-analysis",
            3,
            allowed_producers=frozenset({"relational-temporal-analyzer"}),
            parent_types=frozenset({"composed-candidate"}),
            required_native_fields=frozenset(
                {"source_candidate_ref", "frames", "states", "cues", "allen_constraints"}
            ),
            required_projection_fields=frozenset({"truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "temporal-branch-set",
            "seman2/active/L3/temporal-branch-set",
            3,
            allowed_producers=frozenset({"relational-temporal-analyzer"}),
            parent_types=frozenset({"situation-branch-set", "temporal-analysis"}),
            required_native_fields=frozenset(
                {"source_branch_set_ref", "analysis_refs", "rejected_candidate_refs"}
            ),
            required_projection_fields=frozenset({"selected_ref", "truth_committed"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "temporal-memory",
            "seman2/active/L4/temporal-memory",
            4,
            allowed_producers=frozenset({"relational-temporal-reasoner"}),
            parent_types=frozenset({"temporal-branch-set"}),
            required_native_fields=frozenset(
                {"networks", "discourse_constraints", "state_constraints", "state_history", "queries", "contradictions"}
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed", "selected_network_ref"}
            ),
        )
    )


def build_temporal_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    register_composition_types(registry)
    register_hypothesis_types(registry)
    register_knowledge_types(registry)
    register_temporal_types(registry)
    registry.freeze()
    return registry


class RelationalTemporalAnalyzer:
    def __init__(self, arena: ArtifactArena) -> None:
        self.arena = arena
        self._analysis_cache: dict[str, CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "frameworks": ["Reichenbach-ERS", "Allen-intervals"],
                    "selection": "none",
                    "surface_normalizer": "none",
                }
            ).encode()
        ).hexdigest()

    def analyze(self, candidate: CognitiveArtifact) -> CognitiveArtifact:
        if candidate.artifact_type != "composed-candidate":
            raise ContractError("SYS-05: l'analyse temporelle exige un candidat L2")
        if candidate.status is not ArtifactStatus.SUCCESS:
            raise ContractError("SYS-05: candidat L2 en échec non analysable")
        if candidate.artifact_id in self._analysis_cache:
            return self._analysis_cache[candidate.artifact_id]
        started = time.perf_counter()
        payload = thaw_json(candidate.payload_native)
        properties = {
            row["candidate_ref"]: row["properties"] for row in payload["events"]
        }
        frames: list[dict[str, Any]] = []
        frame_by_event: dict[str, str] = {}
        frame_by_label: dict[str, str] = {}
        for relation in payload["relations"]:
            bindings = {row["role_ref"]: row["value_ref"] for row in relation["bindings"]}
            event_ref = bindings.get("ARG0")
            if relation["part_of_speech"] != "v" or event_ref not in properties:
                continue
            frame_ref = f"temporal-frame:{candidate.artifact_id}:{len(frames)}"
            event_properties = properties[event_ref]
            participants = [
                {
                    "role_ref": role,
                    "value_ref": value,
                    "form_refs": list(self._entity_forms(payload, value)),
                }
                for role, value in sorted(bindings.items())
                if role != "ARG0"
            ]
            frame = {
                "frame_ref": frame_ref,
                "event_ref": event_ref,
                "event_form_ref": f"external:mrs:{relation['predicate']}",
                "relation_ref": relation["relation_ref"],
                "label": relation["label"],
                "tense": event_properties.get("TENSE", "untensed"),
                "progressive": event_properties.get("PROG"),
                "perfect": event_properties.get("PERF"),
                "participants": participants,
                "is_main": event_ref == payload["proposition"]["index_ref"],
                "ers_constraints": self._ers_constraints(event_properties),
            }
            frames.append(frame)
            frame_by_event[event_ref] = frame_ref
            frame_by_label[relation["label"]] = frame_ref

        hcons = {row["high"]: row["low"] for row in payload["scope_constraints"]}

        def handle_frame(source_value: str) -> str | None:
            return frame_by_label.get(hcons.get(source_value, source_value))

        allen: list[dict[str, Any]] = []
        cues: list[dict[str, Any]] = []
        for relation in payload["relations"]:
            source_bindings = {
                row["role_ref"]: row["source_value"] for row in relation["bindings"]
            }
            predicate = relation["predicate"]
            if predicate in {"_before_x_h", "_after_x_h"}:
                left = handle_frame(source_bindings.get("ARG1", ""))
                right = handle_frame(source_bindings.get("ARG2", ""))
                if left and right:
                    if predicate == "_after_x_h":
                        left, right = right, left
                    allen.append(
                        {
                            "left_frame_ref": left,
                            "relation": "before",
                            "right_frame_ref": right,
                            "source_relation_ref": relation["relation_ref"],
                        }
                    )
            cue_kind = None
            if predicate == "_then_a_1":
                cue_kind = "after-prior-focus"
            elif predicate == "_before_p_state" and any(
                row["predicate"] == "_that_q_dem" for row in payload["relations"]
            ):
                cue_kind = "before-anaphoric-antecedent"
            elif predicate == "_late_a_for" and any(
                row["predicate"] == "more_comp" for row in payload["relations"]
            ):
                cue_kind = "after-prior-focus"
            if cue_kind:
                cues.append(
                    {
                        "cue_kind": cue_kind,
                        "source_relation_ref": relation["relation_ref"],
                        "native_predicate": predicate,
                        "main_frame_ref": next(
                            (row["frame_ref"] for row in frames if row["is_main"]), None
                        ),
                        "resolution_status": "unresolved-discourse-candidate",
                    }
                )

        states = [
            {
                "state_form_ref": row["state_form_ref"],
                "bearer_form_refs": list(self._entity_forms(payload, row["bearer_ref"])),
                "relation_ref": row["relation_ref"],
                "is_main": row["event_ref"] == payload["proposition"]["index_ref"],
            }
            for row in payload["state_candidates"]
            if row["bearer_ref"]
        ]
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="temporal-analysis",
                producer_id="relational-temporal-analyzer",
                producer_build=TEMPORAL_BUILD,
                configuration_digest=self.configuration_digest,
                mode=candidate.mode,
                session_id=candidate.session_id,
                wave=max(3, candidate.wave),
                parent_ids=(candidate.artifact_id,),
                observation_refs=candidate.observation_refs,
                context_refs=candidate.context_refs,
                source_anchors=tuple(thaw_json(row) for row in candidate.source_anchors),
                resource_cost={"wall_time_ms": elapsed, "frame_count": len(frames)},
                payload_native={
                    "source_candidate_ref": candidate.artifact_id,
                    "frames": frames,
                    "states": states,
                    "cues": cues,
                    "allen_constraints": allen,
                },
                payload_projection={"truth_committed": False},
                idempotency_key=f"temporal-analysis:{candidate.artifact_id}",
            )
        )
        self._analysis_cache[candidate.artifact_id] = artifact
        return artifact

    def group(
        self, branch_set: CognitiveArtifact, analyses: Iterable[CognitiveArtifact]
    ) -> CognitiveArtifact:
        rows = tuple(analyses)
        if branch_set.artifact_type != "situation-branch-set":
            raise ContractError("SYS-05: regroupement exige une situation L3")
        if any(row.artifact_type != "temporal-analysis" for row in rows):
            raise ContractError("SYS-05: analyse temporelle L3 invalide")
        situation = thaw_json(branch_set.payload_native)
        expected = {
            row["candidate_ref"] for row in situation["branches"]
        }
        actual = {
            thaw_json(row.payload_native)["source_candidate_ref"] for row in rows
        }
        if expected != actual:
            raise ContractError("SYS-05: couverture temporelle incomplète des branches")
        return self.arena.publish(
            ArtifactProposal(
                artifact_type="temporal-branch-set",
                producer_id="relational-temporal-analyzer",
                producer_build=TEMPORAL_BUILD,
                configuration_digest=self.configuration_digest,
                mode=branch_set.mode,
                session_id=branch_set.session_id,
                wave=max((row.wave for row in rows), default=branch_set.wave),
                parent_ids=(branch_set.artifact_id,) + tuple(row.artifact_id for row in rows),
                observation_refs=branch_set.observation_refs,
                context_refs=tuple(ref for row in rows for ref in row.context_refs),
                source_anchors=tuple(thaw_json(row) for row in branch_set.source_anchors),
                resource_cost={"analysis_count": len(rows)},
                payload_native={
                    "source_branch_set_ref": branch_set.artifact_id,
                    "analysis_refs": [row.artifact_id for row in rows],
                    "rejected_candidate_refs": situation["rejected_candidate_refs"],
                },
                payload_projection={"selected_ref": None, "truth_committed": False},
                status=ArtifactStatus.SUCCESS if rows else ArtifactStatus.FAILURE,
                losses=() if rows else ("no-temporal-analysis",),
                idempotency_key=f"temporal-branch-set:{branch_set.artifact_id}",
            )
        )

    @staticmethod
    def _ers_constraints(properties: dict[str, Any]) -> list[str]:
        tense = properties.get("TENSE")
        perfect = properties.get("PERF") == "+"
        if tense == "past" and perfect:
            return ["E<R", "R<S"]
        if tense == "past":
            return ["E=R", "R<S"]
        if tense == "pres" and perfect:
            return ["E<R", "R=S"]
        if tense == "pres":
            return ["E=R", "R=S"]
        if tense == "fut":
            return ["S<R", "R=E"]
        return []

    @staticmethod
    def _entity_forms(payload: dict[str, Any], value_ref: str) -> tuple[str, ...]:
        forms = set()
        for relation in payload["relations"]:
            if not any(
                row["role_ref"] == "ARG0" and row["value_ref"] == value_ref
                for row in relation["bindings"]
            ):
                continue
            if relation["part_of_speech"] in {"n", "u"}:
                forms.add(f"external:mrs:{relation['predicate']}")
            elif relation["predicate"] == "named" and relation.get("constant"):
                forms.add(f"external:mrs:named:{relation['constant']}")
        return tuple(sorted(forms))


class TemporalReasoner:
    def __init__(self, arena: ArtifactArena) -> None:
        self.arena = arena
        self._memory_cache: dict[tuple[str, ...], CognitiveArtifact] = {}
        self.configuration_digest = hashlib.sha256(
            canonical_json(
                {
                    "solver": "Z3",
                    "intervals": "proper",
                    "selection": "none",
                    "model_normalization": "minimum-radius-then-lexicographic",
                }
            ).encode()
        ).hexdigest()

    def remember(self, branch_sets: Iterable[CognitiveArtifact]) -> CognitiveArtifact:
        started = time.perf_counter()
        rows = tuple(branch_sets)
        if not rows or any(row.artifact_type != "temporal-branch-set" for row in rows):
            raise ContractError("SYS-05: mémoire exige des ensembles temporels L3")
        memory_key = tuple(row.artifact_id for row in rows)
        if memory_key in self._memory_cache:
            return self._memory_cache[memory_key]
        analyses = [
            self.arena.get(ref)
            for row in rows
            for ref in thaw_json(row.payload_native)["analysis_refs"]
        ]
        networks = []
        contradictions = []
        for analysis in analyses:
            distinct = self._solve(analysis, merge_repeated=False)
            networks.append(distinct)
            merged = self._solve(analysis, merge_repeated=True)
            if merged["merge_constraints"]:
                networks.append(merged)
            if not merged["consistent"]:
                contradictions.append(
                    {
                        "network_ref": merged["network_ref"],
                        "unsat_core": merged["unsat_core"],
                        "status": "represented-not-rewritten",
                    }
                )

        discourse_constraints = self._discourse_constraints(rows)
        state_history, state_constraints, queries = self._state_history(rows)
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        observation_refs = tuple(ref for row in rows for ref in row.observation_refs)
        anchors = {
            canonical_json(thaw_json(anchor)): thaw_json(anchor)
            for row in rows for anchor in row.source_anchors
        }
        artifact = self.arena.publish(
            ArtifactProposal(
                artifact_type="temporal-memory",
                producer_id="relational-temporal-reasoner",
                producer_build=TEMPORAL_BUILD,
                configuration_digest=self.configuration_digest,
                mode=rows[0].mode,
                session_id=rows[0].session_id,
                wave=max(row.wave for row in rows) + 1,
                parent_ids=tuple(row.artifact_id for row in rows),
                observation_refs=observation_refs,
                context_refs=tuple(sorted({ref for row in rows for ref in row.context_refs})),
                source_anchors=tuple(anchors[key] for key in sorted(anchors)),
                resource_cost={
                    "wall_time_ms": elapsed,
                    "network_count": len(networks),
                    "z3_version": z3.get_version_string(),
                },
                payload_native={
                    "networks": networks,
                    "discourse_constraints": discourse_constraints,
                    "state_constraints": state_constraints,
                    "state_history": state_history,
                    "queries": queries,
                    "contradictions": contradictions,
                },
                payload_projection={
                    "truth_committed": False,
                    "world_update_performed": False,
                    "selected_network_ref": None,
                },
                status=ArtifactStatus.PARTIAL if contradictions else ArtifactStatus.SUCCESS,
                losses=("contradictory-temporal-identity-branch",) if contradictions else (),
                idempotency_key="temporal-memory:" + hashlib.sha256(
                    canonical_json([row.artifact_id for row in rows]).encode()
                ).hexdigest(),
            )
        )
        self._memory_cache[memory_key] = artifact
        return artifact

    def _solve(self, analysis: CognitiveArtifact, *, merge_repeated: bool) -> dict[str, Any]:
        payload = thaw_json(analysis.payload_native)
        solver = z3.Solver()
        frames = payload["frames"]
        variables: dict[str, dict[str, Any]] = {}
        tracked: list[str] = []
        assertions: list[tuple[Any, str]] = []

        def track(expr: Any, label: str) -> None:
            safe = f"c{len(tracked)}_{hashlib.sha256(label.encode()).hexdigest()[:10]}"
            solver.assert_and_track(expr, z3.Bool(safe))
            tracked.append(safe + ":" + label)
            assertions.append((expr, label))

        for index, frame in enumerate(frames):
            vars_for_frame = {
                name: z3.Int(f"t_{analysis.artifact_id[-8:]}_{index}_{name}")
                for name in ("start", "end", "E", "R", "S")
            }
            variables[frame["frame_ref"]] = vars_for_frame
            track(vars_for_frame["start"] < vars_for_frame["end"], f"proper:{frame['frame_ref']}")
            track(vars_for_frame["E"] == vars_for_frame["start"], f"event-anchor:{frame['frame_ref']}")
            track(vars_for_frame["S"] == 0, f"speech-origin:{frame['frame_ref']}")
            for relation in frame["ers_constraints"]:
                left, op, right = relation[0], relation[1], relation[2]
                expr = vars_for_frame[left] < vars_for_frame[right] if op == "<" else vars_for_frame[left] == vars_for_frame[right]
                track(expr, f"ERS:{frame['frame_ref']}:{relation}")

        for item in payload["allen_constraints"]:
            left = variables[item["left_frame_ref"]]
            right = variables[item["right_frame_ref"]]
            track(left["end"] < right["start"], f"Allen:before:{item['source_relation_ref']}")

        merge_constraints = []
        if merge_repeated:
            by_signature: dict[str, list[dict[str, Any]]] = {}
            for frame in frames:
                signature = canonical_json(
                    [
                        frame["event_form_ref"],
                        [
                            [row["role_ref"], row["form_refs"]]
                            for row in frame["participants"]
                        ],
                    ]
                )
                by_signature.setdefault(signature, []).append(frame)
            for group in by_signature.values():
                for other in group[1:]:
                    first = variables[group[0]["frame_ref"]]
                    second = variables[other["frame_ref"]]
                    for name in ("start", "end", "E", "R"):
                        label = f"event-coreference:{group[0]['frame_ref']}:{other['frame_ref']}:{name}"
                        track(first[name] == second[name], label)
                        merge_constraints.append(label)

        result = solver.check()
        consistent = result == z3.sat
        model_values = {}
        if consistent:
            model_values = self._canonical_model(assertions, variables)
        unsat_core: list[str] = []
        if not consistent:
            # Z3 peut retourner différents noyaux parmi plusieurs noyaux valides.
            # Une réduction gloutonne dans l'ordre canonique rend l'explication
            # reproductible sans modifier le verdict de satisfiabilité.
            reduced = list(assertions)
            for index in range(len(reduced) - 1, -1, -1):
                candidate = reduced[:index] + reduced[index + 1 :]
                probe = z3.Solver()
                probe.add(*(expr for expr, _ in candidate))
                if probe.check() == z3.unsat:
                    reduced = candidate
            unsat_core = [label for _, label in reduced]
        hypothesis = "merge-repeated-event-descriptions" if merge_repeated else "distinct-event-occurrences"
        return {
            "network_ref": f"network:{analysis.artifact_id}:{hypothesis}",
            "source_analysis_ref": analysis.artifact_id,
            "identity_hypothesis": hypothesis,
            "consistent": consistent,
            "frames": frames,
            "allen_constraints": payload["allen_constraints"],
            "merge_constraints": merge_constraints,
            "model": model_values,
            "unsat_core": unsat_core,
            "selected": False,
        }

    @staticmethod
    def _canonical_model(
        assertions: list[tuple[Any, str]],
        variables: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, int]]:
        """Return the same compact satisfying assignment for every replay.

        A raw Z3 model is deliberately under-specified: two solver calls may
        choose different integers for the same satisfiable temporal network.
        We first find the smallest symmetric integer radius containing a
        solution, then choose the lexicographically smallest value of each
        variable while preserving satisfiability.
        """
        ordered = [
            (frame_ref, name, variables[frame_ref][name])
            for frame_ref in sorted(variables)
            for name in ("start", "end", "E", "R", "S")
        ]
        if not ordered:
            return {}
        base = [expr for expr, _ in assertions]
        radius = 1
        while True:
            probe = z3.Solver()
            probe.add(*base)
            probe.add(
                *(z3.And(value >= -radius, value <= radius) for _, _, value in ordered)
            )
            if probe.check() == z3.sat:
                break
            radius *= 2

        fixed: list[Any] = [
            z3.And(value >= -radius, value <= radius) for _, _, value in ordered
        ]
        chosen: dict[tuple[str, str], int] = {}
        for frame_ref, name, value in ordered:
            low, high = -radius, radius
            while low < high:
                middle = (low + high) // 2
                probe = z3.Solver()
                probe.add(*base, *fixed, value <= middle)
                if probe.check() == z3.sat:
                    high = middle
                else:
                    low = middle + 1
            fixed.append(value == low)
            chosen[(frame_ref, name)] = low
        return {
            frame_ref: {
                name: chosen[(frame_ref, name)]
                for name in ("start", "end", "E", "R", "S")
            }
            for frame_ref in variables
        }

    def _discourse_constraints(self, rows: tuple[CognitiveArtifact, ...]) -> list[dict[str, Any]]:
        result = []
        prior_frames: list[str] = []
        for branch_set in rows:
            payload = thaw_json(branch_set.payload_native)
            analyses = [self.arena.get(ref) for ref in payload["analysis_refs"]]
            current_main = sorted(
                {
                    frame["frame_ref"]
                    for analysis in analyses
                    for frame in thaw_json(analysis.payload_native)["frames"]
                    if frame["is_main"]
                }
            )
            cues = [
                cue
                for analysis in analyses
                for cue in thaw_json(analysis.payload_native)["cues"]
            ]
            for cue in cues:
                candidates = prior_frames[-2:] if "anaphoric" in cue["cue_kind"] else prior_frames[-1:]
                relation = "before" if cue["cue_kind"].startswith("before") else "after"
                result.append(
                    {
                        "cue": cue,
                        "current_frame_refs": current_main,
                        "antecedent_candidate_refs": candidates,
                        "relation": relation,
                        "selected_antecedent_ref": None,
                    }
                )
            prior_frames.extend(current_main)
        return result

    def _state_history(
        self, rows: tuple[CognitiveArtifact, ...]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        history = []
        constraints = []
        active: dict[str, dict[str, Any]] = {}
        queries = []
        for position, branch_set in enumerate(rows):
            analyses = [
                self.arena.get(ref)
                for ref in thaw_json(branch_set.payload_native)["analysis_refs"]
            ]
            alternatives = [
                state
                for analysis in analyses
                for state in thaw_json(analysis.payload_native)["states"]
                if state["is_main"]
            ]
            signatures = {
                (bearer, state["state_form_ref"])
                for state in alternatives
                for bearer in state["bearer_form_refs"]
            }
            for bearer, state_form in sorted(signatures):
                previous = active.get(bearer)
                opening_constraint_ref = None
                if previous and previous["state_form_ref"] != state_form:
                    opening_constraint_ref = (
                        f"state-order:{previous['support_temporal_branch_ref']}:"
                        f"{branch_set.artifact_id}:{bearer}"
                    )
                    constraints.append(
                        {
                            "constraint_ref": opening_constraint_ref,
                            "left_temporal_branch_ref": previous[
                                "support_temporal_branch_ref"
                            ],
                            "relation": "before",
                            "right_temporal_branch_ref": branch_set.artifact_id,
                            "basis": "observable-source-order",
                        }
                    )
                    previous["closed_at_source_position"] = position
                    previous["closed_by_constraint_ref"] = opening_constraint_ref
                record = {
                    "bearer_form_ref": bearer,
                    "state_form_ref": state_form,
                    "opened_at_source_position": position,
                    "closed_at_source_position": None,
                    "opened_by_constraint_ref": opening_constraint_ref,
                    "closed_by_constraint_ref": None,
                    "support_temporal_branch_ref": branch_set.artifact_id,
                    "status": "observed-state-report",
                }
                active[bearer] = record
                history.append(record)
                queries.append(
                    {
                        "source_position": position,
                        "bearer_form_ref": bearer,
                        "state_form_ref": state_form,
                        "support_ref": branch_set.artifact_id,
                        "ordering_constraint_ref": opening_constraint_ref,
                    }
                )
        return history, constraints, queries
