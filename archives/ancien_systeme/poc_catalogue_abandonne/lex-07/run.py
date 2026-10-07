#!/usr/bin/env python3
"""Run LEX-07: align new occurrences with lexical-resource candidates."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nltk
from delphin import ace
from nltk.corpus import framenet as fn
from nltk.corpus import propbank, verbnet as vn, wordnet as wn
from nltk.corpus.reader.wordnet import WordNetError


POC_DIR = Path(__file__).resolve().parent
REPO_ROOT = POC_DIR.parent.parent
DEFAULT_ACE = REPO_ROOT / ".local" / "bin" / "ace"
DEFAULT_GRAMMAR = (
    REPO_ROOT / ".local" / "share" / "erg" / "erg-2018-x86-64-0.9.34.dat"
)
SEMLINK_ROOT = REPO_ROOT / ".local" / "share" / "semlink"
SUMO_ROOT = REPO_ROOT / ".local" / "share" / "sumo"
ADAPTER_VERSION = "1"
SCHEMA_VERSION = "seman2.occurrence-resource-alignment-poc.v1"

MAPPING_FILES = {
    "n": "WordNetMappings30-noun.txt",
    "v": "WordNetMappings30-verb.txt",
    "a": "WordNetMappings30-adj.txt",
    "r": "WordNetMappings30-adv.txt",
}
SUMO_MAPPING_PATTERN = re.compile(r"&%([^\s&]+?)([=+@:\[\]])(?=\s|$)")
SUMO_OPERATOR_TYPES = {
    "=": "equivalent_to",
    "+": "subsumed_by",
    "@": "instance_of",
    ":": "not_equivalent_to",
    "[": "not_subsumed_by",
    "]": "not_instance_of",
}
ERG_PREDICATE_PATTERN = re.compile(
    r"^_(?P<lemma>.+)_(?P<pos>[nvar])_(?P<entry>[^_]+)$"
)
VN_FN_KEY_PATTERN = re.compile(r"^([0-9][0-9.\-]*)-(.+)$")


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


def ace_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "-V"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


def canonical_pos(pos: str) -> str:
    return "a" if pos == "s" else pos


def parse_sumo_mappings() -> dict[tuple[str, int], list[dict[str, Any]]]:
    mappings: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for pos, filename in MAPPING_FILES.items():
        path = SUMO_ROOT / "WordNetMappings" / filename
        for line_number, line in enumerate(path.open(encoding="utf-8", errors="replace"), 1):
            if re.match(r"^\d{8}\s", line) is None:
                continue
            offset = int(line[:8])
            payload = line.split("|", 1)[1] if "|" in line else ""
            key = (pos, offset)
            existing = {
                (item["sumo_concept"], item["operator"])
                for item in mappings.get(key, [])
            }
            for concept, operator in SUMO_MAPPING_PATTERN.findall(payload):
                if (concept, operator) in existing:
                    continue
                mappings.setdefault(key, []).append(
                    {
                        "edge_id": stable_id(
                            "wordnet-sumo-edge:",
                            {
                                "pos": pos,
                                "offset": offset,
                                "concept": concept,
                                "operator": operator,
                            },
                        ),
                        "relation_type": SUMO_OPERATOR_TYPES[operator],
                        "sumo_concept": concept,
                        "operator": operator,
                        "source_file": filename,
                        "source_line": line_number,
                    }
                )
    return mappings


def production_kif_symbols() -> set[str]:
    symbols: set[str] = set()
    for path in sorted(SUMO_ROOT.glob("*.kif")):
        text = path.read_text(encoding="utf-8", errors="replace")
        in_string = False
        escaped = False
        in_comment = False
        token: list[str] = []
        for character in text:
            if in_comment:
                if character == "\n":
                    in_comment = False
                continue
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                continue
            if character == ";":
                if token:
                    symbols.add("".join(token))
                    token = []
                in_comment = True
            elif character == '"':
                if token:
                    symbols.add("".join(token))
                    token = []
                in_string = True
            elif character.isspace() or character in "()":
                if token:
                    symbols.add("".join(token))
                    token = []
            else:
                token.append(character)
        if token:
            symbols.add("".join(token))
    return symbols


def serialize_ep(ep: Any, variables: dict[str, Any]) -> dict[str, Any]:
    return {
        "predicate": ep.predicate,
        "label": ep.label,
        "charspan": [ep.cfrom, ep.cto],
        "arguments": dict(ep.args),
        "argument_properties": {
            variable: variables.get(variable, {})
            for variable in ep.args.values()
            if variable in variables
        },
    }


def analyze_erg_occurrence(
    fixture: dict[str, Any], response: Any, max_results: int
) -> dict[str, Any]:
    target_span = fixture["target_span"]
    analyses = []
    predicates: set[str] = set()
    derived_lemmas: set[str] = set()
    derived_pos: set[str] = set()
    for rank, result in enumerate(response.results(), start=1):
        mrs = result.mrs()
        # ERG can attach sentence-final punctuation to the lexical EP span
        # (e.g. ``bank.`` is [25, 30] although the source occurrence is
        # ``bank`` at [25, 29]).  Accept only that explicitly bounded case;
        # keep both spans in the output rather than rewriting the occurrence.
        target_eps = [
            ep
            for ep in mrs.rels
            if ep.cfrom == target_span[0]
            and ep.cto >= target_span[1]
            and fixture["sentence"][target_span[1] : ep.cto].strip() in {"", ".", "!", "?"}
            and ERG_PREDICATE_PATTERN.fullmatch(ep.predicate)
        ]
        if len(target_eps) != 1:
            raise RuntimeError(
                f"Expected one target EP for {fixture['id']}, got {len(target_eps)}"
            )
        target = target_eps[0]
        match = ERG_PREDICATE_PATTERN.fullmatch(target.predicate)
        assert match is not None
        lemma = match.group("lemma").replace("_", " ")
        pos = match.group("pos")
        predicates.add(target.predicate)
        derived_lemmas.add(lemma)
        derived_pos.add(pos)
        flags = dict(result.get("flags", []))
        analyses.append(
            {
                "rank": rank,
                "score": flags.get(":ascore"),
                "probability": flags.get(":probability"),
                "target_ep": serialize_ep(target, mrs.variables),
                "target_semantic_argument_roles": sorted(
                    role for role in target.args if role.startswith("ARG") and role != "ARG0"
                ),
                "mrs_relations": [serialize_ep(ep, mrs.variables) for ep in mrs.rels],
                "mrs_raw": result.get("mrs"),
            }
        )
    if not analyses:
        raise RuntimeError(f"ACE/ERG failed to parse {fixture['id']}")
    if len(derived_lemmas) != 1 or len(derived_pos) != 1:
        raise RuntimeError(f"ERG target lemma/POS varies across parses: {fixture['id']}")
    return {
        "analysis_type": "erg_syntactic_semantic_parse",
        "analysis_count": int(response.get("readings", len(analyses))),
        "returned_analysis_count": len(analyses),
        "limit_reached": len(analyses) == max_results,
        "target_text": fixture["sentence"][target_span[0] : target_span[1]],
        "target_span": target_span,
        "derived_lemma": next(iter(derived_lemmas)),
        "derived_part_of_speech": next(iter(derived_pos)),
        "target_predicates": sorted(predicates),
        "analyses": analyses,
        "word_sense_selected": False,
        "frame_selected": False,
    }


def serialize_wordnet_candidates(
    lemma: str,
    pos: str,
    sumo_mappings: dict[tuple[str, int], list[dict[str, Any]]],
    kif_symbols: set[str],
) -> list[dict[str, Any]]:
    candidates = []
    for synset in wn.synsets(lemma, pos=pos):
        candidate_id = stable_id(
            "wordnet-candidate:",
            {"version": wn.get_version(), "synset": synset.name()},
        )
        mappings = [
            {
                **mapping,
                "sumo_concept_occurs_in_production_kif": (
                    mapping["sumo_concept"] in kif_symbols
                ),
            }
            for mapping in sumo_mappings.get(
                (canonical_pos(synset.pos()), synset.offset()), []
            )
        ]
        candidates.append(
            {
                "candidate_id": candidate_id,
                "analysis_type": "wordnet_synset_candidate",
                "synset": synset.name(),
                "offset": synset.offset(),
                "part_of_speech": synset.pos(),
                "lemmas": [item.name() for item in synset.lemmas()],
                "sense_keys": [item.key() for item in synset.lemmas()],
                "definition": synset.definition(),
                "examples": synset.examples(),
                "lexname": synset.lexname(),
                "sumo_mappings": mappings,
                "selected": False,
                "score": None,
                "support": {"method": "wn.synsets(lemma, pos)", "lemma": lemma, "pos": pos},
            }
        )
    return candidates


def vn_numeric_id(class_id: str) -> str:
    return class_id.split("-", 1)[1]


def vn_ancestor_ids(numeric_id: str, class_by_numeric: dict[str, str]) -> list[str]:
    pieces = numeric_id.split("-")
    return [
        "-".join(pieces[:index])
        for index in range(1, len(pieces) + 1)
        if "-".join(pieces[:index]) in class_by_numeric
    ]


def serialize_verbnet_candidates(lemma: str, pos: str) -> list[dict[str, Any]]:
    if pos != "v":
        return []
    class_by_numeric = {vn_numeric_id(item): item for item in vn.classids()}
    candidates = []
    for class_id in vn.classids(lemma):
        numeric_id = vn_numeric_id(class_id)
        roles = []
        for ancestor in vn_ancestor_ids(numeric_id, class_by_numeric):
            for role in vn.themroles(class_by_numeric[ancestor]):
                roles.append(
                    {
                        "origin_class": ancestor,
                        "role": role["type"],
                        "selectional_restrictions": role["modifiers"],
                    }
                )
        candidates.append(
            {
                "candidate_id": stable_id(
                    "verbnet-candidate:",
                    {"version": vn.version, "class_id": class_id, "lemma": lemma},
                ),
                "analysis_type": "verbnet_class_candidate",
                "class_id": class_id,
                "numeric_class_id": numeric_id,
                "thematic_roles_along_hierarchy": roles,
                "selected": False,
                "score": None,
                "support": {"method": "vn.classids(lemma)", "lemma": lemma},
            }
        )
    return candidates


def serialize_propbank_candidates(lemma: str, pos: str) -> list[dict[str, Any]]:
    if pos != "v":
        return []
    candidates = []
    for roleset in propbank.rolesets(lemma):
        roleset_id = roleset.get("id")
        candidates.append(
            {
                "candidate_id": stable_id(
                    "propbank-candidate:",
                    {"resource": "NLTK PropBank 1.0", "roleset": roleset_id},
                ),
                "analysis_type": "propbank_roleset_candidate",
                "roleset_id": roleset_id,
                "name": roleset.get("name"),
                "roles": [
                    {
                        "argument": f"ARG{role.get('n')}",
                        "description": role.get("descr"),
                        "function": role.get("f"),
                    }
                    for role in roleset.findall("roles/role")
                ],
                "selected": False,
                "score": None,
                "support": {"method": "propbank.rolesets(lemma)", "lemma": lemma},
            }
        )
    return candidates


def serialize_framenet_candidates(lemma: str, pos: str) -> list[dict[str, Any]]:
    pattern = "^" + re.escape(lemma) + r"\." + re.escape(pos) + "$"
    candidates = []
    for lu in fn.lus(pattern):
        candidates.append(
            {
                "candidate_id": stable_id(
                    "framenet-candidate:",
                    {"version": "1.7", "lexical_unit_id": lu.ID},
                ),
                "analysis_type": "framenet_frame_candidate_via_lexical_unit",
                "lexical_unit_id": lu.ID,
                "lexical_unit": lu.name,
                "frame_id": lu.frame.ID,
                "frame": lu.frame.name,
                "frame_elements": [
                    {"name": fe.name, "core_type": fe.coreType}
                    for fe in sorted(lu.frame.FE.values(), key=lambda item: item.ID)
                ],
                "selected": False,
                "score": None,
                "support": {"method": "fn.lus(exact_lemma_pos_pattern)", "pattern": pattern},
            }
        )
    return candidates


def normalize_verbnet_wordnet_key(key: str) -> str:
    key = key.lstrip("?")
    return key if key.endswith("::") else key + "::"


def verbnet_wordnet_edges(
    lemma: str,
    vn_candidates: list[dict[str, Any]],
    wn_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    wn_by_synset = {item["synset"]: item["candidate_id"] for item in wn_candidates}
    edges = []
    for candidate in vn_candidates:
        element = vn.vnclass(candidate["class_id"])
        member = next(
            (
                item
                for item in element.findall("./MEMBERS/MEMBER")
                if item.get("name") == lemma
            ),
            None,
        )
        if member is None:
            continue
        for source_key in member.get("wn", "").split():
            normalized_key = normalize_verbnet_wordnet_key(source_key)
            try:
                wordnet_lemma = wn.lemma_from_key(normalized_key)
                synset_name = wordnet_lemma.synset().name()
                target_id = wn_by_synset.get(synset_name)
                resolved = target_id is not None
                error = None if resolved else "resolved synset is outside lemma/POS lookup candidates"
            except (KeyError, ValueError, WordNetError) as exc:
                synset_name = None
                target_id = None
                resolved = False
                error = f"{type(exc).__name__}: {exc}"
            edges.append(
                {
                    "edge_id": stable_id(
                        "verbnet-wordnet-edge:",
                        {
                            "class": candidate["class_id"],
                            "lemma": lemma,
                            "source_key": source_key,
                        },
                    ),
                    "relation_type": "verbnet_member_has_wordnet_sense_key",
                    "source_candidate_id": candidate["candidate_id"],
                    "source_key": source_key,
                    "normalized_key": normalized_key,
                    "wordnet_synset": synset_name,
                    "target_candidate_id": target_id,
                    "resolved_within_occurrence_candidates": resolved,
                    "error": error,
                }
            )
    return edges


def semlink_edges(
    lemma: str,
    pos: str,
    pb_vn_data: dict[str, Any],
    vn_fn_data: dict[str, Any],
    pb_candidates: list[dict[str, Any]],
    vn_candidates: list[dict[str, Any]],
    fn_candidates: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    if pos != "v":
        return {"propbank_to_verbnet": [], "verbnet_to_framenet": []}
    pb_ids = {item["roleset_id"]: item["candidate_id"] for item in pb_candidates}
    vn_ids = {
        item["numeric_class_id"]: item["candidate_id"] for item in vn_candidates
    }
    fn_ids: dict[str, list[str]] = {}
    for item in fn_candidates:
        fn_ids.setdefault(item["frame"], []).append(item["candidate_id"])
    pb_vn_edges = []
    for roleset, mappings in sorted(pb_vn_data.items()):
        if roleset.rsplit(".", 1)[0] != lemma:
            continue
        for vn_class, role_mappings in sorted(mappings.items()):
            pb_vn_edges.append(
                {
                    "edge_id": stable_id(
                        "semlink-pb-vn-edge:",
                        {"roleset": roleset, "vn_class": vn_class},
                    ),
                    "relation_type": "propbank_roleset_maps_to_verbnet_class",
                    "propbank_roleset": roleset,
                    "source_candidate_id": pb_ids.get(roleset),
                    "verbnet_class": vn_class,
                    "target_candidate_id": vn_ids.get(vn_class),
                    "source_resolved_in_installed_candidates": roleset in pb_ids,
                    "target_resolved_in_installed_candidates": vn_class in vn_ids,
                    "role_mappings": [
                        {
                            "propbank_argument": argument,
                            "verbnet_role": role,
                        }
                        for argument, role in sorted(role_mappings.items())
                    ],
                }
            )
    vn_fn_edges = []
    for key, frames in sorted(vn_fn_data.items()):
        match = VN_FN_KEY_PATTERN.fullmatch(key)
        if match is None:
            continue
        vn_class, member = match.groups()
        if member != lemma:
            continue
        for frame in sorted(frames):
            target_ids = fn_ids.get(frame, [])
            vn_fn_edges.append(
                {
                    "edge_id": stable_id(
                        "semlink-vn-fn-edge:",
                        {"vn_class": vn_class, "lemma": lemma, "frame": frame},
                    ),
                    "relation_type": "verbnet_class_member_maps_to_framenet_frame",
                    "verbnet_class": vn_class,
                    "source_candidate_id": vn_ids.get(vn_class),
                    "framenet_frame": frame,
                    "target_candidate_ids": target_ids,
                    "source_resolved_in_installed_candidates": vn_class in vn_ids,
                    "target_resolved_in_installed_candidates": bool(target_ids),
                }
            )
    return {
        "propbank_to_verbnet": pb_vn_edges,
        "verbnet_to_framenet": vn_fn_edges,
    }


def build_alignment(
    fixture: dict[str, Any],
    erg: dict[str, Any],
    sumo_mappings: dict[tuple[str, int], list[dict[str, Any]]],
    kif_symbols: set[str],
    pb_vn_data: dict[str, Any],
    vn_fn_data: dict[str, Any],
) -> dict[str, Any]:
    lemma = erg["derived_lemma"]
    pos = erg["derived_part_of_speech"]
    wn_candidates = serialize_wordnet_candidates(lemma, pos, sumo_mappings, kif_symbols)
    vn_candidates = serialize_verbnet_candidates(lemma, pos)
    pb_candidates = serialize_propbank_candidates(lemma, pos)
    fn_candidates = serialize_framenet_candidates(lemma, pos)
    vn_wn_edges = verbnet_wordnet_edges(lemma, vn_candidates, wn_candidates)
    sl_edges = semlink_edges(
        lemma,
        pos,
        pb_vn_data,
        vn_fn_data,
        pb_candidates,
        vn_candidates,
        fn_candidates,
    )
    sumo_edges = [
        {
            **mapping,
            "source_candidate_id": candidate["candidate_id"],
            "wordnet_synset": candidate["synset"],
        }
        for candidate in wn_candidates
        for mapping in candidate["sumo_mappings"]
    ]
    occurrence_id = stable_id(
        "source-occurrence:",
        {"sentence": fixture["sentence"], "charspan": fixture["target_span"]},
    )
    return {
        **fixture,
        "occurrence_id": occurrence_id,
        "source_observation": {
            "text": fixture["sentence"],
            "target_text": erg["target_text"],
            "target_charspan": fixture["target_span"],
        },
        "erg": erg,
        "lookup_candidates": {
            "wordnet": wn_candidates,
            "verbnet": vn_candidates,
            "propbank": pb_candidates,
            "framenet": fn_candidates,
        },
        "mapping_edges": {
            "verbnet_to_wordnet": vn_wn_edges,
            "propbank_to_verbnet": sl_edges["propbank_to_verbnet"],
            "verbnet_to_framenet": sl_edges["verbnet_to_framenet"],
            "wordnet_to_sumo": sumo_edges,
        },
        "selection": {
            "wordnet_synset": None,
            "verbnet_class": None,
            "propbank_roleset": None,
            "framenet_frame": None,
            "sumo_concept": None,
            "selection_status": "requires_contextual_decision_not_implemented",
            "score": None,
        },
        "method_boundary": {
            "observed_from_parser": [
                "target character span",
                "ERG lexical predicate",
                "lemma and part of speech derived from that predicate",
                "MRS argument structure for each returned parse",
            ],
            "obtained_by_lookup": [
                "WordNet synsets",
                "VerbNet classes for verbal targets",
                "PropBank rolesets for verbal targets",
                "FrameNet lexical-unit frames",
            ],
            "obtained_by_mapping": [
                "VerbNet member to WordNet sense-key edges",
                "SemLink PropBank-VerbNet and VerbNet-FrameNet edges",
                "WordNet-SUMO edges",
            ],
            "requires_decision": [
                "word-sense disambiguation",
                "VerbNet class selection",
                "PropBank roleset selection and semantic role labeling",
                "FrameNet frame and frame-element selection",
                "acceptance of a SUMO mapping as useful internal evidence",
            ],
        },
    }


def candidate_signature(result: dict[str, Any]) -> dict[str, list[str]]:
    candidates = result["lookup_candidates"]
    return {
        "wordnet": [item["candidate_id"] for item in candidates["wordnet"]],
        "verbnet": [item["candidate_id"] for item in candidates["verbnet"]],
        "propbank": [item["candidate_id"] for item in candidates["propbank"]],
        "framenet": [item["candidate_id"] for item in candidates["framenet"]],
    }


def build_contrast_report(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(result["contrast_group"], []).append(result)
    report = []
    for group, items in sorted(grouped.items()):
        if len(items) != 2:
            raise RuntimeError(f"Contrast group {group!r} must contain exactly two items")
        first, second = items
        first_signature = candidate_signature(first)
        second_signature = candidate_signature(second)
        report.append(
            {
                "contrast_group": group,
                "fixture_ids": [first["id"], second["id"]],
                "same_erg_lexical_predicates": (
                    first["erg"]["target_predicates"]
                    == second["erg"]["target_predicates"]
                ),
                "same_lookup_candidate_sets": {
                    resource: first_signature[resource] == second_signature[resource]
                    for resource in first_signature
                },
                "first_erg_argument_signatures": [
                    item["target_semantic_argument_roles"]
                    for item in first["erg"]["analyses"]
                ],
                "second_erg_argument_signatures": [
                    item["target_semantic_argument_roles"]
                    for item in second["erg"]["analyses"]
                ],
                "context_changes_candidate_selection": False,
                "interpretation": (
                    "The parser exposes contextual structure, but lexical lookup returns "
                    "the same inventory and this POC does not rank or select it."
                ),
            }
        )
    return report


def validate(results: list[dict[str, Any]], contrast_report: list[dict[str, Any]]) -> None:
    for result in results:
        fixture_id = result["id"]
        erg = result["erg"]
        if erg["derived_lemma"] != result["expected_lemma"]:
            raise RuntimeError(f"Wrong ERG lemma: {fixture_id}")
        if erg["derived_part_of_speech"] != result["expected_pos"]:
            raise RuntimeError(f"Wrong ERG POS: {fixture_id}")
        if erg["target_predicates"] != [result["expected_erg_predicate"]]:
            raise RuntimeError(f"Wrong ERG predicate: {fixture_id}")
        signatures = {
            tuple(item["target_semantic_argument_roles"])
            for item in erg["analyses"]
        }
        if tuple(result["expected_erg_argument_roles"]) not in signatures:
            raise RuntimeError(f"Wrong ERG argument structure: {fixture_id}")
        wordnet_names = {
            item["synset"] for item in result["lookup_candidates"]["wordnet"]
        }
        if result["expected_wordnet_candidate"] not in wordnet_names:
            raise RuntimeError(f"Missing WordNet candidate: {fixture_id}")
        framenet_names = {
            item["frame"] for item in result["lookup_candidates"]["framenet"]
        }
        if result["expected_framenet_candidate"] not in framenet_names:
            raise RuntimeError(f"Missing FrameNet candidate: {fixture_id}")
        if any(result["selection"][key] is not None for key in (
            "wordnet_synset",
            "verbnet_class",
            "propbank_roleset",
            "framenet_frame",
            "sumo_concept",
        )):
            raise RuntimeError(f"A resource candidate was prematurely selected: {fixture_id}")
        if result["expected_pos"] == "n" and (
            result["lookup_candidates"]["verbnet"]
            or result["lookup_candidates"]["propbank"]
            or result["mapping_edges"]["propbank_to_verbnet"]
        ):
            raise RuntimeError(f"Verb-only resources leaked into noun target: {fixture_id}")
    for comparison in contrast_report:
        if not comparison["same_erg_lexical_predicates"]:
            raise RuntimeError(f"ERG predicate differs in {comparison['contrast_group']}")
        if not all(comparison["same_lookup_candidate_sets"].values()):
            raise RuntimeError(f"Lookup sets differ in {comparison['contrast_group']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ace", type=Path, default=DEFAULT_ACE)
    parser.add_argument("--grammar", type=Path, default=DEFAULT_GRAMMAR)
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args()
    if args.max_results < 1:
        parser.error("--max-results must be positive")
    if not args.ace.is_file() or not args.grammar.is_file():
        parser.error("ACE or ERG is missing; run ./scripts/seman2 install-tools")

    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    pb_vn_path = SEMLINK_ROOT / "instances" / "pb-vn2.json"
    vn_fn_path = SEMLINK_ROOT / "instances" / "vn-fn2.json"
    pb_vn_data = json.loads(pb_vn_path.read_text(encoding="utf-8"))
    vn_fn_data = json.loads(vn_fn_path.read_text(encoding="utf-8"))
    sumo_mappings = parse_sumo_mappings()
    kif_symbols = production_kif_symbols()

    erg_results = []
    with ace.ACEParser(
        str(args.grammar),
        executable=str(args.ace),
        cmdargs=["-n", str(args.max_results)],
    ) as process:
        for fixture in fixtures:
            erg_results.append(
                analyze_erg_occurrence(
                    fixture,
                    process.interact(fixture["sentence"]),
                    args.max_results,
                )
            )

    results = [
        build_alignment(
            fixture,
            erg,
            sumo_mappings,
            kif_symbols,
            pb_vn_data,
            vn_fn_data,
        )
        for fixture, erg in zip(fixtures, erg_results, strict=True)
    ]
    contrast_report = build_contrast_report(results)
    validate(results, contrast_report)

    lookup_counts = Counter()
    mapping_counts = Counter()
    sumo_concepts: set[str] = set()
    for result in results:
        for resource, candidates in result["lookup_candidates"].items():
            lookup_counts[resource] += len(candidates)
        for relation, edges in result["mapping_edges"].items():
            mapping_counts[relation] += len(edges)
        sumo_concepts.update(
            edge["sumo_concept"]
            for edge in result["mapping_edges"]["wordnet_to_sumo"]
        )
    summary = {
        "fixture_count": len(results),
        "contrast_group_count": len(contrast_report),
        "erg_parse_count": sum(item["analysis_count"] for item in erg_results),
        "lookup_candidate_counts_with_repeated_contrast_lookups": dict(
            sorted(lookup_counts.items())
        ),
        "mapping_edge_counts_with_repeated_contrast_lookups": dict(
            sorted(mapping_counts.items())
        ),
        "distinct_sumo_concept_count_reached": len(sumo_concepts),
        "selected_candidate_count": 0,
        "automatic_word_sense_disambiguation_performed": False,
        "automatic_semantic_role_labeling_performed": False,
        "automatic_frame_detection_performed": False,
        "verdict": "GO_FOR_CANDIDATE_GENERATION_NOT_FOR_CONTEXTUAL_SELECTION",
    }
    boundary = {
        "parser_observation": {
            "producer": "ACE + ERG through PyDelphin",
            "provides": "anchored lexical predicate and MRS argument structure",
            "provides_resource_sense_selection": False,
        },
        "lookup": {
            "inputs": ["ERG-derived lemma", "ERG-derived part of speech"],
            "resources": ["WordNet", "VerbNet", "PropBank", "FrameNet"],
            "semantics": "candidate enumeration only",
        },
        "mapping": {
            "resources": ["VerbNet member WN keys", "SemLink", "WordNet-SUMO"],
            "semantics": "typed edges between candidates, with unresolved endpoints retained",
        },
        "decision": {
            "performed": False,
            "required_component": (
                "a contextual lexical-semantic disambiguator and role/frame labeler "
                "that consumes parser evidence without collapsing alternatives"
            ),
        },
    }

    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("results.json", results),
        ("contrast-report.json", contrast_report),
        ("summary.json", summary),
        ("lookup-vs-mapping-vs-decision.json", boundary),
        ("raw/erg-analyses.json", erg_results),
    ):
        (output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    mapping_paths = [
        SUMO_ROOT / "WordNetMappings" / filename
        for filename in MAPPING_FILES.values()
    ]
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "adapter_version": ADAPTER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "ace": ace_version(args.ace),
        "erg": {
            "image": os.path.relpath(args.grammar, REPO_ROOT),
            "sha256": sha256_file(args.grammar),
            "label": "ERG (2018)",
        },
        "software_and_resource_versions": {
            "python": platform.python_version(),
            "nltk": nltk.__version__,
            "pydelphin": importlib.metadata.version("pydelphin"),
            "wordnet": wn.get_version(),
            "verbnet": vn.version,
            "propbank": "NLTK PropBank 1.0",
            "framenet": "1.7",
            "semlink_git_commit": subprocess.run(
                ["git", "-C", str(SEMLINK_ROOT), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "sumo_git_commit": subprocess.run(
                ["git", "-C", str(SUMO_ROOT), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
        },
        "resource_fingerprints": {
            str(path.relative_to(REPO_ROOT)): sha256_file(path)
            for path in [pb_vn_path, vn_fn_path, *mapping_paths]
        },
        "parameters": {
            "max_erg_results": args.max_results,
            "lexical_lookup_key": "ERG-derived lemma plus part of speech",
            "selection": "none",
            "scores_invented": False,
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"LEX-07: {len(results)} occurrences and {len(contrast_report)} contrasts validated")
    for result in results:
        counts = {
            key: len(value) for key, value in result["lookup_candidates"].items()
        }
        print(
            f"{result['id']:16} ERG={result['erg']['target_predicates'][0]} "
            f"WN={counts['wordnet']} VN={counts['verbnet']} "
            f"PB={counts['propbank']} FN={counts['framenet']} selected=0"
        )


if __name__ == "__main__":
    main()
