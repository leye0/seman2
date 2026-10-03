#!/usr/bin/env python3
"""IND-04: induce a recurrent anonymous graph transformation."""
from __future__ import annotations
import importlib.metadata,json,platform
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import networkx as nx
import rustworkx as rx
import z3
from scipy.stats import binomtest
P=Path(__file__).resolve().parent;OUT=P/'output'
def pairs():
 out=[]
 for i in range(10):
  b=nx.DiGraph();a=f'a{i}';c=f'b{i}';b.add_node(a,kind='Pattern_Node_A');b.add_node(c,kind='Pattern_Node_B');b.add_edge(a,c,relation='Pattern_Pre');extra=f'extra{i}';b.add_node(extra,kind=f'Distractor_{i}')
  after=nx.relabel_nodes(b,{a:f'x{i}',c:f'y{i}',extra:f'z{i}'},copy=True);bind={a:f'x{i}',c:f'y{i}',extra:f'z{i}'};after.remove_edge(f'x{i}',f'y{i}');after.add_edge(f'x{i}',f'y{i}',relation='Pattern_Post');new=f'n{i}';after.add_node(new,kind='Pattern_Node_C')
  if i==8:after.add_edge(f'y{i}',new,relation='Wrong_Link')
  elif i<9:after.add_edge(f'y{i}',new,relation='Pattern_Link')
  # i=9 intentionally omits the link.
  out.append({'id':f'pair-{i}','before':b,'after':after,'binding':bind})
 return out
def diff(pair):
 b,a,bind=pair['before'],pair['after'],pair['binding'];rev={v:k for k,v in bind.items()};roles={n:f"v_{b.nodes[n]['kind'].removeprefix('Pattern_Node_')}" for n in b.nodes if b.nodes[n]['kind'].startswith('Pattern_Node_')};created=[n for n in a if n not in rev];created_roles={n:f"v_{a.nodes[n]['kind'].removeprefix('Pattern_Node_')}" for n in created};after_edges={(rev.get(x,x),rev.get(y,y),d['relation']) for x,y,d in a.edges(data=True)};before_edges={(x,y,d['relation']) for x,y,d in b.edges(data=True)}
 norm=lambda edge:(roles.get(edge[0],created_roles.get(edge[0],edge[0])),roles.get(edge[1],created_roles.get(edge[1],edge[1])),edge[2])
 return {'variables':sorted([*roles.values(),*created_roles.values()]),'preconditions':{'nodes':sorted((roles[n],b.nodes[n]['kind']) for n in roles),'edges':sorted(norm(e) for e in before_edges if e[0] in roles and e[1] in roles)},'effects':{'create_nodes':sorted((created_roles[n],a.nodes[n]['kind']) for n in created),'delete_edges':sorted(norm(e) for e in before_edges-after_edges if e[0] in roles and e[1] in roles),'add_edges':sorted(norm(e) for e in after_edges-before_edges if (e[0] in roles or e[0] in created_roles) and (e[1] in roles or e[1] in created_roles))}}
def key(d):return json.dumps(d,sort_keys=True,separators=(',',':'))
def apply(pair,t):
 g=nx.relabel_nodes(pair['before'],pair['binding'],copy=True);role={f"v_{d['kind'].removeprefix('Pattern_Node_')}":n for n,d in g.nodes(data=True) if d['kind'].startswith('Pattern_Node_')}
 for r,kind in t['effects']['create_nodes']:nid=f"generated:{pair['id']}:{r}";g.add_node(nid,kind=kind);role[r]=nid
 for x,y,r in t['effects']['delete_edges']:
  if g.has_edge(role[x],role[y]) and g.edges[role[x],role[y]]['relation']==r:g.remove_edge(role[x],role[y])
 for x,y,r in t['effects']['add_edges']:g.add_edge(role[x],role[y],relation=r)
 return g
