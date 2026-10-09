#!/usr/bin/env python3
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "poc/sys-03/output"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import (  # noqa: E402
    ArtifactArena,
    ArtifactStatus,
    thaw_json,
)
from seman2_runtime.cognitive_query import (  # noqa: E402
    AnswerStatus,
    AutobiographicalResponder,
    RelationalQuestion,
)
from seman2_runtime.contracts import ContractError  # noqa: E402
from seman2_runtime.developmental_core import (  # noqa: E402
    DevelopmentalCore,
    RoleBinding,
)
from seman2_runtime.formal_composition import GenericMRSComposer  # noqa: E402
from seman2_runtime.hypothesis_system import HypothesisManager  # noqa: E402
from seman2_runtime.knowledge_system import (  # noqa: E402
    KnowledgeAdmissionEngine,
    build_knowledge_registry,
)
from seman2_runtime.low_level_system import (  # noqa: E402
    AceErgAnalyzer,
    AnalysisOrchestrator,
    ExperienceGateway,
    LowLevelPolicy,
    lineage_manifest,
    sha256_file,
)
from seman2_runtime.semantic_admission import AdmissionStatus  # noqa: E402


LESSON_SOURCE = Path("data/curriculum/sys_03_relations.txt")
CONTROL_SOURCE = Path("data/the_map_of_everything_nlp_novel.txt")
LESSONS = (
    ("lesson-1", "An apple is a fruit."),
    ("lesson-2", "Every apple is a fruit."),
)
CONTROL = (("control", "Maya carried a blue notebook home."),)


