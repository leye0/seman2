#!/usr/bin/env python3
"""Run LEX-04: inspect the structures exposed by NLTK FrameNet 1.7."""

from __future__ import annotations

import hashlib
import json
import platform
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nltk
from nltk.corpus import framenet as fn


POC_DIR = Path(__file__).resolve().parent
FRAMENET_VERSION = "1.7"
ADAPTER_VERSION = "1"
SCHEMA_VERSION = "seman2.lexical-framenet-poc.v1"


def stable_id(prefix: str, payload: Any) -> str:
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return prefix + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def primitive_attributes(item: Any) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(item).items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }


def named_reference(item: Any) -> dict[str, Any] | None:
    if item is None:
        return None
    if isinstance(item, (str, int)):
        return {"id": None, "name": str(item)}
    return {"id": item.get("ID"), "name": item.get("name")}


def resource_id(kind: str, native_id: int) -> str:
    return stable_id(
        f"framenet-{kind}:",
        {"resource_version": FRAMENET_VERSION, "native_id": native_id},
    )


def serialize_fe(fe: Any) -> dict[str, Any]:
    return {
        "resource_id": resource_id("frame-element", fe.ID),
        "frame_element_id": fe.ID,
        "name": fe.name,
        "abbreviation": fe.get("abbrev"),
        "core_type": fe.coreType,
        "definition": fe.definition,
        "semantic_type": named_reference(fe.get("semType")),
        "requires_frame_element": named_reference(fe.get("requiresFE")),
        "excludes_frame_element": named_reference(fe.get("excludesFE")),
    }


def sentence_counts(lu: Any) -> dict[str, int]:
    counts = lu.get("sentenceCount", {})
    return {key: int(value) for key, value in dict(counts).items()}


def serialize_lu_summary(lu: Any) -> dict[str, Any]:
    incorporated = lu.get("incorporatedFE")
    return {
        "resource_id": resource_id("lexical-unit", lu.ID),
        "lexical_unit_id": lu.ID,
        "name": lu.name,
        "part_of_speech": lu.POS,
        "status": lu.status,
        "definition": lu.definition,
        "sentence_counts": sentence_counts(lu),
        "incorporated_frame_element": named_reference(incorporated),
        "lexemes": [primitive_attributes(lexeme) for lexeme in lu.lexemes],
        "semantic_types": [named_reference(item) for item in lu.semTypes],
    }


def serialize_relation(relation: Any) -> dict[str, Any]:
    return {
        "resource_id": resource_id("frame-relation", relation.ID),
        "relation_id": relation.ID,
        "relation_type": relation.type.name,
        "super_frame": {
            "id": relation.superFrame.ID,
            "name": relation.superFrameName,
        },
        "sub_frame": {
            "id": relation.subFrame.ID,
            "name": relation.subFrameName,
        },
        "frame_element_mappings": [
            {
                "relation_id": mapping.ID,
                "super_frame_element": {
                    "id": mapping.superFE.ID,
                    "name": mapping.superFEName,
                },
                "sub_frame_element": {
                    "id": mapping.subFE.ID,
                    "name": mapping.subFEName,
                },
            }
            for mapping in relation.feRelations
        ],
    }


def serialize_frame(frame: Any, resource_sha256: str) -> dict[str, Any]:
    return {
        "resource_id": resource_id("frame", frame.ID),
        "frame_id": frame.ID,
        "name": frame.name,
        "definition": frame.definition,
        "semantic_types": [named_reference(item) for item in frame.semTypes],
        "frame_elements": [
            serialize_fe(fe) for fe in sorted(frame.FE.values(), key=lambda x: x.ID)
        ],
        "frame_element_core_sets": [
            [named_reference(fe) for fe in sorted(core_set, key=lambda x: x.ID)]
            for core_set in frame.FEcoreSets
        ],
        "lexical_units": [
            serialize_lu_summary(lu)
            for lu in sorted(frame.lexUnit.values(), key=lambda x: x.ID)
        ],
        "frame_relations": [
            serialize_relation(relation)
            for relation in sorted(frame.frameRelations, key=lambda x: x.ID)
        ],
        "producer": {
            "interface": "NLTK FramenetCorpusReader",
            "resource": "Berkeley FrameNet",
            "resource_version": FRAMENET_VERSION,
            "resource_sha256": resource_sha256,
            "adapter_version": ADAPTER_VERSION,
            "schema_version": SCHEMA_VERSION,
        },
    }


