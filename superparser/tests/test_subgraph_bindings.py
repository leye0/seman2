"""POC-02 tests: variable-size subgraphs, ports and reference bindings."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from research.induction import (
    AntiUnificationError,
    anti_unify,
    anti_unify_with_ports,
    generalize_reference_candidates,
    parse_to_observation,
)
from seman_parser import DiscourseProcessor, Parser, __version__
from seman_parser.chart import ChartItem, PackedNode, ParseResult, Provenance
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import LexicalLattice, tokenize
from seman_parser.semantics import SemanticGraph, SemanticPackage


DATA = Path(__file__).resolve().parents[1] / "data"


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


def graph(text: str, roots: tuple[ChartItem, ...]):
    all_items: list[ChartItem] = []
    seen: set[int] = set()

    def collect(node: ChartItem) -> None:
        if id(node) in seen:
            return
        seen.add(id(node))
        all_items.append(node)
        for child in node.children:
            collect(child)

    for root in roots:
        collect(root)
    packed = {
        (node.start, node.end, index): PackedNode(
            start=node.start,
            end=node.end,
            category=node.category,
            best=node,
            alternatives=[node],
        )
        for index, node in enumerate(all_items)
    }
    result = ParseResult(
        text=text,
        lattice=LexicalLattice(text=text, tokens=tokenize(text), candidates=()),
        packed=packed,
        roots=roots,
        completed=True,
    )
    return parse_to_observation(result, parser_version="fixture")


def nested_root(graph_, root_id: str) -> dict:
    nodes = {node.node_id: node for node in graph_.nodes}
    children: dict[str, list] = {}
    for edge in graph_.edges:
        if edge.role == "CHILD":
            children.setdefault(edge.source, []).append(edge)

    def expand(node_id: str) -> dict:
        row = nodes[node_id].properties
        ordered = sorted(children.get(node_id, ()), key=lambda edge: edge.position)
        row["children"] = [expand(edge.target) for edge in ordered]
        return row

    return expand(root_id)


def wrapper_with(child: ChartItem, text: str = "fixture"):
    root = item("CLAUSE", 0, len(text), rule_id="wrapper", children=(child,))
    return graph(text, (root,))


class SubgraphPortTests(unittest.TestCase):
    def test_different_np_sizes_become_one_typed_port(self) -> None:
        left_np = item("NP", 0, 3, surface="cat")
        det = item("DET", 0, 3, surface="the")
        noun = item("N", 4, 7, surface="dog")
        right_np = item("NP", 0, 7, rule_id="np_det_n", children=(det, noun))
        left = wrapper_with(left_np, "cat")
        right = wrapper_with(right_np, "the dog")

        with self.assertRaises(AntiUnificationError):
            anti_unify(left, left.root_ids[0], right, right.root_ids[0])
        candidate = anti_unify_with_ports(
            left, left.root_ids[0], right, right.root_ids[0]
        )
        ports = [node for node in candidate.template.nodes if node.kind == "SUBGRAPH_PORT"]
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0].properties["accepts_category"], "NP")
        self.assertEqual(candidate.instantiate_left(), nested_root(left, left.root_ids[0]))
        self.assertEqual(candidate.instantiate_right(), nested_root(right, right.root_ids[0]))
        self.assertEqual(len(candidate.alignment.residual_left), 1)
        self.assertEqual(len(candidate.alignment.residual_right), 1)

    def test_port_matches_unseen_subgraph_size_but_respects_category(self) -> None:
        left_np = item("NP", 0, 3, surface="cat")
        right_np = item(
            "NP",
            0,
            7,
            rule_id="np_det_n",
            children=(item("DET", 0, 3, surface="the"), item("N", 4, 7, surface="dog")),
        )
        left = wrapper_with(left_np, "cat")
        right = wrapper_with(right_np, "the dog")
        candidate = anti_unify_with_ports(left, left.root_ids[0], right, right.root_ids[0])

        relative_np = item(
            "NP",
            0,
            12,
            rule_id="np_relative",
            children=(
                item("N", 0, 3, surface="dog"),
                item("CLAUSE", 4, 12, rule_id="relative_clause", children=()),
            ),
        )
        heldout = wrapper_with(relative_np, "dog that ran")
        self.assertIsNotNone(candidate.template.match(heldout, heldout.root_ids[0]))

        wrong = wrapper_with(item("VP", 0, 3, surface="ran"), "ran")
        self.assertIsNone(candidate.template.match(wrong, wrong.root_ids[0]))

    def test_port_does_not_hide_polarity_difference(self) -> None:
        left_vp = item(
            "VP", 0, 3, rule_id="vp_short", features={"negation": "false"}
        )
        right_vp = item(
            "VP", 0, 7, rule_id="vp_long", features={"negation": "true"}
        )
        left = wrapper_with(left_vp, "ran")
        right = wrapper_with(right_vp, "did not")
        with self.assertRaisesRegex(AntiUnificationError, "negation"):
            anti_unify_with_ports(left, left.root_ids[0], right, right.root_ids[0])

    def test_reentrant_port_requires_same_subgraph_identity(self) -> None:
        left_shared = item(
            "NP", 0, 3, rule_id="np_left", children=(item("N", 0, 3, surface="foo"),)
        )
        right_shared = item(
            "NP",
            0,
            7,
            rule_id="np_right",
            children=(item("DET", 0, 3, surface="the"), item("N", 4, 7, surface="bar")),
        )
        left_root = item("CLAUSE", 0, 3, rule_id="pair", children=(left_shared, left_shared))
        right_root = item("CLAUSE", 0, 7, rule_id="pair", children=(right_shared, right_shared))
        left = graph("foo", (left_root,))
        right = graph("the bar", (right_root,))
        candidate = anti_unify_with_ports(left, left.root_ids[0], right, right.root_ids[0])
        template_nodes = {node.node_id: node for node in candidate.template.nodes}
        port_edges = [
            edge for edge in candidate.template.edges
            if template_nodes[edge.target].kind == "SUBGRAPH_PORT"
        ]
        self.assertEqual(len({edge.target for edge in port_edges}), 1)

        first = item("NP", 0, 3, rule_id="np_a", children=(item("N", 0, 3, surface="one"),))
        second = item("NP", 4, 7, rule_id="np_b", children=(item("N", 4, 7, surface="two"),))
        mismatch_root = item("CLAUSE", 0, 7, rule_id="pair", children=(first, second))
        mismatch = graph("one two", (mismatch_root,))
        self.assertIsNone(candidate.template.match(mismatch, mismatch.root_ids[0]))

    def test_port_discards_variables_from_failed_exact_alignment(self) -> None:
        left_np = item(
            "NP",
            0,
            3,
            rule_id="np",
            features={"agreement": "singular", "payload": {"left": 1}},
        )
        right_np = item(
            "NP",
            0,
            7,
            rule_id="np",
            features={"agreement": "plural", "payload": {"right": 1}},
        )
        left = wrapper_with(left_np, "cat")
        right = wrapper_with(right_np, "the dogs")

        candidate = anti_unify_with_ports(left, left.root_ids[0], right, right.root_ids[0])
        subgraph_bindings = [
            binding for binding in candidate.bindings if binding.kind == "subgraph"
        ]
        self.assertEqual(len(subgraph_bindings), 1)
        self.assertEqual(
            {binding.name for binding in candidate.bindings},
            {
                str(node.properties["port"]["$var"])
                for node in candidate.template.nodes
                if node.kind == "SUBGRAPH_PORT"
            }
            | {
                str(value["$var"])
                for node in candidate.template.nodes
                for value in node.properties.values()
                if isinstance(value, dict) and set(value) == {"$var"}
            },
        )


class ReferencePortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        parser = Parser.from_dir(DATA)

        def story(first: str, second: str):
            processor = DiscourseProcessor(parser)
            processor.read(first)
            analysis = processor.read(second)
            return parse_to_observation(
                analysis.report.result,
                parser_version=__version__,
                mentions=analysis.mentions,
                reference_links=analysis.reference_links,
                mention_catalog=processor.state.mentions,
            )

        cls.left = story("John found a key.", "He kept it.")
        cls.right = story("Mary found a coin.", "She kept it.")
        cls.heldout = story("Robert found a map.", "He kept it.")
        cls.patterns = generalize_reference_candidates(cls.left, cls.right)

    def test_reference_alternatives_remain_open_candidates(self) -> None:
        self.assertGreater(len(self.patterns), 0)
        self.assertTrue(all(pattern.is_open_candidate for pattern in self.patterns))
        self.assertTrue(all(pattern.reference_kind == "MAYBE_REF" for pattern in self.patterns))

    def test_reference_patterns_reconstruct_observed_endpoints(self) -> None:
        def observed(graph_):
            nodes = {node.node_id: node for node in graph_.nodes}
            return {
                json.dumps(
                    {
                        "source_port": "REF_SOURCE",
                        "target_port": "REF_TARGET",
                        "kind": edge.properties["kind"],
                        "rule_id": edge.properties["rule_id"],
                        "source": nodes[edge.source].properties,
                        "target": nodes[edge.target].properties,
                    },
                    sort_keys=True,
                )
                for edge in graph_.edges
                if edge.role == "REFERENCE"
                and nodes[edge.source].kind == nodes[edge.target].kind == "MENTION"
            }

        left_rows = observed(self.left)
        right_rows = observed(self.right)
        for pattern in self.patterns:
            self.assertIn(json.dumps(pattern.instantiate("left"), sort_keys=True), left_rows)
            self.assertIn(json.dumps(pattern.instantiate("right"), sort_keys=True), right_rows)

    def test_reference_patterns_match_new_story_without_resolving_it(self) -> None:
        matches = sum(len(pattern.match_graph(self.heldout)) for pattern in self.patterns)
        self.assertGreater(matches, 0)
        target_kinds = {pattern.target_template["kind"] for pattern in self.patterns}
        self.assertTrue({"proper", "indefinite", "event"}.issubset(target_kinds))


if __name__ == "__main__":
    unittest.main()

