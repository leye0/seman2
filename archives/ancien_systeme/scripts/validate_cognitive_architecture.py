#!/usr/bin/env python3
"""Valide l'ancien blueprint cognitif archivé pour les POC de compatibilité."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT / "plans/archives/cognitive_system_architecture.json"
REQUIRED_POC = ROOT / "plans/required_poc.md"


def fail(message: str) -> None:
    raise SystemExit(f"NO-GO-COGNITIVE-ARCHITECTURE: {message}")


def main() -> int:
    data = json.loads(ARCHITECTURE.read_text(encoding="utf-8"))
    services = data.get("service_families", [])
    service_ids = [row.get("id") for row in services]
    duplicates = sorted(identifier for identifier, count in Counter(service_ids).items() if count > 1)
    if duplicates:
        fail(f"services dupliqués: {duplicates}")
    known = set(service_ids)
    if None in known or "" in known:
        fail("identifiant de service vide")

    modes = set(data.get("runtime_model", {}).get("modes", []))
    if modes != {"ingestion", "chatbot"}:
        fail(f"modes cognitifs inattendus: {sorted(modes)}")
    if data["runtime_model"].get("primary_live_state") != "ram":
        fail("l'état cognitif vivant principal doit être en RAM")
    if data["runtime_model"].get("source_native_structure_preserved") is not True:
        fail("la structure native observable de la source doit être conservée")
    if data["runtime_model"].get("evaluation_labels_in_cognition") is not False:
        fail("les labels d'évaluation ne peuvent entrer dans la cognition")
    if data["runtime_model"].get("llm_in_cognitive_path") is not False:
        fail("un LLM ne peut entrer dans le chemin cognitif")

    memory_ids = {row["id"] for row in data.get("memory_domains", [])}
    required_fields = set(data.get("artifact_contract", {}).get("required_fields", []))
    contract_minimum = {
        "artifact_id", "artifact_type", "producer_id", "mode", "session_id",
        "observation_refs", "episode_refs", "wave", "derivation_depth", "source_anchors",
        "parent_ids", "status", "justification_ids", "contradiction_ids",
    }
    if not contract_minimum <= required_fields:
        fail(f"contrat d'artefact incomplet: {sorted(contract_minimum - required_fields)}")

    for service in services:
        identifier = service["id"]
        dependencies = service.get("dependencies", [])
        unknown = sorted(set(dependencies) - known)
        if unknown:
            fail(f"{identifier}: dépendances inconnues {unknown}")
        if identifier in dependencies:
            fail(f"{identifier}: auto-dépendance")
        if not service.get("consumes") or not service.get("produces"):
            fail(f"{identifier}: contrat entrée/sortie vide")
        unknown_memories = sorted(set(service.get("memory_domains", [])) - memory_ids)
        if unknown_memories:
            fail(f"{identifier}: mémoires inconnues {unknown_memories}")
        service_modes = set(service.get("modes", []))
        if not service_modes or not service_modes <= {"ingestion", "chatbot", "evaluation"}:
            fail(f"{identifier}: modes invalides {sorted(service_modes)}")
        if not service.get("execution"):
            fail(f"{identifier}: sémantique d'exécution absente")

    by_id = {row["id"]: row for row in services}
    indegree = {identifier: 0 for identifier in known}
    children = {identifier: set() for identifier in known}
    for service in services:
        for dependency in service["dependencies"]:
            if by_id[dependency]["layer"] > service["layer"]:
                fail(
                    f"dépendance descendante interdite: {dependency} "
                    f"(L{by_id[dependency]['layer']}) -> {service['id']} (L{service['layer']})"
                )
            if service["id"] not in children[dependency]:
                children[dependency].add(service["id"])
                indegree[service["id"]] += 1
    ready = sorted(identifier for identifier, count in indegree.items() if count == 0)
    order: list[str] = []
    while ready:
        identifier = ready.pop(0)
        order.append(identifier)
        for child in sorted(children[identifier]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if len(order) != len(services):
        fail("cycle dans les dépendances bottom-up; utiliser feedback_paths avec vague différée")

    required_pocs = set(
        re.findall(r"^### ([A-Z]+-\d+) —", REQUIRED_POC.read_text(encoding="utf-8"), re.MULTILINE)
    )
    covered_pocs = {
        poc_id for service in services for poc_id in service.get("poc_coverage", [])
    }
    if extra := sorted(covered_pocs - required_pocs):
        fail(f"POC inconnues dans le blueprint: {extra}")
    current_architecture_pocs = sorted(required_pocs - covered_pocs)
    invalidated = data.get("invalidated_pocs", {})
    if invalidated:
        fail(f"POC encore invalidées: {sorted(invalidated)}")
    reimplemented = data.get("reimplemented_pocs", {})
    if set(reimplemented) != {"RUN-03", "RUN-04"}:
        fail("RUN-03 et RUN-04 doivent être marquées comme réimplémentées")

    forbidden = set(data.get("forbidden_paths", []))
    required_forbidden = {
        "parquet-to-high-level-system",
        "corpus-answer-id-to-soar-retrieval",
        "evaluation-label-to-cognitive-memory",
        "openrouter-to-runtime-decision",
        "high-level-system-reading-raw-text-without-low-level-parent",
    }
    if not required_forbidden <= forbidden:
        fail(f"raccourcis interdits non spécifiés: {sorted(required_forbidden - forbidden)}")

    retrieval = next(row for row in services if row["id"] == "structural-retrieval")
    if any("parquet" in value or "source-event" in value for value in retrieval["consumes"]):
        fail("le retrieval cognitif ne doit pas interroger la source Parquet")
    if "ranked-internal-memory-reference" not in retrieval["produces"]:
        fail("le retrieval doit retourner des références vers la mémoire interne")

    dictionary_consumers = [
        row["id"] for row in services if "dictionary-jsonl" in row["consumes"]
    ]
    if dictionary_consumers != ["corpus-ingestion"]:
        fail(
            "le dictionnaire JSONL doit entrer uniquement par corpus-ingestion, "
            f"pas comme vérité lexicale: {dictionary_consumers}"
        )

    feedback = data.get("feedback_paths", [])
    if not feedback or any(row.get("visible_after_waves", 0) < 1 for row in feedback):
        fail("tout feedback doit être différé d'au moins une vague")
    unknown_feedback = sorted({row[key] for row in feedback for key in ("from", "to")} - known)
    if unknown_feedback:
        fail(f"feedback vers service inconnu: {unknown_feedback}")

    report = {
        "status": "GO-ARCHIVED-COGNITIVE-BLUEPRINT-STRUCTURALLY-VALID",
        "scope": "legacy-poc-compatibility-not-current-architecture",
        "services": len(services),
        "layers": len({row["layer"] for row in services}),
        "memory_domains": len(memory_ids),
        "covered_pocs": len(covered_pocs),
        "current_architecture_pocs_outside_legacy_blueprint": current_architecture_pocs,
        "invalidated_pocs": sorted(invalidated),
        "reimplemented_pocs": sorted(reimplemented),
        "feedback_paths": len(feedback),
        "bottom_up_topological_order": order,
        "ingestion_services": sum("ingestion" in row["modes"] for row in services),
        "chatbot_services": sum("chatbot" in row["modes"] for row in services),
        "forbidden_shortcuts": len(forbidden),
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"NO-GO-COGNITIVE-ARCHITECTURE: schéma invalide: {exc}", file=sys.stderr)
        raise SystemExit(1)
