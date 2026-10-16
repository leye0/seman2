"""Small exhaustive fixtures for the research-only feature witness tool."""
from dataclasses import dataclass
import unittest

from research.verbnet_lr.feature_witness import seek_feature_witness
from research.verbnet_lr.upper_bound import recognize_upper_bound
from seman_parser.features import FeatureStructure
from seman_parser.grammar import GrammarRule, RuleSymbol
from seman_parser.segmentation import LexicalCandidate


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int


@dataclass
class Lattice:
    tokens: tuple
    candidates: tuple


@dataclass
class Grammar:
    rules: tuple


def symbol(name, **features):
    return RuleSymbol(name, FeatureStructure.build(features))


def make_rule(name, lhs, *rhs):
    return GrammarRule(name, tuple(rhs), lhs, score=1.0)


def lex(text, category, position, **features):
    return LexicalCandidate(position, position + len(text), text, text.lower(),
                            category, FeatureStructure.build(features))


def fixture(gram, definitions):
    at = 0
    tokens, candidates = [], []
    for word, cases in definitions:
        tokens.append(Token(word, at, at + len(word)))
        for cat, feats in cases:
            candidates.append(lex(word, cat, at, **feats))
        at += len(word) + 1
    return gram, Lattice(tuple(tokens), tuple(candidates))


class FeatureWitnessTests(unittest.TestCase):
    def test_earley_span_capture_is_opt_in(self):
        rules = [("CLAUSE", ("V",))]
        simple = recognize_upper_bound(rules, [{"V"}])
        verbose = recognize_upper_bound(rules, [{"V"}], collect_spans=True)
        self.assertEqual(simple["status"], "ACCEPTED")
        self.assertNotIn("spans", simple)
        self.assertIn(("CLAUSE", 0, 1), verbose["spans"])
        self.assertNotIn("spans", recognize_upper_bound(
            rules, [{"N"}], collect_spans=False))

    def test_feature_unification_accepts_matching_agreement(self):
        grammar = Grammar((
            make_rule("clause_np_v", symbol("CLAUSE"), symbol("NP"), symbol("V")),
            make_rule("np_det_n", symbol("NP", number="?n"),
                      symbol("DET", number="?n"), symbol("N", number="?n")),
        ))
        gram, lat = fixture(grammar, [
            ("this", [("DET", {"number": "singular"})]),
            ("dog", [("N", {"number": "singular"})]),
            ("runs", [("V", {})]),
        ])
        outcome = seek_feature_witness(gram, lat)
        self.assertEqual(outcome["status"], "FOUND", outcome)
        self.assertEqual(outcome["witness"]["children"][0]["rule"], "np_det_n")

    def test_missing_feature_proof_is_not_auto_accepted(self):
        grammar = Grammar((
            make_rule("clause_np_v", symbol("CLAUSE"), symbol("NP"), symbol("V")),
            make_rule("np_det_n", symbol("NP", number="?n"),
                      symbol("DET", number="?n"), symbol("N", number="?n")),
        ))
        gram, lat = fixture(grammar, [
            ("these", [("DET", {"number": "plural"})]),
            ("dog", [("N", {"number": "singular"})]),
            ("runs", [("V", {})]),
        ])
        outcome = seek_feature_witness(gram, lat)
        self.assertEqual(outcome["category_status"], "ACCEPTED")
        self.assertEqual(outcome["status"], "UNKNOWN", outcome)
        self.assertIsNone(outcome["witness"])
        self.assertGreater(outcome["unifications"], 0)

    def test_lexical_ambiguity_is_resolved_by_features(self):
        grammar = Grammar((
            make_rule("clause_v", symbol("CLAUSE"), symbol("V", vform="base")),
        ))
        gram, lat = fixture(grammar, [
            ("run", [("V", {"vform": "finite"}), ("V", {"vform": "base"})]),
        ])
        answer = seek_feature_witness(gram, lat)
        self.assertEqual(answer["status"], "FOUND", answer)

    def test_budget_is_unknown_not_grammatical_rejection(self):
        grammar = Grammar((make_rule("clause_v", symbol("CLAUSE"),
                                    symbol("V")),))
        gram, lat = fixture(grammar, [("run", [("V", {})])])
        answer = seek_feature_witness(gram, lat, max_expansions=1)
        self.assertEqual(answer["status"], "UNKNOWN", answer)
        self.assertIn("expansion_budget", answer["reason"])

    def test_category_gap_is_not_a_false_witness(self):
        grammar = Grammar((make_rule("clause_v", symbol("CLAUSE"),
                                    symbol("V")),))
        gram, lat = fixture(grammar, [("dog", [("N", {})])])
        result = seek_feature_witness(gram, lat)
        self.assertEqual(result["status"], "CATEGORY_REJECTED")


if __name__ == "__main__":
    unittest.main()
