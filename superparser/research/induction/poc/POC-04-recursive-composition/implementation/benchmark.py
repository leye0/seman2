"""Dedicated POC-04 benchmark for two learned composition levels."""

from __future__ import annotations

import argparse
import gc
from hashlib import sha256
import json
import math
from pathlib import Path
import time
import tracemalloc
from typing import Any

from research.induction import (
    ComponentComposer,
    ComponentTemplate,
    CompositionCycleError,
    PatternEdge,
    PatternNode,
    canonicalize_template,
    composed_instance_bits,
    composition_depth,
    composition_is_promotable,
    hierarchical_model_bits,
    instance_description_bits,
    template_description_bits,
    validate_dependency_graph,
)


POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures" / "manifest.json"


def template_from_pattern(pattern: dict[str, Any], name: str) -> ComponentTemplate:
    nodes: list[PatternNode] = []
    edges: list[PatternEdge] = []

    def build(value: dict[str, Any]) -> str:
        node_id = f"N{len(nodes)}"
        properties = {key: child for key, child in value.items() if key != "children"}
        nodes.append(
            PatternNode(
                node_id,
                "CONSTITUENT",
                json.dumps(properties, sort_keys=True, separators=(",", ":")),
            )
        )
        for position, child in enumerate(value.get("children", ())):
            child_id = build(child)
            edges.append(PatternEdge(node_id, child_id, "CHILD", position))
        return node_id

    root = build(pattern)
    return ComponentTemplate(name, root, tuple(nodes), tuple(edges))


def build_patterns(manifest: dict[str, Any]):
    base: dict[str, Any] = {
        "category": "LEXICAL_CORE",
        "lexeme": {"$var": "lexeme"},
        "referent": {"$var": "referent"},
        "children": [],
    }
    for depth in range(manifest["base_depth"]):
        base = {
            "category": f"BASE_LAYER_{depth}",
            "invariant": f"base-constant-{depth}",
            "children": [base],
        }
    middles = [
        {
            "category": f"MIDDLE_{index}",
            "middle_constant": f"middle-{index}",
            "middle_value": {"$var": "middle_value"},
            "children": [base],
        }
        for index in range(manifest["middle_contexts"])
    ]
    tops = [
        {
            "category": f"TOP_{index}",
            "top_constant": f"top-{index}",
            "top_value": {"$var": "top_value"},
            "children": [middles[index % len(middles)]],
        }
        for index in range(manifest["top_contexts"])
    ]
    return base, middles, tops


def selector_bits(count: int) -> int:
    return max(1, math.ceil(math.log2(count + 1)))


def count_bits(count: int) -> int:
    width = (count + 1).bit_length()
    return 2 * width - 1


