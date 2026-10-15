from _reading_kernel_v1_fixture_base import *
from dataclasses import dataclass

@dataclass(frozen=True)
class NeedSym:
    category: str
    features: dict
    requires: tuple[str,...] = ('nominal',)

def grammar_fixture():
    g = fixture_grammar()
    g.rules += [
        Rule('np_det_n_clause', Sym('NP'), (Sym('DET'),Sym('N'), NeedSym('CLAUSE', {'nominal':'true'})), 7.0),
        Rule('clause_nominal_that', Sym('CLAUSE', {'nominal':'true'}),(Sym('COMP-THAT'),Sym('CLAUSE')), 8.0),
        Rule('clause_np_vp_shadow', Sym('CLAUSE'),(Sym('NP'),Sym('VP')), 6.0),
    ]
    return g

def test_evidence_first_excludes_unlicensed_openings():
    g=CompiledGrammar(grammar_fixture())
    state=g.roots['NP'].edges['DET'].edges['N']
    assert 'CLAUSE' in state.edges
    assert 'PROPER-NOUN' not in state.dispatch
    assert 'COMP-THAT' in state.dispatch
    assert 'CLAUSE' in state.dispatch['COMP-THAT']

def test_relative_not_swallowed_by_clausal_nominal():
    result=parse('The recipe Rosa followed failed.', grammar_fixture())
    assert result.complete, (result.reason, [e.as_dict() for e in result.events])
    assert any(e.detail == 'np_relative_obj' for e in result.events)
    assert all(not (e.word == 'Rosa' and e.expected == 'CLAUSE' and e.action == 'EXPECT') for e in result.events)
