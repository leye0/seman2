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
OUTPUT = ROOT / "poc/sys-01/output"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_artifacts import (  # noqa: E402
    ArtifactArena,
    ArtifactStatus,
    thaw_json,
)
from seman2_runtime.low_level_system import (  # noqa: E402
    AceErgAnalyzer,
    AnalysisOrchestrator,
    ExperienceGateway,
    LowLevelPolicy,
    build_low_level_registry,
    lineage_manifest,
    sha256_file,
)


NOVEL = Path("data/the_map_of_everything_nlp_novel.txt")
CONTROLLED = Path("data/curriculum/sys_01_open_vocabulary.txt")


def write_json(name: str, value: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def ingest_sample(
    arena: ArtifactArena,
    source_root: Path,
    policy: LowLevelPolicy,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    gateway = ExperienceGateway(
        arena,
        session_id="sys-01",
        policy=policy,
        source_root=source_root,
    )
    novel_rows = gateway.ingest_file(
        source_root / NOVEL,
        experience_prefix="sys-01:novel",
        start_line=15,
        max_observations=4,
    )
    controlled_rows = gateway.ingest_file(
        source_root / CONTROLLED,
        experience_prefix="sys-01:controlled",
        sequence_start=len(novel_rows),
        source_kind="controlled-open-vocabulary-and-negative-experience",
        max_observations=2,
    )
    pairs = novel_rows + controlled_rows
    experiences = tuple(pair[0] for pair in pairs)
    observations = tuple(pair[1] for pair in pairs)
    return experiences, observations


def normal_run(
    source_root: Path,
    *,
    project_root: Path,
    policy: LowLevelPolicy,
) -> tuple[ArtifactArena, tuple[object, ...], object, tuple[object, ...]]:
    registry = build_low_level_registry()
    arena = ArtifactArena(registry)
    _, observations = ingest_sample(arena, source_root, policy)
    analyzer = AceErgAnalyzer(arena, project_root=project_root, policy=policy)
    ledger, contributions = AnalysisOrchestrator(policy=policy).execute(
        observations, analyzer
    )
    return arena, observations, ledger, contributions


def exact_source_bytes(observation: object, source_root: Path) -> bool:
    native = thaw_json(observation.payload_native)
    anchors = [thaw_json(row) for row in observation.source_anchors]
    if len(anchors) != 1:
        return False
    anchor = anchors[0]
    source = source_root / anchor["source_path"]
    with source.open("rb") as handle:
        handle.seek(anchor["byte_start"])
        raw = handle.read(anchor["byte_end"] - anchor["byte_start"])
    return (
        raw == native["surface"].encode("utf-8")
        and native["span_start"] == anchor["byte_start"]
        and native["span_end"] == anchor["byte_end"]
        and native["span_unit"] == "utf8-byte-in-source"
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
            "source_anchors": [thaw_json(anchor) for anchor in row.source_anchors],
            "payload_native": thaw_json(row.payload_native),
            "payload_projection": thaw_json(row.payload_projection),
            "status": row.status.value,
        }
        for row in arena.query()
    ]


def main() -> int:
    # Une POC doit réussir sans aucun résultat antérieur.
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)

    policy = LowLevelPolicy(
        max_sentence_chars=240,
        max_candidates=3,
        worker_timeout_seconds=30.0,
        worker_memory_mib=1_024,
        max_observations_per_wave=8,
    )
    arena, observations, normal_ledger, normal_contributions = normal_run(
        ROOT, project_root=ROOT, policy=policy
    )

    # Les chemins d'échec utilisent exactement les mêmes interfaces de production.
    timeout_policy = LowLevelPolicy(
        max_sentence_chars=240,
        max_candidates=3,
        worker_timeout_seconds=0.001,
        worker_memory_mib=1_024,
        max_observations_per_wave=8,
    )
    timeout_ledger, timeout_rows = AnalysisOrchestrator(
        policy=timeout_policy
    ).execute(
        (observations[0],),
        AceErgAnalyzer(arena, project_root=ROOT, policy=timeout_policy),
    )
    failure_analyzer = AceErgAnalyzer(
        arena,
        project_root=ROOT,
        policy=policy,
        ace_executable=ROOT / ".local/bin/ace-intentionally-absent",
    )
    failure_ledger, failure_rows = AnalysisOrchestrator(policy=policy).execute(
        (observations[1],), failure_analyzer
    )
    all_contributions = normal_contributions + timeout_rows + failure_rows

    normal_payloads = [thaw_json(row.payload_native) for row in normal_contributions]
    surfaces = [thaw_json(row.payload_native)["surface"] for row in observations]
    statuses = [payload["worker_status"] for payload in normal_payloads]
    unknown_rows = [
        payload
        for payload in normal_payloads
        if "glorped" in str(payload.get("native_result", {}).get("mrs", ""))
    ]
    candidates_by_observation: dict[str, list[object]] = {}
    for row in normal_contributions:
        if row.status is ArtifactStatus.SUCCESS:
            candidates_by_observation.setdefault(row.parent_ids[0], []).append(row)

    # Replay depuis une autre racine : aucun chemin absolu ni ancien output ne doit aider.
    with tempfile.TemporaryDirectory(prefix="seman2-sys01-replay-") as temp_name:
        replay_root = Path(temp_name)
        for relative in (NOVEL, CONTROLLED):
            destination = replay_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        replay_arena, _, replay_ledger, _ = normal_run(
            replay_root, project_root=ROOT, policy=policy
        )
        replay_equal = stable_view(arena)[: len(replay_arena.query())] == stable_view(
            replay_arena
        )
        replay_ledger_equal = (
            normal_ledger.ledger_digest == replay_ledger.ledger_digest
        )

    restored = ArtifactArena.restore(build_low_level_registry(), arena.as_dict())
    normal_measured = [
        thaw_json(row.resource_cost) for row in normal_contributions
    ]
    measured_peak_under_limit = all(
        isinstance(cost.get("worker_peak_rss_kib"), int)
        and isinstance(cost.get("ace_peak_rss_kib"), int)
        and max(cost["worker_peak_rss_kib"], cost["ace_peak_rss_kib"])
        <= policy.worker_memory_mib * 1024
        for cost in normal_measured
    )
    grouped_counts: dict[str, int] = {}
    for row in normal_contributions:
        grouped_counts[row.parent_ids[0]] = grouped_counts.get(row.parent_ids[0], 0) + 1

    checks = {
        "generic_streaming_ingestion": len(observations) == 6,
        "source_surface_is_exact_utf8_slice": all(
            exact_source_bytes(row, ROOT) for row in observations
        ),
        "source_anchors_are_clone_relative": all(
            not Path(thaw_json(row.source_anchors[0])["source_path"]).is_absolute()
            for row in observations
        ),
        "source_digests_are_recorded": all(
            thaw_json(row.source_anchors[0])["source_sha256"]
            == sha256_file(ROOT / thaw_json(row.source_anchors[0])["source_path"])
            for row in observations
        ),
        "orchestrator_routes_every_observation": (
            len(normal_ledger.route_decisions) == len(observations)
            and set(normal_ledger.observation_ids)
            == {row.artifact_id for row in observations}
        ),
        "ledger_barrier_is_closed_and_complete": (
            normal_ledger.closed
            and set(normal_ledger.contribution_ids)
            == {row.artifact_id for row in normal_contributions}
        ),
        "real_novel_mrs_exists": any(
            payload.get("native_result", {}).get("mrs")
            for payload in normal_payloads
        ),
        "real_ambiguity_is_semantically_distinct": (
            any(
                len(rows) >= 2
                and len(
                    {
                        thaw_json(row.payload_native)["native_result"]["mrs"]
                        for row in rows
                    }
                )
                == len(rows)
                for rows in candidates_by_observation.values()
            )
        ),
        "unknown_form_reaches_native_mrs": bool(unknown_rows)
        and all("_unknown" in row["native_result"]["mrs"] for row in unknown_rows),
        "native_no_parse_is_retained": "no-parse" in statuses,
        "real_timeout_is_retained": (
            len(timeout_rows) == 1
            and thaw_json(timeout_rows[0].payload_native)["worker_status"] == "timeout"
            and thaw_json(timeout_rows[0].resource_cost).get("process_group_killed") is True
            and timeout_ledger.closed
        ),
        "real_worker_failure_is_retained": (
            len(failure_rows) == 1
            and thaw_json(failure_rows[0].payload_native)["worker_status"]
            == "process-failure"
            and failure_ledger.closed
        ),
        "every_L1_has_exact_L0_parent": all(
            len(row.parent_ids) == 1
            and arena.get(row.parent_ids[0]).artifact_type == "observation"
            for row in all_contributions
        ),
        "no_truth_or_world_commit": all(
            thaw_json(row.payload_projection)["truth_committed"] is False
            and thaw_json(row.payload_projection)["world_update_performed"] is False
            for row in all_contributions
        ),
        "candidate_budget_respected": all(
            count <= policy.max_candidates for count in grouped_counts.values()
        ),
        "resource_costs_are_measured": all(
            isinstance(cost.get("wall_time_ms"), (int, float))
            and cost["wall_time_ms"] > 0
            for cost in normal_measured
        ),
        "measured_peaks_respect_memory_limit": measured_peak_under_limit,
        "location_independent_replay_is_identical": replay_equal
        and replay_ledger_equal,
        "checkpoint_restore_is_exact": stable_view(restored) == stable_view(arena),
    }

    effects = []
    ledger_by_contribution = {
        ref: normal_ledger.ledger_digest for ref in normal_ledger.contribution_ids
    } | {ref: timeout_ledger.ledger_digest for ref in timeout_ledger.contribution_ids} | {
        ref: failure_ledger.ledger_digest for ref in failure_ledger.contribution_ids
    }
    for row in all_contributions:
        status = thaw_json(row.payload_native)["worker_status"]
        effects.append(
            {
                "consumer_artifact_ref": f"closed-ledger:{ledger_by_contribution[row.artifact_id]}",
                "input_factor_ref": row.parent_ids[0],
                "producer_artifact_ref": row.artifact_id,
                "operation": "ACE/ERG parse under orchestrator budget",
                "effect_on_output": (
                    "native candidate appended"
                    if row.status is ArtifactStatus.SUCCESS
                    else f"explicit {status} contribution appended"
                ),
                "activation_or_weight_change": "one ledger contribution added",
                "context_ref": None,
                "reason_if_ignored": None,
            }
        )
    lineage = lineage_manifest(
        arena,
        real_source_refs=[NOVEL.as_posix(), CONTROLLED.as_posix()],
        causal_effects=effects,
    )
    all_passed = all(checks.values())
    results = {
        "verdict": "GO" if all_passed else "NO-GO",
        "scope": "generic bounded L0 ingestion through closed native L1 ledger",
        "checks": checks,
        "counts": {
            "experiences": len(arena.query(artifact_type="experience-occurrence")),
            "observations": len(observations),
            "normal_contributions": len(normal_contributions),
            "success_contributions": sum(
                row.status is ArtifactStatus.SUCCESS for row in normal_contributions
            ),
            "retained_failures": sum(
                row.status is ArtifactStatus.FAILURE for row in all_contributions
            ),
            "closed_ledgers": 3,
        },
        "demonstrated": [
            "generic bounded file ingestion and exact UTF-8 source spans",
            "real ACE/ERG alternatives and open-vocabulary analysis",
            "explicit no-parse, timeout, and process-failure contributions",
            "measured and enforced worker resource budgets",
            "closed L1 ledger with one route decision per observation",
            "location-independent deterministic identities and native results",
            "exact in-memory arena checkpoint restoration",
            "complete L0 to L1 causal trace",
        ],
        "not_demonstrated": [
            "semantic composition",
            "world knowledge",
            "memory consolidation",
            "dialogue",
            "chatbot response",
            "cultural interpretation",
        ],
        "sample_surfaces": surfaces,
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
        "closed-ledgers.json",
        {
            "normal": normal_ledger.as_dict(),
            "timeout": timeout_ledger.as_dict(),
            "process_failure": failure_ledger.as_dict(),
        },
    )
    ace_path = ROOT / ".local/bin/ace"
    erg_path = ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "pydelphin": importlib.metadata.version("pydelphin"),
            "policy": policy.__dict__,
            "registry_digest": arena.registry.digest,
            "ace_sha256": sha256_file(ace_path),
            "erg_sha256": sha256_file(erg_path),
            "source_sha256": {
                NOVEL.as_posix(): sha256_file(ROOT / NOVEL),
                CONTROLLED.as_posix(): sha256_file(ROOT / CONTROLLED),
            },
            "worker": "seman2_runtime.workers.ace_worker",
        },
    )
    print(json.dumps(results, ensure_ascii=False))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
