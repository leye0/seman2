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
OUTPUT = ROOT / "poc/sys-07/output"
SOURCE = Path("data/curriculum/sys_06_identity_discourse.txt")
WORLD = "ctx:sys-07:world"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import ArtifactArena, thaw_json  # noqa: E402
from seman2_runtime.contracts import ContractError  # noqa: E402
from seman2_runtime.developmental_core import DevelopmentalCore  # noqa: E402
from seman2_runtime.discourse_identity_system import (  # noqa: E402
    ContextualIdentityEngine,
    ContextualMentionExtractor,
)
from seman2_runtime.formal_composition import GenericMRSComposer  # noqa: E402
from seman2_runtime.hypothesis_system import HypothesisManager  # noqa: E402
from seman2_runtime.knowledge_system import KnowledgeAdmissionEngine  # noqa: E402
from seman2_runtime.low_level_system import (  # noqa: E402
    AceErgAnalyzer,
    AnalysisOrchestrator,
    ExperienceGateway,
    LowLevelPolicy,
    lineage_manifest,
    sha256_file,
)
from seman2_runtime.soar_control_system import (  # noqa: E402
    BoundedCognitiveRetrieval,
    ControlGoalBuilder,
    SoarExecutive,
    build_soar_control_registry,
)
from seman2_runtime.temporal_system import RelationalTemporalAnalyzer, TemporalReasoner  # noqa: E402


