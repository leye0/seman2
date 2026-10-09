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
OUTPUT = ROOT / "poc/sys-09/output"
CONCEPT_SOURCE = Path("data/curriculum/sys_08_recursive_concepts.txt")
DIALOGUE_SOURCE = Path("data/curriculum/sys_09_dialogue.tsv")
WORLD = "ctx:sys-09:world"
DIALOGUE = "dialogue:sys-09"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import ArtifactArena, thaw_json  # noqa: E402
from seman2_runtime.concept_learning import InductionPolicy  # noqa: E402
from seman2_runtime.contracts import ContractError  # noqa: E402
from seman2_runtime.dialogue_system import (  # noqa: E402
    DialogueGameboard,
    DialogueTurnInterpreter,
    build_dialogue_registry,
)
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
from seman2_runtime.recursive_concept_system import RecursiveConceptEngine  # noqa: E402
from seman2_runtime.temporal_system import (  # noqa: E402
    RelationalTemporalAnalyzer,
    TemporalReasoner,
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
) -> tuple[object, object, tuple[object, ...], tuple[object, ...]]:
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
    return l1, l2, branches, candidates


def build_real_concept_context(
    arena: ArtifactArena,
    gateway: ExperienceGateway,
    knowledge: KnowledgeAdmissionEngine,
    *,
    source_root: Path,
    project_root: Path,
    policy: LowLevelPolicy,
) -> dict[str, object]:
    initial_pairs = gateway.ingest_file(
        source_root / CONCEPT_SOURCE,
        experience_prefix="sys-09-concept",
        max_observations=19,
    )
    observations = tuple(row[1] for row in initial_pairs)
    initial_l1, initial_l2, branches, _ = process_wave(
        arena, observations, project_root=project_root, policy=policy
    )
    episodes = []
    for branch in branches:
        knowledge.observe(branch)
        episodes.append(knowledge._episode_artifacts[branch.artifact_id])
    learner = TransformationLearningEngine(
        arena,
        core=knowledge.core,
        context_ref=WORLD,
        induction_policy=InductionPolicy(
            minimum_support=2,
            minimum_pattern_size=2,
            minimum_specialization_support=2,
            maximum_structures=16,
        ),
    )
    for number, start in enumerate((0, 3, 6, 9, 12), 1):
        learner.observe_scenario(
            f"scenario:sys-09:concept:{number}",
            before_episode=episodes[start],
            event_episode=episodes[start + 1],
            after_episode=episodes[start + 2],
        )
    learned = learner.learn()
    controller = RecursiveConceptEngine(
        arena,
        transformation_engine=learner,
        core=knowledge.core,
        project_root=project_root,
        context_ref=WORLD,
        maximum_structures=16,
    )
    normal = controller.apply(
        learned, before_episode=episodes[15], event_episode=episodes[16]
    )
    divergent = controller.apply(
        learned, before_episode=episodes[17], event_episode=episodes[18]
    )
    outcome_pairs = gateway.ingest_file(
        source_root / CONCEPT_SOURCE,
        experience_prefix="sys-09-concept",
        sequence_start=19,
        start_line=20,
        max_observations=2,
    )
    outcome_observations = tuple(row[1] for row in outcome_pairs)
    outcome_l1, outcome_l2, outcome_branches, _ = process_wave(
        arena, outcome_observations, project_root=project_root, policy=policy
    )
    outcome_episodes = []
    for branch in outcome_branches:
        knowledge.observe(branch)
        outcome_episodes.append(knowledge._episode_artifacts[branch.artifact_id])
    feedback = (
        controller.observe_feedback(normal[-1], after_episode=outcome_episodes[0]),
        controller.observe_feedback(divergent[-1], after_episode=outcome_episodes[1]),
    )
    recursive = controller.induce_recursively(feedback)
    return locals()


