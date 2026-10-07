#!/usr/bin/env python3
"""Run LEX-03: inspect NLTK PropBank rolesets and corpus annotations."""

from __future__ import annotations

import hashlib
import json
import platform
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nltk
from nltk import Tree
from nltk.corpus import propbank, ptb, treebank
from nltk.corpus.reader.propbank import (
    PropbankChainTreePointer,
    PropbankSplitTreePointer,
    PropbankTreePointer,
)


POC_DIR = Path(__file__).resolve().parent
PROPBANK_VERSION = "1.0"
ADAPTER_VERSION = "2"
SCHEMA_VERSION = "seman2.lexical-propbank-poc.v2"


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


def normalized_text(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.split())


def serialize_example_node(node: Any) -> dict[str, Any]:
    return {
        "element": node.tag,
        "attributes": dict(node.attrib),
        "text": normalized_text(node.text),
        "children": [serialize_example_node(child) for child in node],
    }


def serialize_roleset(
    lemma: str, roleset_id: str, resource_sha256: str
) -> dict[str, Any]:
    roleset = propbank.roleset(roleset_id)
    roles = []
    for role in roleset.findall("roles/role"):
        roles.append(
            {
                "argument_label": f"ARG{role.get('n')}",
                "number": role.get("n"),
                "function": role.get("f"),
                "description": role.get("descr"),
                "verbnet_roles": [dict(item.attrib) for item in role.findall("vnrole")],
            }
        )
    return {
        "resource_id": stable_id(
            "propbank-roleset:",
            {"resource_version": PROPBANK_VERSION, "roleset_id": roleset_id},
        ),
        "roleset_id": roleset_id,
        "analysis_type": "propbank_lexical_roleset_candidate",
        "lemma": lemma,
        "name": roleset.get("name"),
        "verbnet_class_ids": roleset.get("vncls", "").split(),
        "attributes": dict(roleset.attrib),
        "selected_by_lemma_lookup": False,
        "score": None,
        "score_status": "not provided by the lexical resource",
        "producer": {
            "interface": "NLTK PropBankCorpusReader",
            "resource": "UPenn PropBank",
            "resource_version": PROPBANK_VERSION,
            "resource_sha256": resource_sha256,
            "adapter_version": ADAPTER_VERSION,
            "schema_version": SCHEMA_VERSION,
        },
        "roles": roles,
        "examples": [
            {
                "attributes": dict(example.attrib),
                "text": normalized_text(example.findtext("text")),
                "annotations": [
                    serialize_example_node(child)
                    for child in example
                    if child.tag != "text"
                ],
            }
            for example in roleset.findall("example")
        ],
    }


def leaf_indices_below(tree: Tree, tree_position: tuple[int, ...]) -> list[int]:
    return [
        index
        for index in range(len(tree.leaves()))
        if tree.leaf_treeposition(index)[: len(tree_position)] == tree_position
    ]


def pointer_kind(pointer: Any) -> str:
    if isinstance(pointer, PropbankChainTreePointer):
        return "chain"
    if isinstance(pointer, PropbankSplitTreePointer):
        return "split"
    if isinstance(pointer, PropbankTreePointer):
        return "tree"
    raise TypeError(f"Unsupported PropBank pointer: {type(pointer)!r}")


def pointer_shape(pointer: Any) -> str:
    kind = pointer_kind(pointer)
    if kind == "tree":
        return kind
    return f"{kind}({','.join(pointer_shape(piece) for piece in pointer.pieces)})"


