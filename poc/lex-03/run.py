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


def stable_id(prefix: str, payload: Any) -> str:
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return prefix + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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


def serialize_roleset(lemma: str, roleset_id: str) -> dict[str, Any]:
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
        "roleset_id": roleset_id,
        "lemma": lemma,
        "name": roleset.get("name"),
        "verbnet_class_ids": roleset.get("vncls", "").split(),
        "attributes": dict(roleset.attrib),
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
        "pieces": pieces,
    }


def role_definition(
    argument_label: str, roleset: dict[str, Any]
) -> dict[str, Any] | None:
    match = re.fullmatch(r"(?:[CR]-)?ARG([0-9]+)", argument_label)
    if match is None:
        return None
    number = match.group(1)
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
    roleset: dict[str, Any],
    raw_line: str,
) -> dict[str, Any]:
    tree = instance.tree
    if tree is None:
        raise RuntimeError(f"Tree unavailable for selected fixture: {fixture['id']}")
    predicate = serialize_pointer(instance.predicate, tree)
    arguments = []
    for pointer, label in instance.arguments:
        arguments.append(
            {
                "label": label,
                "roleset_role_definition": role_definition(label, roleset),
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
        "producer": {
            "interface": "NLTK PropBankCorpusReader",
            "resource": "UPenn PropBank",
            "resource_version": PROPBANK_VERSION,
        },
        "support": {
            "annotation_file": "prop.txt",
            "treebank_fileid": instance.fileid,
            "sentence_number": instance.sentnum,
            "predicate_terminal_number": instance.wordnum,
        },
        "annotation_status": instance.tagger,
        "lemma": instance.baseform,
        "sense_number": instance.sensenumber,
        "roleset_id": instance.roleset,
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
        if not annotation["predicate"]["terminal_indices"]:
            raise RuntimeError(f"Predicate is not anchored: {fixture['id']}")
        if not result["roleset_definition"]["roles"]:
            raise RuntimeError(f"Roleset has no argument definitions: {fixture['id']}")
        if fixture["roleset_id"] not in result["available_roleset_ids_for_lemma"]:
            raise RuntimeError(f"Roleset absent from lemma inventory: {fixture['id']}")
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


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    targets = {requested_key(fixture): fixture for fixture in fixtures}
    available_tree_files = set(treebank.fileids())
    ptb_catalog_path = Path(str(nltk.data.find("corpora/ptb/allcats.txt")))
    ptb_catalog_entry_count = len(ptb_catalog_path.read_text().splitlines())
    licensed_ptb_files = set(ptb.fileids())
    selected_instances: dict[tuple[str, int, int], Any] = {}
    total_instances = 0
    tree_available_instances = 0
    roleset_counts: Counter[str] = Counter()
    for instance in propbank.instances():
        total_instances += 1
        roleset_counts[instance.roleset] += 1
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
        roleset = serialize_roleset(fixture["lemma"], fixture["roleset_id"])
        available_rolesets = [
            serialize_roleset(fixture["lemma"], item.get("id"))
            for item in propbank.rolesets(fixture["lemma"])
        ]
        raw_line = raw_annotations[key]
        annotation = serialize_instance(fixture, instance, roleset, raw_line)
        results.append(
            {
                **fixture,
                "available_roleset_ids_for_lemma": [
                    item["roleset_id"] for item in available_rolesets
                ],
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
    all_rolesets = list(propbank.rolesets())
    summary = {
        "fixture_count": len(fixtures),
        "selected_lemma_count": len(unique_lemmas),
        "selected_roleset_count": len(
            {fixture["roleset_id"] for fixture in fixtures}
        ),
        "selected_instance_count": len(results),
        "selected_argument_count": len(arguments),
        "selected_pointer_counts": dict(sorted(pointer_counts.items())),
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
        "installed_tree_coverage_ratio": (
            tree_available_instances / total_instances
        ),
        "new_sentence_annotation_performed": False,
        "verdict": "PARTIAL_CORPUS_READER_WITH_COMPLETE_FRAME_INVENTORY",
    }
    resource_boundary = {
        "lemma_lookup": {
            "input": "lemma",
            "output": "all roleset definitions stored for that lemma",
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
        "propbank_version": PROPBANK_VERSION,
        "propbank_root": str(propbank.root),
        "treebank_root": str(treebank.root),
        "ptb_root": str(ptb.root),
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
