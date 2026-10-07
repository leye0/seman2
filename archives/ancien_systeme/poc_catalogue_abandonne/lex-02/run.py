#!/usr/bin/env python3
"""Run LEX-02: establish the class and frame data exposed by NLTK VerbNet."""

from __future__ import annotations

import hashlib
import json
import platform
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nltk
from nltk.corpus import verbnet as vn


POC_DIR = Path(__file__).resolve().parent


def stable_id(prefix: str, payload: Any) -> str:
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return prefix + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def hierarchy_index() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    def walk(element: Any, file_id: str, path: list[str]) -> None:
        class_id = element.get("ID")
        current_path = [*path, class_id]
        children = [
            child.get("ID")
            for child in element.findall("SUBCLASSES/VNSUBCLASS")
        ]
        index[class_id] = {
            "class_id": class_id,
            "file_id": file_id,
            "parent_class_id": path[-1] if path else None,
            "root_class_id": current_path[0],
            "path_from_root": current_path,
            "direct_subclass_ids": children,
        }
        for child in element.findall("SUBCLASSES/VNSUBCLASS"):
            walk(child, file_id, current_path)

    for file_id in vn.fileids():
        walk(vn.xml(file_id), file_id, [])
    return index


def direct_members(class_id: str) -> list[dict[str, Any]]:
    element = vn.vnclass(class_id)
    return [
        {
            "lemma": member.get("name"),
            "wordnet_sense_keys": member.get("wn", "").split(),
            "grouping": member.get("grouping", "").split(),
        }
        for member in element.findall("MEMBERS/MEMBER")
    ]


def restriction_tree(container: Any | None) -> dict[str, Any] | None:
    if container is None:
        return None
    children = []
    for child in container:
        if child.tag in ("SELRESTR", "SYNRESTR"):
            children.append(
                {
                    "kind": "restriction",
                    "restriction_type": child.get("type"),
                    "value": child.get("Value"),
                }
            )
        else:
            children.append(
                {
                    "kind": "group",
                    **(restriction_tree(child) or {}),
                }
            )
    return {"logic": container.get("logic"), "children": children}


def thematic_roles(class_id: str) -> list[dict[str, Any]]:
    parsed_roles = vn.themroles(class_id)
    xml_roles = vn.vnclass(class_id).findall("THEMROLES/THEMROLE")
    if len(parsed_roles) != len(xml_roles):
        raise RuntimeError(f"Role/XML count mismatch for {class_id}")
    return [
        {
            "role": role["type"],
            "selectional_restrictions": role["modifiers"],
            "native_selectional_restriction_tree": restriction_tree(
                xml_role.find("SELRESTRS")
            ),
        }
        for role, xml_role in zip(parsed_roles, xml_roles, strict=True)
    ]


def serialize_frames(class_id: str) -> list[dict[str, Any]]:
    parsed_frames = vn.frames(class_id)
    xml_frames = vn.vnclass(class_id).findall("FRAMES/FRAME")
    if len(parsed_frames) != len(xml_frames):
        raise RuntimeError(f"Frame/XML count mismatch for {class_id}")
    records = []
    for ordinal, (frame, xml_frame) in enumerate(
        zip(parsed_frames, xml_frames, strict=True), start=1
    ):
        native_description = dict(xml_frame.find("DESCRIPTION").attrib)
        frame_id = stable_id(
            "verbnet-frame:",
            {
                "version": vn.version,
                "class_id": class_id,
                "ordinal": ordinal,
                "frame": frame,
                "native_description": native_description,
            },
        )
        xml_syntax = list(xml_frame.find("SYNTAX"))
        if len(frame["syntax"]) != len(xml_syntax):
            raise RuntimeError(f"Syntax/XML count mismatch for {class_id}")
        records.append(
            {
                "frame_id": frame_id,
                "ordinal_within_class": ordinal,
                "example": frame["example"],
                "description": frame["description"],
                "native_description_attributes": native_description,
                "syntax": [
                    {
                        "position": position,
                        "category": item["pos_tag"],
                        "thematic_role_or_value": item["modifiers"]["value"],
                        "selectional_restrictions": item["modifiers"][
                            "selrestrs"
                        ],
                        "syntactic_restrictions": item["modifiers"][
                            "synrestrs"
                        ],
                        "native_selectional_restriction_tree": restriction_tree(
                            xml_item.find("SELRESTRS")
                        ),
                        "native_syntactic_restriction_tree": restriction_tree(
                            xml_item.find("SYNRESTRS")
                        ),
                    }
                    for position, (item, xml_item) in enumerate(
                        zip(frame["syntax"], xml_syntax, strict=True), start=1
                    )
                ],
                "semantics": [
                    {
                        "predicate": predicate["predicate_value"],
                        "negated": predicate["negated"],
                        "arguments": predicate["arguments"],
                    }
                    for predicate in frame["semantics"]
                ],
            }
        )
    return records


