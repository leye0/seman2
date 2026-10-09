from __future__ import annotations

from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from seman2.evidence.store import EvidenceStore
from seman2.interpretation.kqml import LocalTripsTransport, parse_kqml, probe_local_trips
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

    def test_transport_uses_parser_setting_message_without_arbitrary_eval(self) -> None:
        class FakeConnection:
            def __init__(self) -> None:
                self.sent = b""
                self.returned = False

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def settimeout(self, _timeout: float) -> None:
                pass

            def sendall(self, payload: bytes) -> None:
                self.sent += payload

            def recv(self, _size: int) -> bytes:
                if self.returned:
                    return b""
                self.returned = True
                match = re.search(rb":uttnum (\d+)", self.sent)
                assert match is not None
                return (
                    b"(tell :sender PARSER :content "
                    b"(failed-to-parse :uttnum " + match.group(1) + b"))"
                )

        connection = FakeConnection()
        with patch("seman2.interpretation.kqml.socket.create_connection", return_value=connection):
            LocalTripsTransport().parse("Exact, punctuation.", {"number-parses-desired": "2"})

        self.assertIn(b"(number-interps-desired 2)", connection.sent)
        self.assertNotIn(b"(eval", connection.sent.lower())

    def test_health_probe_requires_a_reply_from_parser(self) -> None:
        class ProbeConnection:
            def __init__(self) -> None:
                self.sent = b""

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def settimeout(self, _timeout: float) -> None:
                pass

            def sendall(self, payload: bytes) -> None:
                self.sent += payload

            def recv(self, _size: int) -> bytes:
                tag = re.search(rb":reply-with ([^ )]+)", self.sent)
                assert tag is not None
                return (
                    b"(sorry :sender PARSER :in-reply-to "
                    + tag.group(1)
                    + b' :comment "health probe")'
                )

        connection = ProbeConnection()
        with patch("seman2.interpretation.kqml.socket.create_connection", return_value=connection):
            self.assertTrue(probe_local_trips(timeout_seconds=0.2))

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

    def test_tree_only_final_punctuation_gets_an_exact_source_span(self) -> None:
        payload = KQML_FIXTURE.replace(
            b":WORDS (W::DOG W::RUNS W::PUNC-PERIOD)",
            b":WORDS (W::DOG W::RUNS)",
        ).replace(
            b"(W::PUNC))))",
            b"(W::PUNC :FEATS ((W::LEX W::PUNC-PERIOD))))))",
        )

        with TemporaryDirectory() as directory:
            store = EvidenceStore(Path(directory) / "evidence.sqlite")
            evidence = store.append("Dog runs.", stream_id="fixture")
            bundle = TripsAdapter(KqmlFixtureTransportWithPayload(payload)).interpret(evidence)
            store.close()

        punctuation = [
            node
            for node in bundle.hypotheses[0].structural.nodes
            if node.category == "parser-word" and node.attributes.get("surface") == "."
        ]
        self.assertEqual(len(punctuation), 1)
        self.assertEqual((punctuation[0].span.start, punctuation[0].span.end), (8, 9))
        self.assertTrue(punctuation[0].attributes["inferred_from_tree"])


class KqmlFixtureTransportWithPayload(KqmlFixtureTransport):
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def parse(self, input_text: str, parameters: dict[str, str]) -> TripsResponse:
        response = super().parse(input_text, parameters)
        return TripsResponse(
            body=self.payload,
            content_type=response.content_type,
            status=response.status,
            endpoint=response.endpoint,
            headers=response.headers,
        )


if __name__ == "__main__":
    unittest.main()
