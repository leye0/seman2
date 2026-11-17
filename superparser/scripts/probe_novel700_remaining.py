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
if __name__=='__main__':main()
