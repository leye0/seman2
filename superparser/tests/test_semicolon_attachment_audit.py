"""The v2 audit must distinguish recognition from invalid semicolon scope."""

import unittest
from types import SimpleNamespace

from superparser.scripts.audit_semicolon_context import _attachment_warnings


def node(category, rule_id, start, end, *children):
    return SimpleNamespace(
        category=category, rule_id=rule_id, start=start, end=end,
        children=children,
    )


class SemicolonAttachmentAuditTests(unittest.TestCase):
    def test_missing_root_is_explicit(self):
        self.assertEqual(_attachment_warnings(None, 8), ["no_selected_root"])

    def test_semicolon_inside_nominal_apposition_is_flagged(self):
        punctuation = node("COMMA", None, 15, 16)
        apposition = node("NP", "np_appos_comma", 4, 27, punctuation)
        root = node("CLAUSE", "clause_np_vp", 0, 27, apposition)
        self.assertIn(
            "semicolon_consumed_by_nominal_apposition",
            _attachment_warnings(root, 15),
        )

    def test_comma_vp_coordination_cannot_silently_swallow_semicolon(self):
        punctuation = node("COMMA", None, 9, 10)
        coordination = node("VP", "vp_comma_coord", 0, 21, punctuation)
        root = node("CLAUSE", "clause_np_vp", 0, 21, coordination)
        self.assertIn(
            "semicolon_consumed_by_comma_vp_coordination",
            _attachment_warnings(root, 9),
        )

    def test_clause_level_semicolon_has_no_false_positive(self):
        punctuation = node("COMMA", None, 8, 9)
        root = node("CLAUSE", "clause_semicolon_relative", 0, 28,
                    punctuation)
        self.assertEqual(_attachment_warnings(root, 8), [])

    def test_missing_semicolon_leaf_is_reported(self):
        root = node("CLAUSE", "clause_np_vp", 0, 5)
        self.assertEqual(
            _attachment_warnings(root, 7),
            ["semicolon_missing_from_selected_tree"],
        )


if __name__ == "__main__":
    unittest.main()
