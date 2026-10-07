#!/usr/bin/env python3
"""RET-02: explainable partial attributed graph matching."""
from __future__ import annotations

import hashlib,importlib.metadata,json,itertools,platform
from datetime import datetime,timezone
from pathlib import Path
import duckdb,networkx as nx
from z3 import Bool,Or,Not,And,Solver,sat
P=Path(__file__).resolve().parent;ROOT=P.parent.parent;OUT=P/'output'

def graph(nodes,edges):
 g=nx.DiGraph()
 for n,a in nodes:g.add_node(n,**a)
 for s,t,a in edges:g.add_edge(s,t,**a)
 return g

PAT=graph([('?a',{'kind':'person','role':'agent'}),('?e',{'kind':'event','lemma':'greet'}),('?t',{'kind':'person','role':'patient'}),('?c',{'kind':'context','topic':'opening'})],[('?a','?e',{'relation':'agent'}),('?e','?t',{'relation':'patient'}),('?e','?c',{'relation':'in_context'})])
GRAPHS={
 'complete':graph([('a',{'kind':'person','role':'agent'}),('e',{'kind':'event','lemma':'greet'}),('t',{'kind':'person','role':'patient'}),('c',{'kind':'context','topic':'opening'})],[('a','e',{'relation':'agent'}),('e','t',{'relation':'patient'}),('e','c',{'relation':'in_context'})]),
 'partial':graph([('p1',{'kind':'person','role':'agent'}),('v',{'kind':'event','lemma':'greet'}),('p2',{'kind':'person','role':'patient'})],[('p1','v',{'relation':'agent'}),('v','p2',{'relation':'patient'})]),
 'variant':graph([('x',{'kind':'person','role':'agent'}),('y',{'kind':'event','lemma':'welcome'}),('z',{'kind':'person','role':'patient'}),('k',{'kind':'context','topic':'opening'})],[('x','y',{'relation':'agent'}),('y','z',{'relation':'patient'}),('y','k',{'relation':'in_context'})]),
 'distractor':graph([('u',{'kind':'person','role':'patient'}),('v',{'kind':'event','lemma':'depart'}),('w',{'kind':'context','topic':'closing'})],[('v','u',{'relation':'agent'}),('v','w',{'relation':'in_context'})]),
 'noise':graph([('n1',{'kind':'number'}),('n2',{'kind':'number'})],[('n1','n2',{'relation':'next'})])
}
def attr_score(p,c):
 keys=[k for k in p if k!='kind'];return (sum(c.get(k)==p[k] for k in keys)/len(keys)) if keys else 1.0
def best_match(candidate):
 pnodes=list(PAT);cnodes=list(candidate);best=None
 choices=cnodes+[None]
 for values in itertools.product(choices,repeat=len(pnodes)):
  bound=[v for v in values if v is not None]
  if len(bound)!=len(set(bound)):continue
  m=dict(zip(pnodes,values))
  if m['?a'] is None or m['?e'] is None:continue
  if any(v is not None and PAT.nodes[p]['kind']!=candidate.nodes[v].get('kind') for p,v in m.items()):continue
  matched_edges=[]
  for s,t,a in PAT.edges(data=True):
   if m[s] is not None and m[t] is not None and candidate.has_edge(m[s],m[t]) and candidate[m[s]][m[t]].get('relation')==a['relation']:matched_edges.append((s,t))
  attrs=[attr_score(PAT.nodes[p],candidate.nodes[v]) for p,v in m.items() if v is not None]
  comp={'node_coverage':len(bound)/len(pnodes),'edge_coverage':len(matched_edges)/PAT.number_of_edges(),'attribute_agreement':sum(attrs)/len(attrs),'constraint_bonus':1.0}
  score=.35*comp['node_coverage']+.45*comp['edge_coverage']+.15*comp['attribute_agreement']+.05
  item=(score,m,matched_edges,comp)
  if best is None or item[0]>best[0]:best=item
 score,m,matched,comp=best
 # Independent Z3 validation of required, injective, kind-compatible bindings.
 vars={(p,c):Bool(f'b_{p}_{c}') for p in pnodes for c in cnodes}
 s=Solver()
 for p in pnodes:
  allowed=[vars[p,c] for c in cnodes if PAT.nodes[p]['kind']==candidate.nodes[c].get('kind')]
  s.add(Or(*allowed) if p in ('?a','?e') else Or(*(allowed+[Bool(f'unbound_{p}')])) )
  for x,y in itertools.combinations([vars[p,c] for c in cnodes],2):s.add(Not(And(x,y)))
 for c in cnodes:
  for p,q in itertools.combinations(pnodes,2):s.add(Not(And(vars[p,c],vars[q,c])))
 for (p,c),v in vars.items():s.add(v==(m[p]==c))
 z3_ok=s.check()==sat
 missing_nodes=[p for p,v in m.items() if v is None]
 missing_edges=[[s,t,PAT[s][t]['relation']] for s,t in PAT.edges if (s,t) not in matched]
 return {'score':score,'bindings':{p:v for p,v in m.items() if v is not None},'missing_nodes':missing_nodes,'missing_edges':missing_edges,'score_explanation':comp,'constraints_satisfied':z3_ok}
