#!/usr/bin/env python3
"""DISC-02: ingest attributed IsaNLP output and audit its actual boundary."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Any, Mapping

from seman2_runtime.cognitive_artifacts import (
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    thaw_json,
)
from seman2_runtime.cognitive_ingestion import (
    IngestionPolicy,
    IngestionRecord,
    build_foundation_modules,
    ingest_records,
    register_foundation_types,
)
from seman2_runtime.cognitive_runtime import CognitiveRuntime
from seman2_runtime.cognitive_scheduler import ModuleSpec
from seman2_runtime.contracts import canonical_json


POC = Path(__file__).resolve().parent
ROOT = POC.parent.parent
DISC01 = ROOT / "poc" / "disc-01"
SOURCE = DISC01 / "output" / "results.json"
SOURCE_META = DISC01 / "output" / "versions-and-parameters.json"
FIXTURES = DISC01 / "fixtures.json"
OUTPUT = POC / "output"
BUILD = "disc-02-attributed-rst-boundary"
SESSION = "disc-02:actual-isanlp-output"


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nodes(node: Mapping[str, Any], parent: Mapping[str, Any] | None = None):
    yield node, parent
    for key in ("left", "right"):
        child = node.get(key)
        if isinstance(child, Mapping):
            yield from nodes(child, node)


def validate_parsed_result(row: Mapping[str, Any]) -> None:
    fixture = row["fixture"]
    text = fixture["text"]
    assert row["status"] == "parsed"
    assert text and row["trees"]
    leaves = []
    for tree in row["trees"]:
        for node, _ in nodes(tree):
            if "left" not in node and "right" not in node:
                leaves.append(node)
    assert leaves == row["edus"]
    assert row["node_count"] == sum(
        1 for tree in row["trees"] for _ in nodes(tree)
    )
    assert all(
        0 <= edu["start"] <= edu["end"] <= len(text)
        and text[edu["start"] : edu["end"]] == edu["text"]
        for edu in leaves
    )
    assert row["edu_spans_reconstruct_source"] is True


def property_matrix(analyses: list[Mapping[str, Any]]) -> tuple[list[dict], dict]:
    fields: Counter[str] = Counter()
    parents: Counter[tuple[str, int]] = Counter()
    binary = True
    nested = True
    edges = relations = nuclearities = leaves = 0
    for analysis in analyses:
        fixture_id = str(analysis["external_fixture_id"])
        for tree in analysis["trees"]:
            for node, parent in nodes(tree):
                fields.update(node.keys())
                children = [
                    node[key]
                    for key in ("left", "right")
                    if isinstance(node.get(key), Mapping)
                ]
                if children:
                    binary &= len(children) == 2
                    relations += int(bool(node.get("relation")))
                    nuclearities += int(bool(node.get("nuclearity")))
                else:
                    leaves += 1
                if parent is not None:
                    edges += 1
                    parents[(fixture_id, int(node["id"]))] += 1
                    nested &= (
                        parent["start"] <= node["start"] <= node["end"] <= parent["end"]
                    )
    scores = fields["proba"] + sum(len(row.get("scores", ())) for row in analyses)
    signals = fields["signal"] + fields["signals"]
    secondary = sum(
        fields[key] for key in ("secondary", "secondary_edges", "secedges", "secedge")
    )
    turns = sum(
        fields[key] for key in ("speaker", "participant", "turn", "turn_id", "reply_to")
    )
    max_parents = max(parents.values(), default=0)
    matrix = [
        {"property": "EDU segmentation with exact character spans", "present": leaves > 0, "evidence": f"{leaves} elementary leaves reconstruct source slices"},
        {"property": "labeled rhetorical relations", "present": relations > 0, "evidence": f"{relations} labeled internal nodes"},
        {"property": "nuclearity", "present": nuclearities > 0, "evidence": f"{nuclearities} internal NS/SN/NN values"},
        {"property": "binary constituency tree", "present": binary and edges > 0, "evidence": f"{edges} parent-child edges; every internal node has two children"},
        {"property": "confidence scores", "present": scores > 0, "evidence": f"serialized score occurrences={scores}"},
        {"property": "explicit discourse signals", "present": signals > 0, "evidence": f"serialized signal field occurrences={signals}"},
        {"property": "secondary/eRST links", "present": secondary > 0, "evidence": f"serialized secondary-edge occurrences={secondary}"},
        {"property": "non-tree graph", "present": max_parents > 1, "evidence": f"maximum observed parent count={max_parents}"},
        {"property": "crossing/non-projective attachments", "present": not nested, "evidence": f"all child spans nested in parent={nested}"},
        {"property": "automatic dialogue-turn structure", "present": turns > 0, "evidence": f"serialized turn/participant field occurrences={turns}"},
    ]
    validation = {
        "core_rst_properties_present": all(row["present"] for row in matrix[:4]),
        "unsupported_properties_absent": all(not row["present"] for row in matrix[4:]),
        "all_child_spans_nested": nested,
        "maximum_parent_count": max_parents,
        "edge_count": edges,
        "leaf_count": leaves,
    }
    return matrix, validation


def build_runtime(
    actual_by_id: dict[str, dict],
    *,
    expected_count: int,
    configuration_digest: str,
    source_digest: str,
    source_metadata: dict,
) -> CognitiveRuntime:
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.register(
        ArtifactTypeSpec(
            "attributed-rst-analysis", "seman2/attributed-rst-analysis", 2,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"isanlp-rst-output-adapter"}),
            parent_types=frozenset({"observation"}),
            required_native_fields=frozenset({"source_text", "external_fixture_id", "model", "revision", "offset_contract", "trees", "edus", "scores", "source_results_sha256"}),
            required_projection_fields=frozenset({"tree_count", "edu_count", "relation_labels", "nuclearities"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "rst-capability-boundary", "seman2/rst-capability-boundary", 3,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"rst-capability-auditor"}),
            parent_types=frozenset({"attributed-rst-analysis"}),
            required_native_fields=frozenset({"property_matrix", "classification", "validation", "input_count"}),
            required_projection_fields=frozenset({"present_count", "absent_count", "not_an_erst_graph"}),
        )
    )
    registry.freeze()

    def adapt(trigger, context):
        fixture_id = str(trigger.payload_native["native_structure"]["fixture_id"])
        assert fixture_id in actual_by_id
        actual = actual_by_id[fixture_id]
        text = str(trigger.payload_native["text"])
        assert text == actual["fixture"]["text"]
        validate_parsed_result(actual)
        yield ArtifactProposal(
            artifact_type="attributed-rst-analysis",
            producer_id="isanlp-rst-output-adapter",
            producer_build=BUILD,
            configuration_digest=configuration_digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "source_text": text,
                "external_fixture_id": fixture_id,
                "model": source_metadata["model"],
                "revision": source_metadata["revision"],
                "offset_contract": source_metadata["offsets"],
                "trees": actual["trees"],
                "edus": actual["edus"],
                "scores": actual["scores"],
                "source_results_sha256": source_digest,
            },
            payload_projection={
                "tree_count": len(actual["trees"]),
                "edu_count": len(actual["edus"]),
                "relation_labels": actual["relation_labels"],
                "nuclearities": actual["nuclearities"],
            },
            justification_ids=(trigger.artifact_id,),
            losses=("no scores/signals/eRST/dialogue structure in observed serialized output",),
            idempotency_key=f"attributed-rst:{trigger.artifact_id}",
        )

    def audit(trigger, context):
        available = list(context.arena.query(artifact_type="attributed-rst-analysis", session_id=trigger.session_id))
        if len(available) < expected_count:
            return
        assert len(available) == expected_count
        matrix, validation = property_matrix([thaw_json(row.payload_native) for row in available])
        yield ArtifactProposal(
            artifact_type="rst-capability-boundary",
            producer_id="rst-capability-auditor",
            producer_build=BUILD,
            configuration_digest=configuration_digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=tuple(row.artifact_id for row in available),
            observation_refs=tuple(dict.fromkeys(ref for row in available for ref in row.observation_refs)),
            source_anchors=tuple(anchor for row in available for anchor in row.source_anchors),
            payload_native={"property_matrix": matrix, "classification": "RST_BINARY_TREE_OUTPUT_NOT_ERST_GRAPH_OUTPUT", "validation": validation, "input_count": len(available)},
            payload_projection={"present_count": sum(row["present"] for row in matrix), "absent_count": sum(not row["present"] for row in matrix), "not_an_erst_graph": True},
            justification_ids=tuple(row.artifact_id for row in available),
            losses=("absence in this output contract is not evidence that the underlying corpus lacks the property",),
            idempotency_key=f"rst-capability-boundary:{source_digest}",
        )

    policy = IngestionPolicy(max_records=16, max_text_chars=5_000)
    modules = (
        *build_foundation_modules(policy),
        ModuleSpec("isanlp-rst-output-adapter", 2, frozenset({"ingestion"}), frozenset({"observation"}), frozenset({"attributed-rst-analysis"}), BUILD, configuration_digest, adapt),
        ModuleSpec("rst-capability-auditor", 3, frozenset({"ingestion"}), frozenset({"attributed-rst-analysis"}), frozenset({"rst-capability-boundary"}), BUILD, configuration_digest, audit),
    )
    return CognitiveRuntime(registry=registry, modules=modules)


def main() -> None:
    raw_results = json.loads(SOURCE.read_text(encoding="utf-8"))
    metadata = json.loads(SOURCE_META.read_text(encoding="utf-8"))
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    assert metadata["fixture_sha256"] == sha256_bytes(FIXTURES)
    assert [row["fixture"] for row in raw_results] == fixtures
    parsed = [row for row in raw_results if row["status"] == "parsed"]
    rejected = [row for row in raw_results if row["status"] != "parsed"]
    assert len(parsed) == 6 and len(rejected) == 1
    assert rejected[0]["fixture"]["id"] == "empty-adversarial"
    assert rejected[0]["status"] == "invalid_input" and rejected[0]["fixture"]["text"] == ""
    for row in parsed:
        validate_parsed_result(row)

    tampered = json.loads(json.dumps(parsed[0]))
    tampered["edus"][0]["text"] = "tampered"
    try:
        validate_parsed_result(tampered)
    except AssertionError:
        tampered_rejected = True
    else:
        tampered_rejected = False
    assert tampered_rejected

    source_digest = sha256_bytes(SOURCE)
    configuration_digest = hashlib.sha256(canonical_json({"build": BUILD, "source_results_sha256": source_digest, "source_metadata_sha256": sha256_bytes(SOURCE_META), "fixture_sha256": sha256_bytes(FIXTURES)}).encode()).hexdigest()
    runtime = build_runtime(
        {row["fixture"]["id"]: row for row in parsed},
        expected_count=len(parsed),
        configuration_digest=configuration_digest,
        source_digest=source_digest,
        source_metadata=metadata,
    )
    records = tuple(
        IngestionRecord(
            record_id=f"disc-02:{row['fixture']['id']}",
            discourse_id=f"disc-01:{row['fixture']['category']}",
            turn_index=index,
            speaker_role="fixture-source",
            text=row["fixture"]["text"],
            canonical_file=str(FIXTURES.relative_to(ROOT)),
            source_position=index,
            source_record_id=row["fixture"]["id"],
            raw_body_sha256=hashlib.sha256(row["fixture"]["text"].encode()).hexdigest(),
            channel="controlled-discourse",
            source_kind="multi-edu-text",
            native_structure={"fixture_id": row["fixture"]["id"], "language": row["fixture"]["language"], "category": row["fixture"]["category"]},
        )
        for index, row in enumerate(parsed)
    )
    ingestion = ingest_records(runtime, records, policy=IngestionPolicy(max_records=16, max_text_chars=5_000), session_id=SESSION)
    analyses = runtime.arena.query(artifact_type="attributed-rst-analysis", session_id=SESSION)
    boundaries = runtime.arena.query(artifact_type="rst-capability-boundary", session_id=SESSION)
    assert ingestion["pending_tasks"] == 0 and len(analyses) == len(parsed) and len(boundaries) == 1
    boundary = boundaries[0]
    assert set(boundary.parent_ids) == {row.artifact_id for row in analyses}
    matrix = [dict(row) for row in boundary.payload_native["property_matrix"]]
    validation = thaw_json(boundary.payload_native["validation"])
    assert validation["core_rst_properties_present"] is True
    assert validation["unsupported_properties_absent"] is True
    assert all(row["present"] for row in matrix[:4])
    assert all(not row["present"] for row in matrix[4:])
    assert boundary.payload_projection["not_an_erst_graph"] is True

    analysis_results = []
    for analysis in analyses:
        ancestry = runtime.arena.ancestry(analysis.artifact_id)
        by_type = {row.artifact_type: row for row in ancestry}
        assert set(by_type) == {"source-record", "observation", "attributed-rst-analysis"}
        assert by_type["source-record"].payload_native["text"] == analysis.payload_native["source_text"]
        assert by_type["observation"].payload_native["text"] == analysis.payload_native["source_text"]
        assert analysis.payload_native["source_results_sha256"] == source_digest
        analysis_results.append({"fixture_id": analysis.payload_native["external_fixture_id"], "artifact_id": analysis.artifact_id, "parent_observation_id": analysis.parent_ids[0], "tree_count": analysis.payload_projection["tree_count"], "edu_count": analysis.payload_projection["edu_count"], "causal_ancestry_types": sorted(by_type), "source_text_preserved": True})

    full_ancestry = runtime.arena.ancestry(boundary.artifact_id)
    type_counts = Counter(row.artifact_type for row in full_ancestry)
    assert type_counts == {"rst-capability-boundary": 1, "attributed-rst-analysis": 6, "observation": 6, "source-record": 6}
    summary = {
        "source_fixture_count": len(raw_results),
        "parsed_and_ingested_count": len(parsed),
        "invalid_input_count": len(rejected),
        "runtime_artifact_count": len(runtime.arena),
        "property_count": len(matrix),
        "present_count": sum(row["present"] for row in matrix),
        "absent_count": sum(not row["present"] for row in matrix),
        "classification": boundary.payload_native["classification"],
        "actual_isanlp_output_digest_verified": True,
        "runtime_causal_chain_verified": True,
        "tampered_output_rejected": tampered_rejected,
        "heavy_model_reexecuted": False,
        "verdict": "GO_INTEGRATED_ATTRIBUTED_RST_BINARY_TREE_BOUNDARY",
    }
    results = {
        "source_artifact": str(SOURCE.relative_to(ROOT)),
        "source_results_sha256": source_digest,
        "source_model": {"model": metadata["model"], "revision": metadata["revision"], "source_commit": metadata["isanlp_rst_source_commit"]},
        "invalid_input": rejected[0],
        "analyses": analysis_results,
        "boundary_artifact_id": boundary.artifact_id,
        "boundary_parent_ids": list(boundary.parent_ids),
        "boundary_ancestry_type_counts": dict(type_counts),
        "property_matrix": matrix,
        "classification": boundary.payload_native["classification"],
        "validation": validation,
    }
    try:
        package_version = importlib.metadata.version("isanlp_rst")
    except importlib.metadata.PackageNotFoundError:
        package_version = "importable in DISC-01 environment; distribution metadata unavailable here"
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "isanlp_rst": package_version,
        "source_results_sha256": source_digest,
        "source_metadata_sha256": sha256_bytes(SOURCE_META),
        "fixture_sha256": sha256_bytes(FIXTURES),
        "configuration_digest": configuration_digest,
        "model_execution": "reused verified DISC-01 output; no model reload",
        "offset_contract": metadata["offsets"],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, value in (("results.json", results), ("property-matrix.json", matrix), ("runtime-artifacts.json", runtime.arena.as_dict()), ("summary.json", summary), ("versions-and-parameters.json", versions)):
        (OUTPUT / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DISC-02: {len(parsed)} real RST outputs ingested; {summary['present_count']} properties present, {summary['absent_count']} absent; attributed binary-tree boundary")


if __name__ == "__main__":
    main()
