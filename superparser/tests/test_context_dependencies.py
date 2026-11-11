"""Ensure the contextual witness audit preserves original source boundaries."""
import unittest
from scripts.audit_context_dependencies import source_contexts,surface_signatures,audit


class SourceContextAuditTests(unittest.TestCase):
    def test_actual_semicolon_and_paragraph_neighbors(self):
        text=("I promised to return; which I accordingly did. "
              "The weather was cold, but we waited.\n\nMary spoke. I replied.")
        rows=source_contexts(text)
        self.assertEqual(len(rows),5)
        self.assertEqual(rows[1]["source_text"],"which I accordingly did.")
        self.assertEqual(rows[1]["preceding_semicolon_part"],
                         "I promised to return;")
        self.assertEqual(rows[1]["semicolon_part_index"],1)
        self.assertEqual(rows[1]["semicolon_parts"],2)
        self.assertEqual(rows[1]["next_sentence_same_paragraph"],
                         "The weather was cold, but we waited.")
        self.assertIsNone(rows[3]["previous_sentence_same_paragraph"])
        self.assertEqual(rows[4]["previous_sentence_same_paragraph"],
                         "Mary spoke.")

    def test_context_ordinals_remain_frozen_v1_after_v2_introduction(self):
        from research.verbnet_lr.gutenberg_novels import analysis_units

        source = "I promised to return; which I accordingly did."
        historical = list(analysis_units(source, segmentation_version=1))
        prospective = list(analysis_units(source, segmentation_version=2))
        self.assertEqual(len(historical), 2)
        self.assertEqual(len(prospective), 1)

        contexts = source_contexts(source)
        self.assertEqual(
            [contexts[index]["source_text"] for index in range(len(contexts))],
            [unit.source_text for unit in historical],
        )
        self.assertEqual(
            contexts[1]["preceding_semicolon_part"],
            historical[0].source_text,
        )

    def test_surface_signals_are_not_syntactic_labels(self):
        self.assertIn("relative_initial",
                      surface_signatures("which I accordingly did."))
        self.assertIn("coordinator_followed_by_comma",
                      surface_signatures("and, keeping me close, I waited."))
        self.assertIn("ing_surface_not_morphologically_verified",
                      surface_signatures("Avoiding them, she left."))
        self.assertNotIn("relative_initial",
                         surface_signatures("The dog which I saw left."))

    def test_misaligned_cohort_fails_closed(self):
        from unittest.mock import patch
        from scripts.audit_context_dependencies import fingerprint
        cases=[{"book_id":766,"ordinal":i,"text":f"A{i}.",
                "source_text":f"A{i}.","semicolon_split":False,
                "band":"04-08","tokens":4}
               for i in range(500)]
        diagnostics=[{"index":i,"book_id":766,
                      "ordinal":i,"sentence":f"A{i}.","status":"complete"}
                     for i in range(500)]
        diagnostics[0]["ordinal"]=2
        # This fixture is intentionally not the real SHA-pinned cohort.
        # Patch only the digest constant so the ordinal mismatch is tested.
        with patch("scripts.audit_context_dependencies.EXPECTED_500_COHORT_SHA256",
                   fingerprint(cases)):
            with self.assertRaisesRegex(AssertionError, "alignment failure"):
                audit(cases,diagnostics,{766:{}})


if __name__=="__main__":unittest.main()
