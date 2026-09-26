#!/usr/bin/env python3
"""Run NLP-06: compare ERG/ACE/PyDelphin and Link Grammar."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import linkgrammar
from delphin import ace, dmrs, eds, mrs
from linkgrammar import Clinkgrammar as clg
from linkgrammar import Dictionary, ParseOptions, Sentence


POC_DIR = Path(__file__).resolve().parent
REPO_ROOT = POC_DIR.parents[1]
DEFAULT_ACE = REPO_ROOT / ".local/bin/ace"
DEFAULT_GRAMMAR = REPO_ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
DEFAULT_LINK_PARSER = REPO_ROOT / ".local/bin/link-parser"
DEFAULT_MAX_RESULTS = 100
DEFAULT_TIMEOUT_SECONDS = 10
TOKEN_RE = re.compile(
    r'\((?P<id>\d+),\s*(?P<start_vertex>\d+),\s*(?P<end_vertex>\d+),\s*'
    r'<(?P<from>\d+):(?P<to>\d+)>,\s*\d+,\s*"(?P<form>(?:[^"\\]|\\.)*)"'
    r',\s*\d+,\s*"[^"]*"(?:,\s*"(?P<pos>[^"]+)"\s+'
    r'(?P<probability>[0-9.]+))?\)'
)


def stable_id(prefix: str, payload: Any) -> str:
    value = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ace_tokens(raw: str, source: str) -> list[dict[str, Any]]:
    tokens = []
    for match in TOKEN_RE.finditer(raw):
        item = match.groupdict()
        start, end = int(item["from"]), int(item["to"])
        tokens.append(
            {
                "id": int(item["id"]),
                "vertices": [int(item["start_vertex"]), int(item["end_vertex"])],
                "form": json.loads(f'"{item["form"]}"'),
                "charspan": [start, end],
                "source_slice": source[start:end],
                "pos": item["pos"],
                "pos_probability": (
                    float(item["probability"])
                    if item["probability"] is not None
                    else None
                ),
            }
        )
    return tokens


def derivation_rule_count(node: dict[str, Any]) -> int:
    return (1 if "entity" in node else 0) + sum(
        derivation_rule_count(child) for child in node.get("daughters", [])
    )


def ace_candidate(
    fixture: dict[str, Any], rank: int, result: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_mrs = result.get("mrs")
    raw_tree = result.get("tree")
    raw_derivation = result.get("derivation")
    m = result.mrs()
    e = eds.from_mrs(m)
    d = dmrs.from_mrs(m)
    flags = dict(result.get("flags", []))
    candidate_id = stable_id(
        "erg-analysis:",
        {
            "source": fixture["sentence"],
            "mrs": raw_mrs,
            "tree": raw_tree,
            "derivation": raw_derivation,
        },
    )
    roles = [
        [ep.id, role, target]
        for ep in m.rels
        for role, target in ep.args.items()
        if role != "CARG"
    ]
    predications = [
        {
            "id": ep.id,
            "predicate": ep.predicate,
            "charspan": [ep.cfrom, ep.cto] if ep.lnk is not None else None,
            "source_slice": (
                fixture["sentence"][ep.cfrom : ep.cto] if ep.lnk is not None else None
            ),
        }
        for ep in m.rels
    ]
    derivation = result.derivation().to_dict()
    candidate = {
        "analysis_id": candidate_id,
        "rank": rank,
        "score": flags.get(":ascore"),
        "probability": flags.get(":probability"),
        "support": {"source_observation_id": f"source:{fixture['id']}"},
        "producer": {"parser": "ACE", "grammar": "ERG", "decoder": "PyDelphin"},
        "syntax": {
            "phrase_structure_tree": raw_tree,
            "hpsg_derivation_available": bool(raw_derivation),
            "derivation_rule_count": derivation_rule_count(derivation),
        },
        "semantics": {
            "mrs": {
                "well_formed": mrs.is_well_formed(m),
                "predication_count": len(m.rels),
                "predications": predications,
                "variable_and_handle_count": len(m.variables),
                "role_count": len(roles),
                "roles": roles,
                "handle_constraint_count": len(m.hcons),
                "individual_constraint_count": len(m.icons),
                "quantifier_count": sum(m.is_quantifier(ep.id) for ep in m.rels),
            },
            "eds": {"node_count": len(e.nodes), "edge_count": len(e.edges)},
            "dmrs": {"node_count": len(d.nodes), "link_count": len(d.links)},
        },
    }
    raw = {
        "fixture": fixture["id"],
        "rank": rank,
        "analysis_id": candidate_id,
        "flags": result.get("flags"),
        "tree": raw_tree,
        "derivation": raw_derivation,
        "mrs": raw_mrs,
    }
    return candidate, raw


def run_ace(
    fixtures: list[dict[str, Any]], executable: Path, grammar: Path, max_results: int
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    outputs: dict[str, dict[str, Any]] = {}
    raw_records = []
    with ace.ACEParser(
        str(grammar), executable=str(executable), cmdargs=["-n", str(max_results)]
    ) as process:
        for fixture in fixtures:
            response = process.interact(fixture["sentence"])
            candidates = []
            for rank, result in enumerate(response.results(), start=1):
                candidate, raw = ace_candidate(fixture, rank, result)
                candidates.append(candidate)
                raw_records.append(raw)
            candidate_ids = [candidate["analysis_id"] for candidate in candidates]
            for candidate in candidates:
                candidate["competes_with"] = [
                    item for item in candidate_ids if item != candidate["analysis_id"]
                ]
            outputs[fixture["id"]] = {
                "status": "parsed" if candidates else "parse_failure",
                "returned_analysis_count": len(candidates),
                "limit_reached": len(candidates) >= max_results,
                "initial_tokens": ace_tokens(
                    response.get("tokens", {}).get("initial", ""), fixture["sentence"]
                ),
                "internal_tokens": ace_tokens(
                    response.get("tokens", {}).get("internal", ""), fixture["sentence"]
                ),
                "analyses": candidates,
            }
    return outputs, raw_records


def lg_options(
    max_results: int, timeout_seconds: int, max_null_count: int, islands_ok: bool
) -> ParseOptions:
    return ParseOptions(
        linkage_limit=max_results,
        min_null_count=0,
        max_null_count=max_null_count,
        islands_ok=islands_ok,
        spell_guess=False,
        repeatable_rand=True,
        max_parse_time=timeout_seconds,
        display_morphology=True,
    )


def lg_linkage(
    fixture: dict[str, Any], linkage: Any, rank: int, pass_name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    tokens = []
    for index in range(linkage.num_of_words()):
        span = [linkage.word_char_start(index), linkage.word_char_end(index)]
        form = linkage.word(index)
        tokens.append(
            {
                "index": index,
                "form": form,
                "charspan": span,
                "source_slice": fixture["sentence"][slice(*span)],
                "boundary_wall": index in (0, linkage.num_of_words() - 1),
                "disjunct": clg.linkage_get_disjunct_str(linkage._obj, index),
                "word_disjunct_cost": clg.linkage_get_disjunct_cost(
                    linkage._obj, index
                ),
                "dictionary_guess_or_fallback": any(
                    marker in form for marker in ("[?]", "[!]", "UNKNOWN-WORD")
                ),
            }
        )
    links = []
    for index, link in enumerate(linkage.links()):
        left = clg.linkage_get_link_lword(linkage._obj, index)
        right = clg.linkage_get_link_rword(linkage._obj, index)
        links.append(
            {
                "type": clg.linkage_get_link_label(linkage._obj, index),
                "left_word_index": left,
                "left_form": tokens[left]["form"],
                "left_connector": link.left_label,
                "right_word_index": right,
                "right_form": tokens[right]["form"],
                "right_connector": link.right_label,
                "length": len(link),
            }
        )
    costs = {
        "unused_word_cost": linkage.unused_word_cost(),
        "disjunct_cost": linkage.disjunct_cost(),
        "link_cost": linkage.link_cost(),
        "violation_name": linkage.violation_name(),
    }
    constituent_tree = linkage.constituent_tree(2)
    linkage_id = stable_id(
        "lg-linkage:",
        {
            "source": fixture["sentence"],
            "pass": pass_name,
            "rank": rank,
            "tokens": [[item["form"], item["disjunct"]] for item in tokens],
            "links": links,
            "costs": costs,
            "constituents": constituent_tree,
        },
    )
    record = {
        "linkage_id": linkage_id,
        "rank": rank,
        "support": {"source_observation_id": f"source:{fixture['id']}"},
        "producer": {"parser": "Link Grammar", "dictionary_language": "en"},
        "is_full_parse": costs["unused_word_cost"] == 0,
        "tokens": tokens,
        "links": links,
        "costs": costs,
        "constituent_tree": constituent_tree,
    }
    raw = {
        "fixture": fixture["id"],
        "pass": pass_name,
        "rank": rank,
        "linkage_id": linkage_id,
        "words": list(linkage.words()),
        "links": [str(item) for item in linkage.links()],
        "costs": costs,
        "constituent_tree": constituent_tree,
        "diagram": linkage.diagram(display_walls=True, screen_width=180),
    }
    return record, raw


def lg_parse_pass(
    fixture: dict[str, Any],
    dictionary: Dictionary,
    max_results: int,
    timeout_seconds: int,
    max_null_count: int,
    islands_ok: bool,
    pass_name: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    options = lg_options(max_results, timeout_seconds, max_null_count, islands_ok)
    sentence = Sentence(fixture["sentence"], dictionary, options)
    split_status = sentence.split()
    if split_status < 0:
        return {
            "status": "split_failure",
            "counts": {"found": 0, "postprocessed": 0, "valid_returned": 0},
            "sentence_null_count": None,
            "limit_reached_or_sampled": False,
            "linkages": [],
        }, []
    linkage_objects = list(sentence.parse())
    linkages, raw_records = [], []
    for rank, linkage in enumerate(linkage_objects, start=1):
        record, raw = lg_linkage(fixture, linkage, rank, pass_name)
        linkages.append(record)
        raw_records.append(raw)
    ids = [item["linkage_id"] for item in linkages]
    for linkage in linkages:
        linkage["competes_with"] = [item for item in ids if item != linkage["linkage_id"]]
    found = clg.sentence_num_linkages_found(sentence._obj)
    postprocessed = clg.sentence_num_linkages_post_processed(sentence._obj)
    return {
        "status": "parsed" if linkages else "parse_failure",
        "counts": {
            "found": found,
            "postprocessed": postprocessed,
            "valid_returned": len(linkages),
        },
        "sentence_null_count": sentence.null_count(),
        "limit_reached_or_sampled": found > postprocessed or len(linkages) >= max_results,
        "linkages": linkages,
    }, raw_records


def run_link_grammar(
    fixtures: list[dict[str, Any]], max_results: int, timeout_seconds: int
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], Dictionary]:
    dictionary = Dictionary("en")
    outputs = {}
    raw_records = []
    for fixture in fixtures:
        strict, raw = lg_parse_pass(
            fixture,
            dictionary,
            max_results,
            timeout_seconds,
            max_null_count=0,
            islands_ok=False,
            pass_name="strict",
        )
        raw_records.extend(raw)
        recovery = None
        if "link_grammar_recovery_max_null_count" in fixture:
            recovery, raw = lg_parse_pass(
                fixture,
                dictionary,
                max_results,
                timeout_seconds,
                max_null_count=fixture["link_grammar_recovery_max_null_count"],
                islands_ok=True,
                pass_name="null-link-recovery",
            )
            if recovery["linkages"]:
                recovery["status"] = "partial_parse_with_null_links"
            raw_records.extend(raw)
        outputs[fixture["id"]] = {"strict": strict, "recovery": recovery}
    return outputs, raw_records, dictionary


def coverage_class(erg: dict[str, Any], lg: dict[str, Any]) -> str:
    erg_ok = erg["status"] == "parsed"
    lg_ok = lg["strict"]["status"] == "parsed"
    if erg_ok and lg_ok:
        return "both"
    if erg_ok:
        return "erg_only"
    if lg_ok:
        return "link_grammar_only"
    return "neither"


def top_token_alignment(erg: dict[str, Any], lg: dict[str, Any]) -> dict[str, Any] | None:
    if erg["status"] != "parsed" or lg["strict"]["status"] != "parsed":
        return None
    erg_spans = {tuple(token["charspan"]) for token in erg["initial_tokens"]}
    lg_spans = {
        tuple(token["charspan"])
        for token in lg["strict"]["linkages"][0]["tokens"]
        if not token["boundary_wall"]
    }
    union = erg_spans | lg_spans
    return {
        "exact_span_set_match": erg_spans == lg_spans,
        "erg_span_count": len(erg_spans),
        "link_grammar_span_count": len(lg_spans),
        "shared_span_count": len(erg_spans & lg_spans),
        "jaccard": len(erg_spans & lg_spans) / len(union) if union else 1.0,
        "erg_only_spans": sorted(erg_spans - lg_spans),
        "link_grammar_only_spans": sorted(lg_spans - erg_spans),
    }


def comparison_row(
    fixture: dict[str, Any], erg: dict[str, Any], lg: dict[str, Any]
) -> dict[str, Any]:
    erg_trees = {
        candidate["syntax"]["phrase_structure_tree"] for candidate in erg["analyses"]
    }
    erg_mrs = {
        tuple(
            item["predicate"]
            for item in candidate["semantics"]["mrs"]["predications"]
        )
        for candidate in erg["analyses"]
    }
    lg_trees = {
        linkage["constituent_tree"] for linkage in lg["strict"]["linkages"]
    }
    lg_link_sets = {
        tuple(
            sorted(
                (
                    link["left_word_index"],
                    link["type"],
                    link["right_word_index"],
                )
                for link in linkage["links"]
            )
        )
        for linkage in lg["strict"]["linkages"]
    }
    return {
        "fixture": fixture["id"],
        "phenomenon": fixture["phenomenon"],
        "human_assessment": fixture["human_assessment"],
        "coverage": coverage_class(erg, lg),
        "erg": {
            "status": erg["status"],
            "candidate_count": erg["returned_analysis_count"],
            "limit_reached": erg["limit_reached"],
            "distinct_phrase_structure_trees": len(erg_trees),
            "distinct_predicate_sequences": len(erg_mrs),
            "provides_hpsg": bool(erg["analyses"]),
            "provides_mrs_eds_dmrs": bool(erg["analyses"]),
        },
        "link_grammar": {
            "status": lg["strict"]["status"],
            "found_before_postprocessing": lg["strict"]["counts"]["found"],
            "valid_linkage_count": lg["strict"]["counts"]["valid_returned"],
            "limit_reached_or_sampled": lg["strict"]["limit_reached_or_sampled"],
            "distinct_constituent_trees": len(lg_trees),
            "distinct_typed_link_sets": len(lg_link_sets),
            "provides_word_connector_links": bool(lg["strict"]["linkages"]),
            "provides_cost_vectors": bool(lg["strict"]["linkages"]),
        },
        "top_token_alignment": top_token_alignment(erg, lg),
        "candidate_counts_are_directly_comparable": False,
        "comparison_note": (
            "ACE candidates and Link Grammar linkages are different analytical "
            "units; counts measure exposed ambiguity, not equivalent readings."
        ),
    }


CAPABILITY_MATRIX = [
    {"capability": "source-anchored tokens", "ERG_ACE_PyDelphin": True, "Link_Grammar": True},
    {"capability": "alternative analyses", "ERG_ACE_PyDelphin": True, "Link_Grammar": True},
    {"capability": "constituent syntax", "ERG_ACE_PyDelphin": True, "Link_Grammar": True},
    {"capability": "rank or cost information", "ERG_ACE_PyDelphin": True, "Link_Grammar": True},
    {"capability": "HPSG derivation", "ERG_ACE_PyDelphin": True, "Link_Grammar": False},
    {"capability": "MRS, EDS and DMRS semantics", "ERG_ACE_PyDelphin": True, "Link_Grammar": False},
    {"capability": "scope handles and constraints", "ERG_ACE_PyDelphin": True, "Link_Grammar": False},
    {"capability": "direct typed word-to-word connector links", "ERG_ACE_PyDelphin": False, "Link_Grammar": True},
    {"capability": "per-word disjuncts", "ERG_ACE_PyDelphin": False, "Link_Grammar": True},
    {"capability": "explicit null-link recovery cost", "ERG_ACE_PyDelphin": False, "Link_Grammar": True},
]


def validate(
    fixtures: list[dict[str, Any]],
    results: list[dict[str, Any]],
    matrix: list[dict[str, Any]],
) -> None:
    if len(results) != len(fixtures) or len(matrix) != len(fixtures):
        raise RuntimeError("Comparison coverage is incomplete")
    ids: set[str] = set()
    for fixture, result, row in zip(fixtures, results, matrix, strict=True):
        if row["coverage"] != fixture["expected_coverage"]:
            raise RuntimeError(f"Unexpected coverage result: {fixture['id']}")
        if result["erg"]["status"] == "parsed" and not result["erg"]["analyses"]:
            raise RuntimeError(f"Missing ERG candidates: {fixture['id']}")
        if result["link_grammar"]["strict"]["status"] == "parsed" and not result["link_grammar"]["strict"]["linkages"]:
            raise RuntimeError(f"Missing Link Grammar linkages: {fixture['id']}")
        for identifier in [
            *[item["analysis_id"] for item in result["erg"]["analyses"]],
            *[
                item["linkage_id"]
                for item in result["link_grammar"]["strict"]["linkages"]
            ],
        ]:
            if identifier in ids:
                raise RuntimeError(f"Duplicate analysis identifier: {identifier}")
            ids.add(identifier)
    pp = next(row for row in matrix if row["fixture"] == "pp-attachment")
    if pp["erg"]["candidate_count"] < 2 or pp["link_grammar"]["valid_linkage_count"] < 2:
        raise RuntimeError("PP ambiguity is missing from one analyzer")
    pp_result = next(result for result in results if result["id"] == "pp-attachment")
    erg_with_arg1_types = set()
    for candidate in pp_result["erg"]["analyses"]:
        with_ids = {
            item["id"]
            for item in candidate["semantics"]["mrs"]["predications"]
            if "with" in item["predicate"]
        }
        erg_with_arg1_types.update(
            target[0]
            for source, role, target in candidate["semantics"]["mrs"]["roles"]
            if source in with_ids and role == "ARG1" and target
        )
    if not {"e", "x"}.issubset(erg_with_arg1_types):
        raise RuntimeError("ERG PP event/entity attachments are not both observable")
    lg_pp_links = {
        (
            link["left_form"].split(".", 1)[0].lower(),
            link["type"],
            link["right_form"].split(".", 1)[0].lower(),
        )
        for linkage in pp_result["link_grammar"]["strict"]["linkages"]
        for link in linkage["links"]
    }
    if not {("saw", "MVp", "with"), ("man", "Mp", "with")}.issubset(lg_pp_links):
        raise RuntimeError("Link Grammar PP attachments are not both observable")
    if not all(
        row["top_token_alignment"]["exact_span_set_match"]
        for row in matrix
        if row["coverage"] == "both"
    ):
        raise RuntimeError("Shared parses cannot be aligned on token spans")
    relative = next(
        result for result in results if result["id"] == "link-grammar-only-relative"
    )
    relative_links = {
        (link["left_form"], link["type"], link["right_form"])
        for link in relative["link_grammar"]["strict"]["linkages"][0]["links"]
    }
    if ("everything", "CX", "could.v") not in relative_links:
        raise RuntimeError("Contact-relative structure is not observable")
    false_friend = next(
        result for result in results if result["id"] == "link-grammar-overgeneration"
    )
    false_friend_forms = [
        token["form"]
        for token in false_friend["link_grammar"]["strict"]["linkages"][0]["tokens"]
        if not token["boundary_wall"]
    ]
    if false_friend_forms[:3] != ["A.n", "dogs.v", "runs.n"]:
        raise RuntimeError("Expected lexical reinterpretation is not observable")
    malformed = next(result for result in results if result["id"] == "shared-failure")
    recovery = malformed["link_grammar"]["recovery"]
    if not recovery or recovery["status"] != "partial_parse_with_null_links":
        raise RuntimeError("Link Grammar recovery evidence is missing")
    if not all(not linkage["is_full_parse"] for linkage in recovery["linkages"]):
        raise RuntimeError("Partial recovery was mislabeled as a full parse")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ace", type=Path, default=DEFAULT_ACE)
    parser.add_argument("--grammar", type=Path, default=DEFAULT_GRAMMAR)
    parser.add_argument("--link-parser", type=Path, default=DEFAULT_LINK_PARSER)
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    if args.max_results < 1 or args.timeout_seconds < 1:
        parser.error("--max-results and --timeout-seconds must be positive")
    if not all(path.is_file() for path in (args.ace, args.grammar, args.link_parser)):
        parser.error("ACE, ERG, or Link Grammar is missing; run install-tools")

    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    erg_outputs, raw_erg = run_ace(fixtures, args.ace, args.grammar, args.max_results)
    lg_outputs, raw_lg, dictionary = run_link_grammar(
        fixtures, args.max_results, args.timeout_seconds
    )
    results = []
    matrix = []
    for fixture in fixtures:
        erg = erg_outputs[fixture["id"]]
        lg = lg_outputs[fixture["id"]]
        results.append(
            {
                **fixture,
                "source_observation": {
                    "id": f"source:{fixture['id']}",
                    "text": fixture["sentence"],
                    "charspan": [0, len(fixture["sentence"])],
                },
                "erg": erg,
                "link_grammar": lg,
            }
        )
        matrix.append(comparison_row(fixture, erg, lg))

    validate(fixtures, results, matrix)
    coverage_counts = {
        category: sum(row["coverage"] == category for row in matrix)
        for category in ("both", "erg_only", "link_grammar_only", "neither")
    }
    summary = {
        "fixture_count": len(fixtures),
        "coverage": coverage_counts,
        "erg_candidate_count": sum(
            result["erg"]["returned_analysis_count"] for result in results
        ),
        "erg_well_formed_mrs_count": sum(
            candidate["semantics"]["mrs"]["well_formed"]
            for result in results
            for candidate in result["erg"]["analyses"]
        ),
        "erg_non_well_formed_mrs_count": sum(
            not candidate["semantics"]["mrs"]["well_formed"]
            for result in results
            for candidate in result["erg"]["analyses"]
        ),
        "link_grammar_valid_linkage_count": sum(
            result["link_grammar"]["strict"]["counts"]["valid_returned"]
            for result in results
        ),
        "both_parsed_top_token_span_exact_matches": sum(
            row["top_token_alignment"] is not None
            and row["top_token_alignment"]["exact_span_set_match"]
            for row in matrix
        ),
        "both_parsed_fixture_count": coverage_counts["both"],
        "erg_exclusive_capability_count": sum(
            row["ERG_ACE_PyDelphin"] and not row["Link_Grammar"]
            for row in CAPABILITY_MATRIX
        ),
        "link_grammar_exclusive_capability_count": sum(
            row["Link_Grammar"] and not row["ERG_ACE_PyDelphin"]
            for row in CAPABILITY_MATRIX
        ),
        "decision": "KEEP_LINK_GRAMMAR_AS_ATTRIBUTED_SECONDARY_ANALYZER",
        "decision_conditions": [
            "ERG remains the primary deep semantic analyzer.",
            "Link Grammar output is never promoted to truth or used as an automatic fallback.",
            "Coverage gains and overgeneration remain distinguishable by provenance.",
            "Equivalent alternatives may be grouped but original candidates remain available.",
        ],
    }

    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("results.json", results),
        ("comparison-matrix.json", matrix),
        ("capability-matrix.json", CAPABILITY_MATRIX),
        ("summary.json", summary),
        ("raw/ace-results.json", raw_erg),
        ("raw/link-grammar-linkages.json", raw_lg),
    ):
        (output_dir / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    ace_version = subprocess.run(
        [str(args.ace), "-V"], check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout.strip()
    lg_version = subprocess.run(
        [str(args.link_parser), "--version"], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    ).stdout.splitlines()[0]
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "ace": ace_version,
        "erg": {
            "image": os.path.relpath(args.grammar, REPO_ROOT),
            "sha256": sha256(args.grammar),
            "label_reported_by_ace": "ERG (2018)",
        },
        "pydelphin": importlib.metadata.version("pydelphin"),
        "link_grammar": {
            "binding_version": linkgrammar.__version__,
            "parser_version": lg_version,
            "dictionary_version": dictionary.linkgrammar_get_dict_version(),
            "dictionary_locale": dictionary.linkgrammar_get_dict_locale(),
        },
        "parameters": {
            "max_results_per_analyzer": args.max_results,
            "timeout_seconds": args.timeout_seconds,
            "strict_comparison": {"max_null_count": 0, "spell_guess": False},
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"NLP-06: {len(fixtures)} shared fixtures compared")
    print(f"coverage: {coverage_counts}")
    print(
        f"candidates: ERG {summary['erg_candidate_count']}; "
        f"Link Grammar {summary['link_grammar_valid_linkage_count']}"
    )
    print(f"decision: {summary['decision']}")


if __name__ == "__main__":
    main()