def parse_valences(xml_path: Path) -> dict[str, Any]:
    root = ET.parse(xml_path).getroot()
    valences = next(
        (child for child in root if local_name(child.tag) == "valences"), None
    )
    if valences is None:
        return {"frame_element_realizations": [], "frame_element_group_realizations": []}

    def realization(element: ET.Element) -> dict[str, Any]:
        frame_elements = [
            child.attrib["name"]
            for child in element
            if local_name(child.tag) == "FE"
        ]
        patterns = []
        for pattern in element:
            if local_name(pattern.tag) != "pattern":
                continue
            units = [
                {
                    "frame_element": child.attrib.get("FE"),
                    "grammatical_function": child.attrib.get("GF") or None,
                    "phrase_type_or_null_instantiation": child.attrib.get("PT"),
                }
                for child in pattern
                if local_name(child.tag) == "valenceUnit"
            ]
            annotation_set_ids = [
                int(child.attrib["ID"])
                for child in pattern
                if local_name(child.tag) == "annoSet"
            ]
            patterns.append(
                {
                    "total": int(pattern.attrib["total"]),
                    "valence_units": units,
                    "annotation_set_ids": annotation_set_ids,
                }
            )
        return {
            "total": int(element.attrib["total"]),
            "frame_elements": frame_elements,
            "patterns": patterns,
        }

    return {
        "frame_element_realizations": [
            realization(element)
            for element in valences
            if local_name(element.tag) == "FERealization"
        ],
        "frame_element_group_realizations": [
            realization(element)
            for element in valences
            if local_name(element.tag) == "FEGroupRealization"
        ],
    }


def label_span(label: Any, text: str) -> dict[str, Any]:
    if "start" not in label:
        return {
            "start": None,
            "end_exclusive": None,
            "text": None,
            "null_instantiation_type": label.get("itype"),
        }
    start = int(label.start)
    end_exclusive = int(label.end) + 1
    return {
        "start": start,
        "end_exclusive": end_exclusive,
        "text": text[start:end_exclusive],
        "null_instantiation_type": None,
    }


def serialize_layer(layer: Any, text: str) -> dict[str, Any]:
    return {
        "name": layer.name,
        "rank": layer.rank,
        "labels": [
            {
                "name": label.name,
                "frame_element_id": label.get("feID"),
                "annotator": label.get("cBy"),
                **label_span(label, text),
            }
            for label in layer.label
        ],
    }


def annotation_layer(annotation: Any, name: str) -> Any:
    return next(layer for layer in annotation.layer if layer.name == name)


def aligned_frame_elements(annotation: Any, text: str) -> list[dict[str, Any]]:
    fe_layer = annotation_layer(annotation, "FE")
    gf_labels = annotation_layer(annotation, "GF").label
    pt_labels = annotation_layer(annotation, "PT").label

    def aligned_value(labels: Any, fe_label: Any) -> str | None:
        if "start" not in fe_label:
            return None
        match = next(
            (
                label
                for label in labels
                if label.get("start") == fe_label.get("start")
                and label.get("end") == fe_label.get("end")
            ),
            None,
        )
        return match.name if match is not None else None

    return [
        {
            "name": label.name,
            "frame_element_id": label.get("feID"),
            **label_span(label, text),
            "grammatical_function": aligned_value(gf_labels, label),
            "phrase_type": aligned_value(pt_labels, label),
        }
        for label in fe_layer.label
    ]


def find_exemplar(lu: Any, sentence_id: int, annotation_set_id: int) -> tuple[Any, Any]:
    sentence = next(
        (item for item in lu.exemplars if item.ID == sentence_id), None
    )
    if sentence is None:
        raise RuntimeError(f"Unknown exemplar sentence {sentence_id} for {lu.name}")
    annotation = next(
        (item for item in sentence.annotationSet if item.ID == annotation_set_id), None
    )
    if annotation is None:
        raise RuntimeError(
            f"Unknown annotation set {annotation_set_id} in sentence {sentence_id}"
        )
    return sentence, annotation


