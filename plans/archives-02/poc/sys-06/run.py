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
OUTPUT = ROOT / "poc/sys-06/output"
SOURCE = Path("data/curriculum/sys_06_identity_discourse.txt")
WORLD = "ctx:sys-06:world"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import ArtifactArena, thaw_json  # noqa: E402
from seman2_runtime.contracts import ContractError  # noqa: E402
from seman2_runtime.developmental_core import DevelopmentalCore  # noqa: E402
from seman2_runtime.discourse_identity_system import (  # noqa: E402
    ContextualIdentityEngine,
    ContextualMentionExtractor,
    build_discourse_identity_registry,
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
from seman2_runtime.temporal_system import (  # noqa: E402
    RelationalTemporalAnalyzer,
    TemporalReasoner,
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
    arena = ArtifactArena(build_discourse_identity_registry())
    gateway = ExperienceGateway(
        arena, session_id="sys-06", policy=policy, source_root=source_root
    )
    pairs = gateway.ingest_file(
        source_root / SOURCE, experience_prefix="sys-06", max_observations=6
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
    hypotheses = HypothesisManager(arena)
    situations = tuple(
        hypotheses.group(by_observation[row.artifact_id]) for row in observations
    )

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
    temporal_reasoner = TemporalReasoner(arena)
    temporal_memory = temporal_reasoner.remember(temporal_sets)

    extractor = ContextualMentionExtractor(arena, world_context_ref=WORLD)
    identity = ContextualIdentityEngine(arena, world_context_ref=WORLD)
    mention_artifacts = []
    beams = []
    for index, situation in enumerate(situations):
        local = tuple(
            extractor.extract(arena.get(branch["candidate_ref"]))
            for branch in thaw_json(situation.payload_native)["branches"]
        )
        mention_artifacts.extend(local)
        beams.append(
            identity.resolve_observation(
                situation, local, temporal_index=index
            )
        )
    discourse_memory = identity.finalize(
        episode_memories=episodes, temporal_memory=temporal_memory
    )
    return {
        "arena": arena,
        "policy": policy,
        "observations": observations,
        "l1": l1,
        "contributions": contributions,
        "l2": l2,
        "candidates": candidates,
        "situations": situations,
        "episodes": tuple(episodes),
        "temporal_sets": tuple(temporal_sets),
        "temporal_memory": temporal_memory,
        "extractor": extractor,
        "identity": identity,
        "mention_artifacts": tuple(mention_artifacts),
        "beams": tuple(beams),
        "discourse_memory": discourse_memory,
    }


def decision_with_alias(
    beam_payload: dict[str, object], alias: str
) -> tuple[dict[str, object], dict[str, object]]:
    normalized = alias.casefold().strip(" .,!?:;")
    mention_by_ref = {
        row["mention_ref"]: row for row in beam_payload["mentions"]
    }
    for decision in beam_payload["decisions"]:
        mention = mention_by_ref[decision["mention_ref"]]
        if any(
            value.casefold().strip(" .,!?:;") == normalized
            for value in mention["surface_aliases"]
        ):
            return mention, decision
    raise AssertionError(f"mention alias absent: {alias}")


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    run = execute(ROOT, project_root=ROOT)
    arena = run["arena"]
    memory = run["discourse_memory"]
    payload = thaw_json(memory.payload_native)
    beam_payloads = [thaw_json(row.payload_native) for row in run["beams"]]
    profiles = payload["identity_profiles"]
    maya = next(row for row in profiles if "Maya" in row["surface_aliases"])
    amira = next(row for row in profiles if "Amira" in row["surface_aliases"])
    notebook_profiles = [
        row for row in profiles if "_notebook_n_of" in row["surface_aliases"]
    ]
    red_notebook = next(
        row
        for row in notebook_profiles
        if "_red_a_1"
        in row["descriptor_evidence_by_context"].get(WORLD, [])
    )
    blue_notebook = next(
        row
        for row in notebook_profiles
        if "_blue_a_1"
        in row["descriptor_evidence_by_context"].get(WORLD, [])
    )
    she_mention, she_decision = decision_with_alias(beam_payloads[3], "She")
    it_mention, it_decision = decision_with_alias(beam_payloads[3], "it")
    _, blue_definite_decision = decision_with_alias(beam_payloads[4], "notebook")
    attributed_forms = {
        row["relation_form_ref"] for row in payload["attributed_propositions"]
    }
    world_forms = {row["relation_form_ref"] for row in payload["world_propositions"]}
    attributed_contexts = [
        row for row in payload["contexts"] if row["kind"] == "attributed"
    ]
    blue_facets = [
        row for row in payload["facets"] if row["identity_ref"] == blue_notebook["identity_ref"]
    ]

    with tempfile.TemporaryDirectory(prefix="seman2-sys06-replay-") as temp_name:
        replay_root = Path(temp_name)
        destination = replay_root / SOURCE
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / SOURCE, destination)
        replay = execute(replay_root, project_root=ROOT)
        replay_equal = stable_view(arena) == stable_view(replay["arena"])
        replay_core_equal = (
            run["identity"].core.as_dict() == replay["identity"].core.as_dict()
        )

    restored_arena = ArtifactArena.restore(
        build_discourse_identity_registry(), arena.as_dict()
    )
    restored_core = DevelopmentalCore.restore(run["identity"].core.as_dict())
    source_code = (
        ROOT / "seman2_runtime/discourse_identity_system.py"
    ).read_text(encoding="utf-8").lower()
    ancestry_types = {
        row.artifact_type for row in arena.ancestry(memory.artifact_id)
    }

    artifact_count_before_repeat = len(arena.query())
    first_mention = run["mention_artifacts"][0]
    repeated_mention = run["extractor"].extract(arena.get(first_mention.parent_ids[0]))
    repeated_beam = run["identity"].resolve_observation(
        run["situations"][0],
        tuple(
            row
            for row in run["mention_artifacts"]
            if row.observation_refs == run["situations"][0].observation_refs
        ),
        temporal_index=0,
    )
    repeated_memory = run["identity"].finalize(
        episode_memories=run["episodes"], temporal_memory=run["temporal_memory"]
    )
    artifact_count_after_repeat = len(arena.query())
    invalid_extract_rejected = rejects_contract(
        lambda: run["extractor"].extract(memory)
    )
    invalid_finalize_rejected = rejects_contract(
        lambda: run["identity"].finalize(
            episode_memories=(memory,), temporal_memory=run["temporal_memory"]
        )
    )

    she_existing = [
        row for row in she_decision["candidates"] if not row["creates_new_identity"]
    ]
    it_existing = [
        row for row in it_decision["candidates"] if not row["creates_new_identity"]
    ]
    checks = {
        "closed_real_L0_to_L3_stock_is_exclusive_input": (
            run["l1"].closed
            and run["l2"].closed
            and run["l1"].recompute_digest() == run["l1"].ledger_digest
            and run["l2"].recompute_digest() == run["l2"].batch_digest
            and len(run["observations"]) == 6
            and len(run["situations"]) == 6
        ),
        "real_SYS03_and_SYS05_memories_are_dependencies": (
            len(run["episodes"]) == 6
            and all(row.artifact_type == "episode-memory" for row in run["episodes"])
            and run["temporal_memory"].artifact_type == "temporal-memory"
            and set(payload["dependency_refs"]["episode_memory_refs"])
            == {row.artifact_id for row in run["episodes"]}
            and payload["dependency_refs"]["temporal_memory_ref"]
            == run["temporal_memory"].artifact_id
        ),
        "every_mention_candidate_consumes_exact_real_L2": all(
            len(row.parent_ids) == 1
            and arena.get(row.parent_ids[0]).artifact_type == "composed-candidate"
            and thaw_json(row.payload_native)["source_candidate_ref"] == row.parent_ids[0]
            for row in run["mention_artifacts"]
        ),
        "identity_beams_cover_all_real_parse_alternatives": all(
            len(thaw_json(row.payload_native)["source_branch_set_ref"]) > 0
            and {
                arena.get(parent).parent_ids[0]
                for parent in row.parent_ids[1:]
            }
            == {
                branch["candidate_ref"]
                for branch in thaw_json(arena.get(row.parent_ids[0]).payload_native)["branches"]
            }
            for row in run["beams"]
        ),
        "parse_alternatives_do_not_multiply_mentions": (
            any(
                mention["alternative_count"] > 1
                for beam in beam_payloads
                for mention in beam["mentions"]
            )
            and len(maya["mention_refs"]) == 3
            and len(amira["mention_refs"]) == 3
        ),
        "repeated_names_reuse_stable_identities": (
            maya["identity_ref"] != amira["identity_ref"]
            and len(maya["mention_refs"]) == 3
            and len(amira["mention_refs"]) == 3
            and all(
                decision["selected_identity_ref"] in {maya["identity_ref"], amira["identity_ref"]}
                for beam in beam_payloads
                for decision in beam["decisions"]
                if decision["reference_kind"] == "proper"
            )
        ),
        "indefinite_notebooks_remain_distinct": (
            len(notebook_profiles) == 2
            and red_notebook["identity_ref"] != blue_notebook["identity_ref"]
            and any(
                decision["status"] == "indefinite-introduction"
                for beam in beam_payloads
                for decision in beam["decisions"]
            )
        ),
        "supported_definite_continuity_influences_later_identity": (
            blue_definite_decision["selected_identity_ref"]
            == blue_notebook["identity_ref"]
            and blue_definite_decision["status"] == "decisive-candidate"
        ),
        "pronoun_ambiguity_survives_without_commitment": (
            she_decision["status"] == "ambiguous"
            and it_decision["status"] == "ambiguous"
            and she_decision["selected_identity_ref"] is None
            and it_decision["selected_identity_ref"] is None
            and len(she_existing) >= 2
            and len(it_existing) >= 2
        ),
        "continuity_ranks_but_does_not_collapse_pronouns": (
            len({row["rank_score"] for row in she_existing}) > 1
            and len({row["rank_score"] for row in it_existing}) > 1
            and she_decision["candidates"][0]["identity_ref"] == amira["identity_ref"]
            and it_decision["candidates"][0]["identity_ref"] == blue_notebook["identity_ref"]
        ),
        "reported_contexts_are_attributed_to_real_speakers": (
            len(attributed_contexts) == 2
            and {row["attribution_ref"] for row in attributed_contexts}
            == {maya["identity_ref"], amira["identity_ref"]}
            and all(row["parent_context_ref"] == WORLD for row in attributed_contexts)
        ),
        "reported_beliefs_do_not_leak_into_world": (
            {"external:mrs:_old_a_1", "external:mrs:_valuable_a_to-for"}
            <= attributed_forms
            and not (
                {"external:mrs:_old_a_1", "external:mrs:_valuable_a_to-for"}
                & world_forms
            )
            and all(
                not any(
                    descriptor in values
                    for descriptor in ("_old_a_1", "_valuable_a_to-for")
                )
                for profile in profiles
                for context_ref, values in profile[
                    "descriptor_evidence_by_context"
                ].items()
                if context_ref == WORLD
            )
        ),
        "one_identity_keeps_world_and_attributed_facets": (
            {row["context_ref"] for row in blue_facets}
            >= {WORLD, attributed_contexts[0]["context_ref"]}
            or {row["context_ref"] for row in blue_facets}
            >= {WORLD, attributed_contexts[1]["context_ref"]}
        ),
        "production_engine_contains_no_curriculum_entities": all(
            token not in source_code
            for token in (
                "maya",
                "amira",
                "notebook",
                "school",
                "valuable",
                "old_a_1",
                "say_v",
                "believe_v",
            )
        ),
        "no_identity_or_truth_is_committed_for_ambiguous_content": (
            memory.status.value == "partial"
            and thaw_json(memory.payload_projection)["truth_committed"] is False
            and thaw_json(memory.payload_projection)["world_update_performed"] is False
            and all(row["selected_identity_ref"] is None for row in payload["ambiguous_mentions"])
        ),
        "discourse_services_are_idempotent": (
            repeated_mention.artifact_id == first_mention.artifact_id
            and repeated_beam.artifact_id == run["beams"][0].artifact_id
            and repeated_memory.artifact_id == memory.artifact_id
            and artifact_count_before_repeat == artifact_count_after_repeat
        ),
        "invalid_cross_layer_inputs_are_rejected": (
            invalid_extract_rejected and invalid_finalize_rejected
        ),
        "discourse_memory_ancestry_reaches_every_real_layer": {
            "experience-occurrence",
            "observation",
            "analysis-contribution",
            "composed-candidate",
            "situation-branch-set",
            "episode-memory",
            "temporal-analysis",
            "temporal-branch-set",
            "temporal-memory",
            "identity-mention-candidate",
            "identity-beam",
            "discourse-memory",
        } <= ancestry_types,
        "location_independent_full_replay_is_identical": (
            replay_equal and replay_core_equal
        ),
        "arena_and_cognitive_core_restore_exactly": (
            stable_view(restored_arena) == stable_view(arena)
            and restored_core.as_dict() == run["identity"].core.as_dict()
        ),
    }

    operation_by_type = {
        "identity-mention-candidate": "contextual mention extraction",
        "identity-beam": "identity beam resolution",
        "discourse-memory": "context-separated discourse memory",
    }
    effects = [
        {
            "consumer_artifact_ref": row.artifact_id,
            "input_factor_ref": parent,
            "producer_artifact_ref": row.artifact_id,
            "operation": operation_by_type[row.artifact_type],
            "effect_on_output": f"{row.artifact_type}:{row.status.value}",
            "activation_or_weight_change": "contextual identity material added",
            "context_ref": list(row.context_refs),
            "reason_if_ignored": None,
        }
        for row in arena.query()
        if row.artifact_type in operation_by_type
        for parent in row.parent_ids
    ]
    lineage = lineage_manifest(
        arena, real_source_refs=[SOURCE.as_posix()], causal_effects=effects
    )
    all_passed = all(checks.values())
    results = {
        "verdict": "GO" if all_passed else "NO-GO",
        "scope": "real L1/L2/L3 plus episodic and temporal L4 to contextual identity and discourse memory",
        "checks": checks,
        "counts": {
            "source_experiences": len(run["observations"]),
            "L2_candidates": len(run["candidates"]),
            "mention_artifacts": len(run["mention_artifacts"]),
            "identity_beams": len(run["beams"]),
            "identity_profiles": len(profiles),
            "facets": len(payload["facets"]),
            "attributed_contexts": len(attributed_contexts),
            "ambiguous_mentions": len(payload["ambiguous_mentions"]),
        },
        "demonstrated": [
            "parse-deduplicated mention extraction from real composed candidates",
            "stable named identity continuity and distinct indefinite objects",
            "graded continuity influence without pronoun overcommitment",
            "speaker-attributed contexts and non-leaking reported propositions",
            "real episodic and temporal L4 dependencies",
            "deterministic replay, idempotence, and exact restoration",
        ],
        "not_demonstrated": [
            "global cross-document identity",
            "dialogue acts",
            "natural-language response",
        ],
    }
    write_json("results.json", results)
    write_json("summary.json", {"verdict": results["verdict"], "checks_passed": sum(checks.values()), "checks_total": len(checks), **results["counts"]})
    write_json("ledger.json", arena.as_dict())
    write_json("lineage.json", lineage)
    write_json("discourse-memory.json", payload)
    write_json("model.json", run["identity"].core.as_dict())
    write_json("closed-batches.json", {"L1": run["l1"].as_dict(), "L2": run["l2"].as_dict()})
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "pydelphin": importlib.metadata.version("pydelphin"),
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
