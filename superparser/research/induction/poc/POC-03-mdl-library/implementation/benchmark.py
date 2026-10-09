"""Dedicated POC-03 benchmark over 4,500 training observations."""

from __future__ import annotations

import argparse
import gc
from hashlib import sha256
import json
from pathlib import Path
import random
import time
import tracemalloc
from typing import Any

from research.induction import ComponentLibrary, ObservationExample, parse_to_observation
from seman_parser.chart import ChartItem, PackedNode, ParseResult, Provenance
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import LexicalLattice, tokenize
from seman_parser.semantics import SemanticGraph, SemanticPackage


POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures" / "manifest.json"


def item(
    category: str,
    start: int,
    end: int,
    *,
    rule_id: str | None = None,
    features: dict[str, object] | None = None,
    children: tuple[ChartItem, ...] = (),
    surface: str | None = None,
) -> ChartItem:
    detail: dict[str, object] = {"rule_id": rule_id} if rule_id else {}
    if surface is not None:
        detail.update({"surface": surface, "lemma": surface.lower()})
    return ChartItem(
        start=start,
        end=end,
        category=category,
        features=FeatureStructure.build(features or {}),
        semantic=SemanticPackage(SemanticGraph()),
        score=1.0,
        provenance=Provenance(source="rule" if rule_id else "fixture", detail=detail),
        children=children,
        rule_id=rule_id,
    )


def clause_graph(
    subject: str,
    verb: str,
    object_: str,
    *,
    rule_id: str,
    features: dict[str, object] | None = None,
):
    text = f"{subject} {verb} {object_}"
    verb_start = len(subject) + 1
    object_start = verb_start + len(verb) + 1
    subject_node = item("NP", 0, len(subject), surface=subject)
    verb_node = item("V", verb_start, verb_start + len(verb), surface=verb)
    object_node = item("NP", object_start, len(text), surface=object_)
    vp = item(
        "VP",
        verb_start,
        len(text),
        rule_id="vp_transitive",
        features={"voice": "active"},
        children=(verb_node, object_node),
    )
    root = item(
        "CLAUSE",
        0,
        len(text),
        rule_id=rule_id,
        features=features,
        children=(subject_node, vp),
    )
    nodes = (root, subject_node, vp, verb_node, object_node)
    packed = {
        (node.start, node.end, index): PackedNode(
            start=node.start,
            end=node.end,
            category=node.category,
            best=node,
            alternatives=[node],
        )
        for index, node in enumerate(nodes)
    }
    result = ParseResult(
        text=text,
        lattice=LexicalLattice(text=text, tokens=tokenize(text), candidates=()),
        packed=packed,
        roots=(root,),
        completed=True,
    )
    return parse_to_observation(result, parser_version="fixture")


def observation(
    observation_id: str,
    subject: str,
    verb: str,
    object_: str,
    *,
    rule_id: str,
    features: dict[str, object] | None = None,
) -> ObservationExample:
    graph = clause_graph(
        subject,
        verb,
        object_,
        rule_id=rule_id,
        features=features,
    )
    return ObservationExample(observation_id, graph, graph.root_ids[0])


def build_dataset(case: dict[str, Any], rng: random.Random):
    if case["kind"] == "repetitive":
        training: list[ObservationExample] = []
        heldout: list[ObservationExample] = []
        families = (("family-a", "sees"), ("family-b", "opens"))
        for family_index, (rule_id, verb) in enumerate(families):
            for index in range(case["training_per_family"]):
                salt = rng.randrange(10**9)
                training.append(
                    observation(
                        f"train-{family_index}-{index}",
                        f"person-{salt}",
                        verb,
                        f"thing-{index}",
                        rule_id=rule_id,
                    )
                )
            for index in range(case["heldout_per_family"]):
                salt = rng.randrange(10**9)
                heldout.append(
                    observation(
                        f"heldout-{family_index}-{index}",
                        f"novel-person-{salt}",
                        verb,
                        f"novel-thing-{index}",
                        rule_id=rule_id,
                    )
                )
        for index in range(case["training_exceptions"]):
            training.append(
                observation(
                    f"exception-{index}",
                    f"noise-subject-{rng.randrange(10**9)}",
                    f"noise-verb-{index}",
                    f"noise-object-{rng.randrange(10**9)}",
                    rule_id=f"unique-exception-{index}",
                )
            )
        return training, heldout

    if case["kind"] == "unique":
        training = [
            observation(
                f"unique-{index}",
                f"subject-{rng.randrange(10**9)}",
                f"verb-{rng.randrange(10**9)}",
                f"object-{rng.randrange(10**9)}",
                rule_id=f"unique-rule-{index}",
            )
            for index in range(case["training_count"])
        ]
        return training, []

    if case["kind"] == "variable_heavy":
        training = []
        for index in range(case["training_count"]):
            features = {
                f"open-{slot}": f"{rng.randrange(10**9)}-{slot}"
                for slot in range(case["open_feature_count"])
            }
            training.append(
                observation(
                    f"wide-{index}",
                    f"subject-{index}",
                    f"verb-{index}",
                    f"object-{index}",
                    rule_id="variable-heavy",
                    features=features,
                )
            )
        return training, []
    raise ValueError(f"unknown dataset kind: {case['kind']}")


def run(manifest_path: Path) -> dict[str, Any]:
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    rng = random.Random(manifest["seed"])
    policy = manifest["library_policy"]
    rows: list[dict[str, Any]] = []

    for case in manifest["datasets"]:
        training, heldout = build_dataset(case, rng)
        library = ComponentLibrary(**policy)
        gc.collect()
        tracemalloc.start()
        started = time.perf_counter()
        training_report = library.fit(training)
        training_ms = (time.perf_counter() - started) * 1000
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        library.freeze()
        heldout_report = library.evaluate_heldout(heldout) if heldout else None

        expected_count = case["expected_component_count"]
        positive_gain = training_report.gain_vs_raw_bits > 0
        expectation_met = (
            training_report.reconstruction_rate == 1.0
            and training_report.component_count == expected_count
            and positive_gain == case["expected_positive_gain"]
        )
        if case["kind"] == "repetitive":
            expectation_met = expectation_met and (
                training_report.b3_library_bits < training_report.b1_exact_dictionary_bits
                and training_report.b3_library_bits < training_report.b2_single_component_bits
                and heldout_report is not None
                and heldout_report["reconstruction_rate"] == 1.0
                and heldout_report["component_uses"] / len(heldout)
                >= case["minimum_heldout_component_rate"]
            )
        rows.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "training_count": len(training),
                "heldout_count": len(heldout),
                "training": training_report.as_dict(),
                "heldout": heldout_report,
                "training_ms": round(training_ms, 3),
                "peak_memory_mb": round(peak / (1024 * 1024), 3),
                "expectation_met": expectation_met,
            }
        )

    return {
        "poc": "POC-03",
        "schema_version": manifest["schema_version"],
        "seed": manifest["seed"],
        "data_manifest": sha256(raw_manifest).hexdigest(),
        "training_observation_count": sum(row["training_count"] for row in rows),
        "heldout_observation_count": sum(row["heldout_count"] for row in rows),
        "case_expectation_rate": sum(row["expectation_met"] for row in rows) / len(rows),
        "peak_memory_mb": max(row["peak_memory_mb"] for row in rows),
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