def write_json(name: str, value: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def question() -> RelationalQuestion:
    return RelationalQuestion(
        "question:sys-03:apple-kind",
        "relation:kind-of",
        (RoleBinding("subject", "concept-form:external:mrs:_apple_n_1"),),
        "class",
        "ctx:model",
    )


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


def build_L3(
    source_root: Path,
    *,
    project_root: Path,
    session_id: str,
    source: Path,
    rows: tuple[tuple[str, str], ...],
) -> tuple[ArtifactArena, object, object, tuple[object, ...]]:
    policy = LowLevelPolicy(
        max_sentence_chars=160,
        max_candidates=3,
        worker_timeout_seconds=30.0,
        worker_memory_mib=1_024,
        max_observations_per_wave=8,
    )
    arena = ArtifactArena(build_knowledge_registry())
    gateway = ExperienceGateway(
        arena,
        session_id=session_id,
        policy=policy,
        source_root=source_root,
    )
    observations = []
    for sequence, (key, sentence) in enumerate(rows):
        _, observation = gateway.ingest_sentence_from_file(
            source_root / source,
            sentence,
            experience_ref=f"experience:sys-03:{key}",
            sequence_index=sequence,
        )
        observations.append(observation)
    analyzer = AceErgAnalyzer(arena, project_root=project_root, policy=policy)
    l1_ledger, _ = AnalysisOrchestrator(policy=policy).execute(
        observations, analyzer
    )
    l2_batch, candidates = GenericMRSComposer(arena).compose_ledger(l1_ledger)
    by_observation = {row.artifact_id: [] for row in observations}
    for candidate in candidates:
        l1 = arena.get(candidate.parent_ids[0])
        by_observation[l1.parent_ids[0]].append(candidate)
    manager = HypothesisManager(arena)
    branch_sets = tuple(
        manager.group(by_observation[observation.artifact_id])
        for observation in observations
    )
    return arena, l1_ledger, l2_batch, branch_sets


def train_informed(
    source_root: Path, *, project_root: Path
) -> tuple[ArtifactArena, KnowledgeAdmissionEngine, dict[str, object]]:
    arena, l1_ledger, l2_batch, branch_sets = build_L3(
        source_root,
        project_root=project_root,
        session_id="sys-03-informed",
        source=LESSON_SOURCE,
        rows=LESSONS,
    )
    knowledge = KnowledgeAdmissionEngine(arena)
    first_candidates = knowledge.observe(branch_sets[0])
    if len(first_candidates) != 1:
        raise AssertionError(f"unexpected first candidates: {first_candidates}")
    candidate_ref = first_candidates[0]
    after_first = knowledge.ledger.assess(candidate_ref)
    evidence_after_first = tuple(sorted(knowledge.ledger.evidence))
    duplicate_candidates = knowledge.observe(branch_sets[0])
    after_duplicate = knowledge.ledger.assess(candidate_ref)
    evidence_after_duplicate = tuple(sorted(knowledge.ledger.evidence))
    first_episode_artifact = knowledge._episode_artifacts[branch_sets[0].artifact_id]
    first_episode_ref = thaw_json(first_episode_artifact.payload_native)["memory_item"][
        "content_ref"
    ]
    first_episode_exposures = knowledge.core.memory.get(first_episode_ref).exposures
    pending_projection_rejected = False
    try:
        knowledge.project(candidate_ref, temporal_index=1)
    except ContractError:
        pending_projection_rejected = True

    second_candidates = knowledge.observe(branch_sets[1])
    after_second = knowledge.ledger.assess(candidate_ref)
    projection, memory_artifact = knowledge.project(candidate_ref, temporal_index=2)
    answer = AutobiographicalResponder(knowledge.core).answer_relation(question())
    diagnostics = {
        "l1_ledger": l1_ledger,
        "l2_batch": l2_batch,
        "branch_sets": branch_sets,
        "candidate_ref": candidate_ref,
        "first_candidates": first_candidates,
        "duplicate_candidates": duplicate_candidates,
        "second_candidates": second_candidates,
        "after_first": after_first,
        "after_duplicate": after_duplicate,
        "after_second": after_second,
        "evidence_after_first": evidence_after_first,
        "evidence_after_duplicate": evidence_after_duplicate,
        "first_episode_exposures": first_episode_exposures,
        "pending_projection_rejected": pending_projection_rejected,
        "projection": projection,
        "memory_artifact": memory_artifact,
        "answer": answer,
    }
    return arena, knowledge, diagnostics


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)

    arena, knowledge, diag = train_informed(ROOT, project_root=ROOT)
    branch_sets = diag["branch_sets"]
    candidate_ref = diag["candidate_ref"]
    projection = diag["projection"]
    memory_artifact = diag["memory_artifact"]
    informed_answer = diag["answer"]

    control_arena, control_l1, control_l2, control_branches = build_L3(
        ROOT,
        project_root=ROOT,
        session_id="sys-03-control",
        source=CONTROL_SOURCE,
        rows=CONTROL,
    )
    control_knowledge = KnowledgeAdmissionEngine(control_arena)
    control_candidates = control_knowledge.observe(control_branches[0])
    control_answer = AutobiographicalResponder(control_knowledge.core).answer_relation(
        question()
    )

    relation = knowledge.core.universe.relations[
        projection.relation_occurrence_ref
    ]
    memory_payload = thaw_json(memory_artifact.payload_native)
    distributed = knowledge.core.forms.get(memory_payload["distributed_form_ref"])
    memory_item = knowledge.core.memory.get(relation.relation_occurrence_id)
    episode_artifacts = arena.query(artifact_type="episode-memory")
    episode_items = [
        knowledge.core.memory.get(
            thaw_json(row.payload_native)["memory_item"]["content_ref"]
        )
        for row in episode_artifacts
    ]
    decoded_subject = knowledge.core.forms.unbind_role(
        distributed,
        "subject",
        (
            "concept-form:external:mrs:_apple_n_1",
            "concept-form:external:mrs:_fruit_n_1",
            "concept-form:external:mrs:_notebook_n_1",
        ),
    )
    decoded_class = knowledge.core.forms.unbind_role(
        distributed,
        "class",
        (
            "concept-form:external:mrs:_apple_n_1",
            "concept-form:external:mrs:_fruit_n_1",
            "concept-form:external:mrs:_notebook_n_1",
        ),
    )

    response_support_ancestry = set()
    for support_ref in relation.support_refs:
        if support_ref.startswith("ca:"):
            response_support_ancestry.update(
                row.artifact_id for row in arena.ancestry(support_ref)
            )
    response_levels = {
        arena.get(ref).artifact_type for ref in response_support_ancestry
    }

    with tempfile.TemporaryDirectory(prefix="seman2-sys03-replay-") as temp_name:
        replay_root = Path(temp_name)
        for relative in (LESSON_SOURCE,):
            destination = replay_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        replay_arena, replay_knowledge, replay_diag = train_informed(
            replay_root, project_root=ROOT
        )
        replay_equal = stable_arena(arena) == stable_arena(replay_arena)
        replay_model_equal = (
            knowledge.core.as_dict() == replay_knowledge.core.as_dict()
        )
        replay_answer_equal = informed_answer == replay_diag["answer"]

    restored_arena = ArtifactArena.restore(build_knowledge_registry(), arena.as_dict())
    restored_core = DevelopmentalCore.restore(knowledge.core.as_dict())
    restored_answer = AutobiographicalResponder(restored_core).answer_relation(
        question()
    )

    first_parse_count = len(
        [
            row
            for row in arena.query(artifact_type="analysis-contribution")
            if row.observation_refs == ("experience:sys-03:lesson-1",)
            and row.status is ArtifactStatus.SUCCESS
        ]
    )
    after_first = diag["after_first"]
    after_duplicate = diag["after_duplicate"]
    after_second = diag["after_second"]
    checks = {
        "closed_SYS02_batches_are_consumed": (
            diag["l1_ledger"].closed
            and diag["l2_batch"].closed
            and len(branch_sets) == 2
            and all(row.artifact_type == "situation-branch-set" for row in branch_sets)
        ),
        "multiple_parses_count_as_one_experience": (
            first_parse_count >= 2
            and after_first.status is AdmissionStatus.PENDING
            and after_first.independent_support_experiences
            == ("experience:sys-03:lesson-1",)
            and after_first.support_weight == 1.0
        ),
        "duplicate_delivery_is_idempotent": (
            diag["duplicate_candidates"] == diag["first_candidates"]
            and after_duplicate == after_first
            and diag["evidence_after_duplicate"] == diag["evidence_after_first"]
            and diag["first_episode_exposures"] == 1
        ),
        "pending_candidate_cannot_enter_semantic_memory": diag[
            "pending_projection_rejected"
        ],
        "two_independent_experiences_consolidate": (
            diag["second_candidates"] == (candidate_ref,)
            and after_second.status is AdmissionStatus.CONSOLIDATED
            and after_second.independent_support_experiences
            == ("experience:sys-03:lesson-1", "experience:sys-03:lesson-2")
        ),
        "episodic_L4_exists_for_each_real_L3": (
            len(episode_artifacts) == 2
            and {row.parent_ids[0] for row in episode_artifacts}
            == {row.artifact_id for row in branch_sets}
            and all(item.kind == "linguistic-episode" for item in episode_items)
            and all(knowledge.core.memory.accessible(item.content_ref) for item in episode_items)
        ),
        "semantic_L4_consumes_both_real_L3_sets": set(memory_artifact.parent_ids)
        == {row.artifact_id for row in branch_sets},
        "relation_form_and_memory_are_synchronized": (
            memory_item.content_ref == relation.relation_occurrence_id
            and memory_payload["distributed_form_ref"] == distributed.form_id
            and set(memory_payload["distributed_factor_refs"])
            == {row.factor_ref for row in distributed.factors}
            and set(memory_item.support_refs) == set(relation.support_refs)
        ),
        "distributed_form_decodes_its_roles": (
            decoded_subject[0][0] == "concept-form:external:mrs:_apple_n_1"
            and decoded_class[0][0] == "concept-form:external:mrs:_fruit_n_1"
        ),
        "informed_model_answers_only_from_accessible_memory": (
            informed_answer.status is AnswerStatus.SUPPORTED
            and informed_answer.value_refs
            == ("concept-form:external:mrs:_fruit_n_1",)
            and informed_answer.evidence_refs == (relation.relation_occurrence_id,)
            and knowledge.core.memory.accessible(relation.relation_occurrence_id)
            and informed_answer.external_source_consulted is False
        ),
        "response_support_reaches_real_L0_through_L3": {
            "experience-occurrence",
            "observation",
            "analysis-contribution",
            "composed-candidate",
            "situation-branch-set",
        }
        <= response_levels,
        "unexposed_control_biography_answers_unknown": (
            not control_candidates
            and control_answer.status is AnswerStatus.UNKNOWN
            and control_answer.value_refs == ()
            and control_answer.external_source_consulted is False
            and control_l1.closed
            and control_l2.closed
        ),
        "L4_resource_cost_and_context_are_explicit": all(
            row.context_refs == ("ctx:model",)
            and isinstance(thaw_json(row.resource_cost).get("wall_time_ms"), (int, float))
            for row in (*episode_artifacts, memory_artifact)
        ),
        "location_independent_full_replay_is_identical": (
            replay_equal and replay_model_equal and replay_answer_equal
        ),
        "arena_and_cognitive_core_restore_exactly": (
            stable_arena(restored_arena) == stable_arena(arena)
            and restored_core.as_dict() == knowledge.core.as_dict()
            and restored_answer == informed_answer
        ),
    }

    effects = []
    for row in arena.query():
        if row.artifact_type in {"experience-occurrence", "observation"}:
            continue
        for parent_id in row.parent_ids:
            effects.append(
                {
                    "consumer_artifact_ref": row.artifact_id,
                    "input_factor_ref": parent_id,
                    "producer_artifact_ref": row.artifact_id,
                    "operation": {
                        "analysis-contribution": "ACE/ERG analysis",
                        "composed-candidate": "generic MRS composition",
                        "situation-branch-set": "hypothesis grouping",
                        "episode-memory": "episodic admission",
                        "memory-admission": "semantic consolidation and synchronized projection",
                    }[row.artifact_type],
                    "effect_on_output": f"{row.artifact_type}:{row.status.value}",
                    "activation_or_weight_change": (
                        "memory content added"
                        if row.artifact_type in {"episode-memory", "memory-admission"}
                        else "one candidate contribution added"
                    ),
                    "context_ref": list(row.context_refs),
                    "reason_if_ignored": None,
                }
            )
    lineage = lineage_manifest(
        arena,
        real_source_refs=[LESSON_SOURCE.as_posix()],
        causal_effects=effects,
    )
    lineage_ids = {row["artifact_id"] for row in lineage["artifacts"]}
    memory_ancestry = {
        row.artifact_id for row in arena.ancestry(memory_artifact.artifact_id)
    }
    checks["lineage_contains_complete_L0_to_L4_ancestry"] = (
        memory_ancestry <= lineage_ids
        and {
            "experience-occurrence",
            "observation",
            "analysis-contribution",
            "composed-candidate",
            "situation-branch-set",
            "memory-admission",
        }
        <= {arena.get(ref).artifact_type for ref in memory_ancestry}
    )

    all_passed = all(checks.values())
    results = {
        "verdict": "GO" if all_passed else "NO-GO",
        "scope": "closed real L3 branches to episodic/semantic L4 and internal relational query",
        "checks": checks,
        "counts": {
            "experiences": 2,
            "L3_branch_sets": len(branch_sets),
            "L4_episode_memories": len(episode_artifacts),
            "L4_semantic_admissions": 1,
            "independent_support_experiences": len(
                after_second.independent_support_experiences
            ),
            "distributed_factors": len(distributed.factors),
            "response_support_artifacts": len(response_support_ancestry),
        },
        "informed_answer": {
            "status": informed_answer.status.value,
            "value_refs": list(informed_answer.value_refs),
            "evidence_refs": list(informed_answer.evidence_refs),
            "explanation_path": list(informed_answer.explanation_path),
            "support_artifact_refs": list(relation.support_refs),
        },
        "control_answer": {
            "status": control_answer.status.value,
            "value_refs": list(control_answer.value_refs),
            "evidence_refs": list(control_answer.evidence_refs),
            "explanation_path": list(control_answer.explanation_path),
        },
        "demonstrated": [
            "exclusive consumption of closed real SYS-02 L3 stock",
            "independent-experience consolidation without parse multiplication",
            "idempotent episode ingestion",
            "synchronized episodic, relational, distributed, and semantic memory",
            "role-decodable distributed form",
            "supported answer from accessible internal memory",
            "unknown answer in a genuinely unexposed control biography",
            "complete response support path through L3/L2/L1/L0",
            "location-independent replay and dual snapshot restoration",
        ],
        "not_demonstrated": [
            "general semantic composition beyond copular classification",
            "forgetting under long ingestion",
            "state transformations",
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
    write_json("control-ledger.json", control_arena.as_dict())
    write_json("control-model.json", control_knowledge.core.as_dict())
    write_json(
        "closed-batches.json",
        {
            "informed_L1": diag["l1_ledger"].as_dict(),
            "informed_L2": diag["l2_batch"].as_dict(),
            "control_L1": control_l1.as_dict(),
            "control_L2": control_l2.as_dict(),
        },
    )
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "pydelphin": importlib.metadata.version("pydelphin"),
            "registry_digest": arena.registry.digest,
            "minimum_independent_experiences": 2,
            "vector_dimension": knowledge.core.forms.dimension,
            "ace_sha256": sha256_file(ROOT / ".local/bin/ace"),
            "erg_sha256": sha256_file(
                ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
            ),
            "source_sha256": {
                LESSON_SOURCE.as_posix(): sha256_file(ROOT / LESSON_SOURCE),
                CONTROL_SOURCE.as_posix(): sha256_file(ROOT / CONTROL_SOURCE),
            },
        },
    )
    print(json.dumps(results, ensure_ascii=False))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
