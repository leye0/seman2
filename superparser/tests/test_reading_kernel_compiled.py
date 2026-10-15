"""Executable behavioural contract of the compiled, single-path reader."""
from _reading_kernel_v1_fixture_base import *  # fixture grammar follows Seman2 RHS signatures
import pytest

@pytest.mark.parametrize('sentence', [
    'The recipe Rosa followed failed.',
    'Are the keys inside the box?',
    'The teacher listed dates, places, and names.',
    'The document Emma examined disappeared.',
    'Were the papers behind the desk?',
    'The editor cataloged poems, songs, and stories.',
    'The recipe Rosa carefully followed failed.',
    'Are the keys still inside the box?',
    'The teacher listed dates and names.',
    'The teacher listed dates, places, times, and names.',
])
def test_main_and_heldout(sentence):
    r = parse(sentence)
    assert r.complete, (sentence, r.reason, [e.as_dict() for e in r.events])
    assert r.root.category == 'CLAUSE'
    assert r.counters['unifications'] <= 18
    assert r.counters['events'] <= 45
    assert all(e.action not in ('SEARCH','BACKTRACK','REPAIR') for e in r.events)


def test_grammar_missing_no_fake_acceptance():
    g = fixture_grammar()
    g.rules = [r for r in g.rules if r.rule_id != 'wh_bare']
    r = parse('The recipe Rosa followed failed.', g)
    assert not r.complete
    assert r.reason


def test_no_per_token_rule_scanning():
    r = parse('The teacher listed dates, places, and names.')
    assert r.complete, r.reason
    assert r.counters['unifications'] <= 18
    assert r.counters['eligible_transitions'] < 100


def test_compile_grammar_variation_no_named_reactions():
    src = __import__('inspect').getsource(__import__('seman_parser.reading_kernel_compiled', fromlist=['CompiledGrammar']))
    for forbidden in ('zero_relative', 'nominal_list', 'copular_inversion', 'OBJECT_RELATIVE', 'COPULAR_INVERSION'):
        assert forbidden not in src


def test_observed_continuation_beats_high_score_dead_branch():
    """Lexically ambiguous N/V must not force an impossible DET V N path.

    This regression intentionally gives the wrong rule an enormous score.
    The reader is allowed one category projection, not an exploratory parse.
    """
    grammar = fixture_grammar()
    grammar.rules.append(Rule(
        'adversarial_high_score', Sym('NP'),
        (Sym('DET'), Sym('V', {'vform': 'ed'}), Sym('N')),
        99.0,
    ))
    text = 'The recipe Rosa followed failed.'
    tokens, candidates = lex(text)
    word = tokens[1]
    candidates.append(Lex('V', word.start, word.end, word.text, 'recipe',
                          {'vform':'finite', 'subcat':'transitive'}, 15.0))
    def combine(rule, children):
        if rule.rule_id == 'adversarial_high_score':
            return None
        return ReadNode(rule.lhs.category, children[0].start, children[-1].end,
                        rule=rule, children=children)
    reader = IncrementalReader(CompiledGrammar(grammar), combine, tokens, candidates)
    result = reader.read()
    assert result.complete, (result.reason, [e.as_dict() for e in result.events])
    assert result.counters['unifications'] <= 9
    assert any(e.action == 'CONSUME' and e.word == 'recipe' and e.expected == 'N'
               for e in result.events)
    assert not any(e.action == 'CONSUME' and e.word == 'recipe' and e.expected == 'V'
                   for e in result.events)


def test_lexical_category_also_productive_nonterminal():
    """Actual repo grammar includes N -> ADJ N / N N and ADJ -> DEGREE ADJ.

    Previously this caused a lexical N to disappear from the compiler's
    FIRST/dispatch table, and then an NP was closed as np_demonstrative.
    """
    grammar = fixture_grammar()
    grammar.rules += [
        rule('n_adj_n', 'N', 'ADJ', 'N'),
        rule('n_compound', 'N', 'N', 'N'),
        rule('adj_degree', 'ADJ', 'DEGREE', 'ADJ'),
        Rule('np_demonstrative', Sym('NP'), (Sym('DET', {
            'definiteness': 'demonstrative', 'anaphor': 'true',
        }),), 1.2),
    ]
    compiled = CompiledGrammar(grammar)
    assert 'N' in compiled.first['N']
    after_det = compiled.roots['NP'].edges['DET']
    assert 'N' in after_det.edges
    assert 'N' in after_det.dispatch
    tok, candidates = lex('The recipe Rosa followed failed.')
    reader = IncrementalReader(compiled, lambda r, cs: ReadNode(
        r.lhs.category, cs[0].start, cs[-1].end, rule=r, children=cs,
    ), tok, candidates)
    reader.pos = 1
    assert reader._select(after_det) == 'N'
    reader.pos = 0
    result = reader.read()
    assert result.complete, (result.reason, [e.as_dict() for e in result.events])
    assert result.counters['unifications'] <= 12
    assert all(e.action != 'BACKTRACK' for e in result.events)


@pytest.mark.parametrize('sentence', [
    'The recipe Rosa followed failed.',
    'Are the keys inside the box?',
    'The teacher listed dates, places, and names.',
    'The document Emma examined disappeared.',
    'Were the papers behind the desk?',
    'The editor cataloged poems, songs, and stories.',
    'Are the keys still inside the box?',
    'The teacher listed dates and names.',
    'The teacher listed dates, places, times, and names.',
])
def test_productive_lexical_categories_do_not_break_reading(sentence):
    g = fixture_grammar()
    g.rules += [
        rule('n_adj_n', 'N', 'ADJ', 'N'),
        rule('n_compound', 'N', 'N', 'N'),
        rule('adj_degree', 'ADJ', 'DEGREE', 'ADJ'),
    ]
    result = parse(sentence, g)
    assert result.complete, (sentence, result.reason, [e.as_dict() for e in result.events])
    assert result.counters['unifications'] <= 18
