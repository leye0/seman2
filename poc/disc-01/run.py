#!/usr/bin/env python3
"""DISC-01: inspect actual IsaNLP RST gumrrg outputs."""
import hashlib,json,platform,time,traceback
from datetime import datetime,timezone
from pathlib import Path
from isanlp_rst.parser import Parser
from isanlp_rst.utils.serialization import tree_to_dict

P=Path(__file__).resolve().parent; O=P/'output'
def walk(n):
 yield n
 for k in ('left','right'):
  if k in n: yield from walk(n[k])
def main():
 fs=json.loads((P/'fixtures.json').read_text()); started=time.perf_counter(); parser=Parser(hf_model_name='tchewik/isanlp_rst_v3',hf_model_version='gumrrg',cuda_device=-1); load_s=time.perf_counter()-started; out=[]
 for f in fs:
  t=time.perf_counter()
  try:
   native=parser(f['text']); trees=[tree_to_dict(x) for x in native.get('rst',[])]; nodes=[n for tree in trees for n in walk(tree)]; edus=[n for n in nodes if 'left' not in n and 'right' not in n]
   span_ok=all(0<=e['start']<=e['end']<=len(f['text']) and f['text'][e['start']:e['end']]==e.get('text') for e in edus)
   out.append({'fixture':f,'status':'parsed' if trees else 'empty_result','trees':trees,'edus':edus,'node_count':len(nodes),'relation_labels':sorted({n.get('relation') for n in nodes if n.get('relation') and n.get('relation')!='elementary'}),'nuclearities':sorted({n.get('nuclearity') for n in nodes if n.get('nuclearity')}),'scores':[n['proba'] for n in nodes if 'proba' in n],'edu_spans_reconstruct_source':span_ok,'parse_seconds':time.perf_counter()-t})
  except Exception as e:
   out.append({'fixture':f,'status':'failure','error_type':type(e).__name__,'error':str(e),'traceback':traceback.format_exc(),'parse_seconds':time.perf_counter()-t})
 parsed=[r for r in out if r['status']=='parsed']; invalid=next(r for r in out if r['fixture']['id']=='empty-adversarial')
 oracle={'six_nonempty_inputs_parsed':len(parsed)>=6,'all_edu_spans_exact':all(r['edu_spans_reconstruct_source'] for r in parsed),'empty_input_not_silently_parsed':invalid['status']!='parsed'}
 summary={'fixture_count':len(out),'parsed_count':len(parsed),'failure_or_empty_count':len(out)-len(parsed),'language_counts':{x:sum(r['fixture']['language']==x for r in out) for x in ('en','fr','und')},'edu_count':sum(len(r.get('edus',[])) for r in out),'relation_labels':sorted({v for r in parsed for v in r['relation_labels']}),'nuclearities':sorted({v for r in parsed for v in r['nuclearities']}),'score_count':sum(len(r.get('scores',[])) for r in out),'model_load_seconds':load_s,'oracle':oracle,'verdict':'GO_WITH_EXPLICIT_OUTPUT_AND_FAILURE_CONTRACT' if all(oracle.values()) else 'PARTIAL_OUTPUT_OR_FAILURE_CONTRACT_GAP'}
 O.mkdir(parents=True,exist_ok=True)
 raw={'fixtures':[{'id':r['fixture']['id'],'trees':r.get('trees'),'error':r.get('error')} for r in out]}
 for n,v in [('results.json',out),('summary.json',summary),('raw/serialized-rst.json',raw),('versions-and-parameters.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'model':'tchewik/isanlp_rst_v3','revision':'gumrrg','device':'cpu','isanlp_rst_source_commit':'cc8789f44c1341c3e7752b472634d75e81b62518','offsets':'Unicode code points, zero-based, end-exclusive','fixture_sha256':hashlib.sha256((P/'fixtures.json').read_bytes()).hexdigest()})]:
  q=O/n; q.parent.mkdir(parents=True,exist_ok=True); q.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"DISC-01: {len(parsed)}/{len(out)} parsed; {summary['edu_count']} EDUs; {len(summary['relation_labels'])} relation labels; {summary['score_count']} scores")
if __name__=='__main__': main()
