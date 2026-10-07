#!/usr/bin/env python3
"""DLG-01: conversation observations in the bottom-up artifact flow."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import networkx as nx

from seman2_runtime.cognitive_artifacts import ArtifactProposal, ArtifactTypeRegistry, ArtifactTypeSpec, thaw_json
from seman2_runtime.cognitive_ingestion import IngestionPolicy, IngestionRecord, build_foundation_modules, ingest_records, register_foundation_types
from seman2_runtime.cognitive_runtime import CognitiveRuntime
from seman2_runtime.cognitive_scheduler import ModuleSpec
from seman2_runtime.contracts import canonical_json

POC = Path(__file__).resolve().parent
ROOT = POC.parent.parent
FIXTURES = POC / "fixtures.json"
OUTPUT = POC / "output"
BUILD = "dlg-01-bottom-up-conversation-observation"
SESSION = "dlg-01:controlled-conversations"
FORBIDDEN = {"communicative_function", "dialogue_act", "intention", "belief", "commitment", "accepted", "grounded"}


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def validate_fixture(fixture: dict) -> None:
    participants, turns, source = fixture["participants"], fixture["turns"], fixture["source"]
    assert participants and len(participants) == len(set(participants))
    assert turns and len({turn["id"] for turn in turns}) == len(turns)
    assert "\n".join(turn["text"] for turn in turns) == source
    turn_ids = {turn["id"] for turn in turns}
    for index, turn in enumerate(turns):
        start, end = turn["span"]
        assert turn["speaker"] in participants
        assert 0 <= start < end <= len(source) and source[start:end] == turn["text"]
        assert (index == 0 and start == 0) or (index > 0 and start == turns[index - 1]["span"][1] + 1)
        if "reply_to" in turn:
            assert turn["reply_to"] in turn_ids and turn["reply_to"] != turn["id"]
        assert all(target in turn_ids and target != turn["id"] for target in turn.get("overlaps", ()))


def build_graph(turns: list[dict]) -> dict:
    ordered = sorted(turns, key=lambda row: row["turn_index"])
    first = ordered[0]
    conversation_id = first["conversation_id"]
    assert len(ordered) == first["expected_turn_count"]
    assert all(row["conversation_id"] == conversation_id for row in ordered)
    assert [row["turn_index"] for row in ordered] == list(range(len(ordered)))
    assert all(row["participants"] == first["participants"] for row in ordered)
    assert all(row["full_source_sha256"] == first["full_source_sha256"] for row in ordered)
    source = "\n".join(row["raw_text"] for row in ordered)
    assert hashlib.sha256(source.encode()).hexdigest() == first["full_source_sha256"]
    graph = nx.MultiDiGraph()
    graph.add_node(conversation_id, kind="conversation", channel=first["channel"], language=first["language"], raw_source=source, raw_source_sha256=first["full_source_sha256"])
    for participant in first["participants"]:
        graph.add_node(participant, kind="participant")
        graph.add_edge(participant, conversation_id, relation="participates_in")
    for index, turn in enumerate(ordered):
        graph.add_node(turn["turn_id"], kind="turn", speaker=turn["speaker"], raw_text=turn["raw_text"], span=turn["span"], source_order=turn["turn_index"])
        graph.add_edge(turn["speaker"], turn["turn_id"], relation="produced")
        graph.add_edge(turn["turn_id"], conversation_id, relation="contained_in")
        if index:
            graph.add_edge(ordered[index - 1]["turn_id"], turn["turn_id"], relation="precedes_in_source")
        if turn["reply_to"] is not None:
            graph.add_edge(turn["turn_id"], turn["reply_to"], relation="reply_to")
        for target in turn["overlaps"]:
            graph.add_edge(turn["turn_id"], target, relation="overlaps_observably")
    nodes = [{"id": node_id, **attrs} for node_id, attrs in graph.nodes(data=True)]
    edges = [{"source": a, "target": b, **attrs} for a, b, attrs in graph.edges(data=True)]
    assert not any(FORBIDDEN & set(row) for row in nodes + edges)
    return {"conversation_id": conversation_id, "language": first["language"], "channel": first["channel"], "source": source, "source_sha256": first["full_source_sha256"], "nodes": nodes, "edges": edges, "source_reconstructed": True, "pragmatic_inferences_created": 0}


def build_runtime(configuration_digest: str) -> CognitiveRuntime:
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.register(ArtifactTypeSpec(
        "conversation-turn-observation", "seman2/conversation-turn-observation", 2,
        allowed_modes=frozenset({"ingestion"}), allowed_producers=frozenset({"conversation-turn-adapter"}), parent_types=frozenset({"observation"}),
        required_native_fields=frozenset({"conversation_id", "turn_id", "turn_index", "expected_turn_count", "participants", "speaker", "raw_text", "span", "language", "channel", "reply_to", "overlaps", "full_source_sha256"}),
        required_projection_fields=frozenset({"has_reply_to", "overlap_count"}),
    ))
    registry.register(ArtifactTypeSpec(
        "conversation-observation-graph", "seman2/conversation-observation-graph", 3,
        allowed_modes=frozenset({"ingestion"}), allowed_producers=frozenset({"conversation-observation-builder"}), parent_types=frozenset({"conversation-turn-observation"}),
        required_native_fields=frozenset({"conversation_id", "source", "source_sha256", "nodes", "edges", "source_reconstructed", "pragmatic_inferences_created"}),
        required_projection_fields=frozenset({"participant_count", "turn_count", "reply_to_count", "overlap_count"}),
    ))
    registry.freeze()

    def adapt_turn(trigger, context):
        native = thaw_json(trigger.payload_native["native_structure"])
        assert trigger.payload_native["text"] == native["raw_text"]
        assert native["speaker"] in native["participants"]
        assert native["span"][1] - native["span"][0] == len(native["raw_text"])
        yield ArtifactProposal(
            artifact_type="conversation-turn-observation", producer_id="conversation-turn-adapter", producer_build=BUILD, configuration_digest=configuration_digest,
            mode=trigger.mode, session_id=trigger.session_id, wave=context.scheduled_wave, parent_ids=(trigger.artifact_id,), observation_refs=trigger.observation_refs, source_anchors=trigger.source_anchors,
            payload_native=native, payload_projection={"has_reply_to": native["reply_to"] is not None, "overlap_count": len(native["overlaps"])}, justification_ids=(trigger.artifact_id,), idempotency_key=f"conversation-turn:{trigger.artifact_id}",
        )

    def assemble(trigger, context):
        conversation_id = trigger.payload_native["conversation_id"]
        turns = [row for row in context.arena.query(artifact_type="conversation-turn-observation", session_id=trigger.session_id) if row.payload_native["conversation_id"] == conversation_id]
        expected = int(trigger.payload_native["expected_turn_count"])
        if len(turns) < expected:
            return
        assert len(turns) == expected
        graph = build_graph([thaw_json(row.payload_native) for row in turns])
        relations = Counter(row["relation"] for row in graph["edges"])
        yield ArtifactProposal(
            artifact_type="conversation-observation-graph", producer_id="conversation-observation-builder", producer_build=BUILD, configuration_digest=configuration_digest,
            mode=trigger.mode, session_id=trigger.session_id, wave=context.scheduled_wave, parent_ids=tuple(row.artifact_id for row in turns), observation_refs=tuple(dict.fromkeys(ref for row in turns for ref in row.observation_refs)), source_anchors=tuple(anchor for row in turns for anchor in row.source_anchors),
            payload_native=graph,
            payload_projection={"participant_count": sum(row["kind"] == "participant" for row in graph["nodes"]), "turn_count": sum(row["kind"] == "turn" for row in graph["nodes"]), "reply_to_count": relations["reply_to"], "overlap_count": relations["overlaps_observably"]},
            justification_ids=tuple(row.artifact_id for row in turns), idempotency_key=f"conversation-graph:{conversation_id}",
        )

    policy = IngestionPolicy(max_records=32, max_text_chars=5_000)
    return CognitiveRuntime(registry=registry, modules=(
        *build_foundation_modules(policy),
        ModuleSpec("conversation-turn-adapter", 2, frozenset({"ingestion"}), frozenset({"observation"}), frozenset({"conversation-turn-observation"}), BUILD, configuration_digest, adapt_turn),
        ModuleSpec("conversation-observation-builder", 3, frozenset({"ingestion"}), frozenset({"conversation-turn-observation"}), frozenset({"conversation-observation-graph"}), BUILD, configuration_digest, assemble),
    ))


def main() -> None:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    for fixture in fixtures:
        validate_fixture(fixture)
    invalid = json.loads(json.dumps(fixtures[0]))
    invalid["turns"][0]["speaker"] = "unknown-participant"
    try:
        validate_fixture(invalid)
    except AssertionError:
        invalid_rejected = True
    else:
        invalid_rejected = False
    assert invalid_rejected

    fixture_sha = hashlib.sha256(FIXTURES.read_bytes()).hexdigest()
    configuration_digest = digest({"build": BUILD, "fixture_sha256": fixture_sha, "forbidden_inferences": sorted(FORBIDDEN)})
    runtime = build_runtime(configuration_digest)
    records, source_position = [], 0
    for fixture in fixtures:
        source_sha = hashlib.sha256(fixture["source"].encode()).hexdigest()
        for turn_index, turn in enumerate(fixture["turns"]):
            records.append(IngestionRecord(
                record_id=f"dlg-01:{fixture['id']}:{turn['id']}", discourse_id=fixture["id"], turn_index=turn_index, speaker_role=turn["speaker"], text=turn["text"], canonical_file=str(FIXTURES.relative_to(ROOT)), source_position=source_position, source_record_id=f"{fixture['id']}:{turn['id']}", raw_body_sha256=hashlib.sha256(turn["text"].encode()).hexdigest(), channel=fixture["channel"], source_kind="conversation-turn",
                native_structure={"conversation_id": fixture["id"], "turn_id": turn["id"], "turn_index": turn_index, "expected_turn_count": len(fixture["turns"]), "participants": fixture["participants"], "speaker": turn["speaker"], "raw_text": turn["text"], "span": turn["span"], "language": fixture["language"], "channel": fixture["channel"], "reply_to": turn.get("reply_to"), "overlaps": turn.get("overlaps", []), "full_source_sha256": source_sha},
            ))
            source_position += 1
    report = ingest_records(runtime, tuple(records), policy=IngestionPolicy(max_records=32, max_text_chars=5_000), session_id=SESSION)
    turns = runtime.arena.query(artifact_type="conversation-turn-observation", session_id=SESSION)
    graphs = runtime.arena.query(artifact_type="conversation-observation-graph", session_id=SESSION)
    assert report["pending_tasks"] == 0
    assert len(turns) == sum(len(row["turns"]) for row in fixtures) and len(graphs) == len(fixtures)
    results = []
    for fixture, artifact in zip(fixtures, graphs, strict=True):
        graph = thaw_json(artifact.payload_native)
        assert graph["conversation_id"] == fixture["id"] and graph["source"] == fixture["source"]
        assert graph["pragmatic_inferences_created"] == 0 and len(artifact.parent_ids) == len(fixture["turns"])
        counts = Counter(row.artifact_type for row in runtime.arena.ancestry(artifact.artifact_id))
        expected = len(fixture["turns"])
        assert counts == {"conversation-observation-graph": 1, "conversation-turn-observation": expected, "observation": expected, "source-record": expected}
        assert not any(forbidden in canonical_json(graph) for forbidden in FORBIDDEN)
        results.append({**graph, "runtime_artifact_id": artifact.artifact_id, "parent_turn_artifact_ids": list(artifact.parent_ids), "causal_ancestry_type_counts": dict(counts)})

    summary = {
        "fixture_count": len(results), "turn_count": len(turns),
        "participant_count": sum(row.payload_projection["participant_count"] for row in graphs),
        "reply_to_count": sum(row.payload_projection["reply_to_count"] for row in graphs),
        "overlap_count": sum(row.payload_projection["overlap_count"] for row in graphs),
        "runtime_artifact_count": len(runtime.arena), "runtime_causal_chain_verified": True,
        "source_reconstruction_verified": True, "invalid_participant_rejected": invalid_rejected,
        "pragmatic_inferences_created": 0,
        "verdict": "GO_BOTTOM_UP_CONVERSATION_OBSERVATION_WITHOUT_PREMATURE_INTERPRETATION",
    }
    versions = {"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "python": platform.python_version(), "networkx": nx.__version__, "fixture_sha256": fixture_sha, "configuration_digest": configuration_digest, "schema": "seman2/conversation-observation-graph"}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, value in (("results.json", results), ("runtime-artifacts.json", runtime.arena.as_dict()), ("summary.json", summary), ("versions-and-parameters.json", versions)):
        (OUTPUT / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DLG-01: {summary['turn_count']} turns ingested; {summary['reply_to_count']} replies; {summary['overlap_count']} overlaps; 0 pragmatic inference")


if __name__ == "__main__":
    main()
