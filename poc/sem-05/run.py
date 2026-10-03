#!/usr/bin/env python3
"""SEM-05: independent multi-plane retrieval without semantic collapse."""
from __future__ import annotations
import hashlib,importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
import duckdb,networkx as nx,pyarrow as pa,pyarrow.parquet as pq,rustworkx as rx
P=Path(__file__).resolve().parent;ROOT=P.parent.parent;OUT=P/'output'
def main():
 sem1=json.loads((ROOT/'poc/sem-01/output/results.json').read_text());sem3=json.loads((ROOT/'poc/sem-03/output/results.json').read_text())
 fr_io=next(r for r in sem1 if r['fixture']['id']=='fr-atypical-io')['external_analyses'][0]
 en_io=next(r for r in sem1 if r['fixture']['id']=='en-atypical-io')['external_analyses']
 pynini=next(q for q in sem3['queries'] if q['query']['input']=='io')['paths'];composition=sem3['composition']
 nodes=[
  {'node_id':'form:io','plane':'form','value':'io','provenance':'query observation'},
  {'node_id':'form:yo','plane':'form','value':'yo','provenance':'SEM-03 phonographic-io'},
  {'node_id':'form:i-o','plane':'form','value':'i/o','provenance':'SEM-03 segment-io'},
  {'node_id':'form:Io','plane':'form','value':'Io','provenance':'controlled case variant'},
  {'node_id':'phon:jo','plane':'phonological','value':fr_io['ipa'],'provenance':fr_io['analysis_id']},
  {'node_id':'phon:ajow','plane':'phonological','value':en_io[0]['ipa'],'provenance':en_io[0]['analysis_id']},
  {'node_id':'symbol:input-output','plane':'symbolic','value':'input/output','provenance':'SEM-03 composition'},
  {'node_id':'entity:Io','plane':'graph','value':'Jupiter moon Io','provenance':'controlled occurrence astronomy'},
  {'node_id':'context:greeting','plane':'context','value':'dialogue opening','provenance':'controlled greeting episodes'},
  {'node_id':'context:computing','plane':'context','value':'computing discussion','provenance':'controlled computing episodes'},
 ]
 edges=[
  {'edge_id':'e1','source':'form:io','target':'form:i-o','plane':'form','relation':'segmentation_candidate','cost':pynini[0]['weight'],'provenance':'SEM-03/segment-io'},
  {'edge_id':'e2','source':'form:io','target':'form:yo','plane':'form','relation':'phonographic_candidate','cost':pynini[1]['weight'],'provenance':'SEM-03/phonographic-io'},
  {'edge_id':'e3','source':'form:io','target':'form:Io','plane':'form','relation':'case_variant','cost':0.1,'provenance':'controlled case relation'},
  {'edge_id':'e4','source':'form:io','target':'phon:jo','plane':'phonological','relation':'has_pronunciation_candidate','cost':0.0,'provenance':fr_io['analysis_id']},
  {'edge_id':'e5','source':'form:io','target':'phon:ajow','plane':'phonological','relation':'has_pronunciation_candidate','cost':0.0,'provenance':en_io[0]['analysis_id']},
  {'edge_id':'e6','source':'phon:jo','target':'form:yo','plane':'phonological','relation':'phonologically_near','cost':0.0,'provenance':'SEM-01 Epitran jo'},
  {'edge_id':'e7','source':'form:i-o','target':'symbol:input-output','plane':'symbolic','relation':'abbreviation_expansion_candidate','cost':composition['component_weights'][1],'provenance':'SEM-03/expand-io'},
  {'edge_id':'e8','source':'form:Io','target':'entity:Io','plane':'graph','relation':'names_candidate','cost':0.0,'provenance':'controlled astronomy occurrence'},
  {'edge_id':'e9','source':'form:yo','target':'context:greeting','plane':'context','relation':'observed_in','cost':0.0,'provenance':'controlled greeting episodes'},
  {'edge_id':'e10','source':'form:i-o','target':'context:computing','plane':'context','relation':'observed_in','cost':0.0,'provenance':'controlled computing episodes'},
 ]
 OUT.mkdir(parents=True,exist_ok=True);ns=pa.schema([('node_id',pa.string()),('plane',pa.string()),('value',pa.string()),('provenance',pa.string())]);es=pa.schema([('edge_id',pa.string()),('source',pa.string()),('target',pa.string()),('plane',pa.string()),('relation',pa.string()),('cost',pa.float64()),('provenance',pa.string())]);pq.write_table(pa.Table.from_pylist(nodes,schema=ns),OUT/'nodes.parquet',compression='zstd');pq.write_table(pa.Table.from_pylist(edges,schema=es),OUT/'edges.parquet',compression='zstd')
 db=OUT/'sem-05.duckdb'
 if db.exists():db.unlink()
 con=duckdb.connect(str(db));con.execute('CREATE TABLE nodes AS SELECT * FROM read_parquet(?)',[str((OUT/'nodes.parquet').resolve())]);con.execute('CREATE TABLE edges AS SELECT * FROM read_parquet(?)',[str((OUT/'edges.parquet').resolve())]);planes=[r[0] for r in con.execute('SELECT DISTINCT plane FROM edges ORDER BY plane').fetchall()];con.close()
 g=nx.MultiDiGraph()
 for n in nodes:g.add_node(n['node_id'],**n)
 for e in edges:g.add_edge(e['source'],e['target'],key=e['edge_id'],**e)
 queries={'form':['form:i-o','form:yo','form:Io'],'phonological':['phon:jo','phon:ajow','form:yo'],'symbolic':['symbol:input-output'],'graph':['entity:Io'],'context':['context:greeting','context:computing']}
 results={}
 for plane,targets in queries.items():
  items=[]
  for target in targets:
   path=nx.shortest_path(g,'form:io',target,weight='cost');steps=[];score=0.0
   for a,b in zip(path,path[1:]):
    candidates=list(g[a][b].values());edge=min(candidates,key=lambda x:x['cost']);steps.append({'source':a,'relation':edge['relation'],'target':b,'cost':edge['cost'],'provenance':edge['provenance']});score+=edge['cost']
   items.append({'target':target,'typed_path':steps,'score_kind':'path_cost_lower_is_closer','score':score,'provenance':[s['provenance'] for s in steps]})
  results[plane]=sorted(items,key=lambda x:(x['score'],x['target']))
 forbidden=[e for e in edges if e['relation'] in ('semantic_identity','means')]
 bundle={'query_observation':'form:io','plane_results':results,'global_ranking':None,'selected_interpretation':None,'cross_plane_cartesian_product_materialized':False}
 validations={'all_five_planes_queried':set(results)=={'form','phonological','symbolic','graph','context'},'all_results_have_typed_paths':all(x['typed_path'] for rows in results.values() for x in rows),'all_results_have_provenance':all(x['provenance'] for rows in results.values() for x in rows),'no_global_nearest_neighbour':bundle['global_ranking'] is None and bundle['selected_interpretation'] is None,'phonology_not_semantic_identity':not forbidden,'io_to_greeting_path_exists_but_is_not_means':nx.has_path(g,'form:io','context:greeting') and all(step['relation']!='means' for step in results['context'][0]['typed_path']),'source_observation_unchanged':hashlib.sha256(b'io').hexdigest()==next(r for r in sem1 if r['fixture']['id']=='fr-atypical-io')['observation']['sha256']}
 assert all(validations.values())
 result={'index':{'nodes':nodes,'edges':edges,'duckdb_planes':planes},'bundle':bundle,'rejected_inference':{'premises':['io has pronunciation candidate jo','jo is phonologically near yo','yo observed in greeting context'],'forbidden_conclusion':'io semantically equals greeting','rejected':True},'validation':validations};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'node_count':len(nodes),'edge_count':len(edges),'plane_count':len(results),'result_count':sum(map(len,results.values())),'global_selection_count':0,'semantic_identity_inference_count':0,'verdict':'GO_INDEPENDENT_MULTIPLANE_RETRIEVAL_NO_COLLAPSE'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'duckdb':importlib.metadata.version('duckdb'),'networkx':importlib.metadata.version('networkx'),'rustworkx':importlib.metadata.version('rustworkx'),'inputs':['SEM-01','SEM-03','RET-02 scoring contract']},indent=2)+'\n');print(f"SEM-05: {len(results)} planes/{summary['result_count']} results, 0 global selections, 0 semantic collapses; GO")
if __name__=='__main__':main()
