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
OUTPUT = ROOT / "poc/sys-08/output"
SOURCE = Path("data/curriculum/sys_08_recursive_concepts.txt")
CONTEXT = "ctx:sys-08:world"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import ArtifactArena, thaw_json  # noqa: E402
from seman2_runtime.concept_learning import InductionPolicy  # noqa: E402
from seman2_runtime.contracts import ContractError  # noqa: E402
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
from seman2_runtime.recursive_concept_system import (  # noqa: E402
    RecursiveConceptEngine,
    build_recursive_concept_registry,
)
from seman2_runtime.transformation_learning import TransformationLearningEngine  # noqa: E402


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


def process_wave(
    arena: ArtifactArena,
    observations: tuple[object, ...],
    *,
    project_root: Path,
    policy: LowLevelPolicy,
) -> tuple[object, object, tuple[object, ...]]:
    l1, _ = AnalysisOrchestrator(policy=policy).execute(
        observations, AceErgAnalyzer(arena, project_root=project_root, policy=policy)
    )
    l2, candidates = GenericMRSComposer(arena).compose_ledger(l1)
    by_observation = {row.artifact_id: [] for row in observations}
    for candidate in candidates:
        contribution = arena.get(candidate.parent_ids[0])
        by_observation[contribution.parent_ids[0]].append(candidate)
    manager = HypothesisManager(arena)
    branches = tuple(
        manager.group(by_observation[row.artifact_id]) for row in observations
    )
    return l1, l2, branches


def execute(source_root: Path, *, project_root: Path) -> dict[str, object]:
    policy = LowLevelPolicy(
        max_sentence_chars=140,
        max_candidates=3,
        worker_timeout_seconds=30.0,
        worker_memory_mib=1_024,
        max_observations_per_wave=24,
    )
    arena = ArtifactArena(build_recursive_concept_registry())
    gateway = ExperienceGateway(
        arena, session_id="sys-08", policy=policy, source_root=source_root
    )

    # Les deux outcomes réservés (lignes 20-21) sont physiquement absents de
    # l'arène jusqu'à ce que les deux attentes L3 aient été publiées.
    initial_pairs = gateway.ingest_file(
        source_root / SOURCE,
        experience_prefix="sys-08",
        max_observations=19,
    )
    initial_observations = tuple(row[1] for row in initial_pairs)
    initial_l1, initial_l2, initial_branches = process_wave(
        arena, initial_observations, project_root=project_root, policy=policy
    )
    knowledge = KnowledgeAdmissionEngine(arena, context_ref=CONTEXT)
    initial_episodes = []
    for branch in initial_branches:
        knowledge.observe(branch)
        initial_episodes.append(knowledge._episode_artifacts[branch.artifact_id])

    learner = TransformationLearningEngine(
        arena,
        core=knowledge.core,
        context_ref=CONTEXT,
        induction_policy=InductionPolicy(
            minimum_support=2,
            minimum_pattern_size=2,
            minimum_specialization_support=2,
            maximum_structures=16,
        ),
    )
    training_occurrences = []
    for number, start in enumerate((0, 3, 6, 9, 12), 1):
        _, occurrence = learner.observe_scenario(
            f"scenario:sys-08:train:{number}",
            before_episode=initial_episodes[start],
            event_episode=initial_episodes[start + 1],
            after_episode=initial_episodes[start + 2],
        )
        training_occurrences.append(occurrence)
    learned_artifacts = learner.learn()
    if len(learned_artifacts) < 2:
        raise AssertionError(
            "SYS-08 requires a general and a specialized learned pattern: "
            + json.dumps(
                {
                    ref: list(row.structural_factors)
                    for ref, row in learner.occurrences.items()
                },
                ensure_ascii=False,
            )
        )

    controller = RecursiveConceptEngine(
        arena,
        transformation_engine=learner,
        core=knowledge.core,
        project_root=project_root,
        context_ref=CONTEXT,
        beam_bound=2,
        maximum_structures=16,
        memory_limit_mib=2_048,
        timeout_seconds=30.0,
    )
    normal_application = controller.apply(
        learned_artifacts,
        before_episode=initial_episodes[15],
        event_episode=initial_episodes[16],
    )
    divergent_application = controller.apply(
        learned_artifacts,
        before_episode=initial_episodes[17],
        event_episode=initial_episodes[18],
    )
    prediction_sequences = (
        normal_application[-1].created_sequence,
        divergent_application[-1].created_sequence,
    )

    outcome_pairs = gateway.ingest_file(
        source_root / SOURCE,
        experience_prefix="sys-08",
        sequence_start=19,
        start_line=20,
        max_observations=2,
    )
    outcome_observations = tuple(row[1] for row in outcome_pairs)
    outcome_l1, outcome_l2, outcome_branches = process_wave(
        arena, outcome_observations, project_root=project_root, policy=policy
    )
    outcome_episodes = []
    for branch in outcome_branches:
        knowledge.observe(branch)
        outcome_episodes.append(knowledge._episode_artifacts[branch.artifact_id])

    normal_feedback = controller.observe_feedback(
        normal_application[-1], after_episode=outcome_episodes[0]
    )
    divergent_feedback = controller.observe_feedback(
        divergent_application[-1], after_episode=outcome_episodes[1]
    )
    recursive_concept = controller.induce_recursively(
        (normal_feedback, divergent_feedback)
    )
    return locals()