def serialize_pointer(pointer: Any, tree: Tree) -> dict[str, Any]:
    kind = pointer_kind(pointer)
    selected = pointer.select(tree)
    if kind == "tree":
        tree_position = pointer.treepos(tree)
        leaf_indices = leaf_indices_below(tree, tree_position)
        pieces: list[dict[str, Any]] = []
    else:
        tree_position = None
        pieces = [serialize_pointer(piece, tree) for piece in pointer.pieces]
        leaf_indices = sorted(
            {index for piece in pieces for index in piece["terminal_indices"]}
        )
    tokens = tree.leaves()
    return {
        "kind": kind,
        "shape": pointer_shape(pointer),
        "native_type": type(pointer).__name__,
        "notation": str(pointer),
        "word_number": getattr(pointer, "wordnum", None),
        "height": getattr(pointer, "height", None),
        "tree_position": list(tree_position) if tree_position is not None else None,
        "terminal_indices": leaf_indices,
        "selected_tokens": [tokens[index] for index in leaf_indices],
        "selected_text": " ".join(tokens[index] for index in leaf_indices),
        "selected_tree": (
            selected.pformat(margin=1_000_000)
            if isinstance(selected, Tree)
            else str(selected)
        ),
        "source_charspan": None,
        "source_charspan_status": (
            "unavailable: Penn Treebank preserves terminal positions but not "
            "the exact original character offsets"
        ),
        "pieces": pieces,
    }


def analyze_argument_label(argument_label: str) -> dict[str, Any]:
    match = re.fullmatch(
        r"(?:(?P<reference_prefix>[CR])-)?ARG(?P<number>[0-9])(?:-(?P<suffix>.+))?",
        argument_label,
    )
    if match is None:
        return {
            "original_label": argument_label,
            "base_label": argument_label,
            "numbered_role": None,
            "reference_prefix": None,
            "suffix": None,
        }
    number = match.group("number")
    return {
        "original_label": argument_label,
        "base_label": f"ARG{number}",
        "numbered_role": number,
        "reference_prefix": match.group("reference_prefix"),
        "suffix": match.group("suffix"),
    }


def role_definition(
    label_analysis: dict[str, Any], roleset: dict[str, Any] | None
) -> dict[str, Any] | None:
    number = label_analysis["numbered_role"]
    if number is None or roleset is None:
        return None
    return next(
        (role for role in roleset["roles"] if role["number"] == number), None
    )


def serialize_tree(tree: Tree) -> dict[str, Any]:
    tokens = []
    for index, (token, pos) in enumerate(tree.pos()):
        tokens.append(
            {
                "terminal_index": index,
                "token": token,
                "pos": pos,
                "is_empty_category": pos == "-NONE-",
                "tree_position": list(tree.leaf_treeposition(index)),
            }
        )
    return {
        "bracketed": tree.pformat(margin=1_000_000),
        "tokens": tokens,
        "text_with_empty_categories": " ".join(tree.leaves()),
        "surface_text_approximation": " ".join(
            token["token"] for token in tokens if not token["is_empty_category"]
        ),
        "terminal_count": len(tokens),
    }


def instance_key(instance: Any) -> tuple[str, int, int]:
    return instance.fileid, instance.sentnum, instance.wordnum


def requested_key(fixture: dict[str, Any]) -> tuple[str, int, int]:
    locator = fixture["instance"]
    return locator["fileid"], locator["sentnum"], locator["wordnum"]


def raw_annotation_index() -> dict[tuple[str, int, int], str]:
    index = {}
    for line in propbank.raw("prop.txt").splitlines():
        columns = line.split()
        key = (Path(columns[0]).name, int(columns[1]), int(columns[2]))
        index[key] = line
    return index


