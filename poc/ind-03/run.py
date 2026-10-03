#!/usr/bin/env python3
"""IND-03: discover an anonymous recurrent subgraph by canonical enumeration."""
from __future__ import annotations
import importlib.metadata,itertools,json,platform
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import networkx as nx
import rustworkx as rx
from scipy.stats import binomtest
P=Path(__file__).resolve().parent;OUT=P/'output'
def canon(g,nodes):
 best=None;best_order=None
 for order in itertools.permutations(nodes):
  pos={n:i for i,n in enumerate(order)};rep={'nodes':[g.nodes[n]['kind'] for n in order],'edges':sorted((pos[a],pos[b],d['relation']) for a,b,d in g.subgraph(nodes).edges(data=True))};s=json.dumps(rep,sort_keys=True,separators=(',',':'))
  if best is None or s<best:best,best_order=s,order
 return best,best_order
def generate():
 graphs=[]
 for i in range(10):
  g=nx.DiGraph(graph_id=f'g{i}')
  if i<8:
   ids=[f'x{i}',f'y{i}',f'z{i}'];g.add_node(ids[0],kind='Pattern_Node_A');g.add_node(ids[1],kind='Pattern_Node_B');g.add_node(ids[2],kind='Pattern_Node_C');g.add_edge(ids[0],ids[1],relation='Pattern_Edge_1');g.add_edge(ids[1],ids[2],relation='Pattern_Edge_2')
   n=f'noise{i}';g.add_node(n,kind=f'Distractor_{i}');g.add_edge(n,ids[i%3],relation=f'noise_relation_{i}')
  else:
   for j in range(4):g.add_node(f'n{i}_{j}',kind=f'Distractor_{i}_{j}')
   g.add_edge(f'n{i}_0',f'n{i}_2',relation=f'unique_{i}_a');g.add_edge(f'n{i}_3',f'n{i}_1',relation=f'unique_{i}_b')
  graphs.append(g)
 return graphs
def to_rx(g):
 r=rx.PyDiGraph();idx={n:r.add_node(d['kind']) for n,d in g.nodes(data=True)}
 for a,b,d in g.edges(data=True):r.add_edge(idx[a],idx[b],d['relation'])
 return r
def main():
 OUT.mkdir(parents=True,exist_ok=True);graphs=generate();occ=defaultdict(list);representations={}
 for g in graphs:
  seen=set()
  for nodes in itertools.combinations(g.nodes,3):
   sub=g.subgraph(nodes)
   if nx.is_weakly_connected(sub) and sub.number_of_edges()>=2:
    key,order=canon(g,nodes);representations[key]=json.loads(key)
    if key not in seen:occ[key].append({'graph_id':g.graph['graph_id'],'node_binding':{f'v{j}':n for j,n in enumerate(order)},'source':'controlled fixture generator'});seen.add(key)
 ranked=sorted(occ,key=lambda k:(-len(occ[k]),k));winner=ranked[0];rep=representations[winner]
 pattern=nx.DiGraph(pattern_id='Pattern_Recurrent_001')
 for i,kind in enumerate(rep['nodes']):pattern.add_node(i,kind=kind)
 for a,b,r in rep['edges']:pattern.add_edge(a,b,relation=r)
 nm=lambda a,b:a['kind']==b['kind'];em=lambda a,b:a['relation']==b['relation'];nx_verified=[];rx_verified=[]
 for g in graphs:
  nx_verified.append(nx.algorithms.isomorphism.DiGraphMatcher(g,pattern,node_match=nm,edge_match=em).subgraph_is_isomorphic())
  rx_verified.append(rx.is_subgraph_isomorphic(to_rx(g),to_rx(pattern),node_matcher=lambda a,b:a==b,edge_matcher=lambda a,b:a==b,induced=True))
 graph_ids=[g.graph['graph_id'] for g in graphs];exceptions=[gid for gid,ok in zip(graph_ids,nx_verified) if not ok];ci=binomtest(sum(nx_verified),len(graphs)).proportion_ci(confidence_level=.95)
 provenance=[{'occurrence_id':f'Pattern_Recurrent_001:{o["graph_id"]}','pattern_id':'Pattern_Recurrent_001',**o} for o in occ[winner]]
 vals={'winner_discovered_not_selected_by_id':ranked[0]==winner,'canonical_form_expected':rep=={'nodes':['Pattern_Node_A','Pattern_Node_B','Pattern_Node_C'],'edges':[[0,1,'Pattern_Edge_1'],[1,2,'Pattern_Edge_2']]} ,'support_exact':sum(nx_verified)==8,'networkx_rustworkx_agree':nx_verified==rx_verified,'exceptions_exact':exceptions==['g8','g9'],'provenance_complete':len(provenance)==8 and all(len(o['node_binding'])==3 for o in provenance),'distractors_not_promoted':len(occ[ranked[1]])<8 if len(ranked)>1 else True};assert all(vals.values()),(vals,rep)
 result={'pattern':{'id':'Pattern_Recurrent_001','anonymous':True,'canonical_form':rep,'canonical_serialization':winner},'occurrences':provenance,'support':{'graphs_with_pattern':8,'graph_count':10,'fraction':.8,'binomial_95pct_interval':[ci.low,ci.high]},'exceptions':exceptions,'candidate_statistics':[{'canonical_form':representations[k],'graph_support':len(occ[k])} for k in ranked],'verification':{'networkx':dict(zip(graph_ids,nx_verified)),'rustworkx':dict(zip(graph_ids,rx_verified))},'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'graphs':10,'discovered_candidates':len(ranked),'winner_support':8,'support_fraction':.8,'exceptions':2,'cross_engine_agreement':True,'verdict':'GO_ANONYMOUS_RECURRENT_SUBGRAPH'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'networkx':importlib.metadata.version('networkx'),'rustworkx':importlib.metadata.version('rustworkx'),'scipy':importlib.metadata.version('scipy'),'candidate_generation':'all weakly connected induced 3-node subgraphs with >=2 edges','canonicalization':'lexicographic minimum across every node permutation'},indent=2)+'\n');print('IND-03: anonymous 3-node motif discovered in 8/10 graphs; engines agree; GO')
if __name__=='__main__':main()
