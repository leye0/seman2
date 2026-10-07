#!/usr/bin/env python3
"""DLG-06: minimal typed KoS/TTR-inspired public Dialogue Gameboard."""
from __future__ import annotations
import hashlib,importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
import networkx as nx
P=Path(__file__).resolve().parent;OUT=P/'output';ROOT=P.parents[1]

SCHEMA={"$schema":"https://json-schema.org/draft/2020-12/schema","title":"MinimalPublicDialogueGameboard","type":"object","required":["participants","moves","facts","qud","obligations","pending","dependencies","boundary"],"properties":{"participants":{"type":"array"},"moves":{"type":"array"},"facts":{"type":"array"},"qud":{"type":"array"},"obligations":{"type":"array"},"pending":{"type":"array"},"dependencies":{"type":"array"}}}
REQUIRED_ITEM={"id","record_type","source","status","alternatives","unresolved"}
def item(i,t,source,status='proposed',alternatives=None,unresolved=None,**kw):
 return {"id":i,"record_type":t,"source":source,"status":status,"alternatives":alternatives or [],"unresolved":unresolved or [],**kw}
def validate(dgb):
 errors=[]
 for k in SCHEMA['required']:
  if k not in dgb:errors.append(f'missing:{k}')
 ids=set()
 for collection in ('participants','moves','facts','qud','obligations','pending'):
  for row in dgb[collection]:
   missing=REQUIRED_ITEM-set(row)
   if missing:errors.append(f"{row.get('id',collection)}:missing:{sorted(missing)}")
   if row.get('id') in ids:errors.append(f"duplicate:{row['id']}")
   ids.add(row.get('id'))
 for e in dgb['dependencies']:
  if e['source'] not in ids or e['target'] not in ids:errors.append(f"dangling:{e['id']}")
 return errors
def load_json_with_hash(path):
 raw=path.read_bytes();return json.loads(raw),hashlib.sha256(raw).hexdigest()
