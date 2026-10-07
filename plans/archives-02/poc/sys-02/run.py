#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import replace
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile

from delphin.codecs import simplemrs


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "poc/sys-02/output"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import (  # noqa: E402
    ArtifactArena,
    ArtifactStatus,
    thaw_json,
)
from seman2_runtime.contracts import ContractError  # noqa: E402
from seman2_runtime.formal_composition import GenericMRSComposer  # noqa: E402
from seman2_runtime.hypothesis_system import (  # noqa: E402
    HypothesisManager,
    build_situation_registry,
)
from seman2_runtime.low_level_system import (  # noqa: E402
    AceErgAnalyzer,
    AnalysisOrchestrator,
    ExperienceGateway,
    LowLevelPolicy,
    lineage_manifest,
    sha256_file,
)


INPUTS = (
    (
        "ambiguous",
        "Maya drew the old lot beside the apartment building, where weeds pushed through the fence.",
        Path("data/the_map_of_everything_nlp_novel.txt"),
    ),
    (
        "open-vocabulary",
        "Maya glorped the map.",
        Path("data/curriculum/sys_01_open_vocabulary.txt"),
    ),
    (
        "negation",
        "Maple Street was not famous.",
        Path("data/the_map_of_everything_nlp_novel.txt"),
    ),
    (
        "state",
        "The pictures were easy.",
        Path("data/the_map_of_everything_nlp_novel.txt"),
    ),
    (
        "scope",
        "Everyone was allowed to draw one place that mattered, but no one could write a name yet.",
        Path("data/the_map_of_everything_nlp_novel.txt"),
    ),
    (
        "known-copula",
        "A robin is a bird.",
        Path("data/curriculum/sys_02_held_out.txt"),
    ),
    (
        "held-out-copula",
        "A wug is a dax.",
        Path("data/curriculum/sys_02_held_out.txt"),
    ),
    (
        "no-parse",
        "the the the.",
        Path("data/curriculum/sys_01_open_vocabulary.txt"),
    ),
)


