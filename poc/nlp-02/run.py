#!/usr/bin/env python3
"""Run NLP-02: inspect MRS and its EDS/DMRS projections."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delphin import ace, dmrs, eds, lnk, mrs
from delphin.codecs import dmrsjson, eds as edscodec, edsjson, simplemrs


POC_DIR = Path(__file__).resolve().parent
REPO_ROOT = POC_DIR.parents[1]
DEFAULT_ACE = REPO_ROOT / ".local/bin/ace"
DEFAULT_GRAMMAR = REPO_ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
DEFAULT_MAX_RESULTS = 10

LOSS_MATRIX = [
    {
        "information": "predicate occurrences",
        "mrs_to_eds": "preserved",
        "mrs_to_dmrs": "preserved",
    },
    {
        "information": "predicate lnk anchors",
        "mrs_to_eds": "preserved",
        "mrs_to_dmrs": "preserved",
    },
    {
        "information": "intrinsic variable types and properties",
        "mrs_to_eds": "preserved on nodes",
        "mrs_to_dmrs": "preserved on nodes",
    },
    {
        "information": "non-scopal roles",
        "mrs_to_eds": "projected when the target becomes an EDS node; otherwise lost",
        "mrs_to_dmrs": "projected when the target becomes a DMRS node; otherwise lost",
    },
    {
        "information": "quantifier binding",
        "mrs_to_eds": "reformulated as BV edge",
        "mrs_to_dmrs": "reformulated as RSTR/H link",
    },
    {
        "information": "TOP and INDEX",
        "mrs_to_eds": "TOP only; no distinct INDEX",
        "mrs_to_dmrs": "both represented, but this alone does not guarantee lossless roundtrip",
    },
    {
        "information": "raw variable and handle identifiers",
        "mrs_to_eds": "lost or reassigned",
        "mrs_to_dmrs": "replaced by numeric node IDs",
    },
    {
        "information": "labels and raw HCONS",
        "mrs_to_eds": "lost",
        "mrs_to_dmrs": "raw form lost; useful scope projected to H/HEQ links",
    },
    {
        "information": "scope underspecification",
        "mrs_to_eds": "lost",
        "mrs_to_dmrs": "encoded by scopal links; raw HCONS identities are lost",
    },
    {
        "information": "ICONS",
        "mrs_to_eds": "not represented",
        "mrs_to_dmrs": "not represented",
    },
    {
        "information": "unresolved handle arguments such as BODY",
        "mrs_to_eds": "not represented as such",
        "mrs_to_dmrs": "no explicit link when there is no target",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def lnk_value(item: Any) -> dict[str, Any] | None:
    link = getattr(item, "lnk", None)
    if link is None:
        return None
    data = getattr(link, "data", None)
    if isinstance(data, tuple):
        data = list(data)
    type_names = {
        lnk.Lnk.UNSPECIFIED: "unspecified",
        lnk.Lnk.CHARSPAN: "charspan",
        lnk.Lnk.CHARTSPAN: "chartspan",
        lnk.Lnk.TOKENS: "tokens",
        lnk.Lnk.EDGE: "edge",
    }
    return {"type": type_names[link.type], "data": data, "text": str(link)}


def mrs_dict(m: Any) -> dict[str, Any]:
    top_label, scopes = m.scopes()
    scopal_arguments = m.scopal_arguments(scopes)
    return {
        "top": m.top,
        "index": m.index,
        "surface": m.surface,
        "identifier": m.identifier,
        "variables": m.variables,
        "handles": sorted(variable for variable in m.variables if variable.startswith("h")),
        "predications": [
            {
                "id": ep.id,
                "predicate": ep.predicate,
                "label": ep.label,
                "arguments": dict(ep.args),
                "carg": ep.carg,
                "lnk": lnk_value(ep),
                "surface": ep.surface,
                "base": ep.base,
            }
            for ep in m.rels
        ],
        "handle_constraints": [
            {"high": hc.hi, "relation": str(hc.relation), "low": hc.lo}
            for hc in m.hcons
        ],
        "individual_constraints": [
            {"left": ic.left, "relation": ic.relation, "right": ic.right}
            for ic in m.icons
        ],
        "quantifiers": [ep.id for ep in m.rels if m.is_quantifier(ep.id)],
        "scope_projection": {
            "top_label": top_label,
            "labels": {
                label: [ep.id for ep in predications]
                for label, predications in scopes.items()
            },
            "scopal_arguments": {
                predication: [
                    {"role": role, "relation": str(relation), "target_label": target}
                    for role, relation, target in arguments
                ]
                for predication, arguments in scopal_arguments.items()
            },
        },
    }


def eds_dict(e: Any) -> dict[str, Any]:
    return {
        "top": e.top,
        "surface": e.surface,
        "identifier": e.identifier,
        "nodes": [
            {
                "id": node.id,
                "predicate": node.predicate,
                "type": node.type,
                "properties": dict(node.properties),
                "carg": node.carg,
                "lnk": lnk_value(node),
                "surface": node.surface,
                "base": node.base,
            }
            for node in e.nodes
        ],
        "edges": [
            {"source": source, "role": role, "target": target}
            for source, role, target in e.edges
        ],
        # Quantifier nodes have synthetic IDs and a BV edge; direct inspection
        # also avoids relying on EDS's intrinsic-variable predication index.
        "quantifiers": [node.id for node in e.nodes if "BV" in node.edges],
    }


def dmrs_dict(d: Any) -> dict[str, Any]:
    return {
        "top": d.top,
        "index": d.index,
        "surface": d.surface,
        "identifier": d.identifier,
        "nodes": [
            {
                "id": node.id,
                "predicate": node.predicate,
                "type": node.type,
                "properties": dict(node.properties),
                "carg": node.carg,
                "lnk": lnk_value(node),
                "surface": node.surface,
                "base": node.base,
            }
            for node in d.nodes
        ],
        "links": [
            {
                "source": link.start,
                "role": link.role,
                "post": link.post,
                "target": link.end,
            }
            for link in d.links
        ],
        "quantifiers": [node.id for node in d.nodes if d.is_quantifier(node.id)],
    }


def mrs_validation(m: Any) -> dict[str, bool]:
    """Expose every structural validation supplied by PyDelphin."""
    return {
        "connected": mrs.is_connected(m),
        "complete_intrinsic_variables": mrs.has_complete_intrinsic_variables(m),
        "unique_intrinsic_variables": mrs.has_unique_intrinsic_variables(m),
        "intrinsic_variable_property": mrs.has_intrinsic_variable_property(m),
        "plausibly_scopes": mrs.plausibly_scopes(m),
        "well_formed": mrs.is_well_formed(m),
    }


def role_projection(m: Any, e: Any, d: Any) -> dict[str, Any]:
    """Compare role occurrences, rather than only predicates and anchors."""
    eds_rows = []
    dmrs_rows = []
    dmrs_outgoing: dict[int, set[str]] = {}
    for link in d.links:
        dmrs_outgoing.setdefault(link.start, set()).add(link.role)

    for ep, eds_node, dmrs_node in zip(m.rels, e.nodes, d.nodes, strict=True):
        for role, target in ep.args.items():
            if role in {"ARG0", "CARG", "BODY"}:
                continue
            eds_role = "BV" if m.is_quantifier(ep.id) and role == "RSTR" else role
            eds_rows.append(
                {
                    "mrs_predication": ep.id,
                    "predicate": ep.predicate,
                    "mrs_role": role,
                    "mrs_target": target,
                    "projected_role": eds_role,
                    "preserved": eds_role in eds_node.edges,
                }
            )
            dmrs_rows.append(
                {
                    "mrs_predication": ep.id,
                    "predicate": ep.predicate,
                    "mrs_role": role,
                    "mrs_target": target,
                    "projected_role": role,
                    "preserved": role in dmrs_outgoing.get(dmrs_node.id, set()),
                }
            )

    return {
        "comparison_note": (
            "ARG0 is represented by node identity/sortinfo, CARG by a node property, "
            "and unresolved BODY handles are assessed separately as a known loss."
        ),
        "mrs_to_eds": {
            "role_occurrences": eds_rows,
            "preserved_count": sum(row["preserved"] for row in eds_rows),
            "lost_count": sum(not row["preserved"] for row in eds_rows),
        },
        "mrs_to_dmrs": {
            "role_occurrences": dmrs_rows,
            "preserved_count": sum(row["preserved"] for row in dmrs_rows),
            "lost_count": sum(not row["preserved"] for row in dmrs_rows),
        },
    }


def dmrs_roundtrip(m: Any, d: Any) -> tuple[dict[str, Any], str]:
    reconstructed = mrs.from_dmrs(d)
    raw = simplemrs.encode(reconstructed, indent=True)
    return (
        {
            "isomorphic_to_source_mrs": mrs.is_isomorphic(
                m, reconstructed, properties=True
            ),
            "properties_compared": True,
            "reconstructed_mrs_sha256": hashlib.sha256(
                raw.encode("utf-8")
            ).hexdigest(),
            "reconstructed_mrs_validation": mrs_validation(reconstructed),
        },
        raw,
    )


def conversion_observations(m: Any, e: Any, d: Any) -> dict[str, Any]:
    mrs_predicates = [ep.predicate for ep in m.rels]
    eds_predicates = [node.predicate for node in e.nodes]
    dmrs_predicates = [node.predicate for node in d.nodes]
    mrs_anchors = [lnk_value(ep) for ep in m.rels]
    eds_anchors = [lnk_value(node) for node in e.nodes]
    dmrs_anchors = [lnk_value(node) for node in d.nodes]
    return {
        "counts": {
            "mrs_predications": len(m.rels),
            "mrs_variables": len(m.variables),
            "mrs_handle_constraints": len(m.hcons),
            "mrs_individual_constraints": len(m.icons),
            "eds_nodes": len(e.nodes),
            "eds_edges": len(e.edges),
            "dmrs_nodes": len(d.nodes),
            "dmrs_links": len(d.links),
        },
        "predicate_multiset_preserved": {
            "eds": sorted(mrs_predicates) == sorted(eds_predicates),
            "dmrs": sorted(mrs_predicates) == sorted(dmrs_predicates),
        },
        "predicate_anchors_preserved_in_order": {
            "eds": mrs_anchors == eds_anchors,
            "dmrs": mrs_anchors == dmrs_anchors,
        },
        "mrs_handle_constraints": [
            {"high": hc.hi, "relation": str(hc.relation), "low": hc.lo}
            for hc in m.hcons
        ],
        "dmrs_scopal_links": [
            {
                "source": link.start,
                "role": link.role,
                "post": link.post,
                "target": link.end,
            }
            for link in d.links
            if link.post in {"H", "HEQ"}
        ],
        "losses": {
            "mrs_to_eds": [
                "MRS variable and handle identifiers are not retained as such.",
                "Labels, HCONS and ICONS are absent; underspecified scope is lost.",
                "TOP remains, but MRS INDEX is not a separate EDS field.",
                "Quantifier binding is rewritten as a BV edge.",
                "Arguments targeting variables with no projected node can be lost.",
            ],
            "mrs_to_dmrs": [
                "MRS variable and handle identifiers are replaced by numeric node IDs.",
                "Labels and raw HCONS are absent; useful scope is projected to H/HEQ links.",
                "ICONS are not represented by the DMRS data model.",
                "Some handle arguments such as quantifier BODY have no explicit graph link.",
                "Arguments targeting variables with no projected node can be lost.",
            ],
        },
    }


def run_raw(
    executable: Path,
    grammar: Path,
    sentences: list[str],
    max_results: int,
    raw_dir: Path,
) -> None:
    command = [
        str(executable), "-g", str(grammar), "-n", str(max_results),
        "--tsdb-notes", "--tsdb-stdout", "--report-labels",
    ]
    completed = subprocess.run(
        command,
        input="\n".join(sentences) + "\n",
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "ace-tsdb.stdout").write_text(completed.stdout, encoding="utf-8")
    (raw_dir / "ace-tsdb.stderr").write_text(completed.stderr, encoding="utf-8")


def validate(results: list[dict[str, Any]], max_results: int) -> None:
    if len(results) != 7:
        raise RuntimeError("NLP-02 requires all seven semantic fixtures.")
    for result in results:
        if result["status"] != "converted" or not result["analyses"]:
            raise RuntimeError(f"Fixture did not parse: {result['id']}")
        for analysis in result["analyses"]:
            if set(analysis["quality"]["mrs_validation"]) != {
                "connected",
                "complete_intrinsic_variables",
                "unique_intrinsic_variables",
                "intrinsic_variable_property",
                "plausibly_scopes",
                "well_formed",
            }:
                raise RuntimeError(f"Missing MRS diagnostics: {analysis['candidate_id']}")
            observed = analysis["conversion_observations"]
            if not all(observed["predicate_multiset_preserved"].values()):
                raise RuntimeError(f"Predicate loss detected: {analysis['candidate_id']}")
            if not all(observed["predicate_anchors_preserved_in_order"].values()):
                raise RuntimeError(f"Predicate anchor loss detected: {analysis['candidate_id']}")
            for predication in analysis["mrs"]["predications"]:
                anchor = predication["lnk"]
                if anchor is None or anchor["type"] != "charspan":
                    raise RuntimeError(f"Missing charspan: {analysis['candidate_id']}")
                start, end = anchor["data"]
                if not 0 <= start <= end <= len(result["source_observation"]["text"]):
                    raise RuntimeError(f"Invalid charspan: {analysis['candidate_id']}")

    first_analyses = {result["id"]: result["analyses"][0] for result in results}
    if not all(
        analysis["quality"]["mrs_validation"]["well_formed"]
        for analysis in first_analyses.values()
    ):
        raise RuntimeError("At least one top-ranked fixture MRS is not well-formed.")
    quantifier_mrs = first_analyses["quantifiers"]["mrs"]
    if not quantifier_mrs["quantifiers"] or not quantifier_mrs["handle_constraints"]:
        raise RuntimeError("Quantifier fixture no longer exposes quantifiers and HCONS.")
    quantifier_eds = first_analyses["quantifiers"]["eds"]
    if not quantifier_eds["quantifiers"] or not any(
        edge["role"] == "BV" for edge in quantifier_eds["edges"]
    ):
        raise RuntimeError("EDS no longer exposes quantifier BV edges.")
    quantifier_dmrs = first_analyses["quantifiers"]["dmrs"]
    if not quantifier_dmrs["quantifiers"] or not any(
        link["role"] == "RSTR" and link["post"] == "H"
        for link in quantifier_dmrs["links"]
    ):
        raise RuntimeError("DMRS no longer exposes quantifier RSTR/H links.")
    if len(first_analyses["multiple-predicates"]["mrs"]["predications"]) < 2:
        raise RuntimeError("Multiple-predicate fixture no longer has multiple predicates.")
    if not any(
        ep["predicate"] == "neg" for ep in first_analyses["negation"]["mrs"]["predications"]
    ):
        raise RuntimeError("Negation fixture no longer exposes the neg predicate.")
    if not first_analyses["scope-ambiguity"]["mrs"]["scope_projection"]["scopal_arguments"]:
        raise RuntimeError("Scope fixture no longer exposes scopal arguments.")
    if max_results > 1 and not any(result["returned_analysis_count"] > 1 for result in results):
        raise RuntimeError("No concurrent analyses were retained.")


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

    results: list[dict[str, Any]] = []
    raw_sections: list[str] = []
    with ace.ACEParser(
        str(args.grammar),
        executable=str(args.ace),
        cmdargs=["-n", str(args.max_results)],
    ) as process:
        for fixture in fixtures:
            response = process.interact(fixture["sentence"])
            ace_results = response.results()
            source_observation = {
                "id": f"source:{fixture['id']}",
                "text": fixture["sentence"],
                "span": [0, len(fixture["sentence"])],
                "offset_convention": (
                    "zero-based, end-exclusive ACE charspans; fixtures are ASCII, "
                    "so Unicode code-point versus byte behavior is not tested here"
                ),
            }
            if not ace_results:
                results.append(
                    {
                        **fixture,
                        "source_observation": source_observation,
                        "status": "parse_failure",
                        "returned_analysis_count": 0,
                        "analyses": [],
                    }
                )
                continue
            converted = []
            for rank, ace_result in enumerate(ace_results, start=1):
                m = ace_result.mrs()
                e = eds.from_mrs(m)
                d = dmrs.from_mrs(m)
                roundtrip_report, raw_roundtrip_mrs = dmrs_roundtrip(m, d)
                raw_mrs = simplemrs.encode(m, indent=True)
                raw_eds = edscodec.encode(e, indent=True)
                raw_eds_json = edsjson.encode(e, indent=True)
                raw_dmrs_json = dmrsjson.encode(d, indent=True)
                semantic_digest = hashlib.sha256(raw_mrs.encode("utf-8")).hexdigest()
                semantic_id = f"mrs:{semantic_digest}"
                identity_material = f"{fixture['id']}\0{rank}\0{semantic_digest}"
                candidate_digest = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()
                candidate_id = f"{fixture['id']}:{candidate_digest[:16]}"
                raw_sections.extend(
                    [
                        f"===== {candidate_id} rank={rank} / MRS =====\n{raw_mrs}",
                        f"===== {candidate_id} rank={rank} / EDS =====\n{raw_eds}",
                        f"===== {candidate_id} rank={rank} / EDS JSON =====\n{raw_eds_json}",
                        f"===== {candidate_id} rank={rank} / DMRS JSON =====\n{raw_dmrs_json}",
                        (
                            f"===== {candidate_id} rank={rank} / "
                            f"MRS RECONSTRUCTED FROM DMRS =====\n{raw_roundtrip_mrs}"
                        ),
                    ]
                )
                flags = dict(ace_result.get("flags", []))
                converted.append(
                    {
                        "candidate_id": candidate_id,
                        "semantic_id": semantic_id,
                        "rank": rank,
                        "ace_result_id": ace_result.get("result-id"),
                        "score": flags.get(":ascore"),
                        "probability": flags.get(":probability"),
                        "support": {"source_observation_id": source_observation["id"]},
                        "attribution": {
                            "mrs": {
                                "producer": "ACE/ERG",
                                "decoder": "PyDelphin simplemrs",
                            },
                            "eds": {
                                "producer": "PyDelphin",
                                "method": "delphin.eds.from_mrs",
                                "derived_from": candidate_id + ":mrs",
                            },
                            "dmrs": {
                                "producer": "PyDelphin",
                                "method": "delphin.dmrs.from_mrs",
                                "derived_from": candidate_id + ":mrs",
                            },
                        },
                        "raw_serialization_sha256": {
                            "mrs": semantic_digest,
                            "eds": hashlib.sha256(raw_eds.encode("utf-8")).hexdigest(),
                            "dmrs": hashlib.sha256(raw_dmrs_json.encode("utf-8")).hexdigest(),
                        },
                        "quality": {
                            "mrs_validation": mrs_validation(m),
                            "contains_unknown_predicate": any(
                                ep.predicate == "unknown" for ep in m.rels
                            ),
                            "contains_individual_constraints": bool(m.icons),
                            "interpretation": (
                                "external analyzer diagnostics; candidates are retained "
                                "even when malformed or fallback"
                            ),
                        },
                        "mrs": mrs_dict(m),
                        "eds": eds_dict(e),
                        "dmrs": dmrs_dict(d),
                        "conversion_observations": conversion_observations(m, e, d),
                        "conversion_fidelity": {
                            "role_projection": role_projection(m, e, d),
                            "dmrs_to_mrs_roundtrip": roundtrip_report,
                        },
                    }
                )
            results.append(
                {
                    **fixture,
                    "source_observation": source_observation,
                    "status": "converted",
                    "returned_analysis_count": len(converted),
                    "limit_reached": len(converted) == args.max_results,
                    "scope_evaluation": (
                        {
                            "human_readings_are_test_oracle_not_tool_output": fixture[
                                "human_scope_readings_for_test_oracle"
                            ],
                            "tool_output": (
                                "underspecified MRS constraints; no enumerated resolved "
                                "scope readings"
                            ),
                            "resolved_scope_readings": [],
                            "nlp_02_contract": (
                                "Enumeration is not required here; NLP-02 verifies the "
                                "underspecified constraints and conversion losses."
                            ),
                        }
                        if "human_scope_readings_for_test_oracle" in fixture
                        else None
                    ),
                    "analyses": converted,
                }
            )

    validate(results, args.max_results)
    all_analyses = [analysis for result in results for analysis in result["analyses"]]
    summary = {
        "fixture_count": len(results),
        "candidate_count": len(all_analyses),
        "quality": {
            "well_formed_mrs": sum(
                analysis["quality"]["mrs_validation"]["well_formed"]
                for analysis in all_analyses
            ),
            "candidates_with_unknown_predicate": sum(
                analysis["quality"]["contains_unknown_predicate"]
                for analysis in all_analyses
            ),
            "candidates_with_individual_constraints": sum(
                analysis["quality"]["contains_individual_constraints"]
                for analysis in all_analyses
            ),
        },
        "conversion_fidelity": {
            "isomorphic_dmrs_mrs_roundtrips": sum(
                analysis["conversion_fidelity"]["dmrs_to_mrs_roundtrip"][
                    "isomorphic_to_source_mrs"
                ]
                for analysis in all_analyses
            ),
            "eds_role_occurrences_preserved": sum(
                analysis["conversion_fidelity"]["role_projection"]["mrs_to_eds"][
                    "preserved_count"
                ]
                for analysis in all_analyses
            ),
            "eds_role_occurrences_not_directly_preserved": sum(
                analysis["conversion_fidelity"]["role_projection"]["mrs_to_eds"][
                    "lost_count"
                ]
                for analysis in all_analyses
            ),
            "dmrs_role_occurrences_preserved": sum(
                analysis["conversion_fidelity"]["role_projection"]["mrs_to_dmrs"][
                    "preserved_count"
                ]
                for analysis in all_analyses
            ),
            "dmrs_role_occurrences_not_directly_preserved": sum(
                analysis["conversion_fidelity"]["role_projection"]["mrs_to_dmrs"][
                    "lost_count"
                ]
                for analysis in all_analyses
            ),
        },
        "scope_resolution": {
            "underspecified_constraints_available": True,
            "explicit_readings_enumerated": False,
            "nlp_02_requires_enumeration": False,
            "covered_by": "NLP-03",
        },
    }
    (raw_dir / "semantic-representations.txt").write_text(
        "\n\n".join(raw_sections) + "\n", encoding="utf-8"
    )
    (output_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "loss-matrix.json").write_text(
        json.dumps(LOSS_MATRIX, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "ace": subprocess.run(
            [str(args.ace), "-V"], check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        ).stdout.strip(),
        "erg": {
            "image": os.path.relpath(args.grammar, REPO_ROOT),
            "sha256": sha256(args.grammar),
            "label_reported_by_ace": "ERG (2018)",
        },
        "pydelphin": importlib.metadata.version("pydelphin"),
        "pydelphin_capabilities_exercised": {
            "mrs_validation": [
                "is_connected",
                "has_complete_intrinsic_variables",
                "has_unique_intrinsic_variables",
                "has_intrinsic_variable_property",
                "plausibly_scopes",
                "is_well_formed",
            ],
            "dmrs_roundtrip": ["mrs.from_dmrs", "mrs.is_isomorphic"],
            "resolved_scope_reading_enumerator": "not required by NLP-02",
        },
        "parameters": {
            "max_results": args.max_results,
            "all_returned_analyses_are_retained": True,
            "conversion": ["delphin.eds.from_mrs", "delphin.dmrs.from_mrs"],
            "codec_options": {"properties": True, "lnk": True},
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"NLP-02: {len(results)} fixtures parsed and converted")
    for result in results:
        counts = result["analyses"][0]["conversion_observations"]["counts"]
        print(
            f"{result['id']:20} {result['returned_analysis_count']} analysis(es), "
            f"first: {counts['mrs_predications']} predicates, "
            f"{counts['eds_edges']} EDS edges, {counts['dmrs_links']} DMRS links"
        )
    print(
        "quality: "
        f"{sum(a['quality']['mrs_validation']['well_formed'] for a in all_analyses)}/"
        f"{len(all_analyses)} well-formed MRS; "
        f"{sum(a['conversion_fidelity']['dmrs_to_mrs_roundtrip']['isomorphic_to_source_mrs'] for a in all_analyses)}/"
        f"{len(all_analyses)} lossless DMRS roundtrips"
    )


if __name__ == "__main__":
    main()
