#!/usr/bin/env python3
"""RET-03: sequential G1 -> transformation T -> constrained graph C query."""
from __future__ import annotations
import hashlib,importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
import duckdb,networkx as nx,pyarrow as pa,pyarrow.parquet as pq
from z3 import Bool,Int,Solver,sat
P=Path(__file__).resolve().parent;ROOT=P.parent.parent;OUT=P/'output'
def make_graph(nodes,edges):
 g=nx.DiGraph()
 for n,a in nodes:g.add_node(n,**a)
 for s,t,a in edges:g.add_edge(s,t,**a)
 return g
def encoded(g):return json.dumps(nx.node_link_data(g,edges='edges'),ensure_ascii=False,sort_keys=True)
def obs(prefix,text='io'):
 return make_graph([(f'{prefix}:form',{'kind':'form','text':text}),(f'{prefix}:obs',{'kind':'observation','entity_id':f'{prefix}:obs'})],[(f'{prefix}:form',f'{prefix}:obs',{'relation':'observed_as'})])
def trans(prefix,meaning='greeting'):
 return make_graph([(f'{prefix}:obsref',{'kind':'observation_ref','entity_id':f'{prefix}:obs'}),(f'{prefix}:hyp',{'kind':'hypothesis','entity_id':f'{prefix}:hyp','meaning':meaning})],[(f'{prefix}:obsref',f'{prefix}:hyp',{'relation':'interpret','transformation':'T'})])
def final(prefix,meaning='greeting',accepted=True):
 return make_graph([(f'{prefix}:hypref',{'kind':'hypothesis_ref','entity_id':f'{prefix}:hyp','meaning':meaning}),(f'{prefix}:outcome',{'kind':'outcome','accepted':accepted})],[(f'{prefix}:outcome',f'{prefix}:hypref',{'relation':'outcome_of'})])
def row(ep,pos,kind,g):return {'episode_id':ep,'position':pos,'stage_type':kind,'graph_json':encoded(g)}
def node_match(a,b):return all(a.get(k)==v for k,v in b.items() if k in ('kind','text'))
def edge_match(a,b):return a.get('relation')==b.get('relation')
def binding(host,pattern):
 ms=list(nx.algorithms.isomorphism.DiGraphMatcher(host,pattern,node_match=node_match,edge_match=edge_match).subgraph_monomorphisms_iter())
 return {p:h for h,p in ms[0].items()} if ms else None
