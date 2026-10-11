"""Acceptance tests for the strict syntax/semantics boundary."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from seman_parser import Parser
from seman_parser.features import FeatureStructure
from seman_parser.lexicon import LexicalEntry, LexicalSense, Lexicon
from seman_parser.segmentation import (
    LexicalCandidate,
    LexicalInterpretation,
    deduplicate_syntactic_candidates,
    build_lattice,
)


DATA = Path(__file__).resolve().parents[1] / "data"


class SyntaxIsolationTests(unittest.TestCase):
    def test_parse_does_not_load_semantic_modules(self) -> None:
        code = f"""
import sys
from pathlib import Path
from seman_parser import Parser
p = Parser.from_dir(Path({str(DATA)!r}), cache_size=0)
r = p.parse('The dax glorped the blicket.')
assert r.result.completed
assert r.result.best().semantic is None
assert 'seman_parser.semantics' not in sys.modules
assert 'seman_parser.semantic_rules' not in sys.modules
assert 'seman_parser.types' not in sys.modules
"""
        completed = subprocess.run(
            [sys.executable, "-c", code],
            env={"PYTHONPATH": str(DATA.parent)},
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_semantics_are_explicit_and_reproducible(self) -> None:
        report = Parser.from_dir(DATA, cache_size=0).parse("John gave Mary the box.")
        best = report.result.best()
        assert best is not None
        self.assertIsNone(best.semantic)
        relations = {edge.relation for edge in report.interpret(best).graph.relations}
        self.assertTrue({"AGENT", "RECIPIENT", "THEME"} <= relations)

    def test_public_parse_serialization_is_syntax_only(self) -> None:
        report = Parser.from_dir(DATA, cache_size=0).parse("John left.")
        payload = report.as_dict()
        self.assertNotIn("semantic", payload)
        self.assertIn("lattice", payload)
        self.assertIn("syntax", payload["best"])
        self.assertEqual(payload["stats"]["semantic_graphs"], 0)

    def test_pp_attachment_alternatives_survive(self) -> None:
        result = Parser.from_dir(DATA, cache_size=0).parse(
            "I saw the man with the telescope."
        ).result
        alternatives = result.alternatives(limit=4)
        self.assertGreaterEqual(len(alternatives), 2)
        self.assertGreaterEqual(len({item.signature() for item in alternatives}), 2)


class LexicalDeduplicationTests(unittest.TestCase):
    def test_changing_semantic_type_does_not_change_syntax(self) -> None:
        features = FeatureStructure.build({"number": "singular"})
        def lattice(type_name: str):
            sense = LexicalSense("bank-1", "N", features, semantic_type=type_name)
            entry = LexicalEntry("bank", ("bank",), (sense,))
            return build_lattice("bank", Lexicon((entry,))).as_dict()
        self.assertEqual(lattice("INSTITUTION"), lattice("LOCATION"))

    def test_semantic_senses_share_one_syntax_candidate(self) -> None:
        common = dict(
            span_start=0, span_end=4, surface="bank", lemma="bank",
            category="N", features=FeatureStructure.build({"number": "singular"}),
            normalized="bank", source="wordnet", score=1.0,
        )
        rows = [
            LexicalCandidate(
                **common,
                interpretations=(LexicalInterpretation("bank-1", "bank"),),
            ),
            LexicalCandidate(
                **common,
                interpretations=(LexicalInterpretation("bank-2", "bank"),),
            ),
        ]
        deduplicated = deduplicate_syntactic_candidates(rows)
        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(set(deduplicated[0].sense_ids), {"bank-1", "bank-2"})

    def test_distinct_grammar_constraints_are_not_merged(self) -> None:
        base = dict(
            span_start=0, span_end=4, surface="test", lemma="test",
            category="V", features=FeatureStructure.build({"vform": "finite"}),
            normalized="test", source="fixture", score=1.0,
        )
        rows = [
            LexicalCandidate(**base, syntactic_constraints=(None, (("subject",),))),
            LexicalCandidate(**base, syntactic_constraints=(None, (("subject", "object"),))),
        ]
        self.assertEqual(len(deduplicate_syntactic_candidates(rows)), 2)


if __name__ == "__main__":
    unittest.main()
