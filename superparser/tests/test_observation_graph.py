"""POC-00 tests for the allow-listed observation graph."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest

from research.induction.observation_graph import (
    FORBIDDEN_PROPERTY_KEYS,
    ObservationGraph,
    ObservationGraphError,
    parse_to_observation,
    structural_snapshot_from_parse,
)
from seman_parser import Parser, __version__
from seman_parser.chart import ChartItem, PackedNode, ParseResult, Provenance
from seman_parser.discourse import Mention
from seman_parser.features import FeatureStructure
from seman_parser.reference import ReferenceKind, ReferenceLink
from seman_parser.segmentation import LexicalLattice, tokenize
from seman_parser.semantics import SemanticGraph, SemanticPackage


DATA = Path(__file__).resolve().parents[1] / "data"
FIXTURE_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "induction"
    / "poc"
    / "POC-00-observation-graph"
    / "fixtures"
    / "manifest.json"
)


def structural_item(
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
    source = "rule" if rule_id else "fixture"
    if surface is not None:
        detail.update({"surface": surface, "lemma": surface.lower()})
    return ChartItem(
        start=start,
        end=end,
        category=category,
        features=FeatureStructure.build(features or {}),
        semantic=SemanticPackage(SemanticGraph()),
        score=1.0,
        provenance=Provenance(source=source, detail=detail),
        children=children,
        rule_id=rule_id,
    )


def synthetic_result(text: str, roots: tuple[ChartItem, ...]) -> ParseResult:
    all_items: list[ChartItem] = []

    def collect(item: ChartItem) -> None:
        all_items.append(item)
        for child in item.children:
            collect(child)

    for root in roots:
        collect(root)
    packed: dict[tuple[int, int, int], PackedNode] = {}
    # The adapter reads alternatives, not the integer symbol component of the
    # runtime key.  A fixture-local counter keeps groups distinct.
    for counter, item in enumerate(all_items):
        packed[(item.start, item.end, counter)] = PackedNode(
            start=item.start,
            end=item.end,
            category=item.category,
            best=item,
            alternatives=[item],
        )
    return ParseResult(
        text=text,
        lattice=LexicalLattice(text=text, tokens=tokenize(text), candidates=()),
        packed=packed,
        roots=roots,
        completed=bool(roots),
    )


class ObservationGraphIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = Parser.from_dir(DATA)
        cls.result = cls.parser.parse("John opened the box.").result
        cls.graph = parse_to_observation(cls.result, parser_version=__version__)

    def test_graph_validates_and_is_json_roundtrippable(self) -> None:
        self.graph.validate()
        restored = ObservationGraph.from_json(self.graph.canonical_json())
        self.assertEqual(restored, self.graph)
        self.assertEqual(restored.canonical_json(), self.graph.canonical_json())

    def test_structural_snapshot_preserves_only_selected_analysis(self) -> None:
        snapshot = self.graph.structural_snapshot()
        self.assertEqual(snapshot, structural_snapshot_from_parse(self.result))
        self.assertEqual(snapshot["text"], self.result.text)
        self.assertEqual(snapshot["completed"], self.result.completed)
        self.assertEqual(len(snapshot["tokens"]), len(self.result.lattice.tokens))
        self.assertEqual(snapshot["lexical_candidates"], [])
        self.assertEqual(snapshot["forest_analyses"], [])
        self.assertEqual(len(snapshot["root_analyses"]), 1)
        self.assertEqual({root["category"] for root in snapshot["root_analyses"]}, {"CLAUSE"})
        self.assertTrue(all("children" in root for root in snapshot["root_analyses"]))
        self.assertEqual(self.graph.forest_ids, ())
        self.assertEqual(self.graph.selection_policy, "parser_best")
        self.assertFalse(self.graph.selection_provisional)
        self.assertFalse(any(node.kind == "LEXICAL_CANDIDATE" for node in self.graph.nodes))

    def test_semantic_and_wordnet_fields_are_absent(self) -> None:
        payload = json.loads(self.graph.canonical_json())

        def keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value).union(*(keys(child) for child in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(child) for child in value))
            return set()

        self.assertFalse(keys(payload) & FORBIDDEN_PROPERTY_KEYS)
        serialized = self.graph.canonical_json().upper()
        for imported_label in ("AGENT", "AFFECTED", "ARTIFACT", "LOCATED-ON"):
            self.assertNotIn(imported_label, serialized)

    def test_runtime_semantic_ids_do_not_affect_canonical_output(self) -> None:
        repeated = self.parser.parse("John opened the box.").result
        repeated_graph = parse_to_observation(repeated, parser_version=__version__)
        self.assertEqual(repeated_graph.canonical_json(), self.graph.canonical_json())

    def test_reordering_parser_roots_does_not_change_canonical_output(self) -> None:
        reordered = replace(self.result, roots=tuple(reversed(self.result.roots)))
        graph = parse_to_observation(reordered, parser_version=__version__)
        self.assertEqual(graph.canonical_json(), self.graph.canonical_json())

    def test_ordered_child_edges_are_contiguous(self) -> None:
        grouped: dict[str, list[int]] = {}
        for edge in self.graph.edges:
            if edge.role == "CHILD":
                assert edge.position is not None
                grouped.setdefault(edge.source, []).append(edge.position)
        for positions in grouped.values():
            self.assertEqual(sorted(positions), list(range(len(positions))))

    def test_tampering_is_detected(self) -> None:
        row = self.graph.as_dict()
        row["text"] = "tampered"
        with self.assertRaises(ObservationGraphError):
            ObservationGraph.from_dict(row)

    def test_reference_candidates_preserve_structure_not_semantic_types(self) -> None:
        antecedent = Mention(
            mention_id="arbitrary-runtime-A",
            surface="John",
            span=(0, 4),
            kind="proper",
            sentence_index=0,
            features=FeatureStructure.build({"number": "singular"}),
            semantic_type="PERSON",
            node_id="e-secret-1",
            head_lemma="John",
            score=99.0,
        )
        anaphor = Mention(
            mention_id="arbitrary-runtime-B",
            surface="the box",
            span=(12, 19),
            kind="definite",
            sentence_index=1,
            features=FeatureStructure.build({"number": "singular"}),
            semantic_type="CONTAINER",
            node_id="e-secret-2",
            head_lemma="box",
            score=42.0,
        )
        link = ReferenceLink(
            source=anaphor.mention_id,
            target=antecedent.mention_id,
            kind=ReferenceKind.MAYBE_REF,
            rule_id="REF-06:test",
            evidence={"semantic_type": "SHOULD_NOT_LEAK"},
        )
        graph = parse_to_observation(
            self.result,
            parser_version=__version__,
            mentions=(anaphor,),
            reference_links=(link,),
            mention_catalog={antecedent.mention_id: antecedent},
        )
        mentions = [node for node in graph.nodes if node.kind == "MENTION"]
        refs = [edge for edge in graph.edges if edge.role == "REFERENCE"]
        self.assertEqual(len(mentions), 2)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].properties["kind"], "MAYBE_REF")
        serialized = graph.canonical_json()
        for forbidden in ("PERSON", "CONTAINER", "SHOULD_NOT_LEAK", "e-secret"):
            self.assertNotIn(forbidden, serialized)

    def test_runtime_mention_renaming_does_not_change_graph(self) -> None:
        def make_graph(prefix: str) -> ObservationGraph:
            first = Mention(
                mention_id=f"{prefix}-1",
                surface="John",
                span=(0, 4),
                kind="proper",
                sentence_index=0,
                features=FeatureStructure.build({"number": "singular"}),
                head_lemma="John",
            )
            second = Mention(
                mention_id=f"{prefix}-2",
                surface="the box",
                span=(12, 19),
                kind="definite",
                sentence_index=0,
                features=FeatureStructure.build({"number": "singular"}),
                head_lemma="box",
            )
            link = ReferenceLink(
                source=second.mention_id,
                target=first.mention_id,
                kind=ReferenceKind.MAYBE_REF,
                rule_id="REF-06:test",
            )
            return parse_to_observation(
                self.result,
                parser_version=__version__,
                mentions=(first, second),
                reference_links=(link,),
            )

        self.assertEqual(make_graph("M").canonical_json(), make_graph("renamed").canonical_json())


class ObservationGraphContrastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = Parser.from_dir(DATA)

    def test_negation_produces_a_distinct_observation(self) -> None:
        positive = parse_to_observation(
            self.parser.parse("John opened the box.").result,
            parser_version=__version__,
        )
        negative = parse_to_observation(
            self.parser.parse("John did not open the box.").result,
            parser_version=__version__,
        )
        self.assertNotEqual(positive.observation_id, negative.observation_id)
        negative_features = [
            node.properties.get("features", {})
            for node in negative.nodes
            if node.kind in {"LEXICAL_CANDIDATE", "CONSTITUENT"}
        ]
        self.assertTrue(any(features.get("negation") == "true" for features in negative_features))

    def test_failed_parse_is_still_an_observation(self) -> None:
        result = self.parser.parse("the the the the.").result
        graph = parse_to_observation(result, parser_version=__version__)
        self.assertFalse(graph.completed)
        self.assertEqual(len(graph.root_ids), 1)
        self.assertEqual(graph.selection_policy, "structural_fallback")
        self.assertTrue(graph.selection_provisional)
        self.assertEqual(graph.forest_ids, ())
        self.assertGreater(len([node for node in graph.nodes if node.kind == "TOKEN"]), 0)
        graph.validate()


class ObservationGraphStructuralFixtureTests(unittest.TestCase):
    def test_nested_semantic_features_are_removed_recursively(self) -> None:
        leaf = structural_item(
            "PREP",
            0,
            2,
            surface="of",
            features={
                "semantic_type": "POSSESSOR",
                "gap": {"semantic_type": "ENTITY", "case": "accusative"},
            },
        )
        root = structural_item("CLAUSE", 0, 2, rule_id="fixture", children=(leaf,))
        graph = parse_to_observation(synthetic_result("of", (root,)))
        payload = graph.canonical_json()
        self.assertNotIn("semantic_type", payload)
        self.assertNotIn("POSSESSOR", payload)
        prep = next(
            node for node in graph.nodes
            if node.kind == "CONSTITUENT" and node.properties["category"] == "PREP"
        )
        self.assertEqual(prep.properties["features"], {"gap": {"case": "accusative"}})

    def test_scope_modality_embedding_and_coordination_survive_projection(self) -> None:
        john = structural_item("NP", 0, 4, surface="John")
        leave = structural_item("V", 11, 16, features={"vform": "base"}, surface="leave")
        modal_vp = structural_item(
            "VP",
            5,
            16,
            rule_id="vp_modal",
            features={"modal": "true", "negation": "true"},
            children=(leave,),
        )
        embedded = structural_item(
            "CLAUSE",
            0,
            16,
            rule_id="clause_np_vp",
            features={"scope": "embedded"},
            children=(john, modal_vp),
        )
        mary = structural_item("NP", 21, 25, surface="Mary")
        coordination = structural_item(
            "CLAUSE",
            0,
            25,
            rule_id="clause_coordination",
            features={"coordination": "true"},
            children=(embedded, mary),
        )
        graph = parse_to_observation(synthetic_result("John might leave and Mary", (coordination,)))
        root = graph.structural_snapshot()["root_analyses"][0]
        self.assertEqual(root["rule_id"], "clause_coordination")
        self.assertEqual(root["children"][0]["features"]["scope"], "embedded")
        vp = root["children"][0]["children"][1]
        self.assertEqual(vp["features"]["modal"], "true")
        self.assertEqual(vp["features"]["negation"], "true")
        self.assertEqual([child["surface"] for child in root["children"] if "surface" in child], ["Mary"])

    def test_existing_parser_selection_yields_one_ambiguity_reading(self) -> None:
        word = structural_item("N", 0, 4, surface="duck")
        nominal = structural_item("CLAUSE", 0, 4, rule_id="nominal_reading", children=(word,))
        verbal = structural_item("CLAUSE", 0, 4, rule_id="verbal_reading", children=(word,))
        graph = parse_to_observation(synthetic_result("duck", (nominal, verbal)))
        roots = graph.structural_snapshot()["root_analyses"]
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0]["rule_id"], "nominal_reading")
        self.assertFalse(graph.selection_provisional)

    def test_fixture_manifest_has_required_phenomena_and_unique_ids(self) -> None:
        manifest = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
        cases = manifest["cases"]
        ids = [case["id"] for case in cases]
        phenomena = {phenomenon for case in cases for phenomenon in case["phenomena"]}
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(
            {
                "negation",
                "modality",
                "interrogation",
                "embedding",
                "coordination",
                "ambiguity",
                "anaphora",
            }.issubset(phenomena)
        )


if __name__ == "__main__":
    unittest.main()

