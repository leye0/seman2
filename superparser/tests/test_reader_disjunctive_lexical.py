"""A single WordNet candidate may license multiple syntactic frames."""
from _reading_kernel_v1_fixture_base import (fixture_grammar, lex, Lex, ReadNode, CompiledGrammar, IncrementalReader)


def test_disjunctive_verb_frame_is_usable_without_branching():
    text = 'The recipe Rosa followed failed.'
    tokens, original = lex(text)
    candidates = []
    for c in original:
        if c.surface.lower() == 'failed':
            candidates.append(Lex(c.category, c.span_start, c.span_end,
                c.surface, c.lemma,
                {'vform':'finite', 'subcat': ['intransitive','transitive']},c.score))
        else:
            candidates.append(c)

    def combine(rule, children):
        for sym, ch in zip(rule.rhs, children):
            if sym.features and ch.candidate:
                for name, value in sym.features.items():
                    got = ch.candidate.features.get(name)
                    if got != value and not (isinstance(got,list) and value in got):
                        return None
        return ReadNode(rule.lhs.category, children[0].start, children[-1].end,
                        rule=rule, children=children)
    result = IncrementalReader(CompiledGrammar(fixture_grammar()), combine, tokens, candidates).read()
    assert result.complete, (result.reason, [e.as_dict() for e in result.events])
    assert any(e.action == 'COMPLETE' and e.detail == 'vp_intransitive' for e in result.events)