def serialize_instance(
    fixture: dict[str, Any],
    instance: Any,
    roleset: dict[str, Any] | None,
    raw_line: str,
    resource_fingerprints: dict[str, str],
) -> dict[str, Any]:
    tree = instance.tree
    if tree is None:
        raise RuntimeError(f"Tree unavailable for selected fixture: {fixture['id']}")
    predicate = serialize_pointer(instance.predicate, tree)
    arguments = []
    for pointer, label in instance.arguments:
        label_analysis = analyze_argument_label(label)
        arguments.append(
            {
                "label": label,
                "label_analysis": label_analysis,
                "roleset_role_definition": role_definition(
                    label_analysis, roleset
                ),
                "pointer": serialize_pointer(pointer, tree),
            }
        )
    analysis_id = stable_id(
        "propbank-annotation:",
        {
            "resource_version": PROPBANK_VERSION,
            "fileid": instance.fileid,
            "sentnum": instance.sentnum,
            "wordnum": instance.wordnum,
            "roleset": instance.roleset,
            "raw_line": raw_line,
        },
    )
    return {
        "analysis_id": analysis_id,
        "analysis_type": "propbank_corpus_predicate_argument_annotation",
        "producer": {
            "interface": "NLTK PropBankCorpusReader",
            "resource": "UPenn PropBank",
            "resource_version": PROPBANK_VERSION,
            "resource_sha256": resource_fingerprints["propbank.zip"],
            "adapter": "poc/lex-03/run.py",
            "adapter_version": ADAPTER_VERSION,
            "schema_version": SCHEMA_VERSION,
            "nltk_version": nltk.__version__,
            "parameters": {
                "terminal_numbering": "zero-based, including empty categories",
                "character_offsets": "not supplied by Penn Treebank",
            },
        },
        "support": {
            "annotation_file": "prop.txt",
            "treebank_fileid": instance.fileid,
            "sentence_number": instance.sentnum,
            "predicate_terminal_number": instance.wordnum,
            "source_charspan": None,
            "source_charspan_status": (
                "unavailable from PropBank 1.0 and Penn Treebank"
            ),
        },
        "annotation_status": instance.tagger,
        "score": None,
        "score_status": "not provided for gold PropBank corpus annotations",
        "lemma": instance.baseform,
        "sense_number": instance.sensenumber,
        "roleset_id": instance.roleset,
        "roleset_definition_status": (
            "resolved" if roleset is not None else "unresolved_in_corpus_annotation"
        ),
        "roleset_assignment_source": "existing PropBank corpus annotation",
        "automatically_assigned_to_new_text": False,
        "inflection": {
            "code": str(instance.inflection),
            "form": instance.inflection.form,
            "tense": instance.inflection.tense,
            "aspect": instance.inflection.aspect,
            "person": instance.inflection.person,
            "voice": instance.inflection.voice,
        },
        "predicate": predicate,
        "arguments": arguments,
        "tree": serialize_tree(tree),
        "raw_annotation_line": raw_line,
    }