def main():
 rows=[]
 for ep,stages in {
  'episode:match-A':[(1,'observation',obs('A')),(2,'transformation',trans('A')),(3,'final',final('A'))],
  'episode:missing-T':[(1,'observation',obs('B')),(3,'final',final('B'))],
  'episode:wrong-meaning':[(1,'observation',obs('C')),(2,'transformation',trans('C','input_output')),(3,'final',final('C','input_output'))],
  'episode:out-of-order':[(1,'transformation',trans('D')),(2,'observation',obs('D')),(3,'final',final('D'))],
  'episode:match-E':[(4,'observation',obs('E')),(7,'transformation',trans('E')),(9,'final',final('E'))],
  'episode:distractor':[(1,'observation',obs('F','bye')),(2,'transformation',trans('F')),(3,'final',final('F',accepted=False))],
 }.items():
  rows.extend(row(ep,p,k,g) for p,k,g in stages)
 OUT.mkdir(parents=True,exist_ok=True)
 schema=pa.schema([('episode_id',pa.string()),('position',pa.int64()),('stage_type',pa.string()),('graph_json',pa.large_string())]);pq.write_table(pa.Table.from_pylist(rows,schema=schema),OUT/'episodes.parquet',compression='zstd')
 db=OUT/'ret-03.duckdb'
 if db.exists():db.unlink()
 con=duckdb.connect(str(db));con.execute('CREATE TABLE stages AS SELECT * FROM read_parquet(?)',[str((OUT/'episodes.parquet').resolve())]);candidate_ids=[r[0] for r in con.execute("SELECT episode_id FROM stages GROUP BY episode_id HAVING count_if(stage_type='observation')>0 AND count_if(stage_type='transformation')>0 AND count_if(stage_type='final')>0").fetchall()];selected=con.execute('SELECT * FROM stages WHERE episode_id IN (SELECT unnest(?)) ORDER BY episode_id,position',[candidate_ids]).fetchall();con.close()
 by={}
 for ep,pos,kind,gjson in selected:by.setdefault(ep,[]).append((pos,kind,nx.node_link_graph(json.loads(gjson),edges='edges')))
 q1=make_graph([('?form',{'kind':'form','text':'io'}),('?obs',{'kind':'observation'})],[('?form','?obs',{'relation':'observed_as'})]);qt=make_graph([('?oref',{'kind':'observation_ref'}),('?hyp',{'kind':'hypothesis'})],[('?oref','?hyp',{'relation':'interpret'})]);qc=make_graph([('?out',{'kind':'outcome'}),('?href',{'kind':'hypothesis_ref'})],[('?out','?href',{'relation':'outcome_of'})])
 matches=[];rejections=[]
 for ep,stages in by.items():
  g1=[(p,g,binding(g,q1)) for p,k,g in stages if k=='observation' and binding(g,q1)]
  accepted=False
  for p1,g,b1 in g1:
   for pt,gt,bt in [(p,g,binding(g,qt)) for p,k,g in stages if k=='transformation' and p>p1 and binding(g,qt)]:
    for pc,gc,bc in [(p,g,binding(g,qc)) for p,k,g in stages if k=='final' and p>pt and binding(g,qc)]:
     hyp=gt.nodes[bt['?hyp']];href=gc.nodes[bc['?href']];out=gc.nodes[bc['?out']]
     s=Solver();meaning=Int('meaning');ok=Bool('accepted');s.add(meaning==(1 if hyp.get('meaning')=='greeting' else 2));s.add(meaning==1);s.add(ok==bool(out.get('accepted')));s.add(ok)
     entity_links={'observation':g.nodes[b1['?obs']]['entity_id']==gt.nodes[bt['?oref']]['entity_id'],'hypothesis':hyp['entity_id']==href['entity_id']}
     if s.check()==sat and all(entity_links.values()):
      matches.append({'episode_id':ep,'positions':[p1,pt,pc],'bindings':{'G1':b1,'T':bt,'C':bc},'transformation':'T','cross_stage_entity_links':entity_links,'final_constraints':'SAT'});accepted=True
  if not accepted:rejections.append(ep)
 validations={'expected_matches':{m['episode_id'] for m in matches}=={'episode:match-A','episode:match-E'},'strict_order':all(m['positions']==sorted(m['positions']) and len(set(m['positions']))==3 for m in matches),'bindings_each_stage':all(set(m['bindings'])=={'G1','T','C'} for m in matches),'disk_prefilter_excludes_missing_stage':'episode:missing-T' not in candidate_ids,'wrong_meaning_rejected':'episode:wrong-meaning' in rejections,'out_of_order_rejected':'episode:out-of-order' in rejections}
 sem06_path=ROOT/'poc/sem-06/output/results.json';sem06=json.loads(sem06_path.read_text())
 relation=sem06['learned_relation'];prediction=sem06['heldout_prediction']['runtime_prediction'];support_ref=relation['support_refs'][0];relation_ref=sem06['learned_relation_artifact_id']
 assert prediction['relation_ref']==relation_ref and support_ref in relation['support_refs']
 integrated_rows=[
  row('sem06:heldout-sequence',1,'observation',make_graph([(support_ref,{'kind':'semiotic_episode','artifact_id':support_ref})],[])),
  row('sem06:heldout-sequence',2,'transformation',make_graph([(support_ref,{'kind':'semiotic_episode_ref','artifact_id':support_ref}),(relation_ref,{'kind':'learned_semiotic_relation','artifact_id':relation_ref,'predicted_effect':relation['predicted_effect']})],[(support_ref,relation_ref,{'relation':'supports_learned_relation'})])),
  row('sem06:heldout-sequence',3,'final',make_graph([(relation_ref,{'kind':'learned_semiotic_relation_ref','artifact_id':relation_ref}),(prediction['heldout_ref'],{'kind':'heldout_prediction','artifact_id':prediction['heldout_ref'],'predicted_effect':prediction['predicted_effect'],'observed_effect':sem06['heldout_prediction']['fixture']['observed_effect'],'correct':sem06['heldout_prediction']['correct']})],[(relation_ref,prediction['heldout_ref'],{'relation':'produces_prediction'})])),
 ]
 pq.write_table(pa.Table.from_pylist(integrated_rows,schema=schema),OUT/'integrated-episodes.parquet',compression='zstd')
 icon=duckdb.connect();integrated_selected=icon.execute("SELECT * FROM read_parquet(?) WHERE episode_id='sem06:heldout-sequence' ORDER BY position",[str((OUT/'integrated-episodes.parquet').resolve())]).fetchall();icon.close()
 assert [stage[1]for stage in integrated_selected]==[1,2,3]
 igraphs=[nx.node_link_graph(json.loads(stage[3]),edges='edges')for stage in integrated_selected]
 g1_id=next(iter(igraphs[0].nodes));t_support=next(n for n,d in igraphs[1].nodes(data=True)if d['kind']=='semiotic_episode_ref');t_relation=next(n for n,d in igraphs[1].nodes(data=True)if d['kind']=='learned_semiotic_relation');c_relation=next(n for n,d in igraphs[2].nodes(data=True)if d['kind']=='learned_semiotic_relation_ref');c_prediction=next(n for n,d in igraphs[2].nodes(data=True)if d['kind']=='heldout_prediction')
 solver=Solver();effect=Int('integrated_effect');correct=Bool('integrated_correct');solver.add(effect==(1 if igraphs[1].nodes[t_relation]['predicted_effect']=='effect_e1' else 0));solver.add(effect==(1 if igraphs[2].nodes[c_prediction]['observed_effect']=='effect_e1' else 0));solver.add(correct==igraphs[2].nodes[c_prediction]['correct']);solver.add(correct)
 integrated_match={'episode_id':'sem06:heldout-sequence','positions':[1,2,3],'bindings':{'G1':{'?episode':g1_id},'T':{'?episode_ref':t_support,'?relation':t_relation},'C':{'?relation_ref':c_relation,'?prediction':c_prediction}},'cross_stage_entity_links':{'episode':g1_id==t_support,'relation':t_relation==c_relation},'final_constraints':'SAT'if solver.check()==sat else'UNSAT','prediction_ancestry_types':sem06['prediction_ancestry_types']}
 validations.update({'integrated_sem06_strict_order':integrated_match['positions']==[1,2,3],'integrated_sem06_entity_links':all(integrated_match['cross_stage_entity_links'].values()),'integrated_sem06_constraints_sat':integrated_match['final_constraints']=='SAT','integrated_sem06_full_ancestry':{'semiotic-episode','learned-semiotic-relation','semiotic-heldout-prediction'}<=set(sem06['prediction_ancestry_types'])})
 assert all(validations.values())
 result={'query':{'sequence':['G1','T','C'],'final_constraints':['meaning=greeting','accepted=true','same entities across stages']},'duckdb_candidate_episode_ids':candidate_ids,'matches':matches,'rejected_candidate_episode_ids':rejections,'integrated_sem06':{'source_sha256':hashlib.sha256(sem06_path.read_bytes()).hexdigest(),'query':{'sequence':['support episode','learned relation','heldout prediction'],'constraints':['same episode/ref','same relation/ref','predicted effect equals observed effect','prediction correct']},'match':integrated_match},'validation':validations};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'stored_stage_count':len(rows),'disk_candidate_episode_count':len(candidate_ids),'matched_episode_count':len(matches),'matched_episode_ids':[m['episode_id'] for m in matches],'integrated_sem06_matched_episode_count':1,'integrated_sem06_final_constraints':'SAT','verdict':'GO_SEQUENTIAL_STRUCTURAL_TRANSFORMATION_QUERY'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'duckdb':importlib.metadata.version('duckdb'),'networkx':importlib.metadata.version('networkx'),'z3_solver':importlib.metadata.version('z3-solver'),'pyarrow':importlib.metadata.version('pyarrow')},indent=2)+'\n');print(f"RET-03: controlled {len(matches)} + SEM-06 1 episodes match sequential query; GO")
if __name__=='__main__':main()
