"""Stdlib tests for experimental bounded compact checkpoint replay."""
from dataclasses import dataclass, field
import unittest

from research.verbnet_lr.checkpoint_reader import BoundedCheckpointReader, LazyCheckpointReader
from seman_parser.reading_kernel_compiled import CompiledGrammar, IncrementalReader, ReadNode


@dataclass(frozen=True)
class RuleSymbol:
    category: str
    features: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    lhs: RuleSymbol
    rhs: tuple[RuleSymbol, ...]
    score: float = 1.0


@dataclass
class Grammar:
    rules: list[Rule]


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Candidate:
    category: str
    span_start: int
    span_end: int
    lemma: str
    features: dict
    score: float = 1.0


def make_reader(tokens_with_categories, budget=0, *, ellipsis=True, passive=True, lazy=False):
    spec = [
        ("np_det_n", "NP", "DET", "N"),
        ("clause_np_vp", "CLAUSE", "NP", "VP"),
    ]
    if ellipsis:
        spec.append(("clause_aux_ellipsis", "CLAUSE", "NP", "AUX-BE"))
    if passive:
        spec.append(("vp_passive", "VP", "AUX-BE", "V"))
    grammar = Grammar([Rule(name, RuleSymbol(lhs),
                            tuple(RuleSymbol(c) for c in cats))
                       for name, lhs, *cats in spec])
    tokens, lexical = [], []
    char = 0
    for word, cats in tokens_with_categories:
        token = Token(word, char, char + len(word))
        tokens.append(token)
        for category in cats:
            lexical.append(Candidate(category, token.start, token.end,
                                     word.lower(), {}))
        char += len(word) + 1

    def combine(rule, children):
        return ReadNode(rule.lhs.category, children[0].start, children[-1].end,
                        rule=rule, children=tuple(children))
    cls = (LazyCheckpointReader if lazy else BoundedCheckpointReader) if budget else IncrementalReader
    kw = {"replay_budget": budget} if budget else {}
    return cls(CompiledGrammar(grammar), combine, tokens, lexical, **kw)


class TestBoundedCheckpoints(unittest.TestCase):
    sentence = [
        ("The", ("DET",)), ("door", ("N",)),
        ("was", ("AUX-BE",)), ("opened", ("V",)), (".", ()),
    ]

    def test_recovers_auxiliary_ellipsis_without_a_forest(self):
        baseline = make_reader(self.sentence).read()
        self.assertFalse(baseline.complete)
        guided = make_reader(self.sentence, budget=3).read()
        self.assertTrue(guided.complete, (guided.reason, guided.events))
        self.assertEqual(guided.root.category, "CLAUSE")
        self.assertEqual(guided.root.children[1].rule.rule_id, "vp_passive")
        self.assertGreaterEqual(guided.counters["checkpoint_replays"], 1)
        self.assertLessEqual(guided.counters["checkpoint_replays"], 3)
        self.assertEqual(guided.counters["checkpoint_attempts"],
                         guided.counters["checkpoint_replays"] + 1)
        # Accounting includes discarded attempts, not only the final parse.
        self.assertGreater(guided.counters["consumptions"], 4)

    def test_zero_budget_matches_baseline(self):
        plain = make_reader(self.sentence).read()
        zero = make_reader(self.sentence, budget=0).read()
        self.assertEqual(plain.complete, zero.complete)
        self.assertEqual(plain.reason, zero.reason)
        self.assertEqual([(x.action, x.expected) for x in plain.events],
                         [(x.action, x.expected) for x in zero.events])

    def test_budget_never_accepts_unsupported_construction(self):
        no_passive = make_reader(self.sentence, budget=3, passive=False).read()
        self.assertFalse(no_passive.complete)
        self.assertLessEqual(no_passive.counters["checkpoint_attempts"], 4)

    def test_complete_sentence_uses_one_attempt(self):
        positive = [("The", ("DET",)), ("door", ("N",)),
                    ("was", ("AUX-BE",)), (".", ())]
        result = make_reader(positive, budget=3).read()
        self.assertTrue(result.complete)
        self.assertEqual(result.counters["checkpoint_attempts"], 1)

    def test_lazy_checkpoint_retains_positive_recovery(self):
        eager = make_reader(self.sentence, budget=3).read()
        lazy = make_reader(self.sentence, budget=3, lazy=True).read()
        self.assertEqual(eager.complete, lazy.complete)
        self.assertTrue(lazy.complete)
        self.assertEqual(eager.root.children[1].rule.rule_id,
                         lazy.root.children[1].rule.rule_id)
        self.assertLessEqual(lazy.counters["checkpoint_attempts"], 4)

    def test_lazy_success_has_no_alternative_probes(self):
        positive = [("The", ("DET",)), ("door", ("N",)),
                    ("was", ("AUX-BE",)), (".", ())]
        lazy = make_reader(positive, budget=3, lazy=True).read()
        baseline = make_reader(positive).read()
        self.assertTrue(lazy.complete)
        self.assertEqual(lazy.counters["checkpoint_attempts"], 1)
        # No possible structural alternative must be forced by the guide.
        self.assertEqual(lazy.root.rule.rule_id, baseline.root.rule.rule_id)

    def test_replay_budget_is_strict(self):
        zero = make_reader(self.sentence, budget=0)
        self.assertIsInstance(zero, IncrementalReader)
        one = make_reader(self.sentence, budget=1).read()
        self.assertLessEqual(one.counters["checkpoint_attempts"], 2)
        self.assertEqual(one.counters["checkpoint_budget"], 1)
        with self.assertRaises(ValueError):
            make_reader(self.sentence, budget=7)


if __name__ == "__main__":
    unittest.main()
