import unittest
from seman_parser.wsd import WSD

class FakeSynset:
    def name(self): return "sample.n.01"
    def offset(self): return 1
    def pos(self): return "n"
    def lexname(self): return "noun.object"
    def definition(self): return "sample definition"
    def lemmas(self): return []

class WSDAdapterTests(unittest.TestCase):
    def test_passes_exact_context_span_and_lemma(self):
        calls=[]
        def engine(text,a,b,lemma,pos=None):
            calls.append((text,a,b,lemma,pos))
            return [(0.8,FakeSynset())]
        p=WSD(backend=engine)
        report=p.inspect("A sample.",[{"text":"sample","span":[2,8],"lemma":"sample","pos":"NOUN"}])
        self.assertEqual(calls,[("A sample.",2,8,"sample","n")])
        self.assertEqual(report["targets"][0]["prediction"]["id"],"sample.n.01")
        self.assertEqual(report["targets"][0]["prediction"]["score"],0.8)

    def test_no_candidate_and_invalid_span(self):
        p=WSD(backend=lambda *args,**kwargs: [])
        self.assertEqual(p.target("Hello",0,5,"hello","n")["status"],"no_wordnet_candidate")
        with self.assertRaises(ValueError):
            p.target("Hello",0,6,"hello","n")
        with self.assertRaises(ValueError):
            p.inspect("Hello",[{"text":"bad","span":[0,5],"lemma":"hello","pos":"NOUN"}])