def write_json(name: str, value: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


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


def topology(payload: dict[str, object]) -> tuple[object, ...]:
    relations = payload["relations"]
    return (
        tuple(
            sorted(
                tuple(binding["role_ref"] for binding in relation["bindings"])
                for relation in relations
                if relation["predicate"] == "_be_v_id"
            )
        ),
        tuple(
            sorted(
                tuple(binding["role_ref"] for binding in relation["bindings"])
                for relation in relations
                if relation["part_of_speech"] == "q"
            )
        ),
        len(payload["referents"]),
        len(payload["events"]),
        len(payload["scope_constraints"]),
    )


def rejects_contract(operation: object) -> bool:
    try:
        operation()
    except ContractError:
        return True
    return False


def exact_native_fidelity(arena: ArtifactArena, candidate: object) -> bool:
    """Compare independently the L2 projection with its decoded native MRS."""
    contribution = arena.get(candidate.parent_ids[0])
    native = thaw_json(contribution.payload_native)
    mrs_text = native.get("native_result", {}).get("mrs")
    if not mrs_text:
        return False
    mrs = simplemrs.decode(mrs_text)
    payload = thaw_json(candidate.payload_native)
    relations = payload["relations"]
    if len(relations) != len(mrs.rels):
        return False
    for relation, ep in zip(relations, mrs.rels, strict=True):
        expected_span = list(ep.lnk.data) if ep.lnk is not None and ep.lnk.data else None
        actual_bindings = {
            binding["role_ref"]: binding["source_value"]
            for binding in relation["bindings"]
        }
        if (
            relation["predicate"] != ep.predicate
            or relation["label"] != ep.label
            or relation["constant"] != ep.carg
            or actual_bindings != dict(ep.args)
            or relation["span"] != expected_span
        ):
            return False
    projected_variables = {
        row["mrs_variable"]: row["properties"]
        for row in payload["referents"] + payload["events"]
    }
    expected_variables = {
        variable: dict(properties)
        for variable, properties in mrs.variables.items()
        if variable[0] in {"x", "i", "e"}
    }
    if projected_variables != expected_variables:
        return False
    if payload["scope_constraints"] != [
        {"high": row.hi, "relation": str(row.relation), "low": row.lo}
        for row in mrs.hcons
    ]:
        return False
    return payload["individual_constraints"] == [
        {"left": row.left, "relation": str(row.relation), "right": row.right}
        for row in mrs.icons
    ]


def build_pipeline(
    source_root: Path,
    *,
    project_root: Path,
) -> tuple[
    ArtifactArena,
    object,
    tuple[object, ...],
    object,
    tuple[object, ...],
    tuple[object, ...],
]:
    policy = LowLevelPolicy(
        max_sentence_chars=300,
        max_candidates=3,
        worker_timeout_seconds=30.0,
        worker_memory_mib=1_024,
        max_observations_per_wave=12,
    )
    registry = build_situation_registry()
    arena = ArtifactArena(registry)
    gateway = ExperienceGateway(
        arena,
        session_id="sys-02",
        policy=policy,
        source_root=source_root,
    )
    observations = []
    for sequence, (key, surface, relative_source) in enumerate(INPUTS):
        _, observation = gateway.ingest_sentence_from_file(
            source_root / relative_source,
            surface,
            experience_ref=f"experience:sys-02:{key}",
            sequence_index=sequence,
        )
        observations.append(observation)

    analyzer = AceErgAnalyzer(arena, project_root=project_root, policy=policy)
    l1_ledger, contributions = AnalysisOrchestrator(policy=policy).execute(
        observations, analyzer
    )
    composer = GenericMRSComposer(arena)
    l2_batch, candidates = composer.compose_ledger(l1_ledger)

    candidates_by_observation: dict[str, list[object]] = {
        row.artifact_id: [] for row in observations
    }
    for candidate in candidates:
        contribution = arena.get(candidate.parent_ids[0])
        candidates_by_observation[contribution.parent_ids[0]].append(candidate)
    manager = HypothesisManager(arena, maximum_branches=8)
    branch_sets = tuple(
        manager.group(candidates_by_observation[observation.artifact_id])
        for observation in observations
    )
    return (
        arena,
        l1_ledger,
        contributions,
        l2_batch,
        candidates,
        branch_sets,
    )


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)

    arena, l1_ledger, contributions, l2_batch, candidates, branch_sets = (
        build_pipeline(ROOT, project_root=ROOT)
    )
    observations = arena.query(artifact_type="observation")
    payloads = {
        row.artifact_id: thaw_json(row.payload_native) for row in candidates
    }
    by_key: dict[str, list[object]] = {row[0]: [] for row in INPUTS}
    branch_by_key: dict[str, object] = {}
    observation_by_ref = {
        row.observation_refs[0]: row.artifact_id for row in observations
    }
    for candidate in candidates:
        contribution = arena.get(candidate.parent_ids[0])
        experience_ref = contribution.observation_refs[0]
        key = experience_ref.removeprefix("experience:sys-02:")
        by_key[key].append(candidate)
    for branch_set in branch_sets:
        experience_ref = branch_set.observation_refs[0]
        key = experience_ref.removeprefix("experience:sys-02:")
        branch_by_key[key] = branch_set

    successful_candidates = tuple(
        row for row in candidates if row.status is ArtifactStatus.SUCCESS
    )
    failed_candidates = tuple(
        row for row in candidates if row.status is ArtifactStatus.FAILURE
    )
    successful_payloads = [payloads[row.artifact_id] for row in successful_candidates]

    def key_payloads(key: str) -> list[dict[str, object]]:
        return [payloads[row.artifact_id] for row in by_key[key]]

    def predicates(payload: dict[str, object]) -> set[str]:
        return {relation["predicate"] for relation in payload["relations"]}

    known_payloads = key_payloads("known-copula")
    held_out_payloads = key_payloads("held-out-copula")
    scope_payloads = key_payloads("scope")
    negation_payloads = key_payloads("negation")
    state_payloads = key_payloads("state")
    ambiguous_candidates = by_key["ambiguous"]
    no_parse_l2 = by_key["no-parse"]
    no_parse_l3 = branch_by_key["no-parse"]

    # Replay de la verticale complète depuis une racine de sources différente.
    with tempfile.TemporaryDirectory(prefix="seman2-sys02-replay-") as temp_name:
        replay_root = Path(temp_name)
        for relative in sorted({row[2] for row in INPUTS}, key=str):
            destination = replay_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        replay_arena, replay_l1, _, replay_l2, _, _ = build_pipeline(
            replay_root, project_root=ROOT
        )
        replay_equal = stable_view(arena) == stable_view(replay_arena)
        replay_batches_equal = (
            l1_ledger.ledger_digest == replay_l1.ledger_digest
            and l2_batch.batch_digest == replay_l2.batch_digest
        )

    restored = ArtifactArena.restore(build_situation_registry(), arena.as_dict())
    composer_source = (ROOT / "seman2_runtime/formal_composition.py").read_text(
        encoding="utf-8"
    )
    hypothesis_source = (ROOT / "seman2_runtime/hypothesis_system.py").read_text(
        encoding="utf-8"
    )
    l1_ids = {row.artifact_id for row in contributions}
    l2_parent_ids = {row.parent_ids[0] for row in candidates}

    bad_digest_ledger = replace(l1_ledger, ledger_digest="0" * 64)
    swapped_observations = (
        l1_ledger.observation_ids[1],
        l1_ledger.observation_ids[0],
        *l1_ledger.observation_ids[2:],
    )
    swapped_routes = [dict(row) for row in l1_ledger.route_decisions]
    swapped_routes[0]["observation_ref"] = swapped_observations[0]
    swapped_routes[1]["observation_ref"] = swapped_observations[1]
    misbound_ledger = replace(
        l1_ledger,
        observation_ids=swapped_observations,
        route_decisions=tuple(swapped_routes),
        ledger_digest="pending",
    )
    misbound_ledger = replace(
        misbound_ledger, ledger_digest=misbound_ledger.recompute_digest()
    )
    bad_digest_batch = replace(l2_batch, batch_digest="0" * 64)
    negative_manager = HypothesisManager(arena, maximum_branches=1)

    checks = {
        "closed_SYS01_ledger_is_actual_input": (
            l1_ledger.closed
            and l1_ledger.recompute_digest() == l1_ledger.ledger_digest
            and tuple(l1_ledger.contribution_ids)
            == tuple(row.artifact_id for row in contributions)
            and l1_ids == l2_parent_ids
        ),
        "closed_L2_batch_accounts_for_every_L1": (
            l2_batch.closed
            and l2_batch.recompute_digest() == l2_batch.batch_digest
            and tuple(l2_batch.candidate_ids)
            == tuple(row.artifact_id for row in candidates)
            and len(candidates) == len(contributions)
        ),
        "tampered_or_misbound_ledgers_are_rejected": (
            rejects_contract(
                lambda: GenericMRSComposer(arena).compose_ledger(bad_digest_ledger)
            )
            and rejects_contract(
                lambda: GenericMRSComposer(arena).compose_ledger(misbound_ledger)
            )
            and rejects_contract(bad_digest_batch.validate_integrity)
        ),
        "every_L2_consumes_exact_real_L1": all(
            len(row.parent_ids) == 1
            and arena.get(row.parent_ids[0]).artifact_type == "analysis-contribution"
            and payloads[row.artifact_id]["source_analysis_ref"] == row.parent_ids[0]
            for row in candidates
        ),
        "native_failure_becomes_explicit_failed_L2": (
            len(no_parse_l2) == 1
            and no_parse_l2[0].status is ArtifactStatus.FAILURE
            and no_parse_l2[0].artifact_id in l2_batch.rejected_candidate_ids
        ),
        "failed_L2_becomes_zero_branch_L3_with_reason": (
            no_parse_l3.status is ArtifactStatus.FAILURE
            and thaw_json(no_parse_l3.payload_native)["branches"] == []
            and thaw_json(no_parse_l3.payload_native)["rejected_candidate_refs"]
            == [no_parse_l2[0].artifact_id]
            and bool(
                thaw_json(no_parse_l3.payload_native)["grouping_trace"][0][
                    "reason_if_rejected"
                ]
            )
        ),
        "successful_L2_preserves_all_native_EPs": all(
            len(payload["relations"]) == len(payload["composition_trace"])
            and all(trace["native_ep_index"] == index for index, trace in enumerate(payload["composition_trace"]))
            for payload in successful_payloads
        ),
        "independent_oracle_confirms_exact_MRS_fidelity": all(
            exact_native_fidelity(arena, row) for row in successful_candidates
        ),
        "L1_lineage_metadata_is_preserved_exactly": all(
            row.observation_refs == arena.get(row.parent_ids[0]).observation_refs
            and row.source_anchors == arena.get(row.parent_ids[0]).source_anchors
            for row in candidates
        ),
        "native_relation_spans_are_valid_and_grounded": all(
            relation["span_valid"]
            and relation["surface_excerpt"] is not None
            for payload in successful_payloads
            for relation in payload["relations"]
        ),
        "identities_and_facets_are_explicit_candidates": all(
            len(payload["identity_candidates"]) == len(payload["referents"])
            and payload["facet_candidates"]
            and all(
                identity["status"] == "context-local-unresolved"
                for identity in payload["identity_candidates"]
            )
            for payload in successful_payloads
        ),
        "events_relations_and_nary_bindings_are_preserved": (
            all(payload["events"] and payload["relations"] for payload in successful_payloads)
            and any(
                len(relation["bindings"]) >= 3
                for payload in successful_payloads
                for relation in payload["relations"]
            )
        ),
        "parse_alternatives_keep_distinct_contexts": (
            len(ambiguous_candidates) >= 2
            and len(
                {
                    payloads[row.artifact_id]["context"]["context_ref"]
                    for row in ambiguous_candidates
                }
            )
            == len(ambiguous_candidates)
        ),
        "open_vocabulary_predication_survives_composition": all(
            "_glorped/vbd_u_unknown" in predicates(payload)
            and payload["events"]
            and any(
                relation["predicate"] == "_glorped/vbd_u_unknown"
                and {binding["role_ref"] for binding in relation["bindings"]}
                >= {"ARG0", "ARG1", "ARG2"}
                for relation in payload["relations"]
            )
            for payload in key_payloads("open-vocabulary")
        ),
        "negation_is_native_and_uncommitted": all(
            "neg" in predicates(payload)
            and payload["proposition"]["scope_operator_relation_refs"]
            and payload["proposition"]["asserted"] is False
            for payload in negation_payloads
        ),
        "adjectival_state_is_grounded_in_native_relation": all(
            payload["state_candidates"]
            and all(
                state["relation_ref"]
                in {relation["relation_ref"] for relation in payload["relations"]}
                for state in payload["state_candidates"]
            )
            for payload in state_payloads
        ),
        "quantifier_scope_remains_formally_underspecified": all(
            len(payload["proposition"]["quantifier_relation_refs"]) >= 2
            and payload["scope_constraints"]
            and payload["proposition"]["scope_status"] == "underspecified"
            and payload["proposition"]["scope_alternatives_committed"] == 0
            for payload in scope_payloads
        ),
        "individual_constraints_are_not_dropped": all(
            payload["individual_constraints"] for payload in scope_payloads
        ),
        "held_out_copula_has_same_formal_topology": (
            all(
                any(topology(known) == topology(held_out) for known in known_payloads)
                for held_out in held_out_payloads
            )
            and all("_be_v_id" in predicates(payload) for payload in known_payloads)
            and all("_be_v_id" in predicates(payload) for payload in held_out_payloads)
        ),
        "domain_lexemes_are_absent_from_composer": all(
            lexeme not in (composer_source + hypothesis_source).lower()
            for lexeme in ("robin", "bird", "wug", "dax", "maya", "maple")
        ),
        "every_L3_accounts_for_its_exact_L2_set": all(
            row.parent_ids
            and thaw_json(row.payload_native)["candidate_refs"] == list(row.parent_ids)
            and all(
                arena.get(parent).artifact_type == "composed-candidate"
                for parent in row.parent_ids
            )
            for row in branch_sets
        ),
        "one_L3_set_per_real_observation": (
            len(branch_sets) == len(observations)
            and {
                thaw_json(row.payload_native)["observation_ref"] for row in branch_sets
            }
            == set(observation_by_ref.values())
        ),
        "L3_branches_are_lossless_views_of_their_L2_candidates": all(
            all(
                branch["candidate_ref"] in row.parent_ids
                and branch["context_ref"]
                == payloads[branch["candidate_ref"]]["context"]["context_ref"]
                and branch["factor_counts"]
                == {
                    "referents": len(payloads[branch["candidate_ref"]]["referents"]),
                    "events": len(payloads[branch["candidate_ref"]]["events"]),
                    "relations": len(payloads[branch["candidate_ref"]]["relations"]),
                    "state_candidates": len(
                        payloads[branch["candidate_ref"]]["state_candidates"]
                    ),
                }
                for branch in thaw_json(row.payload_native)["branches"]
            )
            for row in branch_sets
        ),
        "cross_observation_and_over_budget_grouping_are_rejected": (
            rejects_contract(
                lambda: HypothesisManager(arena).group(
                    (by_key["state"][0], by_key["negation"][0])
                )
            )
            and rejects_contract(
                lambda: negative_manager.group(tuple(ambiguous_candidates[:2]))
            )
        ),
        "no_branch_truth_or_world_is_selected": all(
            thaw_json(row.payload_native)["selected_ref"] is None
            and not thaw_json(row.payload_projection)["truth_committed"]
            and not thaw_json(row.payload_projection)["world_update_performed"]
            and all(not branch["selected"] for branch in thaw_json(row.payload_native)["branches"])
            for row in branch_sets
        ),
        "L2_and_L3_resources_are_measured": all(
            isinstance(thaw_json(row.resource_cost).get("wall_time_ms"), (int, float))
            for row in successful_candidates + branch_sets
        ),
        "location_independent_full_replay_is_identical": replay_equal
        and replay_batches_equal,
        "checkpoint_restore_is_exact": stable_view(restored) == stable_view(arena),
    }

    effects = [
        {
            "consumer_artifact_ref": f"closed-ledger:{l1_ledger.ledger_digest}",
            "input_factor_ref": row.parent_ids[0],
            "producer_artifact_ref": row.artifact_id,
            "operation": "ACE/ERG parse under SYS-01 orchestrator",
            "effect_on_output": (
                "native L1 candidate appended"
                if row.status is ArtifactStatus.SUCCESS
                else "explicit native L1 failure appended"
            ),
            "activation_or_weight_change": "one closed-ledger contribution added",
            "context_ref": None,
            "reason_if_ignored": None,
        }
        for row in contributions
    ]
    for row in candidates:
        payload = payloads[row.artifact_id]
        effects.append(
            {
                "consumer_artifact_ref": row.artifact_id,
                "input_factor_ref": row.parent_ids[0],
                "producer_artifact_ref": row.artifact_id,
                "operation": "generic native-MRS composition",
                "effect_on_output": {
                    "status": row.status.value,
                    "referents": len(payload["referents"]),
                    "events": len(payload["events"]),
                    "relations": len(payload["relations"]),
                    "identities": len(payload["identity_candidates"]),
                    "facets": len(payload["facet_candidates"]),
                },
                "activation_or_weight_change": "one L2 candidate recorded",
                "context_ref": payload.get("context", {}).get("context_ref"),
                "reason_if_ignored": payload.get("failure_reason"),
            }
        )
    for row in branch_sets:
        payload = thaw_json(row.payload_native)
        for parent_id in row.parent_ids:
            effects.append(
                {
                    "consumer_artifact_ref": row.artifact_id,
                    "input_factor_ref": parent_id,
                    "producer_artifact_ref": row.artifact_id,
                    "operation": "factorized hypothesis grouping",
                    "effect_on_output": {
                        "branches": len(payload["branches"]),
                        "rejected": len(payload["rejected_candidate_refs"]),
                        "selected_ref": None,
                    },
                    "activation_or_weight_change": "L3 branch set closed",
                    "context_ref": list(row.context_refs),
                    "reason_if_ignored": "no composable L2 candidate"
                    if parent_id in payload["rejected_candidate_refs"]
                    else None,
                }
            )
    lineage = lineage_manifest(
        arena,
        real_source_refs=sorted({row[2].as_posix() for row in INPUTS}),
        causal_effects=effects,
    )
    all_passed = all(checks.values())
    results = {
        "verdict": "GO" if all_passed else "NO-GO",
        "scope": "closed real L1 ledger to loss-accounted L2 candidates and unselected L3 branches",
        "checks": checks,
        "counts": {
            "experiences": len(INPUTS),
            "analysis_contributions": len(contributions),
            "composed_candidates": len(candidates),
            "successful_candidates": len(successful_candidates),
            "failed_candidates": len(failed_candidates),
            "situation_branch_sets": len(branch_sets),
            "relations": sum(
                len(payloads[row.artifact_id]["relations"])
                for row in successful_candidates
            ),
            "identity_candidates": sum(
                len(payloads[row.artifact_id]["identity_candidates"])
                for row in successful_candidates
            ),
            "facet_candidates": sum(
                len(payloads[row.artifact_id]["facet_candidates"])
                for row in successful_candidates
            ),
            "state_candidates": sum(
                len(payloads[row.artifact_id]["state_candidates"])
                for row in successful_candidates
            ),
            "scope_constraints": sum(
                len(payloads[row.artifact_id]["scope_constraints"])
                for row in successful_candidates
            ),
            "individual_constraints": sum(
                len(payloads[row.artifact_id]["individual_constraints"])
                for row in successful_candidates
            ),
        },
        "demonstrated": [
            "exclusive consumption of a closed real SYS-01 ledger",
            "loss-accounted native MRS to L2 composition",
            "referents, identity candidates, facets, events, states, and n-ary bindings",
            "preserved HCONS and ICONS without scope commitment",
            "explicit propagation of a native no-parse through L2 and L3",
            "held-out lexical generality with identical copular topology",
            "unselected factorized L3 branches",
            "location-independent deterministic full replay and snapshot restore",
        ],
        "not_demonstrated": [
            "world update",
            "semantic consolidation",
            "reference across experiences",
            "chatbot response",
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
    write_json(
        "closed-batches.json",
        {"L1": l1_ledger.as_dict(), "L2": l2_batch.as_dict()},
    )
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "pydelphin": importlib.metadata.version("pydelphin"),
            "registry_digest": arena.registry.digest,
            "ace_sha256": sha256_file(ROOT / ".local/bin/ace"),
            "erg_sha256": sha256_file(
                ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
            ),
            "source_sha256": {
                path.as_posix(): sha256_file(ROOT / path)
                for path in sorted({row[2] for row in INPUTS}, key=str)
            },
            "composer": "seman2_runtime.formal_composition.GenericMRSComposer",
            "hypothesis_manager": "seman2_runtime.hypothesis_system.HypothesisManager",
        },
    )
    print(json.dumps(results, ensure_ascii=False))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
