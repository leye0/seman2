"""A complete RHS prefix may either extend or reduce, not just change edge.

The tests use generic clause/VP/NP productions: the same words can legally
form nested or sibling constituents. No corpus sentence is hardcoded into the
research algorithm.
"""
from dataclasses import dataclass, field
import unittest

from seman_parser.reading_kernel_compiled import (
    CompiledGrammar, IncrementalReader, ReadNode,
)
from research.verbnet_lr.stack_reader import LocalCheckpointReader


@dataclass(frozen=True)
class Symbol:
    category: str
    features: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    lhs: Symbol
    rhs: tuple[Symbol, ...]
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
    features: dict = field(default_factory=dict)
    score: float = 1.0


def make_reader(reduce_checkpoints, budget=2):
    productions = [
        ("clause_svo", "CLAUSE", ("NP", "VP", "NP")),
        ("np_name", "NP", ("PROPER-NOUN",)),
        ("vp_v", "VP", ("V",)),
        ("vp_v_np", "VP", ("V", "NP")),
    ]
    grammar = Grammar([
        Rule(name, Symbol(lhs), tuple(Symbol(c) for c in rhs))
        for name, lhs, rhs in productions
    ])
    words = [("John", "PROPER-NOUN"), ("sees", "V"),
             ("Mary", "PROPER-NOUN"), (".", None)]
    tokens = []
    lex = []
    start = 0
    for word, category in words:
        token = Token(word, start, start + len(word))
        tokens.append(token)
        if category is not None:
            lex.append(Candidate(category, token.start, token.end,
                                 word.casefold()))
        start += len(word) + 1

    def combine(rule, children):
        return ReadNode(rule.lhs.category, children[0].start, children[-1].end,
                        rule=rule, children=tuple(children))

    kw = dict(replay_budget=budget, reduce_checkpoints=reduce_checkpoints)
    return LocalCheckpointReader(CompiledGrammar(grammar), combine,
                                 tokens, lex, **kw)


class ReduceVersusExtendTests(unittest.TestCase):
    def test_restore_completed_prefix_instead_of_greedy_extension(self):
        greedy = make_reader(False, budget=3).read()
        corrected = make_reader(True, budget=3).read()
        self.assertFalse(greedy.complete)
        self.assertTrue(corrected.complete, corrected.reason)
        self.assertEqual(corrected.root.rule.rule_id, "clause_svo")
        self.assertEqual(corrected.root.children[1].rule.rule_id, "vp_v")
        self.assertGreater(corrected.counters["checkpoint_forced_reductions"], 0)
        self.assertLessEqual(corrected.counters["checkpoint_restores_total"], 3)

    def test_zero_budget_does_not_change_initial_decision(self):
        ordinary = make_reader(False, budget=0).read()
        gated = make_reader(True, budget=0).read()
        self.assertEqual(ordinary.complete, gated.complete)
        self.assertEqual(ordinary.reason, gated.reason)
        self.assertEqual([(x.action, x.expected) for x in ordinary.events],
                         [(x.action, x.expected) for x in gated.events])

    def test_budget_one_can_choose_reduction(self):
        chosen = make_reader(True, budget=1).read()
        self.assertTrue(chosen.complete, chosen.reason)
        self.assertEqual(chosen.counters["checkpoint_restores_total"], 1)


if __name__ == "__main__":
    unittest.main()
