#!/usr/bin/env python3
import hashlib,json,platform
from datetime import datetime,timezone
from pathlib import Path
import networkx as nx
P=Path(__file__).resolve().parent;O=P/'output'
def main():
 fs=json.loads((P/'fixtures.json').read_text());out=[]
 for f in fs:
  g=nx.MultiDiGraph();g.add_node(f['id'],kind='conversation',channel=f['channel'])
  for p in f['participants']:g.add_node(p,kind='participant');g.add_edge(p,f['id'],relation='participates_in')
  for i,t in enumerate(f['turns']):
   g.add_node(t['id'],kind='turn',speaker=t['speaker'],raw=t['text'],span=t['span']);g.add_edge(t['speaker'],t['id'],relation='produced');g.add_edge(t['id'],f['id'],relation='contained_in')
   if i:g.add_edge(f['turns'][i-1]['id'],t['id'],relation='precedes_in_source')
   if 'reply_to'in t:g.add_edge(t['id'],t['reply_to'],relation='reply_to')
   for x in t.get('overlaps',[]):g.add_edge(t['id'],x,relation='overlaps_observably')
  reconstructed='\n'.join(t['text'] for t in f['turns']);assert reconstructed==f['source']
  edges=[{'source':a,'target':b,**d}for a,b,d in g.edges(data=True)];forbidden={'communicative_function','intention','belief','commitment'}
  assert not any(forbidden & set(d) for _,d in g.nodes(data=True))
  out.append({'fixture_id':f['id'],'source':f['source'],'source_sha256':hashlib.sha256(f['source'].encode()).hexdigest(),'nodes':[{'id':n,**d}for n,d in g.nodes(data=True)],'edges':edges,'source_reconstructed':True,'pragmatic_inferences_created':0})
 summary={'fixture_count':len(out),'turn_count':sum(len(f['turns'])for f in fs),'participant_count':sum(len(f['participants'])for f in fs),'reply_to_count':sum('reply_to'in t for f in fs for t in f['turns']),'overlap_count':sum(len(t.get('overlaps',[]))for f in fs for t in f['turns']),'pragmatic_inferences_created':0,'verdict':'GO_CONVERSATION_OBSERVATION_WITHOUT_PREMATURE_INTERPRETATION'}
 O.mkdir(parents=True,exist_ok=True)
 for n,v in [('results.json',out),('summary.json',summary),('versions-and-parameters.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'networkx':nx.__version__,'schema':'seman2.conversation-observation-poc.v1'})]:(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"DLG-01: {summary['turn_count']} turns; {summary['reply_to_count']} replies; {summary['overlap_count']} overlaps; 0 pragmatic inference")
if __name__=='__main__':main()
