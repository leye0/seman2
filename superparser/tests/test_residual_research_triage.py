"""Residual-26 triage contract, independent of WordNet or recognition budgets."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import unittest

from scripts.triage_residual_26 import triage, render_overview

REFERENCE = Path(__file__).resolve().parents[1] / "research" / "residual_26_reference.json"


def fixture():
    reference = json.loads(REFERENCE.read_text(encoding="utf8"))
    diagnostics, contexts, failed = [], [], []
    for i in range(500):
        source = f"source {i}."
        status = "complete"
        if i == 8:
            status = "no_structural_root"
        if i == 463:
            status = "roots_without_valid_analysis"
        if i == 312:
            status = "timeout"
        record = reference["cases"]
        by_index = {x["index"]: x for x in record}
        case_id = by_index[i]["case_id"] if i in by_index else f"fake:{i}"
        diagnostics.append({"index": i, "case_id": case_id, "book_id": 766,
                            "source_text": source, "canonical_analysis_text": source,
                            "status": status, "forest_budget_exceeded": status == "timeout"})
        contexts.append({"index": i, "book_id": 766, "source_text": source,
                         "status": status, "surface_signals": ["actual_semicolon_part"] if i == 8 else [],
                         "context": {"source_text": source, "semicolon_part_index": 1 if i == 8 else 0,
                                     "semicolon_parts": 2 if i == 8 else 1,
                                     "preceding_semicolon_part": "Previous;" if i == 8 else None,
                                     "full_unsplit_sentence": "Previous; source 8." if i == 8 else source}})
        if status != "complete":
            row = {**diagnostics[-1], "lexical_diagnostic": None}
            if i == 8:
                row["lexical_diagnostic"] = {
                    "words_without_any_candidate": [], "words_without_exact_candidate": [],
                    "lexical_candidate_count": 7,
                }
            failed.append(row)
    return diagnostics, contexts, failed, {"cohort_sha256": reference["cohort_sha256"]}, reference


class ResidualResearchTriageTests(unittest.TestCase):
    def test_registry_is_pinned_to_26_unique_cases_and_not_all_faults(self):
        ref = fixture()[-1]
        self.assertEqual(len(ref["cases"]), 26)
        self.assertEqual(len({row["case_id"] for row in ref["cases"]}), 26)
        self.assertEqual(set(row["index"] for row in ref["cases"]), {
            8, 64, 94, 96, 105, 109, 115, 116, 167, 182, 194, 220, 226,
            233, 235, 243, 248, 312, 344, 347, 463, 466, 480, 487, 491, 497,
        })
        self.assertEqual({r["index"] for r in ref["cases"] if
                          r["assessment"] == "verified_marked_mode_prior_test"}, {463, 480})
        self.assertTrue(all(r["assessment"] in {
            "provisional_hypothesis", "verified_marked_mode_prior_test"
        } for r in ref["cases"]))

    def test_recovery_is_tracked_without_erasing_baseline_case(self):
        rows, summary = triage(*fixture())
        self.assertEqual(len(rows), 26)
        self.assertEqual(summary["original_residuals"], 26)
        self.assertEqual(summary["original_still_unresolved"], 3)
        self.assertEqual(summary["original_recovered"], 23)
        self.assertEqual(summary["new_unreviewed_failures"], 0)
        by_index = {row["index"]: row for row in rows}
        self.assertEqual(by_index[8]["current_outcome"], "structural_unresolved")
        self.assertEqual(by_index[312]["current_outcome"], "resource_censored")
        self.assertEqual(by_index[64]["trajectory"], "recovered")
        self.assertEqual(by_index[463]["trajectory"], "unresolved")
        self.assertFalse(by_index[463]["grammatical_fault_established_by_this_audit"])
        self.assertFalse(by_index[463]["marked_parse_reexecuted_in_this_audit"])
        self.assertEqual(by_index[8]["observed_evidence"]["source_context"]
                         ["preceding_semicolon_part"], "Previous;")
        self.assertEqual(summary["current_failed_with_lexical_diagnostic"], 1)
        self.assertIn("provisional_hypothesis", render_overview(rows, summary))

    def test_new_failure_is_surfaced_as_unreviewed(self):
        d, c, f, s, ref = fixture()
        d[42]["status"] = "no_structural_root"
        c[42]["status"] = "no_structural_root"
        f.append({**d[42], "lexical_diagnostic": None})
        rows, summary = triage(d, c, f, s, ref)
        self.assertEqual(summary["new_unreviewed_failures"], 1)
        new = next(row for row in rows if row["index"] == 42)
        self.assertEqual(new["trajectory"], "new_unreviewed_failure")
        self.assertIsNone(new["hypothesis"])
        self.assertEqual(new["research_tracks"], [])
        self.assertFalse(new["grammatical_fault_established_by_this_audit"])

    def test_provenance_and_run_consistency_fail_closed(self):
        builders = [
            lambda d,c,f,s,r: s.update(cohort_sha256="changed"),
            lambda d,c,f,s,r: d[8].update(case_id="wrong"),
            lambda d,c,f,s,r: c[8].update(source_text="other"),
            lambda d,c,f,s,r: f.pop(),
            lambda d,c,f,s,r: d[1].update(index=2),
        ]
        for mutation in builders:
            with self.subTest(mutation=mutation):
                args = deepcopy(fixture())
                mutation(*args)
                with self.assertRaises(ValueError):
                    triage(*args)


if __name__ == "__main__":
    unittest.main()

