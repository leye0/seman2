"""Tests for the feature-agnostic *offline* grammar coverage bound."""
import unittest

from research.verbnet_lr.upper_bound import recognize_upper_bound


class UpperBoundTests(unittest.TestCase):
    RULES = [
        ("CLAUSE", ("NP", "VP")),
        ("NP", ("DET", "N")),
        ("N", ("ADJ", "N")),  # N is BOTH productive and lexical
        ("VP", ("V",)),
        ("NP", ("NP", "PP")),  # direct left recursion
        ("PP", ("PREP", "NP")),
    ]

    def test_productive_or_direct_lexical_noun(self):
        direct = [{"DET"}, {"N"}, {"V"}]
        modifier = [{"DET"}, {"ADJ"}, {"N"}, {"V"}]
        self.assertEqual(recognize_upper_bound(self.RULES, direct)["status"], "ACCEPTED")
        self.assertEqual(recognize_upper_bound(self.RULES, modifier)["status"], "ACCEPTED")

    def test_left_recursive_nominal_modification(self):
        cats = [{"DET"}, {"N"}, {"PREP"}, {"DET"}, {"N"}, {"V"}]
        result = recognize_upper_bound(self.RULES, cats)
        self.assertEqual(result["status"], "ACCEPTED")

    def test_missing_structural_category_is_rejected(self):
        cats = [{"DET"}, {"ADV"}, {"N"}, {"V"}]
        result = recognize_upper_bound(self.RULES, cats)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["complete"], False)

    def test_item_budget_is_not_misreported_as_rejection(self):
        result = recognize_upper_bound(self.RULES, [{"DET"}, {"N"}, {"V"}],
                                       max_items=1)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["complete"])


if __name__ == "__main__":
    unittest.main()