def write_json(name: str, value: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rejects_contract(operation: Callable[[], object]) -> bool:
    try:
        operation()
    except ContractError:
        return True
    return False


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
        max_observations_per_wave=10,
    )
    arena = ArtifactArena(build_soar_control_registry())
    gateway = ExperienceGateway(arena, session_id="sys-07", policy=policy, source_root=source_root)
    pairs = gateway.ingest_file(source_root / SOURCE, experience_prefix="sys-07", max_observations=6)
    observations = tuple(row[1] for row in pairs)
    l1, contributions = AnalysisOrchestrator(policy=policy).execute(
        observations, AceErgAnalyzer(arena, project_root=project_root, policy=policy)
    )
    l2, candidates = GenericMRSComposer(arena).compose_ledger(l1)
    by_observation = {row.artifact_id: [] for row in observations}
    for candidate in candidates:
        contribution = arena.get(candidate.parent_ids[0])
        by_observation[contribution.parent_ids[0]].append(candidate)
    hypotheses = HypothesisManager(arena)
    situations = tuple(hypotheses.group(by_observation[row.artifact_id]) for row in observations)

    knowledge = KnowledgeAdmissionEngine(arena, context_ref=WORLD)
    episodes = []
    for situation in situations:
        knowledge.observe(situation)
        episodes.append(knowledge._episode_artifacts[situation.artifact_id])

    temporal_analyzer = RelationalTemporalAnalyzer(arena)
    temporal_sets = []
    for situation in situations:
        local = tuple(
            temporal_analyzer.analyze(arena.get(branch["candidate_ref"]))
            for branch in thaw_json(situation.payload_native)["branches"]
        )
        temporal_sets.append(temporal_analyzer.group(situation, local))
    temporal_memory = TemporalReasoner(arena).remember(temporal_sets)

    extractor = ContextualMentionExtractor(arena, world_context_ref=WORLD)
    identity = ContextualIdentityEngine(arena, world_context_ref=WORLD, discourse_ref="discourse:sys-07")
    mention_artifacts = []
    beams = []
    for index, situation in enumerate(situations):
        local = tuple(
            extractor.extract(arena.get(branch["candidate_ref"]))
            for branch in thaw_json(situation.payload_native)["branches"]
        )
        mention_artifacts.extend(local)
        beams.append(identity.resolve_observation(situation, local, temporal_index=index))
    discourse_memory = identity.finalize(episode_memories=episodes, temporal_memory=temporal_memory)

    target_beam = beams[-1]
    goal_builder = ControlGoalBuilder(arena, beam_bound=2)
    goal = goal_builder.build(target_beam)
    retrieval_service = BoundedCognitiveRetrieval(arena, maximum_results=2)
    executive = SoarExecutive(
        arena,
        project_root=project_root,
        beam_bound=2,
        memory_limit_mib=2_048,
        timeout_seconds=30.0,
    )
    retrieval, decision = executive.decide(
        goal,
        retrieval_service,
        identity_beam=target_beam,
        episode_memories=episodes,
        temporal_memory=temporal_memory,
        discourse_memory=discourse_memory,
    )
    return locals()


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    run = execute(ROOT, project_root=ROOT)
    arena = run["arena"]
    goal = run["goal"]
    retrieval = run["retrieval"]
    decision = run["decision"]
    goal_payload = thaw_json(goal.payload_native)
    retrieval_payload = thaw_json(retrieval.payload_native)
    decision_payload = thaw_json(decision.payload_native)
    decision_projection = thaw_json(decision.payload_projection)
    target_payload = thaw_json(run["target_beam"].payload_native)
    target_decision = next(
        row for row in target_payload["decisions"]
        if row["mention_ref"] == goal_payload["mention_ref"]
    )
    actual_candidates = {
        row["candidate_ref"] for row in target_decision["candidates"]
        if not row["creates_new_identity"]
    }
    active_refs = [row["candidate_ref"] for row in goal_payload["candidate_beam"]]
    active_identity = {
        row["candidate_ref"]: row["identity_ref"] for row in goal_payload["candidate_beam"]
    }
    wm = decision_payload["soar_trace"]["working_memory"]
    all_l4_refs = {
        *(row.artifact_id for row in run["episodes"]),
        run["temporal_memory"].artifact_id,
        run["discourse_memory"].artifact_id,
    }

    with tempfile.TemporaryDirectory(prefix="seman2-sys07-replay-") as temp_name:
        replay_root = Path(temp_name)
        destination = replay_root / SOURCE
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / SOURCE, destination)
        replay = execute(replay_root, project_root=ROOT)
        replay_equal = stable_view(arena) == stable_view(replay["arena"])

    restored = ArtifactArena.restore(build_soar_control_registry(), arena.as_dict())
    artifacts_before = len(arena.query())
    repeated_retrieval, repeated_decision = run["executive"].decide(
        goal,
        run["retrieval_service"],
        identity_beam=run["target_beam"],
        episode_memories=run["episodes"],
        temporal_memory=run["temporal_memory"],
        discourse_memory=run["discourse_memory"],
    )
    artifacts_after = len(arena.query())
    invalid_goal_rejected = rejects_contract(lambda: run["goal_builder"].build(run["temporal_memory"]))
    invalid_retrieval_rejected = rejects_contract(
        lambda: run["retrieval_service"].retrieve(
            goal,
            episode_memories=(run["discourse_memory"],),
            temporal_memory=run["temporal_memory"],
            discourse_memory=run["discourse_memory"],
            depth=1,
        )
    )
    ancestry_types = {row.artifact_type for row in arena.ancestry(decision.artifact_id)}
    checks = {
        "closed_real_L0_to_L3_stock_is_exclusive_input": (
            run["l1"].closed and run["l2"].closed
            and run["l1"].recompute_digest() == run["l1"].ledger_digest
            and run["l2"].recompute_digest() == run["l2"].batch_digest
            and len(run["observations"]) == 6
        ),
        "real_SYS03_SYS05_SYS06_L4_memories_are_consumed": (
            len(run["episodes"]) == 6
            and run["temporal_memory"].artifact_type == "temporal-memory"
            and run["discourse_memory"].artifact_type == "discourse-memory"
            and all(ref in retrieval.parent_ids for ref in all_l4_refs)
        ),
        "goal_is_derived_from_real_ambiguous_identity_beam": (
            goal.parent_ids == (run["target_beam"].artifact_id,)
            and target_decision["status"] == "ambiguous"
            and set(active_refs) <= actual_candidates
        ),
        "goal_projection_is_bounded_and_keeps_inactive_candidates_external": (
            len(active_refs) == 2
            and len(goal_payload["inactive_candidate_refs"]) >= 1
            and not set(active_refs) & set(goal_payload["inactive_candidate_refs"])
        ),
        "real_SML_cycle_reports_an_impasse_operator": (
            decision_payload["initial_operator"]["action"] == "request-retrieval"
            and decision_payload["initial_operator"]["next_depth"] == 1
            and "1 rule fired" in decision_payload["initial_operator"]["cycle_trace"]
        ),
        "impasse_cycle_sees_ambiguity_and_cannot_select_early": (
            "resolution-status ambiguous"
            in decision_payload["initial_operator"]["working_memory"]
            and "selected-candidate-ref"
            not in decision_payload["initial_operator"]["output"]
        ),
        "impasse_causes_a_new_real_L4_retrieval_artifact": (
            retrieval.created_sequence > goal.created_sequence
            and retrieval_payload["depth"] == 1
            and retrieval_payload["goal_ref"] == goal_payload["goal_ref"]
            and bool(retrieval_payload["hits"])
        ),
        "retrieval_indexes_every_required_memory_family": (
            retrieval_payload["indexed_counts"]["episodes"] == 6
            and retrieval_payload["indexed_counts"]["temporal_networks"] > 0
            and retrieval_payload["indexed_counts"]["identity_profiles"] == 4
        ),
        "retrieval_is_bounded_and_uses_no_raw_source": (
            len(retrieval_payload["hits"]) <= 2
            and retrieval_payload["request"]["maximum_results"] == 2
            and thaw_json(retrieval.payload_projection)["raw_source_accessed"] is False
            and retrieval_payload["work_units"] < 64
        ),
        "retrieval_hits_have_real_L4_support_and_explanations": all(
            row["support_refs"] and row["explanation"]
            and run["discourse_memory"].artifact_id in row["support_refs"]
            and run["temporal_memory"].artifact_id in row["support_refs"]
            and row["influence_factors"]["episode_support_count"] > 0
            and row["influence_factors"]["temporal_memory_support"] is True
            and row["influence_factors"]["discourse_memory_support"] is True
            for row in retrieval_payload["hits"]
        ),
        "retrieval_top_hit_supports_the_selected_real_candidate": (
            retrieval_payload["hits"][0]["content_ref"]
            == active_identity[decision_payload["selected_candidate_ref"]]
        ),
        "second_real_SML_cycle_selects_after_retrieval": (
            decision_payload["final_operator"] == "select-candidate"
            and "1 rule fired" in decision_payload["soar_trace"]["cycle_trace"]
            and bool(decision_payload["soar_trace"]["soar_version"])
        ),
        "decision_cites_exactly_every_compared_candidate": (
            set(decision_payload["compared_candidate_refs"]) == set(active_refs)
            and decision_payload["selected_candidate_ref"] in active_refs
        ),
        "working_memory_contains_only_the_bounded_candidate_projection": (
            all(ref in wm for ref in active_refs)
            and all(ref not in wm for ref in goal_payload["inactive_candidate_refs"])
        ),
        "global_L4_store_is_not_copied_into_Soar": (
            all(ref not in wm for ref in all_l4_refs)
            and decision_projection["persistent_store_copied_to_soar"] is False
        ),
        "only_returned_retrieval_hits_enter_Soar": (
            all(row["content_ref"] in wm for row in retrieval_payload["hits"])
            and len(decision_payload["working_memory_projection"]["retrieval_hit_refs"]) == len(retrieval_payload["hits"])
        ),
        "physical_and_cognitive_budgets_are_explicitly_enforced": (
            thaw_json(goal.resource_cost)["beam_bound"] == 2
            and thaw_json(retrieval.resource_cost)["returned_hits"] <= 2
            and thaw_json(decision.resource_cost)["projected_candidates"] == 2
            and thaw_json(decision.resource_cost)["memory_limit_mib"] == 2_048
        ),
        "Soar_operational_choice_does_not_commit_identity_truth": (
            decision_projection["truth_committed"] is False
            and target_decision["selected_identity_ref"] is None
        ),
        "decision_parents_are_the_exact_goal_retrieval_and_beam": (
            decision.parent_ids == (goal.artifact_id, retrieval.artifact_id, run["target_beam"].artifact_id)
        ),
        "control_services_are_idempotent": (
            repeated_retrieval.artifact_id == retrieval.artifact_id
            and repeated_decision.artifact_id == decision.artifact_id
            and artifacts_before == artifacts_after
        ),
        "invalid_cross_layer_inputs_are_rejected": invalid_goal_rejected and invalid_retrieval_rejected,
        "decision_ancestry_reaches_every_real_layer": {
            "experience-occurrence", "observation", "analysis-contribution",
            "composed-candidate", "situation-branch-set", "episode-memory",
            "temporal-memory", "identity-beam", "discourse-memory",
            "control-goal", "retrieval-result", "soar-control-decision",
        } <= ancestry_types,
        "location_independent_full_replay_is_identical": replay_equal,
        "arena_restore_is_exact": stable_view(restored) == stable_view(arena),
    }
    operation_by_type = {
        "control-goal": "derive control goal from unresolved real beam",
        "retrieval-result": "bounded cognitive retrieval after Soar impasse",
        "soar-control-decision": "real SML operator selection",
    }
    effects = [
        {
            "consumer_artifact_ref": row.artifact_id,
            "input_factor_ref": parent,
            "producer_artifact_ref": row.artifact_id,
            "operation": operation_by_type[row.artifact_type],
            "effect_on_output": f"{row.artifact_type}:{row.status.value}",
            "activation_or_weight_change": "bounded projection or operational selection",
            "context_ref": list(row.context_refs),
            "reason_if_ignored": None,
        }
        for row in arena.query()
        if row.artifact_type in operation_by_type
        for parent in row.parent_ids
    ]
    lineage = lineage_manifest(arena, real_source_refs=[SOURCE.as_posix()], causal_effects=effects)
    passed = all(checks.values())
    results = {
        "verdict": "GO" if passed else "NO-GO",
        "scope": "real L3/L4 cognitive stock through bounded retrieval and a real two-cycle Soar SML decision",
        "checks": checks,
        "counts": {
            "source_experiences": len(run["observations"]),
            "L2_candidates": len(run["candidates"]),
            "episode_memories": len(run["episodes"]),
            "identity_profiles": retrieval_payload["indexed_counts"]["identity_profiles"],
            "projected_candidates": len(active_refs),
            "inactive_candidates": len(goal_payload["inactive_candidate_refs"]),
            "retrieval_hits": len(retrieval_payload["hits"]),
            "soar_cycles": 2,
        },
        "demonstrated": [
            "real ambiguous L3 beam to bounded Soar working memory",
            "real Soar impasse operator causing L4 retrieval",
            "bounded L4 retrieval over actual episodic, temporal, and discourse memories",
            "real Soar selection citing every projected candidate",
            "no global-store copy and no truth commitment",
            "deterministic replay, idempotence, lineage, and exact restoration",
        ],
        "not_demonstrated": ["recursive induction", "dialogue gameboard", "natural-language response"],
    }
    write_json("results.json", results)
    write_json("summary.json", {"verdict": results["verdict"], "checks_passed": sum(checks.values()), "checks_total": len(checks), **results["counts"]})
    write_json("ledger.json", arena.as_dict())
    write_json("lineage.json", lineage)
    write_json("goal.json", goal_payload)
    write_json("retrieval.json", retrieval_payload)
    write_json("decision.json", decision_payload)
    write_json("versions-and-parameters.json", {
        "python": platform.python_version(),
        "pydelphin": importlib.metadata.version("pydelphin"),
        "registry_digest": arena.registry.digest,
        "policy": run["policy"].__dict__,
        "ace_sha256": sha256_file(ROOT / ".local/bin/ace"),
        "erg_sha256": sha256_file(ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"),
        "source_sha256": sha256_file(ROOT / SOURCE),
        "soar_version": decision_payload["soar_trace"]["soar_version"],
    })
    print(json.dumps(results, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
