#!/usr/bin/env python3
"""Run NLP-04: establish DELPH-IN anchoring and offset conventions."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delphin import ace, dmrs, eds, mrs


POC_DIR = Path(__file__).resolve().parent
REPO_ROOT = POC_DIR.parents[1]
DEFAULT_ACE = REPO_ROOT / ".local/bin/ace"
DEFAULT_GRAMMAR = REPO_ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
DEFAULT_MAX_RESULTS = 10
TOKEN_RE = re.compile(
    r'\((?P<id>\d+),\s*(?P<start_vertex>\d+),\s*(?P<end_vertex>\d+),\s*'
    r'<(?P<from>\d+):(?P<to>\d+)>,\s*\d+,\s*"(?P<form>(?:[^"\\]|\\.)*)"'
    r',\s*\d+,\s*"[^"]*"(?:,\s*"(?P<pos>[^"]+)"\s+'
    r'(?P<probability>[0-9.]+))?\)'
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utf8_offset(text: str, codepoint_offset: int) -> int:
    return len(text[:codepoint_offset].encode("utf-8"))


def utf16_offset(text: str, codepoint_offset: int) -> int:
    return len(text[:codepoint_offset].encode("utf-16-le")) // 2


def approximate_grapheme_offset(text: str, codepoint_offset: int) -> int:
    """Count base characters plus combining marks as one display unit."""
    count = 0
    for character in text[:codepoint_offset]:
        if not unicodedata.combining(character):
            count += 1
    return count


def parse_tokens(raw: str, source: str) -> list[dict[str, Any]]:
    tokens = []
    for match in TOKEN_RE.finditer(raw):
        item = match.groupdict()
        start = int(item["from"])
        end = int(item["to"])
        form = json.loads(f'"{item["form"]}"')
        source_slice = source[start:end]
        tokens.append(
            {
                "id": int(item["id"]),
                "vertices": [int(item["start_vertex"]), int(item["end_vertex"])],
                "charspan": [start, end],
                "source_slice": source_slice,
                "form": form,
                "form_matches_source_slice": form == source_slice,
                "pos": item["pos"],
                "pos_probability": (
                    float(item["probability"])
                    if item["probability"] is not None
                    else None
                ),
            }
        )
    return tokens


def merged_spans(spans: list[list[int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return merged


def residual_spans(source: str, covered: list[list[int]]) -> list[dict[str, Any]]:
    residual = []
    cursor = 0
    for start, end in merged_spans(covered):
        if cursor < start:
            residual.append(
                {"charspan": [cursor, start], "source_slice": source[cursor:start]}
            )
        cursor = max(cursor, end)
    if cursor < len(source):
        residual.append(
            {"charspan": [cursor, len(source)], "source_slice": source[cursor:]}
        )
    return residual


def source_coverage(source: str, covered: list[list[int]]) -> dict[str, Any]:
    merged = merged_spans(covered)
    residual = residual_spans(source, merged)
    segments = [
        {"kind": "covered", "charspan": span, "source_slice": source[slice(*span)]}
        for span in merged
    ] + [{"kind": "residual", **item} for item in residual]
    segments.sort(key=lambda item: item["charspan"])
    address_count = [0] * len(source)
    for start, end in (item["charspan"] for item in segments):
        for index in range(start, end):
            address_count[index] += 1
    reassembled = "".join(item["source_slice"] for item in segments)
    return {
        "covered_charspans": merged,
        "residual_spans": residual,
        "ordered_partition": segments,
        "source_fully_addressable": all(count == 1 for count in address_count),
        "reassembled_source": reassembled,
        "source_text_preserved": reassembled == source,
    }


def semantic_anchoring(m: Any, source: str) -> dict[str, Any]:
    predications = []
    predication_by_id = {}
    for ep in m.rels:
        direct = ep.lnk is not None and ep.cfrom >= 0 and ep.cto >= ep.cfrom
        item = {
            "id": ep.id,
            "predicate": ep.predicate,
            "label": ep.label,
            "arguments": dict(ep.args),
            "directly_anchored": direct,
            "charspan": [ep.cfrom, ep.cto] if direct else None,
            "source_slice": source[ep.cfrom : ep.cto] if direct else None,
        }
        predications.append(item)
        predication_by_id[ep.id] = item

    intrinsic: dict[str, list[str]] = {}
    labels: dict[str, list[str]] = {}
    references: dict[str, list[dict[str, str]]] = {}
    for ep in m.rels:
        labels.setdefault(ep.label, []).append(ep.id)
        if ep.args.get("ARG0"):
            intrinsic.setdefault(ep.args["ARG0"], []).append(ep.id)
        for role, target in ep.args.items():
            if role != "CARG":
                references.setdefault(target, []).append(
                    {"predication_id": ep.id, "role": role}
                )

    def support(variable: str) -> dict[str, Any]:
        predication_ids = set(intrinsic.get(variable, []))
        predication_ids.update(labels.get(variable, []))
        predication_ids.update(
            reference["predication_id"] for reference in references.get(variable, [])
        )
        spans = [
            predication_by_id[predication_id]["charspan"]
            for predication_id in predication_ids
            if predication_by_id[predication_id]["charspan"] is not None
        ]
        if variable == m.top and not spans:
            spans = [[0, len(source)]]
        return {
            "predication_ids": sorted(predication_ids),
            "charspans": sorted({tuple(span) for span in spans}),
            "global_source_support": variable == m.top and not predication_ids,
        }

    variables = []
    for variable, properties in m.variables.items():
        indirect = support(variable)
        variables.append(
            {
                "id": variable,
                "type": variable[0],
                "properties": properties,
                "direct_lnk": None,
                "indirect_support": indirect,
                "coverage": "indirect" if indirect["charspans"] else "none",
            }
        )

    roles = []
    for ep in m.rels:
        source_item = predication_by_id[ep.id]
        for role, target in ep.args.items():
            if role == "CARG":
                continue
            target_support = support(target)
            spans = []
            if source_item["charspan"] is not None:
                spans.append(source_item["charspan"])
            spans.extend(target_support["charspans"])
            roles.append(
                {
                    "source_predication_id": ep.id,
                    "role": role,
                    "target": target,
                    "direct_lnk": None,
                    "source_charspan": source_item["charspan"],
                    "target_support_charspans": target_support["charspans"],
                    "derived_support_charspan": (
                        [min(span[0] for span in spans), max(span[1] for span in spans)]
                        if spans
                        else None
                    ),
                }
            )

    directly_anchored = sum(item["directly_anchored"] for item in predications)
    indirectly_covered = sum(item["coverage"] == "indirect" for item in variables)
    return {
        "predications": predications,
        "variables_and_handles": variables,
        "role_relations": roles,
        "coverage": {
            "predications_total": len(predications),
            "predications_directly_anchored": directly_anchored,
            "predications_without_direct_anchor": len(predications) - directly_anchored,
            "variables_and_handles_total": len(variables),
            "variables_and_handles_directly_anchored": 0,
            "variables_and_handles_indirectly_covered": indirectly_covered,
            "variables_and_handles_without_support": len(variables) - indirectly_covered,
            "role_relations_total": len(roles),
            "role_relations_with_derived_support": sum(
                role["derived_support_charspan"] is not None for role in roles
            ),
        },
    }


def eds_anchoring(e: Any, source: str) -> dict[str, Any]:
    nodes = []
    by_id = {}
    for node in e.nodes:
        direct = node.lnk is not None and node.cfrom >= 0 and node.cto >= node.cfrom
        item = {
            "id": node.id,
            "predicate": node.predicate,
            "directly_anchored": direct,
            "charspan": [node.cfrom, node.cto] if direct else None,
            "source_slice": source[node.cfrom : node.cto] if direct else None,
        }
        nodes.append(item)
        by_id[node.id] = item
    edges = []
    for start, role, end in e.edges:
        source_span = by_id[start]["charspan"]
        target_span = by_id[end]["charspan"]
        spans = [span for span in (source_span, target_span) if span is not None]
        edges.append(
            {
                "source": start,
                "role": role,
                "target": end,
                "direct_lnk": None,
                "source_charspan": source_span,
                "target_charspan": target_span,
                "derived_support_charspan": (
                    [min(span[0] for span in spans), max(span[1] for span in spans)]
                    if spans
                    else None
                ),
            }
        )
    return {
        "top": e.top,
        "nodes": nodes,
        "edges": edges,
        "coverage": {
            "nodes_total": len(nodes),
            "nodes_directly_anchored": sum(node["directly_anchored"] for node in nodes),
            "nodes_without_direct_anchor": sum(
                not node["directly_anchored"] for node in nodes
            ),
            "edges_total": len(edges),
            "edges_with_derived_support": sum(
                edge["derived_support_charspan"] is not None for edge in edges
            ),
        },
    }


def dmrs_anchoring(d: Any, source: str) -> dict[str, Any]:
    nodes = []
    by_id = {}
    for node in d.nodes:
        direct = node.lnk is not None and node.cfrom >= 0 and node.cto >= node.cfrom
        item = {
            "id": node.id,
            "predicate": node.predicate,
            "directly_anchored": direct,
            "charspan": [node.cfrom, node.cto] if direct else None,
            "source_slice": source[node.cfrom : node.cto] if direct else None,
        }
        nodes.append(item)
        by_id[node.id] = item
    links = []
    for link in d.links:
        source_span = by_id[link.start]["charspan"]
        target_span = by_id[link.end]["charspan"]
        spans = [span for span in (source_span, target_span) if span is not None]
        links.append(
            {
                "source": link.start,
                "role": link.role,
                "post": link.post,
                "target": link.end,
                "direct_lnk": None,
                "source_charspan": source_span,
                "target_charspan": target_span,
                "derived_support_charspan": (
                    [min(span[0] for span in spans), max(span[1] for span in spans)]
                    if spans
                    else None
                ),
            }
        )
    return {
        "top": d.top,
        "index": d.index,
        "nodes": nodes,
        "links": links,
        "coverage": {
            "nodes_total": len(nodes),
            "nodes_directly_anchored": sum(node["directly_anchored"] for node in nodes),
            "nodes_without_direct_anchor": sum(
                not node["directly_anchored"] for node in nodes
            ),
            "links_total": len(links),
            "links_with_derived_support": sum(
                link["derived_support_charspan"] is not None for link in links
            ),
        },
    }


def cross_representation_anchors(
    mrs_data: dict[str, Any], eds_data: dict[str, Any], dmrs_data: dict[str, Any]
) -> dict[str, Any]:
    mrs_items = [
        (item["predicate"], item["charspan"]) for item in mrs_data["predications"]
    ]
    eds_items = [(item["predicate"], item["charspan"]) for item in eds_data["nodes"]]
    dmrs_items = [
        (item["predicate"], item["charspan"]) for item in dmrs_data["nodes"]
    ]
    return {
        "mrs_to_eds_predicate_anchor_sequence_preserved": mrs_items == eds_items,
        "mrs_to_dmrs_predicate_anchor_sequence_preserved": mrs_items == dmrs_items,
        "mrs_count": len(mrs_items),
        "eds_count": len(eds_items),
        "dmrs_count": len(dmrs_items),
    }


def offset_evidence(
    fixture: dict[str, Any], observed_tokens: list[dict[str, Any]]
) -> dict[str, Any]:
    source = fixture["sentence"]
    expected = fixture["expected_initial_tokens"]
    rows = []
    for expected_item, observed in zip(expected, observed_tokens, strict=True):
        surface, start, end = expected_item
        rows.append(
            {
                "surface": surface,
                "observed": observed["charspan"],
                "observed_source_slice": observed["source_slice"],
                "source_slice_matches_expected": observed["source_slice"] == surface,
                "code_points": [start, end],
                "utf8_bytes": [utf8_offset(source, start), utf8_offset(source, end)],
                "utf16_code_units": [
                    utf16_offset(source, start),
                    utf16_offset(source, end),
                ],
                "base_plus_combining_display_units": [
                    approximate_grapheme_offset(source, start),
                    approximate_grapheme_offset(source, end),
                ],
            }
        )
    return {
        "fixture": fixture["id"],
        "rows": rows,
        "all_match_code_points": all(row["observed"] == row["code_points"] for row in rows),
        "all_match_utf8_bytes": all(row["observed"] == row["utf8_bytes"] for row in rows),
        "all_match_utf16_code_units": all(
            row["observed"] == row["utf16_code_units"] for row in rows
        ),
        "all_match_base_plus_combining_display_units": all(
            row["observed"] == row["base_plus_combining_display_units"]
            for row in rows
        ),
    }


def run_raw(
    executable: Path,
    grammar: Path,
    sentences: list[str],
    max_results: int,
    raw_dir: Path,
) -> None:
    completed = subprocess.run(
        [
            str(executable), "-g", str(grammar), "-n", str(max_results),
            "--tsdb-notes", "--tsdb-stdout", "--report-labels",
        ],
        input="\n".join(sentences) + "\n",
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "ace-tsdb.stdout").write_text(completed.stdout, encoding="utf-8")
    (raw_dir / "ace-tsdb.stderr").write_text(completed.stderr, encoding="utf-8")


def validate(
    results: list[dict[str, Any]], convention: dict[str, Any], max_results: int
) -> None:
    required = {
        "punctuation",
        "contraction",
        "unicode-non-bmp",
        "unicode-combining",
        "multiple-spaces",
        "repeated-tokens",
    }
    if {result["id"] for result in results} != required:
        raise RuntimeError("NLP-04 fixture coverage changed.")
    analysis_ids: set[str] = set()
    for result in results:
        if result["status"] != "parsed":
            raise RuntimeError(f"Fixture did not parse: {result['id']}")
        if not result["analyses"] or len(result["analyses"]) > max_results:
            raise RuntimeError(f"Invalid analysis count: {result['id']}")
        if not result["offset_evidence"]["all_match_code_points"]:
            raise RuntimeError(f"Code-point offsets do not match: {result['id']}")
        if not all(
            row["source_slice_matches_expected"]
            for row in result["offset_evidence"]["rows"]
        ):
            raise RuntimeError(f"Token spans address the wrong text: {result['id']}")
        if not result["initial_token_source_coverage"]["source_fully_addressable"]:
            raise RuntimeError(f"Source residue is not addressable: {result['id']}")
        if not result["initial_token_source_coverage"]["source_text_preserved"]:
            raise RuntimeError(f"Source cannot be reconstructed: {result['id']}")
        if result["returned_analysis_count"] != len(result["analyses"]):
            raise RuntimeError(f"Analysis count disagrees: {result['id']}")
        if [analysis["rank"] for analysis in result["analyses"]] != list(
            range(1, len(result["analyses"]) + 1)
        ):
            raise RuntimeError(f"Analysis ranks are not contiguous: {result['id']}")
        for analysis in result["analyses"]:
            if analysis["analysis_id"] in analysis_ids:
                raise RuntimeError(f"Duplicate analysis id: {analysis['analysis_id']}")
            analysis_ids.add(analysis["analysis_id"])
            coverage = analysis["mrs_anchoring"]["coverage"]
            if coverage["predications_total"] != coverage["predications_directly_anchored"]:
                raise RuntimeError(f"Unanchored MRS predication: {analysis['analysis_id']}")
            if coverage["variables_and_handles_without_support"]:
                raise RuntimeError(
                    f"Unsupported variable or handle: {analysis['analysis_id']}"
                )
            if coverage["role_relations_total"] != coverage["role_relations_with_derived_support"]:
                raise RuntimeError(f"Unsupported MRS role: {analysis['analysis_id']}")
            for projection in ("eds_anchoring", "dmrs_anchoring"):
                projection_coverage = analysis[projection]["coverage"]
                if (
                    projection_coverage["nodes_total"]
                    != projection_coverage["nodes_directly_anchored"]
                ):
                    raise RuntimeError(
                        f"Unanchored projection node: {analysis['analysis_id']}"
                    )
            eds_coverage = analysis["eds_anchoring"]["coverage"]
            if eds_coverage["edges_total"] != eds_coverage["edges_with_derived_support"]:
                raise RuntimeError(f"Unsupported EDS edge: {analysis['analysis_id']}")
            dmrs_coverage = analysis["dmrs_anchoring"]["coverage"]
            if dmrs_coverage["links_total"] != dmrs_coverage["links_with_derived_support"]:
                raise RuntimeError(f"Unsupported DMRS link: {analysis['analysis_id']}")
            semantic_source = analysis["semantic_source_coverage"]
            if not semantic_source["source_fully_addressable"]:
                raise RuntimeError(f"Semantic residue is not addressable: {analysis['analysis_id']}")
            if not semantic_source["source_text_preserved"]:
                raise RuntimeError(f"Semantic source cannot be reconstructed: {analysis['analysis_id']}")
            cross = analysis["cross_representation_anchors"]
            if not cross["mrs_to_eds_predicate_anchor_sequence_preserved"]:
                raise RuntimeError(f"MRS→EDS anchor loss: {analysis['analysis_id']}")
            if not cross["mrs_to_dmrs_predicate_anchor_sequence_preserved"]:
                raise RuntimeError(f"MRS→DMRS anchor loss: {analysis['analysis_id']}")
    if convention["utf8_bytes_matches_all"]:
        raise RuntimeError("Unicode fixtures failed to distinguish UTF-8 byte offsets.")
    if convention["utf16_code_units_matches_all"]:
        raise RuntimeError("Non-BMP fixture failed to distinguish UTF-16 offsets.")
    if convention["display_units_match_all"]:
        raise RuntimeError("Combining fixture failed to distinguish display-unit offsets.")
    contraction = next(result for result in results if result["id"] == "contraction")
    if not any(
        token["source_slice"] == "n't" and token["form"] == "n’t"
        for token in contraction["initial_tokens"]
    ):
        raise RuntimeError("Contraction normalization is no longer observable.")
    repeated = next(result for result in results if result["id"] == "repeated-tokens")
    dog_spans = [
        token["charspan"]
        for token in repeated["initial_tokens"]
        if token["source_slice"].lower() == "dog"
    ]
    if dog_spans != [[4, 7], [19, 22]]:
        raise RuntimeError("Repeated tokens are not independently anchored.")
    dog_predication_spans = [
        predication["charspan"]
        for predication in repeated["analyses"][0]["mrs_anchoring"]["predications"]
        if predication["predicate"] == "_dog_n_1"
    ]
    if dog_predication_spans != [[4, 7], [19, 23]]:
        raise RuntimeError("Repeated predications are not independently anchored.")
    multiple_spaces = next(
        result for result in results if result["id"] == "multiple-spaces"
    )
    whitespace_residue = [
        item
        for item in multiple_spaces["initial_token_source_coverage"]["residual_spans"]
        if item["source_slice"].isspace()
    ]
    if whitespace_residue != [
        {"charspan": [3, 6], "source_slice": "   "},
        {"charspan": [9, 11], "source_slice": "  "},
    ]:
        raise RuntimeError("Multiple-space residue is not preserved exactly.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ace", type=Path, default=DEFAULT_ACE)
    parser.add_argument("--grammar", type=Path, default=DEFAULT_GRAMMAR)
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    args = parser.parse_args()
    if args.max_results < 1:
        parser.error("--max-results must be positive")
    if not args.ace.is_file() or not args.grammar.is_file():
        parser.error("ACE or ERG is missing; run ./scripts/seman2 install-tools")

    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_raw(
        args.ace,
        args.grammar,
        [item["sentence"] for item in fixtures],
        args.max_results,
        raw_dir,
    )

    results = []
    with ace.ACEParser(
        str(args.grammar),
        executable=str(args.ace),
        cmdargs=["-n", str(args.max_results)],
    ) as process:
        for fixture in fixtures:
            response = process.interact(fixture["sentence"])
            analyses = response.results()
            initial = parse_tokens(response.get("tokens", {}).get("initial", ""), fixture["sentence"])
            internal = parse_tokens(response.get("tokens", {}).get("internal", ""), fixture["sentence"])
            if not analyses:
                results.append({**fixture, "status": "parse_failure"})
                continue
            analysis_records = []
            for rank, selected in enumerate(analyses, start=1):
                raw_mrs = selected.get("mrs")
                identity_payload = (
                    fixture["sentence"]
                    + "\0"
                    + raw_mrs
                    + "\0"
                    + (selected.get("tree") or "")
                    + "\0"
                    + (selected.get("derivation") or "")
                )
                analysis_id = "analysis:" + hashlib.sha256(
                    identity_payload.encode("utf-8")
                ).hexdigest()
                m = selected.mrs()
                e = eds.from_mrs(m)
                d = dmrs.from_mrs(m)
                mrs_data = semantic_anchoring(m, fixture["sentence"])
                eds_data = eds_anchoring(e, fixture["sentence"])
                dmrs_data = dmrs_anchoring(d, fixture["sentence"])
                flags = dict(selected.get("flags", []))
                analysis_records.append(
                    {
                        "analysis_id": analysis_id,
                        "rank": rank,
                        "score": flags.get(":ascore"),
                        "probability": flags.get(":probability"),
                        "analysis_attribution": {
                            "source_observation_id": f"source:{fixture['id']}",
                            "producer": "ACE/ERG",
                            "decoder_and_projector": "PyDelphin",
                            "analysis_type": (
                                "DELPH-IN MRS with EDS and DMRS projections"
                            ),
                            "raw_mrs_sha256": hashlib.sha256(
                                raw_mrs.encode("utf-8")
                            ).hexdigest(),
                            "raw_derivation_sha256": hashlib.sha256(
                                (selected.get("derivation") or "").encode("utf-8")
                            ).hexdigest(),
                        },
                        "mrs_validation": {
                            "well_formed": mrs.is_well_formed(m),
                            "connected": mrs.is_connected(m),
                            "has_intrinsic_variable_property": (
                                mrs.has_intrinsic_variable_property(m)
                            ),
                            "plausibly_scopes": mrs.plausibly_scopes(m),
                        },
                        "mrs_anchoring": mrs_data,
                        "eds_anchoring": eds_data,
                        "dmrs_anchoring": dmrs_data,
                        "cross_representation_anchors": cross_representation_anchors(
                            mrs_data, eds_data, dmrs_data
                        ),
                        "semantic_source_coverage": source_coverage(
                            fixture["sentence"],
                            [
                                item["charspan"]
                                for item in mrs_data["predications"]
                                if item["charspan"] is not None
                            ],
                        ),
                    }
                )
            results.append(
                {
                    **fixture,
                    "status": "parsed",
                    "returned_analysis_count": len(analysis_records),
                    "limit_reached": len(analysis_records) == args.max_results,
                    "source_observation": {
                        "id": f"source:{fixture['id']}",
                        "text": fixture["sentence"],
                        "code_point_length": len(fixture["sentence"]),
                        "utf8_byte_length": len(fixture["sentence"].encode("utf-8")),
                        "utf16_code_unit_length": utf16_offset(
                            fixture["sentence"], len(fixture["sentence"])
                        ),
                    },
                    "initial_tokens": initial,
                    "internal_tokens": internal,
                    "initial_token_source_coverage": source_coverage(
                        fixture["sentence"],
                        [token["charspan"] for token in initial],
                    ),
                    "token_lattice_raw": response.get("tokens", {}),
                    "offset_evidence": offset_evidence(fixture, initial),
                    "analyses": analysis_records,
                }
            )

    evidence = [result["offset_evidence"] for result in results if result["status"] == "parsed"]
    convention = {
        "observed": "Unicode code points, zero-based, end-exclusive",
        "code_points_match_all": all(item["all_match_code_points"] for item in evidence),
        "utf8_bytes_matches_all": all(item["all_match_utf8_bytes"] for item in evidence),
        "utf16_code_units_matches_all": all(
            item["all_match_utf16_code_units"] for item in evidence
        ),
        "display_units_match_all": all(
            item["all_match_base_plus_combining_display_units"] for item in evidence
        ),
        "evidence": evidence,
        "important_distinction": (
            "Token forms may be normalized and differ from the exact source slice; "
            "the charspan always addresses the original source text."
        ),
    }
    validate(results, convention, args.max_results)

    all_analyses = [
        analysis for result in results for analysis in result.get("analyses", [])
    ]
    all_mrs_coverage = [
        analysis["mrs_anchoring"]["coverage"] for analysis in all_analyses
    ]
    all_eds_coverage = [
        analysis["eds_anchoring"]["coverage"] for analysis in all_analyses
    ]
    all_dmrs_coverage = [
        analysis["dmrs_anchoring"]["coverage"] for analysis in all_analyses
    ]
    summary = {
        "fixture_count": len(results),
        "analysis_count": len(all_analyses),
        "analysis_limit_per_fixture": args.max_results,
        "well_formed_mrs_count": sum(
            analysis["mrs_validation"]["well_formed"] for analysis in all_analyses
        ),
        "non_well_formed_mrs_count": sum(
            not analysis["mrs_validation"]["well_formed"]
            for analysis in all_analyses
        ),
        "offset_convention": convention["observed"],
        "initial_token_count": sum(len(result["initial_tokens"]) for result in results),
        "internal_token_count": sum(len(result["internal_tokens"]) for result in results),
        "predication_count": sum(
            coverage["predications_total"] for coverage in all_mrs_coverage
        ),
        "directly_anchored_predications": sum(
            coverage["predications_directly_anchored"]
            for coverage in all_mrs_coverage
        ),
        "indirectly_covered_variables_and_handles": sum(
            coverage["variables_and_handles_indirectly_covered"]
            for coverage in all_mrs_coverage
        ),
        "unsupported_variables_and_handles": sum(
            coverage["variables_and_handles_without_support"]
            for coverage in all_mrs_coverage
        ),
        "role_relation_count": sum(
            coverage["role_relations_total"] for coverage in all_mrs_coverage
        ),
        "role_relations_with_derived_support": sum(
            coverage["role_relations_with_derived_support"]
            for coverage in all_mrs_coverage
        ),
        "eds_node_count": sum(coverage["nodes_total"] for coverage in all_eds_coverage),
        "directly_anchored_eds_nodes": sum(
            coverage["nodes_directly_anchored"] for coverage in all_eds_coverage
        ),
        "eds_edge_count": sum(coverage["edges_total"] for coverage in all_eds_coverage),
        "eds_edges_with_derived_support": sum(
            coverage["edges_with_derived_support"] for coverage in all_eds_coverage
        ),
        "dmrs_node_count": sum(coverage["nodes_total"] for coverage in all_dmrs_coverage),
        "directly_anchored_dmrs_nodes": sum(
            coverage["nodes_directly_anchored"] for coverage in all_dmrs_coverage
        ),
        "dmrs_link_count": sum(coverage["links_total"] for coverage in all_dmrs_coverage),
        "dmrs_links_with_derived_support": sum(
            coverage["links_with_derived_support"] for coverage in all_dmrs_coverage
        ),
        "fixtures_reconstructable_from_token_partition": sum(
            result["initial_token_source_coverage"]["source_text_preserved"]
            for result in results
        ),
    }
    (output_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "offset-convention.json").write_text(
        json.dumps(convention, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "ace": subprocess.run(
            [str(args.ace), "-V"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ).stdout.strip(),
        "erg": {
            "image": os.path.relpath(args.grammar, REPO_ROOT),
            "sha256": sha256(args.grammar),
            "label_reported_by_ace": "ERG (2018)",
        },
        "pydelphin": importlib.metadata.version("pydelphin"),
        "parameters": {
            "max_results_per_fixture": args.max_results,
            "retention": "all analyses returned by ACE up to the configured limit",
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"NLP-04: {len(results)} fixtures validated")
    print(f"offsets: {convention['observed']}")
    print(
        f"anchors: {summary['directly_anchored_predications']}/"
        f"{summary['predication_count']} predications direct; "
        f"{summary['unsupported_variables_and_handles']} unsupported variables/handles"
    )
    print(
        f"analyses: {summary['analysis_count']}; "
        f"EDS nodes {summary['directly_anchored_eds_nodes']}/{summary['eds_node_count']}; "
        f"DMRS nodes {summary['directly_anchored_dmrs_nodes']}/{summary['dmrs_node_count']}"
    )


if __name__ == "__main__":
    main()
