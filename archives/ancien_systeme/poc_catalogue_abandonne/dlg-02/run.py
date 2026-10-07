#!/usr/bin/env python3
"""DLG-02: actual Dynamic Syntax traces in the bottom-up artifact flow."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import subprocess
import time

import dynamicsyntax

from seman2_runtime.cognitive_artifacts import ArtifactProposal, ArtifactStatus, ArtifactTypeRegistry, ArtifactTypeSpec, thaw_json
from seman2_runtime.cognitive_ingestion import IngestionPolicy, IngestionRecord, build_foundation_modules, ingest_records, register_foundation_types
from seman2_runtime.cognitive_runtime import CognitiveRuntime
from seman2_runtime.cognitive_scheduler import ModuleSpec
from seman2_runtime.contracts import canonical_json

POC = Path(__file__).resolve().parent
ROOT = POC.parent.parent
FIXTURES = POC / "fixtures.json"
OUTPUT = POC / "output"
BUILD = "dlg-02-integrated-dynamic-syntax-trace"
SESSION = "dlg-02:dynamic-syntax"


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def serialize_tree(value) -> list[dict]:
    return [
        {
            "address": str(address),
            "labels": sorted(str(label) for label in node.labels),
            "complete": node.is_complete(),
        }
        for address, node in sorted(value.items(), key=lambda item: str(item[0]))
    ]


def token_spans(text: str) -> list[dict]:
    rows, position = [], 0
    for raw_token in text.split():
        start = text.find(raw_token, position)
        assert start >= position
        end = start + len(raw_token)
        assert text[start:end] == raw_token
        rows.append({"token": raw_token.casefold(), "surface": raw_token, "span": [start, end]})
        position = end
    return rows


def parse_trace(text: str, speaker: str) -> dict:
    started = time.perf_counter()
    result = dynamicsyntax.parse(text, "ttr", speaker=speaker, trace=True)
    labels = ("initial",) + result.trace_step_labels
    assert len(labels) == len(result.trace_trees)
    states = [
        {"step_index": index, "step": label, "tree": serialize_tree(tree)}
        for index, (label, tree) in enumerate(zip(labels, result.trace_trees, strict=True))
    ]
    actions = [
        {
            "word": action.word,
            "action": action.action_name,
            "edge_id": action.edge_id,
            "before": serialize_tree(action.before_tree),
            "after": serialize_tree(action.after_tree),
        }
        for action in result.action_steps
    ]
    spans = token_spans(text)
    assert len(states) == len(spans) + 1
    return {
        "producer": "dynamicsyntax-python",
        "ok": result.ok,
        "semantics": str(result.semantics) if result.semantics else None,
        "incremental_states": states,
        "actions": actions,
        "token_spans": spans,
        "final_tree": serialize_tree(result.tree) if result.tree else None,
        "parse_seconds": time.perf_counter() - started,
    }


def probe_dylan() -> dict:
    classpath = ":".join(
        [str(ROOT / ".local/src/dylan/dist/jar/*"), str(ROOT / ".local/src/dylan/lib/*")]
    )
    grammar = ROOT / ".local/src/dylan/resource/2015-english-ttr"
    command = ["java", "-cp", classpath, "qmul.ds.SimpleParser", str(grammar)]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
            "compatible_with_checkout_resources": False,
        }
    commit = subprocess.run(
        ["git", "-C", str(ROOT / ".local/src/dylan"), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": False,
        "checkout_commit": commit,
        "compatible_with_checkout_resources": result.returncode == 0,
    }


def build_runtime(configuration_digest: str, expected_count: int) -> CognitiveRuntime:
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.register(ArtifactTypeSpec(
        "dynamic-syntax-incremental-analysis", "seman2/dynamic-syntax-incremental-analysis", 2,
        allowed_modes=frozenset({"ingestion"}), allowed_producers=frozenset({"dynamic-syntax-incremental-worker"}), parent_types=frozenset({"observation"}),
        required_native_fields=frozenset({"source_text", "language", "speaker", "phenomenon", "producer", "ok", "semantics", "incremental_states", "actions", "token_spans", "final_tree"}),
        required_projection_fields=frozenset({"status", "state_count", "action_count", "language_covered"}),
    ))
    registry.register(ArtifactTypeSpec(
        "dynamic-syntax-coverage-boundary", "seman2/dynamic-syntax-coverage-boundary", 3,
        allowed_modes=frozenset({"ingestion"}), allowed_producers=frozenset({"dynamic-syntax-coverage-auditor"}), parent_types=frozenset({"dynamic-syntax-incremental-analysis"}),
        required_native_fields=frozenset({"implementation", "success_ids", "failure_ids", "french_covered", "speaker_prefix_covered", "reference_comparison_complete"}),
        required_projection_fields=frozenset({"success_count", "failure_count", "partial"}),
    ))
    registry.freeze()

    def analyze(trigger, context):
        structure = thaw_json(trigger.payload_native["native_structure"])
        text = str(trigger.payload_native["text"])
        assert text == structure["source_text"]
        native = parse_trace(text, structure["speaker"])
        native.update({"source_text": text, "language": structure["language"], "speaker": structure["speaker"], "phenomenon": structure["phenomenon"]})
        yield ArtifactProposal(
            artifact_type="dynamic-syntax-incremental-analysis", producer_id="dynamic-syntax-incremental-worker", producer_build=BUILD, configuration_digest=configuration_digest,
            mode=trigger.mode, session_id=trigger.session_id, wave=context.scheduled_wave, parent_ids=(trigger.artifact_id,), observation_refs=trigger.observation_refs, source_anchors=trigger.source_anchors,
            payload_native=native,
            payload_projection={"status": "parsed" if native["ok"] else "failure", "state_count": len(native["incremental_states"]), "action_count": len(native["actions"]), "language_covered": native["ok"] if structure["language"] == "fr" else None},
            status=ArtifactStatus.SUCCESS if native["ok"] else ArtifactStatus.FAILURE,
            justification_ids=(trigger.artifact_id,), losses=() if native["ok"] else ("native Dynamic Syntax parse did not complete",),
            idempotency_key=f"dynamic-syntax-incremental:{trigger.artifact_id}",
        )

    def audit(trigger, context):
        rows = list(context.arena.query(artifact_type="dynamic-syntax-incremental-analysis", session_id=trigger.session_id))
        if len(rows) < expected_count:
            return
        assert len(rows) == expected_count
        success_ids = [row.payload_native["phenomenon"] for row in rows if row.payload_native["ok"]]
        failure_ids = [row.payload_native["phenomenon"] for row in rows if not row.payload_native["ok"]]
        french_covered = any(row.payload_native["ok"] for row in rows if row.payload_native["language"] == "fr")
        speaker_prefix_covered = any(row.payload_native["ok"] for row in rows if row.payload_native["phenomenon"] == "speaker_prefix")
        yield ArtifactProposal(
            artifact_type="dynamic-syntax-coverage-boundary", producer_id="dynamic-syntax-coverage-auditor", producer_build=BUILD, configuration_digest=configuration_digest,
            mode=trigger.mode, session_id=trigger.session_id, wave=context.scheduled_wave, parent_ids=tuple(row.artifact_id for row in rows), observation_refs=tuple(dict.fromkeys(ref for row in rows for ref in row.observation_refs)), source_anchors=tuple(anchor for row in rows for anchor in row.source_anchors),
            payload_native={"implementation": "dynamicsyntax-python", "success_ids": success_ids, "failure_ids": failure_ids, "french_covered": french_covered, "speaker_prefix_covered": speaker_prefix_covered, "reference_comparison_complete": False},
            payload_projection={"success_count": len(success_ids), "failure_count": len(failure_ids), "partial": True},
            justification_ids=tuple(row.artifact_id for row in rows),
            losses=("DyLan Java reference cannot load the checked-out grammar resources", "French and speaker-prefixed input are not covered"),
            idempotency_key="dynamic-syntax-coverage-boundary",
        )

    policy = IngestionPolicy(max_records=16, max_text_chars=1_000)
    return CognitiveRuntime(registry=registry, modules=(
        *build_foundation_modules(policy),
        ModuleSpec("dynamic-syntax-incremental-worker", 2, frozenset({"ingestion"}), frozenset({"observation"}), frozenset({"dynamic-syntax-incremental-analysis"}), BUILD, configuration_digest, analyze),
        ModuleSpec("dynamic-syntax-coverage-auditor", 3, frozenset({"ingestion"}), frozenset({"dynamic-syntax-incremental-analysis"}), frozenset({"dynamic-syntax-coverage-boundary"}), BUILD, configuration_digest, audit),
    ))


def main() -> None:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    expected = {"complete": True, "nominal-fragment": True, "incomplete-transitive": True, "hesitation": True, "cross-speaker-prefix": False, "french-uncovered": False}
    assert {row["id"] for row in fixtures} == set(expected)
    fixture_sha = hashlib.sha256(FIXTURES.read_bytes()).hexdigest()
    configuration_digest = digest({"build": BUILD, "fixture_sha256": fixture_sha, "grammar": "ttr alias"})
    runtime = build_runtime(configuration_digest, len(fixtures))
    records = tuple(
        IngestionRecord(
            record_id=f"dlg-02:{fixture['id']}", discourse_id="dlg-02:incremental-phenomena", turn_index=index, speaker_role=fixture["speaker"], text=fixture["text"], canonical_file=str(FIXTURES.relative_to(ROOT)), source_position=index, source_record_id=fixture["id"], raw_body_sha256=hashlib.sha256(fixture["text"].encode()).hexdigest(), channel="controlled-dialogue", source_kind="utterance",
            native_structure={"fixture_id": fixture["id"], "source_text": fixture["text"], "language": fixture["language"], "speaker": fixture["speaker"], "phenomenon": fixture["phenomenon"]},
        )
        for index, fixture in enumerate(fixtures)
    )
    report = ingest_records(runtime, records, policy=IngestionPolicy(max_records=16, max_text_chars=1_000), session_id=SESSION)
    analyses = runtime.arena.query(artifact_type="dynamic-syntax-incremental-analysis", session_id=SESSION)
    boundaries = runtime.arena.query(artifact_type="dynamic-syntax-coverage-boundary", session_id=SESSION)
    assert report["pending_tasks"] == 0 and len(analyses) == len(fixtures) and len(boundaries) == 1
    results = []
    for fixture, artifact in zip(fixtures, analyses, strict=True):
        native = thaw_json(artifact.payload_native)
        assert native["ok"] is expected[fixture["id"]]
        assert native["source_text"] == fixture["text"]
        assert len(native["incremental_states"]) == len(native["token_spans"]) + 1
        assert native["incremental_states"][0]["step"] == "initial"
        ancestry = runtime.arena.ancestry(artifact.artifact_id)
        assert {row.artifact_type for row in ancestry} == {"source-record", "observation", "dynamic-syntax-incremental-analysis"}
        results.append({"fixture": fixture, **native, "runtime_artifact_id": artifact.artifact_id, "parent_observation_id": artifact.parent_ids[0], "causal_ancestry_types": [row.artifact_type for row in ancestry]})
    boundary = boundaries[0]
    assert len(boundary.parent_ids) == len(analyses)
    assert boundary.payload_native["french_covered"] is False
    assert boundary.payload_native["speaker_prefix_covered"] is False

    java = probe_dylan()
    assert java["compatible_with_checkout_resources"] is False
    summary = {
        "fixture_count": len(results),
        "python_success_count": sum(row["ok"] for row in results),
        "python_failure_count": sum(not row["ok"] for row in results),
        "incremental_trace_count": sum(len(row["incremental_states"]) for row in results),
        "action_count": sum(len(row["actions"]) for row in results),
        "runtime_artifact_count": len(runtime.arena),
        "runtime_causal_chain_verified": True,
        "french_success": next(row["ok"] for row in results if row["fixture"]["language"] == "fr"),
        "dylan_java_exit_code": java["exit_code"],
        "implementation_comparison_complete": java["compatible_with_checkout_resources"],
        "verdict": "PARTIAL_INTEGRATED_PYTHON_INCREMENTAL_TRACE_DYLAN_REFERENCE_INCOMPATIBLE",
    }
    versions = {"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "dynamicsyntax": importlib.metadata.version("dynamicsyntax"), "python": platform.python_version(), "grammar": "ttr alias", "fixture_sha256": fixture_sha, "configuration_digest": configuration_digest, "dylan_jar_sha256": hashlib.sha256((ROOT / ".local/src/dylan/dist/jar/ds.jar").read_bytes()).hexdigest()}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, value in (("results.json", results), ("runtime-artifacts.json", runtime.arena.as_dict()), ("dylan-java-probe.json", java), ("summary.json", summary), ("versions-and-parameters.json", versions)):
        (OUTPUT / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DLG-02: Python {summary['python_success_count']}/{len(results)}; {summary['incremental_trace_count']} states; DyLan Java exit {java['exit_code']}")


if __name__ == "__main__":
    main()
