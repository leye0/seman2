from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from seman2.evidence.store import EvidenceStore
from seman2.evidence.stream import dialogue_tsv, ingest_records, text_blocks
from seman2.runtime.engine import Seman2Runtime


class NullInterpreter:
    key = "fixture"


class StreamTests(unittest.TestCase):
    def test_text_blocks_preserve_exact_utf8_slices_and_offsets(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            path.write_bytes("Un.\r\nDeux.\r\n\r\nTrois.\n".encode())
            records = tuple(text_blocks(path))
            self.assertEqual([row.raw for row in records], ["Un.\r\nDeux.\r\n", "Trois.\n"])
            source = path.read_bytes()
            for row in records:
                start = row.source["byte_start"]
                end = row.source["byte_end"]
                self.assertEqual(source[start:end].decode(), row.raw)

    def test_dialogue_keeps_native_row_and_speaker_as_observable_context(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "dialogue.tsv"
            path.write_bytes("A\tBonjour.\r\nB\tSalut.\n".encode())
            records = tuple(dialogue_tsv(path))
            self.assertEqual(records[0].raw, "Bonjour.")
            self.assertEqual(records[0].context["speaker_source_value"], "A")
            self.assertEqual(records[0].metadata["native_record"], "A\tBonjour.\r\n")

    def test_records_enter_the_same_runtime_ingestion_boundary(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.txt"
            source.write_text("Alpha.\n\nBeta.\n", encoding="utf-8")
            store = EvidenceStore(Path(directory) / "runtime.sqlite")
            runtime = Seman2Runtime(store, NullInterpreter())  # type: ignore[arg-type]
            try:
                units = ingest_records(
                    runtime, text_blocks(source), stream_id="book:fixture"
                )
                self.assertEqual([unit.sequence for unit in units], [0, 1])
                self.assertEqual(store.counts()["interpretation_jobs"], 2)
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()

