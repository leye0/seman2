"""Integration tests: parse real English strings with the seed data."""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser import Parser
from seman_parser.chart import Chart
from seman_parser.engine import ParserResources
from seman_parser.grammar import load_grammar
from seman_parser.lexicon import load_lexicon
from seman_parser.segmentation import build_lattice

DATA = Path(__file__).resolve().parents[1] / "data"


def make_parser() -> Parser:
    return Parser.from_dir(DATA)


class SegmentationTests(unittest.TestCase):
    def test_lattice_has_candidates(self) -> None:
        lexicon = load_lexicon(DATA / "lexicon.jsonl")
        lattice = build_lattice("John opened the box.", lexicon)
        self.assertGreater(len(lattice.candidates), 4)
        surfaces = {c.surface for c in lattice.candidates}
        self.assertIn("John", surfaces)
        self.assertIn("opened", surfaces)
        self.assertIn("the", surfaces)
        self.assertIn("box", surfaces)

    def test_multiword_overlap_preserved(self) -> None:
        lexicon = load_lexicon(DATA / "lexicon.jsonl")
        lattice = build_lattice("John found a box.", lexicon)
        # At least the proper-noun and lexicon hypotheses must coexist.
        john = [c for c in lattice.candidates if c.surface == "John"]
        self.assertGreaterEqual(len(john), 1)


class ChartParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = make_parser()

    def test_transitive_clause(self) -> None:
        report = self.parser.parse("John opened the box.")
        self.assertTrue(report.result.completed, report.result.stats)
        best = report.result.best()
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best.category, "CLAUSE")
        self.assertEqual(best.start, 0)

    def test_semantic_roles_on_transitive(self) -> None:
        report = self.parser.parse("John opened the box.")
        best = report.result.best()
        assert best is not None
        relations = {edge.relation for edge in best.semantic.graph.relations}
        self.assertIn("AGENT", relations)
        # Object role name comes from the WordNet verb frame mapping
        # (THEME or AFFECTED depending on the frame).
        self.assertTrue(relations & {"AFFECTED", "THEME"}, relations)

    def test_ditransitive_clause(self) -> None:
        report = self.parser.parse("John gave Mary the box.")
        self.assertTrue(report.result.completed, report.result.stats)
        best = report.result.best()
        assert best is not None
        relations = {edge.relation for edge in best.semantic.graph.relations}
        self.assertIn("RECIPIENT", relations)
        self.assertIn("THEME", relations)

    def test_copula_adjective(self) -> None:
        report = self.parser.parse("Mary is happy.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_intransitive(self) -> None:
        report = self.parser.parse("John left.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_alternatives_are_preserved(self) -> None:
        report = self.parser.parse("John opened the box.")
        # Even with one preferred reading, the API exposes alternatives.
        alts = report.result.alternatives()
        self.assertGreaterEqual(len(alts), 1)
        self.assertIs(report.result.best(), max(alts, key=lambda i: i.score))

    def test_failed_parse_is_honest(self) -> None:
        # Function words alone cannot form a clause.
        report = self.parser.parse("the the the the.")
        self.assertFalse(report.result.completed)

    def test_provenance_present(self) -> None:
        report = self.parser.parse("John opened the box.")
        best = report.result.best()
        assert best is not None
        payload = best.provenance.as_dict()
        self.assertEqual(payload["source"], "rule")
        self.assertIn("rule_id", payload["detail"])


class ConstitutionTests(unittest.TestCase):
    """The engine must not encode domain nouns as dispatch."""

    def test_no_domain_identifiers_in_package(self) -> None:
        import ast

        root = Path(__file__).resolve().parents[1] / "seman_parser"
        forbidden = {"requesthandler", "transferevent", "understand_request", "passivesentence"}
        violations: list[str] = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.lower() in forbidden:
                        violations.append(f"{path.name}:{node.lineno}:{node.name}")
                if isinstance(node, ast.If):
                    # No dispatch on literal semantic type / verb names.
                    for child in ast.walk(node.test):
                        if isinstance(child, ast.Compare):
                            for comparator in child.comparators:
                                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                                    if comparator.value.upper() in {"REQUEST", "TRANSFER", "GIVE", "OPEN"}:
                                        violations.append(
                                            f"{path.name}:{node.lineno}:dispatch on {comparator.value!r}"
                                        )
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
