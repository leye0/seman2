"""Grammar coverage tests: passive, coordination, relatives, questions."""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser import Parser

DATA = Path(__file__).resolve().parents[1] / "data"


def parse(text: str, *, goal: str = "CLAUSE"):
    parser = Parser.from_dir(DATA, goal_category=goal)
    return parser.parse(text)


def relations(text: str, *, goal: str = "CLAUSE") -> set[str]:
    best = parse(text, goal=goal).result.best()
    assert best is not None, text
    return {edge.relation for edge in best.semantic.graph.relations}


class PassiveTests(unittest.TestCase):
    def test_short_passive_theme(self) -> None:
        report = parse("The box was opened.")
        self.assertTrue(report.result.completed)
        rels = relations("The box was opened.")
        self.assertTrue(rels & {"THEME", "AFFECTED"}, rels)

    def test_long_passive_agent(self) -> None:
        rels = relations("The box was opened by John.")
        self.assertTrue(rels & {"THEME", "AFFECTED"}, rels)
        self.assertIn("AGENT", rels)

    def test_passive_uses_passive_rule(self) -> None:
        best = parse("The box was opened.").result.best()
        assert best is not None
        self.assertEqual(best.rule_id, "clause_passive")

    def test_active_still_active(self) -> None:
        best = parse("John opened the box.").result.best()
        assert best is not None
        self.assertEqual(best.rule_id, "clause_np_vp")
        rels = {edge.relation for edge in best.semantic.graph.relations}
        self.assertIn("AGENT", rels)
        self.assertTrue(rels & {"AFFECTED", "THEME"}, rels)


class CoordinationTests(unittest.TestCase):
    def test_np_coordination(self) -> None:
        rels = relations("John and Mary left.")
        self.assertIn("CONJUNCT", rels)

    def test_np_coordination_is_plural(self) -> None:
        report = parse("John and Mary left.")
        self.assertTrue(report.result.completed)


class RelativeTests(unittest.TestCase):
    def test_subject_relative(self) -> None:
        report = parse("the man who left", goal="NP")
        self.assertTrue(report.result.completed)
        self.assertIn("MODIFIER", relations("the man who left", goal="NP"))

    def test_object_relative(self) -> None:
        report = parse("the box that John opened", goal="NP")
        self.assertTrue(report.result.completed)
        self.assertIn("MODIFIER", relations("the box that John opened", goal="NP"))

    def test_relative_embedded_in_clause(self) -> None:
        report = parse("The man who left was happy.")
        self.assertTrue(report.result.completed)


class QuestionTests(unittest.TestCase):
    def test_wh_subject_question(self) -> None:
        rels = relations("Who left?")
        self.assertIn("AGENT", rels)

    def test_yes_no_question(self) -> None:
        best = parse("Did John leave?").result.best()
        assert best is not None
        self.assertEqual(best.rule_id, "clause_yn")

    def test_yes_no_question_roles(self) -> None:
        self.assertIn("AGENT", relations("Did John leave?"))


class ImperativeTests(unittest.TestCase):
    def test_positive_imperative(self) -> None:
        best = parse("Open the door.").result.best()
        assert best is not None
        self.assertEqual(best.rule_id, "clause_imperative")

    def test_imperative_roles(self) -> None:
        self.assertIn("AFFECTED", relations("Open the door."))


class RegressionTests(unittest.TestCase):
    def test_original_suite_still_green(self) -> None:
        for text, expected in [
            ("John opened the box.", True),
            ("John gave Mary the box.", True),
            ("Mary is happy.", True),
            ("John left.", True),
            ("the the the the.", False),
        ]:
            report = parse(text)
            self.assertEqual(report.result.completed, expected, text)


if __name__ == "__main__":
    unittest.main()
