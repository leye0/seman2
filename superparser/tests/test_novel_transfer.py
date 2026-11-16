"""Small regression tests for the separate literary-transfer runner."""

from hashlib import sha256
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from scripts import evaluate_novel_transfer as transfer


class NovelTransferTests(unittest.TestCase):
    def test_normalized_identity_rejects_typographic_duplicates(self):
        self.assertEqual(
            transfer.normalized_identity("“I DON’T know.”"),
            transfer.normalized_identity('"I don\'t know!"'),
        )
        self.assertNotEqual(
            transfer.normalized_identity("I knew."),
            transfer.normalized_identity("I know."),
        )

    def test_source_body_pins_bytes_and_removes_front_matter(self):
        raw = (
            "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\r\n"
            "\r\nTable of Contents\r\n\r\nCHAPTER I\r\n\r\n"
            + "This is a complete sentence.\r\n" * 500
            + "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\r\n"
        ).encode()
        pin = sha256(raw).hexdigest()
        body = transfer.source_body(raw, 99, pin, re.compile(r"(?m)^CHAPTER I$"))
        self.assertTrue(body.startswith("CHAPTER I\n\n"))
        self.assertNotIn("Contents", body)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            transfer.source_body(raw + b" ", 99, pin, re.compile("CHAPTER I"))

    def test_source_round_trip_rejects_synthetic_text_and_invalid_offsets(self):
        case = {
            "transfer_id": "T99-0001", "structural_core_source_span": [0, 11],
            "text": "He sat.", "source_text": "He sat.", "synthetic_prefix": "",
            "synthetic_suffix": "", "synthetic_terminal": False,
        }
        core = "He\n    sat."
        transfer.verify_source(case, core)
        with self.assertRaisesRegex(ValueError, "Non-source-exact"):
            transfer.verify_source({**case, "synthetic_terminal": True}, core)
        with self.assertRaisesRegex(ValueError, "Non-source-exact"):
            transfer.verify_source({**case, "structural_core_source_span": [-1, 4]}, core)

    def test_cli_rejects_drift_before_writing_cohort(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = ["evaluate_novel_transfer", "--sample-only", "--books-dir", directory,
                    "--out-dir", str(root / "output")]
            with patch("sys.argv", args), patch.object(
                transfer, "select_transfer_cases", return_value=([{"new_case": True}], []),
            ), self.assertRaisesRegex(ValueError, "Transfer cohort changed"):
                transfer.main()
            self.assertFalse((root / "output" / "cohort.jsonl").exists())

    def test_cli_sample_only_does_not_initialize_parser(self):
        case = {"source_text": "He sat."}
        digest = sha256((json.dumps(case, sort_keys=True) + "\n").encode()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            args = ["evaluate_novel_transfer", "--sample-only", "--books-dir", directory,
                    "--out-dir", directory]
            with patch("sys.argv", args), patch.object(
                transfer, "select_transfer_cases", return_value=([case], []),
            ), patch.object(transfer, "EXPECTED_COHORT_SHA256", digest), patch.object(
                transfer.ParserResources, "from_dir",
            ) as from_dir:
                transfer.main()
            from_dir.assert_not_called()
            self.assertEqual(json.loads((Path(directory) / "cohort.jsonl").read_text()), case)