def integrated_gameboards():
 dlg01_path=ROOT/'poc/dlg-01/output/results.json';dlg03_path=ROOT/'poc/dlg-03/output/results.json'
 dlg01,dlg01_hash=load_json_with_hash(dlg01_path);dlg03,dlg03_hash=load_json_with_hash(dlg03_path)
 observed=next(row for row in dlg01 if row['conversation_id']=='en-quote-fragment')
 participants=[item(f"obs-{n['id']}",'participant',f"DLG-01:{observed['runtime_artifact_id']}",status='observed',name=n['id'],dialogue_role='observed-participant') for n in observed['nodes'] if n['kind']=='participant']
 participant_ids={p['id'] for p in participants}
 moves=[]
 turn_id_map={}
 for node in observed['nodes']:
  if node['kind']!='turn':continue
  move_id=f"obs-{node['id']}";turn_id_map[node['id']]=move_id
  moves.append(item(move_id,'move',f"DLG-01:{observed['runtime_artifact_id']}",status='observed',speaker=f"obs-{node['speaker']}",addressees=sorted(participant_ids-{f"obs-{node['speaker']}"}),raw=node['raw_text'],source_span=node['span'],source_order=node['source_order']))
 observed_deps=[]
 for index,edge in enumerate(observed['edges']):
  if edge['source'] in turn_id_map and edge['target'] in turn_id_map:
   observed_deps.append({'id':f'obs-d{index}','source':turn_id_map[edge['source']],'target':turn_id_map[edge['target']],'relation':edge['relation']})
 observed_dgb={'schema_version':'dlg-06/1','participants':participants,'moves':moves,'facts':[],'qud':[],'obligations':[],'pending':[],'dependencies':observed_deps,'boundary':{'scope':'observed public topology','claim':'no dialogue act inferred from turn topology'}}

 formal=next(row for row in dlg03 if row['fixture']['id']=='complete')
 bundle=formal['bundle'];analysis_by_producer={row['producer']:row for row in formal['analyses']}
 formal_participant=[item('formal-speaker','participant',f"DLG-03:{formal['runtime_artifact_id']}",status='identified',name='A',dialogue_role='speaker')]
 alternatives=[{'producer':producer,'analysis_ref':bundle['erg_analysis_ref'] if producer=='ACE_ERG' else bundle['dynamic_syntax_analysis_ref'],'status':analysis['status']} for producer,analysis in sorted(analysis_by_producer.items())]
 formal_move=item('formal-m1','move',f"DLG-03:{formal['runtime_artifact_id']}",status='performed',speaker='formal-speaker',addressees=[],raw=formal['fixture']['text'],content_record={'shared_source_observation_ref':bundle['shared_source_observation_ref'],'analysis_bundle_ref':formal['runtime_artifact_id']},alternatives=alternatives,unresolved=['semantic_correspondence'])
 formal_pending=item('formal-n1','pending_content',f"DLG-03:{formal['runtime_artifact_id']}",status='unresolved',content='relation between attributed MRS and TTR analyses',alternatives=alternatives,unresolved=['semantic_correspondence'],supported_by=['formal-m1'])
 formal_dgb={'schema_version':'dlg-06/1','participants':formal_participant,'moves':[formal_move],'facts':[],'qud':[],'obligations':[],'pending':[formal_pending],'dependencies':[{'id':'formal-d1','source':'formal-m1','target':'formal-n1','relation':'leaves_pending'}],'boundary':{'scope':'public formal content candidates','claim':'ERG and Dynamic Syntax stay attributed and unfused'}}
 errors={'observed_topology':validate(observed_dgb),'formal_content':validate(formal_dgb)}
 validations={
  'dlg01_source_hash_bound':hashlib.sha256(observed['source'].encode()).hexdigest()==observed['source_sha256'],
  'dlg01_turns_preserved':len(moves)==2 and all(m['raw']==next(n['raw_text'] for n in observed['nodes'] if n.get('id')==m['id'][4:]) for m in moves),
  'dlg01_no_pragmatic_inference':observed['pragmatic_inferences_created']==0 and not observed_dgb['facts'] and not observed_dgb['qud'],
  'dlg03_both_formal_analyses_consumed':{a['producer'] for a in alternatives}=={'ACE_ERG','dynamicsyntax-python'},
  'dlg03_shared_observation_preserved':formal_move['content_record']['shared_source_observation_ref']==bundle['shared_source_observation_ref'],
  'dlg03_attribution_preserved':{a['analysis_ref'] for a in alternatives}=={bundle['erg_analysis_ref'],bundle['dynamic_syntax_analysis_ref']},
  'dlg03_no_false_fusion':bundle['semantic_nodes_fused'] is False and formal_pending['unresolved']==['semantic_correspondence'],
  'integrated_gameboards_valid':not errors['observed_topology'] and not errors['formal_content'],
 }
 return {'sources':{'dlg01_results_sha256':dlg01_hash,'dlg03_results_sha256':dlg03_hash},'observed_topology_gameboard':observed_dgb,'formal_content_gameboard':formal_dgb,'schema_errors':errors},validations
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 participants=[item('p-alice','participant','fixture:participants',status='identified',name='Alice',dialogue_role='speaker/addressee'),item('p-bob','participant','fixture:participants',status='identified',name='Bob',dialogue_role='speaker/addressee')]
 moves=[
  item('m1','move','turn:t1',status='performed',speaker='p-alice',addressees=['p-bob'],act='question',raw='Quelle couleur est la voiture ?',content_record={'x':{'type':'Entity','value':'car-1'},'c':{'type':'Color','value':None},'constraint':'color(x)=c'}),
  item('m2','move','turn:t2',status='performed',speaker='p-bob',addressees=['p-alice'],act='answer',raw='Rouge, je crois.',content_record={'x':{'type':'Entity','value':'car-1'},'c':{'type':'Color','value':'red'},'judgement':{'type':'ProbabilisticQualifier','value':'uncertain'}},alternatives=[{'color':'crimson','confidence':.25}]),
  item('m3','move','turn:t3',status='performed',speaker='p-alice',addressees=['p-bob'],act='accept',raw="D'accord.",content_record={'target':{'type':'Move','value':'m2'}}),
  item('m4','move','turn:t4',status='performed',speaker='p-bob',addressees=['p-alice'],act='question',raw='Et sa taille ?',content_record={'x':{'type':'Entity','value':None},'s':{'type':'Size','value':None},'constraint':'size(x)=s'},alternatives=[{'x':'car-1'},{'x':'color-swatch-1'}],unresolved=['content_record.x.value']),
 ]
 facts=[item('f1','public_fact','turn:t2',status='proposed',content={'predicate':'color','arguments':['car-1','red']},confidence=.7,supported_by=['m2']),item('f2','public_fact','turn:t3',status='accepted_for_exchange',content={'predicate':'color','arguments':['car-1','red']},confidence=.7,supported_by=['m2','m3'])]
 qud=[item('q1','qud','turn:t1',status='resolved',question={'record_type':'question','fields':{'x':'Entity','c':'Color'},'constraint':'color(x)=c'},raised_by='m1',resolved_by='m2'),item('q2','qud','turn:t4',status='active',question={'record_type':'question','fields':{'x':'Entity','s':'Size'},'constraint':'size(x)=s'},raised_by='m4',alternatives=[{'x':'car-1'},{'x':'color-swatch-1'}],unresolved=['question.fields.x.binding'])]
 obligations=[item('o1','discourse_obligation','turn:t1',status='satisfied',debtor='p-bob',beneficiary='p-alice',expected='answer(q1)',created_by='m1',satisfied_by='m2'),item('o2','discourse_obligation','turn:t4',status='open',debtor='p-alice',beneficiary='p-bob',expected='answer_or_clarify(q2)',created_by='m4')]
 pending=[item('n1','pending_content','turn:t4',status='unresolved',content='referent(m4.x)',alternatives=[{'referent':'car-1','score':.65},{'referent':'color-swatch-1','score':.35}],unresolved=['selected_referent'],supported_by=['m4'])]
 deps=[]
 for i,(a,b,r) in enumerate([('m1','q1','raises'),('q1','o1','creates'),('m2','q1','answers'),('m2','f1','proposes'),('m3','f2','accepts'),('f1','f2','revised_as'),('m4','q2','raises'),('q2','o2','creates'),('m4','n1','leaves_pending')],1):deps.append({'id':f'd{i}','source':a,'target':b,'relation':r})
 dgb={'schema_version':'dlg-06/1','participants':participants,'moves':moves,'facts':facts,'qud':qud,'obligations':obligations,'pending':pending,'dependencies':deps,'constraints':[{'id':'c1','expression':'speaker(move) in participants'},{'id':'c2','expression':'accepted fact requires explicit support'}],'boundary':{'scope':'public interactional context only','not_represented_as':['private belief','private intention','complete cognitive ontology'],'formal_inspiration':['KoS','TTR','Dialogue Gameboard'],'claim':'minimal internal adapter; not a general KoS/TTR runtime'}}
 errors=validate(dgb);g=nx.DiGraph();
 for coll in ('participants','moves','facts','qud','obligations','pending'):
  for row in dgb[coll]:g.add_node(row['id'],record_type=row['record_type'])
 for e in deps:g.add_edge(e['source'],e['target'],relation=e['relation'])
 integrated,integrated_validations=integrated_gameboards();validations={'schema_valid':not errors,'dependency_graph_acyclic':nx.is_directed_acyclic_graph(g),'all_dependencies_resolve':g.number_of_edges()==len(deps),'typed_records_present':all('record_type' in x for c in ('participants','moves','facts','qud','obligations','pending') for x in dgb[c]),'unresolved_and_alternatives_preserved':bool(pending[0]['unresolved'] and pending[0]['alternatives']),'public_fact_not_private_belief':all(f['record_type']=='public_fact' for f in facts),'acceptance_has_explicit_support':facts[1]['supported_by']==['m2','m3'],**integrated_validations};assert all(validations.values()),(errors,validations)
 result={'dialogue_gameboard':dgb,'graph':nx.node_link_data(g,edges='edges'),'schema':SCHEMA,'schema_errors':errors,'integrated_gameboards':integrated,'validations':validations};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');(OUT/'schema.json').write_text(json.dumps(SCHEMA,indent=2)+'\n');summary={'participants':len(participants),'moves':len(moves),'facts':len(facts),'qud':len(qud),'obligations':len(obligations),'pending':len(pending),'unresolved_fields':sum(len(x['unresolved']) for c in ('moves','facts','qud','obligations','pending') for x in dgb[c]),'integrated_observed_turns':len(integrated['observed_topology_gameboard']['moves']),'integrated_formal_alternatives':len(integrated['formal_content_gameboard']['pending'][0]['alternatives']),'verdict':'GO_MINIMAL_TYPED_PUBLIC_DGB'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'networkx':importlib.metadata.version('networkx'),'representation':'internal KoS/TTR-inspired typed records','schema_validation':'explicit required-field, uniqueness and reference-integrity validator'},indent=2)+'\n');print('DLG-06: typed public DGB, unresolved alternatives retained; GO')
if __name__=='__main__':main()
