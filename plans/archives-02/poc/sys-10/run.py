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
OUTPUT = ROOT / "poc/sys-10/output"
CONCEPT_SOURCE = Path("data/curriculum/sys_08_recursive_concepts.txt")
RURAL_SOURCE = Path("data/curriculum/sys_10_rural_biography.txt")
URBAN_SOURCE = Path("data/curriculum/sys_10_urban_biography.txt")
QUESTION_SOURCE = Path("data/curriculum/sys_10_questions.tsv")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import ArtifactArena, ArtifactStatus, thaw_json  # noqa: E402
from seman2_runtime.concept_learning import InductionPolicy  # noqa: E402
from seman2_runtime.contracts import ContractError  # noqa: E402
from seman2_runtime.dialogue_system import DialogueGameboard, DialogueTurnInterpreter  # noqa: E402
from seman2_runtime.discourse_identity_system import ContextualIdentityEngine, ContextualMentionExtractor  # noqa: E402
from seman2_runtime.formal_composition import GenericMRSComposer  # noqa: E402
from seman2_runtime.hypothesis_system import HypothesisManager  # noqa: E402
from seman2_runtime.knowledge_system import KnowledgeAdmissionEngine  # noqa: E402
from seman2_runtime.low_level_system import (  # noqa: E402
    AceErgAnalyzer, AnalysisOrchestrator, ExperienceGateway, LowLevelPolicy,
    lineage_manifest, sha256_file,
)
from seman2_runtime.recursive_concept_system import RecursiveConceptEngine  # noqa: E402
from seman2_runtime.response_system import (  # noqa: E402
    AutobiographicalRetriever, GeneratedTurnGateway, ResponseController,
    SimpleNLGRealizer, build_response_registry,
)
from seman2_runtime.temporal_system import RelationalTemporalAnalyzer, TemporalReasoner  # noqa: E402
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
    branches = tuple(manager.group(by_observation[row.artifact_id]) for row in observations)
    return l1, l2, branches, candidates


