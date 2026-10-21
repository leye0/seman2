"""Prevent unittest CI from silently skipping plain module-level tests."""
from __future__ import annotations

import unittest
from superparser.tests import (
    test_syntax_correctness,
    test_reference_300_evaluator,
)


class TestDiscoveryContract(unittest.TestCase):
    def test_linguistic_quality_functions_are_registered(self):
        suite=unittest.defaultTestLoader.loadTestsFromModule(
            test_syntax_correctness,
        )
        self.assertGreaterEqual(suite.countTestCases(),36)

    def test_reference_gold_functions_are_registered(self):
        suite=unittest.defaultTestLoader.loadTestsFromModule(
            test_reference_300_evaluator,
        )
        self.assertGreaterEqual(suite.countTestCases(),4)


if __name__=="__main__":
    unittest.main()
