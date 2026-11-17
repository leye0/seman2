"""Source-anchored residual Novel-700 repairs: source, independent grammatical controls,
rank-one constituents and relations at the original 50k/500k budgets.
"""
import os
import unittest
from pathlib import Path
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book,extract
from scripts.novel_ladder import LADDER,load_sources,read_ladder
from seman_parser.engine import Parser,ParserResources,ParseReport

ROOT=Path(__file__).resolve().parents[1]
WORDNET=Path(os.environ.get('WORDNET_DICT',''))
BOOK=Book(999,'Independent grammatical controls','Test','syntax')

class Novel700ResidualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not WORDNET.is_dir(): raise RuntimeError('WordNet 3.0 required')
        cls.parser=Parser(ParserResources.from_dir(ROOT/'data',wordnet_dict=WORDNET),cache_size=0)
        cohorts,_,_=read_ladder(LADDER,load_sources())
        cls.cases={c['ladder_index']:c for _,rows in cohorts for c in rows}
    def parse(self,source):
        if isinstance(source,int):c=self.cases[source]
        else:
            cases,_=extract(BOOK,source,length_min=1,length_max=70)
            self.assertEqual(len(cases),1)
            c=cases[0]
        prepared,lattice,r=parse_corpus_case(self.parser,c,max_items=50000,kbest_work_limit=500000)
        self.assertEqual(prepared.analysis_text,c['source_text'])
        return prepared,lattice,r
    def test_n624_source_and_controls(self):
        from seman_parser.scoped_novel_700 import N624_PARATAXIS
        positive=('His anger was without bounds; he sprang on her, impelled by '
                  'all the feelings which can arm one being against the existence of another.')
        negative=('His anger was without bounds; he sprang on her, impelled by '
                  'all the feelings which can arm one being against the existence of another?')
        for text,must in ((624,True),(positive,True),(negative,False)):
            with self.subTest(text=str(text)[:40]):
                prepared,lattice,result=self.parse(text)
                root=result.best()
                if not must:
                    self.assertTrue(root is None or root.rule_id!=N624_PARATAXIS)
                    continue
                self.assertTrue(result.completed)
                self.assertIsNotNone(root)
                self.assertEqual(root.rule_id,N624_PARATAXIS)
                self.assertEqual((root.start,root.end),(0,len(prepared.analysis_text)))
                self.assertEqual([c.category for c in root.children],
                                 ['CLAUSE','SEMICOLON','CLAUSE','COMMA','PARTICIPIAL-SUPPLEMENT','SPEECH-STOP'])
                self.assertEqual(root.children[0].rule_id,'clause_np_vp')
                self.assertEqual(root.children[2].rule_id,'clause_np_vp')
                self.assertFalse(result.stats.get('budget_exceeded'))
                self.assertFalse(result.stats.get('kbest_budget_exceeded'))
                package=ParseReport(result,self.parser._quoted_sentence_resources,lattice).best_semantic_graph()
                self.assertIsNotNone(package)
                edges={(e['relation'],e['source'],e['target']) for e in package['graph']['relations']}
                handles=package['handles']
                self.assertIn(('PARATAXIS',handles['first'],handles['second']),edges)
                self.assertIn(('SUPPLEMENT',handles['second'],handles['depictive']),edges)

if __name__=='__main__': unittest.main()
