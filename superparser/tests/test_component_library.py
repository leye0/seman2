"""POC-03 tests for the lossless component library and MDL accounting."""

from __future__ import annotations

import json
import unittest

from research.induction import (
    ComponentLibrary,
    ComponentTemplate,
    ObservationExample,
    PatternEdge,
    PatternNode,
    canonicalize_template,
    parse_to_observation,
    value_description_bits,
)
from seman_parser.chart import ChartItem, PackedNode, ParseResult, Provenance
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import LexicalLattice, tokenize
from seman_parser.semantics import SemanticGraph, SemanticPackage


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


def graph_for_clause(
    subject: str,
    verb: str,
    object_: str,
    *,
    rule_id: str = "clause_np_vp",
    open_features: dict[str, object] | None = None,
):
    text = f"{subject} {verb} {object_}"
    verb_start = len(subject) + 1
    object_start = verb_start + len(verb) + 1
    subject_item = item("NP", 0, len(subject), surface=subject)
    verb_item = item("V", verb_start, verb_start + len(verb), surface=verb)
    object_item = item("NP", object_start, len(text), surface=object_)
    vp = item(
        "VP",
        verb_start,
        len(text),
        rule_id="vp_transitive",
        features={"voice": "active"},
        children=(verb_item, object_item),
    )
    root = item(
        "CLAUSE",
        0,
        len(text),
        rule_id=rule_id,
        features=open_features,
        children=(subject_item, vp),
    )
    items = (root, subject_item, vp, verb_item, object_item)
    packed = {
        (node.start, node.end, index): PackedNode(
            start=node.start,
            end=node.end,
            category=node.category,
            best=node,
            alternatives=[node],
        )
        for index, node in enumerate(items)
    }
    result = ParseResult(
        text=text,
        lattice=LexicalLattice(text=text, tokens=tokenize(text), candidates=()),
        packed=packed,
        roots=(root,),
        completed=True,
    )
    return parse_to_observation(result, parser_version="fixture")


def examples(
    count: int,
    *,
    verb: str = "sees",
    rule_id: str = "clause_np_vp",
    prefix: str = "train",
) -> list[ObservationExample]:
    rows = []
    for index in range(count):
        graph = graph_for_clause(
            f"person{index}", verb, f"thing{index}", rule_id=rule_id
        )
        rows.append(ObservationExample(f"{prefix}-{index}", graph, graph.root_ids[0]))
    return rows


class LogicalCodeTests(unittest.TestCase):
    def test_value_cost_is_independent_of_mapping_order(self) -> None:
        self.assertEqual(
            value_description_bits({"a": 1, "b": [2, 3]}),
            value_description_bits({"b": [2, 3], "a": 1}),
        )

    def test_template_canonicalization_ignores_node_and_variable_names(self) -> None:
        first = ComponentTemplate(
            "ignored-a",
            "root-a",
            (
                PatternNode("root-a", "CONSTITUENT", json.dumps({"x": {"$var": "X"}})),
                PatternNode("child-a", "CONSTITUENT", json.dumps({"constant": "n"})),
            ),
            (PatternEdge("root-a", "child-a", "CHILD", 0),),
        )
        second = ComponentTemplate(
            "ignored-b",
            "z9",
            (
                PatternNode("q7", "CONSTITUENT", json.dumps({"constant": "n"})),
                PatternNode("z9", "CONSTITUENT", json.dumps({"x": {"$var": "OTHER"}})),
            ),
            (PatternEdge("z9", "q7", "CHILD", 0),),
        )
        canonical_first, _ = canonicalize_template(first)
        canonical_second, _ = canonicalize_template(second)
        self.assertEqual(canonical_first, canonical_second)


class ComponentLibraryTests(unittest.TestCase):
    def test_recurrent_family_is_promoted_and_lossless(self) -> None:
        training = examples(40)
        library = ComponentLibrary(min_support=4)
        report = library.fit(training)
        self.assertGreater(report.component_count, 0)
        self.assertEqual(report.reconstruction_rate, 1.0)
        self.assertGreater(report.gain_vs_raw_bits, 0)
        self.assertEqual(report.b3_library_bits, report.library_model_bits + report.library_data_bits)
        self.assertTrue(all(library.decode(library.encode(row)) == row.snapshot for row in training))

    def test_frozen_roundtrip_library_reuses_component_on_heldout(self) -> None:
        library = ComponentLibrary(min_support=4)
        library.fit(examples(30))
        library.freeze()
        restored = ComponentLibrary.from_dict(
            json.loads(json.dumps(library.as_dict(), sort_keys=True))
        )
        heldout = examples(12, prefix="heldout")
        report = restored.evaluate_heldout(heldout)
        self.assertEqual(report["component_uses"], len(heldout))
        self.assertEqual(report["reconstruction_rate"], 1.0)
        self.assertGreater(report["gain_bits"], 0)
        with self.assertRaisesRegex(RuntimeError, "frozen"):
            restored.fit(heldout)

    def test_unique_structures_are_not_promoted(self) -> None:
        corpus = [
            examples(1, rule_id=f"unique-{index}", prefix=f"unique-{index}")[0]
            for index in range(20)
        ]
        library = ComponentLibrary(min_support=4)
        report = library.fit(corpus)
        self.assertEqual(report.component_count, 0)
        self.assertLessEqual(report.b0_raw_bits, report.b3_library_bits)

    def test_variables_everywhere_are_not_promoted(self) -> None:
        corpus = []
        for index in range(12):
            features = {f"open-{slot}": f"{index}-{slot}" for slot in range(40)}
            graph = graph_for_clause(
                f"s{index}", f"v{index}", f"o{index}", open_features=features
            )
            corpus.append(ObservationExample(f"wide-{index}", graph, graph.root_ids[0]))
        library = ComponentLibrary(min_support=4)
        library.fit(corpus)
        self.assertEqual(len(library.active_components), 0)

    def test_two_families_can_beat_a_single_flat_component(self) -> None:
        corpus = examples(30, verb="sees", rule_id="family-a", prefix="a")
        corpus += examples(30, verb="opens", rule_id="family-b", prefix="b")
        library = ComponentLibrary(min_support=4)
        report = library.fit(corpus)
        self.assertEqual(report.component_count, 2)
        self.assertLess(report.b3_library_bits, report.b2_single_component_bits)
        self.assertLess(report.b3_library_bits, report.b1_exact_dictionary_bits)

    def test_retired_component_is_not_used(self) -> None:
        corpus = examples(20)
        library = ComponentLibrary(min_support=4)
        library.fit(corpus)
        component_id = library.active_components[0].template.component_id
        library.retire(component_id)
        encoded = library.encode(corpus[0])
        self.assertEqual(encoded.mode, "raw")

    def test_duplicate_observation_ids_are_rejected(self) -> None:
        corpus = examples(2)
        duplicate = [corpus[0], ObservationExample(corpus[0].observation_id, corpus[1].graph, corpus[1].root_id)]
        with self.assertRaisesRegex(ValueError, "unique"):
            ComponentLibrary().fit(duplicate)


if __name__ == "__main__":
    unittest.main()
