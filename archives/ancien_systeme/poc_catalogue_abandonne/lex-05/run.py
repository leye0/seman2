#!/usr/bin/env python3
"""Run LEX-05: audit SemLink 2 mappings against installed NLTK resources."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nltk
import polars as pl
from nltk.corpus import framenet as fn
from nltk.corpus import propbank, verbnet as vn, wordnet as wn
from nltk.corpus.reader.wordnet import WordNetError


POC_DIR = Path(__file__).resolve().parent
REPO_ROOT = POC_DIR.parent.parent
SEMLINK_ROOT = REPO_ROOT / ".local" / "share" / "semlink"
SEMLINK_VERSION = "2"
SEMLINK_EXPECTED_VERBNET_VERSION = "3.3"
SEMLINK_EXPECTED_PROPBANK_VERSION = "Unified PropBank"
FRAMENET_VERSION = "1.7"
ADAPTER_VERSION = "1"
SCHEMA_VERSION = "seman2.lexical-semlink-poc.v1"


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


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def rate_record(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "resolved": numerator,
        "applicable": denominator,
        "rate": ratio(numerator, denominator),
    }


def normalize_role(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def numeric_class_id(class_id: str) -> str:
    return class_id.split("-", 1)[1]


def class_ancestors(numeric_id: str) -> list[str]:
    pieces = numeric_id.split("-")
    return ["-".join(pieces[:index]) for index in range(1, len(pieces) + 1)]


def normalize_wordnet_key(key: str) -> str:
    # VerbNet 2.1 omits the final empty head-word fields from WordNet keys.
    key = key.lstrip("?")
    return key if key.endswith("::") else key + "::"


def resolve_wordnet_key(key: str) -> dict[str, Any]:
    normalized = normalize_wordnet_key(key)
    try:
        lemma = wn.lemma_from_key(normalized)
        return {
            "source_key": key,
            "normalized_key": normalized,
            "resolved": True,
            "lemma": lemma.name(),
            "synset": lemma.synset().name(),
            "synset_offset": lemma.synset().offset(),
            "part_of_speech": lemma.synset().pos(),
            "error": None,
        }
    except (ValueError, KeyError, WordNetError) as error:
        return {
            "source_key": key,
            "normalized_key": normalized,
            "resolved": False,
            "lemma": None,
            "synset": None,
            "synset_offset": None,
            "part_of_speech": None,
            "error": f"{type(error).__name__}: {error}",
        }


def build_resource_indexes() -> dict[str, Any]:
    propbank_roleset_rows = []
    propbank_argument_rows = []
    for roleset in propbank.rolesets():
        roleset_id = roleset.get("id")
        if not roleset_id:
            continue
        propbank_roleset_rows.append(
            {"pb_roleset": roleset_id, "pb_resolved": True}
        )
        for role in roleset.findall("roles/role"):
            number = role.get("n")
            if number is not None:
                propbank_argument_rows.append(
                    {
                        "pb_roleset": roleset_id,
                        "pb_argument": f"ARG{number}",
                    }
                )

    class_ids = {numeric_class_id(class_id): class_id for class_id in vn.classids()}
    verbnet_class_rows = [
        {
            "vn_class": numeric_id,
            "nltk_vn_class_id": class_id,
            "vn_class_resolved": True,
        }
        for numeric_id, class_id in class_ids.items()
    ]
    verbnet_roles: dict[str, set[str]] = {}
    for numeric_id in class_ids:
        verbnet_roles[numeric_id] = {
            normalize_role(role["type"])
            for ancestor in class_ancestors(numeric_id)
            if ancestor in class_ids
            for role in vn.themroles(class_ids[ancestor])
        }

    verbnet_member_rows = []
    member_details: dict[tuple[str, str], dict[str, Any]] = {}
    for numeric_id, class_id in class_ids.items():
        element = vn.vnclass(class_id)
        for member in element.findall("./MEMBERS/MEMBER"):
            lemma = member.get("name")
            wordnet_keys = member.get("wn", "").split()
            wordnet_senses = [resolve_wordnet_key(key) for key in wordnet_keys]
            detail = {
                "vn_class": numeric_id,
                "nltk_vn_class_id": class_id,
                "lemma": lemma,
                "wordnet_senses": wordnet_senses,
                "wordnet_key_count": len(wordnet_senses),
                "wordnet_resolved_key_count": sum(
                    item["resolved"] for item in wordnet_senses
                ),
            }
            member_details[(numeric_id, lemma)] = detail
            verbnet_member_rows.append(
                {
                    "vn_class": numeric_id,
                    "lemma": lemma,
                    "vn_member_resolved": True,
                    "wordnet_key_count": detail["wordnet_key_count"],
                    "wordnet_resolved_key_count": detail[
                        "wordnet_resolved_key_count"
                    ],
                }
            )

    framenet_frame_rows = []
    framenet_lu_rows = []
    framenet_fe_rows = []
    frame_details: dict[str, dict[str, Any]] = {}
    for frame in fn.frames():
        framenet_frame_rows.append(
            {"fn_frame": frame.name, "fn_frame_resolved": True}
        )
        lu_lemmas: set[str] = set()
        for lu in frame.lexUnit.values():
            lemma = lu.name.rsplit(".", 1)[0]
            lu_lemmas.add(lemma)
            lu_lemmas.add(lemma.replace(" ", "_"))
        for lemma in sorted(lu_lemmas):
            framenet_lu_rows.append(
                {
                    "fn_frame": frame.name,
                    "lemma": lemma,
                    "fn_lexical_unit_resolved": True,
                }
            )
        for frame_element in frame.FE.values():
            framenet_fe_rows.append(
                {
                    "fn_frame": frame.name,
                    "fn_frame_element_normalized": normalize_role(
                        frame_element.name
                    ),
                    "fn_frame_element": frame_element.name,
                }
            )
        frame_details[frame.name] = {
            "frame_id": frame.ID,
            "name": frame.name,
            "lexical_unit_count": len(frame.lexUnit),
            "frame_element_count": len(frame.FE),
        }

    return {
        "propbank_roleset_rows": propbank_roleset_rows,
        "propbank_argument_rows": propbank_argument_rows,
        "verbnet_class_rows": verbnet_class_rows,
        "verbnet_member_rows": verbnet_member_rows,
        "verbnet_member_details": member_details,
        "verbnet_roles": verbnet_roles,
        "framenet_frame_rows": framenet_frame_rows,
        "framenet_lu_rows": framenet_lu_rows,
        "framenet_fe_rows": framenet_fe_rows,
        "framenet_frame_details": frame_details,
    }


def parse_pb_vn_mappings(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "edge_id": stable_id(
                "semlink-pb-vn-edge:",
                {"pb_roleset": roleset, "vn_class": vn_class},
            ),
            "relation_type": "propbank_roleset_maps_to_verbnet_class",
            "pb_roleset": roleset,
            "lemma": roleset.rsplit(".", 1)[0],
            "vn_class": vn_class,
            "argument_mappings": [
                {
                    "relation_type": "propbank_argument_maps_to_verbnet_role",
                    "propbank_argument": argument,
                    "verbnet_role": role,
                }
                for argument, role in sorted(argument_mappings.items())
            ],
        }
        for roleset, vn_classes in sorted(data.items())
        for vn_class, argument_mappings in sorted(vn_classes.items())
    ]


def parse_vn_fn_mappings(data: dict[str, Any]) -> list[dict[str, Any]]:
    key_pattern = re.compile(r"^([0-9][0-9.\-]*)-(.+)$")
    records = []
    for key, frames in sorted(data.items()):
        match = key_pattern.fullmatch(key)
        if match is None:
            raise RuntimeError(f"Unsupported VN-FN key: {key!r}")
        vn_class, lemma = match.groups()
        for frame in sorted(frames):
            records.append(
                {
                    "edge_id": stable_id(
                        "semlink-vn-fn-edge:",
                        {"vn_class": vn_class, "lemma": lemma, "frame": frame},
                    ),
                    "relation_type": "verbnet_class_member_maps_to_framenet_frame",
                    "vn_class": vn_class,
                    "lemma": lemma,
                    "fn_frame": frame,
                }
            )
    return records


def parse_dependency(token: str) -> dict[str, Any]:
    pointer, label_and_mapping = token.split("-", 1)
    if "=" in label_and_mapping:
        label, mapping_text = label_and_mapping.split("=", 1)
        mapped_roles = mapping_text.split(";")
        verbnet_role = mapped_roles[0]
        framenet_frame_element = mapped_roles[1] if len(mapped_roles) > 1 else None
    else:
        label = label_and_mapping
        verbnet_role = None
        framenet_frame_element = None
    return {
        "pointer": pointer,
        "propbank_label": label,
        "verbnet_role": verbnet_role,
        "framenet_frame_element": framenet_frame_element,
    }


def parse_instance_line(line: str, row_number: int) -> dict[str, Any]:
    fields = line.split()
    if len(fields) < 8:
        raise RuntimeError(f"Malformed SemLink instance line {row_number}")
    raw_frame = fields[5]
    if raw_frame == "IN":
        frame_status = "indeterminate_multiple_mappings"
        frame = None
    elif raw_frame == "NF":
        frame_status = "no_mapping"
        frame = None
    elif raw_frame == "None":
        frame_status = "not_annotated"
        frame = None
    else:
        frame_status = "assigned"
        frame = raw_frame
    dependencies = [token for token in fields[8:] if token not in {"-----", "None"}]
    locator = {
        "source_file": Path(fields[0]).name,
        "sentence_number": int(fields[1]),
        "token_number": int(fields[2]),
    }
    return {
        "instance_id": stable_id("semlink-instance:", locator),
        "row_number": row_number,
        **locator,
        "lemma": fields[3],
        "verbnet_class": None if fields[4] == "None" else fields[4],
        "framenet_frame": frame,
        "framenet_frame_raw": raw_frame,
        "framenet_assignment_status": frame_status,
        "propbank_roleset": None if fields[6] == "None" else fields[6],
        "ontonotes_sense_group": None if fields[7] == "None" else fields[7],
        "dependencies": [parse_dependency(token) for token in dependencies],
        "raw_line": line.rstrip("\n"),
    }


def dataframe(rows: list[dict[str, Any]], columns: list[str]) -> pl.DataFrame:
    return pl.DataFrame([{key: row.get(key) for key in columns} for row in rows])


def non_null_count(frame: pl.DataFrame, column: str) -> int:
    return int(frame.select(pl.col(column).is_not_null().sum()).item())


def true_count(frame: pl.DataFrame, column: str) -> int:
    return int(frame.select(pl.col(column).fill_null(False).sum()).item())


def audit_joins(
    pb_vn_edges: list[dict[str, Any]],
    vn_fn_edges: list[dict[str, Any]],
    instances: list[dict[str, Any]],
    indexes: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    pb_df = dataframe(
        indexes["propbank_roleset_rows"], ["pb_roleset", "pb_resolved"]
    ).unique()
    vn_class_df = dataframe(
        indexes["verbnet_class_rows"],
        ["vn_class", "nltk_vn_class_id", "vn_class_resolved"],
    ).unique()
    vn_member_df = dataframe(
        indexes["verbnet_member_rows"],
        [
            "vn_class",
            "lemma",
            "vn_member_resolved",
            "wordnet_key_count",
            "wordnet_resolved_key_count",
        ],
    ).unique(subset=["vn_class", "lemma"])
    fn_frame_df = dataframe(
        indexes["framenet_frame_rows"], ["fn_frame", "fn_frame_resolved"]
    ).unique()
    fn_lu_df = dataframe(
        indexes["framenet_lu_rows"],
        ["fn_frame", "lemma", "fn_lexical_unit_resolved"],
    ).unique()
    pb_argument_df = dataframe(
        indexes["propbank_argument_rows"], ["pb_roleset", "pb_argument"]
    ).unique().with_columns(pl.lit(True).alias("pb_argument_resolved"))
    vn_role_df = pl.DataFrame(
        [
            {
                "vn_class": vn_class,
                "vn_role_normalized": role,
                "vn_role_resolved": True,
            }
            for vn_class, roles in indexes["verbnet_roles"].items()
            for role in roles
        ]
    ).unique()
    fn_fe_df = dataframe(
        indexes["framenet_fe_rows"],
        ["fn_frame", "fn_frame_element_normalized"],
    ).unique().with_columns(pl.lit(True).alias("fn_frame_element_resolved"))

    pb_edge_df = dataframe(
        pb_vn_edges,
        ["pb_roleset", "lemma", "vn_class"],
    )
    pb_edge_audit = (
        pb_edge_df.join(pb_df, on="pb_roleset", how="left")
        .join(vn_class_df, on="vn_class", how="left")
        .join(vn_member_df, on=["vn_class", "lemma"], how="left")
    )
    pb_edge_count = pb_edge_audit.height
    pb_resolved = true_count(pb_edge_audit, "pb_resolved")
    vn_class_resolved = true_count(pb_edge_audit, "vn_class_resolved")
    vn_member_resolved = true_count(pb_edge_audit, "vn_member_resolved")
    full_pb_vn_resolution = int(
        pb_edge_audit.select(
            (
                pl.col("pb_resolved").fill_null(False)
                & pl.col("vn_member_resolved").fill_null(False)
            ).sum()
        ).item()
    )
    with_wordnet_keys = int(
        pb_edge_audit.select((pl.col("wordnet_key_count").fill_null(0) > 0).sum())
        .item()
    )
    all_wordnet_keys_resolved = int(
        pb_edge_audit.select(
            (
                (pl.col("wordnet_key_count").fill_null(0) > 0)
                & (
                    pl.col("wordnet_key_count")
                    == pl.col("wordnet_resolved_key_count")
                )
            ).sum()
        ).item()
    )

    vn_fn_df = dataframe(vn_fn_edges, ["vn_class", "lemma", "fn_frame"])
    vn_fn_audit = (
        vn_fn_df.join(vn_class_df, on="vn_class", how="left")
        .join(vn_member_df, on=["vn_class", "lemma"], how="left")
        .join(fn_frame_df, on="fn_frame", how="left")
        .join(fn_lu_df, on=["fn_frame", "lemma"], how="left")
    )
    vn_fn_count = vn_fn_audit.height
    vn_fn_full = int(
        vn_fn_audit.select(
            (
                pl.col("vn_member_resolved").fill_null(False)
                & pl.col("fn_lexical_unit_resolved").fill_null(False)
            ).sum()
        ).item()
    )

    pb_vn_pair_df = pb_edge_df.select("pb_roleset", "vn_class").unique().with_columns(
        pl.lit(True).alias("pb_vn_mapping_agrees")
    )
    vn_fn_triple_df = vn_fn_df.unique().with_columns(
        pl.lit(True).alias("vn_fn_mapping_agrees")
    )
    instance_df = dataframe(
        instances,
        [
            "row_number",
            "lemma",
            "propbank_roleset",
            "verbnet_class",
            "framenet_frame",
            "framenet_frame_raw",
        ],
    ).rename(
        {
            "propbank_roleset": "pb_roleset",
            "verbnet_class": "vn_class",
            "framenet_frame": "fn_frame",
        }
    )
    instance_audit = (
        instance_df.join(pb_df, on="pb_roleset", how="left")
        .join(vn_class_df, on="vn_class", how="left")
        .join(vn_member_df, on=["vn_class", "lemma"], how="left")
        .join(fn_frame_df, on="fn_frame", how="left")
        .join(fn_lu_df, on=["fn_frame", "lemma"], how="left")
        .join(pb_vn_pair_df, on=["pb_roleset", "vn_class"], how="left")
        .join(vn_fn_triple_df, on=["vn_class", "lemma", "fn_frame"], how="left")
    )
    pb_present = non_null_count(instance_audit, "pb_roleset")
    vn_present = non_null_count(instance_audit, "vn_class")
    fn_assigned = non_null_count(instance_audit, "fn_frame")
    pb_vn_applicable = int(
        instance_audit.select(
            (pl.col("pb_roleset").is_not_null() & pl.col("vn_class").is_not_null()).sum()
        ).item()
    )
    vn_fn_applicable = int(
        instance_audit.select(
            (pl.col("vn_class").is_not_null() & pl.col("fn_frame").is_not_null()).sum()
        ).item()
    )

    role_link_rows = [
        {
            "pb_roleset": instance["propbank_roleset"],
            "pb_argument": dependency["propbank_label"],
            "vn_class": instance["verbnet_class"],
            "vn_role_normalized": normalize_role(dependency["verbnet_role"]),
            "fn_frame": instance["framenet_frame"],
            "fn_frame_element_normalized": (
                normalize_role(dependency["framenet_frame_element"])
                if dependency["framenet_frame_element"]
                else None
            ),
        }
        for instance in instances
        for dependency in instance["dependencies"]
        if dependency["verbnet_role"] is not None
    ]
    role_link_df = pl.DataFrame(role_link_rows)
    role_link_audit = (
        role_link_df.join(
            pb_argument_df, on=["pb_roleset", "pb_argument"], how="left"
        )
        .join(vn_role_df, on=["vn_class", "vn_role_normalized"], how="left")
        .join(
            fn_fe_df,
            on=["fn_frame", "fn_frame_element_normalized"],
            how="left",
        )
    )
    fn_fe_applicable = int(
        role_link_audit.select(
            (
                pl.col("fn_frame").is_not_null()
                & pl.col("fn_frame_element_normalized").is_not_null()
            ).sum()
        ).item()
    )

    join_rates = {
        "engine": {"name": "Polars", "version": pl.__version__},
        "mapping_tables": {
            "propbank_to_verbnet_edges": pb_edge_count,
            "propbank_roleset_against_installed_propbank": rate_record(
                pb_resolved, pb_edge_count
            ),
            "verbnet_class_against_installed_verbnet": rate_record(
                vn_class_resolved, pb_edge_count
            ),
            "verbnet_class_member_against_installed_verbnet": rate_record(
                vn_member_resolved, pb_edge_count
            ),
            "full_propbank_verbnet_edge_resolution": rate_record(
                full_pb_vn_resolution, pb_edge_count
            ),
            "verbnet_members_with_wordnet_keys": rate_record(
                with_wordnet_keys, pb_edge_count
            ),
            "verbnet_members_with_all_wordnet_keys_resolved": rate_record(
                all_wordnet_keys_resolved, pb_edge_count
            ),
            "verbnet_to_framenet_edges": vn_fn_count,
            "vn_fn_verbnet_class_resolution": rate_record(
                true_count(vn_fn_audit, "vn_class_resolved"), vn_fn_count
            ),
            "vn_fn_verbnet_member_resolution": rate_record(
                true_count(vn_fn_audit, "vn_member_resolved"), vn_fn_count
            ),
            "vn_fn_frame_resolution": rate_record(
                true_count(vn_fn_audit, "fn_frame_resolved"), vn_fn_count
            ),
            "vn_fn_frame_lexical_unit_resolution": rate_record(
                true_count(vn_fn_audit, "fn_lexical_unit_resolved"), vn_fn_count
            ),
            "full_verbnet_framenet_edge_resolution": rate_record(
                vn_fn_full, vn_fn_count
            ),
        },
        "instances": {
            "total": instance_audit.height,
            "propbank_assignment_present": pb_present,
            "propbank_assignment_resolved": rate_record(
                true_count(instance_audit, "pb_resolved"), pb_present
            ),
            "verbnet_assignment_present": vn_present,
            "verbnet_class_resolved": rate_record(
                true_count(instance_audit, "vn_class_resolved"), vn_present
            ),
            "verbnet_class_member_resolved": rate_record(
                true_count(instance_audit, "vn_member_resolved"), vn_present
            ),
            "framenet_frame_assigned": fn_assigned,
            "framenet_frame_resolved": rate_record(
                true_count(instance_audit, "fn_frame_resolved"), fn_assigned
            ),
            "framenet_frame_lexical_unit_resolved": rate_record(
                true_count(instance_audit, "fn_lexical_unit_resolved"), fn_assigned
            ),
            "assigned_pb_vn_pair_present_in_mapping_table": rate_record(
                true_count(instance_audit, "pb_vn_mapping_agrees"), pb_vn_applicable
            ),
            "assigned_vn_fn_triple_present_in_mapping_table": rate_record(
                true_count(instance_audit, "vn_fn_mapping_agrees"), vn_fn_applicable
            ),
        },
        "instance_role_links": {
            "propbank_argument_to_verbnet_role_count": role_link_audit.height,
            "propbank_argument_against_installed_propbank": rate_record(
                true_count(role_link_audit, "pb_argument_resolved"),
                role_link_audit.height,
            ),
            "verbnet_role_against_installed_verbnet": rate_record(
                true_count(role_link_audit, "vn_role_resolved"),
                role_link_audit.height,
            ),
            "links_with_framenet_frame_and_element": fn_fe_applicable,
            "framenet_element_against_installed_framenet": rate_record(
                true_count(role_link_audit, "fn_frame_element_resolved"),
                fn_fe_applicable,
            ),
        },
    }
    return join_rates, {
        "pb_edge_audit": pb_edge_audit,
        "vn_fn_audit": vn_fn_audit,
        "instance_audit": instance_audit,
        "role_link_audit": role_link_audit,
    }


def enrich_pb_vn_edge(
    edge: dict[str, Any], indexes: dict[str, Any], vn_fn_by_key: dict[tuple[str, str], list[dict[str, Any]]]
) -> dict[str, Any]:
    roleset_ids = {row["pb_roleset"] for row in indexes["propbank_roleset_rows"]}
    pb_arguments = {
        (row["pb_roleset"], row["pb_argument"])
        for row in indexes["propbank_argument_rows"]
    }
    class_rows = {
        row["vn_class"]: row for row in indexes["verbnet_class_rows"]
    }
    member = indexes["verbnet_member_details"].get(
        (edge["vn_class"], edge["lemma"])
    )
    valid_roles = indexes["verbnet_roles"].get(edge["vn_class"], set())
    argument_mappings = [
        {
            **mapping,
            "installed_propbank_argument_resolved": (
                edge["pb_roleset"], mapping["propbank_argument"]
            )
            in pb_arguments,
            "installed_verbnet_role_resolved": normalize_role(
                mapping["verbnet_role"]
            )
            in valid_roles,
        }
        for mapping in edge["argument_mappings"]
    ]
    fn_edges = vn_fn_by_key.get((edge["vn_class"], edge["lemma"]), [])
    frames = indexes["framenet_frame_details"]
    return {
        **edge,
        "argument_mappings": argument_mappings,
        "installed_propbank_roleset_resolved": edge["pb_roleset"] in roleset_ids,
        "installed_verbnet_class_id": (
            class_rows.get(edge["vn_class"], {}).get("nltk_vn_class_id")
        ),
        "installed_verbnet_class_resolved": edge["vn_class"] in class_rows,
        "installed_verbnet_member_resolved": member is not None,
        "wordnet_link": {
            "relation_type": "verbnet_member_has_wordnet_sense_key",
            "source": "installed NLTK VerbNet member metadata",
            "senses": member["wordnet_senses"] if member else [],
        },
        "framenet_candidates": [
            {
                **fn_edge,
                "installed_frame_resolved": fn_edge["fn_frame"] in frames,
                "installed_frame": frames.get(fn_edge["fn_frame"]),
            }
            for fn_edge in fn_edges
        ],
    }


def enrich_instance(instance: dict[str, Any], indexes: dict[str, Any]) -> dict[str, Any]:
    valid_roles = indexes["verbnet_roles"].get(instance["verbnet_class"], set())
    frame_elements = {
        (row["fn_frame"], row["fn_frame_element_normalized"])
        for row in indexes["framenet_fe_rows"]
    }
    dependencies = []
    for dependency in instance["dependencies"]:
        vn_role = dependency["verbnet_role"]
        fn_fe = dependency["framenet_frame_element"]
        dependencies.append(
            {
                **dependency,
                "verbnet_role_relation_type": (
                    "propbank_argument_maps_to_verbnet_role" if vn_role else None
                ),
                "installed_verbnet_role_resolved": (
                    normalize_role(vn_role) in valid_roles if vn_role else None
                ),
                "framenet_element_relation_type": (
                    "verbnet_role_maps_to_framenet_frame_element" if fn_fe else None
                ),
                "installed_framenet_element_resolved": (
                    (instance["framenet_frame"], normalize_role(fn_fe))
                    in frame_elements
                    if fn_fe and instance["framenet_frame"]
                    else None
                ),
            }
        )
    return {**instance, "dependencies": dependencies}


def validate(fixtures: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
    if len(fixtures) != len(results):
        raise RuntimeError("LEX-05 fixture coverage is incomplete")
    for fixture, result in zip(fixtures, results, strict=True):
        candidates = result["propbank_to_verbnet_candidates"]
        if bool(candidates) != fixture["expected_mapping_present"]:
            raise RuntimeError(f"Wrong mapping presence: {fixture['id']}")
        if result["installed_propbank_roleset_resolved"] != fixture[
            "expected_installed_propbank_resolution"
        ]:
            raise RuntimeError(f"Wrong PropBank resolution: {fixture['id']}")
        actual_vn = {item["vn_class"] for item in candidates}
        if set(fixture.get("expected_verbnet_classes", [])) != actual_vn:
            raise RuntimeError(f"Wrong VN candidates: {fixture['id']}")
        actual_fn = {
            frame["fn_frame"]
            for candidate in candidates
            for frame in candidate["framenet_candidates"]
        }
        if set(fixture.get("expected_framenet_frames", [])) != actual_fn:
            raise RuntimeError(f"Wrong FN candidates: {fixture['id']}")
        if fixture.get("expected_multiple_verbnet_candidates") and len(candidates) < 2:
            raise RuntimeError(f"Missing multiple VN candidates: {fixture['id']}")
        if fixture.get("expected_multiple_framenet_candidates") and len(actual_fn) < 2:
            raise RuntimeError(f"Missing multiple FN candidates: {fixture['id']}")
        unresolved = fixture.get("expected_unresolved_verbnet_class")
        if unresolved:
            candidate = next(item for item in candidates if item["vn_class"] == unresolved)
            if candidate["installed_verbnet_class_resolved"]:
                raise RuntimeError(f"Expected unresolved VN class: {fixture['id']}")
        minimum_wordnet = fixture.get("expected_wordnet_key_minimum", 0)
        wordnet_senses = [
            sense
            for candidate in candidates
            for sense in candidate["wordnet_link"]["senses"]
        ]
        if len(wordnet_senses) < minimum_wordnet or not all(
            sense["resolved"] for sense in wordnet_senses
        ):
            raise RuntimeError(f"Wrong WordNet resolution: {fixture['id']}")
        instance = result["instance"]
        if "instance" in fixture:
            if instance is None:
                raise RuntimeError(f"Missing instance: {fixture['id']}")
            if fixture.get("expected_instance_frame") != instance[
                "framenet_frame"
            ] and fixture.get("expected_instance_frame") is not None:
                raise RuntimeError(f"Wrong instance frame: {fixture['id']}")
            if fixture.get("expected_instance_frame_status") != instance[
                "framenet_frame_raw"
            ] and fixture.get("expected_instance_frame_status") is not None:
                raise RuntimeError(f"Wrong frame status: {fixture['id']}")
            if fixture.get("expected_instance_verbnet_class") != instance[
                "verbnet_class"
            ] and fixture.get("expected_instance_verbnet_class") is not None:
                raise RuntimeError(f"Wrong instance VN class: {fixture['id']}")
        elif instance is not None:
            raise RuntimeError(f"Unexpected instance: {fixture['id']}")


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    paths = {
        "instances/semlink-2": SEMLINK_ROOT / "instances" / "semlink-2",
        "instances/pb-vn2.json": SEMLINK_ROOT / "instances" / "pb-vn2.json",
        "instances/vn-fn2.json": SEMLINK_ROOT / "instances" / "vn-fn2.json",
        "other_resources/VN-FNRoleMapping.txt": (
            SEMLINK_ROOT / "other_resources" / "VN-FNRoleMapping.txt"
        ),
    }
    for path in paths.values():
        if not path.is_file():
            raise RuntimeError(f"Missing SemLink resource: {path}")

    pb_vn_data = json.loads(paths["instances/pb-vn2.json"].read_text())
    vn_fn_data = json.loads(paths["instances/vn-fn2.json"].read_text())
    pb_vn_edges = parse_pb_vn_mappings(pb_vn_data)
    vn_fn_edges = parse_vn_fn_mappings(vn_fn_data)
    instances = [
        parse_instance_line(line, row_number)
        for row_number, line in enumerate(
            paths["instances/semlink-2"].open(encoding="utf-8"), start=1
        )
    ]
    indexes = build_resource_indexes()
    join_rates, _audit_frames = audit_joins(
        pb_vn_edges, vn_fn_edges, instances, indexes
    )

    pb_vn_by_roleset: dict[str, list[dict[str, Any]]] = {}
    for edge in pb_vn_edges:
        pb_vn_by_roleset.setdefault(edge["pb_roleset"], []).append(edge)
    vn_fn_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in vn_fn_edges:
        vn_fn_by_key.setdefault((edge["vn_class"], edge["lemma"]), []).append(edge)
    instance_by_locator = {
        (
            instance["source_file"],
            instance["sentence_number"],
            instance["token_number"],
        ): instance
        for instance in instances
    }
    installed_rolesets = {
        row["pb_roleset"] for row in indexes["propbank_roleset_rows"]
    }

    results = []
    selected_raw_lines = []
    selected_mappings = []
    for fixture in fixtures:
        roleset = fixture["propbank_roleset"]
        candidates = [
            enrich_pb_vn_edge(edge, indexes, vn_fn_by_key)
            for edge in pb_vn_by_roleset.get(roleset, [])
        ]
        locator = fixture.get("instance")
        instance = None
        if locator:
            key = (
                locator["source_file"],
                locator["sentence_number"],
                locator["token_number"],
            )
            native_instance = instance_by_locator.get(key)
            if native_instance is None:
                raise RuntimeError(f"Missing selected SemLink instance: {fixture['id']}")
            instance = enrich_instance(native_instance, indexes)
            selected_raw_lines.append(
                {"fixture": fixture["id"], "line": native_instance["raw_line"]}
            )
        result = {
            **fixture,
            "installed_propbank_roleset_resolved": roleset in installed_rolesets,
            "propbank_to_verbnet_candidates": candidates,
            "candidate_count": len(candidates),
            "instance": instance,
            "mapping_interpretation": {
                "candidate_edges_are_equivalences": False,
                "candidate_selection_performed": False,
                "wordnet_link_source": (
                    "installed VerbNet member metadata, not a direct SemLink column"
                ),
                "propbank_to_framenet_path": "PropBank -> VerbNet -> FrameNet",
            },
        }
        results.append(result)
        selected_mappings.append(
            {
                "fixture": fixture["id"],
                "pb_vn_source": pb_vn_data.get(roleset),
                "vn_fn_source": {
                    f"{candidate['vn_class']}-{candidate['lemma']}": vn_fn_data.get(
                        f"{candidate['vn_class']}-{candidate['lemma']}"
                    )
                    for candidate in candidates
                },
            }
        )

    validate(fixtures, results)

    instance_frame_status_counts = Counter(
        instance["framenet_frame_raw"] for instance in instances
    )
    mapped_dependencies = [
        dependency
        for instance in instances
        for dependency in instance["dependencies"]
        if dependency["verbnet_role"] is not None
    ]
    dependencies_with_fn = [
        dependency
        for dependency in mapped_dependencies
        if dependency["framenet_frame_element"] is not None
    ]
    pb_vn_key_counts = Counter(edge["pb_roleset"] for edge in pb_vn_edges)
    vn_fn_key_counts = Counter(
        (edge["vn_class"], edge["lemma"]) for edge in vn_fn_edges
    )
    summary = {
        "fixture_count": len(fixtures),
        "instance_count": len(instances),
        "pb_vn_roleset_key_count": len(pb_vn_data),
        "pb_vn_edge_count": len(pb_vn_edges),
        "pb_vn_keys_with_multiple_classes": sum(
            count > 1 for count in pb_vn_key_counts.values()
        ),
        "vn_fn_class_member_key_count": len(vn_fn_data),
        "vn_fn_edge_count": len(vn_fn_edges),
        "vn_fn_keys_with_multiple_frames": sum(
            count > 1 for count in vn_fn_key_counts.values()
        ),
        "instance_argument_mapping_count": len(mapped_dependencies),
        "instance_argument_mapping_with_framenet_fe_count": len(
            dependencies_with_fn
        ),
        "installed_nltk_versions": {
            "nltk": nltk.__version__,
            "verbnet": vn.version,
            "wordnet": wn.get_version(),
            "propbank": "1.0 corpus distributed by NLTK",
            "framenet": FRAMENET_VERSION,
            "polars": pl.__version__,
        },
        "semlink_declared_targets": {
            "verbnet": SEMLINK_EXPECTED_VERBNET_VERSION,
            "propbank": SEMLINK_EXPECTED_PROPBANK_VERSION,
            "framenet": FRAMENET_VERSION,
        },
        "version_alignment": {
            "verbnet": vn.version == SEMLINK_EXPECTED_VERBNET_VERSION,
            "propbank": False,
            "framenet": True,
        },
        "verdict": "PARTIAL_DUE_TO_INSTALLED_PROPBANK_AND_VERBNET_VERSION_MISMATCH",
    }
    inventory = {
        "instance_field_presence": {
            "propbank": sum(
                instance["propbank_roleset"] is not None for instance in instances
            ),
            "verbnet": sum(
                instance["verbnet_class"] is not None for instance in instances
            ),
            "framenet_assigned": sum(
                instance["framenet_frame"] is not None for instance in instances
            ),
            "ontonotes_group": sum(
                instance["ontonotes_sense_group"] is not None
                for instance in instances
            ),
        },
        "framenet_raw_value_counts": dict(
            sorted(instance_frame_status_counts.items())
        ),
        "framenet_special_markers": {
            "IN": "indeterminate: the VN-FN key has multiple frame mappings",
            "NF": "no frame mapping produced by the SemLink update procedure",
            "None": "no FrameNet annotation stored on the instance",
        },
        "installed_resource_key_counts": {
            "propbank_distinct_roleset_ids": len(installed_rolesets),
            "verbnet_classes": len(indexes["verbnet_class_rows"]),
            "verbnet_class_member_pairs": len(indexes["verbnet_member_rows"]),
            "framenet_frames": len(indexes["framenet_frame_rows"]),
            "framenet_frame_lemma_pairs": len(indexes["framenet_lu_rows"]),
        },
        "legacy_vn_fn_role_mapping": {
            "path": "other_resources/VN-FNRoleMapping.txt",
            "status": (
                "available but dated 2006 and not merged into current SemLink 2 "
                "lexical edge joins"
            ),
        },
    }
    resource_boundary = {
        "mapping_lookup": {
            "operation": (
                "lookup stored PB-VN and VN-FN candidate edges and instance role links"
            ),
            "selects_a_sense_for_new_text": False,
            "relation_semantics": "typed mapping candidates, not identity",
        },
        "wordnet": {
            "direct_semlink_mapping_column": False,
            "link_path": "SemLink VN class/member -> installed VerbNet WN key -> WordNet synset",
            "normalization": (
                "append the two omitted empty sense-key fields (::) before NLTK lookup"
            ),
        },
        "instance_annotations": {
            "source": "existing OntoNotes/WSJ predicates distributed by SemLink",
            "new_text_annotation_performed": False,
        },
        "version_constraint": {
            "semlink_targets": (
                "VerbNet 3.3, Unified PropBank, and FrameNet 1.7"
            ),
            "installed": (
                f"VerbNet {vn.version}, NLTK PropBank 1.0, FrameNet {FRAMENET_VERSION}"
            ),
            "effect": "unresolved keys remain explicit and lower join rates",
        },
    }

    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("results.json", results),
        ("summary.json", summary),
        ("join-rates.json", join_rates),
        ("corpus-inventory.json", inventory),
        ("resource-vs-inference.json", resource_boundary),
        ("raw/selected-instance-lines.json", selected_raw_lines),
        ("raw/selected-mappings.json", selected_mappings),
    ):
        (output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    commit = subprocess.run(
        ["git", "-C", str(SEMLINK_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "adapter_version": ADAPTER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "semlink_version": SEMLINK_VERSION,
        "semlink_git_commit": commit,
        "resource_files": {
            name: {"path": str(path), "sha256": sha256_file(path)}
            for name, path in paths.items()
        },
        "software_versions": {
            "python": platform.python_version(),
            "nltk": nltk.__version__,
            "polars": pl.__version__,
            "verbnet_resource": vn.version,
            "wordnet_resource": wn.get_version(),
            "framenet_resource": FRAMENET_VERSION,
        },
        "parameters": {
            "join_engine": "Polars left joins on exact native keys",
            "pb_vn_join": ["pb_roleset", "vn_class", "lemma"],
            "vn_fn_join": ["vn_class", "lemma", "fn_frame"],
            "wordnet_join": "normalized VerbNet member WN sense key",
            "automatic_occurrence_alignment": False,
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"LEX-05: {len(results)} fixtures validated")
    print(
        f"SemLink instances: {len(instances)}; PB-VN edges: {len(pb_vn_edges)}; "
        f"VN-FN edges: {len(vn_fn_edges)}"
    )
    print(
        "version alignment: VerbNet "
        f"{vn.version}/3.3 mismatch; PropBank 1.0/Unified mismatch; "
        "FrameNet 1.7 aligned"
    )


if __name__ == "__main__":
    main()
