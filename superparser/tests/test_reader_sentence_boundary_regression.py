"""Regression for the observed real-grammar failure at 'failed.'."""
from _reading_kernel_v1_fixture_base import (
    CompiledGrammar, IncrementalReader, ReadNode, Lex, lex,
    fixture_grammar, Rule, Sym
)


def _case():
    sentence = 'The recipe Rosa followed failed.'
    tokens, lexical = lex(sentence)
    failed = next(t for t in tokens if t.text == 'failed')
    dot = next(t for t in tokens if t.text == '.')
    lexical = [c for c in lexical if c.surface != 'failed']
    lexical.extend([
        Lex('V', failed.start, failed.end, 'failed', 'fail',
            {'vform': 'finite', 'subcat': 'subject_control'}, 1.0),
        Lex('V', failed.start, failed.end, 'failed', 'fail',
            {'vform': 'finite', 'subcat': ['intransitive', 'prepositional']}, .95),
        Lex('COMMA', dot.start, dot.end, '.', '.', {}, 0.2),
    ])
    rules = fixture_grammar()
    rules.rules.append(Rule(
        'vp_colon_question', Sym('VP'),
        (Sym('V', {'vform': 'finite'}), Sym('COMMA'), Sym('CLAUSE')),
        1.2,
    ))

    def combine(rule, children):
        for sym, child in zip(rule.rhs, children):
            if child.candidate:
                for name, wanted in sym.features.items():
                    actual = child.candidate.features.get(name)
                    if actual != wanted and not (
                        isinstance(actual, (list, tuple)) and wanted in actual
                    ):
                        return None
        return ReadNode(
            rule.lhs.category, children[0].start, children[-1].end,
            rule=rule, children=tuple(children)
        )

    return CompiledGrammar(rules), combine, tokens, lexical


def test_sentence_stop_cannot_look_like_comma_continuation():
    grammar, combine, tokens, lexical = _case()
    reader = IncrementalReader(grammar, combine, tokens, lexical)
    assert 'COMMA' not in reader._categories(len(tokens) - 1)
    result = reader.read()
    assert result.complete, (
        result.reason, [e.as_dict() for e in result.events]
    )
    assert any(
        e.action == 'COMPLETE' and e.detail == 'vp_intransitive'
        for e in result.events
    )
    assert result.counters['unifications'] <= 12
    assert not any(e.action == 'BACKTRACK' for e in result.events)


def test_question_mark_remains_grammar_owned():
    grammar, combine, tokens, lexical = _case()
    tok, cands = lex('Are the keys inside the box?')
    reader = IncrementalReader(grammar, combine, tok, cands)
    assert 'QMARK' in reader._categories(len(tok) - 1)
