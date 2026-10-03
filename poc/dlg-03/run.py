#!/usr/bin/env python3
"""DLG-03: side-by-side, non-fused ERG and Dynamic Syntax analyses."""
import importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
import dynamicsyntax
from delphin import ace
P=Path(__file__).resolve().parent;ROOT=P.parent.parent;O=P/'output'
def dstree(t):return [{'address':str(a),'labels':sorted(str(x)for x in n.labels)}for a,n in sorted(t.items(),key=lambda x:str(x[0]))]
def main():
 fs=json.loads((P/'fixtures.json').read_text());out=[]
 with ace.ACEParser(str(ROOT/'.local/share/erg/erg-2018-x86-64-0.9.34.dat'),executable=str(ROOT/'.local/bin/ace'),cmdargs=['-n','5'])as parser:
  for f in fs:
   er=parser.interact(f['text']);ds=dynamicsyntax.parse(f['ds_text'],'ttr',trace=True)
   erg={'analysis_id':f"erg:{f['id']}",'producer':'ACE_ERG','status':'parsed'if er.results()else'failure','candidate_count':len(er.results()),'candidates':[{'result_id':x.get('result-id'),'mrs':x.get('mrs'),'derivation':x.get('derivation'),'tree':x.get('tree')}for x in er.results()],'tokens':str(er.tokens('initial'))if er.get('tokens')else None}
   dyn={'analysis_id':f"ds:{f['id']}",'producer':'dynamicsyntax-python','status':'parsed'if ds.ok else'failure','semantics':str(ds.semantics)if ds.semantics else None,'incremental_states':[{'step':label,'tree':dstree(tree)}for label,tree in zip(('initial',)+ds.trace_step_labels,ds.trace_trees)],'actions':[{'word':a.word,'action':a.action_name}for a in ds.action_steps]}
   out.append({'fixture':f,'analyses':[erg,dyn],'shared_surface_link_only':{'erg_text':f['text'],'ds_text':f['ds_text']},'semantic_nodes_fused':False,'correspondence_claims':[]})
 matrix=[]
 for r in out:
  e,d=r['analyses'];matrix.append({'fixture_id':r['fixture']['id'],'phenomenon':r['fixture']['phenomenon'],'erg_parsed':e['status']=='parsed','erg_candidate_count':e['candidate_count'],'erg_mrs':any(x['mrs']for x in e['candidates']),'ds_parsed':d['status']=='parsed','ds_incremental_state_count':len(d['incremental_states']),'ds_ttr':d['semantics']is not None,'fused':False})
 assert any(x['ds_incremental_state_count']>1 for x in matrix)and any(x['erg_mrs']for x in matrix)and all(not x['fused']for x in matrix)
 summary={'fixture_count':len(out),'erg_success_count':sum(x['erg_parsed']for x in matrix),'ds_success_count':sum(x['ds_parsed']for x in matrix),'bundles_with_both':sum(x['erg_parsed']and x['ds_parsed']for x in matrix),'semantic_fusion_count':0,'demonstrated_complementarity':['ERG ranked full-sentence HPSG/MRS candidates','Dynamic Syntax word-level trees/actions and TTR'],'verdict':'GO_SEPARATE_COMPLEMENTARY_ANALYSIS_BUNDLE'}
 O.mkdir(parents=True,exist_ok=True)
 for n,v in [('results.json',out),('comparison-matrix.json',matrix),('summary.json',summary),('versions-and-parameters.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'dynamicsyntax':importlib.metadata.version('dynamicsyntax'),'pydelphin':importlib.metadata.version('pydelphin'),'erg':'ERG 2018','max_erg_results':5})]:(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"DLG-03: ERG {summary['erg_success_count']}/{len(out)}, DS {summary['ds_success_count']}/{len(out)}, both {summary['bundles_with_both']}, fusion 0")
if __name__=='__main__':main()
