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
OUTPUT = ROOT / "poc/sys-04/output"
SOURCE = Path("data/curriculum/sys_04_transformations.txt")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import (  # noqa: E402
    ArtifactArena,
    thaw_json,
)
from seman2_runtime.contracts import ContractError  # noqa: E402
from seman2_runtime.developmental_core import DevelopmentalCore  # noqa: E402
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
from seman2_runtime.transformation_learning import (  # noqa: E402
    TransformationLearningEngine,
    build_transformation_registry,
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


def independently_extract_role_forms(
    arena: ArtifactArena, episode: object
) -> set[tuple[str, str]]:
    """Rebuild event participant bindings directly from the episode's real L2."""
    branch_set = arena.get(episode.parent_ids[0])
    rows: set[tuple[str, str]] = set()
    for branch in thaw_json(branch_set.payload_native)["branches"]:
        payload = thaw_json(arena.get(branch["candidate_ref"]).payload_native)
        index_ref = payload["proposition"]["index_ref"]
        for relation in payload["relations"]:
            bindings = {
                item["role_ref"]: item["value_ref"]
                for item in relation["bindings"]
            }
            if relation["part_of_speech"] != "v" or bindings.get("ARG0") != index_ref:
                continue
            for role, value_ref in bindings.items():
                if role == "ARG0":
                    continue
                for entity_relation in payload["relations"]:
                    if not any(
                        item["role_ref"] == "ARG0"
                        and item["value_ref"] == value_ref
                        for item in entity_relation["bindings"]
                    ):
                        continue
                    if entity_relation["part_of_speech"] in {"n", "u"}:
                        rows.add((role, f"external:mrs:{entity_relation['predicate']}"))
                    elif (
                        entity_relation["predicate"] == "named"
                        and isinstance(entity_relation.get("constant"), str)
                    ):
                        rows.add(
                            (
                                role,
                                f"external:mrs:named:{entity_relation['constant']}",
                            )
                        )
    return rows


def stable_arena(arena: ArtifactArena) -> list[dict[str, object]]:
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
        observations,
        AceErgAnalyzer(arena, project_root=project_root, policy=policy),
    )
    l2, candidates = GenericMRSComposer(arena).compose_ledger(l1)
    candidates_by_observation = {row.artifact_id: [] for row in observations}
    for candidate in candidates:
        contribution = arena.get(candidate.parent_ids[0])
        candidates_by_observation[contribution.parent_ids[0]].append(candidate)
    manager = HypothesisManager(arena)
    branch_sets = tuple(
        manager.group(candidates_by_observation[row.artifact_id])
        for row in observations
    )
    return l1, l2, branch_sets


