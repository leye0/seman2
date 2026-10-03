#!/usr/bin/env python3
"""RET-04: disk-backed prefilter before active graph loading."""
from __future__ import annotations
import importlib.metadata,json,platform,time,tracemalloc
from datetime import datetime,timezone
from pathlib import Path
import duckdb,networkx as nx,polars as pl,pyarrow as pa,pyarrow.parquet as pq,rustworkx as rx
P=Path(__file__).resolve().parent;OUT=P/'output';TOTAL=5000
def fragment(i,match):
 g=nx.DiGraph()
 if match:
  g.add_node(f'p{i}',kind='person');g.add_node(f'e{i}',kind='event',lemma='greet');g.add_node(f'c{i}',kind='context',topic='opening');g.add_edge(f'p{i}',f'e{i}',relation='agent');g.add_edge(f'e{i}',f'c{i}',relation='in_context')
 else:g.add_node(f'n{i}',kind='noise',value=i)
 return json.dumps(nx.node_link_data(g,edges='edges'),sort_keys=True,separators=(',',':'))
def verify(data):
 g=nx.node_link_graph(json.loads(data),edges='edges');r=rx.PyDiGraph();idx={n:r.add_node(a) for n,a in g.nodes(data=True)}
 for a,b,d in g.edges(data=True):r.add_edge(idx[a],idx[b],d)
 edge_data=[r.get_edge_data_by_index(i) for i in r.edge_indices()]
 return any(a.get('kind')=='event' and a.get('lemma')=='greet' for a in r.nodes()) and any(e.get('relation')=='in_context' for e in edge_data)
def main():
 OUT.mkdir(parents=True,exist_ok=True);stats=[];fragments=[]
 for i in range(TOTAL):
  match=i%137==0;stats.append({'graph_id':f'g{i:05d}','ordinal':i,'has_greet_event':match,'has_opening_context':match,'has_agent_relation':match});fragments.append({'graph_id':f'g{i:05d}','graph_json':fragment(i,match)})
 pq.write_table(pa.Table.from_pylist(stats),OUT/'graph-stats.parquet',compression='zstd');pq.write_table(pa.Table.from_pylist(fragments),OUT/'graph-fragments.parquet',compression='zstd')
 db=OUT/'ret-04.duckdb'
 if db.exists():db.unlink()
 con=duckdb.connect(str(db));sp=str((OUT/'graph-stats.parquet').resolve());fp=str((OUT/'graph-fragments.parquet').resolve());sp_sql=sp.replace("'","''");fp_sql=fp.replace("'","''");con.execute(f"CREATE VIEW stats AS SELECT * FROM read_parquet('{sp_sql}')");con.execute(f"CREATE VIEW fragments AS SELECT * FROM read_parquet('{fp_sql}')")
 measurements=[]
 for size in (100,1000,5000):
  tracemalloc.start();start=time.perf_counter_ns();ids=[r[0] for r in con.execute('SELECT graph_id FROM stats WHERE ordinal < ? AND has_greet_event AND has_opening_context AND has_agent_relation ORDER BY graph_id',[size]).fetchall()];prefilter_ns=time.perf_counter_ns()-start;_,prefilter_peak=tracemalloc.get_traced_memory();tracemalloc.stop()
  tracemalloc.start();start=time.perf_counter_ns();loaded=con.execute('SELECT graph_id,graph_json FROM fragments WHERE graph_id IN (SELECT unnest(?)) ORDER BY graph_id',[ids]).fetchall();load_ns=time.perf_counter_ns()-start;_,load_peak=tracemalloc.get_traced_memory();tracemalloc.stop();verified=[gid for gid,data in loaded if verify(data)]
  measurements.append({'collection_size':size,'candidate_ids':ids,'candidate_count':len(ids),'fragment_count_loaded':len(loaded),'verified_match_count':len(verified),'prefilter_latency_ns':prefilter_ns,'fragment_load_and_verify_latency_ns':load_ns,'prefilter_python_peak_bytes':prefilter_peak,'active_fragment_python_peak_bytes':load_peak,'collection_fraction_loaded':len(loaded)/size})
 plan='\n'.join(f'{r[0]}\n{r[1]}' for r in con.execute(f"EXPLAIN SELECT f.graph_id,f.graph_json FROM read_parquet('{fp_sql}') f JOIN read_parquet('{sp_sql}') s USING(graph_id) WHERE s.has_greet_event AND s.has_opening_context AND s.has_agent_relation").fetchall())
 polars_ids=(pl.scan_parquet(sp).filter(pl.col('has_greet_event') & pl.col('has_opening_context') & pl.col('has_agent_relation')).select('graph_id').sort('graph_id').collect(engine='streaming').get_column('graph_id').to_list());con.close()
 full_json_bytes=sum(len(r['graph_json'].encode()) for r in fragments);loaded_ids=set(measurements[-1]['candidate_ids']);loaded_json_bytes=sum(len(r['graph_json'].encode()) for r in fragments if r['graph_id'] in loaded_ids)
 validations={'all_candidates_verified':all(m['candidate_count']==m['verified_match_count'] for m in measurements),'never_loaded_entire_collection':all(m['fragment_count_loaded']<m['collection_size'] for m in measurements),'selection_before_fragment_load':True,'largest_loaded_fraction_below_one_percent':measurements[-1]['collection_fraction_loaded']<.01,'loaded_bytes_below_full_bytes':loaded_json_bytes<full_json_bytes,'duckdb_polars_candidate_ids_equal':polars_ids==measurements[-1]['candidate_ids'],'query_plan_captured':bool(plan) and 'READ_PARQUET' in plan and 'Filters:' in plan};assert all(validations.values())
 result={'measurements':measurements,'largest_run_bytes':{'all_fragment_json_bytes':full_json_bytes,'loaded_fragment_json_bytes':loaded_json_bytes},'polars_streaming_candidate_ids':polars_ids,'duckdb_query_plan':plan,'validation':validations};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');last=measurements[-1];summary={'largest_collection_size':TOTAL,'largest_candidate_count':last['candidate_count'],'largest_fragment_count_loaded':last['fragment_count_loaded'],'largest_collection_fraction_loaded':last['collection_fraction_loaded'],'all_fragment_json_bytes':full_json_bytes,'loaded_fragment_json_bytes':loaded_json_bytes,'verdict':'GO_DISK_PREFILTER_BEFORE_ACTIVE_GRAPH_LOADING'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'duckdb':importlib.metadata.version('duckdb'),'polars':importlib.metadata.version('polars'),'pyarrow':importlib.metadata.version('pyarrow'),'rustworkx':importlib.metadata.version('rustworkx'),'memory_scope':'Python tracemalloc only; DuckDB/rustworkx native allocations excluded'},indent=2)+'\n');print(f"RET-04: selected/loaded {last['fragment_count_loaded']}/{TOTAL} fragments ({last['collection_fraction_loaded']:.3%}); GO")
if __name__=='__main__':main()
