"""Diagnostic breakdown must count real quote spans, never apostrophes."""
from __future__ import annotations
import unittest

from scripts.audit_dialogue_failures import analyze


class DialogueResidualAuditTests(unittest.TestCase):
    def test_genuine_speech_vs_lexical_apostrophe(self):
        def row(i, text, status, parts):
            return {"index": i, "source_text": text, "status": status,
                    "structural_functions": parts, "case_id": "test"}
        report = analyze([
            row(0, "He couldn't come at o’clock.", "complete",
                ["utterance", "matrix_clause"]),
            row(1, '“I know,” said Mary, “you came.”',
                "roots_without_valid_analysis",
                ["utterance", "direct_speech", "direct_speech",
                 "reporting_clause", "split_direct_speech_turn",
                 "spoken_clause_candidate", "spoken_clause_candidate"]),
            row(2, '“Welcome. Sit down.”', "complete",
                ["utterance", "direct_speech",
                 "spoken_clause_candidate", "spoken_clause_candidate"]),
            row(3, "It's all right.", "no_structural_root",
                ["utterance", "matrix_clause"]),
        ])
        stats = report["outcomes"]
        self.assertEqual(stats["direct_speech"]["total"], 2)
        self.assertEqual(stats["direct_speech"]["failed"], 1)
        self.assertEqual(stats["non_direct_speech"]["total"], 2)
        self.assertEqual(stats["non_direct_speech"]["failed"], 1)
        self.assertEqual(
            stats["speech_subtype:split_speech_with_intercalated_reporting_clause"]["failed"],
            1,
        )
        self.assertEqual(
            stats["speech_subtype:multisentence_quotation"]["complete"], 1
        )
        self.assertEqual(len(report["failed_direct_speech_cases"]), 1)
        self.assertTrue(report["parse_results_unchanged"])

    def test_missing_structural_metadata_does_not_guess_from_glyph(self):
        with self.assertRaisesRegex(ValueError, "structural functions"):
            analyze([{"index": 0, "status": "complete",
                      "source_text": '"I came."'}])


if __name__ == "__main__":
    unittest.main()
