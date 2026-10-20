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
        semantic = report.interpret(best)
        relations = {edge.relation for edge in semantic.graph.relations}
        self.assertIn("AGENT", relations)
        # Object role name comes from the WordNet verb frame mapping
        # (THEME or AFFECTED depending on the frame).
        self.assertTrue(relations & {"AFFECTED", "THEME"}, relations)

    def test_ditransitive_clause(self) -> None:
        report = self.parser.parse("John gave Mary the box.")
        self.assertTrue(report.result.completed, report.result.stats)
        best = report.result.best()
        assert best is not None
        semantic = report.interpret(best)
        relations = {edge.relation for edge in semantic.graph.relations}
        self.assertIn("RECIPIENT", relations)
        self.assertIn("THEME", relations)

    def test_copula_adjective(self) -> None:
        report = self.parser.parse("Mary is happy.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_intransitive(self) -> None:
        report = self.parser.parse("John left.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_pied_piped_relative_pp_is_a_headed_np(self) -> None:
        """A preposition plus an oblique wh-word modifies a real NP head."""
        examples = (
            ("The shore on which Mary stood was quiet.",
             "np_relative_pp_restrictive"),
            ("The sea, on which the moon shone, was calm.",
             "np_relative_pp_comma_pair"),
            ("The question to which Mary replied was difficult.",
             "np_relative_pp_restrictive"),
            ("The students, of whose work Mary spoke, waited.",
             "np_relative_pp_comma_pair"),
        )
        def descendants(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in descendants(child)
            }
        for sentence, rule in examples:
            with self.subTest(sentence=sentence):
                parsed = self.parser.parse(sentence).result
                self.assertTrue(parsed.completed, parsed.stats)
                best = parsed.best()
                self.assertIsNotNone(best)
                self.assertIn(rule, descendants(best))

    def test_pied_piping_cannot_be_invented_from_any_wh_or_prep(self) -> None:
        """Reject missing relative pronouns and unlicensed possessive gaps."""
        def descendants(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in descendants(child)
            }
        for sentence in (
            "The shore on Mary stood was quiet.",
            "The shore on what Mary stood was quiet.",
            "The students, of whose Mary spoke, waited.",
            "The shore on which Mary.",
        ):
            with self.subTest(sentence=sentence):
                best = self.parser.parse(sentence).result.best()
                if best is not None:
                    self.assertFalse(
                        any(rule is not None and rule.startswith("np_relative_pp")
                            for rule in descendants(best)),
                        sentence,
                    )
        control = self.parser.parse("Mary stood on the shore.").result.best()
        self.assertIsNotNone(control)
        self.assertFalse(
            any(rule is not None and rule.startswith("np_relative_pp")
                for rule in descendants(control))
        )

    def test_predicative_adjectives_license_finite_content_clauses(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        cases = (
            ("Mary is sure John will return.", "adjp_clausal_bare"),
            ("Mary is sure that John will return.", "adjp_clausal_that"),
            ("Mary is afraid John will leave.", "adjp_clausal_bare"),
            ("Mary is glad that John will return.", "adjp_clausal_that"),
            ("Are you quite sure that you can go?", "adjp_degree_clausal"),
        )
        for text, required in cases:
            with self.subTest(text=text):
                parsed = self.parser.parse(text).result
                self.assertTrue(parsed.completed, parsed.stats)
                trees = [tree for tree in parsed.alternatives(limit=64)]
                self.assertTrue(
                    any(required in rule_ids(tree) for tree in trees),
                    (text, parsed.stats, [tree.rule_id for tree in trees]),
                )

    def test_clausal_adjective_valency_excludes_generic_adjectives(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        for text in (
            "Mary is tall John will return.",
            "Mary is blue that John returned.",
            "Are you quite tall that John returned?",
        ):
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                for tree in result.alternatives(limit=8):
                    self.assertNotIn("adjp_clausal_bare", rule_ids(tree))
                    self.assertNotIn("adjp_clausal_that", rule_ids(tree))
        # Existing ordinary adjectival predication remains available.
        basic = self.parser.parse("Mary is sure.").result
        self.assertTrue(basic.completed, basic.stats)

    def test_discourse_parentheticals_inside_finite_clauses(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        sentences = (
            ("Mary, however, opened the box.", "clause_subject_parenthetical_vp"),
            ("Mary, indeed, left.", "clause_subject_parenthetical_vp"),
            ("John tried, therefore, to open the box.",
             "vp_subject_control_parenthetical_inf"),
        )
        for text, expected in sentences:
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(
                    any(expected in rule_ids(tree)
                        for tree in result.alternatives(limit=24)),
                    (text, result.stats),
                )

    def test_discourse_parenthetical_cannot_swallow_plain_adverbs(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        for text in (
            "Mary, quickly, opened the box.",
            "Mary however opened the box.",
            "Mary, however opened the box.",
            "John kicked, therefore, to open the box.",
        ):
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                for tree in result.alternatives(limit=16):
                    rule_set = rule_ids(tree)
                    self.assertNotIn("clause_subject_parenthetical_vp", rule_set)
                    self.assertNotIn("vp_subject_control_parenthetical_inf", rule_set)

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


class ParserCacheTests(unittest.TestCase):
    def test_repeated_parse_reuses_complete_result(self) -> None:
        parser = Parser.from_dir(DATA, cache_size=4)
        first = parser.parse("John opened the box.")
        after_first = parser.cache_stats()
        second = parser.parse("John opened the box.")
        after_second = parser.cache_stats()

        self.assertIs(second.result, first.result)
        self.assertEqual(after_first["parse"]["misses"], 1)
        self.assertEqual(after_first["parse"]["size"], 1)
        self.assertEqual(after_second["parse"]["hits"], 1)

    def test_hierarchical_result_is_cached_too(self) -> None:
        parser = Parser.from_dir(DATA, cache_size=4)
        text = (
            "Mom worked during the day, Dad worked from home, "
            "and Eli learned to read."
        )
        first = parser.parse(text)
        self.assertEqual(first.result.stats.get("engine"), "vector-hierarchical-lazy-kbest")
        second = parser.parse(text)

        self.assertIs(second.result, first.result)
        self.assertEqual(parser.cache_stats()["parse"]["hits"], 1)


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
