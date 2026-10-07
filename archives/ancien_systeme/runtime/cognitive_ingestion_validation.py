"""Validation exécutable d'une session d'ingestion cognitive complète.

Ce module n'exécute pas une POC et ne lit aucune sortie de POC. Il inspecte
directement l'état vivant d'une :class:`CognitiveIngestionSession`, ce qui le
rend utilisable aussi bien par la CLI que par les preuves runtime RUN-01/02.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .cognitive_artifacts import ArtifactStatus, Residency
from .cognitive_ingestion_session import CognitiveIngestionSession


REQUIRED_INGESTION_MODULES = frozenset(
    {
        "observation-normalizer",
        "sentence-segmenter",
        "formal-analysis-dispatch",
        "erg-worker",
        "dynamic-syntax-worker",
        "link-grammar-worker",
        "lexical-resource-worker",
        "form-phonology-worker",
        "native-analysis-ledger",
        "cross-representation-linker",
        "mrs-graph-adapter",
        "semantic-composer",
        "semantic-reference-state",
        "temporal-relation-system",
        "constraint-engine",
        "factorized-hypothesis-manager",
        "hypothesis-family-builder",
        "soar-control",
        "formal-discourse-system",
        "formal-dialogue-system",
        "situation-episode-system",
        "structural-retrieval",
        "statistics-system",
        "induction-engine",
        "cultural-concept-system",
        "candidate-transformation-system",
        "soar-transformation-control",
        "ingestion-state-consolidator",
    }
)

ANALYSIS_ARTIFACT_TYPES = frozenset(
    {
        "mrs-analysis",
        "dynamic-syntax-analysis",
        "linkage-analysis",
        "lexical-analysis",
        "form-phonology-analysis",
    }
)

CRITICAL_ARTIFACT_TYPES = (
    "constraint-solution",
    "soar-control-state",
    "dialogue-state-candidate",
    "episode-candidate",
    "cultural-learning-state",
    "soar-transformation-decision",
    "memory-consolidation-state",
)


def assess_cognitive_ingestion(
    session: CognitiveIngestionSession,
    *,
    records_processed_this_run: int,
    input_path: Path | None = None,
    input_format: str | None = None,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    """Retourne une preuve structurée de participation et de causalité.

    La simple présence d'un module dans une trace ne suffit pas. Chaque état de
    consolidation terminal doit avoir, dans son ascendance réelle, les sorties
    de tous les modules requis. Cela prouve que les niveaux hauts consomment la
    matière produite en dessous plutôt que de seulement s'exécuter à côté.
    """

    runtime = session.runtime
    artifacts = runtime.arena.query()
    artifact_counts = Counter(row.artifact_type for row in artifacts)
    module_counts: Counter[str] = Counter()
    exhausted: list[dict[str, Any]] = []
    for frontier in runtime.scheduler.trace:
        for result in frontier["results"]:
            module_counts[result["module_id"]] += 1
            if result["status"] != "completed":
                exhausted.append(result)

    observations = artifact_counts["observation"]
    units = artifact_counts["observable-unit"]
    episodes = artifact_counts["episode-candidate"]
    pending = runtime.scheduler.pending_count
    missing_modules = sorted(REQUIRED_INGESTION_MODULES - set(module_counts))

    native_failure_artifacts = [
        {
            "artifact_type": row.artifact_type,
            "producer_id": row.producer_id,
            "losses": list(row.losses),
        }
        for row in artifacts
        if row.status is ArtifactStatus.FAILURE
        and row.artifact_type in ANALYSIS_ARTIFACT_TYPES
    ]
    worker_execution_failures = [
        row for row in native_failure_artifacts if row["losses"]
    ]
    mandatory_analysis_types = (
        "mrs-analysis",
        "lexical-analysis",
        "form-phonology-analysis",
    )
    mandatory_analysis_complete = all(
        artifact_counts[artifact_type] == units
        and all(
            row.status is ArtifactStatus.SUCCESS
            for row in runtime.arena.query(artifact_type=artifact_type)
        )
        for artifact_type in mandatory_analysis_types
    )
    critical_failure_artifacts = [
        {
            "artifact_type": row.artifact_type,
            "producer_id": row.producer_id,
            "losses": list(row.losses),
        }
        for artifact_type in CRITICAL_ARTIFACT_TYPES
        for row in runtime.arena.query(artifact_type=artifact_type)
        if row.status is not ArtifactStatus.SUCCESS
    ]
    consolidations = runtime.arena.query(
        artifact_type="memory-consolidation-state"
    )
    soar_states = runtime.arena.query(artifact_type="soar-control-state")
    soar_active_context_projection_complete = bool(soar_states) and all(
        row.payload_native["working_memory_verified"]
        and row.payload_native["all_required_refs_observed_in_wm"]
        and row.payload_native["inactive_refs_absent_from_wm"]
        and row.payload_native["projected_justification_ref_count"] > 0
        and len(row.payload_native["active_context_digest"]) == 64
        and not row.payload_projection["persistent_store_copied_to_soar"]
        for row in soar_states
    )
    transformation_decisions = runtime.arena.query(
        artifact_type="soar-transformation-decision"
    )
    soar_transformation_projection_complete = bool(transformation_decisions) and all(
        row.payload_native["selection_is_operational"]
        and not row.payload_native["semantic_truth_selected"]
        and row.payload_native["all_required_refs_observed_in_wm"]
        and row.payload_native["projected_precondition_ref_count"] > 0
        and len(row.payload_native["active_context_digest"]) == 64
        for row in transformation_decisions
    )
    consolidations_applied = bool(consolidations) and all(
        row.payload_native["applied"]
        and not row.payload_native["truth_committed"]
        for row in consolidations
    )

    terminal_lineages = []
    for terminal in consolidations:
        ancestry = runtime.arena.ancestry(terminal.artifact_id)
        producers = {row.producer_id for row in ancestry}
        types = {row.artifact_type for row in ancestry}
        terminal_lineages.append(
            {
                "terminal_artifact_id": terminal.artifact_id,
                "ancestry_size": len(ancestry),
                "root_source_present": "source-record" in types,
                "observation_present": "observation" in types,
                "covered_required_modules": sorted(
                    REQUIRED_INGESTION_MODULES & producers
                ),
                "missing_required_modules": sorted(
                    REQUIRED_INGESTION_MODULES - producers
                ),
            }
        )
    every_terminal_has_complete_bottom_up_lineage = bool(terminal_lineages) and all(
        row["root_source_present"]
        and row["observation_present"]
        and not row["missing_required_modules"]
        for row in terminal_lineages
    )

    critical_ok = (
        observations == session.next_record_index
        and units > 0
        and artifact_counts["dynamic-syntax-analysis"] == units
        and artifact_counts["linkage-analysis"] == units
        and artifact_counts["native-analysis-ledger-entry"] == units * 5
        and artifact_counts["cross-representation-hypothesis"] == units
        and mandatory_analysis_complete
        and episodes > 0
        and artifact_counts["soar-control-state"] == episodes
        and artifact_counts["constraint-solution"] > 0
        and artifact_counts["dialogue-state-candidate"] == episodes
        and artifact_counts["cultural-learning-state"] == episodes
        and artifact_counts["memory-consolidation-state"] == episodes
        and pending == 0
        and not exhausted
        and not worker_execution_failures
        and not critical_failure_artifacts
        and consolidations_applied
        and soar_active_context_projection_complete
        and soar_transformation_projection_complete
        and not missing_modules
        and every_terminal_has_complete_bottom_up_lineage
    )

    report: dict[str, Any] = {
        "status": "GO-INGESTION-SYSTEM" if critical_ok else "NO-GO-INGESTION-SYSTEM",
        "source_record_count": len(session.records),
        "records_processed_this_run": records_processed_this_run,
        "next_record_index": session.next_record_index,
        "complete": session.complete,
        "pending_tasks": pending,
        "artifact_count": len(runtime.arena),
        "active_artifact_count": len(
            runtime.arena.query(residency=Residency.ACTIVE)
        ),
        "latent_artifact_count": len(
            runtime.arena.query(residency=Residency.LATENT)
        ),
        "artifact_counts": dict(sorted(artifact_counts.items())),
        "participating_modules": dict(sorted(module_counts.items())),
        "required_modules": sorted(REQUIRED_INGESTION_MODULES),
        "missing_required_modules": missing_modules,
        "terminal_bottom_up_lineages": terminal_lineages,
        "every_terminal_has_complete_bottom_up_lineage": (
            every_terminal_has_complete_bottom_up_lineage
        ),
        "module_failures_or_budget_exhaustion": exhausted,
        "native_failure_artifacts": native_failure_artifacts,
        "worker_execution_failures": worker_execution_failures,
        "critical_failure_artifacts": critical_failure_artifacts,
        "all_memory_consolidations_applied_without_truth_commit": (
            consolidations_applied
        ),
        "soar_active_context_projection_complete": (
            soar_active_context_projection_complete
        ),
        "soar_transformation_projection_complete": (
            soar_transformation_projection_complete
        ),
        "accepted_coverage_limits": [
            "Dynamic Syntax may preserve a native parse failure while ERG carries the semantic branch",
            "Link Grammar may preserve a native no-linkage result while ERG carries the semantic branch",
            "RST requires a routed multi-EDU unit",
            "calendar normalization requires attributed external calendar context",
            "Tree-sitter requires an observation explicitly typed as code",
        ],
        "worker_limit": runtime.control.limits.max_worker_count,
        "checkpoint": str(checkpoint_path) if checkpoint_path else None,
        "cognitive_labels_or_oracles_used": False,
    }
    if input_path is not None:
        report.update(
            {
                "input": str(input_path),
                "input_format": input_format,
                "source_bytes": input_path.stat().st_size,
            }
        )
    return report
