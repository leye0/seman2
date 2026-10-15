"""The selected sense must license a rule that can actually close now."""
from _reading_kernel_v1_fixture_base import (
    CompiledGrammar, IncrementalReader, ReadNode, Lex, lex, fixture_grammar, Rule, Sym
)


def test_high_lexical_prior_must_not_override_current_grammatical_closure():
    sentence = 'The recipe Rosa followed failed.'
    tokens, candidates = lex(sentence)
    target = next(token for token in tokens if token.text == 'failed')
    candidates = [c for c in candidates if c.surface != 'failed']
    candidates += [
        Lex('V', target.start, target.end, 'failed', 'fail',
            {'vform': 'finite', 'subcat': 'subject_control'}, 1.0),
        Lex('V', target.start, target.end, 'failed', 'fail',
            {'vform': 'finite', 'subcat': ['intransitive', 'prepositional']}, 0.95),
    ]
    grammar = CompiledGrammar(fixture_grammar())
    vp = grammar.roots['VP']
    assert vp.edges['V'].finals[0].rule_id == 'vp_intransitive'
    # A projection from a non-closing rule is mistakenly rated as a
    # valid completion in the overall hint list. The runtime must not
    # prefer it when there is no viable continuation beyond this token.
    wrong = Rule('vp_unfinished_control', Sym('VP'),
                 (Sym('V', {'subcat': 'subject_control'}), Sym('TO')), 50.0)
    vp.hints['V'].append((wrong, wrong.rhs[0], ()))

    def combine(rule, children):
        for sym, ch in zip(rule.rhs, children):
            if ch.candidate:
                for name, expected in sym.features.items():
                    got = ch.candidate.features.get(name)
                    if got != expected and not (isinstance(got, list) and expected in got):
                        return None
        return ReadNode(rule.lhs.category, children[0].start, children[-1].end,
                        rule=rule, children=children)

    result = IncrementalReader(grammar, combine, tokens, candidates).read()
    assert result.complete, (result.reason, [e.as_dict() for e in result.events])
    assert any(e.action == 'COMPLETE' and e.detail == 'vp_intransitive'
               for e in result.events)
