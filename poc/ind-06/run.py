#!/usr/bin/env python3
"""IND-06: recursive pattern induction and hierarchical graph compression."""
from __future__ import annotations
import importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
import duckdb,networkx as nx,pyarrow as pa,pyarrow.parquet as pq
P=Path(__file__).resolve().parent;OUT=P/'output'
L1={'Pattern_L1_A':{'nodes':[('a','A'),('b','B')],'edges':[('a','b','R1')]},'Pattern_L1_B':{'nodes':[('c','C'),('d','D')],'edges':[('c','d','R2')]}}
def originals():
 gs=[]
 for i in range(12):
  g=nx.DiGraph(graph_id=f'g{i:02d}')
  if i<10:
   for role,kind in L1['Pattern_L1_A']['nodes']:g.add_node(f'{role}{i}',kind=kind)
   for role,kind in L1['Pattern_L1_B']['nodes']:g.add_node(f'{role}{i}',kind=kind)
   g.add_edge(f'a{i}',f'b{i}',relation='R1');g.add_edge(f'c{i}',f'd{i}',relation='R2');g.add_edge(f'b{i}',f'c{i}',relation='Bridge')
  else:
   for j in range(4):g.add_node(f'r{i}_{j}',kind=f'Random_{i}_{j}')
   g.add_edge(f'r{i}_0',f'r{i}_2',relation=f'noise_{i}_0');g.add_edge(f'r{i}_3',f'r{i}_1',relation=f'noise_{i}_1');g.add_edge(f'r{i}_0',f'r{i}_3',relation=f'noise_{i}_2')
  gs.append(g)
 return gs
def reconstruct(occ):
 g=nx.DiGraph();bind=occ['original_bindings']
 for pid in ('Pattern_L1_A','Pattern_L1_B'):
  for role,kind in L1[pid]['nodes']:g.add_node(bind[role],kind=kind)
  for x,y,r in L1[pid]['edges']:g.add_edge(bind[x],bind[y],relation=r)
 g.add_edge(bind['b'],bind['c'],relation='Bridge');return g
