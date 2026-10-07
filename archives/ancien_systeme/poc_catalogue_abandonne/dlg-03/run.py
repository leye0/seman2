#!/usr/bin/env python3
"""DLG-03: non-fused ERG and Dynamic Syntax branches in Artifact Arena."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import dynamicsyntax
from delphin import ace

from seman2_runtime.cognitive_artifacts import ArtifactProposal, ArtifactStatus, ArtifactTypeRegistry, ArtifactTypeSpec, thaw_json
from seman2_runtime.cognitive_ingestion import IngestionPolicy, IngestionRecord, build_foundation_modules, ingest_records, register_foundation_types
from seman2_runtime.cognitive_runtime import CognitiveRuntime
from seman2_runtime.cognitive_scheduler import ModuleSpec
from seman2_runtime.contracts import canonical_json

POC = Path(__file__).resolve().parent
ROOT = POC.parent.parent
FIXTURES = POC / "fixtures.json"
OUTPUT = POC / "output"
BUILD = "dlg-03-non-fused-complementary-branches"
SESSION = "dlg-03:erg-ds-complementarity"


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def ds_tree(tree) -> list[dict]:
    return [
        {"address": str(address), "labels": sorted(str(label) for label in node.labels), "complete": node.is_complete()}
        for address, node in sorted(tree.items(), key=lambda item: str(item[0]))
    ]


def build_runtime(parser, configuration_digest: str) -> CognitiveRuntime:
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.register(ArtifactTypeSpec(
        "erg-dialogue-analysis", "seman2/erg-dialogue-analysis", 2,
        allowed_modes=frozenset({"ingestion"}), allowed_producers=frozenset({"erg-dialogue-worker"}), parent_types=frozenset({"observation"}),
        required_native_fields=frozenset({"fixture_id", "source_text", "producer", "status", "candidate_count", "candidates", "tokens"}),
        required_projection_fields=frozenset({"parsed", "has_mrs"}),
    ))
    registry.register(ArtifactTypeSpec(
        "dynamic-syntax-dialogue-analysis", "seman2/dynamic-syntax-dialogue-analysis", 2,
        allowed_modes=frozenset({"ingestion"}), allowed_producers=frozenset({"dynamic-syntax-dialogue-worker"}), parent_types=frozenset({"observation"}),
        required_native_fields=frozenset({"fixture_id", "source_text", "analyzed_text", "producer", "status", "semantics", "incremental_states", "actions"}),
        required_projection_fields=frozenset({"parsed", "has_ttr", "state_count"}),
    ))
    registry.register(ArtifactTypeSpec(
        "complementary-analysis-bundle", "seman2/complementary-analysis-bundle", 3,
        allowed_modes=frozenset({"ingestion"}), allowed_producers=frozenset({"complementary-analysis-bundler"}), parent_types=frozenset({"erg-dialogue-analysis", "dynamic-syntax-dialogue-analysis"}),
        required_native_fields=frozenset({"fixture_id", "phenomenon", "erg_analysis_ref", "dynamic_syntax_analysis_ref", "shared_source_observation_ref", "correspondence_claims", "semantic_nodes_fused"}),
        required_projection_fields=frozenset({"erg_parsed", "ds_parsed", "both_parsed", "fusion_count"}),
    ))
    registry.freeze()

    def analyze_erg(trigger, context):
        fixture = thaw_json(trigger.payload_native["native_structure"])
        text = str(trigger.payload_native["text"])
        response = parser.interact(text)
        candidates = [
            {"result_id": row.get("result-id"), "mrs": row.get("mrs"), "derivation": row.get("derivation"), "tree": row.get("tree")}
            for row in response.results()
        ]
        status = "parsed" if candidates else "failure"
        yield ArtifactProposal(
            artifact_type="erg-dialogue-analysis", producer_id="erg-dialogue-worker", producer_build=BUILD, configuration_digest=configuration_digest,
            mode=trigger.mode, session_id=trigger.session_id, wave=context.scheduled_wave, parent_ids=(trigger.artifact_id,), observation_refs=trigger.observation_refs, source_anchors=trigger.source_anchors,
            payload_native={"fixture_id": fixture["fixture_id"], "source_text": text, "producer": "ACE_ERG", "status": status, "candidate_count": len(candidates), "candidates": candidates, "tokens": str(response.tokens("initial")) if response.get("tokens") else None},
            payload_projection={"parsed": bool(candidates), "has_mrs": any(row["mrs"] for row in candidates)},
            status=ArtifactStatus.SUCCESS if candidates else ArtifactStatus.FAILURE,
            justification_ids=(trigger.artifact_id,), losses=() if candidates else ("ERG returned no analysis",), idempotency_key=f"erg-dialogue:{trigger.artifact_id}",
        )

    def analyze_ds(trigger, context):
        fixture = thaw_json(trigger.payload_native["native_structure"])
        source_text = str(trigger.payload_native["text"])
        analyzed_text = fixture["ds_text"]
        result = dynamicsyntax.parse(analyzed_text, "ttr", trace=True)
        states = [
            {"step": label, "tree": ds_tree(tree)}
            for label, tree in zip(("initial",) + result.trace_step_labels, result.trace_trees, strict=True)
        ]
        actions = [{"word": row.word, "action": row.action_name, "edge_id": row.edge_id} for row in result.action_steps]
        assert len(states) == len(analyzed_text.split()) + 1
        status = "parsed" if result.ok else "failure"
        yield ArtifactProposal(
            artifact_type="dynamic-syntax-dialogue-analysis", producer_id="dynamic-syntax-dialogue-worker", producer_build=BUILD, configuration_digest=configuration_digest,
            mode=trigger.mode, session_id=trigger.session_id, wave=context.scheduled_wave, parent_ids=(trigger.artifact_id,), observation_refs=trigger.observation_refs, source_anchors=trigger.source_anchors,
            payload_native={"fixture_id": fixture["fixture_id"], "source_text": source_text, "analyzed_text": analyzed_text, "producer": "dynamicsyntax-python", "status": status, "semantics": str(result.semantics) if result.semantics else None, "incremental_states": states, "actions": actions},
            payload_projection={"parsed": result.ok, "has_ttr": result.semantics is not None, "state_count": len(states)},
            status=ArtifactStatus.SUCCESS if result.ok else ArtifactStatus.FAILURE,
            justification_ids=(trigger.artifact_id,), losses=("case and terminal punctuation normalized explicitly for Dynamic Syntax",) + (() if result.ok else ("Dynamic Syntax parse did not complete",)), idempotency_key=f"dynamic-syntax-dialogue:{trigger.artifact_id}",
        )

    def bundle(trigger, context):
        observation_id = trigger.parent_ids[0]
        erg_rows = [row for row in context.arena.query(artifact_type="erg-dialogue-analysis", session_id=trigger.session_id) if row.parent_ids == (observation_id,)]
        ds_rows = [row for row in context.arena.query(artifact_type="dynamic-syntax-dialogue-analysis", session_id=trigger.session_id) if row.parent_ids == (observation_id,)]
        if not erg_rows or not ds_rows:
            return
        assert len(erg_rows) == len(ds_rows) == 1
        erg_row, ds_row = erg_rows[0], ds_rows[0]
        assert erg_row.payload_native["fixture_id"] == ds_row.payload_native["fixture_id"]
        observation = context.arena.get(observation_id)
        fixture = observation.payload_native["native_structure"]
        yield ArtifactProposal(
            artifact_type="complementary-analysis-bundle", producer_id="complementary-analysis-bundler", producer_build=BUILD, configuration_digest=configuration_digest,
            mode=trigger.mode, session_id=trigger.session_id, wave=context.scheduled_wave, parent_ids=(erg_row.artifact_id, ds_row.artifact_id), observation_refs=trigger.observation_refs, source_anchors=trigger.source_anchors,
            payload_native={"fixture_id": erg_row.payload_native["fixture_id"], "phenomenon": fixture["phenomenon"], "erg_analysis_ref": erg_row.artifact_id, "dynamic_syntax_analysis_ref": ds_row.artifact_id, "shared_source_observation_ref": observation_id, "correspondence_claims": [], "semantic_nodes_fused": False},
            payload_projection={"erg_parsed": erg_row.payload_projection["parsed"], "ds_parsed": ds_row.payload_projection["parsed"], "both_parsed": erg_row.payload_projection["parsed"] and ds_row.payload_projection["parsed"], "fusion_count": 0},
            justification_ids=(erg_row.artifact_id, ds_row.artifact_id), losses=("MRS and TTR nodes remain unaligned",), idempotency_key=f"complementary-bundle:{observation_id}",
        )

    policy = IngestionPolicy(max_records=16, max_text_chars=1_000)
    return CognitiveRuntime(registry=registry, modules=(
        *build_foundation_modules(policy),
        ModuleSpec("erg-dialogue-worker", 2, frozenset({"ingestion"}), frozenset({"observation"}), frozenset({"erg-dialogue-analysis"}), BUILD, configuration_digest, analyze_erg),
        ModuleSpec("dynamic-syntax-dialogue-worker", 2, frozenset({"ingestion"}), frozenset({"observation"}), frozenset({"dynamic-syntax-dialogue-analysis"}), BUILD, configuration_digest, analyze_ds),
        ModuleSpec("complementary-analysis-bundler", 3, frozenset({"ingestion"}), frozenset({"erg-dialogue-analysis", "dynamic-syntax-dialogue-analysis"}), frozenset({"complementary-analysis-bundle"}), BUILD, configuration_digest, bundle),
    ))


def main() -> None:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    fixture_sha = hashlib.sha256(FIXTURES.read_bytes()).hexdigest()
    configuration_digest = digest({"build": BUILD, "fixture_sha256": fixture_sha, "erg_max_results": 5})
    grammar = ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
    executable = ROOT / ".local/bin/ace"
    with ace.ACEParser(str(grammar), executable=str(executable), cmdargs=["-n", "5"]) as parser:
        runtime = build_runtime(parser, configuration_digest)
        records = tuple(
            IngestionRecord(
                record_id=f"dlg-03:{fixture['id']}", discourse_id="dlg-03:controlled-surfaces", turn_index=index, speaker_role="fixture-source", text=fixture["text"], canonical_file=str(FIXTURES.relative_to(ROOT)), source_position=index, source_record_id=fixture["id"], raw_body_sha256=hashlib.sha256(fixture["text"].encode()).hexdigest(), channel="controlled-dialogue", source_kind="utterance",
                native_structure={"fixture_id": fixture["id"], "phenomenon": fixture["phenomenon"], "ds_text": fixture["ds_text"]},
            ) for index, fixture in enumerate(fixtures)
        )
        report = ingest_records(runtime, records, policy=IngestionPolicy(max_records=16, max_text_chars=1_000), session_id=SESSION)
    erg_rows = runtime.arena.query(artifact_type="erg-dialogue-analysis", session_id=SESSION)
    ds_rows = runtime.arena.query(artifact_type="dynamic-syntax-dialogue-analysis", session_id=SESSION)
    bundles = runtime.arena.query(artifact_type="complementary-analysis-bundle", session_id=SESSION)
    assert report["pending_tasks"] == 0 and len(erg_rows) == len(ds_rows) == len(bundles) == len(fixtures)
    expected = {"complete": (True, True), "nominal-fragment": (True, True), "incomplete-transitive": (False, True), "scope": (True, False), "unknown": (True, False), "reprise": (True, False)}
    results, matrix = [], []
    for fixture, erg_row, ds_row, bundle_row in zip(fixtures, erg_rows, ds_rows, bundles, strict=True):
        erg_native, ds_native, bundle_native = thaw_json(erg_row.payload_native), thaw_json(ds_row.payload_native), thaw_json(bundle_row.payload_native)
        assert (erg_native["status"] == "parsed", ds_native["status"] == "parsed") == expected[fixture["id"]]
        assert set(bundle_row.parent_ids) == {erg_row.artifact_id, ds_row.artifact_id}
        assert bundle_native["correspondence_claims"] == [] and bundle_native["semantic_nodes_fused"] is False
        ancestry = runtime.arena.ancestry(bundle_row.artifact_id)
        counts = Counter(row.artifact_type for row in ancestry)
        assert counts == {"complementary-analysis-bundle": 1, "erg-dialogue-analysis": 1, "dynamic-syntax-dialogue-analysis": 1, "observation": 1, "source-record": 1}
        results.append({"fixture": fixture, "analyses": [erg_native, ds_native], "bundle": bundle_native, "runtime_artifact_id": bundle_row.artifact_id, "causal_ancestry_type_counts": dict(counts)})
        matrix.append({"fixture_id": fixture["id"], "phenomenon": fixture["phenomenon"], "erg_parsed": erg_native["status"] == "parsed", "erg_candidate_count": erg_native["candidate_count"], "erg_mrs": any(row["mrs"] for row in erg_native["candidates"]), "ds_parsed": ds_native["status"] == "parsed", "ds_incremental_state_count": len(ds_native["incremental_states"]), "ds_ttr": ds_native["semantics"] is not None, "fused": False})
    assert any(row["ds_incremental_state_count"] > 1 for row in matrix)
    assert any(row["erg_mrs"] for row in matrix) and all(not row["fused"] for row in matrix)
    assert any(row["erg_parsed"] and not row["ds_parsed"] for row in matrix)
    assert any(row["ds_parsed"] and not row["erg_parsed"] for row in matrix)
    summary = {"fixture_count": len(results), "erg_success_count": sum(row["erg_parsed"] for row in matrix), "ds_success_count": sum(row["ds_parsed"] for row in matrix), "bundles_with_both": sum(row["erg_parsed"] and row["ds_parsed"] for row in matrix), "runtime_artifact_count": len(runtime.arena), "runtime_causal_chain_verified": True, "semantic_fusion_count": 0, "demonstrated_complementarity": ["ERG ranked full-sentence HPSG/MRS candidates", "Dynamic Syntax word-level trees/actions and TTR"], "verdict": "GO_INTEGRATED_SEPARATE_COMPLEMENTARY_ANALYSIS_BUNDLE"}
    versions = {"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "dynamicsyntax": importlib.metadata.version("dynamicsyntax"), "pydelphin": importlib.metadata.version("pydelphin"), "erg": "ERG 2018", "max_erg_results": 5, "fixture_sha256": fixture_sha, "configuration_digest": configuration_digest}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, value in (("results.json", results), ("comparison-matrix.json", matrix), ("runtime-artifacts.json", runtime.arena.as_dict()), ("summary.json", summary), ("versions-and-parameters.json", versions)):
        (OUTPUT / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DLG-03: ERG {summary['erg_success_count']}/{len(results)}, DS {summary['ds_success_count']}/{len(results)}, both {summary['bundles_with_both']}, fusion 0")


if __name__ == "__main__":
    main()
