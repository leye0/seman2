from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from seman2.evidence.store import EvidenceStore
from seman2.learning.engine import CoupledLearningRuntime
from seman2.learning.fragments import (
    instantiate,
    linearize,
    match_fragment,
    parse_bracketed,
)
from seman2.learning.retro import match_fragment_on_tree
from seman2.interpretation.trips_adapter import TripsAdapter, TripsResponse
from seman2.runtime.engine import Seman2Runtime


FIXTURE = Path(__file__).parent / "fixtures" / "trips_alternatives.xml"


class FixtureTransport:
    endpoint = "fixture://trips"

    def parse(self, input_text: str, parameters: dict[str, str]) -> TripsResponse:
        return TripsResponse(
            body=FIXTURE.read_bytes(),
            content_type="application/xml",
            status=200,
            endpoint=self.endpoint,
            headers={},
        )


class RetroMatchTests(unittest.TestCase):
    def test_complex_segment_is_found_in_host_tree(self) -> None:
        sentence = ("the", "dog", "ran", "to", "the", "park")
        tree = (
            "(S (NP (DT 0) (NN 1)) (VP (VBD 2) (PP (IN 3) (NP (DT 4) (NN 5)))))"
        )
        fragment = "(S (NP (DT the) (NN )) (VP (VBD ran) (PP (IN to) (NP ))))"
        matches = match_fragment_on_tree(fragment, tree, sentence)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].bindings["0.0.1"], "(NN dog)")
        self.assertEqual(matches[0].bindings["0.1.1.1"], "(NP (DT the) (NN park))")

    def test_instantiation_produces_novel_surface_without_templates(self) -> None:
        fragment = parse_bracketed(
            "(S (NP (DT the) (NN )) (VP (VBD ran) (PP (IN to) (NP ))))"
        )
        filled = instantiate(
            fragment,
            {
                "0.0.1": "(NN cat)",
                "0.1.1.1": parse_bracketed("(NP (DT a) (NN store))"),
            },
        )
        self.assertEqual(linearize(filled), "the cat ran to a store")


class RetroLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.database = Path(self.temporary.name) / "retro.sqlite"
        self.store = EvidenceStore(self.database)
        self.learner = CoupledLearningRuntime.open(self.database)
        self.runtime = Seman2Runtime(
            self.store,
            TripsAdapter(FixtureTransport(), number_parses_desired=3),
            context_window=2,
            learner=self.learner,
        )

    def tearDown(self) -> None:
        self.runtime.close()
        self.temporary.cleanup()

    def test_fragments_are_sent_back_into_stored_analyses(self) -> None:
        for index in range(3):
            self.runtime.ingest(
                "A dax moves.",
                stream_id="retro",
                sequence=index,
            )
            self.runtime.process_next()

        consolidated = self.runtime.consolidate(minimum_support=2, use_discodop=True)
        self.assertGreaterEqual(consolidated["dop_fragments"], 1)

        report = self.runtime.retro()
        self.assertGreaterEqual(report["fragments"], 1)
        self.assertGreaterEqual(report["trees"], 1)
        self.assertGreaterEqual(report["matches"], 1)

        matches = self.learner.store.structures(family="fragment-match")
        self.assertGreaterEqual(len(matches), 1)
        first = matches[0]
        self.assertIn("bindings", first.payload)
        self.assertIn("fragment", first.payload)
        self.assertTrue(first.payload["tree_structure_id"].startswith("structure_"))

        # Every match is traceable back to the complex segment and the tree.
        trace = self.learner.store.trace(first.structure_id)
        relations = {row["relation"] for row in trace["incoming"]}
        self.assertIn("instantiated-by", relations)
        self.assertIn("exhibits", relations)

    def test_reprocess_reruns_the_retro_loop(self) -> None:
        self.runtime.ingest("A dax moves.", stream_id="retro")
        self.runtime.process_next()
        self.runtime.consolidate(minimum_support=2, use_discodop=True)

        report = self.runtime.reprocess()
        self.assertIn("retro", report)
        self.assertGreaterEqual(report["retro"]["matches"], 1)

    def test_learning_failures_do_not_corrupt_analyses(self) -> None:
        unit = self.runtime.ingest("A dax moves.", stream_id="retro")
        bundle = self.runtime.process_next()
        assert bundle is not None
        self.assertEqual(self.store.get(unit.evidence_id).raw, "A dax moves.")
        self.assertEqual(len(bundle.hypotheses), 2)

    def test_generation_instantiates_learned_complex_segments(self) -> None:
        for index in range(3):
            self.runtime.ingest("A dax moves.", stream_id="retro", sequence=index)
            self.runtime.process_next()
        self.runtime.consolidate(minimum_support=2, use_discodop=True)
        self.runtime.retro()

        candidates = self.runtime.generate(
            {"family": "target"},
            limit=20,
            modes=("instantiate",),
        )
        self.assertGreaterEqual(len(candidates), 1)
        instantiated = [row for row in candidates if row.mode == "instantiate"]
        self.assertGreaterEqual(len(instantiated), 1)
        # Surfaces come from fragment slots filled with observed material only.
        for row in instantiated:
            self.assertTrue(row.surface)
            self.assertIn("fragment", row.structure)


if __name__ == "__main__":
    unittest.main()
