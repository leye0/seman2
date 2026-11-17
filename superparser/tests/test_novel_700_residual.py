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
                self.assertEqual(root.children[0].rule_id,'segment_interface')
                self.assertEqual(root.children[2].rule_id,'segment_interface')
                self.assertFalse(result.stats.get('budget_exceeded'))
                self.assertFalse(result.stats.get('kbest_budget_exceeded'))
                package=ParseReport(result,self.parser._quoted_sentence_resources,lattice).best_semantic_graph()
                self.assertIsNotNone(package)
                edges={(e['relation'],e['source'],e['target']) for e in package['graph']['relations']}
                handles=package['handles']
                self.assertIn(('PARATAXIS',handles['first'],handles['second']),edges)
                self.assertIn(('SUPPLEMENT',handles['second'],handles['depictive']),edges)


    def test_n643_split_questions_source_and_controls(self):
        from seman_parser.scoped_novel_700 import N643_SPLIT_QUESTIONS
        positive='"Oh, captain," we cried, "what shall we do? Where is she wounded?"'
        negative='"Oh, captain," we cried, "what shall we do Where is she wounded?"'
        for text,must in ((643,True),(positive,True),(negative,False)):
            with self.subTest(text=str(text)[:45]):
                prepared,lattice,result=self.parse(text)
                root=result.best()
                if not must:
                    self.assertTrue(root is None or root.rule_id!=N643_SPLIT_QUESTIONS)
                    continue
                self.assertTrue(result.completed)
                self.assertIsNotNone(root)
                self.assertEqual(root.rule_id,N643_SPLIT_QUESTIONS)
                self.assertEqual((root.start,root.end),(0,len(prepared.analysis_text)))
                self.assertEqual([c.category for c in root.children],
                    ['OPEN-QUOTE','INTERJECTION','COMMA','NP','COMMA','CLOSE-QUOTE',
                     'SPEECH-TAG','COMMA','OPEN-QUOTE','CLAUSE','CLAUSE','CLOSE-QUOTE'])
                self.assertFalse(result.stats.get('budget_exceeded'))
                package=ParseReport(result,self.parser._quoted_sentence_resources,lattice).best_semantic_graph()
                self.assertIsNotNone(package)
                handles=package['handles']
                edges={(e['relation'],e['source'],e['target']) for e in package['graph']['relations']}
                self.assertIn(('QUESTION_SEQUENCE',handles['question1'],handles['question2']),edges)
                self.assertIn(('REPORTED_CONTENT',handles['reporter'],handles['question2']),edges)

    def test_n648_progressive_source_and_controls(self):
        from seman_parser.scoped_novel_700 import N648_PROGRESSIVE
        positive=('Next moment we were both groping downstairs, leaving the lantern '
                  'by the empty chest; and the next we had opened the gate and were in full retreat.')
        negative=('Next moment we were both groping downstairs, leaving the lantern '
                  'by the empty chest; and the next we has opened the gate and were in full retreat.')
        for text,must in ((648,True),(positive,True),(negative,False)):
            with self.subTest(text=str(text)[:45]):
                prepared,lattice,result=self.parse(text)
                root=result.best()
                if not must:
                    self.assertTrue(root is None or root.rule_id!=N648_PROGRESSIVE)
                    continue
                self.assertTrue(result.completed)
                self.assertIsNotNone(root)
                self.assertEqual(root.rule_id,N648_PROGRESSIVE)
                self.assertEqual((root.start,root.end),(0,len(prepared.analysis_text)))
                self.assertEqual([c.category for c in root.children],
                    ['ADJ','N','CLAUSE','COMMA','V','NP','PP','SEMICOLON','COORD',
                     'NP','CLAUSE','COORD','COPULA','PP','SPEECH-STOP'])
                self.assertFalse(result.stats.get('budget_exceeded'))
                package=ParseReport(result,self.parser._quoted_sentence_resources,lattice).best_semantic_graph()
                self.assertIsNotNone(package)
                handles=package['handles']
                edges={(e['relation'],e['source'],e['target']) for e in package['graph']['relations']}
                for relation,left,right in (
                    ('SUPPLEMENT','first','leaving'),('THEME','leaving','candle'),
                    ('PARATAXIS','first','second'),('STATE','were','retreat')):
                    self.assertIn((relation,handles[left],handles[right]),edges)



    def verify_new_source_plan(self, idx, positive, negative, rule_id, relations,
                               expected_children=None):
        for source,must in ((idx,True),(positive,True),(negative,False)):
            with self.subTest(index=idx,source=str(source)[:50]):
                prepared,lattice,result=self.parse(source)
                root=result.best()
                if not must:
                    self.assertTrue(root is None or root.rule_id!=rule_id)
                    continue
                self.assertTrue(result.completed, (idx,result.stats))
                self.assertIsNotNone(root)
                self.assertEqual(root.rule_id,rule_id)
                self.assertEqual((root.start,root.end),(0,len(prepared.analysis_text)))
                self.assertFalse(result.stats.get('budget_exceeded'))
                self.assertFalse(result.stats.get('kbest_budget_exceeded'))
                if expected_children:
                    self.assertEqual([c.category for c in root.children],expected_children)
                package=ParseReport(result,self.parser._quoted_sentence_resources,lattice).best_semantic_graph()
                self.assertIsNotNone(package)
                handles=package['handles']
                edges={(e['relation'],e['source'],e['target']) for e in package['graph']['relations']}
                for relation,left,right in relations:
                    self.assertIn((relation,handles[left],handles[right]),edges)
                for node in package['graph']['nodes']:
                    if node.get('span') is not None and node.get('surface') is not None:
                        a,b=node['span']
                        self.assertEqual(node['surface'],prepared.analysis_text[a:b])

    def test_n625_existential_relative_and_semicolon(self):
        from seman_parser.scoped_novel_700 import N625_EXISTENTIAL
        positive=('"I thank him, but all that you mention is nothing to me; '
                  'on the whole earth there is no comfort which I am capable of receiving."')
        negative=('"I thank him, but all that you mentions is nothing to me; '
                  'on the whole earth there is no comfort which I am capable of receiving."')
        self.verify_new_source_plan(625,positive,negative,N625_EXISTENTIAL,
            [('CONTRAST','thank','copular'),('PARATAXIS','copular','existent')],
            ['OPEN-QUOTE','CLAUSE','COMMA','COORD','RELATIVE-COPULAR',
             'SEMICOLON','EXISTENTIAL-RELATIVE','SPEECH-STOP','CLOSE-QUOTE'])

    def test_n639_dashed_reformulation(self):
        from seman_parser.scoped_novel_700 import N639_APPOSITIVE
        positive=('"And there\'s something under that, no doubt--something, surely, '
                  'under that, Ben--bad or good."')
        negative=('"And there\'s something under that, no doubt--something, surely, '
                  'under that, Ben--bad or goods."')
        self.verify_new_source_plan(639,positive,negative,N639_APPOSITIVE,
            [('NEGATION','doubt','no'),('APPOSITION','existential','something'),
             ('ATTRIBUTE','something','qualities')])

    def test_n672_source_quoted_two_sentences_and_wish(self):
        from seman_parser.scoped_novel_700 import N672_WISH
        positive=('‘I have almost forgotten that there is something to do in the world '
                  'but to go out tossing on the sea here. I wish there was not.’')
        negative=('‘I have almost forgotten that there are anything to do in the world '
                  'but to go out tossing on the sea here. I wish there was not.’')
        self.verify_new_source_plan(672,positive,negative,N672_WISH,
            [('DISCOURSE_SEQUENCE','first','wish'),('ANAPHORIC_REPRISE','wish','first')],
            ['OPEN-QUOTE','FIRST-SPOKEN-CLAUSE','CLAUSE','CLOSE-QUOTE'])



    def test_n647_superlative_and_instrument_cleft(self):
        from seman_parser.scoped_novel_700 import N647_CLEFT
        positive=('The coins, too, were about the scarcest, and it was with these only '
                  'that my mother knew how to make her count.')
        negative=('The coins, too, was about the scarcest, and it was with these only '
                  'that my mother knew how to make her count.')
        self.verify_new_source_plan(647,positive,negative,N647_CLEFT,
            [('THEME','were','guineas'),('ATTRIBUTE','were','scarcest'),
             ('CONJUNCT','were','cleft')])
        for source in (647,positive):
            with self.subTest(source=str(source)[:35],detail='bare-causative'):
                prepared,lattice,result=self.parse(source)
                root=result.best()
                self.assertIsNotNone(root)
                cleft=next(c for c in root.children if c.category=='FOCUSED-CLEFT')
                causative=next(c for c in cleft.children if c.category=='BARE-CAUSATIVE')
                self.assertEqual([c.category for c in causative.children],['V','NP','V'])
                self.assertEqual([prepared.analysis_text[c.start:c.end]
                                  for c in causative.children],['make','her','count'])
                self.assertEqual(causative.children[0].lexical_candidate.lemma,'make')
                self.assertEqual(causative.children[2].lexical_candidate.lemma,'count')
                package=ParseReport(result,self.parser._quoted_sentence_resources,lattice).best_semantic_graph()
                h=package['handles']
                edges={(e['relation'],e['source'],e['target']) for e in package['graph']['relations']}
                for rel,left,right in (('CAUSATIVE','make','count'),
                                       ('PATIENT','make','her'),('AGENT','count','her')):
                    self.assertIn((rel,h[left],h[right]),edges)

    def test_n649_parallel_interrogative_manner(self):
        from seman_parser.scoped_novel_700 import N649_PARALLEL
        positive=('Indeed, it was remarkable how well he bore these insults and '
                  'with what unwearying politeness he kept on trying to ingratiate himself with all.')
        negative=('Indeed, it was remarkable how well he bore these insults and '
                  'with what unwearying politeness he keeps on trying to ingratiate himself with all.')
        self.verify_new_source_plan(649,positive,negative,N649_PARALLEL,
            [('CONTENT','remark','bore'),('MANNER','bore','well'),
             ('PARALLEL_MANNER','bore','manner')])

    def test_n660_negative_minor_vocative_and_modal_gerund(self):
        from seman_parser.scoped_novel_700 import N660_GERUND_QUESTION
        positive='‘Not I! my dear Alice--will you mind my calling you Alice?’'
        negative='‘Not I! my dear Alice--will you mind my calling you Alice!’'
        self.verify_new_source_plan(660,positive,negative,N660_GERUND_QUESTION,
            [('DISCOURSE_SEQUENCE','minor','question'),('VOCATIVE','question','vocative')])

    def test_n661_preserve_dialectal_title_and_epistemic_tag(self):
        from seman_parser.scoped_novel_700 import N661_DIALECTAL
        positive='‘Mas’r John, shall you see him, d’ye think?’'
        negative='‘Mas’r John, shall you sees him, d’ye think?’'
        self.verify_new_source_plan(661,positive,negative,N661_DIALECTAL,
            [('ADDRESS','see','name'),('AGENT','see','you'),
             ('THEME','see','her'),('EPISTEMIC_TAG','see','think')])

    def test_n669_as_to_topic_reporter_and_coordinated_question(self):
        from seman_parser.scoped_novel_700 import N669_TOPICAL_REPORT
        positive='As to a fish-kettle, Mrs. Smith said, well! would I only come and look at the range?'
        negative='As to a fish-kettle, Mrs. Smith said, well! would I only comes and look at the range?'
        self.verify_new_source_plan(669,positive,negative,N669_TOPICAL_REPORT,
            [('TOPIC','report','topic'),('REPORTED_CONTENT','report','question')])

    def test_n691_two_quotations_with_affect_and_emphatic_question(self):
        from seman_parser.scoped_novel_700 import N691_INTERCALATED
        positive='“I am grieved indeed,” cried Henry; “grieved--shocked. But is it certain--absolutely certain?”'
        negative='“I am grieved indeed,” cried Henry; “grieved--shocked. But are it certain--absolutely certain?”'
        self.verify_new_source_plan(691,positive,negative,N691_INTERCALATED,
            [('REPORTED_CONTENT','report','first'),('DISCOURSE_REPRISE','first','affect'),
             ('DISCOURSE_SEQUENCE','affect','question')])

if __name__=='__main__': unittest.main()