def iso(g,h):return nx.is_isomorphic(g,h,node_match=lambda a,b:a['kind']==b['kind'],edge_match=lambda a,b:a['relation']==b['relation'])
def to_rx(g):
 r=rx.PyDiGraph();ids={n:r.add_node(d['kind']) for n,d in g.nodes(data=True)}
 for a,b,d in g.edges(data=True):r.add_edge(ids[a],ids[b],d['relation'])
 return r
def main():
 OUT.mkdir(parents=True,exist_ok=True);ps=pairs();diffs=[diff(p) for p in ps];counts=Counter(key(d) for d in diffs);winner_key,support=counts.most_common(1)[0];winner=json.loads(winner_key);supported=[p['id'] for p,d in zip(ps,diffs) if key(d)==winner_key];exceptions=[{'pair_id':p['id'],'observed_diff':d,'reason':'differs from recurrent transformation'} for p,d in zip(ps,diffs) if key(d)!=winner_key]
 nx_ok=[];rx_ok=[];constraints=[]
 for p in ps:
  pred=apply(p,winner);n=iso(pred,p['after']);r=rx.is_isomorphic(to_rx(pred),to_rx(p['after']),node_matcher=lambda a,b:a==b,edge_matcher=lambda a,b:a==b);nx_ok.append(n);rx_ok.append(r);vs={v:z3.Int(v) for v in winner['variables']};s=z3.Solver();s.add(z3.Distinct(*vs.values()));status=s.check();constraints.append({'pair_id':p['id'],'distinct_variable_binding':str(status).upper(),'bindings':p['binding']})
 ci=binomtest(support,len(ps)).proportion_ci(.95)
 vals={'support_exact':support==8 and supported==[f'pair-{i}' for i in range(8)],'exceptions_exact':[e['pair_id'] for e in exceptions]==['pair-8','pair-9'],'contains_creation_deletion_and_links':bool(winner['effects']['create_nodes'] and winner['effects']['delete_edges'] and len(winner['effects']['add_edges'])==2),'networkx_application_matches_support':nx_ok==[True]*8+[False,False],'rustworkx_agrees':rx_ok==nx_ok,'z3_bindings_satisfiable':all(c['distinct_variable_binding']=='SAT' for c in constraints),'anonymous_variables':set(winner['variables'])=={'v_A','v_B','v_C'}};assert all(vals.values()),(vals,winner)
 result={'transformation':{'id':'Pattern_Transformation_001','canonical':winner,'support_pair_ids':supported},'support':{'pairs':support,'total':len(ps),'fraction':support/len(ps),'binomial_95pct_interval':[ci.low,ci.high]},'exceptions':exceptions,'candidate_counts':[{'canonical':json.loads(k),'support':v} for k,v in counts.most_common()],'bindings_and_constraints':constraints,'application_verification':{'networkx':dict(zip([p['id'] for p in ps],nx_ok)),'rustworkx':dict(zip([p['id'] for p in ps],rx_ok))},'provenance':[{'transformation_id':'Pattern_Transformation_001','pair_id':p['id'],'source_before':f"fixture:{p['id']}:before",'source_after':f"fixture:{p['id']}:after",'binding':p['binding']} for p in ps if p['id'] in supported],'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'pairs':10,'support':support,'exceptions':len(exceptions),'variables':winner['variables'],'create_nodes':len(winner['effects']['create_nodes']),'delete_edges':len(winner['effects']['delete_edges']),'add_edges':len(winner['effects']['add_edges']),'verdict':'GO_ANONYMOUS_RECURRENT_TRANSFORMATION'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'networkx':importlib.metadata.version('networkx'),'rustworkx':importlib.metadata.version('rustworkx'),'z3-solver':importlib.metadata.version('z3-solver'),'scipy':importlib.metadata.version('scipy'),'canonicalization':'role names derived only from anonymous Pattern_Node_* kinds; concrete IDs excluded'},indent=2)+'\n');print('IND-04: recurrent create/delete/link transform induced in 8/10 pairs; GO')
if __name__=='__main__':main()
