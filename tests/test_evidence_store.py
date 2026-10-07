from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from seman2.evidence.store import EvidenceStore, EvidenceStoreError


class EvidenceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.database = Path(self.temporary.name) / "evidence.sqlite"
        self.store = EvidenceStore(self.database)

    def tearDown(self) -> None:
        self.store.close()
        self.temporary.cleanup()

    def test_append_is_lossless_ordered_and_queued_atomically(self) -> None:
        raw = "Première ligne.\r\nDeuxième ligne.\n"
        first = self.store.append(
            raw,
            stream_id="stream-1",
            source={"type": "fixture", "source_id": "one"},
            metadata={"language_hint": "fr"},
        )
        second = self.store.append(
            "Next.",
            stream_id="stream-1",
            source={"type": "fixture", "source_id": "two"},
        )

        self.assertEqual(self.store.journal_mode.lower(), "wal")
        self.assertEqual(self.store.get(first.evidence_id).raw, raw)
        self.assertEqual(first.raw_sha256, hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(second.sequence, 1)
        self.assertEqual(second.context["previous"], first.evidence_id)
        self.assertEqual(
            self.store.counts(),
            {
                "evidence_units": 2,
                "interpretation_jobs": 2,
                "analysis_bundles": 0,
                "interpretation_hypotheses": 0,
                "hypothesis_revisions": 0,
            },
        )

    def test_evidence_cannot_be_updated_or_deleted(self) -> None:
        evidence = self.store.append("immutable", stream_id="stream-1")
        external = sqlite3.connect(self.database)
        try:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                external.execute(
                    "UPDATE evidence_units SET raw_text = 'changed' WHERE evidence_id = ?",
                    (evidence.evidence_id,),
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                external.execute(
                    "DELETE FROM evidence_units WHERE evidence_id = ?",
                    (evidence.evidence_id,),
                )
        finally:
            external.close()

    def test_sequence_cannot_move_backwards_and_context_is_stream_local(self) -> None:
        first = self.store.append("one", stream_id="a", sequence=4)
        other = self.store.append("other", stream_id="b")
        self.assertIsNone(other.context["previous"])
        with self.assertRaisesRegex(EvidenceStoreError, "monotonically"):
            self.store.append("duplicate", stream_id="a", sequence=4)
        self.assertEqual(self.store.context_before(first.evidence_id, limit=3), ())

    def test_replay_adds_a_generation_without_touching_evidence(self) -> None:
        evidence = self.store.append("one", stream_id="a")
        job_id = self.store.enqueue_replay(evidence.evidence_id, interpreter_key="trips")
        trace = self.store.trace(evidence.evidence_id)
        self.assertTrue(job_id.startswith("job_"))
        self.assertEqual([row["generation"] for row in trace["jobs"]], [0, 1])
        self.assertEqual(trace["evidence"]["raw"], "one")


if __name__ == "__main__":
    unittest.main()

