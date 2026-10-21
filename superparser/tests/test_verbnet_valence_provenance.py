"""Morphosyntactic valence evidence is never widened beyond its source."""
from __future__ import annotations

import unittest

from scripts.audit_verbal_readings import _frame_valence, load_verbnet_index


class VerbNetProvenanceTests(unittest.TestCase):
    def test_direct_pp_and_np_plus_pp_frames_are_distinct(self):
        adjunct_to_object = {
            "symbols": [["NP"], ["PREP:on"], ["NP"]],
        }
        intransitive_pp = {
            "symbols": [["PREP:on"], ["NP"]],
        }
        a = _frame_valence(adjunct_to_object)
        b = _frame_valence(intransitive_pp)
        self.assertEqual(a["prepositions"], ["on"])
        self.assertFalse(a["direct_pp_frame"])
        self.assertEqual(b["prepositions"], ["on"])
        self.assertTrue(b["direct_pp_frame"])

    def test_wildcard_preposition_is_not_a_specific_attested_on(self):
        wildcard = _frame_valence({
            "symbols": [["PREP:*"], ["NP"]],
        })
        self.assertEqual(wildcard["prepositions"], ["*"])
        self.assertTrue(wildcard["direct_pp_frame"])
        self.assertNotIn("on", wildcard["prepositions"])

    def test_bundled_verbnet_preserves_frame_source(self):
        index = load_verbnet_index()
        for lemma in ("fix", "drink", "encompass"):
            with self.subTest(lemma=lemma):
                frames = index[lemma]
                self.assertTrue(frames)
                self.assertTrue(all(row["lemma"] == lemma for row in frames))
                self.assertTrue(all("id" in row and "link" in row
                                    and "symbols" in row for row in frames))
        fix_prepositions = {
            p for row in index["fix"]
            for p in _frame_valence(row)["prepositions"]
        }
        # This is a limitation of the pinned bundle, NOT an English
        # grammatical prohibition. Do not invent evidence for fix on.
        self.assertNotIn("on", fix_prepositions)


if __name__ == "__main__":
    unittest.main()
