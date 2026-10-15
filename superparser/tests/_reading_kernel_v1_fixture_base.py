"""Isolated behavioural tests. These do NOT substitute for real WordNet integration."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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
    score: float = 1


@dataclass
class Grammar:
    rules: list[Rule]


@dataclass(frozen=True)
class Lex:
    category: str
    span_start: int
    span_end: int
    surface: str
    lemma: str
    features: dict
    score: float = 0


@dataclass(frozen=True)
class Tok:
    text: str
    start: int
    end: int


def rule(name, lhs, *rhs, subcat=None):
    children = [Sym(x) for x in rhs]
    if subcat:
        children[0] = Sym(rhs[0], {'subcat': subcat})
    return Rule(name, Sym(lhs), tuple(children))


def fixture_grammar():
    # Structural extracts of the real Seman2 grammar. No per-sentence pattern.
    names = [
        ('np_det_n', 'NP', ('DET', 'N'), None),
        ('np_proper', 'NP', ('PROPER-NOUN',), None),
        ('np_bare', 'NP', ('N',), None),
        ('pp_prep_np', 'PP', ('PREP', 'NP'), None),
        ('pp_adv_prep', 'PP', ('ADV', 'PP'), None),
        ('vp_transitive', 'VP', ('V', 'NP'), 'transitive'),
        ('vp_intransitive', 'VP', ('V',), 'intransitive'),
        ('clause_np_vp', 'CLAUSE', ('NP', 'VP'), None),
        ('clause_yn_cop_pp', 'CLAUSE', ('COPULA', 'NP', 'PP', 'QMARK'), None),
        ('np_relative_obj', 'NP', ('NP', 'WH-OBJ'), None),
        ('wh_bare', 'WH-OBJ', ('NP', 'VP-GAP'), None),
        ('vp_gap_transitive', 'VP-GAP', ('V',), 'transitive'),
        ('vp_gap_with_adv', 'VP-GAP', ('ADV', 'V'), None),
        ('np_comma', 'NP', ('NP', 'COMMA', 'NP'), None),
        ('np_list_last', 'NP', ('NP', 'COMMA', 'COORD', 'NP'), None),
        ('np_list_full', 'NP', ('NP', 'COMMA', 'NP', 'COMMA', 'COORD', 'NP'), None),
        ('np_coord', 'NP', ('NP', 'COORD', 'NP'), None),
    ]
    return Grammar([rule(name, lhs, *rhs, subcat=subcat) for name, lhs, rhs, subcat in names])


CATEGORIES = {
    'the': 'DET', 'recipe': 'N', 'rosa': 'PROPER-NOUN',
    'followed': 'V', 'failed': 'V',
    'are': 'COPULA', 'keys': 'N', 'inside': 'PREP', 'box': 'N',
    'teacher': 'N', 'listed': 'V', 'dates': 'N', 'places': 'N',
    'and': 'COORD', 'names': 'N', 'times': 'N', 'still': 'ADV', 'carefully': 'ADV',
    'document': 'N', 'emma': 'PROPER-NOUN', 'examined': 'V',
    'disappeared': 'V', 'were': 'COPULA', 'papers': 'N',
    'behind': 'PREP', 'desk': 'N', 'editor': 'N', 'cataloged': 'V',
    'poems': 'N', 'songs': 'N', 'stories': 'N',
    ',': 'COMMA', '?': 'QMARK',
}


def lex(text):
    tokens = [Tok(m.group(), m.start(), m.end())
              for m in re.finditer(r'[A-Za-z]+|[.,?]', text)]
    candidates = []
    for t in tokens:
        if t.text == '.':
            continue
        c = CATEGORIES.get(t.text.lower())
        if c is None:
            continue
        features = {}
        if c == 'V':
            features['subcat'] = ('transitive' if t.text.lower() in
                                  ('followed', 'examined', 'listed', 'cataloged')
                                  else 'intransitive')
            features['vform'] = 'finite'
        candidates.append(Lex(c, t.start, t.end, t.text, t.text.lower(), features))
    return tokens, candidates


def parse(text, grammar=None):
    compiled = CompiledGrammar(grammar or fixture_grammar())
    tok, cand = lex(text)

    def combine(rule, children):
        for sym, ch in zip(rule.rhs, children):
            if sym.features and ch.candidate:
                for name, value in sym.features.items():
                    if ch.candidate.features.get(name) != value:
                        return None
        return ReadNode(rule.lhs.category, children[0].start, children[-1].end,
                           rule=rule, children=children)

    return IncrementalReader(compiled, combine, tok, cand).read()


def assert_economic(outcome, *, limit=45):
    assert outcome.complete, outcome.reason
    assert outcome.root.category == 'CLAUSE'
    assert outcome.counters['consumptions'] <= 16
    assert outcome.counters['unifications'] <= 16
    assert outcome.counters['events'] <= limit
    assert 'revisions' not in outcome.counters
    assert 'backtracks' not in outcome.counters
    assert all(e.action not in ('SEARCH', 'BACKTRACK') for e in outcome.events)


