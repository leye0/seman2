"""Deterministic grammar repair queue selection never ranks candidates."""

import json
import unittest

from scripts.next_grammar_case import DEFAULT_QUEUE, select_next


class NextGrammarCaseTests(unittest.TestCase):
    def setUp(self):
        self.queue = json.loads(DEFAULT_QUEUE.read_text(encoding="utf-8"))

    def test_next_follows_persisted_cursor_without_hardcoded_case(self):
        indices = [row["index"] for row in self.queue["unresolved"]]
        cursor = self.queue["last_attempted_index"]
        expected = next((index for index in indices if index > cursor), indices[0])
        self.assertEqual(select_next(self.queue)["index"], expected)

    def test_advances_to_next_unresolved_without_ranking(self):
        indices = [row["index"] for row in self.queue["unresolved"]]
        self.assertEqual(select_next(self.queue, after=indices[1])["index"],
                         indices[2])

    def test_wraps_to_first_unresolved(self):
        indices = [row["index"] for row in self.queue["unresolved"]]
        self.assertEqual(select_next(self.queue, after=indices[-1])["index"],
                         indices[0])

    def test_rejects_duplicate_or_missing_queue_entries(self):
        broken = {**self.queue, "unresolved": self.queue["unresolved"] * 2}
        with self.assertRaises(ValueError):
            select_next(broken)
        broken = {**self.queue, "unresolved": self.queue["unresolved"][1:]}
        with self.assertRaises(ValueError):
            select_next(broken)


if __name__ == "__main__":
    unittest.main()
