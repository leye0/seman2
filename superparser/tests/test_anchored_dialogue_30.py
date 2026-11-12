"""Check the *entire* historical 30-case dialogue failure set, not toy snippets."""
from __future__ import annotations

from collections import Counter
import unittest
from hashlib import sha256

from scripts.audit_anchored_dialogue_30 import (
    WITNESSES, EXPECTED_COHORT_SHA, audit,
)
from scripts.diagnose_novel_parses import select_cases, EXPECTED_500_COHORT_SHA256
from seman_parser.structural_preanalysis import analyze_paragraph


class AnchoredDialogue30Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, _sources = select_cases(500)

    def test_original_30_are_exactly_the_current_real_literary_sources(self):
        self.assertEqual(EXPECTED_500_COHORT_SHA256, EXPECTED_COHORT_SHA)
        self.assertEqual(len(WITNESSES), 30)
        self.assertEqual(len(self.cases), 500)
        self.assertEqual(
            dict(Counter(w.subtype for w in WITNESSES)),
            {
                "nested_quotation": 2,
                "single_quote_with_reporting_clause": 8,
                "split_speech_with_intercalated_reporting_clause": 7,
                "multisentence_quotation": 6,
                "unattributed_single_quotation": 7,
            }
        )
        for w in WITNESSES:
            with self.subTest(index=w.index):
                case = self.cases[w.index]
                identifier = str(case["book_id"]) + ":" + sha256(
                    case["source_text"].encode("utf-8")
                ).hexdigest()[:16]
                self.assertEqual(identifier, w.case_id)
                self.assertEqual(case["source_text"], case["text"])
                self.assertEqual(case["quotation_status"], "balanced")
                self.assertTrue(any(
                    p["function"] == "direct_speech"
                    for p in case["structural_constituents"]
                ))
                # Every component has real source positions and legal governor
                ids = {part["id"] for part in case["structural_constituents"]}
                for part in case["structural_constituents"]:
                    self.assertEqual(
                        case["source_text"][part["start"]:part["end"]],
                        case["text"][part["start"]:part["end"]],
                    )
                    if part["governor"] is not None:
                        self.assertIn(part["governor"], ids)

    def test_paired_audit_does_not_hide_failures_or_change_sample(self):
        rows = []
        for i, case in enumerate(self.cases):
            rows.append({
                "index": i,
                "book_id": case["book_id"],
                "case_id": str(case["book_id"]) + ":" + sha256(
                    case["source_text"].encode("utf8")
                ).hexdigest()[:16],
                "source_text": case["source_text"],
                "structural_functions": [
                    p["function"] for p in case["structural_constituents"]
                ],
                "structural_relations": [
                    p["relation"] for p in case["structural_constituents"]
                ],
                "quotation_status": case["quotation_status"],
                "status": "roots_without_valid_analysis",
            })
        # This is a fixture of statuses, NOT a claim of parse success.
        rows[WITNESSES[0].index]["status"] = "complete"
        result = audit(rows, cohort_sha=EXPECTED_COHORT_SHA)
        self.assertEqual(result["total"], 30)
        self.assertEqual(result["now_complete"], 1)
        self.assertEqual(result["still_failed"], 29)
        self.assertEqual(len(result["cases"]), 30)
        self.assertEqual(result["schema"], "seman2-anchored-real-dialogue-30-v2")
        anchored = {c["index"]: c for c in result["cases"]}
        for i in (413, 157):
            self.assertIn("postposed_vocative_with_reporter",
                          anchored[i]["source_composition_plans_not_proofs"])
            self.assertTrue(any(
                c["function"] == "reporting_clause"
                for c in anchored[i]["all_quote_and_reporting_constituents"]
            ))
        self.assertFalse(anchored[11]["source_composition_plans_not_proofs"])
        self.assertGreater(result["not_currently_planned"], 0)
        self.assertEqual(result["cases"][0]["index"], WITNESSES[0].index)
        with self.assertRaisesRegex(ValueError, "cannot migrate"):
            audit(rows, cohort_sha="different_cohort")
        rows[WITNESSES[0].index]["case_id"] = "changed"
        with self.assertRaisesRegex(AssertionError, "ordering changed"):
            audit(rows, cohort_sha=EXPECTED_COHORT_SHA)


if __name__ == "__main__":
    unittest.main()
