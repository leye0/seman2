from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from seman2.evidence.store import EvidenceStore
from seman2.interpretation.kqml import LocalTripsTransport, parse_kqml
from seman2.interpretation.trips_adapter import TripsAdapter, TripsResponse


KQML_FIXTURE = b"""(TELL :CONTENT (NEW-SPEECH-ACT (UTT
  :ROOT ONT::V1
  :RELIABILITY 91
  :TERMS (
    (TERM :LF (ONT::F ONT::V1 ONT::MOVE :AGENT ONT::V2)
          :VAR ONT::V1 :INPUT (W::DOG W::RUNS) :START 0 :END 8)
    (TERM :LF (ONT::THE ONT::V2 ONT::ANIMAL)
          :VAR ONT::V2 :INPUT (W::DOG) :START 0 :END 3))
  :WORDS (W::DOG W::RUNS W::PUNC-PERIOD)
  :TREE ((W::S :SUB ((W::N) (W::V) (W::PUNC))))
  :UTTNUM 1)) :sender PARSER)"""


class KqmlFixtureTransport:
    endpoint = "kqml://127.0.0.1:6200"

    def parse(self, input_text: str, parameters: dict[str, str]) -> TripsResponse:
        return TripsResponse(
            body=KQML_FIXTURE,
            content_type="application/kqml; charset=utf-8",
            status=0,
            endpoint=self.endpoint,
            headers={"transport": "KQML/TCP"},
        )


class LocalTripsTests(unittest.TestCase):
    def test_transport_rejects_every_non_loopback_address(self) -> None:
        with self.assertRaises(ValueError):
            LocalTripsTransport("8.8.8.8")
        self.assertEqual(LocalTripsTransport().endpoint, "kqml://127.0.0.1:6200")

    def test_native_kqml_is_retained_and_projected_twice(self) -> None:
        with TemporaryDirectory() as directory:
            store = EvidenceStore(Path(directory) / "evidence.sqlite")
            evidence = store.append("Dog runs.", stream_id="fixture")
            bundle = TripsAdapter(KqmlFixtureTransport()).interpret(evidence)
            store.close()

        self.assertEqual(bundle.raw_payload, KQML_FIXTURE)
        self.assertEqual(bundle.raw_content_type, "application/kqml; charset=utf-8")
        self.assertEqual(len(bundle.hypotheses), 1)
        hypothesis = bundle.hypotheses[0]
        self.assertEqual(len(hypothesis.semantic.nodes), 2)
        self.assertGreaterEqual(len(hypothesis.structural.nodes), 4)
        self.assertGreater(len(hypothesis.cross_links), 0)
        self.assertEqual(hypothesis.semantic.nodes[0].span.evidence_id, evidence.evidence_id)
        self.assertEqual(parse_kqml(KQML_FIXTURE)[0], "TELL")


if __name__ == "__main__":
    unittest.main()