def validate(fixtures: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
    if len(fixtures) != len(results):
        raise RuntimeError("LEX-03 fixture coverage is incomplete")
    ids: set[str] = set()
    for fixture, result in zip(fixtures, results, strict=True):
        annotation = result["instance_annotation"]
        if annotation["analysis_id"] in ids:
            raise RuntimeError(f"Duplicate analysis ID: {fixture['id']}")
        ids.add(annotation["analysis_id"])
        if annotation["roleset_id"] != fixture["roleset_id"]:
            raise RuntimeError(f"Unexpected roleset: {fixture['id']}")
        labels = {argument["label"] for argument in annotation["arguments"]}
        if not set(fixture["expected_arguments"]).issubset(labels):
            raise RuntimeError(f"Missing arguments: {fixture['id']}")
        kinds = {
            argument["pointer"]["kind"] for argument in annotation["arguments"]
        }
        if not set(fixture["expected_pointer_kinds"]).issubset(kinds):
            raise RuntimeError(f"Missing pointer kind: {fixture['id']}")
        shapes = {
            argument["pointer"]["shape"] for argument in annotation["arguments"]
        }
        if not set(fixture.get("expected_pointer_shapes", [])).issubset(shapes):
            raise RuntimeError(f"Missing pointer shape: {fixture['id']}")
        if not annotation["predicate"]["terminal_indices"]:
            raise RuntimeError(f"Predicate is not anchored: {fixture['id']}")
        definition_expected = fixture.get("expected_roleset_definition", True)
        if definition_expected:
            if not result["roleset_definition"]["roles"]:
                raise RuntimeError(
                    f"Roleset has no argument definitions: {fixture['id']}"
                )
            if fixture["roleset_id"] not in result["available_roleset_ids_for_lemma"]:
                raise RuntimeError(
                    f"Roleset absent from lemma inventory: {fixture['id']}"
                )
        elif result["roleset_definition"] is not None:
            raise RuntimeError(f"Unresolved roleset was resolved: {fixture['id']}")
        expected_normalized = fixture.get("expected_normalized_argument")
        if expected_normalized:
            argument = next(
                item
                for item in annotation["arguments"]
                if item["label"] == expected_normalized["label"]
            )
            analysis = argument["label_analysis"]
            if analysis["base_label"] != expected_normalized["base_label"]:
                raise RuntimeError(f"Bad normalized label: {fixture['id']}")
            if analysis["suffix"] != expected_normalized["suffix"]:
                raise RuntimeError(f"Bad argument suffix: {fixture['id']}")
            if argument["roleset_role_definition"] is None:
                raise RuntimeError(f"Suffixed role was not linked: {fixture['id']}")
    run_results = [result for result in results if result["lemma"] == "run"]
    if {result["roleset_definition"]["roleset_id"] for result in run_results} != {
        "run.01",
        "run.02",
    }:
        raise RuntimeError("Polysemous run rolesets are not both represented")
    if any(
        result["instance_annotation"]["automatically_assigned_to_new_text"]
        for result in results
    ):
        raise RuntimeError("Corpus annotations were mislabeled as automatic SRL")
    if not any(
        result["instance_annotation"]["roleset_definition_status"]
        == "unresolved_in_corpus_annotation"
        for result in results
    ):
        raise RuntimeError("Unresolved corpus rolesets are not represented")
    if not all(
        result["available_rolesets_for_lemma"]
        and all(
            not candidate["selected_by_lemma_lookup"]
            for candidate in result["available_rolesets_for_lemma"]
        )
        for result in results
    ):
        raise RuntimeError("Lemma candidates are incomplete or prematurely selected")


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    targets = {requested_key(fixture): fixture for fixture in fixtures}
    available_tree_files = set(treebank.fileids())
    ptb_catalog_path = Path(str(nltk.data.find("corpora/ptb/allcats.txt")))
    ptb_catalog_entry_count = len(ptb_catalog_path.read_text().splitlines())
    licensed_ptb_files = set(ptb.fileids())
    archive_paths = {
        "propbank.zip": Path(str(nltk.data.find("corpora/propbank.zip"))),
        "treebank.zip": Path(str(nltk.data.find("corpora/treebank.zip"))),
        "ptb.zip": Path(str(nltk.data.find("corpora/ptb.zip"))),
    }
    resource_fingerprints = {
        name: sha256_file(path) for name, path in archive_paths.items()
    }
    selected_instances: dict[tuple[str, int, int], Any] = {}
    total_instances = 0
    tree_available_instances = 0
    roleset_counts: Counter[str] = Counter()
    argument_label_counts: Counter[str] = Counter()
    pointer_type_counts: Counter[str] = Counter()
    pointer_shape_counts: Counter[str] = Counter()
    unresolved_roleset_counts: Counter[str] = Counter()
    annotation_status_counts: Counter[str] = Counter()
    for instance in propbank.instances():
        total_instances += 1
        roleset_counts[instance.roleset] += 1
        annotation_status_counts[instance.tagger] += 1
        if instance.roleset.endswith(".XX"):
            unresolved_roleset_counts[instance.roleset] += 1
        for pointer, label in instance.arguments:
            argument_label_counts[label] += 1
            pointer_type_counts[type(pointer).__name__] += 1
            pointer_shape_counts[pointer_shape(pointer)] += 1
        if instance.fileid in available_tree_files:
            tree_available_instances += 1
        key = instance_key(instance)
        if key in targets:
            if key in selected_instances:
                raise RuntimeError(f"Duplicate target instance: {key}")
            selected_instances[key] = instance
    if set(selected_instances) != set(targets):
        missing = sorted(set(targets) - set(selected_instances))
        raise RuntimeError(f"Missing fixture instances: {missing}")

    raw_annotations = raw_annotation_index()
    results = []
    raw_frame_xml: dict[str, str] = {}
    raw_parse_trees: dict[str, str] = {}
    selected_raw_lines = []
    for fixture in fixtures:
        key = requested_key(fixture)
        instance = selected_instances[key]
        available_rolesets = [
            serialize_roleset(
                fixture["lemma"],
                item.get("id"),
                resource_fingerprints["propbank.zip"],
            )
            for item in propbank.rolesets(fixture["lemma"])
        ]
        candidate_ids = [item["resource_id"] for item in available_rolesets]
        for candidate in available_rolesets:
            candidate["support"] = {
                "lookup_operation": "propbank.rolesets(lemma)",
                "lookup_lemma": fixture["lemma"],
            }
            candidate["competes_with"] = [
                candidate_id
                for candidate_id in candidate_ids
                if candidate_id != candidate["resource_id"]
            ]
        available_by_id = {
            item["roleset_id"]: item for item in available_rolesets
        }
        roleset = available_by_id.get(fixture["roleset_id"])
        raw_line = raw_annotations[key]
        annotation = serialize_instance(
            fixture, instance, roleset, raw_line, resource_fingerprints
        )
        results.append(
            {
                **fixture,
                "available_roleset_ids_for_lemma": [
                    item["roleset_id"] for item in available_rolesets
                ],
                "available_rolesets_for_lemma": available_rolesets,
                "lemma_lookup_selects_a_roleset": False,
                "roleset_definition": roleset,
                "instance_annotation": annotation,
            }
        )
        raw_frame_xml[fixture["lemma"]] = propbank.open(
            f"frames/{fixture['lemma']}.xml"
        ).read()
        raw_parse_trees[fixture["id"]] = annotation["tree"]["bracketed"]
        selected_raw_lines.append({"fixture": fixture["id"], "line": raw_line})

    validate(fixtures, results)
    arguments = [
        argument
        for result in results
        for argument in result["instance_annotation"]["arguments"]
    ]
    pointer_counts = Counter(argument["pointer"]["kind"] for argument in arguments)
    unique_lemmas = sorted({fixture["lemma"] for fixture in fixtures})
    candidate_roleset_ids = {
        candidate["resource_id"]
        for result in results
        for candidate in result["available_rolesets_for_lemma"]
    }
    all_rolesets = list(propbank.rolesets())
    summary = {
        "fixture_count": len(fixtures),
        "selected_lemma_count": len(unique_lemmas),
        "selected_annotation_roleset_id_count": len(
            {fixture["roleset_id"] for fixture in fixtures}
        ),
        "candidate_roleset_definition_count": len(candidate_roleset_ids),
        "selected_instance_count": len(results),
        "selected_argument_count": len(arguments),
        "selected_pointer_counts": dict(sorted(pointer_counts.items())),
        "selected_nested_pointer_shape_count": sum(
            argument["pointer"]["shape"].startswith("chain(")
            and "split(" in argument["pointer"]["shape"]
            for argument in arguments
        ),
        "corpus_verb_count": len(propbank.verbs()),
        "corpus_roleset_count": len(all_rolesets),
        "corpus_instance_count": total_instances,
        "installed_treebank_file_count": len(available_tree_files),
        "nltk_ptb_catalog_entry_count": ptb_catalog_entry_count,
        "licensed_ptb_parse_file_count": len(licensed_ptb_files),
        "instances_with_installed_tree_count": tree_available_instances,
        "instances_without_installed_tree_count": (
            total_instances - tree_available_instances
        ),
        "unresolved_roleset_instance_count": sum(
            unresolved_roleset_counts.values()
        ),
        "unresolved_roleset_id_count": len(unresolved_roleset_counts),
        "distinct_argument_label_count": len(argument_label_counts),
        "installed_tree_coverage_ratio": (
            tree_available_instances / total_instances
        ),
        "new_sentence_annotation_performed": False,
        "verdict": "PARTIAL_CORPUS_READER_WITH_COMPLETE_FRAME_INVENTORY",
    }
    corpus_inventory = {
        "annotation_status_counts": dict(sorted(annotation_status_counts.items())),
        "roleset_counts": dict(sorted(roleset_counts.items())),
        "unresolved_roleset_counts": dict(
            sorted(unresolved_roleset_counts.items())
        ),
        "argument_label_counts": dict(sorted(argument_label_counts.items())),
        "pointer_native_type_counts": dict(sorted(pointer_type_counts.items())),
        "pointer_shape_counts": dict(sorted(pointer_shape_counts.items())),
    }
    resource_boundary = {
        "lemma_lookup": {
            "input": "lemma",
            "output": (
                "all structured roleset definitions stored for that lemma, "
                "with stable IDs and explicit competition links"
            ),
            "selects_sense_for_occurrence": False,
        },
        "corpus_annotation_lookup": {
            "input": "existing PropBank file/sentence/predicate coordinates",
            "output": "the manually assigned roleset and argument tree pointers",
            "assignment_source": "PropBank corpus annotation",
        },
        "new_sentence": {
            "automatic_semantic_role_labeling_available_from_this_resource": False,
            "required_additional_component": (
                "a semantic role labeler or a project adapter combining syntax, "
                "lexical candidates, and context"
            ),
        },
        "text_anchoring": {
            "tree_positions_and_terminal_indices_available": True,
            "original_character_spans_available": False,
            "representation": (
                "source_charspan is null with an explicit status; reconstructed "
                "Treebank text is never presented as the exact source string"
            ),
        },
        "tree_availability": {
            "propbank_annotations": total_instances,
            "annotations_resolvable_against_installed_nltk_treebank": (
                tree_available_instances
            ),
            "reason": (
                "NLTK distributes PropBank annotation lines for the full WSJ corpus, "
                "while its freely included Treebank contains only a sample."
            ),
            "nltk_ptb_package": {
                "catalog_entries": ptb_catalog_entry_count,
                "parse_files_present": len(licensed_ptb_files),
                "interpretation": (
                    "The downloadable NLTK ptb package supplies allcats.txt, but "
                    "licensed .MRG files must be added by an authorized user."
                ),
            },
        },
    }

    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("results.json", results),
        ("summary.json", summary),
        ("resource-vs-annotation.json", resource_boundary),
        ("corpus-inventory.json", corpus_inventory),
        ("raw/annotation-lines.json", selected_raw_lines),
        ("raw/frame-xml.json", raw_frame_xml),
        ("raw/parse-trees.json", raw_parse_trees),
    ):
        (output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "nltk_version": nltk.__version__,
        "adapter_version": ADAPTER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "propbank_version": PROPBANK_VERSION,
        "propbank_root": str(propbank.root),
        "treebank_root": str(treebank.root),
        "ptb_root": str(ptb.root),
        "resource_archives": {
            name: {"path": str(path), "sha256": resource_fingerprints[name]}
            for name, path in archive_paths.items()
        },
        "parameters": {
            "rolesets": "propbank.rolesets(lemma) and propbank.roleset(id)",
            "instances": "propbank.instances()",
            "trees": "instance.tree through the installed NLTK Treebank sample",
            "terminal_numbering": "zero-based and includes empty categories",
            "new_sentence_annotation": False,
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"LEX-03: {len(results)} fixtures validated")
    print(
        f"rolesets: {summary['corpus_roleset_count']}; "
        f"instances: {total_instances}; "
        f"installed trees: {tree_available_instances}/{total_instances}"
    )
    print("new sentence semantic role labeling: not performed (corpus lookup only)")


if __name__ == "__main__":
    main()
