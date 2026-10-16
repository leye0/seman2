"""Fast integration tests: recovery -> sparse preferences -> no grammar bypass."""
import unittest
from dataclasses import dataclass, field

from research.verbnet_lr.sparse_ambiguity import Conflict, SparseAmbiguityMemory
from research.verbnet_lr.sparse_guided_reader import SparseGuidedCheckpointReader
from seman_parser.reading_kernel_compiled import CompiledGrammar, ReadNode


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


def reader(memory, *, parent_needs_np=True, i=0, **kwargs):
    # VP V and VP V NP are both licensed; the owner of Mary is ambiguous.
    productions = [
        ("clause", "CLAUSE", ("NP", "VP", "NP") if parent_needs_np
         else ("NP", "VP")),
        ("np", "NP", ("PROPER-NOUN",)),
        ("vp_short", "VP", ("V",)),
        ("vp_long", "VP", ("V", "NP")),
    ]
    grammar = Grammar([
        Rule(name, Symbol(lhs), tuple(Symbol(cat) for cat in rhs))
        for name, lhs, rhs in productions
    ])
    words = [(f"Subject{i}", "PROPER-NOUN"),
             ("sees", "V"), (f"Object{i}", "PROPER-NOUN")]
    tokens, lex, start = [], [], 0
    for word, category in words:
        tokens.append(Token(word, start, start + len(word)))
        lex.append(Candidate(category, start, start+len(word),
                             word.casefold()))
        start += len(word) + 1

    def combine(rule, children):
        return ReadNode(rule.lhs.category, children[0].start,
                        children[-1].end, rule=rule, children=tuple(children))

    return SparseGuidedCheckpointReader(
        CompiledGrammar(grammar), combine, tokens, lex,
        sparse_memory=memory, replay_budget=2, reduce_checkpoints=True,
        **kwargs)


class SparseRecoveryTests(unittest.TestCase):
    def test_retry_learns_tiny_decision_then_eliminates_restore(self):
        memory = SparseAmbiguityMemory()
        for i in range(12):
            result = reader(memory, i=i, learn_recoveries=True,
                            use_recovery_hints=True).read()
            self.assertTrue(result.complete, result.reason)
            self.assertEqual(result.root.rule.rule_id, "clause")
            self.assertEqual(result.root.children[1].rule.rule_id, "vp_short")
            self.assertGreater(result.counters["checkpoint_restores_total"], 0)
        self.assertEqual(memory.summary()["recovery_observations"], 12)
        self.assertEqual(memory.summary()["verified_observations"], 0)
        guided = reader(memory, i=24, learn_recoveries=True,
                        use_recovery_hints=True).read()
        self.assertTrue(guided.complete, guided.reason)
        self.assertEqual(guided.counters["checkpoint_restores_total"], 0)
        self.assertGreater(guided.counters["sparse_hint_applied"], 0)

    def test_recovery_is_not_independent_gold_or_parser_truth(self):
        memory = SparseAmbiguityMemory()
        site = Conflict("reduce_vs_extend", "CLAUSE", "VP",
                        ("$REDUCE", "NP"),
                        next_categories=("PROPER-NOUN",))
        for i in range(12):
            self.assertTrue(memory.note_recovery(
                site, failed="NP", chosen="$REDUCE", observation_id=i))
        self.assertIsNone(memory.hint(site))
        self.assertEqual(memory.recovery_hint(site), "$REDUCE")
        self.assertFalse(memory.note_recovery(
            site, failed="NP", chosen="$REDUCE", observation_id=0))
        self.assertFalse(memory.observe(
            site, "$REDUCE", source="parser_completion"))
        for _ in range(8):
            memory.observe(site, "NP", source="gold")
        self.assertEqual(memory.hint(site), "NP")

    def test_bad_recovery_preference_can_be_undone(self):
        memory = SparseAmbiguityMemory()
        probe = reader(memory, parent_needs_np=False, i=0,
                       capture_conflicts=True)
        # Run once to obtain the actual state-specific structural site.
        ordinary = probe.read()
        self.assertTrue(ordinary.complete, ordinary.reason)
        sites = [site for site, _ in probe.conflict_trace
                 if "$REDUCE" in site.alternatives and "NP" in site.alternatives]
        self.assertTrue(sites)
        for i in range(12):
            memory.note_recovery(sites[-1], failed="NP", chosen="$REDUCE",
                                 observation_id=i)
        corrected = reader(memory, parent_needs_np=False, i=50,
                           use_recovery_hints=True).read()
        self.assertTrue(corrected.complete, corrected.reason)
        self.assertEqual(corrected.root.children[1].rule.rule_id, "vp_long")
        self.assertGreater(corrected.counters["checkpoint_restores_total"], 0)

    def test_learned_finish_keeps_one_reversible_extension_checkpoint(self):
        productions = [
            ("clause", "CLAUSE", ("NP", "V")),
            ("np_n", "NP", ("N",)),
            ("np_pp", "NP", ("NP", "PP")),
            ("pp", "PP", ("PREP", "NP")),
        ]
        grammar = Grammar([
            Rule(name, Symbol(lhs), tuple(Symbol(cat) for cat in rhs))
            for name, lhs, rhs in productions
        ])
        compiled = CompiledGrammar(grammar)
        tokens, candidates, start = [], [], 0
        for word, category in [
                ("dogs", "N"), ("in", "PREP"), ("yard", "N"), ("run", "V")]:
            tokens.append(Token(word, start, start + len(word)))
            candidates.append(Candidate(category, start, start + len(word),
                                        word.casefold()))
            start += len(word) + 1

        def combine(rule, children):
            return ReadNode(rule.lhs.category, children[0].start,
                            children[-1].end, rule=rule, children=tuple(children))

        memory = SparseAmbiguityMemory()
        def create(*, capture=False):
            return SparseGuidedCheckpointReader(
                compiled, combine, tokens, candidates,
                sparse_memory=memory, replay_budget=2,
                extension_checkpoints=True, capture_conflicts=capture)

        probe = create(capture=True)
        expected = probe.read()
        self.assertTrue(expected.complete, expected.reason)
        sites = [site for site, chosen in probe.conflict_trace
                 if chosen == "$EXTEND"
                 and site.alternatives == ("$EXTEND", "$FINISH")]
        self.assertTrue(sites)
        for _ in range(8):
            memory.observe(sites[0], "$FINISH", source="gold")
        guided = create()
        guided.use_recovery_hints = True
        outcome = guided.read()
        self.assertTrue(outcome.complete, outcome.reason)
        self.assertGreater(outcome.counters["sparse_finish_hints"], 0)
        self.assertEqual(outcome.counters["checkpoint_extension_saves"], 1)
        self.assertEqual(outcome.counters["checkpoint_restores_total"], 1)
        self.assertEqual(outcome.root.rule.rule_id, "clause")

    def test_bounded_memory_and_no_false_training_on_failures(self):
        memory = SparseAmbiguityMemory(max_contexts=2, max_votes=12)
        site = Conflict("c", "CLAUSE", "VP", ("A", "B"))
        for i in range(30):
            memory.note_recovery(site, failed="A", chosen="B",
                                 observation_id=i)
        self.assertLessEqual(memory.summary()["recovery_votes"], 12)
        for name in ("X", "Y"):
            different = Conflict(name, "CLAUSE", "VP", ("A", "B"))
            memory.note_recovery(different, failed="A", chosen="B")
        self.assertEqual(memory.summary()["recovery_contexts"], 2)
        self.assertEqual(memory.summary()["recovery_evictions"], 1)


if __name__ == "__main__":
    unittest.main()