def serialize_annotation(fixture: dict[str, Any], lu: Any) -> dict[str, Any]:
    sentence, annotation = find_exemplar(
        lu, fixture["sentence_id"], fixture["annotation_set_id"]
    )
    layers = [serialize_layer(layer, sentence.text) for layer in annotation.layer]
    target_labels = annotation_layer(annotation, "Target").label
    return {
        "analysis_id": stable_id(
            "framenet-corpus-annotation:",
            {
                "resource_version": FRAMENET_VERSION,
                "sentence_id": sentence.ID,
                "annotation_set_id": annotation.ID,
            },
        ),
        "analysis_type": "framenet_existing_exemplar_annotation",
        "sentence_id": sentence.ID,
        "annotation_set_id": annotation.ID,
        "annotation_status": annotation.status,
        "text": sentence.text,
        "target": [label_span(label, sentence.text) for label in target_labels],
        "frame_elements": aligned_frame_elements(annotation, sentence.text),
        "layers": layers,
        "offset_convention": (
            "source XML end offsets are inclusive; end_exclusive is normalized "
            "to Python half-open character spans"
        ),
        "frame_assignment_source": "existing FrameNet 1.7 corpus annotation",
        "automatically_detected_in_new_text": False,
        "score": None,
        "score_status": "not provided for manual FrameNet exemplar annotations",
    }


def valence_patterns_for_annotation(
    valences: dict[str, Any], annotation_set_id: int
) -> list[dict[str, Any]]:
    matches = []
    for kind in ("frame_element_realizations", "frame_element_group_realizations"):
        for realization in valences[kind]:
            for pattern in realization["patterns"]:
                if annotation_set_id in pattern["annotation_set_ids"]:
                    matches.append(
                        {
                            "realization_kind": kind,
                            "frame_elements": realization["frame_elements"],
                            **pattern,
                        }
                    )
    return matches