def dominant_outcome(expectation: object) -> str:
    rows = thaw_json(expectation.payload_native)["expectations"]
    return max(rows, key=lambda row: (row["confidence"], row["outcome_ref"]))[
        "outcome_ref"
    ]


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    run = execute(ROOT, project_root=ROOT)
    arena = run["arena"]
    learner = run["learner"]
    controller = run["controller"]
    normal = run["normal_application"]
    divergent = run["divergent_application"]
    feedback = (run["normal_feedback"], run["divergent_feedback"])
    recursive = run["recursive_concept"]

    structures = learner.inducer.structures
    general = max(structures.values(), key=lambda row: row.support_count)
    specializations = tuple(
        row for row in structures.values()
        if general.learned_structure_id in row.generalizations
    )
    specialized = min(
        specializations,
        key=lambda row: (row.support_count, -len(row.structural_pattern), row.learned_structure_id),
    )
    ordinary_specialized = max(
        specializations,
        key=lambda row: (row.support_count, len(row.structural_pattern), row.learned_structure_id),
    )
    learned_by_structure = {
        thaw_json(row.payload_native)["learned_structure_ref"]: row
        for row in run["learned_artifacts"]
    }
    normal_decision_payload = thaw_json(normal[2].payload_native)
    divergent_decision_payload = thaw_json(divergent[2].payload_native)
    normal_selected = thaw_json(arena.get(normal_decision_payload["selected_candidate_ref"]).payload_native)["learned_structure_ref"]
    divergent_selected = thaw_json(arena.get(divergent_decision_payload["selected_candidate_ref"]).payload_native)["learned_structure_ref"]
    actual_outcomes = [
        set(thaw_json(row.payload_native)["observed_outcomes"]) for row in feedback
    ]
    learned_predictions = [dominant_outcome(normal[-1]), dominant_outcome(divergent[-1])]
    learned_accuracy = sum(
        prediction in observed
        for prediction, observed in zip(learned_predictions, actual_outcomes, strict=True)
    ) / 2
    global_counts: dict[str, int] = {}
    for occurrence in learner.occurrences.values():
        for outcome in occurrence.outcome_refs:
            global_counts[outcome] = global_counts.get(outcome, 0) + 1
    baseline_prediction = min(global_counts, key=lambda ref: (-global_counts[ref], ref))
    baseline_accuracy = sum(
        baseline_prediction in observed for observed in actual_outcomes
    ) / 2

    recursive_payload = thaw_json(recursive.payload_native)
    recursive_form = run["knowledge"].core.forms.get(
        recursive_payload["distributed_prototype_ref"]
    )
    decoded_recursive = run["knowledge"].core.forms.decode(
        recursive_form, recursive_form.factors
    )
    source_code = (
        ROOT / "seman2_runtime/recursive_concept_system.py"
    ).read_text(encoding="utf-8").lower()

    with tempfile.TemporaryDirectory(prefix="seman2-sys08-replay-") as temp_name:
        replay_root = Path(temp_name)
        destination = replay_root / SOURCE
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / SOURCE, destination)
        replay = execute(replay_root, project_root=ROOT)
        replay_equal = stable_view(arena) == stable_view(replay["arena"])
        replay_core_equal = run["knowledge"].core.as_dict() == replay["knowledge"].core.as_dict()

    restored = ArtifactArena.restore(build_recursive_concept_registry(), arena.as_dict())
    before_repeat = len(arena.query())
    repeated_application = controller.apply(
        run["learned_artifacts"],
        before_episode=run["initial_episodes"][15],
        event_episode=run["initial_episodes"][16],
    )
    repeated_feedback = controller.observe_feedback(
        normal[-1], after_episode=run["outcome_episodes"][0]
    )
    repeated_recursive = controller.induce_recursively(feedback)
    after_repeat = len(arena.query())
    invalid_application_rejected = rejects_contract(
        lambda: controller.apply(
            run["learned_artifacts"],
            before_episode=run["learned_artifacts"][0],
            event_episode=run["initial_episodes"][16],
        )
    )
    invalid_feedback_rejected = rejects_contract(
        lambda: controller.observe_feedback(
            run["initial_episodes"][0], after_episode=run["outcome_episodes"][0]
        )
    )

    normal_goal = thaw_json(normal[0].payload_native)
    divergent_goal = thaw_json(divergent[0].payload_native)
    normal_retrieval = thaw_json(normal[1].payload_native)
    divergent_retrieval = thaw_json(divergent[1].payload_native)
    recursive_ancestry_types = {
        row.artifact_type for row in arena.ancestry(recursive.artifact_id)
    }
    outcome_first_sequence = min(row[0].created_sequence for row in run["outcome_pairs"])
    general_payload = thaw_json(learned_by_structure[general.learned_structure_id].payload_native)
    specialized_payload = thaw_json(learned_by_structure[specialized.learned_structure_id].payload_native)
    specialization_delta = set(specialized.structural_pattern) - set(general.structural_pattern)

    checks = {
        "closed_real_L0_to_L4_stock_is_the_only_training_input": (
            run["initial_l1"].closed and run["initial_l2"].closed
            and run["initial_l1"].recompute_digest() == run["initial_l1"].ledger_digest
            and run["initial_l2"].recompute_digest() == run["initial_l2"].batch_digest
            and len(run["initial_observations"]) == 19
            and len(run["initial_episodes"]) == 19
        ),
        "five_ordered_real_scenarios_form_five_L4_occurrences": (
            len(run["training_occurrences"]) == 5
            and len(learner.occurrences) == 5
            and all(row.artifact_type == "transformation-episode" for row in run["training_occurrences"])
        ),
        "parse_alternatives_never_multiply_lived_support": (
            sum(len(thaw_json(row.payload_native)["branches"]) for row in run["initial_branches"][:15]) > 15
            and general.support_count == 5
            and set(general.support_occurrences) == {f"scenario:sys-08:train:{n}" for n in range(1, 6)}
        ),
        "general_pattern_is_anonymous_and_role_normalized": (
            any(row.startswith("event-form:") for row in general.structural_pattern)
            and any(row.startswith("event-role:") for row in general.structural_pattern)
            and not any(row.startswith("pre-state:") for row in general.structural_pattern)
            and all(
                set(general.structural_pattern) < set(row.structural_pattern)
                for row in specializations
            )
            and all(name not in " ".join(general.structural_pattern).lower() for name in ("maya", "jonah", "amira", "noah", "lina", "box", "door", "cabinet", "chest", "drawer"))
        ),
        "divergent_real_outcomes_create_a_supported_specialization": (
            specialized.support_count == 2
            and specialized.generalizations
            and general.learned_structure_id in specialized.generalizations
            and len(specialization_delta) >= 1
            and all(row.startswith(("patient-facet:", "pre-state:")) for row in specialization_delta)
            and len(specialized.observed_outcomes) == 1
        ),
        "general_pattern_preserves_divergence_without_erasure": (
            len(general.observed_outcomes) == 2
            and len(general.exceptions) == 2
            and len(general_payload["observed_outcomes"]) == 2
            and len(general_payload["exceptions"]) == 2
        ),
        "learned_L5_patterns_have_only_real_L4_occurrence_parents": all(
            row.parent_ids
            and all(arena.get(ref).artifact_type == "transformation-episode" for ref in row.parent_ids)
            for row in run["learned_artifacts"]
        ),
        "held_out_people_objects_and_combinations_are_absent_from_patterns": all(
            name not in " ".join(general.structural_pattern + specialized.structural_pattern).lower()
            for name in ("priya", "omar", "gate", "safe")
        ),
        "both_predictions_exist_before_reserved_outcome_ingestion": (
            max(run["prediction_sequences"]) < outcome_first_sequence
            and all(not set(row.observation_refs) & set(run["outcome_episodes"][0].observation_refs + run["outcome_episodes"][1].observation_refs) for row in (normal[-1], divergent[-1]))
        ),
        "ordinary_case_selects_its_supported_specialization": (
            normal_selected == ordinary_specialized.learned_structure_id
            and ordinary_specialized.support_count > specialized.support_count
        ),
        "divergent_case_selects_more_specific_pattern": (
            divergent_selected == specialized.learned_structure_id
            and len(specialized.structural_pattern) > len(general.structural_pattern)
        ),
        "real_SML_impasses_request_bounded_retrieval": all(
            thaw_json(application[2].payload_native)["initial_operator"]["action"] == "request-concept-retrieval"
            and "1 rule fired" in thaw_json(application[2].payload_native)["initial_operator"]["cycle_trace"]
            for application in (normal, divergent)
        ),
        "retrieval_uses_only_real_L5_patterns_and_no_raw_source": (
            normal_retrieval["indexed_count"] == len(run["learned_artifacts"])
            and divergent_retrieval["indexed_count"] == len(run["learned_artifacts"])
            and len(normal_retrieval["hits"]) == len(divergent_retrieval["hits"]) == 2
            and thaw_json(normal[1].payload_projection)["raw_source_accessed"] is False
            and thaw_json(divergent[1].payload_projection)["raw_source_accessed"] is False
        ),
        "second_real_SML_cycles_select_after_retrieval": all(
            thaw_json(application[2].payload_native)["final_operator"] == "select-concept"
            and "1 rule fired" in thaw_json(application[2].payload_native)["soar_trace"]["cycle_trace"]
            for application in (normal, divergent)
        ),
        "Soar_compares_exactly_the_bounded_real_candidates": all(
            set(thaw_json(application[2].payload_native)["compared_candidate_refs"])
            == {row["candidate_ref"] for row in thaw_json(application[0].payload_native)["candidate_beam"]}
            for application in (normal, divergent)
        ),
        "L5_reenters_as_real_L2_then_L3_without_truth_commitment": all(
            application[3].artifact_type == "learned-concept-contribution"
            and application[4].artifact_type == "concept-expectation-set"
            and application[4].parent_ids == (application[3].artifact_id,)
            and thaw_json(application[3].payload_projection)["truth_committed"] is False
            and thaw_json(application[3].payload_projection)["world_update_performed"] is False
            and thaw_json(application[4].payload_native)["selected_ref"] is None
            for application in (normal, divergent)
        ),
        "observed_outcomes_come_from_later_real_L0_to_L4_processing": (
            run["outcome_l1"].closed and run["outcome_l2"].closed
            and len(run["outcome_episodes"]) == 2
            and all(row.artifact_type == "episode-memory" for row in run["outcome_episodes"])
            and all(thaw_json(row.payload_native)["observed_outcomes"] for row in feedback)
        ),
        "learned_patterns_improve_reserved_prediction_over_ablation": (
            learned_accuracy == 1.0 and baseline_accuracy == 0.5 and learned_accuracy > baseline_accuracy
        ),
        "feedback_episodes_consume_actual_L3_expectations_and_L4_outcomes": all(
            row.parent_ids[0] in {normal[-1].artifact_id, divergent[-1].artifact_id}
            and arena.get(row.parent_ids[0]).artifact_type == "concept-expectation-set"
            and arena.get(row.parent_ids[1]).artifact_type == "episode-memory"
            for row in feedback
        ),
        "recursive_L5_concept_consumes_concepts_reinjected_through_L2_L3_L4": (
            recursive.parent_ids == tuple(sorted(row.artifact_id for row in feedback))
            and recursive_payload["recursion_depth"] == 2
            and len(recursive_payload["support_occurrences"]) == 2
            and "source-level:learned-pattern" in recursive_payload["structural_pattern"]
        ),
        "recursive_concept_is_more_abstract_than_lexical_training_pattern": (
            all(not row.startswith(("event-form:", "pre-state:", "patient-facet:")) for row in recursive_payload["structural_pattern"])
            and {"schema-has:event-form", "schema-has:pre-state", "schema-has:observed-outcome"} <= set(recursive_payload["structural_pattern"])
        ),
        "recursive_distributed_prototype_is_traceable_and_decodable": (
            recursive_form.form_id == recursive_payload["distributed_prototype_ref"]
            and len(decoded_recursive) == len(recursive_form.factors)
            and all(row.traced for row in decoded_recursive)
            and run["knowledge"].core.memory.accessible(recursive_payload["learned_structure_ref"])
        ),
        "production_engine_has_no_curriculum_lexeme_or_expected_label_table": all(
            token not in source_code for token in ("locked", "open_a", "closed_a", "wooden", "garden", "gate", "safe", "maya", "priya", "omar", "gold-label", "expected-label")
        ),
        "physical_and_cognitive_budgets_are_explicit": (
            thaw_json(normal[0].resource_cost)["beam_bound"] == 2
            and normal_retrieval["work_units"] <= 16
            and thaw_json(normal[2].resource_cost)["memory_limit_mib"] == 2_048
            and len(run["initial_observations"]) + len(run["outcome_observations"]) <= 24
        ),
        "services_are_idempotent_without_new_artifacts": (
            repeated_application[-1].artifact_id == normal[-1].artifact_id
            and repeated_feedback.artifact_id == feedback[0].artifact_id
            and repeated_recursive.artifact_id == recursive.artifact_id
            and before_repeat == after_repeat
        ),
        "invalid_cross_layer_inputs_are_rejected": invalid_application_rejected and invalid_feedback_rejected,
        "recursive_ancestry_reaches_every_real_layer_and_Soar": {
            "experience-occurrence", "observation", "analysis-contribution",
            "composed-candidate", "situation-branch-set", "episode-memory",
            "transformation-episode", "learned-transformation",
            "concept-application-goal", "concept-match-retrieval",
            "soar-concept-decision", "learned-concept-contribution",
            "concept-expectation-set", "concept-feedback-episode",
            "recursive-learned-concept",
        } <= recursive_ancestry_types,
        "location_independent_full_replay_is_identical": replay_equal and replay_core_equal,
        "arena_restore_is_exact": stable_view(restored) == stable_view(arena),
    }

    operation_by_type = {
        "analysis-contribution": "ACE/ERG analysis",
        "composed-candidate": "generic MRS composition",
        "situation-branch-set": "hypothesis grouping",
        "episode-memory": "episodic admission",
        "transformation-episode": "real before/event/after alignment",
        "learned-transformation": "anonymous cross-episode induction",
        "concept-application-goal": "bounded learned-pattern projection",
        "concept-match-retrieval": "structural pattern matching",
        "soar-concept-decision": "real SML concept selection",
        "learned-concept-contribution": "L5 feedback into L2",
        "concept-expectation-set": "non-committed L3 prediction",
        "concept-feedback-episode": "observed prediction outcome",
        "recursive-learned-concept": "second-order induction",
    }
    effects = [
        {
            "consumer_artifact_ref": row.artifact_id,
            "input_factor_ref": parent,
            "producer_artifact_ref": row.artifact_id,
            "operation": operation_by_type[row.artifact_type],
            "effect_on_output": f"{row.artifact_type}:{row.status.value}",
            "activation_or_weight_change": "one attributed structural factor or outcome",
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
        "scope": "real L4 outcomes to anonymous/specialized L5 patterns, Soar-controlled L2/L3 feedback, and recursive L5 abstraction",
        "checks": checks,
        "counts": {
            "source_experiences": 21,
            "training_scenarios": len(run["training_occurrences"]),
            "learned_L5_patterns": len(run["learned_artifacts"]),
            "held_out_predictions": 2,
            "feedback_episodes": len(feedback),
            "recursive_concepts": 1,
            "soar_cycles": 4,
        },
        "ablation": {
            "global_majority_prediction": baseline_prediction,
            "global_majority_accuracy": baseline_accuracy,
            "learned_predictions": learned_predictions,
            "learned_accuracy": learned_accuracy,
            "actual_outcomes": [sorted(row) for row in actual_outcomes],
        },
        "concepts": {
            "general": general_payload,
            "specialized": specialized_payload,
            "specialization_delta": sorted(specialization_delta),
            "recursive": recursive_payload,
        },
        "demonstrated": [
            "anonymous role-normalized induction from real episodes",
            "supported specialization after divergent real outcomes",
            "held-out improvement over an unconditioned majority ablation",
            "real bounded Soar selection between learned structures",
            "causal L5 to L2/L3 feedback before outcome observation",
            "recursive L4 feedback to a more abstract L5 concept",
            "distributed prototype, full lineage, replay, idempotence, and restoration",
        ],
        "not_demonstrated": ["dialogue gameboard", "natural-language response", "cultural interpretation"],
    }
    write_json("results.json", results)
    write_json("summary.json", {"verdict": results["verdict"], "checks_passed": sum(checks.values()), "checks_total": len(checks), **results["counts"]})
    write_json("lineage.json", lineage)
    write_json("ledger.json", arena.as_dict())
    write_json("model.json", run["knowledge"].core.as_dict())
    write_json("concepts.json", results["concepts"])
    write_json("ablation.json", results["ablation"])
    write_json("versions-and-parameters.json", {
        "python": platform.python_version(),
        "pydelphin": importlib.metadata.version("pydelphin"),
        "registry_digest": arena.registry.digest,
        "policy": run["policy"].__dict__,
        "induction_policy": learner.inducer.policy.__dict__,
        "ace_sha256": sha256_file(ROOT / ".local/bin/ace"),
        "erg_sha256": sha256_file(ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"),
        "source_sha256": sha256_file(ROOT / SOURCE),
        "soar_version": thaw_json(normal[2].payload_native)["soar_trace"]["soar_version"],
    })
    print(json.dumps(results, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
