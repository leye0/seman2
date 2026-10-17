"""Partial grammar reductions are retained even if enclosing CLAUSE fails."""
import unittest

from seman_parser.engine import ParserResources
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.features import FeatureStructure
from seman_parser.lexicon import Lexicon, parse_entry
from seman_parser.segmentation import build_lattice
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from research.verbnet_lr.partial_structure_memory import PartialStructureMemory


def S(cat):
    return RuleSymbol(cat,FeatureStructure.empty())


class PartialGrammarTests(unittest.TestCase):
    def setUp(self):
        grammar=Grammar([
            GrammarRule("clause", (S("NP"),S("VP")), S("CLAUSE")),
            GrammarRule("np", (S("DET"),S("N")), S("NP")),
            GrammarRule("vp", (S("V"),), S("VP")),
        ])
        entries=[]
        for cat, words in (
            ("DET",("the","a")),
            ("N",("dog","cat")),
            ("V",("eats","sleeps")),
            ("ADV",("loudly",))):
            for w in words:
                entries.append(parse_entry({
                    "lemma":w,
                    "surfaces":[w],
                    "senses":[{"id":w+cat,"category":cat,
                               "features":{},"score":1.0}]
                }))
        self.resources=ParserResources(grammar,Lexicon(entries),None)
        self.reader=SemanCompiledReader(self.resources,token_only_lattice=True)

    def test_failed_longer_sentence_still_returns_grammar_reductions(self):
        sentence="The dog eats loudly."
        lattice=build_lattice(sentence,self.resources.lexicon,multiword_max=1)
        ordinary=self.reader.parse(sentence,lattice=lattice)
        report=self.reader.parse(sentence,lattice=lattice,capture_partials=True)
        self.assertFalse(ordinary.complete)
        self.assertFalse(report.complete)
        self.assertEqual(ordinary.partial_constituents,())
        self.assertEqual(report.outcome.reason,ordinary.outcome.reason)
        self.assertTrue(any(i.category=="NP" and i.rule_id=="np"
                            for i in report.partial_constituents))
        self.assertFalse(report.partial_truncated)

    def test_provisional_partial_revalidates_on_different_words(self):
        text="The dog eats loudly."
        lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
        failed=self.reader.parse(text,lattice=lattice,capture_partials=True)
        self.assertFalse(failed.complete)
        mem=PartialStructureMemory(self.resources,min_tokens=2,max_tokens=5)
        stats=mem.observe(failed.partial_constituents,lattice,
                          sentence_id=1,failed=True)
        self.assertGreater(stats["unique_added"],0)
        other=build_lattice("A cat sleeps.",self.resources.lexicon,
                            multiword_max=1)
        matched=mem.match(other)
        self.assertTrue(matched.grammar_validated_windows)
        self.assertTrue(any(category=="NP" for _,_,category
                            in matched.matched_spans))
        # No complete CLAUSE is accepted by learning a fragment alone.
        self.assertEqual(mem.summary()["counters"][
            "failed_sentences_with_partial_evidence"],1)

    def test_two_different_sentences_reuse_a_tree_without_word_identity(self):
        memory=PartialStructureMemory(self.resources)
        for num,text in enumerate(("The dog eats loudly.",
                                    "A cat sleeps loudly."),1):
            lattice=build_lattice(text,self.resources.lexicon,multiword_max=1)
            report=self.reader.parse(text,lattice=lattice,capture_partials=True)
            self.assertFalse(report.complete)
            stats=memory.observe(report.partial_constituents,lattice,
                                 sentence_id=num,failed=True)
            if num==2:
                self.assertTrue(stats["repeated"])
        self.assertGreater(memory.summary()["counters"][
            "failed_sentences_with_reused_partial"],0)

    def test_capture_is_opt_in_and_bounded(self):
        lattice=build_lattice("The dog eats loudly.",
                              self.resources.lexicon,multiword_max=1)
        result=self.reader.parse(lattice.text,lattice=lattice,
                                 capture_partials=True,max_partial_constituents=1)
        self.assertEqual(len(result.partial_constituents),1)
        self.assertTrue(result.partial_truncated)
        with self.assertRaises(ValueError):
            self.reader.parse(lattice.text,lattice=lattice,
                              capture_partials=True,max_partial_constituents=0)


if __name__=="__main__":
    unittest.main()
