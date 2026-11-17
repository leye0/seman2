"""Bounded diagnostic for failed Novel-700 source-scoped compositions."""
import os
from pathlib import Path
from scripts.novel_ladder import LADDER,load_sources,read_ladder
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from seman_parser.engine import Parser,ParserResources
from seman_parser.scoped_novel_700 import (
 plan_n672_wish, plan_n647_cleft, plan_n649_parallel_manner,
 N672_WISH,N647_CLEFT,N649_PARALLEL,
)
from seman_parser.structural_composition import QuotedSentenceComposer

ROOT=Path(__file__).resolve().parents[1]
def main():
 parser=Parser(ParserResources.from_dir(ROOT/'data',wordnet_dict=Path(os.environ['WORDNET_DICT'])),cache_size=0)
 cohorts,_,_=read_ladder(LADDER,load_sources())
 cases={c['ladder_index']:c for _,rows in cohorts for c in rows}
 for idx,planner,rule in ((672,plan_n672_wish,N672_WISH),(647,plan_n647_cleft,N647_CLEFT),(649,plan_n649_parallel_manner,N649_PARALLEL)):
  c=cases[idx]
  prepared,lattice,result=parse_corpus_case(parser,c,max_items=50000,kbest_work_limit=500000)
  text=prepared.analysis_text
  print('CASE',idx,repr(text), 'status',result.completed,flush=True)
  cs=prepared.structural_constituents
  specs=planner(text,cs)
  print('PLANNER',bool(specs),'COMPONENTS',cs,flush=True)
  if not specs: continue
  for cat,a,b,kind,required in specs:
   segment=text[a:b]
   if kind in ('phrase','subject-phrase'):
    try:
     gram=parser._dialogue_vector_grammar if cat=='SPEECH-TAG' else parser._vector_grammar
     pr=gram.parse_lattice(parser._lattice_for_text(segment),goal_category=cat,max_items=5000,kbest_work_limit=60000,beam=parser.beam)
     best=pr.best()
     print('PROOF',cat,repr(segment),best.rule_id if best else None,'flags',pr.stats.get('budget_exceeded'), 'req',required,flush=True)
    except Exception as e:print('PROOF ERROR',cat,repr(segment),repr(e),flush=True)
   else:
    matches=[v for v in lattice.candidates if v.span==(a,b) and v.category==cat]
    print('LEX',cat,repr(segment),kind,'candidates',[(v.lemma,v.features.as_dict()) for v in matches[:3]],'req',required,flush=True)
  comp=parser._quoted_sentence_resources
  print('COMPOSER',type(comp),flush=True)
  try:
   outcome=comp._compose_verified_dialogue_pattern(parser,text,lattice,specs,rule,max_items=50000,kbest_work_limit=500000)
   print('COMPOSE',bool(outcome),outcome.best().rule_id if outcome and outcome.best() else None,flush=True)
  except Exception as e:print('COMPOSE ERROR',type(e).__name__,str(e),flush=True)
if __name__=='__main__':main()
