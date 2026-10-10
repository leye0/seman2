"""Tests for signature compatibility, induction, and original parse contract."""
import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from seman_parser.fastpath import (
    CachedLexiconView, CategoryBits, ConstructionIndex, ConstructionLearner,
    ConstructionTemplate, LexicalSignatureLattice, EarleyStructureRecognizer,
)
from seman_parser.segmentation import LexicalLattice, LexicalCandidate, Token
from seman_parser.features import FeatureStructure
from seman_parser.chart import Provenance, _DeferredProvenanceChildren


def sample_lattice():
    # Simulates the example: The man is breaking the hammer.
    tokens = (Token(0, 0, 3, 'The'), Token(1, 4, 7, 'man'),
              Token(2, 8, 10, 'is'), Token(3, 11, 19, 'breaking'),
              Token(4, 20, 23, 'the'), Token(5, 24, 30, 'hammer'))
    pos = (('DET',), ('N', 'V'), ('AUX', 'COPULA'), ('V', 'ADJ'), ('DET',), ('N', 'V'))
    candidates = tuple(LexicalCandidate(
        span_start=t.start, span_end=t.end, surface=t.text,
        lemma=t.text.lower(), category=category, features=FeatureStructure.empty(),
    ) for t, cats in zip(tokens, pos) for category in cats)
    return LexicalLattice('The man is breaking the hammer.', tokens, candidates)


