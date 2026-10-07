from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from seman2.evidence.store import EvidenceStore
from seman2.interpretation.trips_adapter import TripsAdapter


@unittest.skipUnless(
    os.environ.get("SEMAN2_TRIPS_INTEGRATION") == "1",
    "activer avec SEMAN2_TRIPS_INTEGRATION=1 et un TRIPS local",
)
class LocalTripsIntegrationTests(unittest.TestCase):
    def test_real_local_parser_returns_native_dual_hypotheses(self) -> None:
        with TemporaryDirectory() as directory:
            store = EvidenceStore(Path(directory) / "evidence.sqlite")
            evidence = store.append("The dog runs.", stream_id="integration")
            bundle = TripsAdapter(number_parses_desired=2).interpret(evidence)
            store.close()

        self.assertEqual(bundle.request_metadata["endpoint"], "kqml://127.0.0.1:6200")
        self.assertEqual(bundle.raw_content_type, "application/kqml; charset=utf-8")
        self.assertTrue(bundle.raw_payload.startswith(b"(TELL :CONTENT"))
        self.assertGreaterEqual(len(bundle.hypotheses), 1)
        primary = bundle.hypotheses[0]
        self.assertGreater(len(primary.semantic.nodes), 0)
        self.assertGreater(len(primary.structural.nodes), 0)
        self.assertGreater(len(primary.cross_links), 0)


if __name__ == "__main__":
    unittest.main()
