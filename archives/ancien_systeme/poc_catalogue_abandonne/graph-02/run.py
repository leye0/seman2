#!/usr/bin/env python3
"""GRAPH-02: strict attributed external-annotation contract, Arrow + Protobuf."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import struct
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

P = Path(__file__).resolve().parent
ROOT = P.parent.parent
OUT = P / "output"

PRODUCERS = {
    "nlp-01": ("ACE+ERG", "HPSG/MRS"), "nlp-02": ("PyDelphin+ERG", "MRS/DMRS"),
    "nlp-03": ("PyDelphin+Z3", "MRS/scopal constraints"), "nlp-04": ("ACE+ERG", "HPSG/MRS"),
    "nlp-05": ("Link Grammar", "linkage"), "nlp-06": ("ACE+ERG and Link Grammar", "parallel syntax/semantics"),
    "lex-01": ("NLTK WordNet", "lexical semantic network"), "lex-02": ("NLTK VerbNet", "VerbNet classes/frames"),
    "lex-03": ("NLTK PropBank", "PropBank rolesets"), "lex-04": ("NLTK FrameNet", "FrameNet"),
    "lex-05": ("SemLink", "cross-resource mappings"), "lex-06": ("WordNet+SUMO", "ontology mapping"),
    "lex-07": ("ACE/ERG+lexical resources", "occurrence/resource alignment"),
    "time-01": ("seman2 temporal adapter", "strict partial order"), "time-02": ("seman2 Allen reasoner", "Allen interval algebra"),
    "time-03": ("seman2 temporal adapter", "Reichenbach E/R/S"), "time-04": ("seman2 temporal reasoner", "Event Calculus"),
    "time-05": ("seman2 discourse adapter", "Temporal DRT/SDRT"), "time-06": ("seman2 episodic retriever", "relational temporal retrieval"),
    "time-07": ("seman2 revision ledger", "non-destructive belief revision"),
    "time-08": ("HeidelTime+Duckling quarantine adapter", "surface temporal normalization"),
    "sem-01": ("Epitran", "grapheme-to-phoneme"), "sem-02": ("PanPhon", "phonological feature distance"),
    "sem-03": ("Pynini", "weighted finite-state transduction"), "sem-04": ("Phonetisaurus", "WFST G2P"),
    "disc-01": ("IsaNLP RST", "RST constituency"),
    "dlg-01": ("seman2 conversation adapter", "conversation observation graph"),
    "dlg-02": ("dynamicsyntax-python", "Dynamic Syntax/TTR"),
    "dlg-03": ("ACE/ERG+dynamicsyntax", "separate MRS and TTR analyses"),
    "dlg-04": ("DialogBank adapter", "ISO 24617-2/DiAML"), "dlg-05": ("DISRPT adapter", "SDRT"),
    "code-01": ("Tree-sitter", "concrete syntax tree"), "code-02": ("Tree-sitter", "error-tolerant concrete syntax tree"),
}


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def representative(value):
    return max(value, key=lambda item: len(canonical(item))) if isinstance(value, list) and value else value


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def extract_spans(sample) -> list[dict]:
    spans, seen = [], set()
    for item in walk(sample):
        if not isinstance(item, dict):
            continue
        candidates = []
        for key, value in item.items():
            if "span" in key.lower() and isinstance(value, list) and len(value) == 2 and all(isinstance(x, int) for x in value):
                candidates.append((key, value[0], value[1]))
        if all(k in item for k in ("start", "end")) and all(isinstance(item[k], int) for k in ("start", "end")):
            candidates.append(("explicit_start_end", item["start"], item["end"]))
        for coordinate, start, end in candidates:
            identity = (coordinate, start, end)
            if start <= end and identity not in seen:
                spans.append({"coordinate_system": coordinate, "start": start, "end": end,
                              "unit": "producer_native"})
                seen.add(identity)
            if len(spans) >= 16:
                return spans
    return spans


def extract_named_lists(sample, needle: str) -> list[str]:
    found = []
    for item in walk(sample):
        if isinstance(item, dict):
            for key, value in item.items():
                if needle in key.lower() and isinstance(value, (list, dict)):
                    values = value if isinstance(value, list) else [value]
                    found.extend(canonical(x) for x in values[:8])
        if len(found) >= 16:
            break
    return found[:16]


def extract_score(sample):
    for item in walk(sample):
        if isinstance(item, dict):
            for key, value in item.items():
                if key.lower() in {"score", "probability", "confidence"} and isinstance(value, (int, float)) and not isinstance(value, bool):
                    return float(value)
    return None


def version_label(metadata: dict) -> str:
    """Only report actual version/revision evidence, never Python as producer version."""
    values = []
    for key, value in metadata.items():
        lowered = key.lower()
        if any(marker in lowered for marker in ("version", "commit", "revision")) and isinstance(value, (str, int, float)):
            values.append(f"{key}={value}")
        elif isinstance(value, dict):
            for child_key, child in value.items():
                if any(marker in child_key.lower() for marker in ("version", "commit", "revision", "label")) and isinstance(child, (str, int, float)):
                    values.append(f"{key}.{child_key}={child}")
    return "; ".join(values[:8]) or "not_reported_by_source"


def protobuf_classes():
    file = descriptor_pb2.FileDescriptorProto(name="external_annotation.proto", package="seman2.graph.v1", syntax="proto3")
    span = file.message_type.add(name="Span")
    ann = file.message_type.add(name="ExternalAnnotation")

    def field(message, name, number, kind, label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
              type_name=None, proto3_optional=False):
        f = message.field.add(name=name, number=number, type=kind, label=label)
        if type_name:
            f.type_name = type_name
        if proto3_optional:
            oneof = message.oneof_decl.add(name=f"_{name}")
            f.oneof_index = len(message.oneof_decl) - 1
            f.proto3_optional = True

    T = descriptor_pb2.FieldDescriptorProto
    for number, name, kind in ((1, "coordinate_system", T.TYPE_STRING), (2, "start", T.TYPE_INT64),
                               (3, "end", T.TYPE_INT64), (4, "unit", T.TYPE_STRING)):
        field(span, name, number, kind)
    string_fields = ((1, "id"), (2, "input_observation_id"), (3, "producer"), (4, "producer_version"),
                     (5, "parameters_json"), (6, "model"), (7, "formalism"), (8, "annotation_type"),
                     (9, "raw_value_json"))
    for number, name in string_fields:
        field(ann, name, number, T.TYPE_STRING)
    field(ann, "spans", 10, T.TYPE_MESSAGE, T.LABEL_REPEATED, ".seman2.graph.v1.Span")
    field(ann, "alternatives_json", 11, T.TYPE_STRING, T.LABEL_REPEATED)
    field(ann, "constraints_json", 12, T.TYPE_STRING, T.LABEL_REPEATED)
    field(ann, "score", 13, T.TYPE_DOUBLE, proto3_optional=True)
    for number, name, kind in ((14, "input_modality", T.TYPE_STRING), (15, "derived_from_text", T.TYPE_BOOL),
                               (16, "is_audio_observation", T.TYPE_BOOL), (17, "source_artifact", T.TYPE_STRING),
                               (18, "source_selector", T.TYPE_STRING), (19, "source_cognitive_artifact_id", T.TYPE_STRING),
                               (20, "producer_build", T.TYPE_STRING), (21, "configuration_digest", T.TYPE_STRING),
                               (22, "status", T.TYPE_STRING)):
        field(ann, name, number, kind)
    pool = descriptor_pool.DescriptorPool()
    pool.Add(file)
    return (message_factory.GetMessageClass(pool.FindMessageTypeByName("seman2.graph.v1.ExternalAnnotation")), file)


def validate(record: dict) -> None:
    required = ("id", "input_observation_id", "producer", "producer_version", "parameters_json", "formalism",
                "annotation_type", "raw_value_json", "input_modality", "source_artifact", "source_selector",
                "producer_build", "configuration_digest", "status")
    assert all(record[key] for key in required)
    assert record["input_modality"] == "text" and record["derived_from_text"] is True
    assert record["is_audio_observation"] is False
    assert all(span["start"] <= span["end"] for span in record["spans"])
    assert json.loads(record["parameters_json"]) is not None and json.loads(record["raw_value_json"]) is not None


def main() -> None:
    records = []

    def adapt(record_id: str, poc_id: str, producer: str, formalism: str, sample,
              metadata: dict, result_path: Path, selector: str, annotation_type: str | None = None,
              producer_version_override: str | None = None,
              cognitive_artifact: dict | None = None) -> None:
        score = extract_score(sample)
        native_digest = hashlib.sha256(canonical(sample).encode()).hexdigest()
        record = {
            "id": record_id,
            "input_observation_id": (
                cognitive_artifact["observation_refs"][0]
                if cognitive_artifact and cognitive_artifact["observation_refs"]
                else f"external-source:{poc_id}:{native_digest[:24]}"
            ),
            "producer": producer, "producer_version": producer_version_override or version_label(metadata),
            "parameters_json": canonical(metadata.get("parameters", metadata)),
            "model": str(metadata.get("model", metadata.get("erg", {}).get("label_reported_by_ace", ""))) if isinstance(metadata.get("erg", {}), dict) else str(metadata.get("model", "")),
            "formalism": formalism, "annotation_type": annotation_type or poc_id,
            "raw_value_json": canonical(sample), "spans": extract_spans(sample),
            "alternatives_json": extract_named_lists(sample, "alternative"),
            "constraints_json": extract_named_lists(sample, "constraint"),
            "score": score, "input_modality": "text", "derived_from_text": True,
            "is_audio_observation": False, "source_artifact": str(result_path.relative_to(ROOT)),
            "source_selector": selector,
            "source_cognitive_artifact_id": cognitive_artifact["artifact_id"] if cognitive_artifact else "",
            "producer_build": cognitive_artifact["producer_build"] if cognitive_artifact else "external-poc-adapter",
            "configuration_digest": cognitive_artifact["configuration_digest"] if cognitive_artifact else hashlib.sha256(canonical(metadata).encode()).hexdigest(),
            "status": cognitive_artifact["status"] if cognitive_artifact else str(sample.get("status", "observed-output")) if isinstance(sample, dict) else "observed-output",
        }
        validate(record)
        records.append(record)

    for poc_id, (producer, formalism) in PRODUCERS.items():
        result_path = ROOT / "poc" / poc_id / "output/results.json"
        version_path = result_path.with_name("versions-and-parameters.json")
        root_value = json.loads(result_path.read_text())
        sample = representative(root_value)
        metadata = json.loads(version_path.read_text())
        base_version_override = None
        if poc_id == "sem-01":
            base_version_override = f"epitran={metadata['epitran']}"
        elif poc_id == "dlg-02":
            base_version_override = f"dynamicsyntax={metadata['dynamicsyntax']}"
        adapt(f"annotation:{poc_id}:representative", poc_id, producer, formalism, sample, metadata,
              result_path, "$[0]" if isinstance(root_value, list) else "$",
              producer_version_override=base_version_override)

    # Split compound POC bundles into producer-specific records. A combined
    # wrapper is not evidence that each contained tool has been represented.
    time_path = ROOT / "poc/time-08/output/results.json"
    time_root = json.loads(time_path.read_text())
    temporal_versions = {
        "HeidelTime": json.loads((ROOT / "poc/time-08/legacy/heideltime/output/versions-and-parameters.json").read_text()),
        "Duckling": json.loads((ROOT / "poc/time-08/legacy/duckling/output/versions-and-parameters.json").read_text()),
    }
    external = time_root["integration"]["external_analyses"]
    for producer, wanted_id in (("HeidelTime", "heidel:en-ambiguous:0"),
                                ("Duckling", "duckling:en-ambiguous:0")):
        sample = next(row for row in external if row["id"] == wanted_id)
        version_metadata = temporal_versions[producer]
        producer_version = (f"distribution={version_metadata['heideltime']['distribution']}"
                            if producer == "HeidelTime" else
                            f"package_version={version_metadata['duckling']['package_version']}; "
                            f"source_commit={version_metadata['duckling']['source_commit']}")
        adapt(f"annotation:time-08:{producer.lower()}", "time-08", producer,
              "surface temporal normalization", sample, version_metadata, time_path,
              f"$.integration.external_analyses[id={wanted_id}]", "time-08-producer-specific",
              producer_version)

    dlg_path = ROOT / "poc/dlg-03/output/results.json"
    dlg_root = json.loads(dlg_path.read_text())
    dlg_meta = json.loads(dlg_path.with_name("versions-and-parameters.json").read_text())
    dlg_runtime = json.loads((dlg_path.parent / "runtime-artifacts.json").read_text())["artifacts"]
    for index, producer, artifact_type in ((0, "ACE_ERG", "erg-dialogue-analysis"), (1, "dynamicsyntax-python", "dynamic-syntax-dialogue-analysis")):
        sample = dlg_root[0]["analyses"][index]
        cognitive_artifact = next(row for row in dlg_runtime if row["artifact_type"] == artifact_type and row["payload_native"]["fixture_id"] == "complete")
        producer_version = (f"ERG={dlg_meta['erg']}; pydelphin={dlg_meta['pydelphin']}"
                            if index == 0 else f"dynamicsyntax={dlg_meta['dynamicsyntax']}")
        adapt(f"annotation:dlg-03:{producer.lower()}", "dlg-03", producer,
              "MRS" if index == 0 else "Dynamic Syntax/TTR", sample, dlg_meta, dlg_path,
              f"$[0].analyses[{index}]", "dlg-03-producer-specific", producer_version,
              cognitive_artifact)

    sem_path = ROOT / "poc/sem-01/output/results.json"
    sem_root = json.loads(sem_path.read_text())
    sem_meta = json.loads(sem_path.with_name("versions-and-parameters.json").read_text())
    for producer in ("Epitran", "Flite lex_lookup"):
        located = next(((row_index, analysis_index, analysis)
                        for row_index, row in enumerate(sem_root)
                        for analysis_index, analysis in enumerate(row.get("external_analyses", [row.get("external_analysis")]))
                        if analysis and analysis["producer"] == producer), None)
        if located:
            row_index, analysis_index, sample = located
            producer_version = (f"epitran={sem_meta['epitran']}" if producer == "Epitran" else
                                f"flite_commit={sem_meta['flite_commit']}")
            adapt(f"annotation:sem-01:{producer.lower().replace(' ', '-')}", "sem-01", producer,
                  "grapheme-to-phoneme", sample, sem_meta, sem_path,
                  f"$[{row_index}].external_analyses[{analysis_index}]", "sem-01-producer-specific",
                  producer_version)

    span_type = pa.struct([("coordinate_system", pa.string()), ("start", pa.int64()),
                           ("end", pa.int64()), ("unit", pa.string())])
    schema = pa.schema([
        ("id", pa.string()), ("input_observation_id", pa.string()), ("producer", pa.string()),
        ("producer_version", pa.string()), ("parameters_json", pa.large_string()), ("model", pa.string()),
        ("formalism", pa.string()), ("annotation_type", pa.string()), ("raw_value_json", pa.large_string()),
        ("spans", pa.list_(span_type)), ("alternatives_json", pa.list_(pa.large_string())),
        ("constraints_json", pa.list_(pa.large_string())), ("score", pa.float64()),
        ("input_modality", pa.string()), ("derived_from_text", pa.bool_()),
        ("is_audio_observation", pa.bool_()), ("source_artifact", pa.string()), ("source_selector", pa.string()),
        ("source_cognitive_artifact_id", pa.string()), ("producer_build", pa.string()),
        ("configuration_digest", pa.string()), ("status", pa.string()),
    ])
    OUT.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(records, schema=schema)
    pq.write_table(table, OUT / "external-annotations.parquet", compression="zstd")
    arrow_rows = pq.read_table(OUT / "external-annotations.parquet").to_pylist()
    arrow_roundtrip = arrow_rows == records

    Message, descriptor = protobuf_classes()
    stream = bytearray()
    protobuf_roundtrip = True
    for record in records:
        message = Message()
        for key in ("id", "input_observation_id", "producer", "producer_version", "parameters_json", "model",
                    "formalism", "annotation_type", "raw_value_json", "input_modality", "source_artifact",
                    "source_selector", "source_cognitive_artifact_id", "producer_build",
                    "configuration_digest", "status"):
            setattr(message, key, record[key])
        message.derived_from_text = record["derived_from_text"]
        message.is_audio_observation = record["is_audio_observation"]
        if record["score"] is not None:
            message.score = record["score"]
        message.alternatives_json.extend(record["alternatives_json"])
        message.constraints_json.extend(record["constraints_json"])
        for value in record["spans"]:
            span = message.spans.add()
            for key, item in value.items():
                setattr(span, key, item)
        encoded = message.SerializeToString(deterministic=True)
        decoded = Message.FromString(encoded)
        protobuf_roundtrip &= decoded.id == record["id"] and decoded.raw_value_json == record["raw_value_json"]
        protobuf_roundtrip &= decoded.source_selector == record["source_selector"]
        protobuf_roundtrip &= decoded.HasField("score") == (record["score"] is not None)
        stream.extend(struct.pack(">I", len(encoded)))
        stream.extend(encoded)
    (OUT / "external-annotations.pb").write_bytes(stream)
    (OUT / "descriptor.pb").write_bytes(descriptor.SerializeToString())
    producer_specific_required = {"HeidelTime", "Duckling", "ACE_ERG", "dynamicsyntax-python",
                                  "Epitran", "Flite lex_lookup"}
    producer_names = {row["producer"] for row in records}
    producer_specific_coverage = [
        {"producer": producer, "covered": producer in producer_names,
         "record_ids": [row["id"] for row in records if row["producer"] == producer],
         "versions": sorted({row["producer_version"] for row in records if row["producer"] == producer})}
        for producer in sorted(producer_specific_required)]
    proto_source = (P / "external_annotation.proto").read_text()
    proto_descriptor_in_sync = all(f" {field.name} = {field.number};" in proto_source
                                   for field in descriptor.message_type[1].field)
    assert arrow_roundtrip and protobuf_roundtrip and all(not row["is_audio_observation"] for row in records)
    assert all(row["covered"] and all(version != "not_reported_by_source" for version in row["versions"])
               for row in producer_specific_coverage) and proto_descriptor_in_sync

    manifest = [{k: v for k, v in record.items() if k != "raw_value_json"} |
                {"raw_value_sha256": hashlib.sha256(record["raw_value_json"].encode()).hexdigest()}
                for record in records]
    (OUT / "results.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    summary = {
        "annotation_count": len(records), "producer_count": len({r["producer"] for r in records}),
        "annotations_with_spans": sum(bool(r["spans"]) for r in records),
        "annotations_with_alternatives": sum(bool(r["alternatives_json"]) for r in records),
        "annotations_with_constraints": sum(bool(r["constraints_json"]) for r in records),
        "annotations_with_native_score": sum(r["score"] is not None for r in records),
        "text_derived_marked_not_audio_count": sum(r["derived_from_text"] and not r["is_audio_observation"] for r in records),
        "producer_specific_coverage": producer_specific_coverage,
        "unavailable_analyzer_outputs": [{"producer": "DyLan Java", "reason": "grammar initialization fails; DLG-02 records a probe failure, not an analysis"}],
        "proto_source_dynamic_descriptor_in_sync": proto_descriptor_in_sync,
        "actual_cognitive_artifact_ref_count": sum(bool(r["source_cognitive_artifact_id"]) for r in records),
        "future_poc_rerun_required": False,
        "arrow_roundtrip": arrow_roundtrip, "protobuf_roundtrip": protobuf_roundtrip,
        "verdict": "GO_CURRENT_PRODUCERS_STRICT_CONTRACT_WITH_CAUSAL_REFS",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "pyarrow": importlib.metadata.version("pyarrow"),
        "protobuf": importlib.metadata.version("protobuf"), "schema": "seman2.graph.v1.ExternalAnnotation",
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"GRAPH-02: {len(records)} attributed annotations/{summary['producer_count']} producers; Arrow+Protobuf GO")


if __name__ == "__main__":
    main()