def validate(fixtures: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
    if len(fixtures) != len(results):
        raise RuntimeError("LEX-04 fixture coverage is incomplete")
    ids: set[str] = set()
    for fixture, result in zip(fixtures, results, strict=True):
        frame = result["frame"]
        annotation = result["exemplar_annotation"]
        if annotation["analysis_id"] in ids:
            raise RuntimeError(f"Duplicate analysis ID: {fixture['id']}")
        ids.add(annotation["analysis_id"])
        if frame["frame_id"] != fixture["frame_id"]:
            raise RuntimeError(f"Wrong frame: {fixture['id']}")
        if len(frame["lexical_units"]) < fixture["expected_min_lexical_units"]:
            raise RuntimeError(f"Too few lexical units: {fixture['id']}")
        target = " ".join(item["text"] for item in annotation["target"])
        if target != fixture["expected_target"]:
            raise RuntimeError(f"Wrong target text: {fixture['id']}: {target!r}")
        fe_names = {item["name"] for item in annotation["frame_elements"]}
        if not set(fixture["expected_frame_elements"]).issubset(fe_names):
            raise RuntimeError(f"Missing annotated FEs: {fixture['id']}")
        relation_types = {
            item["relation_type"] for item in frame["frame_relations"]
        }
        if not set(fixture["expected_relation_types"]).issubset(relation_types):
            raise RuntimeError(f"Missing frame relation type: {fixture['id']}")
        parent = fixture.get("expected_inheritance_parent")
        if parent and not any(
            item["relation_type"] == "Inheritance"
            and item["super_frame"]["name"] == parent
            and item["sub_frame"]["name"] == fixture["frame_name"]
            for item in frame["frame_relations"]
        ):
            raise RuntimeError(f"Missing inheritance parent: {fixture['id']}")
        if len(frame["frame_element_core_sets"]) < fixture.get(
            "expected_core_set_count", 0
        ):
            raise RuntimeError(f"Missing FE core set: {fixture['id']}")
        null_types = {
            item["null_instantiation_type"]
            for item in annotation["frame_elements"]
            if item["null_instantiation_type"] is not None
        }
        expected_null = fixture["expected_null_instantiation"]
        if bool(null_types) != expected_null:
            raise RuntimeError(f"Wrong null-instantiation status: {fixture['id']}")
        if fixture.get("expected_null_type") not in null_types and expected_null:
            raise RuntimeError(f"Missing null-instantiation type: {fixture['id']}")
        if not result["matching_valence_patterns"]:
            raise RuntimeError(f"Annotation absent from valence tables: {fixture['id']}")
        if annotation["automatically_detected_in_new_text"]:
            raise RuntimeError("A corpus annotation was mislabeled as automatic detection")


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    corpus_root = Path(str(fn.root))
    archive_path = Path(str(nltk.data.find("corpora/framenet_v17.zip")))
    archive_sha256 = sha256_file(archive_path)

    frame_cache: dict[int, dict[str, Any]] = {}
    valence_cache: dict[int, dict[str, Any]] = {}
    results = []
    raw_frames: dict[str, str] = {}
    raw_lexical_units: dict[str, str] = {}
    for fixture in fixtures:
        native_frame = fn.frame(fixture["frame_id"])
        if native_frame.name != fixture["frame_name"]:
            raise RuntimeError(f"Frame ID/name mismatch: {fixture['id']}")
        frame = frame_cache.setdefault(
            native_frame.ID, serialize_frame(native_frame, archive_sha256)
        )
        lu = fn.lu(fixture["lexical_unit_id"])
        if lu.name != fixture["lexical_unit_name"] or lu.frame.ID != native_frame.ID:
            raise RuntimeError(f"LU/frame mismatch: {fixture['id']}")
        lu_xml_path = corpus_root / "lu" / f"lu{lu.ID}.xml"
        valences = valence_cache.setdefault(lu.ID, parse_valences(lu_xml_path))
        annotation = serialize_annotation(fixture, lu)
        results.append(
            {
                **fixture,
                "frame": frame,
                "selected_lexical_unit": serialize_lu_summary(lu),
                "selected_lexical_unit_exemplar_count": len(lu.exemplars),
                "valence_source": {
                    "status": "available in FrameNet LU XML but skipped by NLTK 3.10.3",
                    "reader_source_note": (
                        "FramenetCorpusReader._handle_lexunit_elt explicitly continues "
                        "past the valences element"
                    ),
                    "path_within_resource": f"lu/lu{lu.ID}.xml",
                },
                "valences": valences,
                "exemplar_annotation": annotation,
                "matching_valence_patterns": valence_patterns_for_annotation(
                    valences, annotation["annotation_set_id"]
                ),
            }
        )
        raw_frames[native_frame.name] = (
            corpus_root / "frame" / f"{native_frame.name}.xml"
        ).read_text(encoding="utf-8")
        raw_lexical_units[str(lu.ID)] = lu_xml_path.read_text(encoding="utf-8")

    validate(fixtures, results)

    all_frames = list(fn.frames())
    all_lus = list(fn.lus())
    all_relations = list(fn.frame_relations())
    relation_counts = Counter(item.type.name for item in all_relations)
    frame_element_core_type_counts = Counter(
        fe.coreType for frame in all_frames for fe in frame.FE.values()
    )
    lu_pos_counts = Counter(lu.POS for lu in all_lus)
    lu_status_counts = Counter(lu.status for lu in all_lus)
    annotated_exemplar_count_from_lu_metadata = sum(
        sentence_counts(lu).get("annotated", 0) for lu in all_lus
    )
    selected_annotations = [result["exemplar_annotation"] for result in results]
    selected_fes = [
        fe for annotation in selected_annotations for fe in annotation["frame_elements"]
    ]
    unique_selected_lus = {fixture["lexical_unit_id"] for fixture in fixtures}
    summary = {
        "fixture_count": len(fixtures),
        "selected_frame_count": len(frame_cache),
        "selected_lexical_unit_count": len(unique_selected_lus),
        "selected_exemplar_annotation_count": len(selected_annotations),
        "selected_frame_element_annotation_count": len(selected_fes),
        "selected_null_instantiation_count": sum(
            fe["null_instantiation_type"] is not None for fe in selected_fes
        ),
        "corpus_frame_count": len(all_frames),
        "corpus_lexical_unit_count": len(all_lus),
        "corpus_frame_element_count": sum(len(frame.FE) for frame in all_frames),
        "corpus_frame_relation_count": len(all_relations),
        "corpus_frame_relation_type_counts": dict(sorted(relation_counts.items())),
        "corpus_annotated_exemplar_count_from_lu_metadata": (
            annotated_exemplar_count_from_lu_metadata
        ),
        "full_text_document_count": len(fn.docs_metadata()),
        "new_sentence_frame_detection_performed": False,
        "verdict": "GO_AS_LEXICAL_AND_ANNOTATED_CORPUS_RESOURCE_NOT_AS_FRAME_DETECTOR",
    }
    inventory = {
        "frame_element_core_type_counts": dict(
            sorted(frame_element_core_type_counts.items())
        ),
        "lexical_unit_part_of_speech_counts": dict(sorted(lu_pos_counts.items())),
        "lexical_unit_status_counts": dict(sorted(lu_status_counts.items())),
        "frame_relation_type_counts": dict(sorted(relation_counts.items())),
        "selected_frames": [
            {
                "id": frame["frame_id"],
                "name": frame["name"],
                "lexical_unit_count": len(frame["lexical_units"]),
                "frame_element_count": len(frame["frame_elements"]),
                "relation_count": len(frame["frame_relations"]),
                "core_set_count": len(frame["frame_element_core_sets"]),
            }
            for frame in frame_cache.values()
        ],
    }
    resource_boundary = {
        "frame_lookup": {
            "input": "frame name or numeric frame ID",
            "output": (
                "stored frame definition, lexical units, frame elements, core sets, "
                "semantic types, and typed relations with FE mappings"
            ),
            "detects_a_frame_in_new_text": False,
        },
        "lexical_unit_lookup": {
            "input": "lexical-unit name pattern or numeric LU ID",
            "output": (
                "stored LU metadata and its existing lexicographic exemplar annotations"
            ),
            "selects_a_frame_for_an_occurrence": False,
        },
        "corpus_annotation_lookup": {
            "input": "existing FrameNet sentence and annotation-set IDs",
            "output": (
                "the manually assigned frame target plus FE, GF, PT and null-"
                "instantiation labels"
            ),
            "assignment_source": "FrameNet corpus annotation",
        },
        "valence": {
            "nltk_api_support": False,
            "resource_xml_support": True,
            "adapter_operation": (
                "parse FERealization and FEGroupRealization from the installed LU XML"
            ),
        },
        "new_sentence": {
            "automatic_frame_detection_available_from_this_resource": False,
            "required_additional_component": (
                "a frame-semantic parser or project adapter for target identification, "
                "frame disambiguation, and frame-element labeling"
            ),
        },
    }

    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("results.json", results),
        ("summary.json", summary),
        ("corpus-inventory.json", inventory),
        ("resource-vs-detection.json", resource_boundary),
        ("raw/frame-xml.json", raw_frames),
        ("raw/lexical-unit-xml.json", raw_lexical_units),
    ):
        (output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "nltk_version": nltk.__version__,
        "framenet_version": FRAMENET_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "framenet_root": str(fn.root),
        "resource_archive": {
            "path": str(archive_path),
            "sha256": archive_sha256,
        },
        "parameters": {
            "frames": "fn.frame(id), fn.frames(), and frame.frameRelations",
            "lexical_units": "fn.lu(id) and fn.lus()",
            "examples": "LU.exemplars selected by stable sentence and annotation IDs",
            "valence": "FrameNet 1.7 LU XML valences parsed because NLTK skips it",
            "offsets": "zero-based, end-exclusive in normalized output",
            "new_sentence_frame_detection": False,
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"LEX-04: {len(results)} fixtures validated")
    print(
        f"frames: {len(all_frames)}; lexical units: {len(all_lus)}; "
        f"frame relations: {len(all_relations)}"
    )
    print(
        "new sentence frame detection: not performed "
        "(lexical resource and existing corpus annotations only)"
    )


if __name__ == "__main__":
    main()
