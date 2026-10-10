"""POC-01 tests for constrained graph anti-unification."""

from __future__ import annotations

from pathlib import Path
import unittest

from research.induction import (
    AntiUnificationError,
    anti_unify,
    parse_to_observation,
    propose_root_generalizations,
)
from seman_parser import Parser, __version__
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


def graph_for_roots(text: str, roots: tuple[ChartItem, ...]):
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


def graph_for_clause(
    subject: str,
    verb: str,
    object_: str,
    *,
    root_rule: str | tuple[str, ...] = "clause_np_vp",
    negation: str = "false",
):
    text = f"{subject} {verb} {object_}"
    subject_start = 0
    verb_start = len(subject) + 1
    object_start = verb_start + len(verb) + 1
    subject_item = item("NP", subject_start, len(subject), surface=subject)
    verb_item = item("V", verb_start, verb_start + len(verb), surface=verb)
    object_item = item("NP", object_start, len(text), surface=object_)
    vp = item(
        "VP",
        verb_start,
        len(text),
        rule_id="vp_transitive",
        features={"voice": "active", "negation": negation},
        children=(verb_item, object_item),
    )
    root_rules = (root_rule,) if isinstance(root_rule, str) else root_rule
    roots = tuple(
        item(
            "CLAUSE",
            0,
            len(text),
            rule_id=rule,
            features={"negation": negation},
            children=(subject_item, vp),
        )
        for rule in root_rules
    )
    return graph_for_roots(text, roots)


def only_root(graph) -> tuple[str, dict]:
    assert len(graph.root_ids) == 1
    return graph.root_ids[0], graph.structural_snapshot()["root_analyses"][0]


def snapshot_for_root(graph, root_id: str) -> dict:
    nodes = {node.node_id: node for node in graph.nodes}
    children: dict[str, list] = {}
    for edge in graph.edges:
        if edge.role == "CHILD":
            children.setdefault(edge.source, []).append(edge)

    def expand(node_id: str) -> dict:
        row = nodes[node_id].properties
        ordered = sorted(children.get(node_id, ()), key=lambda edge: edge.position)
        row["children"] = [expand(edge.target) for edge in ordered]
        return row

    return expand(root_id)


