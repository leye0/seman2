"""POC-13 comparison using one evidence vector for every architecture."""

from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from research.induction import (
    AlignmentPolicy,
    AntiUnificationError,
    GraphNode,
    ObservationGraph,
    anti_unify,
    compare_architectures,
)
from research.induction.corpus_evidence import load_real_corpus


POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures/manifest.json"
ROOT = Path(__file__).resolve().parents[6]
POC_ROOT = ROOT / "superparser/research/induction/poc"
DEFAULT_CACHE_DIR = ROOT / ".local/cache/seman2/induction"


def read_result(poc_dir: str, name: str = "results.json") -> dict:
    return json.loads((POC_ROOT / poc_dir / name).read_text(encoding="utf-8"))


def polarity_graph(observation_id: str, negation: str) -> ObservationGraph:
    node = GraphNode.build(
        kind="CONSTITUENT",
        properties={
            "category": "CLAUSE",
            "rule_id": "controlled-clause",
            "origin": "controlled",
            "features": {"negation": negation},
            "span": [0, 1],
        },
    )
    graph = ObservationGraph(
        observation_id=observation_id,
        text=observation_id,
        completed=True,
        parser_version="controlled-poc13",
        nodes=(node,),
        edges=(),
        root_ids=(node.node_id,),
        forest_ids=(),
        selection_policy="controlled",
        selection_provisional=False,
    )
    identity = json.dumps(
        graph._identity_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    graph = replace(
        graph,
        observation_id="observation_" + sha256(identity.encode("utf-8")).hexdigest()[:24],
    )
    graph.validate()
    return graph


def central_ablations(poc03: dict, poc04: dict, poc11: dict) -> dict:
    positive = polarity_graph("positive", "false")
    negative = polarity_graph("negative", "true")
    constrained_rejected = False
    try:
        anti_unify(positive, positive.root_ids[0], negative, negative.root_ids[0])
    except AntiUnificationError:
        constrained_rejected = True
    unconstrained = anti_unify(
        positive,
        positive.root_ids[0],
        negative,
        negative.root_ids[0],
        policy=AlignmentPolicy(protected_features=frozenset()),
    )
    repetitive = poc03["repetitive"]
    return {
        "composition": {
            "evidence": "temporary_controlled",
            "training_loss_without_composition_bits": poc04["training"]["gain_bits"],
            "heldout_loss_without_composition_bits": poc04["heldout"]["gain_bits"],
        },
        "mdl": {
            "evidence": "temporary_controlled",
            "library_compression_ratio": repetitive["compression_ratio"],
            "loss_without_library_bits": repetitive["b0_raw_bits"] - repetitive["b3_library_bits"],
        },
        "variable_constraints": {
            "evidence": "temporary_controlled",
            "polarity_mismatch_rejected_with_constraints": constrained_rejected,
            "polarity_mismatch_accepted_without_constraints": unconstrained is not None,
        },
        "deltas": {
            "evidence": "temporary_controlled",
            "alignments_with_deltas": poc11["controlled"]["alignment_count"],
            "alignments_without_deltas": poc11["controlled"]["without_delta_alignment_count"],
        },
    }


def run(path: Path, cache_dir: Path) -> dict:
    raw = path.read_bytes()
    config = json.loads(raw)
    graphs = load_real_corpus(cache_dir, required=config["required_observations"])
    for graph in graphs:
        graph.validate()

    poc03 = read_result("POC-03-mdl-library")
    poc04 = read_result("POC-04-recursive-composition")
    poc06 = read_result("POC-06-latent-referent-classes")
    poc07 = read_result("POC-07-latent-relations")
    poc08 = read_result("POC-08-partial-state-delta")
    poc09 = read_result("POC-09-transition-induction")
    poc09_controlled = read_result("POC-09-transition-induction", "results_controlled.json")
    poc10 = read_result("POC-10-revision")
    poc11 = read_result("POC-11-cross-construction")
    poc12 = read_result("POC-12-incremental-learning")

    real_counts = {
        row["poc"]: row.get("observation_count", row.get("real_audit", {}).get("observation_count"))
        for row in (poc06, poc07, poc08, poc09, poc10, poc11, poc12)
    }
    common = {
        "real_observation_count": len(graphs),
        "compact_graph_validation_rate": 1.0,
        "referent_test_f1": poc06["test"]["f1"],
        "relation_test_predictions": poc07["test_prediction_count"],
        "relation_test_precision": poc07["test_precision"],
        "transition_real_precision": poc09["learned"]["precision"],
        "transition_real_recall": poc09["learned"]["recall"],
        "transition_controlled_f1": poc09_controlled["heldout_f1"],
        "revision_controlled_error_reduction": poc10["controlled"]["error_reduction"],
        "transfer_real_precision": poc11["real_audit"]["heldout_precision"],
        "transfer_real_recall": poc11["real_audit"]["heldout_recall"],
        "incremental_component_count": poc12["batch_component_count"],
        "incremental_max_p99_ms": max(row["p99_ms"] for row in poc12["runs"]),
        "incremental_comparison_fraction": poc12["maximum_comparison_fraction"],
    }
    comparison = compare_architectures(
        common, failed_capabilities=config["failed_real_capabilities"]
    )
    same_evidence = all(
        row["measurements"] == comparison["candidates"][0]["measurements"]
        for row in comparison["candidates"]
    )
    all_real_counts_valid = all(
        count == config["required_observations"] for count in real_counts.values()
    )
    passed = (
        same_evidence
        and all_real_counts_valid
        and comparison["provisional_choice"] == config["expected_provisional_choice"]
        and all(row["topology"]["duplicated_primitive_count"] == 0 for row in comparison["candidates"])
    )
    return {
        "poc": "POC-13",
        "manifest_sha256": sha256(raw).hexdigest(),
        "real_observation_counts": real_counts,
        "same_empirical_evidence_for_all_candidates": same_evidence,
        "comparison": comparison,
        "ablations": central_ablations(poc03, poc04, poc11),
        "passed": passed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.manifest, args.cache_dir), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