def execute(source_root: Path, *, project_root: Path) -> dict[str, object]:
    policy = LowLevelPolicy(
        max_sentence_chars=180,
        max_candidates=3,
        worker_timeout_seconds=30.0,
        worker_memory_mib=1_024,
        max_observations_per_wave=48,
    )
    arena = ArtifactArena(build_dialogue_registry())
    gateway = ExperienceGateway(
        arena, session_id="sys-09", policy=policy, source_root=source_root
    )
    knowledge = KnowledgeAdmissionEngine(arena, context_ref=WORLD)
    concepts = build_real_concept_context(
        arena,
        gateway,
        knowledge,
        source_root=source_root,
        project_root=project_root,
        policy=policy,
    )
    learned_context = tuple(concepts["learned"]) + (concepts["recursive"],)

    dialogue_pairs = gateway.ingest_dialogue_tsv(
        source_root / DIALOGUE_SOURCE,
        dialogue_ref=DIALOGUE,
        experience_prefix="sys-09-dialogue",
        sequence_start=21,
        max_turns=13,
    )
    extractor = ContextualMentionExtractor(arena, world_context_ref=WORLD)
    identity = ContextualIdentityEngine(
        arena, world_context_ref=WORLD, discourse_ref=DIALOGUE
    )
    temporal_analyzer = RelationalTemporalAnalyzer(arena)
    temporal_reasoner = TemporalReasoner(arena)
    interpreter = DialogueTurnInterpreter(arena, maximum_referents=8)
    gameboard = DialogueGameboard(arena, project_root=project_root)

    l1_ledgers = []
    l2_batches = []
    branch_sets = []
    dialogue_episodes = []
    temporal_sets = []
    temporal_memories = []
    mention_sets = []
    identity_beams = []
    discourse_memories = []
    contents = []
    goals = []
    decisions = []
    states = []
    previous_state = None
    for turn_index, (_, observation) in enumerate(dialogue_pairs):
        l1, l2, local_branches, _ = process_wave(
            arena, (observation,), project_root=project_root, policy=policy
        )
        branch = local_branches[0]
        knowledge.observe(branch)
        episode = knowledge._episode_artifacts[branch.artifact_id]
        local_temporal = tuple(
            temporal_analyzer.analyze(arena.get(row["candidate_ref"]))
            for row in thaw_json(branch.payload_native)["branches"]
        )
        temporal_set = temporal_analyzer.group(branch, local_temporal)
        temporal_sets.append(temporal_set)
        temporal_memory = temporal_reasoner.remember(temporal_sets)
        local_mentions = tuple(
            extractor.extract(arena.get(row["candidate_ref"]))
            for row in thaw_json(branch.payload_native)["branches"]
        )
        beam = identity.resolve_observation(
            branch, local_mentions, temporal_index=turn_index
        )
        discourse_memory = identity.finalize(
            episode_memories=dialogue_episodes + [episode],
            temporal_memory=temporal_memory,
        )
        content = interpreter.interpret(
            branch, beam, learned_context=learned_context
        )
        goal, decision, state = gameboard.advance(
            content,
            episode_memory=episode,
            identity_beam=beam,
            temporal_memory=temporal_memory,
            discourse_memory=discourse_memory,
            previous_state=previous_state,
        )
        l1_ledgers.append(l1)
        l2_batches.append(l2)
        branch_sets.append(branch)
        dialogue_episodes.append(episode)
        temporal_memories.append(temporal_memory)
        mention_sets.append(local_mentions)
        identity_beams.append(beam)
        discourse_memories.append(discourse_memory)
        contents.append(content)
        goals.append(goal)
        decisions.append(decision)
        states.append(state)
        previous_state = state
    return locals()


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    run = execute(ROOT, project_root=ROOT)
    arena = run["arena"]
    contents = run["contents"]
    states = run["states"]
    decisions = run["decisions"]
    final_state = states[-1]
    final = thaw_json(final_state.payload_native)
    content_payloads = [thaw_json(row.payload_native) for row in contents]
    state_payloads = [thaw_json(row.payload_native) for row in states]

    first_qud = state_payloads[4]["active_qud_ref"]
    first_proposal = state_payloads[5]["proposals"][-1]
    first_grounding = state_payloads[6]["groundings"][-1]
    location_qud = state_payloads[7]["active_qud_ref"]
    location_proposal = state_payloads[8]["proposals"][-1]
    repair = state_payloads[9]["repairs"][-1]
    clarification_qud = state_payloads[10]["active_qud_ref"]
    clarification = next(row for row in state_payloads[10]["quds"] if row["qud_ref"] == clarification_qud)
    clarification_grounding = state_payloads[11]["groundings"][-1]
    final_qud = final["active_qud_ref"]

    with tempfile.TemporaryDirectory(prefix="seman2-sys09-replay-") as temp_name:
        replay_root = Path(temp_name)
        for source in (CONCEPT_SOURCE, DIALOGUE_SOURCE):
            destination = replay_root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, destination)
        replay = execute(replay_root, project_root=ROOT)
        replay_equal = stable_view(arena) == stable_view(replay["arena"])
        replay_core_equal = run["knowledge"].core.as_dict() == replay["knowledge"].core.as_dict()

    restored = ArtifactArena.restore(build_dialogue_registry(), arena.as_dict())
    before_repeat = len(arena.query())
    repeated = run["gameboard"].advance(
        contents[-1],
        episode_memory=run["dialogue_episodes"][-1],
        identity_beam=run["identity_beams"][-1],
        temporal_memory=run["temporal_memories"][-1],
        discourse_memory=run["discourse_memories"][-1],
        previous_state=states[-2],
    )
    after_repeat = len(arena.query())
    invalid_content_rejected = rejects_contract(
        lambda: run["interpreter"].interpret(
            run["dialogue_episodes"][0],
            run["identity_beams"][0],
            learned_context=run["learned_context"],
        )
    )
    invalid_state_rejected = rejects_contract(
        lambda: run["gameboard"].advance(
            contents[-1],
            episode_memory=run["dialogue_episodes"][-1],
            identity_beam=run["identity_beams"][-1],
            temporal_memory=run["temporal_memories"][-1],
            discourse_memory=run["discourse_memories"][-1],
            previous_state=run["dialogue_episodes"][-2],
        )
    )
    final_ancestry_types = {
        row.artifact_type for row in arena.ancestry(final_state.artifact_id)
    }
    source_code = (
        ROOT / "seman2_runtime/dialogue_system.py"
    ).read_text(encoding="utf-8").lower()
    dialogue_observation_refs = [row[1].observation_refs[0] for row in run["dialogue_pairs"]]

    checks = {
        "real_SYS08_concepts_are_reconstructed_before_dialogue": (
            len(run["concepts"]["learned"]) == 3
            and run["concepts"]["recursive"].artifact_type == "recursive-learned-concept"
            and all(row.created_sequence < run["dialogue_pairs"][0][0].created_sequence for row in run["learned_context"])
        ),
        "dialogue_gateway_preserves_real_speaker_turn_and_surface_boundaries": all(
            thaw_json(experience.payload_native)["channel"] == "dialogue"
            and thaw_json(experience.payload_native)["turn_index"] == index
            and thaw_json(experience.payload_native)["speaker_ref"].startswith("speaker:")
            and "\t" not in thaw_json(observation.payload_native)["surface"]
            for index, (experience, observation) in enumerate(run["dialogue_pairs"])
        ),
        "every_turn_crosses_closed_real_L0_to_L3_batches": (
            len(run["l1_ledgers"]) == len(run["l2_batches"]) == len(run["branch_sets"]) == 13
            and all(row.closed and row.recompute_digest() == row.ledger_digest for row in run["l1_ledgers"])
            and all(row.closed and row.recompute_digest() == row.batch_digest for row in run["l2_batches"])
        ),
        "every_turn_produces_real_episode_identity_temporal_and_discourse_memory": (
            len(run["dialogue_episodes"]) == len(run["identity_beams"]) == len(run["temporal_memories"]) == len(run["discourse_memories"]) == 13
            and all(row.artifact_type == "episode-memory" for row in run["dialogue_episodes"])
            and all(row.artifact_type == "identity-beam" for row in run["identity_beams"])
            and all(row.artifact_type == "temporal-memory" for row in run["temporal_memories"])
            and all(row.artifact_type == "discourse-memory" for row in run["discourse_memories"])
        ),
        "dialogue_interpretation_uses_MRS_and_never_raw_surface": all(
            thaw_json(row.payload_projection)["raw_surface_accessed"] is False
            and row.parent_ids[0] == run["branch_sets"][index].artifact_id
            and row.parent_ids[1] == run["identity_beams"][index].artifact_id
            for index, row in enumerate(contents)
        ),
        "question_force_is_derived_from_real_MRS_events": (
            content_payloads[4]["question_type"] == "wh"
            and "question" in {row["act"] for row in content_payloads[4]["act_candidates"]}
            and content_payloads[10]["question_type"] == "polar"
            and content_payloads[12]["question_type"] == "wh"
        ),
        "fragments_are_preserved_as_analysed_content": (
            "fragment" in {row["act"] for row in content_payloads[5]["act_candidates"]}
            and "fragment" in {row["act"] for row in content_payloads[8]["act_candidates"]}
            and state_payloads[5]["history"][-1]["move_kind"] == "answer-fragment"
        ),
        "grounding_and_correction_come_from_real_formal_relations": (
            "grounding" in {row["act"] for row in content_payloads[6]["act_candidates"]}
            and "correction" in {row["act"] for row in content_payloads[9]["act_candidates"]}
            and "grounding" in {row["act"] for row in content_payloads[11]["act_candidates"]}
        ),
        "first_question_fragment_and_grounding_share_exact_QUD": (
            first_proposal["qud_ref"] == first_qud
            and first_grounding["target_ref"] == first_proposal["proposal_ref"]
            and next(row for row in state_payloads[6]["quds"] if row["qud_ref"] == first_qud)["status"] == "grounded"
        ),
        "new_question_changes_QUD_without_erasing_grounded_history": (
            location_qud != first_qud
            and any(row["qud_ref"] == first_qud and row["status"] == "grounded" for row in state_payloads[7]["quds"])
            and len(state_payloads[7]["quds"]) == 2
        ),
        "correction_changes_focus_and_ranking_revisably": (
            repair["qud_ref"] == location_qud
            and repair["old_focus_identity_ref"] != repair["new_focus_identity_ref"]
            and repair["ranking_before"] != repair["ranking_after"]
            and repair["status"] == "applied-revisably"
            and location_proposal["proposal_ref"] == repair["corrected_proposal_ref"]
            and next(row for row in state_payloads[9]["proposals"] if row["proposal_ref"] == location_proposal["proposal_ref"])["status"] == "corrected"
        ),
        "correction_preserves_every_prior_state_and_observation": (
            len(state_payloads[9]["history"]) == 10
            and state_payloads[9]["history"][:9] == state_payloads[8]["history"]
            and set(states[8].observation_refs) < set(states[9].observation_refs)
        ),
        "clarification_inherits_repaired_focus_and_parent_QUD": (
            clarification["parent_qud_ref"] == location_qud
            and clarification["focus_identity_ref"] == repair["new_focus_identity_ref"]
            and state_payloads[10]["history"][-1]["move_kind"] == "clarification-question"
        ),
        "second_grounding_attaches_to_active_clarification_not_old_content": (
            clarification_grounding["target_ref"] == clarification_qud
            and clarification_grounding["target_ref"] != first_grounding["target_ref"]
            and next(row for row in state_payloads[11]["quds"] if row["qud_ref"] == clarification_qud)["status"] == "grounded"
        ),
        "final_question_changes_QUD_and_retains_complete_gameboard": (
            final_qud not in {first_qud, location_qud, clarification_qud}
            and len(final["quds"]) == 4
            and len(final["history"]) == 13
            and len(final["groundings"]) == 2
            and len(final["repairs"]) == 1
        ),
        "every_turn_is_controlled_by_a_real_bounded_SML_cycle": (
            len(decisions) == 13
            and all(
                "1 rule fired" in thaw_json(row.payload_native)["soar_trace"]["cycle_trace"]
                and len(thaw_json(row.payload_native)["compared_operator_refs"]) == 2
                for row in decisions
            )
        ),
        "Soar_working_memory_contains_projection_not_persistent_stores": all(
            thaw_json(row.payload_projection)["persistent_store_copied_to_soar"] is False
            and all(memory.artifact_id not in thaw_json(row.payload_native)["soar_trace"]["working_memory"] for memory in run["discourse_memories"])
            for row in decisions
        ),
        "each_new_state_consumes_exact_real_turn_memories_and_previous_state": all(
            run["dialogue_episodes"][index].artifact_id in state.parent_ids
            and run["identity_beams"][index].artifact_id in state.parent_ids
            and run["temporal_memories"][index].artifact_id in state.parent_ids
            and run["discourse_memories"][index].artifact_id in state.parent_ids
            and (index == 0 or states[index - 1].artifact_id in state.parent_ids)
            for index, state in enumerate(states)
        ),
        "future_turns_never_enter_earlier_state_ancestry": all(
            not set(dialogue_observation_refs[index + 1 :])
            & {ref for row in arena.ancestry(states[index].artifact_id) for ref in row.observation_refs}
            for index in range(12)
        ),
        "real_SYS08_concepts_are_read_but_irrelevant_ones_are_not_forced": all(
            set(row.parent_ids[2:]) == {concept.artifact_id for concept in run["learned_context"]}
            and all(
                context["applicable"] or context["reason_if_ignored"] == "no-structural-factor-overlap"
                for context in thaw_json(row.payload_native)["concept_context"]
            )
            for row in contents
        ),
        "dialogue_state_never_commits_world_truth": all(
            thaw_json(row.payload_projection)["truth_committed"] is False
            and thaw_json(row.payload_projection)["world_update_performed"] is False
            for row in states
        ),
        "speaker_attribution_is_carried_from_L0_into_every_history_entry": all(
            state_payloads[index]["history"][-1]["speaker_ref"]
            == thaw_json(run["dialogue_pairs"][index][0].payload_native)["speaker_ref"]
            for index in range(13)
        ),
        "parse_alternatives_are_kept_without_multiplying_turns": (
            sum(len(thaw_json(row.payload_native)["branches"]) for row in run["branch_sets"]) > 13
            and len(contents) == len(states) == 13
        ),
        "physical_and_cognitive_budgets_are_explicit": all(
            thaw_json(run["goals"][index].resource_cost)["beam_bound"] == 2
            and thaw_json(decisions[index].resource_cost)["memory_limit_mib"] == 2_048
            and thaw_json(contents[index].resource_cost)["referent_candidates"] <= 8
            for index in range(13)
        ),
        "production_dialogue_engine_contains_no_curriculum_entity_or_surface_rules": all(
            f'"{token}"' not in source_code and f"'{token}'" not in source_code
            for token in (
                "maya", "amira", "notebook", "table", "bag", "blue", "red",
                "which notebook", "on the table", "where is",
            )
        ),
        "services_are_idempotent_without_new_artifacts": (
            repeated[-1].artifact_id == final_state.artifact_id
            and before_repeat == after_repeat
        ),
        "invalid_cross_layer_inputs_are_rejected": invalid_content_rejected and invalid_state_rejected,
        "final_ancestry_reaches_real_L0_to_L6_concepts_memories_and_dialogue": {
            "experience-occurrence", "observation", "analysis-contribution",
            "composed-candidate", "situation-branch-set", "episode-memory",
            "temporal-memory", "identity-beam", "discourse-memory",
            "transformation-episode", "learned-transformation",
            "recursive-learned-concept", "dialogue-turn-content",
            "dialogue-control-goal", "soar-dialogue-decision", "dialogue-state",
        } <= final_ancestry_types,
        "location_independent_full_replay_is_identical": replay_equal and replay_core_equal,
        "arena_restore_is_exact": stable_view(restored) == stable_view(arena),
    }

    operation_by_type = {
        "analysis-contribution": "ACE/ERG analysis",
        "composed-candidate": "generic MRS composition",
        "situation-branch-set": "hypothesis grouping",
        "episode-memory": "episodic admission",
        "temporal-memory": "prefix-bounded temporal memory",
        "identity-beam": "contextual identity ranking",
        "discourse-memory": "prefix-bounded discourse memory",
        "learned-transformation": "real learned conceptual context",
        "recursive-learned-concept": "recursive conceptual context",
        "dialogue-turn-content": "formal pragmatic interpretation",
        "dialogue-control-goal": "bounded operator projection",
        "soar-dialogue-decision": "real SML dialogue control",
        "dialogue-state": "append-only gameboard transition",
    }
    effects = [
        {
            "consumer_artifact_ref": row.artifact_id,
            "input_factor_ref": parent,
            "producer_artifact_ref": row.artifact_id,
            "operation": operation_by_type[row.artifact_type],
            "effect_on_output": f"{row.artifact_type}:{row.status.value}",
            "activation_or_weight_change": "one attributed turn, memory, ranking, or gameboard transition",
            "context_ref": list(row.context_refs),
            "reason_if_ignored": None,
        }
        for row in arena.query()
        if row.artifact_type in operation_by_type
        for parent in row.parent_ids
    ]
    lineage = lineage_manifest(
        arena,
        real_source_refs=[CONCEPT_SOURCE.as_posix(), DIALOGUE_SOURCE.as_posix()],
        causal_effects=effects,
    )
    passed = all(checks.values())
    results = {
        "verdict": "GO" if passed else "NO-GO",
        "scope": "real multi-turn L0-L6 dialogue gameboard over episodic, temporal, discourse, conceptual, and Soar stock",
        "checks": checks,
        "counts": {
            "dialogue_turns": 13,
            "dialogue_states": len(states),
            "quds": len(final["quds"]),
            "proposals": len(final["proposals"]),
            "groundings": len(final["groundings"]),
            "repairs": len(final["repairs"]),
            "soar_cycles": len(decisions),
            "learned_contexts": len(run["learned_context"]),
        },
        "gameboard": final,
        "demonstrated": [
            "every attributed dialogue turn re-enters the real L0-L4 pipeline",
            "MRS-grounded question, fragment, correction, grounding, and clarification acts",
            "append-only QUD, proposal, grounding, repair, and speaker history",
            "correction changes referent ranking without erasing prior states",
            "real bounded Soar operator selection before every next state",
            "prefix-only episodic, temporal, identity, and discourse memories",
            "real concept context with explicit non-activation when irrelevant",
            "complete lineage, replay, idempotence, budgets, and restoration",
        ],
        "not_demonstrated": ["natural-language response generation", "autonomous initiative", "cultural interpretation"],
    }
    write_json("results.json", results)
    write_json("summary.json", {"verdict": results["verdict"], "checks_passed": sum(checks.values()), "checks_total": len(checks), **results["counts"]})
    write_json("lineage.json", lineage)
    write_json("ledger.json", arena.as_dict())
    write_json("gameboard.json", final)
    write_json("dialogue-states.json", state_payloads)
    write_json("versions-and-parameters.json", {
        "python": platform.python_version(),
        "pydelphin": importlib.metadata.version("pydelphin"),
        "registry_digest": arena.registry.digest,
        "policy": run["policy"].__dict__,
        "ace_sha256": sha256_file(ROOT / ".local/bin/ace"),
        "erg_sha256": sha256_file(ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"),
        "concept_source_sha256": sha256_file(ROOT / CONCEPT_SOURCE),
        "dialogue_source_sha256": sha256_file(ROOT / DIALOGUE_SOURCE),
        "soar_version": thaw_json(decisions[-1].payload_native)["soar_trace"]["soar_version"],
    })
    print(json.dumps(results, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
