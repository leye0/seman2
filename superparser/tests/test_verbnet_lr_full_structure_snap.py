"""Whole-structure snapping regression tests (no WordNet download)."""
import unittest
from dataclasses import dataclass
from seman_parser.engine import ParserResources
from seman_parser.features import FeatureStructure, Variable
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.segmentation import LexicalCandidate, LexicalLattice, Token
from seman_parser.predictive import CompactNode, PredictiveParser
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.symbols import intern
from research.verbnet_lr.full_structure_snap import (
    FullStructureSnapIndex, SnappingResearchReader)
from research.verbnet_lr.packed_witness import seek_packed_witness
from research.verbnet_lr.construction_guard import ConstructionGuard
from research.verbnet_lr.full_structure_snap import SnapResult, SnapMatch


def S(cat, **features):
    return RuleSymbol(cat, FeatureStructure.build(features))


def R(name, lhs, *rhs):
    return GrammarRule(name, tuple(rhs), lhs)


class FullStructureSnapTests(unittest.TestCase):
    def setUp(self):
        grammar = Grammar([
            R("clause", S("CLAUSE"), S("PRON"), S("VP")),
            R("vp_np", S("VP"), S("V"), S("NP")),
            R("vp_pp", S("VP"), S("VP"), S("PP")),
            R("np_n", S("NP"), S("N", number="sg")),
            R("np_pp", S("NP"), S("NP"), S("PP")),
            R("pp", S("PP"), S("PREP"), S("NP")),
        ])
        self.resources = ParserResources(grammar, None, None)
        self.index = FullStructureSnapIndex(self.resources)
        self.rules = {r.rule_id:r for r in grammar}
        self.adapter = PredictiveParser(self.resources)

    def lattice(self, words, categories):
        tokens, options = [], []
        pos = 0
        for i, (word, rows) in enumerate(zip(words, categories)):
            token = Token(i, pos, pos + len(word), word)
            tokens.append(token)
            for cat, number, score in rows:
                options.append(LexicalCandidate(
                    pos, pos+len(word), word, word.casefold(), cat,
                    FeatureStructure.build({"number": number} if number else {}),
                    score=score))
            pos += len(word)+1
        return LexicalLattice(" ".join(words), tuple(tokens), tuple(options))

    def leaf(self, cand):
        return CompactNode(cand.category, intern(cand.category),
                           cand.span_start, cand.span_end, cand.features,
                           frozenset(k for k,v in cand.features.items()
                                     if not isinstance(v, Variable)),
                           cand.score, candidate=cand)

    def tree(self, rule_name, *children):
        node = PredictiveParser._reduce(self.rules[rule_name], children)
        self.assertIsNotNone(node, rule_name)
        return node

    def two_attached_trees(self, lattice):
        c = lattice.candidates
        # The same exact lexical sequence supports VP and NP attachment.
        pron, verb, noun, prep, final = [self.leaf(x) for x in c]
        first_np = self.tree("np_n", noun)
        second_np = self.tree("np_n", final)
        pp = self.tree("pp", prep, second_np)
        vp_attached = self.tree("clause", pron,
                               self.tree("vp_pp",
                                   self.tree("vp_np", verb, first_np), pp))
        np_attached = self.tree("clause", pron,
                               self.tree("vp_np", verb,
                                   self.tree("np_pp", first_np, pp)))
        return (self.adapter._materialize(vp_attached),
                self.adapter._materialize(np_attached))

    def test_one_type_sequence_snaps_to_both_complete_trees(self):
        raw = [("PRON", None, 1), ("V", None, 1),
               ("N", "sg", 1), ("PREP", None, 1), ("N", "sg", 1)]
        training = self.lattice(["I", "saw", "girl", "with", "hat"],
                                [[entry] for entry in raw])
        a, b = self.two_attached_trees(training)
        ids = [self.index.observe(x, lattice=training) for x in (a, b)]
        self.assertNotEqual(ids[0], ids[1])
        self.assertEqual(self.index.summary()["templates"], 2)
        unseen = self.lattice(["we", "met", "pilot", "near", "town"],
                              [[entry] for entry in raw])
        result = self.index.match(unseen)
        self.assertTrue(result.complete, result.reason)
        self.assertFalse(result.incomplete, result.reason)
        self.assertEqual({m.template_id for m in result.matches}, set(ids))
        self.assertEqual({m.item.rule_id for m in result.matches}, {"clause"})
        self.assertTrue(all(not m.independently_verified_template
                            for m in result.matches))

    def test_all_lexical_candidates_retained_and_real_unification(self):
        rows = [[("PRON", None, 1)], [("V", None, 1)],
                [("N", "pl", 9), ("N", "sg", 1)],
                [("PREP", None, 1)], [("N", "sg", 1)]]
        lattice = self.lattice(["I", "saw", "girl", "with", "hat"],
                               [[r[-1]] for r in rows])
        self.index.observe(self.two_attached_trees(lattice)[0], lattice=lattice)
        ambiguous = self.lattice(["we", "met", "pilot", "near", "town"], rows)
        result = self.index.match(ambiguous)
        self.assertEqual(len(result.matches), 1)
        self.assertEqual(len(result.lattice.candidates), 6)
        leaves = []
        def visit(item):
            if item.lexical_candidate is not None:
                leaves.append(item.lexical_candidate)
            for child in item.children:
                visit(child)
        visit(result.item)
        self.assertEqual(str(leaves[2].features.as_dict()["number"]), "sg")
        wrong = self.lattice(["we", "met", "pilot", "near", "town"],
                             [[r[0]] if i!=2 else [("N", "pl", 1)]
                              for i,r in enumerate(rows)])
        missed = self.index.match(wrong)
        self.assertFalse(missed.complete)
        self.assertEqual(missed.reason, "templates_failed_feature_unification")

    def test_source_evidence_orders_operational_choice_without_deleting_alternatives(self):
        raw=[("PRON",None,1),("V",None,1),("N","sg",1),
             ("PREP",None,1),("N","sg",1)]
        lattice=self.lattice(["I","saw","girl","with","hat"],[[x] for x in raw])
        a,b=self.two_attached_trees(lattice)
        self.index.observe(a,lattice=lattice,evidence="candidate")
        self.index.observe(b,lattice=lattice,evidence="grammar_witness")
        result=self.index.match(lattice)
        self.assertEqual(len(result.matches),2)
        # Equal rule scores: the Earley grammatical witness breaks a tie.
        self.assertTrue(result.matches[0].grammar_witness_template)
        self.assertEqual(result.matches[0].template_id,1)
        self.assertEqual({m.template_id for m in result.matches},{0,1})
        self.assertFalse(result.matches[0].independently_verified_template)

        # A lower-scored witness should not suppress a stronger alternative.
        original=self.rules["np_pp"]
        self.index.rules["np_pp"]=GrammarRule(
            original.rule_id,original.rhs,original.lhs,score=-7.0)
        outranked=self.index.match(lattice)
        self.assertEqual(outranked.matches[0].template_id,0)
        self.assertFalse(outranked.matches[0].grammar_witness_template)
        self.assertEqual({m.template_id for m in outranked.matches},{0,1})

    def test_many_templates_same_sequence_remain_bounded(self):
        rows=[[("PRON",None,1)],[("V",None,1)],
              [("N","sg",1)],[("PREP",None,1)],[("N","sg",1)]]
        source=self.lattice(["I","saw","girl","with","hat"],rows)
        for tree in self.two_attached_trees(source):
            self.index.observe(tree,lattice=source)
        result=self.index.match(source,max_templates_checked=1)
        self.assertEqual(result.candidate_templates,2)
        self.assertEqual(result.checked_templates,1)
        self.assertEqual(len(result.matches),1)
        self.assertTrue(result.incomplete)
        self.assertIs(self.index.templates[0].categories,
                      self.index.templates[1].categories)

    def test_deferred_alternatives_paged_and_first_match_can_return(self):
        from unittest.mock import patch
        cats=[[("PRON",None,1)],[("V",None,1)],
              [("N","sg",1)],[("PREP",None,1)],[("N","sg",1)]]
        lattice=self.lattice(["I","saw","girl","with","hat"],cats)
        for tree in self.two_attached_trees(lattice):
            self.index.observe(tree,lattice=lattice)
        first=self.index.match(lattice,max_templates_checked=1)
        self.assertTrue(first.complete)
        self.assertEqual(first.next_template_offset,1)
        second=self.index.match(lattice,max_templates_checked=1,
                                template_offset=first.next_template_offset)
        self.assertEqual(second.matches[0].template_id,1)
        self.assertIsNone(second.next_template_offset)
        self.assertEqual(second.candidate_templates,2)
        past=self.index.match(lattice,max_templates_checked=1,
                              template_offset=2)
        self.assertEqual(past.reason,"template_offset_past_end")
        self.assertFalse(past.complete)
        with self.assertRaises(ValueError):
            self.index.match(lattice,template_offset=-1)

        class NeverFallback:
            def parse(self, text):
                raise AssertionError("L-R fallback must not run on valid snap")
        wrapper=SnappingResearchReader(self.resources,index=self.index,
                                       fallback=NeverFallback(),
                                       max_templates_checked=1)
        with patch("seman_parser.segmentation.build_lattice",return_value=lattice):
            snapped,path=wrapper.parse(lattice.text)
        self.assertEqual(path,"snap")
        self.assertTrue(snapped.incomplete)
        self.assertTrue(snapped.complete)

    def test_chartitem_construction_guard_and_hybrid_rejection(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        def leaf(word,category,lemma=None,**features):
            c=SimpleNamespace(surface=word,category=category,
                              lemma=lemma or word.casefold(),features=features)
            return SimpleNamespace(category=category,lexical_candidate=c,
                                   children=(),rule_id=None)
        def phrase(category,children):
            return SimpleNamespace(category=category,lexical_candidate=None,
                                   children=tuple(children),rule_id="synthetic")
        subject=phrase("NP",(leaf("The","DET"),
                              leaf("dogs","N",number="plural")))
        vp=phrase("VP",(leaf("barks","V",lemma="bark"),))
        wrong=phrase("CLAUSE",(subject,vp))
        self.assertFalse(ConstructionGuard().validate(wrong).acceptable)
        good=phrase("CLAUSE",(subject,
                              phrase("VP",(leaf("bark","V",lemma="bark"),))))
        self.assertTrue(ConstructionGuard().validate(good).acceptable)

        class ControlFallback:
            def parse(self, text):
                return SimpleNamespace(complete=False)
        fake_lattice=self.lattice(["The","dogs","barks"],
            [[("DET",None,1)],[("N","pl",1)],[("V",None,1)]])
        fake=SnapResult((SnapMatch(0,wrong,False),),fake_lattice,
                        1,1,0,False,"matched")
        wrapper=SnappingResearchReader(self.resources,index=self.index,
                                       fallback=ControlFallback())
        with patch("seman_parser.segmentation.build_lattice",
                   return_value=fake_lattice), patch.object(self.index,"match",
                   return_value=fake):
            result,path=wrapper.parse(fake_lattice.text)
        self.assertEqual(path,"left_to_right")
        self.assertFalse(result.complete)

    def test_prebuilt_lattice_reused_by_l_r_after_snap_miss(self):
        from unittest.mock import patch
        cases=[[("PRON",None,1)], [("V",None,1)], [("N","sg",1)]]
        lattice=self.lattice(["I","saw","girl"],cases)
        fallback=SemanCompiledReader(self.resources,token_only_lattice=True)
        # Resources have no lexicon in this fixture: this MUST use the
        # supplied candidate lattice rather than calling build_lattice again.
        parsed=fallback.parse(lattice.text,lattice=lattice)
        self.assertTrue(parsed.complete,parsed.outcome.reason)
        with self.assertRaises(ValueError):
            fallback.parse("different text",lattice=lattice)
        wrapper=SnappingResearchReader(self.resources,index=self.index,
                                       fallback=fallback)
        with patch("seman_parser.segmentation.build_lattice",return_value=lattice):
            wrapped,path=wrapper.parse(lattice.text)
        self.assertEqual(path,"left_to_right")
        self.assertTrue(wrapped.complete,wrapped.outcome.reason)
        self.assertEqual(wrapped.item.rule_id,parsed.item.rule_id)

    def test_reused_lattice_for_full_online_sentence(self):
        from unittest.mock import patch
        from research.verbnet_lr.full_structure_snap import SnappingResearchReader
        cats=[[("PRON",None,1)],[("V",None,1)],[("N","sg",1)]]
        lattice=self.lattice(["I","saw","girl"],cats)
        fallback=SemanCompiledReader(self.resources,token_only_lattice=True)
        wrapper=SnappingResearchReader(
            self.resources,index=self.index,fallback=fallback)
        with patch("seman_parser.segmentation.build_lattice") as build:
            result,route=wrapper.parse(
                lattice.text,lattice=lattice,learn_candidate=True)
            build.assert_not_called()
        self.assertEqual(route,"left_to_right")
        self.assertTrue(result.complete)
        self.assertEqual(len(self.index.templates),1)
        with patch("seman_parser.segmentation.build_lattice") as build:
            again,route=wrapper.parse(lattice.text,lattice=lattice)
            build.assert_not_called()
        self.assertEqual(route,"snap")
        self.assertTrue(again.complete)
        with self.assertRaises(ValueError):
            wrapper.parse("wrong",lattice=lattice)

    def test_extra_lexical_categories_can_never_block_snap(self):
        base=[("PRON",None,1),("V",None,1),("N","sg",1),
              ("PREP",None,1),("N","sg",1)]
        training=self.lattice(["I","saw","girl","with","hat"],
                              [[x] for x in base])
        for item in self.two_attached_trees(training):
            self.index.observe(item,lattice=training)
        abundant=[
            [base[0],("N",None,2),("ADJ",None,5)],
            [base[1],("N",None,10),("ADV",None,7)],
            [base[2],("ADJ",None,11),("V",None,9)],
            [base[3],("N",None,3)],
            [base[4],("ADV",None,8)],
        ]
        query=self.lattice(["we","met","pilot","near","town"],abundant)
        matching=self.index.match(query)
        self.assertEqual(len(matching.matches),2)
        self.assertEqual({m.template_id for m in matching.matches},{0,1})
        self.assertIs(matching.lattice,query)
        self.assertEqual(len(query.candidates),sum(map(len,abundant)))

    def test_unknown_and_explicit_budgets(self):
        cats = [[("PRON",None,1)], [("V",None,1)],
                [("N","sg",1)], [("PREP",None,1)],
                [("N","sg",1)]]
        src = self.lattice(["I", "saw", "girl", "with", "hat"],cats)
        for tree in self.two_attached_trees(src):
            self.index.observe(tree, lattice=src)
        limited = self.index.match(src, max_templates_checked=1)
        self.assertTrue(limited.incomplete)
        self.assertEqual(limited.candidate_templates, 2)
        self.assertEqual(len(limited.matches), 1)
        missing = self.lattice(["I", "saw", "girl"], cats[:3])
        self.assertEqual(self.index.match(missing).reason,"unseen_pattern")
        self.assertEqual(len(self.index.templates), 2)

    def test_dedup_and_provenance(self):
        rows = [[("PRON",None,1)], [("V",None,1)],
                [("N","sg",1)], [("PREP",None,1)],
                [("N","sg",1)]]
        src = self.lattice(["I","saw","girl","with","hat"], rows)
        t = self.two_attached_trees(src)[0]
        self.assertEqual(self.index.observe(t, lattice=src), 0)
        self.assertEqual(self.index.observe(t, lattice=src), 0)
        self.assertEqual(self.index.templates[0].candidate_observations, 2)
        self.assertFalse(self.index.match(src).matches[0].independently_verified_template)
        self.index.observe(t,lattice=src,evidence="verified")
        self.assertTrue(self.index.match(src).matches[0].independently_verified_template)
        with self.assertRaises(ValueError):
            self.index.observe(t,lattice=src,evidence="parser_completion")

    def test_independent_earley_witness_is_not_gold(self):
        categories=[[("PRON",None,1)], [("V",None,1)],
                    [("N","sg",1)]]
        lattice=self.lattice(["I","saw","girl"],categories)
        result=seek_packed_witness(
            self.resources.grammar,lattice,
            max_items=50000,max_seconds=1.0,
            return_compact_node=True)
        self.assertEqual(result["status"],"FOUND",result)
        self.assertIsNotNone(result["witness_node"])
        item=self.adapter._materialize(result["witness_node"])
        template_id=self.index.observe(item,lattice=lattice,
                                        evidence="grammar_witness")
        snapped=self.index.match(lattice)
        self.assertTrue(snapped.complete,snapped.reason)
        match=next(m for m in snapped.matches if m.template_id==template_id)
        self.assertTrue(match.grammar_witness_template)
        self.assertFalse(match.independently_verified_template)
        self.assertEqual(self.index.summary()["verified_templates"],0)

    def test_no_multiword_fabrication(self):
        rows = [[("PRON",None,1)], [("V",None,1)],
                [("N","sg",1)], [("PREP",None,1)],
                [("N","sg",1)]]
        src = self.lattice(["I","saw","girl","with","hat"], rows)
        t = self.two_attached_trees(src)[0]
        shortened = LexicalLattice(src.text, src.tokens[:-1], src.candidates)
        with self.assertRaises(ValueError):
            self.index.observe(t,lattice=shortened)


if __name__ == "__main__":
    unittest.main()
