"""Feature variables MUST survive reconstruction of a remembered grammar tree.

No training text is cached: the structural index keeps rule IDs and lexical
category slots. Replaying the same or a different lexical realization must
reapply RHS constraints through every descendant.
"""
from __future__ import annotations

import unittest

from research.verbnet_lr.full_structure_snap import FullStructureSnapIndex
from seman_parser.engine import ParserResources
from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.segmentation import LexicalCandidate, LexicalLattice, Token
from seman_parser.vector_chart import VectorGrammar


def S(category, **features):
    return RuleSymbol(category, FeatureStructure.build(features))


def R(rule_id, lhs, *rhs):
    return GrammarRule(rule_id, tuple(rhs), lhs)


def lattice(text, first, second):
    a,b=text.split()
    tokens=(Token(0,0,len(a),a),Token(1,len(a)+1,len(text),b))
    candidates=(
        LexicalCandidate(0,len(a),a,a.casefold(),"PRONOUN",
                         FeatureStructure.build(first),score=5.0),
        LexicalCandidate(len(a)+1,len(text),b,b.casefold(),"V",
                         FeatureStructure.build(second),score=4.0),
    )
    return LexicalLattice(text,tokens,candidates)


def normalized_tree(node):
    return (
        node.category,node.rule_id,node.start,node.end,
        node.features.as_dict(),node.syntax.as_dict(),
        tuple(normalized_tree(ch) for ch in node.children),
    )


class SnapContextualFeatureTests(unittest.TestCase):
    def setUp(self):
        self.grammar=Grammar([
            R("clause",S("CLAUSE"),S("PRONOUN",gender="?g"),S("VP")),
            R("vp",S("VP"),S("V")),
        ])
        self.resources=ParserResources(self.grammar,None,None)
        self.parser=VectorGrammar(self.grammar)
        self.memory=FullStructureSnapIndex(self.resources)

    def analyze(self, row):
        result=self.parser.parse_lattice(row,beam=80,max_items=50000,goal_category="CLAUSE")
        self.assertTrue(result.completed)
        item=result.best()
        self.assertIsNotNone(item)
        return item

    def test_variable_on_lexical_child_is_preserved_after_replay(self):
        # The lexical pronoun does not specify gender, but the parent rule
        # requires a unification variable that must remain visible.
        row=lattice("they walk",{"person":"3"},{"tense":"present"})
        initial=self.analyze(row)
        self.assertEqual(initial.children[0].features.as_dict()["gender"],"?g")
        self.memory.observe(initial,lattice=row)
        replay=self.memory.match(row)
        self.assertTrue(replay.complete,replay.reason)
        self.assertEqual(normalized_tree(initial),normalized_tree(replay.item))
        self.assertEqual(replay.item.children[0].features.as_dict()["gender"],"?g")

    def test_new_words_reunify_context_not_training_features(self):
        source=lattice("they walk",{"person":"3"},{"tense":"present"})
        item=self.analyze(source)
        self.memory.observe(item,lattice=source)
        # An unrelated phrase with *different* lexical values must not
        # inherit training lexical data, only the grammar constraint.
        target=lattice("she sings",{"gender":"feminine","person":"3"},
                       {"tense":"past"})
        snapped=self.memory.match(target)
        self.assertTrue(snapped.complete,snapped.reason)
        self.assertEqual(snapped.item.children[0].features.as_dict()["gender"],
                         "feminine")
        self.assertEqual(snapped.item.children[1].children[0].features.as_dict()["tense"],
                         "past")
        self.assertEqual(
            normalized_tree(self.analyze(target)), normalized_tree(snapped.item))

    def test_nested_unresolved_variable_survives_two_rule_levels(self):
        grammar=Grammar([
            R("clause",S("CLAUSE"),S("PRONOUN",gender="?g"),
              S("VP",tense="?t")),
            R("vp",S("VP",tense="?t"),S("V",tense="?t")),
        ])
        parser=VectorGrammar(grammar)
        resources=ParserResources(grammar,None,None)
        memory=FullStructureSnapIndex(resources)
        row=lattice("they walk",{"person":"3"},{"aspect":"simple"})
        result=parser.parse_lattice(row,goal_category="CLAUSE")
        self.assertTrue(result.completed)
        initial=result.best()
        memory.observe(initial,lattice=row)
        snapped=memory.match(row)
        self.assertTrue(snapped.complete)
        self.assertEqual(normalized_tree(initial),normalized_tree(snapped.item))
        self.assertEqual(snapped.item.children[0].features.as_dict()["gender"],"?g")
        self.assertIn("tense",snapped.item.children[1].children[0].features.as_dict())

    def test_incompatible_gender_is_not_snapped(self):
        grammar=Grammar([
            R("clause",S("CLAUSE"),S("PRONOUN",gender="masculine"),S("VP")),
            R("vp",S("VP"),S("V")),
        ])
        resources=ParserResources(grammar,None,None)
        memory=FullStructureSnapIndex(resources)
        masculine=lattice("he walks",{"gender":"masculine"},{})
        feminine=lattice("she walks",{"gender":"feminine"},{})
        native=VectorGrammar(grammar).parse_lattice(masculine,beam=80,max_items=50000,goal_category="CLAUSE")
        self.assertTrue(native.completed)
        memory.observe(native.best(),lattice=masculine)
        result=memory.match(feminine)
        self.assertFalse(result.complete)


if __name__=="__main__":
    unittest.main()
