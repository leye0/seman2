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
                reduce_follow_only=False, unrelated_root_edge=False,
                reachable_checkpoints_only=False,
                terminal_prefix_preference=False):
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
              reduce_follow_only=reduce_follow_only,
              reachable_checkpoints_only=reachable_checkpoints_only,
              terminal_prefix_preference=terminal_prefix_preference)
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
        result = make_reader(False, budget=1, unrelated_root_edge=True,
                             reachable_checkpoints_only=True).read()
        self.assertFalse(result.complete)
        self.assertGreater(result.counters["checkpoint_unavailable_skips"], 0)
        self.assertEqual(result.counters.get("checkpoint_saves", 0), 0)
        self.assertEqual(result.counters["checkpoint_restores_total"], 0)
        # Real reduce-vs-extend ambiguity in the same sentence must survive.
        recovered = make_reader(True, budget=3,
                                unrelated_root_edge=True,
                                reachable_checkpoints_only=True).read()
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

    def test_terminal_prefix_uses_existing_grammar_evidence(self):
        # Direct 3-token lexical evidence HAVE ADV V discriminates against
        # V NP whose NP can begin with ADV but cannot consume the next V.
        productions = [
            ("clause_np_vp", "CLAUSE", ("NP", "VP"), 1.0),
            ("np_name", "NP", ("PROPER-NOUN",), 1.0),
            ("np_adv_n", "NP", ("ADV", "N"), 1.0),
            ("vp_greedy_v_np", "VP", ("V", "NP"), 10.0),
            ("vp_perfect_adv", "VP", ("HAVE", "ADV", "V"), 1.0),
        ]
        grammar = Grammar([
            Rule(name, Symbol(lhs), tuple(Symbol(cat) for cat in rhs), score)
            for name, lhs, rhs, score in productions
        ])
        words = [
            ("Alice", ("PROPER-NOUN",)),
            ("had", ("V", "HAVE")),
            ("already", ("ADV",)),
            ("examined", ("V",)),
            (".", ()),
        ]
        tokens, lex, start = [], [], 0
        for word, categories in words:
            tokens.append(Token(word, start, start+len(word)))
            for cat in categories:
                lex.append(Candidate(cat, start, start+len(word), word.casefold()))
            start += len(word)+1
        def combine(rule, children):
            return ReadNode(rule.lhs.category, children[0].start,
                            children[-1].end, rule=rule, children=tuple(children))
        parser = LocalCheckpointReader(
            CompiledGrammar(grammar), combine, tokens, lex,
            replay_budget=0, terminal_prefix_preference=True)
        parsed = parser.read()
        self.assertTrue(parsed.complete, parsed.reason)
        self.assertEqual(parsed.root.children[1].rule.rule_id, "vp_perfect_adv")
        self.assertGreater(parsed.counters["terminal_prefix_guided_choices"], 0)

    def test_terminal_prefix_never_changes_default_choice(self):
        baseline = make_reader(True, budget=1).read()
        control = make_reader(True, budget=1, terminal_prefix_preference=False).read()
        self.assertEqual(baseline.complete, control.complete)
        self.assertEqual(baseline.reason, control.reason)


    def test_return_instead_of_greedy_extension_is_grammar_licensed(self):
        # NP -> NP CONJ NP competes with the parent's CLAUSE -> NP CONJ VP.
        # NP can BEGIN with V N but cannot finish on the final bare V.
        # The abandoned extension must not swallow the parent's CONJ.
        grammar = Grammar([
            Rule(name, Symbol(lhs), tuple(Symbol(cat) for cat in rhs))
            for name, lhs, rhs in (
                ("clause_np_conj_vp", "CLAUSE", ("NP", "CONJ", "VP")),
                ("np_n", "NP", ("N",)),
                ("np_verb_noun", "NP", ("V", "N")),
                ("np_coord", "NP", ("NP", "CONJ", "NP")),
                ("vp_v", "VP", ("V",)),
            )
        ])
        words = [("Cats", "N"), ("and", "CONJ"), ("run", "V"), (".", None)]
        tokens, candidates, offset = [], [], 0
        for word, category in words:
            tokens.append(Token(word, offset, offset + len(word)))
            if category:
                candidates.append(Candidate(
                    category, offset, offset + len(word), word.casefold()))
            offset += len(word) + 1
        def combine(rule, children):
            return ReadNode(rule.lhs.category, children[0].start,
                            children[-1].end, rule=rule, children=tuple(children))
        compiled = CompiledGrammar(grammar)
        baseline = LocalCheckpointReader(
            compiled, combine, tokens, candidates,
            replay_budget=1).read()
        guided = LocalCheckpointReader(
            compiled, combine, tokens, candidates,
            replay_budget=1, extension_checkpoints=True).read()
        self.assertFalse(baseline.complete)
        self.assertTrue(guided.complete, guided.reason)
        self.assertEqual(guided.root.rule.rule_id, "clause_np_conj_vp")
        self.assertEqual(guided.counters["checkpoint_restores_total"], 1)
        self.assertGreater(guided.counters["checkpoint_forced_extension_finishes"], 0)

    def test_budget_one_can_choose_reduction(self):
        chosen = make_reader(True, budget=1).read()
        self.assertTrue(chosen.complete, chosen.reason)
        self.assertEqual(chosen.counters["checkpoint_restores_total"], 1)


if __name__ == "__main__":
    unittest.main()
