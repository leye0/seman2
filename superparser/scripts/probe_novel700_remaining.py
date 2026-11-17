"""One-time bounded diagnostic for the frozen 12 residual Novel-700 cases.
Use only canonical parse_corpus_case, source-preserving spans, and fixed budgets.
"""
import os, json, signal
from pathlib import Path
from scripts.novel_ladder import LADDER,load_sources,read_ladder
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from seman_parser.engine import Parser,ParserResources
from scripts.audit_novel_tree_quality import display_tree

IDS=(624,625,639,643,647,648,649,660,661,669,672,691)
def main():
  data=Path(__file__).resolve().parents[1]/'data'
  parser=Parser(ParserResources.from_dir(data,wordnet_dict=Path(os.environ['WORDNET_DICT'])),cache_size=0,max_items=50000)
  cohorts,_,_=read_ladder(LADDER,load_sources())
  cases={c['ladder_index']:c for _,rows in cohorts for c in rows}
  for idx in IDS:
    c=cases[idx]
    print('\n===== N%s ====='%idx,flush=True)
    print('SOURCE:',repr(c['source_text']),flush=True)
    print('PARAGRAPH:',c.get('structural_paragraph_index'),'SPAN:',c.get('structural_core_source_span'),flush=True)
    for sc in c.get('structural_constituents',[]):
      print('PREANALYSIS:',str(sc)[:300],flush=True)
    def timeout(signum,frame):raise TimeoutError('10s per-case limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(10)
    try:
      prepared,lattice,result=parse_corpus_case(parser,c,max_items=50000,kbest_work_limit=500000)
      root=result.best()
      keep=('forest_nodes','budget_exceeded','kbest_budget_exceeded','kbest_work_units','partial_states','partial_proposals','structural_root_nodes','saturation_top_rules','saturation_top_categories')
      print('RESULT:',json.dumps({'completed':result.completed,'status':root.rule_id if root else None,'stats':{k:result.stats.get(k) for k in keep},'tokens':[(t.text,t.start,t.end) for t in lattice.tokens]}),flush=True)
      for t in lattice.tokens:
        cs=lattice.covering(t.start,t.end)
        print('LEX',t.text,' '.join('%s:%s'%(x.category,x.features.as_dict().get('vform','')) for x in cs[:12]),flush=True)
      for rank,tree in enumerate(result.alternatives(limit=2)):
        print('TREE',rank, '\n'.join(display_tree(tree,prepared.analysis_text))[:6500],flush=True)
    except Exception as e:
      print('FAIL:',type(e).__name__,str(e),flush=True)
    finally:signal.alarm(0)

FRAGMENTS = {"624": [My rage was without bounds","I sprang on him","the feelings","all the feelings","one being","the existence of another","against the existence of another","on him","impelled by all the feelings"],"625": [I thank you","all that you mention is nothing to me","there is no comfort","on the whole earth","no comfort","I am capable of receiving","the whole earth","I am capable"],"639": [there's something under that","something under that","no doubt","bad or good","under that","Jim"],"643": [what shall we do?","Where is he wounded?","we cried","Oh, doctor","doctor"],"647": [The guineas","the scarcest","my mother","how to make her count","her count","with these","these slights"],"648": [we were both groping downstairs","the empty chest","the candle","by the empty chest","we had opened the door","the next","in full retreat","the door"],"649": [it was remarkable","these slights","he bore these slights","with all","with what unwearying politeness","he kept on trying to ingratiate himself with all","to ingratiate himself with all"],"660": [my dear Daisy","will you mind my calling you Daisy?","my calling you Daisy","you mind my calling you Daisy","Not I!"],"661": [shall you see her?","d’ye think?","Davy","Mas’r Davy"],"669": [Mrs. Crupp said","the range","come and look at the range","a fish-kittle","would I only come and look at the range?"],"672": [I wish there was not.","I have almost forgotten","there is anything to do in the world","anything to do in the world","on the sea","I wish there was not","to go out tossing on the sea here"],"691": [I am grieved indeed","grieved--shocked","is it certain?","But is it certain--absolutely certain?","cried Darcy"]};
def fragments():
  data=Path(__file__).resolve().parents[1]/'data'
  parser=Parser(ParserResources.from_dir(data,wordnet_dict=Path(os.environ['WORDNET_DICT'])),cache_size=0,max_items=50000)
  for idx,parts in FRAGMENTS.items():
    for text in parts:
      scores={}
      for category in ('NP','PP','VP','CLAUSE','ADJP','SPEECH-TAG'):
        try:
          gram=parser._dialogue_vector_grammar if category=='SPEECH-TAG' else parser._vector_grammar
          result=gram.parse_lattice(parser._lattice_for_text(text),goal_category=category,max_items=2500,kbest_work_limit=25000)
          b=result.best()
          if b is not None: scores[category]=b.rule_id
        except Exception as e: scores[category]=type(e).__name__
      print('FRAGMENT',idx,repr(text),scores,flush=True)

if __name__=='__main__':fragments()