def run(manifest_path: Path) -> dict[str, Any]:
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    base_pattern, middle_patterns, top_patterns = build_patterns(manifest)
    composer = ComponentComposer()
    base = composer.register_atomic(template_from_pattern(base_pattern, "base"))

    middles = []
    for index, pattern in enumerate(middle_patterns):
        component = composer.discover_composition(
            template_from_pattern(pattern, f"middle-flat-{index}"),
            (base.component_id,),
        )
        if component is None:
            raise RuntimeError("failed to discover middle composition")
        middles.append(component)

    tops = []
    flat_tops = []
    for index, pattern in enumerate(top_patterns):
        flat, _ = canonicalize_template(template_from_pattern(pattern, f"top-flat-{index}"))
        component = composer.discover_composition(
            flat,
            (middles[index % len(middles)].component_id,),
        )
        if component is None:
            raise RuntimeError("failed to discover top composition")
        flat_tops.append(flat)
        tops.append(component)

    root_count = len(tops)
    select_bits = selector_bits(root_count)
    flat_model_bits = count_bits(root_count) + sum(
        template_description_bits(template) for template in flat_tops
    )
    recursive_model_bits = hierarchical_model_bits(
        composer, [component.component_id for component in tops]
    )

    def measure_instances(per_top: int, split: str):
        flat_data = count_bits(per_top * root_count)
        recursive_data = count_bits(per_top * root_count)
        exact = 0
        instance_count = 0
        for top_index, (flat, component) in enumerate(zip(flat_tops, tops)):
            flat_variables = tuple(
                sorted(
                    {
                        value["$var"]
                        for node in flat.nodes
                        for value in _walk(node.properties)
                        if isinstance(value, dict) and set(value) == {"$var"}
                    }
                )
            )
            for index in range(per_top):
                flat_bindings = {
                    name: f"{split}-{top_index}-{name}-{index}"
                    for name in flat_variables
                }
                snapshot = flat.instantiate(flat_bindings)
                recursive_bindings = composer.match(component.component_id, snapshot)
                if recursive_bindings is None:
                    raise RuntimeError("recursive component failed to match source")
                rebuilt = composer.instantiate(component.component_id, recursive_bindings)
                exact += rebuilt == snapshot
                flat_data += instance_description_bits(
                    flat, flat_bindings, selector_bits=select_bits
                )
                recursive_data += composed_instance_bits(
                    composer,
                    component.component_id,
                    recursive_bindings,
                    selector_bits=select_bits,
                )
                instance_count += 1
        return {
            "observation_count": instance_count,
            "flat_data_bits": flat_data,
            "recursive_data_bits": recursive_data,
            "reconstruction_rate": exact / instance_count,
        }

    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    training = measure_instances(manifest["training_per_top"], "train")
    elapsed_ms = (time.perf_counter() - started) * 1000
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    heldout = measure_instances(manifest["heldout_per_top"], "heldout")

    training["flat_total_bits"] = flat_model_bits + training["flat_data_bits"]
    training["recursive_total_bits"] = recursive_model_bits + training["recursive_data_bits"]
    training["gain_bits"] = training["flat_total_bits"] - training["recursive_total_bits"]
    training["compression_ratio_vs_flat"] = (
        training["recursive_total_bits"] / training["flat_total_bits"]
    )
    heldout["gain_bits"] = heldout["flat_data_bits"] - heldout["recursive_data_bits"]
    heldout["compression_ratio_vs_flat"] = (
        heldout["recursive_data_bits"] / heldout["flat_data_bits"]
    )
    depths = [composition_depth(composer, component.component_id) for component in tops]
    policy = manifest["policy"]
    roots_promotable = all(
        composition_is_promotable(
            support=manifest["training_per_top"],
            gain_bits=training["gain_bits"],
            depth=depth,
            **policy,
        )
        for depth in depths
    )
    one_off_rejected = not composition_is_promotable(
        support=1,
        gain_bits=max(1, training["gain_bits"]),
        depth=max(depths),
        **policy,
    )
    try:
        validate_dependency_graph({"A": ("B",), "B": ("A",)})
        cycle_rejected = False
    except CompositionCycleError:
        cycle_rejected = True

    expectations = (
        training["reconstruction_rate"] == 1.0
        and heldout["reconstruction_rate"] == 1.0
        and min(depths) >= manifest["thresholds"]["minimum_real_depth"]
        and training["gain_bits"] > 0
        and roots_promotable
        and one_off_rejected
        and cycle_rejected
    )
    return {
        "poc": "POC-04",
        "schema_version": manifest["schema_version"],
        "seed": manifest["seed"],
        "data_manifest": sha256(raw_manifest).hexdigest(),
        "atomic_component_count": 1,
        "middle_component_count": len(middles),
        "top_component_count": len(tops),
        "shared_definition_count": len(composer.components),
        "maximum_depth": max(depths),
        "flat_model_bits": flat_model_bits,
        "recursive_model_bits": recursive_model_bits,
        "training": training,
        "heldout": heldout,
        "roots_promotable": roots_promotable,
        "single_use_rejected": one_off_rejected,
        "cycle_rejected": cycle_rejected,
        "expectation_met": expectations,
        "evaluation_ms": round(elapsed_ms, 3),
        "peak_memory_mb": round(peak / (1024 * 1024), 3),
    }


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
