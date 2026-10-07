from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from seman2.evidence.store import EvidenceStore
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


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.store = EvidenceStore(Path(self.temporary.name) / "runtime.sqlite")
        self.runtime = Seman2Runtime(
            self.store,
            TripsAdapter(FixtureTransport(), number_parses_desired=3),
            context_window=2,
        )

    def tearDown(self) -> None:
        self.runtime.close()
        self.temporary.cleanup()

    def test_ingest_process_persist_trace_revise_and_replay(self) -> None:
        first = self.runtime.ingest("A dax moves.", stream_id="dialogue")
        first_bundle = self.runtime.process_next()
        self.assertIsNotNone(first_bundle)
        assert first_bundle is not None
        loaded = self.store.load_analysis(first_bundle.analysis_id)
        self.assertEqual(loaded.raw_payload, first_bundle.raw_payload)
        self.assertEqual(len(loaded.hypotheses), 2)

        later = self.runtime.ingest("More context.", stream_id="dialogue")
        self.runtime.process_next()
        hypothesis = first_bundle.hypotheses[0]
        revision_id = self.runtime.revise(
            hypothesis.hypothesis_id,
            evidence_id=later.evidence_id,
            score=0.82,
            derivation={"algorithm": "fixture-reranker", "version": "1"},
        )
        history = self.store.hypothesis_history(hypothesis.hypothesis_id)
        self.assertTrue(revision_id.startswith("rev_"))
        self.assertEqual([row["score"] for row in history], [0.61, 0.82])
        self.assertEqual(self.store.get(first.evidence_id).raw, "A dax moves.")

        self.runtime.replay(first.evidence_id)
        replay = self.runtime.process_next()
        self.assertIsNotNone(replay)
        assert replay is not None
        self.assertNotEqual(first_bundle.analysis_id, replay.analysis_id)
        self.assertEqual(len(self.store.analyses_for(first.evidence_id)), 2)

        trace = self.runtime.trace(first.evidence_id)
        self.assertEqual(len(trace["analyses"]), 2)
        self.assertEqual(trace["jobs"][0]["status"], "complete")


if __name__ == "__main__":
    unittest.main()