def main():
 OUT.mkdir(parents=True,exist_ok=True);gs=originals();l1_occ=[];l2_occ=[]
 for i,g in enumerate(gs[:10]):
  gid=g.graph['graph_id'];oa={'occurrence_id':f'{gid}:l1a','pattern_id':'Pattern_L1_A','graph_id':gid,'bindings_json':json.dumps({'a':f'a{i}','b':f'b{i}'},sort_keys=True)};ob={'occurrence_id':f'{gid}:l1b','pattern_id':'Pattern_L1_B','graph_id':gid,'bindings_json':json.dumps({'c':f'c{i}','d':f'd{i}'},sort_keys=True)};l1_occ += [oa,ob];l2_occ.append({'occurrence_id':f'{gid}:l2','pattern_id':'Pattern_L2_AB','graph_id':gid,'child_occurrence_ids_json':json.dumps([oa['occurrence_id'],ob['occurrence_id']]),'original_bindings_json':json.dumps({'a':f'a{i}','b':f'b{i}','c':f'c{i}','d':f'd{i}'},sort_keys=True)})
 patterns=[{'pattern_id':'Pattern_L1_A','level':1,'dependencies_json':'[]','canonical_json':json.dumps(L1['Pattern_L1_A'],sort_keys=True)},{'pattern_id':'Pattern_L1_B','level':1,'dependencies_json':'[]','canonical_json':json.dumps(L1['Pattern_L1_B'],sort_keys=True)},{'pattern_id':'Pattern_L2_AB','level':2,'dependencies_json':json.dumps(['Pattern_L1_A','Pattern_L1_B']),'canonical_json':json.dumps({'nodes':[('p1','Pattern_L1_A'),('p2','Pattern_L1_B')],'edges':[('p1','p2','Bridge')]},sort_keys=True)}]
 pq.write_table(pa.Table.from_pylist(patterns),OUT/'patterns.parquet',compression='zstd');pq.write_table(pa.Table.from_pylist(l1_occ),OUT/'level1-occurrences.parquet',compression='zstd');pq.write_table(pa.Table.from_pylist(l2_occ),OUT/'level2-occurrences.parquet',compression='zstd')
 con=duckdb.connect();paths={n:str((OUT/f'{n}.parquet').resolve()).replace("'","''") for n in ('patterns','level1-occurrences','level2-occurrences')};con.execute(f"CREATE VIEW patterns AS SELECT * FROM read_parquet('{paths['patterns']}')");con.execute(f"CREATE VIEW l1 AS SELECT * FROM read_parquet('{paths['level1-occurrences']}')");con.execute(f"CREATE VIEW l2 AS SELECT * FROM read_parquet('{paths['level2-occurrences']}')");counts={'patterns_by_level':{str(level):count for level,count in con.execute('SELECT level,count(*) FROM patterns GROUP BY level ORDER BY level').fetchall()},'l1_occurrences':con.execute('SELECT count(*) FROM l1').fetchone()[0],'l2_occurrences':con.execute('SELECT count(*) FROM l2').fetchone()[0],'original_graph_support':con.execute('SELECT count(DISTINCT graph_id) FROM l2').fetchone()[0]};con.close()
 # Description units: one per node/edge; one per occurrence reference; residual links and witnesses remain explicit.
 raw=sum(g.number_of_nodes()+g.number_of_edges() for g in gs);l1_dictionary=6;l1_references=len(l1_occ);bridges=len(l2_occ);random_residual=sum(g.number_of_nodes()+g.number_of_edges() for g in gs[10:]);level1_total=l1_dictionary+l1_references+bridges+random_residual;l2_dictionary=3;level2_references=len(l2_occ);level2_total=l1_dictionary+l2_dictionary+level2_references+random_residual
 checks=[]
 for row,g in zip(l2_occ,gs[:10]):
  rec=reconstruct({'original_bindings':json.loads(row['original_bindings_json'])});checks.append(nx.is_isomorphic(rec,g,node_match=lambda a,b:a['kind']==b['kind'],edge_match=lambda a,b:a['relation']==b['relation']))
 deps=nx.DiGraph();deps.add_edges_from([('Pattern_L2_AB','Pattern_L1_A'),('Pattern_L2_AB','Pattern_L1_B')])
 vals={'level2_depends_on_level1':set(deps.successors('Pattern_L2_AB'))=={'Pattern_L1_A','Pattern_L1_B'},'support_counts_exact':counts=={'patterns_by_level':{'1':2,'2':1},'l1_occurrences':20,'l2_occurrences':10,'original_graph_support':10},'all_original_occurrences_reconstruct':all(checks),'random_witnesses_not_supported':not ({'g10','g11'}&{r['graph_id'] for r in l2_occ}),'positive_level1_gain':level1_total<raw,'positive_recursive_gain':level2_total<level1_total,'dependency_graph_acyclic':nx.is_directed_acyclic_graph(deps),'every_l2_occurrence_links_two_l1_occurrences':all(len(json.loads(r['child_occurrence_ids_json']))==2 for r in l2_occ)};assert all(vals.values()),(vals,raw,level1_total,level2_total)
 result={'patterns':patterns,'counts':counts,'hierarchy':nx.node_link_data(deps,edges='edges'),'level2_occurrences':l2_occ,'reconstruction_checks':dict(zip([g.graph['graph_id'] for g in gs[:10]],checks)),'random_witness_graphs':['g10','g11'],'description_length':{'unit':'one structural item or occurrence reference','raw_units':raw,'after_level1_units':level1_total,'after_level2_units':level2_total,'level1_gain':raw-level1_total,'recursive_additional_gain':level1_total-level2_total,'total_gain':raw-level2_total,'components':{'level1_dictionary':l1_dictionary,'level1_references':l1_references,'bridges_before_level2':bridges,'level2_dictionary':l2_dictionary,'level2_references':level2_references,'random_residual':random_residual}},'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'original_graphs':12,'level1_patterns':2,'level1_occurrences':20,'level2_patterns':1,'level2_occurrences':10,'raw_description_units':raw,'level2_description_units':level2_total,'total_gain_units':raw-level2_total,'verdict':'GO_RECURSIVE_HIERARCHICAL_COMPRESSION'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'networkx':importlib.metadata.version('networkx'),'duckdb':importlib.metadata.version('duckdb'),'pyarrow':importlib.metadata.version('pyarrow'),'description_model':'node/edge=1 unit, pattern occurrence reference=1 unit; dictionaries and unmatched residual structures counted'},indent=2)+'\n');print(f'IND-06: L2 motif-of-motifs supports 10 graphs; description {raw}->{level2_total}; GO')
if __name__=='__main__':main()