class SignatureTests(unittest.TestCase):
    def test_ambiguities_are_preserved_without_enumeration(self):
        vocab = CategoryBits()
        sig = LexicalSignatureLattice(sample_lattice(), vocab)
        self.assertEqual(sig.token_signatures[1].categories, ('N', 'V'))
        self.assertEqual(sig.token_signatures[5].categories, ('N', 'V'))
        self.assertEqual(len(sig.edges), 6)  # six positions, not 16 POS sequences

    def test_seed_keeps_lexical_category_even_when_also_nonterminal(self):
        def rule(rule_id, lhs, *rhs):
            return SimpleNamespace(rule_id=rule_id, lhs=SimpleNamespace(category=lhs),
                                   rhs=tuple(SimpleNamespace(category=c) for c in rhs))
        grammar = (rule('np_det_n', 'NP', 'DET', 'N'),
                   rule('n_modifier', 'N', 'ADJ', 'N'))
        index = ConstructionIndex()
        self.assertEqual(index.seed_from_grammar(grammar), 2)
        self.assertIn(('NP', ('DET', 'N')),
                      {(m.label, m.categories) for m in index.scan(sample_lattice())})

    def test_compiled_patterns_match_ambiguous_tokens(self):
        vocab = CategoryBits()
        idx = ConstructionIndex(vocab)
        idx.add(ConstructionTemplate('CLAUSE', ('DET', 'N', 'AUX', 'V', 'DET', 'N')))
        idx.add(ConstructionTemplate('OTHER', ('DET', 'V', 'AUX', 'ADJ', 'DET', 'V')))
        matches = idx.scan(sample_lattice())
        self.assertEqual({m.label for m in matches}, {'CLAUSE', 'OTHER'})
        self.assertEqual({(m.start, m.end) for m in matches}, {(0, 30)})

    def test_morphology_cache_is_bounded_and_explicitly_invalidated(self):
        class Lex:
            def __init__(self):
                self.calls = 0
            def lookup_morphology(self, text):
                self.calls += 1
                return [text.lower()]
        source = Lex()
        cache = CachedLexiconView(source, capacity=1)
        self.assertEqual(cache.lookup_morphology('Over'), ('over',))
        self.assertEqual(cache.lookup_morphology('over'), ('over',))
        self.assertEqual(source.calls, 1)
        cache.lookup_morphology('hammer')
        cache.lookup_morphology('over')
        self.assertEqual(source.calls, 3)
        cache.invalidate()
        self.assertEqual(cache.stats()['entries'], 0)

    def test_new_structures_are_tentative_not_grammar_rules(self):
        index = ConstructionIndex()
        learner = ConstructionLearner(index, threshold=2)
        leaf1 = SimpleNamespace(category='DET', children=())
        leaf2 = SimpleNamespace(category='N', children=())
        node = SimpleNamespace(category='NP', children=(leaf1, leaf2))
        result = SimpleNamespace(completed=True, alternatives=lambda limit: (node,))
        report = SimpleNamespace(result=result)
        self.assertEqual(learner.observe_parsed(report), 0)
        self.assertEqual(learner.observe_parsed(report), 1)
        self.assertIn(('NP', ('DET', 'N')), {(x.label, x.categories) for x in index.templates()})
        self.assertFalse(hasattr(learner, 'grammar'))

    def test_unknown_shape_retains_category_sets(self):
        lattice = LexicalSignatureLattice(sample_lattice(), CategoryBits())
        learner = ConstructionLearner(ConstructionIndex())
        learner.observe_unparsed(lattice)
        self.assertEqual(len(learner.unknown_shapes), 1)
        shape = next(iter(learner.unknown_shapes))
        self.assertEqual(shape[1], ('N', 'V'))

    def test_earley_recognizes_hierarchical_structure(self):
        def rule(lhs, *rhs):
            return SimpleNamespace(lhs=SimpleNamespace(category=lhs),
                                   rhs=tuple(SimpleNamespace(category=c) for c in rhs))
        grammar = (rule('CLAUSE', 'NP', 'VP'), rule('NP', 'DET', 'N'),
                   rule('VP', 'AUX', 'V', 'NP'))
        lattice = LexicalSignatureLattice(sample_lattice(), CategoryBits())
        recognition = EarleyStructureRecognizer(grammar).recognize(lattice)
        self.assertTrue(recognition.possible)
        self.assertFalse(recognition.exceeded_budget)
        self.assertLess(recognition.state_count, 400)
        impossible = (rule('CLAUSE', 'NP', 'VP'), rule('NP', 'DET', 'ADJ'),
                      rule('VP', 'AUX', 'V', 'NP'))
        self.assertFalse(EarleyStructureRecognizer(impossible).recognize(lattice).possible)

    def test_earley_supports_multiword_lexical_edge(self):
        def rule(lhs, *rhs):
            return SimpleNamespace(lhs=SimpleNamespace(category=lhs),
                                   rhs=tuple(SimpleNamespace(category=c) for c in rhs))
        text = 'New York arrived.'
        tokens = (Token(0,0,3,'New'),Token(1,4,8,'York'),Token(2,9,16,'arrived'))
        candidates = (
            LexicalCandidate(0,8,'New York','new york','PROPER-NOUN', FeatureStructure.empty()),
            LexicalCandidate(9,16,'arrived','arrive','V', FeatureStructure.empty()),
        )
        lattice = LexicalSignatureLattice(LexicalLattice(text,tokens,candidates), CategoryBits())
        grammar = (rule('CLAUSE','NP','V'), rule('NP','PROPER-NOUN'))
        self.assertTrue(EarleyStructureRecognizer(grammar).recognize(lattice).possible)

    def test_earley_reports_budget_exhaustion(self):
        def rule(lhs, *rhs):
            return SimpleNamespace(lhs=SimpleNamespace(category=lhs),
                                   rhs=tuple(SimpleNamespace(category=c) for c in rhs))
        grammar = (rule('CLAUSE','NP','VP'), rule('NP','DET','N'), rule('VP','AUX','V','NP'))
        lattice = LexicalSignatureLattice(sample_lattice(), CategoryBits())
        result = EarleyStructureRecognizer(grammar).recognize(lattice,max_states=2)
        self.assertTrue(result.exceeded_budget)

    def test_deferred_provenance_has_same_export(self):
        leaf = SimpleNamespace(provenance=Provenance('lexicon', {'surface': 'man'}))
        parent = Provenance('rule', {
            'rule_id': 'np', 'children': _DeferredProvenanceChildren((leaf,))
        })
        self.assertEqual(parent.as_dict(), {
            'source': 'rule',
            'detail': {'rule_id': 'np', 'children': [{'source': 'lexicon', 'detail': {'surface': 'man'}}]},
        })
        self.assertEqual(parent.detail['children'][0]['detail']['surface'], 'man')


if __name__ == '__main__':
    unittest.main()