def execute(source_root: Path, *, project_root: Path) -> dict[str, object]:
    policy = LowLevelPolicy(
        max_sentence_chars=120,
        max_candidates=3,
        worker_timeout_seconds=30.0,
        worker_memory_mib=1_024,
        max_observations_per_wave=16,
    )
    arena = ArtifactArena(build_transformation_registry())
    gateway = ExperienceGateway(
        arena,
        session_id="sys-04",
        policy=policy,
        source_root=source_root,
    )

    # Les onze premières expériences excluent explicitement l'outcome réservé.
    initial_pairs = gateway.ingest_file(
        source_root / SOURCE,
        experience_prefix="sys-04",
        max_observations=11,
    )
    initial_observations = tuple(row[1] for row in initial_pairs)
    initial_l1, initial_l2, initial_branches = process_wave(
        arena,
        initial_observations,
        project_root=project_root,
        policy=policy,
    )
    knowledge = KnowledgeAdmissionEngine(arena)
    initial_episodes = []
    for branch_set in initial_branches:
        knowledge.observe(branch_set)
        initial_episodes.append(knowledge._episode_artifacts[branch_set.artifact_id])

    learner = TransformationLearningEngine(arena, core=knowledge.core)
    training_episode_artifacts = []
    for index, start in enumerate((0, 3, 6), start=1):
        _, artifact = learner.observe_scenario(
            f"scenario:sys-04:train:{index}",
            before_episode=initial_episodes[start],
            event_episode=initial_episodes[start + 1],
            after_episode=initial_episodes[start + 2],
        )
        training_episode_artifacts.append(artifact)
    learned_artifacts = learner.learn()
    if not learned_artifacts:
        raise AssertionError("no learned transformation")
    learned_artifact = max(
        learned_artifacts,
        key=lambda row: (
            len(thaw_json(row.payload_native)["support_occurrences"]),
            len(thaw_json(row.payload_native)["structural_pattern"]),
            row.artifact_id,
        ),
    )

    contribution, expectation_set = learner.predict(
        learned_artifact,
        before_episode=initial_episodes[9],
        event_episode=initial_episodes[10],
    )
    prediction_created_sequence = expectation_set.created_sequence

    # L'outcome réservé n'est ingéré qu'après la prédiction.
    outcome_pairs = gateway.ingest_file(
        source_root / SOURCE,
        experience_prefix="sys-04",
        sequence_start=11,
        start_line=12,
        max_observations=1,
    )
    outcome_observation = outcome_pairs[0][1]
    outcome_l1, outcome_l2, outcome_branches = process_wave(
        arena,
        (outcome_observation,),
        project_root=project_root,
        policy=policy,
    )
    knowledge.observe(outcome_branches[0])
    outcome_episode = knowledge._episode_artifacts[outcome_branches[0].artifact_id]
    observed_outcomes = learner.observed_outcomes(
        before_episode=initial_episodes[9],
        event_episode=initial_episodes[10],
        after_episode=outcome_episode,
    )
    return {
        "arena": arena,
        "knowledge": knowledge,
        "learner": learner,
        "initial_l1": initial_l1,
        "initial_l2": initial_l2,
        "outcome_l1": outcome_l1,
        "outcome_l2": outcome_l2,
        "initial_branches": initial_branches,
        "outcome_branches": outcome_branches,
        "initial_episodes": tuple(initial_episodes),
        "outcome_episode": outcome_episode,
        "training_episode_artifacts": tuple(training_episode_artifacts),
        "learned_artifacts": learned_artifacts,
        "learned_artifact": learned_artifact,
        "contribution": contribution,
        "expectation_set": expectation_set,
        "prediction_created_sequence": prediction_created_sequence,
        "outcome_experience_created_sequence": outcome_pairs[0][0].created_sequence,
        "observed_outcomes": observed_outcomes,
        "policy": policy,
    }


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    run = execute(ROOT, project_root=ROOT)
    arena = run["arena"]
    knowledge = run["knowledge"]
    learner = run["learner"]
    learned_artifact = run["learned_artifact"]
    contribution = run["contribution"]
    expectation_set = run["expectation_set"]
    learned = thaw_json(learned_artifact.payload_native)
    predicted = thaw_json(contribution.payload_native)
    expectations = thaw_json(expectation_set.payload_native)["expectations"]
    prediction_by_outcome = {
        row["outcome_ref"]: row["confidence"] for row in expectations
    }
    observed_outcomes = run["observed_outcomes"]
    dominant_prediction = max(
        expectations, key=lambda row: (row["confidence"], row["outcome_ref"])
    )["outcome_ref"]

    learned_structure = learner.inducer.structures[learned["learned_structure_ref"]]
    prototype = knowledge.core.forms.get(learned["distributed_prototype_ref"])
    decoded = knowledge.core.forms.decode(prototype, prototype.factors)
    source_code = (
        ROOT / "seman2_runtime/transformation_learning.py"
    ).read_text(encoding="utf-8").lower()

    with tempfile.TemporaryDirectory(prefix="seman2-sys04-replay-") as temp_name:
        replay_root = Path(temp_name)
        destination = replay_root / SOURCE
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / SOURCE, destination)
        replay = execute(replay_root, project_root=ROOT)
        replay_equal = stable_arena(arena) == stable_arena(replay["arena"])
        replay_core_equal = (
            knowledge.core.as_dict() == replay["knowledge"].core.as_dict()
        )

    restored_arena = ArtifactArena.restore(
        build_transformation_registry(), arena.as_dict()
    )
    restored_core = DevelopmentalCore.restore(knowledge.core.as_dict())

    training_scenarios = run["training_episode_artifacts"]
    training_alternative_payloads = [
        alternative
        for row in training_scenarios
        for alternative in thaw_json(row.payload_native)["alternatives"]
    ]
    training_actor_forms = {
        binding["participant_form_ref"]
        for alternative in training_alternative_payloads
        for binding in alternative["participant_bindings"]
        if binding["role_ref"] == "ARG1"
    }
    training_patient_forms = {
        binding["participant_form_ref"]
        for alternative in training_alternative_payloads
        for binding in alternative["participant_bindings"]
        if binding["role_ref"] == "ARG2"
    }
    held_out_alternatives = predicted["input_alternatives"]
    held_out_actor_forms = {
        binding["participant_form_ref"]
        for alternative in held_out_alternatives
        for binding in alternative["participant_bindings"]
        if binding["role_ref"] == "ARG1"
    }
    held_out_patient_forms = {
        binding["participant_form_ref"]
        for alternative in held_out_alternatives
        for binding in alternative["participant_bindings"]
        if binding["role_ref"] == "ARG2"
    }
    participant_bindings_are_native = all(
        {
            (binding["role_ref"], binding["participant_form_ref"])
            for alternative in thaw_json(scenario.payload_native)["alternatives"]
            for binding in alternative["participant_bindings"]
        }
        <= independently_extract_role_forms(arena, run["initial_episodes"][event_index])
        for scenario, event_index in zip(training_scenarios, (1, 4, 7), strict=True)
    ) and {
        (binding["role_ref"], binding["participant_form_ref"])
        for alternative in held_out_alternatives
        for binding in alternative["participant_bindings"]
    } <= independently_extract_role_forms(arena, run["initial_episodes"][10])
    training_event_tenses = {
        event["properties"].get("TENSE")
        for index in (1, 4, 7)
        for candidate in learner._L2_candidates(run["initial_episodes"][index])
        for event in [
            next(
                (
                    row
                    for row in thaw_json(candidate.payload_native)["events"]
                    if row["candidate_ref"]
                    == thaw_json(candidate.payload_native)["proposition"]["index_ref"]
                ),
                None,
            )
        ]
        if event is not None
    }
    artifact_count_before_idempotency = len(arena.query())
    repeated_occurrence, repeated_episode = learner.observe_scenario(
        "scenario:sys-04:train:1",
        before_episode=run["initial_episodes"][0],
        event_episode=run["initial_episodes"][1],
        after_episode=run["initial_episodes"][2],
    )
    repeated_contribution, repeated_expectation = learner.predict(
        learned_artifact,
        before_episode=run["initial_episodes"][9],
        event_episode=run["initial_episodes"][10],
    )
    artifact_count_after_idempotency = len(arena.query())
    invalid_episode_input_rejected = rejects_contract(
        lambda: learner.observe_scenario(
            "scenario:sys-04:invalid",
            before_episode=learner._L2_candidates(run["initial_episodes"][0])[0],
            event_episode=run["initial_episodes"][1],
            after_episode=run["initial_episodes"][2],
        )
    )
    invalid_prediction_input_rejected = rejects_contract(
        lambda: learner.predict(
            run["initial_episodes"][0],
            before_episode=run["initial_episodes"][9],
            event_episode=run["initial_episodes"][10],
        )
    )
    aligned_training_alternatives = sum(
        len(thaw_json(row.payload_native)["alternatives"])
        for row in training_scenarios
    )
    upstream_training_parse_branches = sum(
        len(thaw_json(row.payload_native)["branches"])
        for row in run["initial_branches"][:9]
    )
    feedback_parents = set(contribution.parent_ids)
    predicted_probabilities = sorted(prediction_by_outcome.values(), reverse=True)
    checks = {
        "closed_SYS03_upstream_stock_is_consumed": (
            run["initial_l1"].closed
            and run["initial_l2"].closed
            and run["initial_l1"].recompute_digest()
            == run["initial_l1"].ledger_digest
            and run["initial_l2"].recompute_digest()
            == run["initial_l2"].batch_digest
            and len(run["initial_branches"]) == 11
            and len(run["initial_episodes"]) == 11
        ),
        "three_real_scenarios_become_three_L4_occurrences": (
            len(training_scenarios) == 3
            and len(learner.occurrences) == 3
            and all(row.artifact_type == "transformation-episode" for row in training_scenarios)
        ),
        "parse_alternatives_do_not_multiply_experiences": (
            upstream_training_parse_branches > 9
            and upstream_training_parse_branches > aligned_training_alternatives
            and aligned_training_alternatives > len(training_scenarios)
            and learned_structure.support_count == 3
            and set(learned_structure.support_occurrences)
            == {f"scenario:sys-04:train:{index}" for index in (1, 2, 3)}
        ),
        "learned_pattern_comes_from_real_event_and_prestate": (
            any(factor.startswith("event-form:") for factor in learned_structure.structural_pattern)
            and any(factor.startswith("pre-state:") for factor in learned_structure.structural_pattern)
            and all(factor.startswith(("event-form:", "event-role:", "pre-state:", "patient-facet:")) for factor in learned_structure.structural_pattern)
        ),
        "real_lexical_variants_and_participant_bindings_generalize": (
            len(training_event_tenses) >= 2
            and len(training_actor_forms) >= 2
            and len(training_patient_forms) >= 2
            and bool(held_out_actor_forms)
            and bool(held_out_patient_forms)
            and training_actor_forms.isdisjoint(held_out_actor_forms)
            and training_patient_forms.isdisjoint(held_out_patient_forms)
        ),
        "participant_bindings_are_reconstructed_from_real_L2": (
            participant_bindings_are_native
        ),
        "production_engine_contains_no_curriculum_effect_lexemes": all(
            token not in source_code
            for token in (
                "_open_v_cause", "_closed_a_1", "_open_a_to", "wooden",
                "metal", "automatic", "garden", "gate", "maya", "jonah",
                "amira", "box", "door",
            )
        ),
        "exception_is_preserved_and_confidence_is_qualified": (
            learned["exceptions"] == ["scenario:sys-04:train:3"]
            and len(expectations) >= 2
            and predicted_probabilities[0] < 1.0
            and predicted["qualification"] == "full-match-with-observed-exceptions"
        ),
        "learned_structure_has_real_L4_parents": (
            set(learned_artifact.parent_ids)
            == {row.artifact_id for row in training_scenarios}
            and all(
                len(row.parent_ids) == 3
                and all(
                    arena.get(parent_id).artifact_type == "episode-memory"
                    for parent_id in row.parent_ids
                )
                for row in training_scenarios
            )
        ),
        "distributed_prototype_is_traceable_and_decodable": (
            prototype.form_id == learned["distributed_prototype_ref"]
            and len(decoded) == len(prototype.factors)
            and all(row.traced for row in decoded)
            and knowledge.core.memory.accessible(learned["learned_structure_ref"])
        ),
        "L5_reenters_future_experience_as_L2_then_L3": (
            learned_artifact.artifact_id in feedback_parents
            and run["initial_episodes"][9].artifact_id in feedback_parents
            and run["initial_episodes"][10].artifact_id in feedback_parents
            and contribution.artifact_type == "learned-transformation-contribution"
            and expectation_set.parent_ids == (contribution.artifact_id,)
            and expectation_set.artifact_type == "transformation-expectation-set"
        ),
        "held_out_combination_is_full_match_without_patient_leak": (
            predicted["missing_factors"] == []
            and predicted["qualification"].startswith("full-match")
            and all(
                token not in " ".join(learned["structural_pattern"]).lower()
                for token in ("gate", "garden", "amira")
            )
        ),
        "prediction_precedes_reserved_outcome_ingestion": (
            run["prediction_created_sequence"]
            < run["outcome_experience_created_sequence"]
            and run["outcome_episode"].observation_refs[0]
            not in learned_artifact.observation_refs
            and run["outcome_episode"].observation_refs[0]
            not in contribution.observation_refs
        ),
        "dominant_prediction_matches_real_reserved_outcome": (
            dominant_prediction in observed_outcomes
            and prediction_by_outcome[dominant_prediction]
            == max(prediction_by_outcome.values())
        ),
        "expectation_does_not_commit_truth_or_world": (
            thaw_json(contribution.payload_projection)["truth_committed"] is False
            and thaw_json(contribution.payload_projection)["world_update_performed"] is False
            and thaw_json(expectation_set.payload_native)["selected_ref"] is None
            and thaw_json(expectation_set.payload_projection)["truth_committed"] is False
            and thaw_json(expectation_set.payload_projection)["world_update_performed"] is False
            and all(not row["selected"] for row in expectations)
        ),
        "reserved_outcome_also_uses_closed_real_pipeline": (
            run["outcome_l1"].closed
            and run["outcome_l2"].closed
            and run["outcome_l1"].recompute_digest()
            == run["outcome_l1"].ledger_digest
            and run["outcome_l2"].recompute_digest()
            == run["outcome_l2"].batch_digest
            and len(run["outcome_branches"]) == 1
            and run["outcome_episode"].artifact_type == "episode-memory"
        ),
        "learning_and_prediction_are_idempotent": (
            repeated_occurrence == learner.occurrences["scenario:sys-04:train:1"]
            and repeated_episode.artifact_id == training_scenarios[0].artifact_id
            and repeated_contribution.artifact_id == contribution.artifact_id
            and repeated_expectation.artifact_id == expectation_set.artifact_id
            and artifact_count_before_idempotency == artifact_count_after_idempotency
        ),
        "invalid_cross_layer_inputs_are_rejected": (
            invalid_episode_input_rejected and invalid_prediction_input_rejected
        ),
        "all_new_artifacts_have_context_and_resource_cost": all(
            row.context_refs == ("ctx:model",) and bool(thaw_json(row.resource_cost))
            for artifact_type in (
                "transformation-episode",
                "learned-transformation",
                "learned-transformation-contribution",
                "transformation-expectation-set",
            )
            for row in arena.query(artifact_type=artifact_type)
        ),
        "location_independent_full_replay_is_identical": replay_equal
        and replay_core_equal,
        "arena_and_cognitive_core_restore_exactly": (
            stable_arena(restored_arena) == stable_arena(arena)
            and restored_core.as_dict() == knowledge.core.as_dict()
        ),
    }

    operation_by_type = {
        "analysis-contribution": "ACE/ERG analysis",
        "composed-candidate": "generic MRS composition",
        "situation-branch-set": "hypothesis grouping",
        "episode-memory": "episodic admission",
        "transformation-episode": "before/event/after delta alignment",
        "learned-transformation": "cross-episode induction",
        "learned-transformation-contribution": "L5 feedback into new experience",
        "transformation-expectation-set": "qualified consequence proposal",
    }
    effects = []
    for row in arena.query():
        if row.artifact_type not in operation_by_type:
            continue
        for parent_id in row.parent_ids:
            effects.append(
                {
                    "consumer_artifact_ref": row.artifact_id,
                    "input_factor_ref": parent_id,
                    "producer_artifact_ref": row.artifact_id,
                    "operation": operation_by_type[row.artifact_type],
                    "effect_on_output": f"{row.artifact_type}:{row.status.value}",
                    "activation_or_weight_change": (
                        "learned expectation added"
                        if row.artifact_type
                        in {
                            "learned-transformation",
                            "learned-transformation-contribution",
                            "transformation-expectation-set",
                        }
                        else "one attributed structure added"
                    ),
                    "context_ref": list(row.context_refs),
                    "reason_if_ignored": None,
                }
            )
    lineage = lineage_manifest(
        arena,
        real_source_refs=[SOURCE.as_posix()],
        causal_effects=effects,
    )
    ancestry = {
        row.artifact_id for row in arena.ancestry(expectation_set.artifact_id)
    }
    checks["expectation_ancestry_reaches_real_L0_and_L5"] = {
        "experience-occurrence",
        "observation",
        "analysis-contribution",
        "composed-candidate",
        "situation-branch-set",
        "episode-memory",
        "transformation-episode",
        "learned-transformation",
        "learned-transformation-contribution",
        "transformation-expectation-set",
    } <= {arena.get(ref).artifact_type for ref in ancestry}

    all_passed = all(checks.values())
    results = {
        "verdict": "GO" if all_passed else "NO-GO",
        "scope": "real episodic before/event/after stock to learned L5 transformation and held-out L2/L3 expectation",
        "checks": checks,
        "counts": {
            "source_experiences": 12,
            "training_scenarios": len(training_scenarios),
            "upstream_training_parse_branches": upstream_training_parse_branches,
            "aligned_training_alternatives": aligned_training_alternatives,
            "learned_transformations": len(run["learned_artifacts"]),
            "support_occurrences": learned_structure.support_count,
            "exceptions": len(learned["exceptions"]),
            "predicted_outcomes": len(expectations),
            "observed_reserved_outcomes": len(observed_outcomes),
        },
        "evidence": {
            "training_actor_forms": sorted(training_actor_forms),
            "training_patient_forms": sorted(training_patient_forms),
            "held_out_actor_forms": sorted(held_out_actor_forms),
            "held_out_patient_forms": sorted(held_out_patient_forms),
            "training_event_tenses": sorted(training_event_tenses),
        },
        "prediction": {
            "structural_pattern": learned["structural_pattern"],
            "predicted_outcomes": predicted["predicted_outcomes"],
            "qualification": predicted["qualification"],
            "observed_outcomes_after_prediction": list(observed_outcomes),
        },
        "demonstrated": [
            "real L2/L3 events and states assembled into L4 episodes",
            "cross-episode L5 induction without a verb-effect lookup table",
            "parse-deduplicated support and explicit exception retention",
            "decodable distributed transformation prototype",
            "authorized L5 to future-L2/L3 feedback",
            "held-out prediction before outcome ingestion",
            "qualified expectation matching the later real outcome",
            "complete causal lineage, replay, and snapshot restoration",
        ],
        "not_demonstrated": [
            "temporal interval reasoning",
            "cross-sentence personal identity resolution",
            "dialogue",
            "natural-language response",
        ],
    }
    write_json("results.json", results)
    write_json(
        "summary.json",
        {
            "verdict": results["verdict"],
            "checks_passed": sum(checks.values()),
            "checks_total": len(checks),
            **results["counts"],
        },
    )
    write_json("lineage.json", lineage)
    write_json("ledger.json", arena.as_dict())
    write_json("model.json", knowledge.core.as_dict())
    write_json(
        "closed-batches.json",
        {
            "initial_L1": run["initial_l1"].as_dict(),
            "initial_L2": run["initial_l2"].as_dict(),
            "outcome_L1": run["outcome_l1"].as_dict(),
            "outcome_L2": run["outcome_l2"].as_dict(),
        },
    )
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "pydelphin": importlib.metadata.version("pydelphin"),
            "registry_digest": arena.registry.digest,
            "policy": run["policy"].__dict__,
            "ace_sha256": sha256_file(ROOT / ".local/bin/ace"),
            "erg_sha256": sha256_file(
                ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
            ),
            "source_sha256": sha256_file(ROOT / SOURCE),
        },
    )
    print(json.dumps(results, ensure_ascii=False))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
