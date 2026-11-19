import unittest

from scripts.audit_equivalent_rules import equivalent_groups, inventory
from scripts.compare_novel1000_semantic_replay import graph_additions, assert_reviewed
from seman_parser.grammar import Grammar, parse_rule
from seman_parser.semantic_rules import parse_action


class GrammarGeneralizationContractTest(unittest.TestCase):
    def test_endpoint_lists_lower_to_existing_ordered_links(self):
        choices = [{"relation": None, "child_rules": {"1": ["miss"]}}]
        args = {"compose": {"links": [
            {"relation": "SUBJECT", "sources": [{"child": 1, "handle": "head"}, "second"],
             "target": "subject", "choices": choices},
            {"relation": "MEMBER", "source": "group", "targets": ["one", "two"]},
        ]}}
        self.assertEqual(parse_action(args).args["links"], [
            {"relation": "SUBJECT", "source": {"child": 1, "handle": "head"},
             "target": "subject", "choices": choices},
            {"relation": "SUBJECT", "source": "second", "target": "subject", "choices": choices},
            {"relation": "MEMBER", "source": "group", "target": "one"},
            {"relation": "MEMBER", "source": "group", "target": "two"},
        ])
        self.assertIn("sources", args["compose"]["links"][0])

    def test_no_implicit_cartesian_product_or_mixed_endpoint(self):
        invalid = (
            {"sources": ["e"], "targets": ["x"]},
            {"sources": ["e"], "source": "event", "target": "x"},
            {"sources": "head", "target": "x"},
            {"sources": [], "target": "x"},
            {"targets": ["x"]},
        )
        for link in invalid:
            with self.subTest(link=link), self.assertRaises(ValueError):
                parse_action({"compose": {"links": [link]}})

    def test_duplicate_detector_preserves_requirements_aliases_and_scope(self):
        def rule(name, var, *, scope=None, requires=(), alias="subject", score=1):
            return parse_rule({"id": name, "score": score,
                               "provenance": {"source_plan": scope} if scope else {},
                               "lhs": {"category": "CLAUSE", "features": {"number": var}},
                               "rhs": [{"category": "NP", "features": {"number": var},
                                        "exports": {"referent": alias}, "requires": list(requires)},
                                       {"category": "VP", "features": {"number": var}}]})

        signature = parse_action({"compose": {"links": [
            {"relation": "SUBJECT", "source": "event", "target": "subject"},
        ]}})
        grammar = Grammar([
            rule("first", "?agreement"), rule("higher", "?p", score=2),
            rule("other-graph", "?p"), rule("scoped", "?p", scope="different_source"),
            rule("required", "?p", requires=("number",)), rule("alias", "?p", alias="object"),
        ])
        self.assertEqual(equivalent_groups(grammar, {"other-graph": (signature,)}),
                         [{"keep": "higher", "score": 2, "remove": ["first"]}])

    def test_production_grammars_have_no_exact_duplicate_candidates(self):
        self.assertEqual(inventory(), {"grammar": [], "dialogue_grammar": [],
                                       "dialogue_structural_grammar": []})

    def test_replay_delta_only_accepts_reviewed_edges_and_stable_nodes(self):
        def graph(a, b, additions=()):
            return {"graph": {"nodes": [{"id": a, "span": [0, 1]}, {"id": b, "span": [2, 3]}],
                              "relations": [{"relation": role, "source": a, "target": b,
                                             "attributes": {}}
                                            for role in ("OLD", *additions)]},
                    "handles": {"subject": b}}

        before, after = graph("a", "b"), graph("c", "d", ("SUBJECT",))
        expected = [{"relation": "SUBJECT", "source_span": [0, 1], "target_span": [2, 3]}]
        self.assertEqual(graph_additions(before, after), expected)
        with self.assertRaisesRegex(ValueError, "removed"):
            graph_additions(after, before)
        after["handles"]["subject"] = "c"
        with self.assertRaisesRegex(ValueError, "handles"):
            graph_additions(before, after)
        observation = {"schema": "example", "manifest_sha256": "fixed", "compared": {},
                       "cases": {"one": {"source_sha256": "source", "selected_graph_sha256": "graph",
                                         "additions": expected}}}
        assert_reviewed(observation, observation)
        with self.assertRaisesRegex(ValueError, "one"):
            assert_reviewed(observation, {**observation, "cases": {}})
