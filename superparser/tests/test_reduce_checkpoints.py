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


def make_reader(reduce_checkpoints, budget=2, *, parent_follow_reduce=False,
                reduce_follow_only=False, unrelated_root_edge=False):
    productions = [
        ("clause_svo", "CLAUSE", ("NP", "VP", "NP")),
        ("np_name", "NP", ("PROPER-NOUN",)),
        ("vp_v", "VP", ("V",)),
        ("vp_v_np", "VP", ("V", "NP")),
    ]
    if unrelated_root_edge:
        # An alternative grammatical RHS in the trie is *not* necessarily
        # available to the observed first token.
        productions.append(("clause_v_np", "CLAUSE", ("V", "NP")))
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

    kw = dict(replay_budget=budget, reduce_checkpoints=reduce_checkpoints,
              parent_follow_reduce=parent_follow_reduce,
              reduce_follow_only=reduce_follow_only)
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

    def test_parent_follow_witness_reduces_without_backtracking(self):
        parsed = make_reader(True, budget=1, parent_follow_reduce=True).read()
        self.assertTrue(parsed.complete, parsed.reason)
        self.assertEqual(parsed.root.children[1].rule.rule_id, "vp_v")
        self.assertEqual(parsed.counters["checkpoint_restores_total"], 0)
        self.assertGreater(parsed.counters["parent_follow_witness_reductions"], 0)

    def test_deferred_reduce_when_parent_follow_is_proven(self):
        parsed = make_reader(True, budget=1, reduce_follow_only=True).read()
        self.assertTrue(parsed.complete, parsed.reason)
        self.assertEqual(parsed.root.children[1].rule.rule_id, "vp_v")
        self.assertEqual(parsed.counters["checkpoint_restores_total"], 1)

    def test_do_not_save_lexically_unreachable_checkpoints(self):
        # CLAUSE starts with either NP or V in this grammar; the actual
        # first word has only a PROPER-NOUN lexical candidate (hence NP).
        # Recording an alternative V at that point cannot help recovery.
        result = make_reader(False, budget=1, unrelated_root_edge=True).read()
        self.assertFalse(result.complete)
        self.assertGreater(result.counters["checkpoint_unavailable_skips"], 0)
        self.assertEqual(result.counters["checkpoint_saves"], 0)
        self.assertEqual(result.counters["checkpoint_restores_total"], 0)
        # Real reduce-vs-extend ambiguity in the same sentence must survive.
        recovered = make_reader(True, budget=3,
                                unrelated_root_edge=True).read()
        self.assertTrue(recovered.complete, recovered.reason)
        self.assertEqual(recovered.root.children[1].rule.rule_id, "vp_v")
        self.assertGreater(recovered.counters["checkpoint_forced_reductions"], 0)

    def test_checkpoint_peak_is_sentence_local(self):
        reader = make_reader(True, budget=3)
        self.assertTrue(reader.read().complete)
        self.assertGreater(reader._peak_checkpoints, 0)
        reader.replay_budget = 0
        second = reader.read()
        self.assertEqual(second.counters["checkpoint_peak_saved"], 0)

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
