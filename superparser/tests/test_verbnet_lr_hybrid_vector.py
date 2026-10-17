"""Regression contracts for opt-in C-guided canonical vector parse forest."""
from __future__ import annotations
import unittest
import os
from pathlib import Path

from seman_parser.engine import Parser, ParserResources
from research.verbnet_lr.hybrid_vector import GuidedVectorGrammar, HybridVectorParser

DATA=Path(__file__).resolve().parents[1]/"data"


def structure(node):
    if node is None:return None
    if node.lexical_candidate:
        return (node.category,node.lexical_candidate.category,
                node.lexical_candidate.surface.casefold())
    return (node.category,node.rule_id,tuple(structure(x) for x in node.children))


class HybridVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources=ParserResources.from_dir(DATA,wordnet_dict=os.environ.get('WORDNET_DICT'))
        cls.reference=Parser(resources,cache_size=0)
        cls.hybrid=HybridVectorParser(resources,cache_size=0)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_01_learning_only_original_rules_and_provenance(self):
        training=[
            "John opened the box.",
            "Mary opened the door.",
            "John gave Mary the box.",
            "Mary gave John a book.",
            "The child laughed.",
            "The teacher praised the student.",
        ]
        learned=0
        for i,txt in enumerate(training):
            parsed=self.reference.parse(txt)
            if not parsed.result.completed:continue
            result=self.hybrid.observe(parsed,source_id=f"train-{i}")
            learned+=int(result["learned"])
            duplicate=self.hybrid.observe(parsed,source_id=f"train-{i}")
            self.assertFalse(duplicate["learned"])
        self.assertGreaterEqual(learned,4)
        stats=self.hybrid.compile_guidance()
        self.assertGreater(stats["rules_with_support"],0)
        self.assertGreater(self.hybrid.guidance_summary()["observed_structures"]["training_sentences"],0)
        self.assertEqual(self.hybrid._vector_grammar.rule_support is not None,True)
        self.assertEqual(
            {r.rule.rule_id for r in self.hybrid._vector_grammar.rules},
            {r.rule.rule_id for r in self.reference._vector_grammar.rules}
        )
        self.assertEqual(
            len(self.hybrid._vector_grammar.rules),
            len(self.reference._vector_grammar.rules)
        )

    def test_02_canonical_complete_tree_and_semantics(self):
        for sentence in (
            "John opened the box.", "John gave Mary the box.",
            "The child watched the man with a telescope.",
            "She did not open the window.",
        ):
            with self.subTest(sentence=sentence):
                original=self.reference.parse(sentence)
                guided=self.hybrid.parse(sentence)
                self.assertEqual(original.result.completed,guided.result.completed)
                self.assertTrue(guided.result.completed)
                a=original.result.best()
                b=guided.result.best()
                self.assertIsNotNone(b)
                self.assertEqual(b.category,"CLAUSE")
                self.assertEqual(structure(a),structure(b))
                self.assertEqual(a.syntax.as_dict(),b.syntax.as_dict())
                self.assertIsNotNone(guided.result.shared_forest)
                self.assertIsNotNone(guided.result.lattice)
                self.assertIn("hybrid_guidance",guided.result.stats)
                self.assertIn("event",b.syntax.anchors)
                if "gave" in sentence:
                    roles={r.relation for r in guided.interpret(b).graph.relations}
                    self.assertIn("THEME",roles)
                    self.assertIn("RECIPIENT",roles)

    def test_03_lexical_disjunction_and_negative_acceptance_not_silently_changed(self):
        for sentence in (
            "I saw the man with the telescope.",
            "The dogs barks loudly.",
            "She can read the letter.",
        ):
            with self.subTest(sentence=sentence):
                old=self.reference.parse(sentence).result
                new=self.hybrid.parse(sentence).result
                self.assertEqual(old.completed,new.completed)
                self.assertEqual(
                    {(x.span_start,x.span_end,x.category) for x in old.lattice.candidates},
                    {(x.span_start,x.span_end,x.category) for x in new.lattice.candidates},
                )
                if old.completed:
                    self.assertEqual(structure(old.best()),structure(new.best()))

    def test_04_untrained_is_safe_and_invalid_evidence_is_rejected(self):
        parser=HybridVectorParser(self.reference.resources,cache_size=0)
        blank=parser.compile_guidance()
        self.assertEqual(blank["rules_with_support"],0)
        ref=self.reference.parse("John opened the box.").result
        current=parser.parse("John opened the box.").result
        self.assertEqual(structure(ref.best()),structure(current.best()))
        with self.assertRaises(ValueError):
            parser.observe(ref,source_id="bad",evidence="invented")
        with self.assertRaises(ValueError):
            parser.observe(ref,source_id="",evidence="candidate")

    def test_05_guided_budget_fallback_never_disguises_truncation(self):
        parser=HybridVectorParser(self.reference.resources,cache_size=0,max_items=12)
        report=self.reference.parse("John opened the box.")
        for i in range(2):
            parser.observe(report,source_id=str(i))
        parser.compile_guidance()
        result=parser.parse("John opened the box.").result
        self.assertTrue(result.stats["hybrid_guidance"].get("fallback_after_guided_budget",False))
        self.assertTrue(result.stats["budget_exceeded"])

    def test_06_canonical_full_tree_and_tentative_C_witnesses_coexist(self):
        text="John gave Mary the box."
        full,witnesses=self.hybrid.parse_with_local_witnesses(
            text,min_report_tokens=2,emit_trees=True)
        self.assertTrue(full.result.completed)
        self.assertEqual(full.result.best().category,"CLAUSE")
        self.assertGreaterEqual(witnesses.count_at_least(2),1)
        for hit in witnesses.hits:
            self.assertIsNotNone(hit.tree)
            self.assertEqual(hit.tree.category,hit.category)
            self.assertTrue(hasattr(hit.tree,"syntax"))
            self.assertGreater(hit.tree.end,hit.tree.start)
            self.assertLessEqual(hit.tree.end,len(text))
        self.assertIsNotNone(full.result.shared_forest)
        self.assertEqual(
            structure(self.reference.parse(text).result.best()),
            structure(full.result.best()))


if __name__=="__main__":
    unittest.main()
