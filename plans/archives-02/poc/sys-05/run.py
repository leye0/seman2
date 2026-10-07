#!/usr/bin/env python3
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "poc/sys-05/output"
SOURCE = Path("data/curriculum/sys_05_temporal.txt")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import ArtifactArena, thaw_json  # noqa: E402
from seman2_runtime.contracts import ContractError  # noqa: E402
from seman2_runtime.formal_composition import GenericMRSComposer  # noqa: E402
from seman2_runtime.hypothesis_system import HypothesisManager  # noqa: E402
from seman2_runtime.low_level_system import (  # noqa: E402
    AceErgAnalyzer,
    AnalysisOrchestrator,
    ExperienceGateway,
    LowLevelPolicy,
    lineage_manifest,
    sha256_file,
)
from seman2_runtime.temporal_system import (  # noqa: E402
    RelationalTemporalAnalyzer,
    TemporalReasoner,
    build_temporal_registry,
)


def write_json(name: str, value: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def rejects_contract(operation: Callable[[], object]) -> bool:
    try:
        operation()
    except ContractError:
        return True
    return False


def independently_validate_model(network: dict[str, object]) -> bool:
    if not network["consistent"]:
        return False
    model = network["model"]
    for frame in network["frames"]:
        values = model[frame["frame_ref"]]
        if not values["start"] < values["end"] or values["E"] != values["start"] or values["S"] != 0:
            return False
        for relation in frame["ers_constraints"]:
            left, operator, right = relation[0], relation[1], relation[2]
            if operator == "<" and not values[left] < values[right]:
                return False
            if operator == "=" and not values[left] == values[right]:
                return False
    for constraint in network["allen_constraints"]:
        left = model[constraint["left_frame_ref"]]
        right = model[constraint["right_frame_ref"]]
        if not left["end"] < right["start"]:
            return False
    if network["identity_hypothesis"] == "merge-repeated-event-descriptions":
        groups: dict[str, list[dict[str, object]]] = {}
        for frame in network["frames"]:
            signature = json.dumps(
                [
                    frame["event_form_ref"],
                    [[row["role_ref"], row["form_refs"]] for row in frame["participants"]],
                ],
                sort_keys=True,
            )
            groups.setdefault(signature, []).append(frame)
        for group in groups.values():
            if len(group) < 2:
                continue
            first = model[group[0]["frame_ref"]]
            if any(
                any(model[row["frame_ref"]][key] != first[key] for key in ("start", "end", "E", "R"))
                for row in group[1:]
            ):
                return False
    return True


def stable_view(arena: ArtifactArena) -> list[dict[str, object]]:
    return [
        {
            "artifact_id": row.artifact_id,
            "artifact_type": row.artifact_type,
            "producer_id": row.producer_id,
            "producer_revision": row.producer_build,
            "configuration_digest": row.configuration_digest,
            "parent_ids": list(row.parent_ids),
            "observation_refs": list(row.observation_refs),
            "context_refs": list(row.context_refs),
            "source_anchors": [thaw_json(anchor) for anchor in row.source_anchors],
            "payload_native": thaw_json(row.payload_native),
            "payload_projection": thaw_json(row.payload_projection),
            "status": row.status.value,
            "losses": list(row.losses),
        }
        for row in arena.query()
    ]


def execute(source_root: Path, *, project_root: Path) -> dict[str, object]:
    policy = LowLevelPolicy(
        max_sentence_chars=180,
        max_candidates=3,
        worker_timeout_seconds=30.0,
        worker_memory_mib=1_024,
        max_observations_per_wave=12,
    )
    arena = ArtifactArena(build_temporal_registry())
    gateway = ExperienceGateway(
        arena, session_id="sys-05", policy=policy, source_root=source_root
    )
    pairs = gateway.ingest_file(
        source_root / SOURCE,
        experience_prefix="sys-05",
        max_observations=8,
    )
    observations = tuple(row[1] for row in pairs)
    l1, contributions = AnalysisOrchestrator(policy=policy).execute(
        observations,
        AceErgAnalyzer(arena, project_root=project_root, policy=policy),
    )
    l2, candidates = GenericMRSComposer(arena).compose_ledger(l1)
    by_observation = {row.artifact_id: [] for row in observations}
    for candidate in candidates:
        contribution = arena.get(candidate.parent_ids[0])
        by_observation[contribution.parent_ids[0]].append(candidate)
    manager = HypothesisManager(arena)
    situations = tuple(
        manager.group(by_observation[row.artifact_id]) for row in observations
    )

    temporal = RelationalTemporalAnalyzer(arena)
    temporal_sets = []
    analyses = []
    for situation in situations:
        payload = thaw_json(situation.payload_native)
        local = tuple(
            temporal.analyze(arena.get(branch["candidate_ref"]))
            for branch in payload["branches"]
        )
        analyses.extend(local)
        temporal_sets.append(temporal.group(situation, local))
    reasoner = TemporalReasoner(arena)
    memory = reasoner.remember(temporal_sets)
    return {
        "arena": arena,
        "policy": policy,
        "observations": observations,
        "l1": l1,
        "contributions": contributions,
        "l2": l2,
        "candidates": candidates,
        "situations": situations,
        "analyses": tuple(analyses),
        "temporal_sets": tuple(temporal_sets),
        "temporal_analyzer": temporal,
        "temporal_reasoner": reasoner,
        "memory": memory,
    }


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    run = execute(ROOT, project_root=ROOT)
    arena = run["arena"]
    memory = run["memory"]
    payload = thaw_json(memory.payload_native)
    networks = payload["networks"]
    consistent = [row for row in networks if row["consistent"]]
    inconsistent = [row for row in networks if not row["consistent"]]
    analyses = run["analyses"]
    analysis_payloads = [thaw_json(row.payload_native) for row in analyses]
    frames = [frame for row in analysis_payloads for frame in row["frames"]]
    cues = [cue for row in analysis_payloads for cue in row["cues"]]
    allen = [item for row in analysis_payloads for item in row["allen_constraints"]]

    with tempfile.TemporaryDirectory(prefix="seman2-sys05-replay-") as temp_name:
        replay_root = Path(temp_name)
        destination = replay_root / SOURCE
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / SOURCE, destination)
        replay = execute(replay_root, project_root=ROOT)
        replay_equal = stable_view(arena) == stable_view(replay["arena"])

    restored = ArtifactArena.restore(build_temporal_registry(), arena.as_dict())
    temporal_source = (ROOT / "seman2_runtime/temporal_system.py").read_text(
        encoding="utf-8"
    ).lower()
    box_history = [
        row
        for row in payload["state_history"]
        if row["bearer_form_ref"] == "external:mrs:_box_n_of"
    ]
    box_queries = [
        row
        for row in payload["queries"]
        if row["bearer_form_ref"] == "external:mrs:_box_n_of"
    ]
    discourse = payload["discourse_constraints"]
    state_constraints = payload["state_constraints"]
    anaphoric = [row for row in discourse if "anaphoric" in row["cue"]["cue_kind"]]
    ancestry_types = {
        row.artifact_type for row in arena.ancestry(memory.artifact_id)
    }
    artifact_count_before_repeat = len(arena.query())
    repeated_analysis = run["temporal_analyzer"].analyze(
        arena.get(analyses[0].parent_ids[0])
    )
    repeated_memory = run["temporal_reasoner"].remember(run["temporal_sets"])
    artifact_count_after_repeat = len(arena.query())
    invalid_analysis_rejected = rejects_contract(
        lambda: run["temporal_analyzer"].analyze(memory)
    )
    invalid_memory_rejected = rejects_contract(
        lambda: run["temporal_reasoner"].remember((analyses[0],))
    )

    checks = {
        "closed_real_L0_to_L3_stock_is_exclusive_input": (
            run["l1"].closed
            and run["l2"].closed
            and run["l1"].recompute_digest() == run["l1"].ledger_digest
            and run["l2"].recompute_digest() == run["l2"].batch_digest
            and len(run["observations"]) == 8
            and len(run["situations"]) == 8
        ),
        "every_temporal_analysis_consumes_exact_real_L2": (
            len(analyses) == sum(
                len(thaw_json(row.payload_native)["branches"])
                for row in run["situations"]
            )
            and all(
                len(row.parent_ids) == 1
                and arena.get(row.parent_ids[0]).artifact_type == "composed-candidate"
                and thaw_json(row.payload_native)["source_candidate_ref"]
                == row.parent_ids[0]
                for row in analyses
            )
        ),
        "all_parse_alternatives_remain_unselected": all(
            thaw_json(row.payload_projection)["selected_ref"] is None
            and len(thaw_json(row.payload_native)["analysis_refs"])
            == len(thaw_json(arena.get(row.parent_ids[0]).payload_native)["branches"])
            for row in run["temporal_sets"]
        ),
        "reichenbach_ERS_comes_from_native_tense_and_aspect": (
            any(
                frame["tense"] == "past"
                and frame["perfect"] == "+"
                and frame["ers_constraints"] == ["E<R", "R<S"]
                for frame in frames
            )
            and any(
                frame["tense"] == "past"
                and frame["perfect"] == "-"
                and frame["ers_constraints"] == ["E=R", "R<S"]
                for frame in frames
            )
        ),
        "native_before_after_relations_become_Allen_constraints": (
            len(allen) >= 2
            and all(item["relation"] == "before" for item in allen)
            and all(item["source_relation_ref"] for item in allen)
        ),
        "then_later_and_before_that_remain_attributed_candidates": (
            {cue["native_predicate"] for cue in cues}
            >= {"_then_a_1", "_late_a_for", "_before_p_state"}
            and all(cue["resolution_status"] == "unresolved-discourse-candidate" for cue in cues)
        ),
        "temporal_anaphora_preserves_multiple_antecedents": (
            bool(anaphoric)
            and any(len(row["antecedent_candidate_refs"]) >= 2 for row in anaphoric)
            and all(row["selected_antecedent_ref"] is None for row in anaphoric)
        ),
        "Z3_solves_distinct_event_networks": (
            bool(consistent)
            and all(row["model"] for row in consistent if row["frames"])
            and all(not row["selected"] for row in consistent)
        ),
        "independent_oracle_validates_every_Z3_model": all(
            independently_validate_model(row) for row in consistent
        ),
        "contradictory_coreference_branch_is_preserved": (
            bool(inconsistent)
            and bool(payload["contradictions"])
            and all(row["unsat_core"] for row in inconsistent)
            and all(
                any(item.startswith("Allen:before:") for item in row["unsat_core"])
                and any(item.startswith("event-coreference:") for item in row["unsat_core"])
                for row in inconsistent
            )
            and all(
                row["status"] == "represented-not-rewritten"
                for row in payload["contradictions"]
            )
        ),
        "identity_ambiguity_keeps_consistent_and_inconsistent_branches": any(
            left["source_analysis_ref"] == right["source_analysis_ref"]
            and left["consistent"]
            and not right["consistent"]
            for left in networks
            for right in networks
        ),
        "state_persistence_changes_only_on_real_state_reports": (
            [row["state_form_ref"] for row in box_history]
            == [
                "external:mrs:_closed_a_1",
                "external:mrs:_open_a_to",
                "external:mrs:_closed_a_1",
            ]
            and box_history[0]["closed_at_source_position"]
            == box_history[1]["opened_at_source_position"]
            and box_history[1]["closed_at_source_position"]
            == box_history[2]["opened_at_source_position"]
            and box_history[2]["closed_at_source_position"] is None
            and len(state_constraints) >= 2
            and all(row["basis"] == "observable-source-order" for row in state_constraints)
            and all(
                row["closed_by_constraint_ref"]
                in {constraint["constraint_ref"] for constraint in state_constraints}
                for row in box_history[:-1]
            )
        ),
        "temporal_queries_change_with_produced_state_constraints": (
            [row["state_form_ref"] for row in box_queries]
            == [
                "external:mrs:_closed_a_1",
                "external:mrs:_open_a_to",
                "external:mrs:_closed_a_1",
            ]
            and all(row["support_ref"] for row in box_queries)
            and all(
                row["ordering_constraint_ref"] is not None
                for row in box_queries[1:]
            )
        ),
        "no_surface_time_normalizer_participates": (
            "heideltime" not in temporal_source
            and "duckling" not in temporal_source
            and all(
                row.producer_id
                not in {"heideltime", "duckling", "heideltime-worker", "duckling-worker"}
                for row in arena.query()
            )
        ),
        "memory_selects_no_network_truth_or_world_update": (
            thaw_json(memory.payload_projection)["selected_network_ref"] is None
            and thaw_json(memory.payload_projection)["truth_committed"] is False
            and thaw_json(memory.payload_projection)["world_update_performed"] is False
            and all(not row["selected"] for row in networks)
        ),
        "all_temporal_artifacts_are_contextual_and_costed": all(
            row.context_refs and thaw_json(row.resource_cost)
            for artifact_type in ("temporal-analysis", "temporal-branch-set", "temporal-memory")
            for row in arena.query(artifact_type=artifact_type)
        ),
        "temporal_services_are_idempotent": (
            repeated_analysis.artifact_id == analyses[0].artifact_id
            and repeated_memory.artifact_id == memory.artifact_id
            and artifact_count_before_repeat == artifact_count_after_repeat
        ),
        "invalid_cross_layer_inputs_are_rejected": (
            invalid_analysis_rejected and invalid_memory_rejected
        ),
        "temporal_memory_ancestry_reaches_real_L0": {
            "experience-occurrence",
            "observation",
            "analysis-contribution",
            "composed-candidate",
            "situation-branch-set",
            "temporal-analysis",
            "temporal-branch-set",
            "temporal-memory",
        } <= ancestry_types,
        "location_independent_full_replay_is_identical": replay_equal,
        "checkpoint_restore_is_exact": stable_view(restored) == stable_view(arena),
    }

    effects = [
        {
            "consumer_artifact_ref": row.artifact_id,
            "input_factor_ref": parent,
            "producer_artifact_ref": row.artifact_id,
            "operation": row.producer_id,
            "effect_on_output": f"{row.artifact_type}:{row.status.value}",
            "activation_or_weight_change": "attributed temporal material added",
            "context_ref": list(row.context_refs),
            "reason_if_ignored": None,
        }
        for row in arena.query()
        if row.artifact_type in {"temporal-analysis", "temporal-branch-set", "temporal-memory"}
        for parent in row.parent_ids
    ]
    lineage = lineage_manifest(
        arena, real_source_refs=[SOURCE.as_posix()], causal_effects=effects
    )
    all_passed = all(checks.values())
    results = {
        "verdict": "GO" if all_passed else "NO-GO",
        "scope": "real L2/L3 temporal material to attributed E/R/S, Allen/Z3 networks and temporal memory",
        "checks": checks,
        "counts": {
            "source_experiences": len(run["observations"]),
            "L2_candidates": len(run["candidates"]),
            "temporal_analyses": len(analyses),
            "event_frames": len(frames),
            "native_allen_constraints": len(allen),
            "discourse_constraints": len(discourse),
            "networks": len(networks),
            "consistent_networks": len(consistent),
            "inconsistent_networks": len(inconsistent),
            "state_reports": len(payload["state_history"]),
        },
        "demonstrated": [
            "native tense/aspect to attributed Reichenbach E/R/S",
            "native before/after handles to Allen constraints checked by Z3",
            "unselected parse, anaphora, and event-coreference alternatives",
            "explicit preserved contradiction with unsat core",
            "state persistence and changing temporal answers from real L2 states",
            "location-independent replay and exact snapshot restoration",
        ],
        "not_demonstrated": [
            "calendar normalization",
            "cross-experience identity commitment",
            "dialogue",
        ],
    }
    write_json("results.json", results)
    write_json("summary.json", {"verdict": results["verdict"], "checks_passed": sum(checks.values()), "checks_total": len(checks), **results["counts"]})
    write_json("ledger.json", arena.as_dict())
    write_json("lineage.json", lineage)
    write_json("temporal-memory.json", payload)
    write_json("closed-batches.json", {"L1": run["l1"].as_dict(), "L2": run["l2"].as_dict()})
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "pydelphin": importlib.metadata.version("pydelphin"),
            "z3_solver": importlib.metadata.version("z3-solver"),
            "registry_digest": arena.registry.digest,
            "policy": run["policy"].__dict__,
            "ace_sha256": sha256_file(ROOT / ".local/bin/ace"),
            "erg_sha256": sha256_file(ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"),
            "source_sha256": sha256_file(ROOT / SOURCE),
        },
    )
    print(json.dumps(results, ensure_ascii=False))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