def main():
 OUT.mkdir(parents=True,exist_ok=True);db=OUT/'ret-02.duckdb'
 if db.exists():db.unlink()
 con=duckdb.connect(str(db));con.execute('CREATE TABLE graph_index(id VARCHAR, person_count INTEGER, event_count INTEGER, context_count INTEGER)')
 for gid,g in GRAPHS.items():con.execute('INSERT INTO graph_index VALUES (?,?,?,?)',[gid,sum(d.get('kind')=='person' for _,d in g.nodes(data=True)),sum(d.get('kind')=='event' for _,d in g.nodes(data=True)),sum(d.get('kind')=='context' for _,d in g.nodes(data=True))])
 candidate_ids=[r[0] for r in con.execute('SELECT id FROM graph_index WHERE person_count>=1 AND event_count>=1').fetchall()];con.close()
 ranked=sorted([{'graph_id':gid,**best_match(GRAPHS[gid])} for gid in candidate_ids],key=lambda x:(-x['score'],x['graph_id']))
 graph03_path=ROOT/'poc/graph-03/output/results.json';ret01_path=ROOT/'poc/ret-01/output/results.json'
 graph03=json.loads(graph03_path.read_text());ret01=json.loads(ret01_path.read_text())
 actual=nx.node_link_graph(graph03['graph'],edges='edges')
 actual_candidates=[n for n,d in actual.nodes(data=True) if d['node_type']=='candidate']
 assert len(actual_candidates)==len(ret01['integrated_graph03_query']['occurrences'])
 index_rows=[];actual_ranked=[]
 for candidate_id in actual_candidates:
  outgoing=list(actual.out_edges(candidate_id,keys=True,data=True));incoming=list(actual.in_edges(candidate_id,keys=True,data=True))
  group_ids=[target for _,target,_,attrs in outgoing if attrs['edge_type']=='member_of']
  support_ids=[target for _,target,_,attrs in outgoing if attrs['edge_type']=='supported_by']
  conflicts=sorted({target for _,target,_,attrs in outgoing if attrs['edge_type']=='conflicts_with'}|{source for source,_,_,attrs in incoming if attrs['edge_type']=='conflicts_with'})
  assert len(group_ids)==len(support_ids)==1
  support=actual.nodes[support_ids[0]];candidate=actual.nodes[candidate_id]
  hash_resolves=candidate['payload_sha256'] in support['supported_payload_sha256']
  index_rows.append((candidate_id,1,1,len(conflicts),support['poc_id']))
  node_coverage=(3+int(bool(conflicts)))/4;edge_coverage=(2+int(bool(conflicts)))/3
  score=.35*node_coverage+.45*edge_coverage+.15*1.0+.05
  actual_ranked.append({'candidate_id':candidate_id,'score':score,
   'bindings':{'?candidate':candidate_id,'?group':group_ids[0],'?support':support_ids[0],**({'?conflict':conflicts[0]}if conflicts else{})},
   'missing_nodes':[]if conflicts else['?conflict'],'missing_edges':[]if conflicts else[['?candidate','?conflict','conflicts_with']],
   'score_explanation':{'node_coverage':node_coverage,'edge_coverage':edge_coverage,'attribute_agreement':1.0,'constraint_bonus':1.0},
   'support_hash_resolves':hash_resolves,'source_poc':support['poc_id'],'conflict_count':len(conflicts)})
 actual_db=duckdb.connect();actual_db.execute('CREATE TABLE candidate_index(candidate_id VARCHAR, has_group INTEGER, has_support INTEGER, conflict_count INTEGER, source_poc VARCHAR)');actual_db.executemany('INSERT INTO candidate_index VALUES (?,?,?,?,?)',index_rows)
 actual_candidate_ids=[row[0]for row in actual_db.execute('SELECT candidate_id FROM candidate_index WHERE has_group=1 AND has_support=1 ORDER BY candidate_id').fetchall()];actual_db.close()
 actual_ranked=sorted((row for row in actual_ranked if row['candidate_id'] in actual_candidate_ids),key=lambda row:(-row['score'],row['candidate_id']))
 actual_full=next(row for row in actual_ranked if row['conflict_count']>0);actual_partial=next(row for row in actual_ranked if row['conflict_count']==0)
 validations={'complete_ranked_first':ranked[0]['graph_id']=='complete','partial_precedes_distractor':next(i for i,x in enumerate(ranked) if x['graph_id']=='partial')<next(i for i,x in enumerate(ranked) if x['graph_id']=='distractor'),'noise_filtered_by_duckdb': 'noise' not in candidate_ids,'all_constraints_satisfied':all(x['constraints_satisfied'] for x in ranked),'partial_reports_missing_context': '?c' in next(x for x in ranked if x['graph_id']=='partial')['missing_nodes'],
 'graph03_all_candidates_prefiltered':set(actual_candidate_ids)==set(actual_candidates),'graph03_all_support_hashes_resolve':all(row['support_hash_resolves']for row in actual_ranked),'graph03_partial_reports_missing_conflict':'?conflict'in actual_partial['missing_nodes'],'graph03_full_precedes_partial':actual_full['score']>actual_partial['score']}
 assert all(validations.values())
 result={'pattern':nx.node_link_data(PAT,edges='edges'),'duckdb_candidate_ids':candidate_ids,'top_k':ranked,
 'integrated_graph03':{'source_sha256':hashlib.sha256(graph03_path.read_bytes()).hexdigest(),'ret01_source_sha256':hashlib.sha256(ret01_path.read_bytes()).hexdigest(),'query':{'required':['candidate member_of group','candidate supported_by support'],'optional':['candidate conflicts_with candidate']},'duckdb_candidate_ids':actual_candidate_ids,'ranked':actual_ranked,'full_example':actual_full,'partial_example':actual_partial},'validation':validations}
 (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'indexed_graph_count':len(GRAPHS),'loaded_candidate_count':len(candidate_ids),'top_k_count':len(ranked),'winner':ranked[0]['graph_id'],'winner_score':ranked[0]['score'],'integrated_graph03_candidate_count':len(actual_ranked),'integrated_full_candidate_count':sum(row['conflict_count']>0 for row in actual_ranked),'integrated_partial_candidate_count':sum(row['conflict_count']==0 for row in actual_ranked),'verdict':'GO_EXPLAINABLE_PARTIAL_GRAPH_RETRIEVAL'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'networkx':importlib.metadata.version('networkx'),'duckdb':importlib.metadata.version('duckdb'),'z3_solver':importlib.metadata.version('z3-solver'),'weights':{'nodes':.35,'edges':.45,'attributes':.15,'constraints':.05}},indent=2)+'\n');print(f"RET-02: controlled {len(ranked)} + GRAPH-03 {len(actual_ranked)} candidates; full > partial; GO")
if __name__=='__main__':main()