def build_real_concept_context(
    arena: ArtifactArena,
    gateway: ExperienceGateway,
    knowledge: KnowledgeAdmissionEngine,
    *,
    model_name: str,
    source_root: Path,
    project_root: Path,
    policy: LowLevelPolicy,
) -> dict[str, object]:
    pairs = gateway.ingest_file(
        source_root / CONCEPT_SOURCE,
        experience_prefix=f"sys-10-{model_name}-concept",
        max_observations=19,
    )
    observations = tuple(row[1] for row in pairs)
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
        context_ref=f"ctx:sys-10:{model_name}:world",
        induction_policy=InductionPolicy(
            minimum_support=2,
            minimum_pattern_size=2,
            minimum_specialization_support=2,
            maximum_structures=16,
        ),
    )
    for number, start in enumerate((0, 3, 6, 9, 12), 1):
        learner.observe_scenario(
            f"scenario:sys-10:{model_name}:concept:{number}",
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
        context_ref=f"ctx:sys-10:{model_name}:world",
        maximum_structures=16,
    )
    normal = controller.apply(learned, before_episode=episodes[15], event_episode=episodes[16])
    divergent = controller.apply(learned, before_episode=episodes[17], event_episode=episodes[18])
    outcome_pairs = gateway.ingest_file(
        source_root / CONCEPT_SOURCE,
        experience_prefix=f"sys-10-{model_name}-concept",
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


def execute_model(
    model_name: str,
    biography_source: Path,
    source_root: Path,
    *,
    project_root: Path,
) -> dict[str, object]:
    world = f"ctx:sys-10:{model_name}:world"
    dialogue = f"dialogue:sys-10:{model_name}"
    policy = LowLevelPolicy(
        max_sentence_chars=180,
        max_candidates=3,
        worker_timeout_seconds=30.0,
        worker_memory_mib=1_024,
        max_observations_per_wave=48,
    )
    arena = ArtifactArena(build_response_registry())
    gateway = ExperienceGateway(
        arena,
        session_id=f"sys-10-{model_name}",
        policy=policy,
        source_root=source_root,
        mode="chatbot",
    )
    knowledge = KnowledgeAdmissionEngine(arena, context_ref=world)
    concepts = build_real_concept_context(
        arena,
        gateway,
        knowledge,
        model_name=model_name,
        source_root=source_root,
        project_root=project_root,
        policy=policy,
    )
    learned_context = tuple(concepts["learned"]) + (concepts["recursive"],)

    biography_pairs = gateway.ingest_file(
        source_root / biography_source,
        experience_prefix=f"sys-10-{model_name}-biography",
        sequence_start=21,
        source_kind="autobiographical-curriculum",
        max_observations=5,
    )
    extractor = ContextualMentionExtractor(arena, world_context_ref=world)
    identity = ContextualIdentityEngine(arena, world_context_ref=world, discourse_ref=dialogue)
    temporal_analyzer = RelationalTemporalAnalyzer(arena)
    temporal_reasoner = TemporalReasoner(arena)
    all_temporal_sets = []
    all_episodes = []
    biography_episodes = []
    biography_branches = []
    biography_l1 = []
    biography_l2 = []
    biography_beams = []
    biography_temporal_memories = []
    biography_discourse_memories = []
    for index, (_, observation) in enumerate(biography_pairs):
        l1, l2, branches, _ = process_wave(
            arena, (observation,), project_root=project_root, policy=policy
        )
        branch = branches[0]
        knowledge.observe(branch)
        episode = knowledge._episode_artifacts[branch.artifact_id]
        local_temporal = tuple(
            temporal_analyzer.analyze(arena.get(row["candidate_ref"]))
            for row in thaw_json(branch.payload_native)["branches"]
        )
        temporal_set = temporal_analyzer.group(branch, local_temporal)
        all_temporal_sets.append(temporal_set)
        temporal_memory = temporal_reasoner.remember(all_temporal_sets)
        local_mentions = tuple(
            extractor.extract(arena.get(row["candidate_ref"]))
            for row in thaw_json(branch.payload_native)["branches"]
        )
        beam = identity.resolve_observation(branch, local_mentions, temporal_index=index)
        all_episodes.append(episode)
        discourse_memory = identity.finalize(
            episode_memories=all_episodes, temporal_memory=temporal_memory
        )
        biography_l1.append(l1)
        biography_l2.append(l2)
        biography_branches.append(branch)
        biography_episodes.append(episode)
        biography_beams.append(beam)
        biography_temporal_memories.append(temporal_memory)
        biography_discourse_memories.append(discourse_memory)

    question_pairs = gateway.ingest_dialogue_tsv(
        source_root / QUESTION_SOURCE,
        dialogue_ref=dialogue,
        experience_prefix=f"sys-10-{model_name}-question",
        sequence_start=26,
        max_turns=4,
    )
    interpreter = DialogueTurnInterpreter(arena, maximum_referents=8)
    gameboard = DialogueGameboard(arena, project_root=project_root)
    retriever = AutobiographicalRetriever(arena, maximum_memories=16)
    response_controller = ResponseController(arena, project_root=project_root)
    realizer = SimpleNLGRealizer(arena, project_root=project_root)
    generated_gateway = GeneratedTurnGateway(arena)
    question_l1 = []
    question_l2 = []
    question_branches = []
    question_episodes = []
    question_beams = []
    question_temporal_memories = []
    question_discourse_memories = []
    contents = []
    dialogue_goals = []
    dialogue_decisions = []
    states = []
    retrievals = []
    response_goals = []
    response_decisions = []
    plans = []
    realized = []
    reingested = []
    previous_state = None
    for offset, (_, observation) in enumerate(question_pairs):
        temporal_index = len(biography_pairs) + offset
        l1, l2, branches, _ = process_wave(
            arena, (observation,), project_root=project_root, policy=policy
        )
        branch = branches[0]
        knowledge.observe(branch)
        episode = knowledge._episode_artifacts[branch.artifact_id]
        local_temporal = tuple(
            temporal_analyzer.analyze(arena.get(row["candidate_ref"]))
            for row in thaw_json(branch.payload_native)["branches"]
        )
        temporal_set = temporal_analyzer.group(branch, local_temporal)
        all_temporal_sets.append(temporal_set)
        temporal_memory = temporal_reasoner.remember(all_temporal_sets)
        local_mentions = tuple(
            extractor.extract(arena.get(row["candidate_ref"]))
            for row in thaw_json(branch.payload_native)["branches"]
        )
        beam = identity.resolve_observation(branch, local_mentions, temporal_index=temporal_index)
        all_episodes.append(episode)
        discourse_memory = identity.finalize(
            episode_memories=all_episodes, temporal_memory=temporal_memory
        )
        content = interpreter.interpret(branch, beam, learned_context=learned_context)
        dialogue_goal, dialogue_decision, state = gameboard.advance(
            content,
            episode_memory=episode,
            identity_beam=beam,
            temporal_memory=temporal_memory,
            discourse_memory=discourse_memory,
            previous_state=previous_state,
        )
        retrieval = retriever.retrieve(
            content,
            state,
            episode_memories=biography_episodes,
            identity_beam=beam,
            temporal_memory=temporal_memory,
            discourse_memory=discourse_memory,
        )
        response_goal, response_decision, plan = response_controller.plan(
            retrieval, state, discourse_memory
        )
        turn = realizer.realize(plan)
        feedback = generated_gateway.reingest(
            turn,
            dialogue_ref=dialogue,
            turn_index=offset * 2 + 1,
            sequence_index=30 + offset,
        )
        question_l1.append(l1)
        question_l2.append(l2)
        question_branches.append(branch)
        question_episodes.append(episode)
        question_beams.append(beam)
        question_temporal_memories.append(temporal_memory)
        question_discourse_memories.append(discourse_memory)
        contents.append(content)
        dialogue_goals.append(dialogue_goal)
        dialogue_decisions.append(dialogue_decision)
        states.append(state)
        retrievals.append(retrieval)
        response_goals.append(response_goal)
        response_decisions.append(response_decision)
        plans.append(plan)
        realized.append(turn)
        reingested.append(feedback)
        previous_state = state
    return locals()


def execute(source_root: Path, *, project_root: Path) -> dict[str, dict[str, object]]:
    return {
        "rural": execute_model("rural", RURAL_SOURCE, source_root, project_root=project_root),
        "urban": execute_model("urban", URBAN_SOURCE, source_root, project_root=project_root),
    }


def artifact_payloads(rows: list[object]) -> list[dict[str, object]]:
    return [thaw_json(row.payload_native) for row in rows]


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    run = execute(ROOT, project_root=ROOT)
    rural, urban = run["rural"], run["urban"]
    models = (rural, urban)
    retrieval_payloads = {name: artifact_payloads(model["retrievals"]) for name, model in run.items()}
    plan_payloads = {name: artifact_payloads(model["plans"]) for name, model in run.items()}
    surfaces = {
        name: [thaw_json(row.payload_native)["surface"] for row in model["realized"]]
        for name, model in run.items()
    }

    with tempfile.TemporaryDirectory(prefix="seman2-sys10-replay-") as temp_name:
        replay_root = Path(temp_name)
        for source in (CONCEPT_SOURCE, RURAL_SOURCE, URBAN_SOURCE, QUESTION_SOURCE):
            destination = replay_root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, destination)
        replay = execute(replay_root, project_root=ROOT)
        replay_equal = all(
            stable_view(run[name]["arena"]) == stable_view(replay[name]["arena"])
            for name in run
        )
        replay_core_equal = all(
            run[name]["knowledge"].core.as_dict() == replay[name]["knowledge"].core.as_dict()
            for name in run
        )

    restored_equal = all(
        stable_view(ArtifactArena.restore(build_response_registry(), model["arena"].as_dict()))
        == stable_view(model["arena"])
        for model in models
    )
    before_repeat = [len(model["arena"].query()) for model in models]
    repeated = [
        model["generated_gateway"].reingest(
            model["realized"][-1],
            dialogue_ref=model["dialogue"],
            turn_index=7,
            sequence_index=33,
        )
        for model in models
    ]
    after_repeat = [len(model["arena"].query()) for model in models]
    invalid_retrieval_rejected = rejects_contract(
        lambda: rural["retriever"].retrieve(
            rural["contents"][0],
            rural["states"][0],
            episode_memories=urban["biography_episodes"],
            identity_beam=rural["question_beams"][0],
            temporal_memory=rural["question_temporal_memories"][0],
            discourse_memory=rural["question_discourse_memories"][0],
        )
    )
    invalid_plan_rejected = rejects_contract(
        lambda: rural["response_controller"].plan(
            rural["question_episodes"][0],
            rural["states"][0],
            rural["question_discourse_memories"][0],
        )
    )

    question_surfaces = [
        thaw_json(pair[1].payload_native)["surface"] for pair in rural["question_pairs"]
    ]
    urban_question_surfaces = [
        thaw_json(pair[1].payload_native)["surface"] for pair in urban["question_pairs"]
    ]
    expected_types = {
        "experience-occurrence", "observation", "analysis-contribution",
        "composed-candidate", "situation-branch-set", "episode-memory",
        "temporal-analysis", "temporal-branch-set", "temporal-memory",
        "identity-mention-candidate", "identity-beam", "discourse-memory",
        "learned-transformation", "recursive-learned-concept",
        "dialogue-turn-content", "dialogue-control-goal", "soar-dialogue-decision",
        "dialogue-state", "internal-memory-retrieval", "response-control-goal",
        "soar-response-decision", "communicative-plan", "realized-turn",
        "reingested-experience", "reingested-observation",
    }
    source_code = (ROOT / "seman2_runtime/response_system.py").read_text(encoding="utf-8").lower()
    biography_episode_sets = {
        name: {row.artifact_id for row in model["biography_episodes"]}
        for name, model in run.items()
    }

    checks = {
        "two_genuinely_different_biography_sources_are_ingested": (
            sha256_file(ROOT / RURAL_SOURCE) != sha256_file(ROOT / URBAN_SOURCE)
            and all(len(model["biography_pairs"]) == 5 for model in models)
            and all(
                thaw_json(pair[0].payload_native)["source_kind"] == "autobiographical-curriculum"
                for model in models for pair in model["biography_pairs"]
            )
        ),
        "both_models_receive_the_exact_same_four_new_questions": (
            question_surfaces == urban_question_surfaces
            and len(question_surfaces) == 4
            and all(
                thaw_json(pair[0].payload_native)["source_sha256"] == sha256_file(ROOT / QUESTION_SOURCE)
                for model in models for pair in model["question_pairs"]
            )
        ),
        "real_SYS08_concepts_are_reconstructed_in_each_model": all(
            len(model["concepts"]["learned"]) == 3
            and model["concepts"]["recursive"].artifact_type == "recursive-learned-concept"
            for model in models
        ),
        "every_biographical_experience_crosses_closed_L0_to_L4_processing": all(
            len(model["biography_l1"]) == len(model["biography_l2"]) == len(model["biography_episodes"]) == 5
            and all(row.closed and row.recompute_digest() == row.ledger_digest for row in model["biography_l1"])
            and all(row.closed and row.recompute_digest() == row.batch_digest for row in model["biography_l2"])
            for model in models
        ),
        "every_question_crosses_real_L0_to_L4_and_dialogue_gameboard": all(
            len(model["question_l1"]) == len(model["contents"]) == len(model["states"]) == 4
            and all(row.closed for row in model["question_l1"])
            and all("question" in {item["act"] for item in thaw_json(content.payload_native)["act_candidates"]} for content in model["contents"])
            for model in models
        ),
        "retrieval_consumes_only_the_models_real_biography_episodes": all(
            set(payload["memory_scope_refs"]) == biography_episode_sets[name]
            and set(payload["memory_scope_refs"]) <= set(retrieval.parent_ids)
            for name, model in run.items()
            for retrieval, payload in zip(model["retrievals"], retrieval_payloads[name], strict=True)
        ),
        "retrieval_also_consumes_real_identity_temporal_discourse_and_dialogue_states": all(
            model["question_beams"][index].artifact_id in retrieval.parent_ids
            and model["question_temporal_memories"][index].artifact_id in retrieval.parent_ids
            and model["question_discourse_memories"][index].artifact_id in retrieval.parent_ids
            and model["states"][index].artifact_id in retrieval.parent_ids
            for model in models for index, retrieval in enumerate(model["retrievals"])
        ),
        "rural_model_answers_apples_from_its_own_memory": (
            retrieval_payloads["rural"][0]["epistemic_status"] == "supported"
            and retrieval_payloads["rural"][0]["answer_candidates"][0]["object_phrase"].lower() == "trees"
            and bool(plan_payloads["rural"][0]["evidence_refs"])
        ),
        "urban_model_does_not_invent_an_apple_answer": (
            retrieval_payloads["urban"][0]["epistemic_status"] == "unknown"
            and retrieval_payloads["urban"][0]["answer_candidates"] == []
            and plan_payloads["urban"][0]["evidence_refs"] == []
        ),
        "urban_model_answers_trains_from_its_own_memory": (
            retrieval_payloads["urban"][1]["epistemic_status"] == "supported"
            and retrieval_payloads["urban"][1]["answer_candidates"][0]["object_phrase"].lower() == "stations"
            and bool(plan_payloads["urban"][1]["evidence_refs"])
        ),
        "rural_model_does_not_invent_a_train_answer": (
            retrieval_payloads["rural"][1]["epistemic_status"] == "unknown"
            and retrieval_payloads["rural"][1]["answer_candidates"] == []
            and plan_payloads["rural"][1]["evidence_refs"] == []
        ),
        "unsupported_dolphin_question_produces_explicit_ignorance_in_both_models": all(
            retrieval_payloads[name][2]["qualification"] == "no-accessible-internal-path"
            and plan_payloads[name][2]["intent"] == "acknowledge-ignorance"
            and plan_payloads[name][2]["content"]["answer_refs"] == []
            for name in run
        ),
        "conflicting_lantern_locations_remain_qualified_and_trigger_clarification": all(
            retrieval_payloads[name][3]["epistemic_status"] == "ambiguous"
            and retrieval_payloads[name][3]["qualification"] == "multiple-incompatible-accessible-locations"
            and len(retrieval_payloads[name][3]["answer_candidates"]) == 2
            and plan_payloads[name][3]["intent"] == "request-location-clarification"
            for name in run
        ),
        "biography_changes_the_answers_to_identical_questions": (
            surfaces["rural"][0] != surfaces["urban"][0]
            and surfaces["rural"][1] != surfaces["urban"][1]
            and retrieval_payloads["rural"][0]["query_frame"]["subject_predicate"]
            == retrieval_payloads["urban"][0]["query_frame"]["subject_predicate"]
        ),
        "every_supported_or_ambiguous_answer_path_ends_in_own_biography": all(
            set(path["episode_ref"] for path in payload["support_paths"])
            <= biography_episode_sets[name]
            for name in run for payload in retrieval_payloads[name]
        ),
        "no_evidence_crosses_between_model_sessions": (
            biography_episode_sets["rural"].isdisjoint(biography_episode_sets["urban"])
            and all(row.session_id == "sys-10-rural" for row in rural["arena"].query())
            and all(row.session_id == "sys-10-urban" for row in urban["arena"].query())
        ),
        "communicative_plans_are_explicit_and_contain_no_surface_sentence": all(
            thaw_json(plan.payload_projection)["surface_text_present"] is False
            and "surface" not in thaw_json(plan.payload_native)
            and thaw_json(plan.payload_native)["content"]["intent"] == thaw_json(plan.payload_native)["intent"]
            for model in models for plan in model["plans"]
        ),
        "plan_evidence_and_explanation_paths_are_complete": all(
            set(payload["evidence_refs"]) <= set(payload["explanation_path"])
            and model["retrievals"][index].artifact_id in payload["explanation_path"]
            and model["response_decisions"][index].artifact_id in payload["explanation_path"]
            for name, model in run.items() for index, payload in enumerate(plan_payloads[name])
        ),
        "all_response_choices_are_real_one_cycle_bounded_SML_decisions": all(
            "1 rule fired" in thaw_json(row.payload_native)["soar_trace"]["cycle_trace"]
            and len(thaw_json(row.payload_native)["compared_operator_refs"]) == 2
            for model in models for row in model["response_decisions"]
        ),
        "Soar_receives_only_bounded_projections_not_persistent_memory": all(
            thaw_json(row.payload_projection)["persistent_store_copied_to_soar"] is False
            and all(
                memory.artifact_id not in thaw_json(row.payload_native)["soar_trace"]["working_memory"]
                for memory in model["biography_episodes"]
            )
            for model in models for row in model["response_decisions"]
        ),
        "real_SimpleNLG_4_5_realizes_every_plan_without_added_content": all(
            thaw_json(row.payload_native)["backend"] == "SimpleNLG-4.5.0"
            and thaw_json(row.payload_native)["backend_sha256"] == sha256_file(ROOT / ".local/opt/simplenlg/SimpleNLG-4.5.0.jar")
            and thaw_json(row.payload_native)["added_content"] == []
            and thaw_json(row.payload_projection)["content_selected"] is False
            for model in models for row in model["realized"]
        ),
        "supported_surfaces_realize_only_retrieved_relations": (
            surfaces["rural"][0] == "Apples grow on trees."
            and surfaces["urban"][1] == "Trains stop at stations."
        ),
        "ignorance_surfaces_are_explicit_and_non_fabricating": all(
            surfaces[name][index] == "I do not know."
            for name, index in (("urban", 0), ("rural", 1), ("rural", 2), ("urban", 2))
        ),
        "ambiguous_surfaces_preserve_both_internal_alternatives": all(
            "barn" in surfaces[name][3].lower()
            and "shed" in surfaces[name][3].lower()
            and surfaces[name][3].endswith("?")
            for name in run
        ),
        "every_realized_turn_is_reingested_exactly_as_L0_feedback": all(
            thaw_json(pair[1].payload_native)["surface"] == thaw_json(turn.payload_native)["surface"]
            and thaw_json(pair[1].payload_native)["surface_sha256"] == thaw_json(turn.payload_native)["surface_sha256"]
            and pair[0].parent_ids == (turn.artifact_id,)
            and pair[0].wave == turn.wave + 1
            for model in models for turn, pair in zip(model["realized"], model["reingested"], strict=True)
        ),
        "generated_turns_are_not_committed_as_world_truth": all(
            thaw_json(pair[0].payload_projection)["truth_committed"] is False
            and thaw_json(pair[1].payload_projection)["truth_committed"] is False
            for model in models for pair in model["reingested"]
        ),
        "the_whole_execution_is_in_real_chatbot_mode": all(
            row.mode == "chatbot" for model in models for row in model["arena"].query()
        ),
        "retrieval_and_response_never_claim_raw_external_or_LLM_access": all(
            thaw_json(row.payload_projection).get("raw_source_accessed", False) is False
            and thaw_json(row.payload_projection).get("external_source_consulted", False) is False
            for model in models
            for row in (*model["retrievals"], *model["plans"])
        ),
        "production_response_code_contains_no_curriculum_entity_rules_or_external_lookup": (
            all(f'"{token}"' not in source_code and f"'{token}'" not in source_code for token in ("apple", "train", "dolphin", "lantern", "barn", "shed"))
            and "openrouter" not in source_code
            and "english-dictionary" not in source_code
        ),
        "all_parse_alternatives_are_retained_while_one_answer_is_aggregated_per_experience": all(
            sum(len(thaw_json(row.payload_native)["branches"]) for row in model["biography_branches"]) >= 5
            and all(row.status is ArtifactStatus.SUCCESS for row in model["biography_branches"])
            for model in models
        ),
        "physical_and_cognitive_bounds_are_explicit": all(
            thaw_json(retrieval.resource_cost)["memories_examined"] == 5
            and thaw_json(goal.resource_cost)["beam_bound"] == 2
            and thaw_json(decision.resource_cost)["memory_limit_mib"] == 2_048
            for model in models
            for retrieval, goal, decision in zip(model["retrievals"], model["response_goals"], model["response_decisions"], strict=True)
        ),
        "final_feedback_ancestry_reaches_real_L0_through_L7_stock": all(
            expected_types <= {row.artifact_type for row in model["arena"].ancestry(model["reingested"][-1][1].artifact_id)}
            for model in models
        ),
        "cross_model_and_cross_layer_misuse_is_rejected": invalid_retrieval_rejected and invalid_plan_rejected,
        "response_and_feedback_services_are_idempotent": (
            before_repeat == after_repeat
            and all(repeated[index][1].artifact_id == models[index]["reingested"][-1][1].artifact_id for index in range(2))
        ),
        "location_independent_full_replay_is_identical": replay_equal and replay_core_equal,
        "both_arenas_restore_exactly": restored_equal,
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
        "dialogue-state": "append-only gameboard transition",
        "internal-memory-retrieval": "structural autobiographical retrieval",
        "response-control-goal": "bounded response operator projection",
        "soar-response-decision": "real SML response control",
        "communicative-plan": "epistemically qualified content planning",
        "realized-turn": "SimpleNLG surface realization",
        "reingested-experience": "L7-to-L0 generated feedback",
        "reingested-observation": "generated surface observation",
    }
    manifests = []
    for name, model in run.items():
        effects = [
            {
                "consumer_artifact_ref": row.artifact_id,
                "input_factor_ref": parent,
                "producer_artifact_ref": row.artifact_id,
                "operation": operation_by_type[row.artifact_type],
                "effect_on_output": f"{row.artifact_type}:{row.status.value}",
                "activation_or_weight_change": "one attributed structural contribution or controlled transition",
                "context_ref": list(row.context_refs),
                "reason_if_ignored": None,
            }
            for row in model["arena"].query()
            if row.artifact_type in operation_by_type
            for parent in row.parent_ids
        ]
        manifests.append(
            lineage_manifest(
                model["arena"],
                real_source_refs=[CONCEPT_SOURCE.as_posix(), model["biography_source"].as_posix(), QUESTION_SOURCE.as_posix()],
                causal_effects=effects,
            )
        )
    lineage = {
        "architecture": "plans/architecture_cognitive_developpementale.md",
        "artifact_levels": sorted({level for manifest in manifests for level in manifest["artifact_levels"]}),
        "real_source_refs": sorted({ref for manifest in manifests for ref in manifest["real_source_refs"]}),
        "causal_effects": [effect for manifest in manifests for effect in manifest["causal_effects"]],
        "artifacts": [artifact for manifest in manifests for artifact in manifest["artifacts"]],
    }
    passed = all(checks.values())
    results = {
        "verdict": "GO" if passed else "NO-GO",
        "scope": "two autobiographical chatbot models from real L0-L7 cognitive stock with L7-to-L0 feedback",
        "checks": checks,
        "counts": {
            "models": 2,
            "biographical_experiences": sum(len(model["biography_pairs"]) for model in models),
            "shared_questions_per_model": 4,
            "responses": sum(len(model["realized"]) for model in models),
            "response_soar_cycles": sum(len(model["response_decisions"]) for model in models),
            "reingested_turns": sum(len(model["reingested"]) for model in models),
        },
        "questions": question_surfaces,
        "surfaces": surfaces,
        "retrievals": retrieval_payloads,
        "plans": plan_payloads,
        "demonstrated": [
            "biography-dependent answers to identical new questions",
            "structural retrieval from genuine L4 episode memories and L2 ancestry",
            "explicit ignorance and ambiguity without plausible invention",
            "real dialogue gameboard and two real bounded SML decisions per question",
            "inspectable L6 plans followed by content-neutral SimpleNLG realization",
            "exact L7-to-L0 generated-turn feedback without truth commitment",
            "complete lineage, replay, idempotence, budgets, and restoration",
        ],
        "not_demonstrated": [
            "open-domain response generation",
            "multi-sentence discourse generation",
            "cultural interpretation",
            "curriculum tutor and external evaluation",
        ],
    }
    write_json("results.json", results)
    write_json("summary.json", {"verdict": results["verdict"], "checks_passed": sum(checks.values()), "checks_total": len(checks), **results["counts"]})
    write_json("lineage.json", lineage)
    write_json("ledgers.json", {name: model["arena"].as_dict() for name, model in run.items()})
    write_json("versions-and-parameters.json", {
        "python": platform.python_version(),
        "pydelphin": importlib.metadata.version("pydelphin"),
        "registry_digest": rural["arena"].registry.digest,
        "policy": rural["policy"].__dict__,
        "ace_sha256": sha256_file(ROOT / ".local/bin/ace"),
        "erg_sha256": sha256_file(ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"),
        "simplenlg_sha256": sha256_file(ROOT / ".local/opt/simplenlg/SimpleNLG-4.5.0.jar"),
        "sources": {source.as_posix(): sha256_file(ROOT / source) for source in (CONCEPT_SOURCE, RURAL_SOURCE, URBAN_SOURCE, QUESTION_SOURCE)},
        "soar_version": thaw_json(rural["response_decisions"][-1].payload_native)["soar_trace"]["soar_version"],
    })
    print(json.dumps(results, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