class AntiUnificationUnitTests(unittest.TestCase):
    def test_generalization_reconstructs_both_observations(self) -> None:
        left = graph_for_clause("john", "sees", "apple")
        right = graph_for_clause("mary", "sees", "book")
        left_id, left_snapshot = only_root(left)
        right_id, right_snapshot = only_root(right)
        candidate = anti_unify(left, left_id, right, right_id)
        self.assertEqual(candidate.instantiate_left(), left_snapshot)
        self.assertEqual(candidate.instantiate_right(), right_snapshot)
        self.assertGreater(candidate.evaluation.variable_count, 0)
        self.assertFalse(candidate.evaluation.trivial)
        self.assertEqual(candidate.alignment.residual_left, ())
        self.assertEqual(candidate.alignment.residual_right, ())

    def test_repeated_values_share_one_variable_and_constrain_matching(self) -> None:
        left = graph_for_clause("foo", "sees", "foo")
        right = graph_for_clause("bar", "sees", "bar")
        candidate = anti_unify(left, left.root_ids[0], right, right.root_ids[0])
        lexical = [binding for binding in candidate.bindings if binding.kind == "lexical"]
        foo_bar = [binding for binding in lexical if binding.left == "foo" and binding.right == "bar"]
        self.assertEqual(len(foo_bar), 1)

        matching = graph_for_clause("cat", "sees", "cat")
        mismatch = graph_for_clause("cat", "sees", "dog")
        self.assertIsNotNone(candidate.template.match(matching, matching.root_ids[0]))
        self.assertIsNone(candidate.template.match(mismatch, mismatch.root_ids[0]))

    def test_distinct_pairs_remain_distinct_variables(self) -> None:
        left = graph_for_clause("foo", "sees", "apple")
        right = graph_for_clause("bar", "sees", "book")
        candidate = anti_unify(left, left.root_ids[0], right, right.root_ids[0])
        lexical_pairs = {(binding.left, binding.right) for binding in candidate.bindings if binding.kind == "lexical"}
        self.assertIn(("foo", "bar"), lexical_pairs)
        self.assertIn(("apple", "book"), lexical_pairs)
        novel = graph_for_clause("alexander", "sees", "encyclopedia")
        self.assertIsNotNone(candidate.template.match(novel, novel.root_ids[0]))
        same_value = graph_for_clause("cat", "sees", "cat")
        self.assertIsNotNone(candidate.template.match(same_value, same_value.root_ids[0]))

    def test_graph_reentrance_is_preserved(self) -> None:
        left_shared = item("NP", 0, 3, surface="foo")
        left_root = item(
            "CLAUSE", 0, 3, rule_id="shared_pair", children=(left_shared, left_shared)
        )
        right_shared = item("NP", 0, 3, surface="bar")
        right_root = item(
            "CLAUSE", 0, 3, rule_id="shared_pair", children=(right_shared, right_shared)
        )
        left = graph_for_roots("foo", (left_root,))
        right = graph_for_roots("bar", (right_root,))
        candidate = anti_unify(left, left.root_ids[0], right, right.root_ids[0])
        root_edges = [
            edge for edge in candidate.template.edges
            if edge.source == candidate.template.root_id
        ]
        self.assertEqual(len({edge.target for edge in root_edges}), 1)

        first = item("NP", 0, 3, surface="cat")
        second = item("NP", 4, 7, surface="cat")
        mismatch_root = item(
            "CLAUSE", 0, 7, rule_id="shared_pair", children=(first, second)
        )
        mismatch = graph_for_roots("cat cat", (mismatch_root,))
        self.assertIsNone(candidate.template.match(mismatch, mismatch.root_ids[0]))

    def test_polarity_difference_is_rejected(self) -> None:
        positive = graph_for_clause("john", "sees", "apple", negation="false")
        negative = graph_for_clause("john", "sees", "apple", negation="true")
        with self.assertRaisesRegex(AntiUnificationError, "negation"):
            anti_unify(positive, positive.root_ids[0], negative, negative.root_ids[0])

    def test_rule_difference_is_rejected(self) -> None:
        left = graph_for_clause("john", "sees", "apple", root_rule="clause_np_vp")
        right = graph_for_clause("mary", "sees", "book", root_rule="clause_inversion")
        with self.assertRaisesRegex(AntiUnificationError, "rule_id"):
            anti_unify(left, left.root_ids[0], right, right.root_ids[0])

    def test_candidate_serialization_contains_costs_and_provenance(self) -> None:
        left = graph_for_clause("john", "sees", "apple")
        right = graph_for_clause("mary", "sees", "book")
        candidate = anti_unify(left, left.root_ids[0], right, right.root_ids[0])
        payload = candidate.as_dict()
        self.assertTrue(payload["template"]["component_id"].startswith("component_"))
        self.assertEqual(len(payload["alignment"]["node_mapping"]), 5)
        self.assertIn("estimated_gain_bytes", payload["evaluation"])

    def test_variables_everywhere_candidate_is_flagged_trivial(self) -> None:
        left_features = {f"open_feature_{index}": f"left-{index}" for index in range(20)}
        right_features = {f"open_feature_{index}": f"right-{index}" for index in range(20)}
        left_root = item("N", 0, 1, features=left_features, surface="a")
        right_root = item("N", 0, 1, features=right_features, surface="b")
        left = graph_for_roots("a", (left_root,))
        right = graph_for_roots("b", (right_root,))
        candidate = anti_unify(left, left.root_ids[0], right, right.root_ids[0])
        self.assertTrue(candidate.evaluation.trivial)

    def test_root_proposal_uses_only_the_selected_analysis(self) -> None:
        rules = ("clause_np_vp", "clause_alt")
        left = graph_for_clause("foo", "sees", "apple", root_rule=rules)
        right = graph_for_clause("bar", "sees", "book", root_rule=rules)
        candidates = propose_root_generalizations(left, right)
        root_rules = {
            next(
                node for node in candidate.template.nodes
                if node.node_id == candidate.template.root_id
            ).properties["rule_id"]
            for candidate in candidates
        }
        self.assertEqual(len(left.root_ids), 1)
        self.assertEqual(len(right.root_ids), 1)
        self.assertEqual(root_rules, {"clause_np_vp"})


if __name__ == "__main__":
    unittest.main()

