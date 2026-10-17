"""No-reparse regression tests for compiled grammatical-structure occurrences."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from research.verbnet_lr.compiled_structure_snap import CompiledStructureReplayer
from seman_parser.engine import ParserResources
from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.predictive import PredictiveParser
from seman_parser.segmentation import LexicalCandidate, LexicalLattice, Token
from seman_parser.vector_chart import VectorGrammar


def sym(category,**features):
    return RuleSymbol(category,FeatureStructure.build(features))


def sample(text,first_features,second_features):
    words=text.split()
    tokens=[]
    candidates=[]
    start=0
    for i,(word,category,features) in enumerate(zip(
            words,("PRONOUN","V"),(first_features,second_features))):
        end=start+len(word)
        tokens.append(Token(i,start,end,word))
        candidates.append(LexicalCandidate(
            start,end,word,word.casefold(),category,
            FeatureStructure.build(features),score=4.0))
        start=end+1
    return LexicalLattice(text,tuple(tokens),tuple(candidates))


def learn(grammar,row):
    resources=ParserResources(grammar,None,None)
    r=VectorGrammar(grammar).parse_lattice(
        row,beam=80,max_items=50000,goal_category="CLAUSE")
    assert r.completed
    engine=CompiledStructureReplayer(resources)
    item=r.best()
    tid=engine.observe(item,lattice=row)
    return engine,tid,item


class CompiledStructureSnapTests(unittest.TestCase):
    def test_words_original_and_shared_tree_without_reductions(self):
        grammar=Grammar([
            GrammarRule("clause",(sym("PRONOUN",gender="?g"),sym("V")),sym("CLAUSE"))
        ])
        source=sample("they sing",{},{"tense":"present"})
        replay=sample("she walks",{"gender":"feminine"},{"tense":"past"})
        engine,tid,original=learn(grammar,source)
        plan=engine.plans[tid]
        self.assertIs(plan.structure,engine.index.templates[tid].shape)
        with patch.object(PredictiveParser,"_reduce",side_effect=AssertionError("Reduction on hit")),\
             patch.object(PredictiveParser,"_materialize",side_effect=AssertionError("Materialization on hit")):
            result=engine.replay(replay)
        self.assertTrue(result.complete,result.reason)
        self.assertIs(result.occurrence.structure,plan.structure)
        self.assertEqual(result.occurrence.structure_id,tid)
        self.assertEqual(result.occurrence.words,("she","walks"))
        self.assertEqual(result.occurrence.original_text,replay.text)
        self.assertEqual(result.occurrence.lexical_slots[0].lemma,"she")
        self.assertEqual(len(result.occurrence.tokens),2)
        self.assertIsNot(result.occurrence.lexical_slots[0],
                         source.candidates[0])

    def test_precompiled_agreement_rejects_conflicting_new_words(self):
        grammar=Grammar([
            GrammarRule("clause",(sym("PRONOUN",number="?n"),
                                   sym("V",number="?n")),sym("CLAUSE"))
        ])
        trained=sample("they sing",{"number":"plural"},{"number":"plural"})
        engine,tid,_=learn(grammar,trained)
        good=sample("we walk",{"number":"plural"},{"number":"plural"})
        bad=sample("she walk",{"number":"singular"},{"number":"plural"})
        self.assertEqual(engine.replay(good).occurrence.structure_id,tid)
        rejected=engine.replay(bad)
        self.assertFalse(rejected.complete)
        self.assertEqual(rejected.reason,"requires_fallback")

    def test_constant_gender_is_enforced_no_learning_values_copied(self):
        grammar=Grammar([
            GrammarRule("clause",(sym("PRONOUN",gender="masculine"),
                                    sym("V")),sym("CLAUSE"))
        ])
        row=sample("he runs",{"gender":"masculine"},{})
        engine,_,_=learn(grammar,row)
        feminine=sample("she runs",{"gender":"feminine"},{})
        self.assertFalse(engine.replay(feminine).complete)
        self.assertTrue(engine.replay(sample(
            "someone runs",{},{})).complete)

    def test_nested_cross_rule_variable_interfaces(self):
        grammar=Grammar([
            GrammarRule("clause",(sym("PRONOUN"),sym("VP",tense="?t")),sym("CLAUSE")),
            GrammarRule("vp",(sym("V",tense="?t"),),sym("VP",tense="?t"))
        ])
        source=sample("they walk",{},{"tense":"present"})
        engine,_,_=learn(grammar,source)
        target=sample("she ran",{},{"tense":"past"})
        self.assertTrue(engine.replay(target).complete)

    def test_deduplicate_tree_and_keep_occurrences_separate(self):
        grammar=Grammar([
            GrammarRule("clause",(sym("PRONOUN"),sym("V")),sym("CLAUSE"))
        ])
        first=sample("they sing",{},{}); other=sample("we walk",{}, {})
        engine,tid,item=learn(grammar,first)
        self.assertEqual(engine.observe(item,lattice=first),tid)
        self.assertEqual(len(engine.plans),1)
        a=engine.replay(first).occurrence
        b=engine.replay(other).occurrence
        self.assertIs(a.structure,b.structure)
        self.assertNotEqual(a.original_text,b.original_text)
        self.assertIsNot(a.lexical_slots,b.lexical_slots)

    def test_nested_feature_constraints_are_compiled_once(self):
        grammar=Grammar([
            GrammarRule("clause",(sym("PRONOUN",agreement={"number":"plural"}),
                                    sym("V")),sym("CLAUSE"))
        ])
        # Nested feature agreement is checked directly during replay,
        # without reconstructing a grammatical tree.
        resources=ParserResources(grammar,None,None)
        from research.verbnet_lr.compiled_structure_snap import compile_plan
        from research.verbnet_lr.full_structure_snap import Structure
        tree=Structure("CLAUSE","clause",(Structure("PRONOUN"),Structure("V")))
        plan=compile_plan(tree,{"clause":grammar.rules[0]})
        self.assertIsNotNone(plan)
        qualified=sample("they sing",{"agreement":{"number":"plural"}},{})
        rejected=sample("they sing",{"agreement":{"number":"singular"}},{})
        self.assertIsNotNone(CompiledStructureReplayer._fill(
            plan,CompiledStructureReplayer._lexical_slots(qualified)))
        self.assertIsNone(CompiledStructureReplayer._fill(
            plan,CompiledStructureReplayer._lexical_slots(rejected)))


    def test_remembered_word_reading_survives_later_lexicon_change(self):
        grammar=Grammar([GrammarRule(
            "clause",(sym("PRONOUN"),sym("N")),sym("CLAUSE"))])
        source=LexicalLattice(
            "he mildest",(Token(0,0,2,"he"),Token(1,3,10,"mildest")),(
                LexicalCandidate(0,2,"he","he","PRONOUN",FeatureStructure.empty()),
                LexicalCandidate(3,10,"mildest","mildest","N",
                                 FeatureStructure.build({"number":"singular"})),
            ))
        parsed=VectorGrammar(grammar).parse_lattice(
            source,beam=80,max_items=50000,goal_category="CLAUSE")
        self.assertTrue(parsed.completed)
        engine=CompiledStructureReplayer(ParserResources(grammar,None,None))
        tid=engine.observe(parsed.best(),lattice=source)
        # WordNet's evolving lexical entries no longer propose the N reading.
        # A lexical memory keyed by individual word, not full sentence,
        # must preserve the previous interpretation.
        replay=LexicalLattice(source.text,source.tokens,(
            source.candidates[0],
            LexicalCandidate(3,10,"mildest","mild","ADJ",FeatureStructure.empty()),
        ))
        with patch.object(PredictiveParser,"_reduce",
                          side_effect=AssertionError("No grammar deduction")), \
             patch.object(PredictiveParser,"_materialize",
                          side_effect=AssertionError("No grammar reconstruction")):
            found=engine.replay(replay)
        self.assertTrue(found.complete,found.reason)
        self.assertEqual(found.occurrence.structure_id,tid)
        self.assertEqual(found.occurrence.lexical_slots[1].category,"N")
        self.assertEqual(found.occurrence.original_text,"he mildest")
        self.assertEqual(len(found.occurrence.lexical_alternatives[1]),1)

    def test_nonterminal_required_evidence_is_precompiled_not_reparsed(self):
        grammar=Grammar([
            GrammarRule("clause",(
                sym("PRONOUN"),
                RuleSymbol("VP",FeatureStructure.empty(),
                           requires=("voice",))
            ),sym("CLAUSE")),
            GrammarRule("vp",(sym("V",voice="?v"),),
                        sym("VP",voice="?v")),
        ])
        row=sample("they walk",{},{"voice":"active"})
        engine,tid,_=learn(grammar,row)
        self.assertIsNotNone(engine.plans[tid])
        self.assertTrue(engine.plans[tid].evidence_any)
        with patch.object(PredictiveParser,"_reduce",
                          side_effect=AssertionError("No grammar deduction")), \
             patch.object(PredictiveParser,"_materialize",
                          side_effect=AssertionError("No tree reconstruction")):
            replay=engine.replay(sample(
                "we move",{},{"voice":"passive"}))
            invalid=engine.replay(sample("we move",{},{}))
        self.assertTrue(replay.complete,replay.reason)
        self.assertFalse(invalid.complete)

    def test_hyphenated_compound_leaf_spans_multiple_tokens(self):
        grammar=Grammar([GrammarRule(
            "clause",(sym("ADJ"),sym("N")),sym("CLAUSE"))])
        def compound(adjective,noun):
            text=adjective+" "+noun
            hyphen=adjective.index("-")
            nstart=len(adjective)+1
            tokens=(
                Token(0,0,hyphen,adjective[:hyphen]),
                Token(1,hyphen,hyphen+1,"-"),
                Token(2,hyphen+1,len(adjective),adjective[hyphen+1:]),
                Token(3,nstart,len(text),noun),
            )
            candidates=(
                LexicalCandidate(0,len(adjective),adjective,adjective,"ADJ",
                                 FeatureStructure.empty()),
                LexicalCandidate(nstart,len(text),noun,noun,"N",
                                 FeatureStructure.empty()),
            )
            return LexicalLattice(text,tokens,candidates)
        source=compound("well-known","cat")
        parsed=VectorGrammar(grammar).parse_lattice(
            source,beam=80,max_items=50000,goal_category="CLAUSE")
        self.assertTrue(parsed.completed)
        engine=CompiledStructureReplayer(ParserResources(grammar,None,None))
        tid=engine.observe(parsed.best(),lattice=source)
        self.assertIn(tid,engine._spanning_ids)
        replay=compound("deep-rooted","tree")
        with patch.object(PredictiveParser,"_reduce",
                          side_effect=AssertionError("No parsing")), \
             patch.object(PredictiveParser,"_materialize",
                          side_effect=AssertionError("No materializing")):
            result=engine.replay(replay)
        self.assertTrue(result.complete,result.reason)
        self.assertEqual(result.occurrence.structure_id,tid)
        self.assertEqual(result.occurrence.words,("deep-rooted","tree"))
        self.assertEqual(len(result.occurrence.tokens),4)
        self.assertIs(result.occurrence.structure,engine.plans[tid].structure)
        self.assertTrue(engine.probe_original_template(replay,tid))

    def test_contraction_two_leaves_inside_one_token_are_indexed_and_replayed(self):
        grammar=Grammar([GrammarRule(
            "clause",(sym("PRONOUN"),sym("V")),sym("CLAUSE"))])
        source=LexicalLattice("she's",(Token(0,0,5,"she's"),),(
            LexicalCandidate(0,3,"she","she","PRONOUN",FeatureStructure.empty()),
            LexicalCandidate(3,5,"'s","be","V",FeatureStructure.empty()),
        ))
        parsed=VectorGrammar(grammar).parse_lattice(
            source,beam=80,max_items=50000,goal_category="CLAUSE")
        self.assertTrue(parsed.completed)
        engine=CompiledStructureReplayer(ParserResources(grammar,None,None))
        tid=engine.observe(parsed.best(),lattice=source)
        self.assertEqual(len(engine.plans),1)
        self.assertEqual(engine.plans[tid].token_category_groups,
                         (("PRONOUN","V"),))
        with patch.object(PredictiveParser,"_reduce",
                          side_effect=AssertionError("No grammar reparse")), \
             patch.object(PredictiveParser,"_materialize",
                          side_effect=AssertionError("No tree materialization")):
            same=engine.replay(source)
            other=LexicalLattice("he's",(Token(0,0,4,"he's"),),(
                LexicalCandidate(0,2,"he","he","PRONOUN",FeatureStructure.empty()),
                LexicalCandidate(2,4,"'s","be","V",FeatureStructure.empty()),
            ))
            new=engine.replay(other)
        self.assertTrue(same.complete,same.reason)
        self.assertTrue(new.complete,new.reason)
        self.assertEqual(same.occurrence.structure_id,tid)
        self.assertEqual(new.occurrence.words,("he","'s"))
        self.assertEqual(new.occurrence.original_text,"he's")
        self.assertIs(new.occurrence.structure,same.occurrence.structure)
        self.assertEqual(len(new.occurrence.tokens),1)

    def test_contraction_does_not_fabricate_missing_segment(self):
        grammar=Grammar([GrammarRule(
            "clause",(sym("PRONOUN"),sym("V")),sym("CLAUSE"))])
        src=LexicalLattice("she's",(Token(0,0,5,"she's"),),(
            LexicalCandidate(0,3,"she","she","PRONOUN",FeatureStructure.empty()),
            LexicalCandidate(3,5,"'s","be","V",FeatureStructure.empty()),
        ))
        parsed=VectorGrammar(grammar).parse_lattice(
            src,beam=80,max_items=50000,goal_category="CLAUSE")
        self.assertTrue(parsed.completed)
        engine=CompiledStructureReplayer(ParserResources(grammar,None,None))
        engine.observe(parsed.best(),lattice=src)
        broken=LexicalLattice(src.text,src.tokens,src.candidates[:1])
        self.assertFalse(engine.replay(broken).complete)

    def test_wordnet_disjunction_must_not_drop_valid_original_reading(self):
        grammar=Grammar([GrammarRule(
            "clause",(sym("PRONOUN",gender="feminine"),sym("V")),
            sym("CLAUSE"))])
        row=sample("she sings",{"gender":"feminine"},{})
        engine,tid,_=learn(grammar,row)
        c=row.candidates[0]
        ambiguous=LexicalCandidate(c.span_start,c.span_end,c.surface,
            c.lemma,c.category,FeatureStructure.build({
                "gender":["masculine","feminine"]}),score=100)
        updated=LexicalLattice(row.text,row.tokens,(ambiguous,)+row.candidates)
        res=engine.replay(updated)
        self.assertTrue(res.complete,res.reason)
        self.assertEqual(res.occurrence.structure_id,tid)
        self.assertIs(res.occurrence.lexical_slots[0],ambiguous)

    def test_backtrack_earlier_reading_when_later_agreement_conflicts(self):
        # Regression: greedy _fill() chose masculine at position 0 and
        # wrongly rejected a grammatical feminine alternative at position 1.
        grammar=Grammar([GrammarRule(
            "clause",(sym("PRONOUN",gender="?g"),sym("V",gender="?g")),
            sym("CLAUSE"))])
        row=sample("she sings",{"gender":"feminine"},{"gender":"feminine"})
        engine,tid,_=learn(grammar,row)
        first=row.candidates[0]
        wrong=LexicalCandidate(first.span_start,first.span_end,
            first.surface,"wrong-reading","PRONOUN",
            FeatureStructure.build({"gender":"masculine"}),score=200.0)
        replay=LexicalLattice(row.text,row.tokens,(wrong,)+row.candidates)
        with patch.object(PredictiveParser,"_reduce",side_effect=AssertionError), \
             patch.object(PredictiveParser,"_materialize",side_effect=AssertionError):
            found=engine.replay(replay)
        self.assertTrue(found.complete,found.reason)
        self.assertEqual(found.occurrence.structure_id,tid)
        self.assertEqual(found.occurrence.lexical_slots[0].lemma,"she")

    def test_ninth_lexical_reading_is_not_artificially_excluded(self):
        grammar=Grammar([GrammarRule(
            "clause",(sym("PRONOUN",gender="feminine"),sym("V")),
            sym("CLAUSE"))])
        source=sample("she sings",{"gender":"feminine"},{})
        engine,tid,_=learn(grammar,source)
        base=source.candidates[0]
        wrong=tuple(LexicalCandidate(base.span_start,base.span_end,
            base.surface,"bad"+str(i),"PRONOUN",
            FeatureStructure.build({"gender":"masculine"}),score=100-i)
            for i in range(9))
        replay=LexicalLattice(source.text,source.tokens,wrong+source.candidates)
        result=engine.replay(replay)
        self.assertTrue(result.complete,result.reason)
        self.assertEqual(result.occurrence.structure_id,tid)
        self.assertEqual(result.occurrence.lexical_slots[0].lemma,"she")

    def test_index_pagination_checks_template_beyond_first_32(self):
        grammar=Grammar([GrammarRule(
            "clause",(sym("PRONOUN"),sym("V")),sym("CLAUSE"))])
        source=sample("they sing",{}, {})
        engine,tid,_=learn(grammar,source)
        # Simulate many same-POS patterns already in the structural index,
        # all of which require unsupported plans. The genuine plan is at
        # the end: old code stopped at the first 32 and claimed a miss.
        from research.verbnet_lr.positional_template_index import PositionalTemplateIndex
        idx=PositionalTemplateIndex()
        engine.plans=[None]*40+[engine.plans[0]]
        for i in range(41):
            idx.add(("PRONOUN","V"),i)
        engine.index._positional_index=idx
        result=engine.replay(source,max_templates_checked=8)
        self.assertTrue(result.complete,result.reason)
        self.assertEqual(result.occurrence.structure_id,40)
        self.assertGreater(result.checked_templates,32)
        self.assertTrue(result.incomplete is False)

    def test_lexical_ambiguities_remain_accessible_for_layer2(self):
        grammar=Grammar([GrammarRule(
            "clause",(sym("PRONOUN"),sym("V")),sym("CLAUSE"))])
        row=sample("they sing",{}, {})
        engine,_,_=learn(grammar,row)
        alternative=LexicalCandidate(0,4,"they","other","PRONOUN",
                                     FeatureStructure.empty(),score=1)
        replay=LexicalLattice(row.text,row.tokens,row.candidates+(alternative,))
        result=engine.replay(replay)
        self.assertTrue(result.complete)
        self.assertEqual(len(result.occurrence.lexical_alternatives[0]),2)


if __name__=="__main__":
    unittest.main()
