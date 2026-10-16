"""Guardrails for an intentionally tiny structural tie-break memory."""
import unittest
from research.verbnet_lr.sparse_ambiguity import Conflict, SparseAmbiguityMemory


def conflict(parent="CLAUSE", lexical=("N", "DET")):
    return Conflict("reduce_vs_extend", parent, "VP", ("NP", "$REDUCE"),
                    next_categories=lexical, caller_expectations=("NP",))


class SparseAmbiguityTests(unittest.TestCase):
    def test_no_self_training_and_abstention_until_support(self):
        memory = SparseAmbiguityMemory()
        site = conflict()
        self.assertFalse(memory.observe(site, "$REDUCE", source="parser_completion"))
        for _ in range(7):
            self.assertTrue(memory.observe(site, "$REDUCE", source="gold"))
        self.assertIsNone(memory.hint(site))
        memory.observe(site, "$REDUCE", source="verified_correction")
        self.assertEqual(memory.hint(site), "$REDUCE")

    def test_grammar_only_context_not_word_or_order(self):
        a = Conflict("reduce_vs_extend", "CLAUSE", "VP", ("$REDUCE", "NP"),
                     next_categories=("DET", "N"), caller_expectations=("NP", "NP"))
        self.assertEqual(a, conflict())
        memory = SparseAmbiguityMemory()
        for _ in range(8):
            memory.observe(a, "NP", source="gold")
        self.assertEqual(memory.hint(conflict()), "NP")
        self.assertIsNone(memory.hint(conflict(parent="NP")))
        self.assertIsNone(memory.hint(conflict(lexical=("PRONOUN",))))

    def test_mixed_evidence_never_invents_edges(self):
        memory = SparseAmbiguityMemory()
        for _ in range(5):
            memory.observe(conflict(), "NP", source="gold")
            memory.observe(conflict(), "$REDUCE", source="gold")
        self.assertIsNone(memory.hint(conflict()))
        self.assertFalse(memory.observe(conflict(), "UNKNOWN_EDGE", source="gold"))
        with self.assertRaises(ValueError):
            Conflict("test", "CLAUSE", "VP", ("NP",))

    def test_eviction_and_adaptation_are_bounded(self):
        memory = SparseAmbiguityMemory(max_contexts=2, max_votes=12,
                                       min_support=6, min_share=.8)
        first = conflict()
        for _ in range(10):
            memory.observe(first, "$REDUCE", source="gold")
        self.assertEqual(memory.hint(first), "$REDUCE")
        for _ in range(40):
            memory.observe(first, "NP", source="verified_correction")
        self.assertEqual(memory.hint(first), "NP")
        memory.observe(conflict(parent="NP"), "NP", source="gold")
        memory.observe(conflict(parent="VP"), "NP", source="gold")
        self.assertLessEqual(memory.summary()["stored_votes"], 24)
        self.assertEqual(memory.summary()["contexts"], 2)
        self.assertEqual(memory.summary()["evictions"], 1)


if __name__ == "__main__":
    unittest.main()
