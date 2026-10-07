#!/usr/bin/env python3
"""Run NLP-03: retain and compare concurrent ERG analyses."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delphin import ace, mrs
from delphin.codecs import simplemrs
from z3 import And, Distinct, Int, Or, Solver, sat
import z3


POC_DIR = Path(__file__).resolve().parent
REPO_ROOT = POC_DIR.parents[1]
DEFAULT_ACE = REPO_ROOT / ".local/bin/ace"
DEFAULT_GRAMMAR = REPO_ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
DEFAULT_MAX_RESULTS = 25
DEFAULT_MAX_SCOPE_RESULTS = 100


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def derivation_signature(node: dict[str, Any]) -> dict[str, Any]:
    """Remove transient ACE edge IDs and scores from a derivation tree."""
    signature: dict[str, Any] = {
        "entity": node["entity"],
        "span": [node["start"], node["end"]],
    }
    if "form" in node:
        signature["form"] = node["form"]
    if node.get("daughters"):
        signature["daughters"] = [
            derivation_signature(daughter) for daughter in node["daughters"]
        ]
    return signature


def derivation_rules(node: dict[str, Any]) -> list[str]:
    rules = [node["entity"]]
    for daughter in node.get("daughters", []):
        rules.extend(derivation_rules(daughter))
    return rules


def expanded_counter_difference(left: Counter[str], right: Counter[str]) -> list[str]:
    return sorted((left - right).elements())


def mrs_summary(m: Any) -> dict[str, Any]:
    return {
        "top": m.top,
        "index": m.index,
        "predications": [
            {
                "id": ep.id,
                "predicate": ep.predicate,
                "label": ep.label,
                "arguments": dict(ep.args),
                "charspan": [ep.cfrom, ep.cto],
            }
            for ep in m.rels
        ],
        "variables": m.variables,
        "handle_constraints": [
            {"high": hc.hi, "relation": str(hc.relation), "low": hc.lo}
            for hc in m.hcons
        ],
        "individual_constraints": [
            {"left": ic.left, "relation": ic.relation, "right": ic.right}
            for ic in m.icons
        ],
        "quantifiers": [ep.id for ep in m.rels if m.is_quantifier(ep.id)],
    }


def mrs_validation(m: Any) -> dict[str, bool]:
    return {
        "connected": mrs.is_connected(m),
        "complete_intrinsic_variables": mrs.has_complete_intrinsic_variables(m),
        "unique_intrinsic_variables": mrs.has_unique_intrinsic_variables(m),
        "intrinsic_variable_property": mrs.has_intrinsic_variable_property(m),
        "plausibly_scopes": mrs.plausibly_scopes(m),
        "well_formed": mrs.is_well_formed(m),
    }


def attachment_observation(m: Any) -> dict[str, Any] | None:
    preposition = next((ep for ep in m.rels if ep.predicate == "_with_p"), None)
    if preposition is None:
        return None
    intrinsic = {
        ep.args.get("ARG0"): ep.predicate
        for ep in m.rels
        if not m.is_quantifier(ep.id) and ep.args.get("ARG0")
    }
    return {
        "predicate": preposition.predicate,
        "arg1": preposition.args.get("ARG1"),
        "arg1_introduced_by": intrinsic.get(preposition.args.get("ARG1")),
        "arg2": preposition.args.get("ARG2"),
        "arg2_introduced_by": intrinsic.get(preposition.args.get("ARG2")),
    }


def resolve_scopes(
    m: Any,
    source_candidate_id: str,
    max_solutions: int,
    oracle: list[dict[str, Any]],
) -> dict[str, Any]:
    """Enumerate fully plugged scope trees compatible with MRS qeq constraints."""
    validation = mrs_validation(m)
    if not validation["well_formed"]:
        return {
            "status": "invalid_source_mrs",
            "solver": "Z3",
            "solutions": [],
            "truncated": False,
        }

    labels = list(dict.fromkeys(ep.label for ep in m.rels))
    label_index = {label: index for index, label in enumerate(labels)}
    quantifiers = {ep.label: ep for ep in m.rels if m.is_quantifier(ep.id)}
    owned_holes: list[tuple[str, str, str]] = []
    for ep in m.rels:
        for role, target in ep.args.items():
            if target.startswith("h"):
                owned_holes.append((target, ep.label, role))

    holes = list(dict.fromkeys([m.top] + [hole for hole, _, _ in owned_holes]))
    owner = {hole: label for hole, label, _ in owned_holes}
    owner_role = {hole: role for hole, _, role in owned_holes}
    unsupported_relations = sorted(
        {str(hc.relation) for hc in m.hcons if str(hc.relation) != "qeq"}
    )
    if unsupported_relations:
        return {
            "status": "unsupported_handle_constraint",
            "unsupported_relations": unsupported_relations,
            "solver": "Z3",
            "solutions": [],
            "truncated": False,
        }
    if len(holes) != len(labels) or len(owner) != len(labels) - 1:
        return {
            "status": "unsupported_non_tree_scope_topology",
            "label_count": len(labels),
            "hole_count": len(holes),
            "owned_hole_count": len(owner),
            "solver": "Z3",
            "solutions": [],
            "truncated": False,
        }

    body_holes = {}
    restriction_targets = {}
    quantifier_bound_predicates = {}
    for label, quantifier in quantifiers.items():
        body_hole = quantifier.args.get("BODY")
        restriction_hole = quantifier.args.get("RSTR")
        bound_variable = quantifier.args.get("ARG0")
        bound_labels = {
            ep.label
            for ep in m.rels
            if not m.is_quantifier(ep.id) and ep.args.get("ARG0") == bound_variable
        }
        if (
            body_hole not in holes
            or restriction_hole not in holes
            or len(bound_labels) != 1
        ):
            return {
                "status": "unsupported_quantifier_binding",
                "quantifier": quantifier.predicate,
                "solver": "Z3",
                "solutions": [],
                "truncated": False,
            }
        body_holes[label] = body_hole
        restriction_targets[restriction_hole] = next(iter(bound_labels))
        quantifier_bound_predicates[label] = "+".join(
            sorted(
                ep.predicate
                for ep in m.rels
                if not m.is_quantifier(ep.id)
                and ep.args.get("ARG0") == bound_variable
            )
        )

    plug = {hole: Int(f"plug_{hole}") for hole in holes}
    depth = {label: Int(f"depth_{label}") for label in labels}
    solver = Solver()
    size = len(labels)
    for variable in plug.values():
        solver.add(variable >= 0, variable < size)
    solver.add(Distinct(*plug.values()))
    for variable in depth.values():
        solver.add(variable >= 0, variable < size)

    solver.add(
        Or(
            *[
                And(plug[m.top] == index, depth[label] == 0)
                for index, label in enumerate(labels)
            ]
        )
    )
    for hole, parent_label in owner.items():
        solver.add(
            Or(
                *[
                    And(
                        plug[hole] == index,
                        depth[label] == depth[parent_label] + 1,
                    )
                    for index, label in enumerate(labels)
                ]
            )
        )

    # A quantifier's RSTR is anchored to the EP introducing its bound variable.
    # This excludes spurious solutions that insert unrelated quantifiers inside
    # another quantifier's nominal restriction.
    for hole, target_label in restriction_targets.items():
        solver.add(plug[hole] == label_index[target_label])

    def qeq_expression(
        hole: str, target_label: str, available_quantifiers: tuple[str, ...]
    ) -> Any:
        alternatives = [plug[hole] == label_index[target_label]]
        for quantifier_label in available_quantifiers:
            alternatives.append(
                And(
                    plug[hole] == label_index[quantifier_label],
                    qeq_expression(
                        body_holes[quantifier_label],
                        target_label,
                        tuple(
                            label
                            for label in available_quantifiers
                            if label != quantifier_label
                        ),
                    ),
                )
            )
        return Or(*alternatives)

    quantifier_labels = tuple(quantifiers)
    for constraint in m.hcons:
        if constraint.hi not in plug or constraint.lo not in label_index:
            return {
                "status": "unsupported_dangling_handle_constraint",
                "solver": "Z3",
                "solutions": [],
                "truncated": False,
            }
        solver.add(qeq_expression(constraint.hi, constraint.lo, quantifier_labels))

    solutions = []
    while len(solutions) < max_solutions and solver.check() == sat:
        model = solver.model()
        bindings = {
            hole: labels[model[variable].as_long()] for hole, variable in plug.items()
        }
        depths = {label: model[variable].as_long() for label, variable in depth.items()}
        root_label = bindings[m.top]
        dominance_edges = [
            {
                "source_label": parent_label,
                "role": owner_role[hole],
                "hole": hole,
                "target_label": bindings[hole],
            }
            for hole, parent_label in owner.items()
        ]
        quantifier_order = [
            {
                "label": label,
                "predicate": quantifiers[label].predicate,
                "bound_predicate": quantifier_bound_predicates[label],
                "quantifier_key": (
                    quantifiers[label].predicate
                    + "@"
                    + quantifier_bound_predicates[label]
                ),
                "depth": depths[label],
            }
            for label in sorted(quantifiers, key=lambda item: depths[item])
        ]
        predicate_order = [item["predicate"] for item in quantifier_order]
        quantifier_key_order = [item["quantifier_key"] for item in quantifier_order]
        oracle_match = next(
            (
                item["reading"]
                for item in oracle
                if (
                    item.get("quantifier_keys") == quantifier_key_order
                    or item.get("quantifier_order") == predicate_order
                )
            ),
            None,
        )
        constraint_evidence = []
        for constraint in m.hcons:
            path = [bindings[constraint.hi]]
            while path[-1] != constraint.lo:
                current_label = path[-1]
                if current_label not in body_holes:
                    raise RuntimeError("Solver model violates a qeq constraint")
                path.append(bindings[body_holes[current_label]])
            constraint_evidence.append(
                {
                    "high": constraint.hi,
                    "relation": str(constraint.relation),
                    "low": constraint.lo,
                    "satisfied": True,
                    "label_path": path,
                }
            )
        identity_payload = json.dumps(
            {
                "source_candidate_id": source_candidate_id,
                "bindings": bindings,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        solution_id = "scope:" + hashlib.sha256(
            identity_payload.encode("utf-8")
        ).hexdigest()
        solutions.append(
            {
                "solution_id": solution_id,
                "source_candidate_id": source_candidate_id,
                "bindings": bindings,
                "root_label": root_label,
                "label_depths": depths,
                "dominance_edges": dominance_edges,
                "quantifier_order": quantifier_order,
                "scope_order_key": " > ".join(quantifier_key_order),
                "satisfied_handle_constraints": constraint_evidence,
                "test_oracle_reading": oracle_match,
            }
        )
        solver.add(
            Or(
                *[
                    variable != model[variable].as_long()
                    for variable in plug.values()
                ]
            )
        )

    truncated = len(solutions) == max_solutions and solver.check() == sat
    solution_ids = [solution["solution_id"] for solution in solutions]
    alternative_set_id = "scope-alternatives:" + source_candidate_id.split(":", 1)[1]
    for solution in solutions:
        solution["alternative_set_id"] = alternative_set_id
        solution["incompatible_with"] = [
            solution_id
            for solution_id in solution_ids
            if solution_id != solution["solution_id"]
        ]
        solution["equivalent_scope_order_to"] = [
            other["solution_id"]
            for other in solutions
            if other["solution_id"] != solution["solution_id"]
            and other["scope_order_key"] == solution["scope_order_key"]
        ]
    return {
        "status": "resolved" if solutions else "unsatisfiable",
        "solver": "Z3",
        "solver_version": z3.get_version_string(),
        "max_solutions": max_solutions,
        "truncated": truncated,
        "label_count": len(labels),
        "hole_count": len(holes),
        "solutions": solutions,
    }
def candidate_from_result(fixture: dict[str, Any], rank: int, result: Any) -> dict[str, Any]:
    m = result.mrs()
    raw_mrs = result.get("mrs")
    raw_tree = result.get("tree")
    raw_derivation = result.get("derivation")
    derivation = result.derivation().to_dict()
    signature = derivation_signature(derivation)
    identity_payload = json.dumps(
        {
            "sentence": fixture["sentence"],
            "mrs": raw_mrs,
            "tree": raw_tree,
            "derivation": signature,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    candidate_id = "analysis:" + hashlib.sha256(
        identity_payload.encode("utf-8")
    ).hexdigest()
    flags = dict(result.get("flags", []))
    predicates = [ep.predicate for ep in m.rels]
    return {
        "candidate_id": candidate_id,
        "rank": rank,
        "ace_result_id": result.get("result-id"),
        "score": flags.get(":ascore"),
        "probability": flags.get(":probability"),
        "support": {"source_observation_id": f"source:{fixture['id']}"},
        "producer": {"parser": "ACE", "grammar": "ERG", "decoder": "PyDelphin"},
        "quality": {
            "mrs_validation": mrs_validation(m),
            "contains_unknown_predicate": "unknown" in predicates,
            "contains_individual_constraints": bool(m.icons),
        },
        "syntax_tree": result.tree(),
        "derivation_signature": signature,
        "derivation_rules": derivation_rules(signature),
        "mrs": mrs_summary(m),
        "scope": {
            "representation": "underspecified MRS",
            "quantifier_count": sum(m.is_quantifier(ep.id) for ep in m.rels),
            "handle_constraint_count": len(m.hcons),
            "resolved_readings_returned_by_ace_erg_pydelphin": [],
            "resolution": None,
        },
        "phenomenon_observation": (
            attachment_observation(m) if fixture["id"] == "attachment" else None
        ),
        "raw": {
            "mrs": raw_mrs,
            "tree": raw_tree,
            "derivation": raw_derivation,
        },
        "_mrs_object": m,
    }


def compare_to_first(candidate: dict[str, Any], first: dict[str, Any]) -> dict[str, Any]:
    candidate_predicates = Counter(
        ep["predicate"] for ep in candidate["mrs"]["predications"]
    )
    first_predicates = Counter(ep["predicate"] for ep in first["mrs"]["predications"])
    candidate_rules = Counter(candidate["derivation_rules"])
    first_rules = Counter(first["derivation_rules"])
    return {
        "reference_candidate_id": first["candidate_id"],
        "same_candidate": candidate["candidate_id"] == first["candidate_id"],
        "mrs_isomorphic": mrs.is_isomorphic(
            candidate["_mrs_object"], first["_mrs_object"], properties=True
        ),
        "syntax_tree_equal": candidate["syntax_tree"] == first["syntax_tree"],
        "derivation_equal": (
            candidate["derivation_signature"] == first["derivation_signature"]
        ),
        "predicates_added": expanded_counter_difference(
            candidate_predicates, first_predicates
        ),
        "predicates_removed": expanded_counter_difference(
            first_predicates, candidate_predicates
        ),
        "derivation_rules_added": expanded_counter_difference(
            candidate_rules, first_rules
        ),
        "derivation_rules_removed": expanded_counter_difference(
            first_rules, candidate_rules
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
    results: list[dict[str, Any]], max_results: int, max_scope_results: int
) -> None:
    if {result["id"] for result in results} != {
        "attachment",
        "structural",
        "scope",
        "scope-three-quantifiers",
    }:
        raise RuntimeError(
            "NLP-03 requires attachment, structural, and two scope fixtures."
        )
    all_ids = []
    for result in results:
        if result["returned_analysis_count"] < 2:
            raise RuntimeError(f"No competing parses for {result['id']}")
        if result["returned_analysis_count"] > max_results:
            raise RuntimeError(f"Result cap exceeded for {result['id']}")
        all_ids.extend(candidate["candidate_id"] for candidate in result["analyses"])
        expected_pair_count = (
            result["returned_analysis_count"]
            * (result["returned_analysis_count"] - 1)
            // 2
        )
        if len(result["pairwise_comparisons"]) != expected_pair_count:
            raise RuntimeError(f"Incomplete pairwise comparison for {result['id']}")
        if not result["analyses"][0]["quality"]["mrs_validation"]["well_formed"]:
            raise RuntimeError(f"Top-ranked MRS is malformed for {result['id']}")
    if len(all_ids) != len(set(all_ids)):
        raise RuntimeError("Candidate IDs are not unique.")

    attachment = next(result for result in results if result["id"] == "attachment")
    heads = {
        candidate["phenomenon_observation"]["arg1_introduced_by"]
        for candidate in attachment["analyses"]
        if candidate["phenomenon_observation"] is not None
    }
    if len(heads) < 2:
        raise RuntimeError("Attachment alternatives are no longer structurally distinct.")

    scope_result = next(result for result in results if result["id"] == "scope")
    top_scope = scope_result["analyses"][0]["scope"]
    if top_scope["quantifier_count"] < 2 or top_scope["handle_constraint_count"] < 2:
        raise RuntimeError("Scope fixture no longer exposes underspecified scope.")
    resolution = top_scope["resolution"]
    if resolution["status"] != "resolved":
        raise RuntimeError("Canonical scope analysis was not resolved.")
    orders = {
        tuple(item["predicate"] for item in solution["quantifier_order"])
        for solution in resolution["solutions"]
    }
    expected_orders = {("_every_q", "_a_q"), ("_a_q", "_every_q")}
    if max_scope_results >= 2 and (
        orders != expected_orders or resolution["truncated"]
    ):
        raise RuntimeError(f"Unexpected canonical scope solutions: {orders}")
    if max_scope_results == 1 and (
        len(orders) != 1 or not orders <= expected_orders or not resolution["truncated"]
    ):
        raise RuntimeError("Scope limit/truncation is not represented correctly.")
    if any(solution["test_oracle_reading"] is None for solution in resolution["solutions"]):
        raise RuntimeError("A canonical scope solution does not match the test oracle.")

    three_scope_result = next(
        result for result in results if result["id"] == "scope-three-quantifiers"
    )
    three_resolution = three_scope_result["analyses"][0]["scope"]["resolution"]
    three_orders = {
        tuple(item["quantifier_key"] for item in solution["quantifier_order"])
        for solution in three_resolution["solutions"]
    }
    expected_three_orders = {
        tuple(item["quantifier_keys"])
        for item in three_scope_result["scope_readings_are_test_oracle"]
    }
    expected_three_count = min(max_scope_results, len(expected_three_orders))
    if len(three_orders) != expected_three_count or not three_orders <= expected_three_orders:
        raise RuntimeError(f"Unexpected three-quantifier solutions: {three_orders}")
    if max_scope_results >= len(expected_three_orders):
        if three_resolution["truncated"] or three_orders != expected_three_orders:
            raise RuntimeError("Three-quantifier enumeration is incomplete.")
    elif not three_resolution["truncated"]:
        raise RuntimeError("Three-quantifier truncation was not reported.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ace", type=Path, default=DEFAULT_ACE)
    parser.add_argument("--grammar", type=Path, default=DEFAULT_GRAMMAR)
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    parser.add_argument(
        "--max-scope-results", type=int, default=DEFAULT_MAX_SCOPE_RESULTS
    )
    args = parser.parse_args()
    if args.max_results < 3:
        parser.error("--max-results must be at least 3 for ambiguity coverage")
    if args.max_scope_results < 1:
        parser.error("--max-scope-results must be positive")
    if not args.ace.is_file() or not args.grammar.is_file():
        parser.error("ACE or ERG is missing; run ./scripts/seman2 install-tools")

    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_raw(
        args.ace,
        args.grammar,
        [fixture["sentence"] for fixture in fixtures],
        args.max_results,
        raw_dir,
    )

    results = []
    raw_records = []
    with ace.ACEParser(
        str(args.grammar),
        executable=str(args.ace),
        cmdargs=["-n", str(args.max_results)],
    ) as process:
        for fixture in fixtures:
            response = process.interact(fixture["sentence"])
            candidates = [
                candidate_from_result(fixture, rank, result)
                for rank, result in enumerate(response.results(), start=1)
            ]
            if not candidates:
                raise RuntimeError(f"ACE returned no analysis for {fixture['id']}")
            parse_alternative_set_id = f"parse-alternatives:{fixture['id']}"
            candidate_ids = [candidate["candidate_id"] for candidate in candidates]
            for candidate in candidates:
                candidate["alternative_set_id"] = parse_alternative_set_id
                candidate["competes_with"] = [
                    candidate_id
                    for candidate_id in candidate_ids
                    if candidate_id != candidate["candidate_id"]
                ]
                if "scope_readings_are_test_oracle" in fixture:
                    candidate["scope"]["resolution"] = resolve_scopes(
                        candidate["_mrs_object"],
                        candidate["candidate_id"],
                        args.max_scope_results,
                        fixture["scope_readings_are_test_oracle"],
                    )
            first = candidates[0]
            for candidate in candidates:
                candidate["difference_from_rank_1"] = compare_to_first(candidate, first)
                raw_records.append(
                    {
                        "fixture": fixture["id"],
                        "candidate_id": candidate["candidate_id"],
                        "rank": candidate["rank"],
                        **candidate["raw"],
                    }
                )
            pairwise_comparisons = []
            for left_index, left in enumerate(candidates):
                for right in candidates[left_index + 1 :]:
                    comparison = compare_to_first(right, left)
                    comparison["candidate_id"] = right["candidate_id"]
                    pairwise_comparisons.append(comparison)
            for candidate in candidates:
                del candidate["_mrs_object"]
                del candidate["raw"]

            results.append(
                {
                    **fixture,
                    "source_observation": {
                        "id": f"source:{fixture['id']}",
                        "text": fixture["sentence"],
                        "span": [0, len(fixture["sentence"])],
                    },
                    "status": "parsed",
                    "returned_analysis_count": len(candidates),
                    "limit_reached": len(candidates) == args.max_results,
                    "parse_candidates_are_scope_readings": False,
                    "scope_assessment": (
                        {
                            "underspecified_constraints_available": True,
                            "explicit_resolved_readings_from_ace_erg_pydelphin": 0,
                            "explicit_resolved_readings_from_z3_adapter": sum(
                                len(candidate["scope"]["resolution"]["solutions"])
                                for candidate in candidates
                            ),
                            "canonical_parse_resolved_readings": len(
                                candidates[0]["scope"]["resolution"]["solutions"]
                            ),
                            "status": "resolved_by_poc_z3_adapter",
                        }
                        if "scope_readings_are_test_oracle" in fixture
                        else None
                    ),
                    "pairwise_comparisons": pairwise_comparisons,
                    "analyses": candidates,
                }
            )

    validate(results, args.max_results, args.max_scope_results)
    all_candidates = [candidate for result in results for candidate in result["analyses"]]
    summary = {
        "verdict": "GO_CONCURRENT_PARSE_AND_SCOPE_CANDIDATES_RETAINED",
        "fixture_count": len(results),
        "candidate_count": len(all_candidates),
        "by_fixture": {
            result["id"]: result["returned_analysis_count"] for result in results
        },
        "well_formed_mrs": sum(
            candidate["quality"]["mrs_validation"]["well_formed"]
            for candidate in all_candidates
        ),
        "fallback_unknown_candidates": sum(
            candidate["quality"]["contains_unknown_predicate"]
            for candidate in all_candidates
        ),
        "candidates_with_score": sum(
            candidate["score"] is not None for candidate in all_candidates
        ),
        "scope": {
            "underspecified_mrs_available": True,
            "resolved_readings_from_ace_erg_pydelphin": 0,
            "resolved_readings_from_z3_adapter": sum(
                len(candidate["scope"]["resolution"]["solutions"])
                for result in results
                if result["scope_assessment"] is not None
                for candidate in result["analyses"]
            ),
            "canonical_parse_resolved_readings": len(
                next(result for result in results if result["id"] == "scope")[
                    "analyses"
                ][0]["scope"]["resolution"]["solutions"]
            ),
            "canonical_three_quantifier_readings": len(
                next(
                    result
                    for result in results
                    if result["id"] == "scope-three-quantifiers"
                )["analyses"][0]["scope"]["resolution"]["solutions"]
            ),
            "verdict": "GO with the POC Z3 scope adapter",
        },
    }
    (output_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (raw_dir / "candidates.json").write_text(
        json.dumps(raw_records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
            "sha256": sha256_file(args.grammar),
            "label_reported_by_ace": "ERG (2018)",
        },
        "pydelphin": importlib.metadata.version("pydelphin"),
        "z3": z3.get_version_string(),
        "parameters": {
            "max_results": args.max_results,
            "max_scope_results": args.max_scope_results,
            "all_returned_analyses_are_retained": True,
            "candidate_identity": (
                "SHA-256 of sentence + raw MRS + raw syntax tree + derivation "
                "without transient edge IDs and scores"
            ),
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"NLP-03: {len(all_candidates)} candidates retained")
    for result in results:
        print(
            f"{result['id']:12} {result['returned_analysis_count']} analysis(es), "
            f"limit_reached={result['limit_reached']}"
        )
    print(
        f"quality: {summary['well_formed_mrs']}/{len(all_candidates)} well-formed; "
        f"{summary['fallback_unknown_candidates']} fallback unknown"
    )
    print(
        "scope: "
        f"{summary['scope']['canonical_parse_resolved_readings']} canonical "
        "reading(s) resolved by the Z3 adapter"
    )


if __name__ == "__main__":
    main()
