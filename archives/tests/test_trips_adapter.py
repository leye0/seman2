from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from seman2.evidence.store import EvidenceStore
from seman2.interpretation.trips_adapter import (
    TripsAdapter,
    TripsProtocolError,
    TripsResponse,
)


FIXTURE = Path(__file__).parent / "fixtures" / "trips_alternatives.xml"


class FixtureTransport:
    endpoint = "fixture://trips"

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, str]]] = []

    def parse(self, input_text: str, parameters: dict[str, str]) -> TripsResponse:
        self.calls.append((input_text, dict(parameters)))
        return TripsResponse(
            body=self.payload,
            content_type="application/xml",
            status=200,
            endpoint=self.endpoint,
            headers={"X-Fixture": "true"},
        )


class TripsAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.store = EvidenceStore(Path(self.temporary.name) / "evidence.sqlite")
        self.transport = FixtureTransport(FIXTURE.read_bytes())
        self.adapter = TripsAdapter(self.transport, number_parses_desired=3)

    def tearDown(self) -> None:
        self.store.close()
        self.temporary.cleanup()

    def test_raw_response_alternatives_and_dual_projection_are_preserved(self) -> None:
        evidence = self.store.append("A dax moves.", stream_id="fixture")
        bundle = self.adapter.interpret(evidence, request_id="request-1")

        self.assertEqual(bundle.raw_payload, FIXTURE.read_bytes())
        self.assertEqual(bundle.analyzer_version, "fixture-v1")
        self.assertEqual(len(bundle.segments), 1)
        self.assertEqual(len(bundle.hypotheses), 2)
        primary, alternative = bundle.hypotheses
        self.assertEqual((primary.score, alternative.score), (0.61, 0.39))
        self.assertGreater(len(primary.semantic.nodes), 0)
        self.assertGreater(len(primary.structural.nodes), 0)
        self.assertGreater(len(primary.cross_links), 0)
        self.assertTrue(alternative.parser_attributes["tags_inherited_from_primary"])
        self.assertTrue(
            all(
                node.span.evidence_id == evidence.evidence_id
                for node in primary.semantic.nodes
                if node.span is not None
            )
        )

    def test_context_is_submitted_without_mutating_any_evidence(self) -> None:
        previous = self.store.append("Earlier text.", stream_id="fixture")
        current = self.store.append("A dax moves.", stream_id="fixture")
        bundle = self.adapter.interpret(current, (previous,), request_id="request-2")

        # Context is preserved as provenance, not concatenated into the chart
        # input: multi-unit inputs make TRIPS explode into compound parses.
        self.assertEqual(self.transport.calls[-1][0], "A dax moves.")
        self.assertEqual(bundle.context_evidence_ids, (previous.evidence_id,))
        self.assertEqual(bundle.input_spans[0].evidence_id, current.evidence_id)
        self.assertEqual(self.store.get(previous.evidence_id).raw, "Earlier text.")

    def test_failed_parse_is_a_retained_segment_not_an_exception(self) -> None:
        payload = b'<trips-parser-output parser-build-date="x"><failed-to-parse /></trips-parser-output>'
        adapter = TripsAdapter(FixtureTransport(payload))
        evidence = self.store.append("???", stream_id="failure")
        bundle = adapter.interpret(evidence)
        self.assertEqual(bundle.segments[0].status, "failed-to-parse")
        self.assertEqual(bundle.hypotheses, ())

    def test_non_xml_response_is_rejected_before_projection(self) -> None:
        adapter = TripsAdapter(FixtureTransport(b"not xml"))
        evidence = self.store.append("text", stream_id="failure")
        with self.assertRaises(TripsProtocolError):
            adapter.interpret(evidence)


if __name__ == "__main__":
    unittest.main()

