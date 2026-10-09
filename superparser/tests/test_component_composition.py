"""POC-04 tests for recursive component composition."""

from __future__ import annotations

import json
import unittest

from research.induction import (
    ComponentCall,
    ComponentComposer,
    ComponentTemplate,
    CompositionCycleError,
    composition_is_promotable,
    PatternEdge,
    PatternNode,
    hierarchical_model_bits,
    template_description_bits,
    validate_dependency_graph,
)


def template_from_pattern(pattern: dict, component_id: str = "fixture") -> ComponentTemplate:
    nodes: list[PatternNode] = []
    edges: list[PatternEdge] = []

    def build(value: dict) -> str:
        node_id = f"n{len(nodes)}"
        properties = {key: child for key, child in value.items() if key != "children"}
        nodes.append(PatternNode(node_id, "CONSTITUENT", json.dumps(properties)))
        for position, child in enumerate(value.get("children", ())):
            child_id = build(child)
            edges.append(PatternEdge(node_id, child_id, "CHILD", position))
        return node_id

    root = build(pattern)
    return ComponentTemplate(component_id, root, tuple(nodes), tuple(edges))


def port_shell(category: str = "WRAP", ports: int = 1) -> ComponentTemplate:
    root = PatternNode("root", "CONSTITUENT", json.dumps({"category": category}))
    nodes = [root]
    edges = []
    for index in range(ports):
        node_id = f"port-{index}"
        nodes.append(
            PatternNode(
                node_id,
                "SUBGRAPH_PORT",
                json.dumps(
                    {
                        "port": {"$var": f"P{index}"},
                        "accepts_category": "LEAF",
                    }
                ),
            )
        )
        edges.append(PatternEdge("root", node_id, "CHILD", index))
    return ComponentTemplate("shell", "root", tuple(nodes), tuple(edges))


LEAF_PATTERN = {
    "category": "LEAF",
    "surface": {"$var": "word"},
    "children": [],
}


class CompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = ComponentComposer()
        self.leaf = self.composer.register_atomic(template_from_pattern(LEAF_PATTERN))

    def test_shared_outer_variable_preserves_identity_constraint(self) -> None:
        inner = self.composer.exposed_variables(self.leaf.component_id)[0]
        pair = self.composer.compose(
            port_shell("PAIR", ports=2),
            (
                ComponentCall("P0", self.leaf.component_id, ((inner, "same"),)),
                ComponentCall("P1", self.leaf.component_id, ((inner, "same"),)),
            ),
        )
        variable = self.composer.exposed_variables(pair.component_id)[0]
        snapshot = self.composer.instantiate(pair.component_id, {variable: "echo"})
        self.assertEqual(snapshot["children"][0], snapshot["children"][1])
        self.assertEqual(self.composer.match(pair.component_id, snapshot), {variable: "echo"})

        mismatch = json.loads(json.dumps(snapshot))
        mismatch["children"][1]["surface"] = "other"
        self.assertIsNone(self.composer.match(pair.component_id, mismatch))

    def test_distinct_variables_may_receive_same_value(self) -> None:
        inner = self.composer.exposed_variables(self.leaf.component_id)[0]
        pair = self.composer.compose(
            port_shell("PAIR", ports=2),
            (
                ComponentCall("P0", self.leaf.component_id, ((inner, "left"),)),
                ComponentCall("P1", self.leaf.component_id, ((inner, "right"),)),
            ),
        )
        variables = self.composer.exposed_variables(pair.component_id)
        snapshot = self.composer.instantiate(
            pair.component_id,
            {variables[0]: "same", variables[1]: "same"},
        )
        self.assertIsNotNone(self.composer.match(pair.component_id, snapshot))

    def test_composition_is_canonical_under_call_order_and_outer_renaming(self) -> None:
        inner = self.composer.exposed_variables(self.leaf.component_id)[0]
        first = self.composer.compose(
            port_shell("PAIR", ports=2),
            (
                ComponentCall("P0", self.leaf.component_id, ((inner, "a"),)),
                ComponentCall("P1", self.leaf.component_id, ((inner, "b"),)),
            ),
        )
        second = self.composer.compose(
            port_shell("PAIR", ports=2),
            (
                ComponentCall("P1", self.leaf.component_id, ((inner, "y"),)),
                ComponentCall("P0", self.leaf.component_id, ((inner, "x"),)),
            ),
        )
        self.assertEqual(first.component_id, second.component_id)

    def test_dependency_cycle_is_rejected(self) -> None:
        with self.assertRaises(CompositionCycleError):
            validate_dependency_graph({"A": ("B",), "B": ("C",), "C": ("A",)})

    def test_unknown_dependency_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            validate_dependency_graph({"A": ("missing",)})

    def test_discovers_two_real_reuse_levels_and_roundtrips(self) -> None:
        middle_pattern = {
            "category": "MIDDLE",
            "fixed": "middle",
            "children": [LEAF_PATTERN],
        }
        middle_flat = template_from_pattern(middle_pattern, "middle-flat")
        middle = self.composer.discover_composition(
            middle_flat, (self.leaf.component_id,)
        )
        self.assertIsNotNone(middle)
        assert middle is not None

        top_pattern = {
            "category": "TOP",
            "context": {"$var": "context"},
            "children": [middle_pattern],
        }
        top_flat = template_from_pattern(top_pattern, "top-flat")
        top = self.composer.discover_composition(top_flat, (middle.component_id,))
        self.assertIsNotNone(top)
        assert top is not None
        snapshot = {
            "category": "TOP",
            "context": "novel-context",
            "children": [
                {
                    "category": "MIDDLE",
                    "fixed": "middle",
                    "children": [
                        {"category": "LEAF", "surface": "novel-word", "children": []}
                    ],
                }
            ],
        }
        bindings = self.composer.match(top.component_id, snapshot)
        self.assertIsNotNone(bindings)
        assert bindings is not None
        self.assertEqual(self.composer.instantiate(top.component_id, bindings), snapshot)
        self.assertIn(middle.component_id, top.dependencies)
        self.assertIn(self.leaf.component_id, middle.dependencies)
        restored = ComponentComposer.from_dict(
            json.loads(json.dumps(self.composer.as_dict(), sort_keys=True))
        )
        restored_bindings = restored.match(top.component_id, snapshot)
        self.assertEqual(restored_bindings, bindings)
        assert restored_bindings is not None
        self.assertEqual(
            restored.instantiate(top.component_id, restored_bindings), snapshot
        )

    def test_hierarchy_factors_reused_subcomponent_model_cost(self) -> None:
        deep = LEAF_PATTERN
        for depth in range(5):
            deep = {
                "category": f"LAYER-{depth}",
                "fixed": f"constant-{depth}",
                "children": [deep],
            }
        deep_atomic = self.composer.register_atomic(template_from_pattern(deep, "deep"))
        flats = []
        composites = []
        for context in range(8):
            flat = template_from_pattern(
                {
                    "category": f"CONTEXT-{context}",
                    "fixed": f"context-constant-{context}",
                    "children": [deep],
                },
                f"flat-{context}",
            )
            flats.append(flat)
            composite = self.composer.discover_composition(
                flat, (deep_atomic.component_id,)
            )
            self.assertIsNotNone(composite)
            composites.append(composite)
        flat_bits = sum(template_description_bits(flat) for flat in flats)
        hierarchical_bits = hierarchical_model_bits(
            self.composer,
            [component.component_id for component in composites if component is not None],
        )
        self.assertLess(hierarchical_bits, flat_bits)

    def test_unrelated_subgraph_is_not_factored(self) -> None:
        unrelated = template_from_pattern(
            {"category": "OTHER", "constant": "x", "children": []}
        )
        self.assertIsNone(
            self.composer.discover_composition(unrelated, (self.leaf.component_id,))
        )

    def test_one_off_composition_is_not_promotable(self) -> None:
        self.assertFalse(
            composition_is_promotable(support=1, gain_bits=10_000, depth=3)
        )
        self.assertFalse(
            composition_is_promotable(support=100, gain_bits=10_000, depth=9)
        )
        self.assertTrue(
            composition_is_promotable(support=4, gain_bits=1, depth=3)
        )


if __name__ == "__main__":
    unittest.main()
