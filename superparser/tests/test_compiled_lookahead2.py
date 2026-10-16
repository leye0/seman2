"""Compiled two-token lookahead is a bounded lexical witness, not a forest."""
from dataclasses import dataclass, field
import unittest

from seman_parser.reading_kernel_compiled import CompiledGrammar, IncrementalReader, ReadNode


@dataclass(frozen=True)
class Sym:
    category: str
    features: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    lhs: Sym
    rhs: tuple[Sym, ...]
    score: float = 1.0


@dataclass
class Grammar:
    rules: list[Rule]


@dataclass(frozen=True)
class Tok:
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
    score: float = 1


def grammar():
    signatures = [
        ("np_det_n", "NP", "DET", "N"),
        ("vp_passive", "VP", "AUX-BE", "V"),
        ("vp_transitive", "VP", "V", "NP"),
        ("vp_with_pp", "VP", "V", "NP", "PP"),
        ("clause_ellipsis", "CLAUSE", "NP", "AUX-BE"),
        ("clause_np_vp", "CLAUSE", "NP", "VP"),
        ("pp_prep_np", "PP", "PREP", "NP"),
        ("pp_adv_prep", "PP", "ADV", "PP"),
    ]
    return Grammar([Rule(name, Sym(lhs), tuple(Sym(v) for v in rhs))
                    for name, lhs, *rhs in signatures])


def reader(sequence, *, lookahead):
    tokens = []
    candidates = []
    position = 0
    for word, category in sequence:
        t = Tok(word, position, position + len(word))
        tokens.append(t)
        if category:
            candidates.append(Candidate(category, t.start, t.end, word.lower()))
        position += len(word) + 1
    compiled = CompiledGrammar(grammar())
    def combine(rule, children):
        return ReadNode(rule.lhs.category, children[0].start, children[-1].end,
                        rule=rule, children=tuple(children))
    return IncrementalReader(compiled, combine, tokens, candidates,
                             compiled_lookahead=lookahead)


class TestBoundedLookahead(unittest.TestCase):
    def test_two_token_passive_beats_ellipsis(self):
        series = [("The","DET"), ("door","N"), ("was","AUX-BE"), ("opened","V"), (".",None)]
        old = reader(series, lookahead=1)
        new = reader(series, lookahead=2)
        old.pos = new.pos = 2
        state_old = old.g.roots["CLAUSE"].edges["NP"]
        state_new = new.g.roots["CLAUSE"].edges["NP"]
        self.assertEqual(old._select(state_old), "AUX-BE")
        self.assertEqual(new._select(state_new), "VP")
        self.assertGreater(new.count["two_token_witnesses"], 0)

    def test_minimum_yield_guards_adv_pp_at_end(self):
        series = [("He","N"), ("watched","V"), ("the","DET"),
                  ("man","N"), ("quietly","ADV"), (".",None)]
        r = reader(series, lookahead=2)
        r.pos = 4
        self.assertEqual(r._min_yield["PP"], 2)
        self.assertFalse(r._min_yield_available("PP", 4))
        after_object = r.g.roots["VP"].edges["V"].edges["NP"]
        self.assertIsNone(r._select(after_object))

    def test_unknown_continuation_is_not_false_acceptance(self):
        series = [("He","N"), ("was","AUX-BE"), (".",None)]
        r = reader(series, lookahead=2)
        r.pos = 1
        self.assertFalse(r._two_token_witness("VP", 1))
        self.assertEqual(r.g.stats["grammar_rules"], 8)

    def test_opt_in_keeps_original_default(self):
        series = [("The","DET"), ("door","N"), ("was","AUX-BE"), ("opened","V")]
        r = reader(series, lookahead=1)
        self.assertEqual(r.compiled_lookahead, 1)
        self.assertEqual(r.count["two_token_probes"], 0)


if __name__ == "__main__":
    unittest.main()
