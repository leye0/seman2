"""Feature structure unification tests."""

from __future__ import annotations

import unittest

from seman_parser.features import (
    Atom,
    Disjunction,
    FeatureStructure,
    TOP,
    Variable,
    substitute_structure,
    unify,
    unify_values,
)


class UnificationTests(unittest.TestCase):
    def test_atom_unify(self) -> None:
        left = FeatureStructure.build({"number": "singular"})
        right = FeatureStructure.build({"number": "singular"})
        result = unify(left, right)
        self.assertIsNotNone(result)
        merged, _ = result
        self.assertEqual(merged.get("number"), Atom.of("singular"))

    def test_atom_conflict(self) -> None:
        left = FeatureStructure.build({"number": "singular"})
        right = FeatureStructure.build({"number": "plural"})
        self.assertIsNone(unify(left, right))

    def test_variable_binds(self) -> None:
        left = FeatureStructure.build({"number": "?n"})
        right = FeatureStructure.build({"number": "singular"})
        result = unify(left, right)
        self.assertIsNotNone(result)
        merged, env = result
        self.assertEqual(env["n"], Atom.of("singular"))
        self.assertEqual(merged.get("number"), Atom.of("singular"))

    def test_shared_variable_agreement(self) -> None:
        np = FeatureStructure.build({"number": "?n", "person": "3"})
        vp = FeatureStructure.build({"number": "?n", "person": "?p"})
        result = unify(np, vp)
        self.assertIsNotNone(result)
        merged, env = result
        self.assertEqual(env.get("p"), Atom.of("3"))
        concrete = FeatureStructure.build({"number": "singular", "person": "3"})
        result2 = unify(merged, concrete)
        self.assertIsNotNone(result2)

    def test_merge_compatible_features(self) -> None:
        left = FeatureStructure.build({"number": "singular"})
        right = FeatureStructure.build({"person": "3"})
        result = unify(left, right)
        self.assertIsNotNone(result)
        merged, _ = result
        self.assertEqual(merged.get("number"), Atom.of("singular"))
        self.assertEqual(merged.get("person"), Atom.of("3"))

    def test_nested_structures(self) -> None:
        left = FeatureStructure.build({"agr": {"number": "singular"}})
        right = FeatureStructure.build({"agr": {"person": "3"}})
        result = unify(left, right)
        self.assertIsNotNone(result)
        merged, _ = result
        agr = merged.get("agr")
        self.assertIsInstance(agr, FeatureStructure)
        assert isinstance(agr, FeatureStructure)
        self.assertEqual(agr.get("number"), Atom.of("singular"))

    def test_top_absorbs(self) -> None:
        left = FeatureStructure.build({"number": "singular"})
        right = FeatureStructure.empty()
        result = unify(left, right)
        self.assertIsNotNone(result)

    def test_disjunction_narrows(self) -> None:
        left = FeatureStructure.build({"number": ["singular", "plural"]})
        right = FeatureStructure.build({"number": "singular"})
        result = unify(left, right)
        self.assertIsNotNone(result)
        merged, _ = result
        self.assertEqual(merged.get("number"), Atom.of("singular"))

    def test_disjunction_conflict(self) -> None:
        self.assertIsNone(unify_values(Disjunction((Atom.of("a"), Atom.of("b"))), Atom.of("c"), {}))

    def test_non_destructive_failure(self) -> None:
        left = FeatureStructure.build({"x": "?a", "y": "1"})
        right = FeatureStructure.build({"x": "2", "y": "9"})
        env_before: dict = {}
        self.assertIsNone(unify(left, right, env_before))
        # No partial binding leak expected from a failed unify of atoms.
        self.assertNotIn("a", env_before)

    def test_substitute(self) -> None:
        structure = FeatureStructure.build({"number": "?n"})
        env = {"n": Atom.of("singular")}
        filled = substitute_structure(structure, env)
        self.assertEqual(filled.get("number"), Atom.of("singular"))

    def test_variable_identity(self) -> None:
        self.assertIsNotNone(unify_values(Variable("a"), Variable("a"), {}))


class TopSentinelTests(unittest.TestCase):
    def test_dump_top(self) -> None:
        from seman_parser.features import dump_value

        self.assertIsNone(dump_value(TOP))


if __name__ == "__main__":
    unittest.main()
