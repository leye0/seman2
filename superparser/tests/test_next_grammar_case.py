"""Deterministic grammar repair queue selection never ranks candidates."""

import json
import unittest

from scripts.next_grammar_case import DEFAULT_QUEUE, select_next


class NextGrammarCaseTests(unittest.TestCase):
    def setUp(self):
        self.queue = json.loads(DEFAULT_QUEUE.read_text(encoding="utf-8"))

    def test_next_after_last_repaired_354_is_370(self):
        self.assertEqual(select_next(self.queue)["index"], 370)

    def test_advances_to_next_unresolved_without_ranking(self):
        self.assertEqual(select_next(self.queue, after=370)["index"], 371)

    def test_wraps_to_first_unresolved(self):
        self.assertEqual(select_next(self.queue, after=497)["index"], 8)

    def test_rejects_duplicate_or_missing_queue_entries(self):
        broken = {**self.queue, "unresolved": self.queue["unresolved"] * 2}
        with self.assertRaises(ValueError):
            select_next(broken)
        broken = {**self.queue, "unresolved": self.queue["unresolved"][1:]}
        with self.assertRaises(ValueError):
            select_next(broken)


if __name__ == "__main__":
    unittest.main()
