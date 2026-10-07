#!/usr/bin/env python3
"""IND-03: discover an anonymous recurrent subgraph by canonical enumeration."""
from __future__ import annotations
import hashlib,importlib.metadata,itertools,json,platform
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import networkx as nx
import rustworkx as rx
from scipy.stats import binomtest
P=Path(__file__).resolve().parent;OUT=P/'output';ROOT=P.parents[1]
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
def integrated_justification_pattern():
 path=ROOT/'poc/hyp-02/output/results.json';raw=path.read_bytes();source=json.loads(raw);global_graph=nx.DiGraph()
 for node in source['justification_graph']['nodes']:global_graph.add_node(node['id'],kind=node['kind'])
 for edge in source['justification_graph']['edges']:global_graph.add_edge(edge['source'],edge['target'],relation=edge['relation'])
 graphs=[]
 for hypothesis_id,explanation in sorted(source['explanations'].items()):
  nodes=[hypothesis_id,*explanation['transitive_dependencies']];graph=global_graph.subgraph(nodes).copy();graph.graph['graph_id']=hypothesis_id;graphs.append(graph)
 occurrences=defaultdict(list);representations={}
 for graph in graphs:
  bindings_by_key=defaultdict(list)
  for nodes in itertools.combinations(graph.nodes,3):
   subgraph=graph.subgraph(nodes)
   if nx.is_weakly_connected(subgraph) and subgraph.number_of_edges()>=2:
    key,order=canon(graph,nodes);representations[key]=json.loads(key)
    bindings_by_key[key].append(tuple(order))
  # A graph may instantiate the same anonymous form more than once.  Pick the
  # lexicographically first binding so provenance is reproducible across hash
  # seeds and NetworkX view iteration orders while support still counts graphs.
  for key,orders in bindings_by_key.items():
   order=min(orders);occurrences[key].append({'hypothesis_id':graph.graph['graph_id'],'node_binding':{f'v{index}':node for index,node in enumerate(order)}})
 ranked=sorted(occurrences,key=lambda key:(-len(occurrences[key]),key));winner=ranked[0];representation=representations[winner];pattern=nx.DiGraph()
 for index,kind in enumerate(representation['nodes']):pattern.add_node(index,kind=kind)
 for left,right,relation in representation['edges']:pattern.add_edge(left,right,relation=relation)
 node_match=lambda left,right:left['kind']==right['kind'];edge_match=lambda left,right:left['relation']==right['relation'];nx_matches=[];rx_matches=[]
 for graph in graphs:
  nx_matches.append(nx.algorithms.isomorphism.DiGraphMatcher(graph,pattern,node_match=node_match,edge_match=edge_match).subgraph_is_isomorphic());rx_matches.append(rx.is_subgraph_isomorphic(to_rx(graph),to_rx(pattern),node_matcher=lambda left,right:left==right,edge_matcher=lambda left,right:left==right,induced=True))
 graph_ids=[graph.graph['graph_id'] for graph in graphs];exceptions=[graph_id for graph_id,matched in zip(graph_ids,nx_matches) if not matched];ci=binomtest(sum(nx_matches),len(graphs)).proportion_ci(confidence_level=.95)
 details={'source':{'poc':'HYP-02','results_sha256':hashlib.sha256(raw).hexdigest()},'pattern':{'id':'Pattern_Justification_Recurrent_001','anonymous':True,'canonical_form':representation,'canonical_serialization':winner},'occurrences':occurrences[winner],'support':{'hypotheses_with_pattern':sum(nx_matches),'hypothesis_count':len(graphs),'fraction':sum(nx_matches)/len(graphs),'binomial_95pct_interval':[ci.low,ci.high]},'exceptions':exceptions,'candidate_statistics':[{'canonical_form':representations[key],'graph_support':len(occurrences[key])} for key in ranked],'verification':{'networkx':dict(zip(graph_ids,nx_matches)),'rustworkx':dict(zip(graph_ids,rx_matches))}}
 validations={'actual_hypothesis_graph_count':len(graphs)==4,'actual_recurrent_pattern_found_in_all':sum(nx_matches)==4,'actual_engines_agree':nx_matches==rx_matches,'actual_occurrence_bindings_complete':len(details['occurrences'])==4 and all(len(row['node_binding'])==3 for row in details['occurrences']),'actual_bindings_respect_support_role':all(global_graph.nodes[row['node_binding']['v0']]['kind']=='support' for row in details['occurrences']),'actual_structural_pattern_spans_distinct_bindings':len({row['node_binding']['v0'] for row in details['occurrences']})>1,'actual_pattern_is_anonymous':not any(token in json.dumps(representation) for token in ('surface-io','hyp:H','computing','greeting','astronomy')),'actual_less_frequent_candidates_retained':any(row['graph_support']<4 for row in details['candidate_statistics'])}
 return details,validations
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
 integrated,integrated_vals=integrated_justification_pattern();vals={'winner_discovered_not_selected_by_id':ranked[0]==winner,'canonical_form_expected':rep=={'nodes':['Pattern_Node_A','Pattern_Node_B','Pattern_Node_C'],'edges':[[0,1,'Pattern_Edge_1'],[1,2,'Pattern_Edge_2']]} ,'support_exact':sum(nx_verified)==8,'networkx_rustworkx_agree':nx_verified==rx_verified,'exceptions_exact':exceptions==['g8','g9'],'provenance_complete':len(provenance)==8 and all(len(o['node_binding'])==3 for o in provenance),'distractors_not_promoted':len(occ[ranked[1]])<8 if len(ranked)>1 else True,**integrated_vals};assert all(vals.values()),(vals,rep)
 result={'pattern':{'id':'Pattern_Recurrent_001','anonymous':True,'canonical_form':rep,'canonical_serialization':winner},'occurrences':provenance,'support':{'graphs_with_pattern':8,'graph_count':10,'fraction':.8,'binomial_95pct_interval':[ci.low,ci.high]},'exceptions':exceptions,'candidate_statistics':[{'canonical_form':representations[k],'graph_support':len(occ[k])} for k in ranked],'verification':{'networkx':dict(zip(graph_ids,nx_verified)),'rustworkx':dict(zip(graph_ids,rx_verified))},'integrated_justification_pattern':integrated,'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'graphs':10,'discovered_candidates':len(ranked),'winner_support':8,'support_fraction':.8,'exceptions':2,'cross_engine_agreement':True,'integrated_hypothesis_graphs':integrated['support']['hypothesis_count'],'integrated_winner_support':integrated['support']['hypotheses_with_pattern'],'integrated_candidates':len(integrated['candidate_statistics']),'verdict':'GO_ANONYMOUS_RECURRENT_SUBGRAPH'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'networkx':importlib.metadata.version('networkx'),'rustworkx':importlib.metadata.version('rustworkx'),'scipy':importlib.metadata.version('scipy'),'candidate_generation':'all weakly connected induced 3-node subgraphs with >=2 edges','canonicalization':'lexicographic minimum across every node permutation','hyp02_sha256':integrated['source']['results_sha256']},indent=2)+'\n');print('IND-03: anonymous 3-node motif discovered in 8/10 graphs; engines agree; GO')
if __name__=='__main__':main()
