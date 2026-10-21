from __future__ import annotations

import json
from pathlib import Path

from seman_parser import Parser

from scripts.evaluate_reference_300 import (
    gold_relations,
    normalized_gold,
    normalized_parser,
    parser_relations,
    raw_gold,
    raw_parser,
)


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "seman2_reference_300_compact.json"
DATA = ROOT / "superparser" / "data"


def rows_by_id() -> dict[str, dict]:
    rows = json.loads(CORPUS.read_text(encoding="utf-8"))["sentences"]
    return {row["id"]: row for row in rows}


def test_reviewed_reference_has_300_stable_ids() -> None:
    rows = rows_by_id()
    assert len(rows) == 300
    assert set(rows) == {f"SEM-GOLD-{index:03d}" for index in range(1, 301)}


def test_normalization_does_not_change_raw_constituents() -> None:
    row = rows_by_id()["SEM-GOLD-148"]
    best = Parser.from_dir(DATA).parse(row["text"]).result.best()
    assert best is not None
    assert raw_gold(row["tree"]) != raw_parser(best)
    assert normalized_gold(row["tree"]) == normalized_parser(best)


def test_adverb_relation_is_measured_as_advmod() -> None:
    row = rows_by_id()["SEM-GOLD-051"]
    best = Parser.from_dir(DATA).parse(row["text"]).result.best()
    assert best is not None
    expected = gold_relations(row["tree"])
    actual = parser_relations(best)
    assert any(relation == "advmod" for relation, _head, _dep in expected)
    assert expected == actual


def test_flat_existential_is_a_documented_normalized_equivalent() -> None:
    row = rows_by_id()["SEM-GOLD-266"]
    best = Parser.from_dir(DATA).parse(row["text"]).result.best()
    assert best is not None
    assert normalized_gold(row["tree"]) == normalized_parser(best)


def load_tests(loader, tests, pattern):
    """Register module-level test_* functions with the unittest CI runner.

    unittest's default module loader only discovers TestCase subclasses;
    without this hook the grammar/reference checks were silently skipped.
    """
    import unittest
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            tests.addTest(unittest.FunctionTestCase(function, description=name))
    assert tests.countTestCases() >= 4, "Grammatical checks are not registered"
    return tests
