"""The original 85 failed cases remain pinned after fixes shrink active queue."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.audit_failure_families_85 import inventory, markdown

ROOT = Path(__file__).resolve().parents[2]


class Original85InventoryTests(unittest.TestCase):
    def test_original_witnesses_persist_after_first_three_batch_repairs(self):
        output = inventory()
        pinned = json.loads(
            (ROOT / "superparser/research/pinned_original_failure_85.json").read_text()
        )
        active = json.loads((ROOT / "docs/GRAMMAR_CASE_QUEUE.json").read_text())
        self.assertEqual(output["cohort_sha256"], pinned["cohort_sha256"])
        self.assertEqual(output["cohort_sha256"], active["cohort_sha256"])
        self.assertEqual(output["baseline_completed"], 415)
        self.assertEqual(output["original_unresolved"], 85)
        self.assertEqual(len(output["cases"]), 85)
        self.assertEqual(
            [(r["index"], r["case_id"], r["status"]) for r in output["cases"]],
            [(r["index"], r["case_id"], r["status"])
             for r in pinned["witnesses"]],
        )
        self.assertEqual(output["active_completed"], active["completed_count"])
        self.assertEqual(output["active_unresolved"], len(active["unresolved"]))
        self.assertEqual(output["repaired_original_indexes"],
                         sorted(set(r["index"] for r in pinned["witnesses"])
                                - set(r["index"] for r in active["unresolved"])))
        self.assertTrue(
            {22, 270, 280}.issubset(output["repaired_original_indexes"])
        )
        self.assertTrue(
            {22, 270, 280}.issubset(r["index"] for r in output["cases"])
        )
        report = markdown(output)
        self.assertIn("85/85 original baseline failures", report)
        self.assertIn(f"**Current active failures:** {len(active['unresolved'])}", report)

    def test_inventory_never_mutates_active_queue_or_original_snapshot(self):
        paths = (
            ROOT / "docs/GRAMMAR_CASE_QUEUE.json",
            ROOT / "superparser/research/pinned_original_failure_85.json",
        )
        before = tuple(p.read_bytes() for p in paths)
        inventory()
        after = tuple(p.read_bytes() for p in paths)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
