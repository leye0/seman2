"""Non-regression guards for selective expensive-sentence experiments."""
import unittest
from scripts.benchmark_heavy_sentence_ab import (
    early_filter_eligible, has_quotation, split_plan, quantile, summarize,
)
from seman_parser.segmentation import tokenize


class HeavySentenceTests(unittest.TestCase):
    def test_short_and_quoted_not_selected(self):
        self.assertFalse(early_filter_eligible("John walks.",tokenize("John walks.")))
        self.assertTrue(early_filter_eligible("ordinary",tuple(range(17))))
        for quote in ('"Hello!"','“Hello!”','‘Hello!’'):
            self.assertTrue(has_quotation(quote))
            self.assertFalse(early_filter_eligible(quote,tuple(range(25))))

    def test_split_guard_does_not_call_planner_for_quotes_or_short_text(self):
        class Trap:
            def _clause_plan(self,*args):raise AssertionError("unexpected planner")
        self.assertIsNone(split_plan('"Hello," said Mary, and left, quietly.',
                                     tuple(range(30)),Trap()))
        self.assertIsNone(split_plan("John was quick, polite, and kind.",
                                     tuple(range(10)),Trap()))

    def test_split_rejects_short_segments(self):
        class Fake:
            _coord_surfaces=frozenset(("and","or"))
            def _clause_plan(self,text,tokens):return (((0,3),(4,16)),())
        class Tok:
            def __init__(self,i):
                self.start=i
                self.end=i+1
                self.text="word"
        self.assertIsNone(split_plan("here, there, and elsewhere",
                                     tuple(Tok(i) for i in range(30)),Fake()))

    def test_single_coordination_is_proposed_without_discarding_words(self):
        class Fake:
            _coord_surfaces=frozenset(("and",))
            def _clause_plan(self,*args):
                raise AssertionError("comma planning should not be invoked")
        class Tok:
            def __init__(self,i):
                self.start=i*5
                self.end=i*5+4
                self.text="and" if i==12 else "word"
        tokens=tuple(Tok(i) for i in range(27))
        plan=split_plan("word "*27,tokens,Fake())
        self.assertIsNotNone(plan)
        spans,separators=plan
        self.assertEqual(separators,(tokens[12],))
        self.assertEqual(spans,((tokens[0].start,tokens[11].end),
                                (tokens[13].start,tokens[-1].end)))

    def test_quantile(self):
        self.assertIsNone(quantile([],.5))
        self.assertEqual(quantile([1,3,5,7],.5),4)

    def test_signature_changes_and_rescues_are_reported(self):
        def arm(ms,done,sig):
            return {"ms":ms,"completed":done,"signature":sig,"budget":False}
        a={"band":"04-08","baseline":arm(10,True,"a"),
           "early":arm(11,True,"a"),"split":arm(12,True,"b"),
           "early_eligible":False,"split_eligible":False,"split_route":"not_eligible"}
        b={"band":"25-32","baseline":arm(90,False,None),
           "early":arm(60,True,"c"),"split":arm(90,False,None),
           "early_eligible":True,"split_eligible":True,"split_route":"failed_then_fallback"}
        report=summarize([a,b],[])
        self.assertEqual(report["groups"]["all"]["early"]["rescued"],1)
        self.assertEqual(report["groups"]["all"]["split"]["changed_signature"],1)


if __name__=="__main__":unittest.main()
