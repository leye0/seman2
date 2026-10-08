"""Unit tests for symbol interning and type DAG."""

from __future__ import annotations

import unittest

from seman_parser.symbols import SymbolTable
from seman_parser.types import TypeHierarchy, load_types


class SymbolTableTests(unittest.TestCase):
    def test_intern_is_stable(self) -> None:
        table = SymbolTable()
        a = table.intern("NP")
        b = table.intern("NP")
        self.assertEqual(a, b)
        self.assertEqual(table.resolve(a), "NP")
        self.assertEqual(len(table), 1)

    def test_distinct_symbols(self) -> None:
        table = SymbolTable()
        a = table.intern("NP")
        b = table.intern("VP")
        self.assertNotEqual(a, b)
        self.assertEqual(len(table), 2)

    def test_frozen_snapshot(self) -> None:
        table = SymbolTable()
        table.intern("X")
        frozen = table.freeze()
        self.assertEqual(frozen.intern("X"), 0)
        with self.assertRaises(KeyError):
            frozen.intern("Y")


class TypeHierarchyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.types = load_types(
            [
                {"name": "TOP"},
                {"name": "REFERENTIAL", "parents": ["TOP"]},
                {"name": "PHYSICAL-OBJECT", "parents": ["REFERENTIAL"]},
                {"name": "PERSON", "parents": ["PHYSICAL-OBJECT"]},
                {"name": "LOCATION", "parents": ["PHYSICAL-OBJECT"]},
                {"name": "EVENT", "parents": ["TOP"]},
            ]
        )

    def test_subtype_transitive(self) -> None:
        self.assertTrue(self.types.is_subtype_named("PERSON", "REFERENTIAL"))
        self.assertTrue(self.types.is_subtype_named("PERSON", "TOP"))
        self.assertTrue(self.types.is_subtype_named("PERSON", "PERSON"))
        self.assertFalse(self.types.is_subtype_named("PERSON", "EVENT"))
        self.assertFalse(self.types.is_subtype_named("REFERENTIAL", "PERSON"))

    def test_compatible(self) -> None:
        self.assertTrue(self.types.compatible(
            self.types.lookup("PERSON"), self.types.lookup("PHYSICAL-OBJECT")
        ))
        self.assertFalse(self.types.compatible(
            self.types.lookup("PERSON"), self.types.lookup("EVENT")
        ))

    def test_least_general_subsumer(self) -> None:
        lgs = self.types.least_general_subsumer(
            self.types.lookup("PERSON"), self.types.lookup("LOCATION")
        )
        self.assertIsNotNone(lgs)
        self.assertEqual(self.types.name_of(lgs), "PHYSICAL-OBJECT")

    def test_load_resolves_parents_late(self) -> None:
        hierarchy = load_types(
            [
                {"name": "CHILD", "parents": ["PARENT"]},
                {"name": "PARENT", "parents": ["TOP"]},
                {"name": "TOP"},
            ]
        )
        self.assertTrue(hierarchy.is_subtype_named("CHILD", "TOP"))

    def test_undefined_parent_raises(self) -> None:
        with self.assertRaises(ValueError):
            load_types([{"name": "ORPHAN", "parents": ["MISSING"]}])


if __name__ == "__main__":
    unittest.main()