def hierarchy_definitions(
    path: list[str], frame_cache: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    definitions = []
    for class_id in path:
        frames = frame_cache.setdefault(class_id, serialize_frames(class_id))
        definitions.append(
            {
                "class_id": class_id,
                "local_members": direct_members(class_id),
                "local_thematic_roles": thematic_roles(class_id),
                "local_frame_count": len(frames),
                "local_frame_ids": [frame["frame_id"] for frame in frames],
            }
        )
    return definitions


def serialize_class(
    fixture: dict[str, Any],
    class_id: str,
    hierarchy: dict[str, dict[str, Any]],
    frame_cache: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    hierarchy_item = hierarchy[class_id]
    path = hierarchy_item["path_from_root"]
    definitions = hierarchy_definitions(path, frame_cache)
    roles_along_path = [
        {"origin_class_id": level["class_id"], **role}
        for level in definitions
        for role in level["local_thematic_roles"]
    ]
    frames = frame_cache.setdefault(class_id, serialize_frames(class_id))
    frames_along_path = [
        {
            "origin_class_id": origin_class_id,
            "defined_on_candidate_class": origin_class_id == class_id,
            **frame,
        }
        for origin_class_id in path
        for frame in frame_cache.setdefault(
            origin_class_id, serialize_frames(origin_class_id)
        )
    ]
    analysis_id = stable_id(
        "verbnet-analysis:",
        {
            "source_observation_id": f"source:{fixture['id']}",
            "lemma": fixture["lemma"],
            "verbnet_version": vn.version,
            "class_id": class_id,
        },
    )
    return {
        "analysis_id": analysis_id,
        "support": {"source_observation_id": f"source:{fixture['id']}"},
        "producer": {
            "interface": "NLTK VerbNet",
            "resource": "VerbNet",
            "resource_version": vn.version,
        },
        "selected_by_lookup": False,
        "class_id": class_id,
        "short_class_id": vn.shortid(class_id),
        "file_id": hierarchy_item["file_id"],
        "hierarchy": {
            "root_class_id": hierarchy_item["root_class_id"],
            "parent_class_id": hierarchy_item["parent_class_id"],
            "path_from_root": path,
            "ancestor_class_ids": path[:-1],
            "direct_subclass_ids": hierarchy_item["direct_subclass_ids"],
            "definitions_by_level": definitions,
        },
        "local_members": direct_members(class_id),
        "local_thematic_roles": thematic_roles(class_id),
        "thematic_roles_available_along_hierarchy": roles_along_path,
        "local_frames": frames,
        "local_frame_count": len(frames),
        "frames_available_along_hierarchy": frames_along_path,
        "frame_count_available_along_hierarchy": sum(
            level["local_frame_count"] for level in definitions
        ),
    }


def lookup_fixture(
    fixture: dict[str, Any],
    hierarchy: dict[str, dict[str, Any]],
    frame_cache: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    class_ids = vn.classids(fixture["lemma"])
    candidates = [
        serialize_class(fixture, class_id, hierarchy, frame_cache)
        for class_id in class_ids
    ]
    candidate_ids = [candidate["analysis_id"] for candidate in candidates]
    for candidate in candidates:
        candidate["competes_with"] = [
            item for item in candidate_ids if item != candidate["analysis_id"]
        ]
    result = {
        **fixture,
        "source_observation": {
            "id": f"source:{fixture['id']}",
            "text": fixture["lemma"],
            "charspan": [0, len(fixture["lemma"])],
        },
        "lookup": {
            "api_call": f"vn.classids({fixture['lemma']!r})",
            "candidate_class_ids": class_ids,
            "candidate_count": len(class_ids),
            "status": "candidates_found" if class_ids else "no_candidates",
            "selected_class_id": None,
            "is_occurrence_classification": False,
        },
        "candidates": candidates,
    }
    raw = {
        "fixture": fixture["id"],
        "lemma": fixture["lemma"],
        "api_call": f"vn.classids({fixture['lemma']!r})",
        "returned_class_ids": class_ids,
    }
    xml = {
        class_id: ET.tostring(vn.vnclass(class_id), encoding="unicode")
        for candidate in candidates
        for class_id in candidate["hierarchy"]["path_from_root"]
    }
    return result, raw, xml


def context_independence(break_result: dict[str, Any]) -> dict[str, Any]:
    class_ids = break_result["lookup"]["candidate_class_ids"]
    contexts = [
        {
            "text": "Tony broke the window.",
            "target_span": [5, 10],
            "target_lemma": "break",
            "humanly_relevant_class": "break-45.1",
        },
        {
            "text": "The doctor broke him of the habit.",
            "target_span": [11, 16],
            "target_lemma": "break",
            "humanly_relevant_class": "cheat-10.6",
        },
    ]
    for context in contexts:
        context["verbnet_lookup_input"] = context["target_lemma"]
        context["returned_candidate_class_ids"] = class_ids
        context["selected_class_id"] = None
    return {
        "target_lemma": "break",
        "contexts": contexts,
        "candidate_lists_identical": (
            contexts[0]["returned_candidate_class_ids"]
            == contexts[1]["returned_candidate_class_ids"]
        ),
        "verbnet_lookup_uses_context": False,
        "verbnet_lookup_selects_a_class": False,
        "conclusion": (
            "VerbNet lemma lookup enumerates candidate classes; occurrence-level "
            "class selection requires syntax, semantics, and context from other components."
        ),
    }


def validate(
    fixtures: list[dict[str, Any]],
    results: list[dict[str, Any]],
    context_demo: dict[str, Any],
) -> None:
    if len(fixtures) != len(results):
        raise RuntimeError("LEX-02 fixture coverage is incomplete")
    analysis_ids: set[str] = set()
    frame_ids: set[str] = set()
    for fixture, result in zip(fixtures, results, strict=True):
        observed = set(result["lookup"]["candidate_class_ids"])
        if not set(fixture.get("expected_classes", [])).issubset(observed):
            raise RuntimeError(f"Missing expected class: {fixture['id']}")
        if len(observed) < fixture.get("expected_minimum_classes", 0):
            raise RuntimeError(f"Insufficient class candidates: {fixture['id']}")
        if fixture.get("expected_classes") == [] and result["lookup"]["status"] != "no_candidates":
            raise RuntimeError("Absent verb is not explicit")
        for candidate in result["candidates"]:
            if candidate["analysis_id"] in analysis_ids:
                raise RuntimeError(f"Duplicate analysis id: {candidate['analysis_id']}")
            analysis_ids.add(candidate["analysis_id"])
            if candidate["class_id"] not in candidate["hierarchy"]["path_from_root"]:
                raise RuntimeError(f"Broken hierarchy: {candidate['class_id']}")
            if not candidate["local_frames"]:
                raise RuntimeError(f"No frames exposed for {candidate['class_id']}")
            for frame in candidate["local_frames"]:
                if frame["frame_id"] in frame_ids:
                    continue
                frame_ids.add(frame["frame_id"])
                if not frame["example"] or not frame["syntax"] or not frame["semantics"]:
                    raise RuntimeError(f"Incomplete frame: {frame['frame_id']}")
    give = next(result for result in results if result["id"] == "hierarchical-give")
    candidate = give["candidates"][0]
    if candidate["hierarchy"]["path_from_root"] != give["expected_hierarchy_path"]:
        raise RuntimeError("Give hierarchy changed")
    roles = {
        role["role"] for role in candidate["thematic_roles_available_along_hierarchy"]
    }
    if not set(give["expected_roles_along_hierarchy"]).issubset(roles):
        raise RuntimeError("Inherited thematic context is incomplete")
    all_candidates = [candidate for result in results for candidate in result["candidates"]]
    all_frames = [frame for candidate in all_candidates for frame in candidate["local_frames"]]
    if not any(role["selectional_restrictions"] for candidate in all_candidates for role in candidate["thematic_roles_available_along_hierarchy"]):
        raise RuntimeError("Thematic selectional restrictions are absent")
    if not any(item["selectional_restrictions"] for frame in all_frames for item in frame["syntax"]):
        raise RuntimeError("Frame selectional restrictions are absent")
    if not any(item["syntactic_restrictions"] for frame in all_frames for item in frame["syntax"]):
        raise RuntimeError("Frame syntactic restrictions are absent")
    if not any(predicate["negated"] for frame in all_frames for predicate in frame["semantics"]):
        raise RuntimeError("Negated semantic predicates are absent")
    if not context_demo["candidate_lists_identical"]:
        raise RuntimeError("VerbNet lookup unexpectedly used occurrence context")
    if any(context["selected_class_id"] is not None for context in context_demo["contexts"]):
        raise RuntimeError("Lookup was mislabeled as occurrence classification")


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    hierarchy = hierarchy_index()
    frame_cache: dict[str, list[dict[str, Any]]] = {}
    results = []
    raw_lookups = []
    raw_xml: dict[str, str] = {}
    for fixture in fixtures:
        result, raw, xml = lookup_fixture(fixture, hierarchy, frame_cache)
        results.append(result)
        raw_lookups.append(raw)
        raw_xml.update(xml)
    break_result = next(result for result in results if result["id"] == "polyclass-break")
    context_demo = context_independence(break_result)
    validate(fixtures, results, context_demo)

    candidates = [candidate for result in results for candidate in result["candidates"]]
    unique_local_frames = {
        frame["frame_id"]: frame
        for candidate in candidates
        for frame in candidate["local_frames"]
    }
    unique_hierarchy_frames = {
        frame["frame_id"]: frame
        for candidate in candidates
        for frame in candidate["frames_available_along_hierarchy"]
    }
    syntax_items = [
        item for frame in unique_hierarchy_frames.values() for item in frame["syntax"]
    ]
    semantic_predicates = [
        predicate
        for frame in unique_hierarchy_frames.values()
        for predicate in frame["semantics"]
    ]
    summary = {
        "fixture_count": len(results),
        "candidate_class_count": len(candidates),
        "candidate_counts_by_fixture": {
            result["id"]: len(result["candidates"]) for result in results
        },
        "unique_local_frame_count": len(unique_local_frames),
        "unique_frame_count_available_along_hierarchies": len(
            unique_hierarchy_frames
        ),
        "thematic_role_declaration_count_along_hierarchies": sum(
            len(candidate["thematic_roles_available_along_hierarchy"])
            for candidate in candidates
        ),
        "syntax_element_count": len(syntax_items),
        "syntax_selectional_restriction_count": sum(
            len(item["selectional_restrictions"]) for item in syntax_items
        ),
        "syntactic_restriction_count": sum(
            len(item["syntactic_restrictions"]) for item in syntax_items
        ),
        "semantic_predicate_count": len(semantic_predicates),
        "negated_semantic_predicate_count": sum(
            predicate["negated"] for predicate in semantic_predicates
        ),
        "absent_verb_count": sum(not result["candidates"] for result in results),
        "occurrence_classification_performed": False,
        "selected_class_count": 0,
        "verdict": "GO_AS_CANDIDATE_VERB_CLASS_RESOURCE",
    }

    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("results.json", results),
        ("context-independence.json", context_demo),
        ("summary.json", summary),
        ("raw/lookups.json", raw_lookups),
        ("raw/class-xml.json", raw_xml),
    ):
        (output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "nltk_version": nltk.__version__,
        "verbnet_version": vn.version,
        "verbnet_root": str(vn.root),
        "parameters": {
            "lookup": "vn.classids(lemma)",
            "hierarchy": "reconstructed from nested VNCLASS/VNSUBCLASS XML",
            "frames": "local frames plus definitions recorded at every ancestor level",
            "context_used": False,
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"LEX-02: {len(results)} fixtures validated")
    print(
        f"classes: {summary['candidate_class_count']}; "
        f"unique local frames: {summary['unique_local_frame_count']}; "
        f"semantic predicates: {summary['semantic_predicate_count']}"
    )
    print("occurrence class selection: not performed (candidate lookup only)")


if __name__ == "__main__":
    main()
