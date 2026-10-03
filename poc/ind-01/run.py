#!/usr/bin/env python3
"""IND-01: odis FCA structures and explicit operational qualification."""
from __future__ import annotations
import importlib.metadata,json,platform,time,tracemalloc
from datetime import datetime,timezone
from pathlib import Path
import odis
P=Path(__file__).resolve().parent;OUT=P/'output'
def encode(concepts):
 rows=[]
 for i,c in enumerate(concepts):rows.append({'id':f'c{i}','extent':sorted(c.extent),'intent':sorted(c.intent)})
 return rows
def covers(rows):
 out=[]
 for lower in rows:
  a=set(lower['intent'])
  for upper in rows:
   b=set(upper['intent'])
   if a<b and not any(a<set(mid['intent'])<b for mid in rows):out.append({'less_specific':lower['id'],'more_specific':upper['id']})
 return out
def rss():
 for line in Path('/proc/self/status').read_text().splitlines():
  if line.startswith('VmRSS:'):return int(line.split()[1])*1024
 return 0
def sparse(n):return {f'o{i:05d}':[f'a{i%16:02d}',f'b{i%16:02d}'] for i in range(n)}
def main():
 OUT.mkdir(parents=True,exist_ok=True);ctx=odis.FormalContext.from_dict({'o1':['a','b'],'o2':['a','c'],'o3':['a','b','c']});rows=encode(ctx.concepts());order=covers(rows)
 expected={(('o1','o2','o3'),('a',)),(('o1','o3'),('a','b')),(('o2','o3'),('a','c')),(('o3',),('a','b','c'))};actual={(tuple(r['extent']),tuple(r['intent'])) for r in rows}
 snapshot=encode(ctx.concepts());ctx.add_object('o4',['a']);mutated=encode(ctx.concepts());snapshot_still=snapshot==rows
 measurements=[]
 for n in (100,500,1000,5000):
  before=rss();tracemalloc.start();start=time.perf_counter_ns();c=odis.FormalContext.from_dict(sparse(n));built=time.perf_counter_ns();concepts=encode(c.concepts());done=time.perf_counter_ns();_,peak=tracemalloc.get_traced_memory();tracemalloc.stop();measurements.append({'objects':n,'attributes':32,'incidences':2*n,'density':2/32,'concept_count':len(concepts),'build_latency_ns':built-start,'enumeration_latency_ns':done-built,'python_peak_bytes':peak,'rss_delta_bytes':max(0,rss()-before)})
 api=set(dir(odis.FormalContext));qual={'incremental':{'context_mutation_available':{'value':{'add_object','remove_object','add_attribute','remove_attribute'}<=api,'evidence':['add_object','remove_object','add_attribute','remove_attribute']},'incremental_lattice_maintenance':{'value':False,'evidence':'No update-concepts/lattice API; concepts() is explicitly called again after mutation.'}},'pruned':{'value':False,'lazy_enumeration_available':True,'evidence':'concepts(lazy=True) is a generator but exposes no pruning predicate or support threshold.'},'utility_driven':{'value':False,'evidence':'No utility/cost argument in the FormalContext or concepts API.'},'disk_aware':{'value':False,'serialization_available':{'to_file','from_file'}<=api,'evidence':'Serialization exists, but concept enumeration operates on the in-memory FormalContext.'}}
 vals={'expected_lattice_exact':actual==expected,'cover_order_has_four_edges':len(order)==4,'closure_extent':sorted(ctx.extent(['b']))==['o1','o3'],'closure_intent':sorted(ctx.intent(['o1','o3']))==['a','b'],'mutation_changes_recomputed_lattice':mutated!=snapshot and any('o4' in r['extent'] for r in mutated),'pre_mutation_snapshot_remains_valid':snapshot_still,'sparse_runs_complete':len(measurements)==4 and all(m['concept_count']==18 for m in measurements),'qualifications_separate':set(qual)=={'incremental','pruned','utility_driven','disk_aware'}};assert all(vals.values()),vals
 result={'controlled_context':{'objects':['o1','o2','o3'],'attributes':['a','b','c'],'concepts':rows,'cover_order':order},'mutation':{'operation':'add o4 with {a}','snapshot_before':snapshot,'recomputed_after':mutated,'snapshot_remained_valid':snapshot_still},'sparse_measurements':measurements,'operational_qualification':qual,'memory_scope':'Python tracemalloc plus process RSS delta; native Rust allocation attribution is not isolated','validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'controlled_concepts':len(rows),'cover_edges':len(order),'largest_objects':measurements[-1]['objects'],'largest_concepts':measurements[-1]['concept_count'],'context_mutation':True,'incremental_lattice':False,'pruned':False,'utility_driven':False,'disk_aware':False,'verdict':'GO_FCA_STRUCTURES_WITH_CAPABILITY_GAPS'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'odis-python':importlib.metadata.version('odis-python'),'sparse_design':'32 attributes, 16 repeated disjoint attribute pairs, 2 incidences/object'},indent=2)+'\n');print('IND-01: exact 4-concept lattice; mutation yes, incremental lattice/pruning/utility/disk no; GO')
if __name__=='__main__':main()
