"""Sampling is outside parsing, bounded and never automatically gold."""
import unittest
from unittest.mock import patch

from research.verbnet_lr.sampled_teacher import VerificationSamplingQueue
from research.verbnet_lr.full_structure_snap import FullStructureSnapIndex
from seman_parser.engine import ParserResources
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import LexicalCandidate, LexicalLattice, Token


class SamplingQueueTests(unittest.TestCase):
    def lattice(self):
        token = Token(0,0,3,"run")
        candidate = LexicalCandidate(0,3,"run","run","V",FeatureStructure.empty())
        return LexicalLattice("run",(token,),(candidate,))

    def test_exact_tenth_and_bounded_queue(self):
        q=VerificationSamplingQueue(every=10,phase=0,max_pending=1)
        for i in range(35):
            q.enqueue("run",self.lattice())
        self.assertEqual(q.summary()["seen"],35)
        self.assertEqual(q.summary()["sampled"],4)
        self.assertEqual(q.summary()["pending"],1)
        self.assertEqual(q.summary()["dropped"],3)
        self.assertEqual(q.summary()["grammar_witnesses"],0)

    def test_explicit_offline_drain_provenance_not_gold(self):
        grammar=Grammar((GrammarRule(
            "clause_v",(RuleSymbol("V"),),RuleSymbol("CLAUSE")),))
        index=FullStructureSnapIndex(ParserResources(grammar,None,None))
        q=VerificationSamplingQueue(every=10,phase=0)
        for i in range(10):
            q.enqueue("run",self.lattice())
        self.assertEqual(len(index.templates),0)
        with patch("research.verbnet_lr.packed_witness.seek_packed_witness",
                   wraps=None) as teacher:
            teacher.return_value={"status":"UNKNOWN","witness_node":None}
            out=q.drain_teacher(index)
        self.assertEqual(out["unknown_or_rejected"],1)
        self.assertEqual(q.pending,0)
        self.assertEqual(len(index.templates),0)
        q.enqueue("run",self.lattice())
        out=q.drain_teacher(index,max_seconds=1)
        self.assertEqual(out["grammar_witnesses"],1,out)
        self.assertEqual(index.summary()["grammar_witness_templates"],1)
        self.assertEqual(index.summary()["verified_templates"],0)

    def test_fast_reader_only_enqueues_never_runs_teacher(self):
        from unittest.mock import patch
        from research.verbnet_lr.full_structure_snap import SnappingResearchReader
        from types import SimpleNamespace
        rules=Grammar((GrammarRule("clause_v",(RuleSymbol("V"),),
                                   RuleSymbol("CLAUSE")),))
        index=FullStructureSnapIndex(ParserResources(rules,None,None))
        q=VerificationSamplingQueue(every=10,phase=0)
        class Fallback:
            def parse(self,text):
                return SimpleNamespace(complete=False)
        wrapper=SnappingResearchReader(index.resources,index=index,
                                       fallback=Fallback(),sampler=q)
        with patch("seman_parser.segmentation.build_lattice",
                   return_value=self.lattice()), patch(
                   "research.verbnet_lr.packed_witness.seek_packed_witness") as teacher:
            for _ in range(10):
                wrapper.parse("run")
            teacher.assert_not_called()
        self.assertEqual(q.summary()["seen"],10)
        self.assertEqual(q.summary()["pending"],1)

    def test_arguments_rejected(self):
        for kwargs in ({"every":0},{"every":10,"phase":10},
                       {"max_pending":0}):
            with self.assertRaises(ValueError):
                VerificationSamplingQueue(**kwargs)


if __name__=="__main__":
    unittest.main()
