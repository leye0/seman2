#!/usr/bin/env python3
"""IND-01: odis FCA structures and explicit operational qualification."""
from __future__ import annotations
import hashlib,importlib.metadata,json,platform,time,tracemalloc
from datetime import datetime,timezone
from pathlib import Path
import odis
P=Path(__file__).resolve().parent;OUT=P/'output';ROOT=P.parents[1]
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
def integrated_hypothesis_context():
 path=ROOT/'poc/hyp-04/output/results.json';raw=path.read_bytes();source=json.loads(raw);source_hash=hashlib.sha256(raw).hexdigest();attributes={hypothesis_id:set() for hypothesis_id in source['upstream']['hypothesis_artifact_ids']}
 for hypothesis_id,supports in source['upstream']['justification_supports'].items():
  attributes[hypothesis_id].update(f'justification:{support}' for support in supports)
 for entry in source['ledger']:
  attributes[entry['hypothesis_id']].add(f"evidence-family:{entry['family']}")
 context_dict={hypothesis_id:sorted(values) for hypothesis_id,values in sorted(attributes.items())};context=odis.FormalContext.from_dict(context_dict);concepts=encode(context.concepts());common_intent=sorted(context.intent(sorted(context_dict)))
 artifact_ids=source['upstream']['hypothesis_artifact_ids'];details={'source':{'poc':'HYP-04','results_sha256':source_hash},'objects':[{'hypothesis_id':hypothesis_id,'hypothesis_artifact_id':artifact_ids[hypothesis_id],'attributes':values} for hypothesis_id,values in context_dict.items()],'attributes':sorted({attribute for values in context_dict.values() for attribute in values}),'concepts':concepts,'cover_order':covers(concepts),'common_intent':common_intent}
 validations={'actual_all_hypotheses_are_objects':set(context_dict)==set(artifact_ids),'actual_artifact_ids_preserved':all(row['hypothesis_artifact_id']==artifact_ids[row['hypothesis_id']] for row in details['objects']),'actual_ledger_families_materialized':all(f"evidence-family:{entry['family']}" in context_dict[entry['hypothesis_id']] for entry in source['ledger']),'actual_leaf_supports_materialized':all(f'justification:{support}' in context_dict[hypothesis_id] for hypothesis_id,supports in source['upstream']['justification_supports'].items() for support in supports),'actual_shared_surface_support_in_common_intent':'justification:support:surface-io' in common_intent,'actual_concepts_nonempty':bool(concepts)}
 return details,validations
def main():
 OUT.mkdir(parents=True,exist_ok=True);ctx=odis.FormalContext.from_dict({'o1':['a','b'],'o2':['a','c'],'o3':['a','b','c']});rows=encode(ctx.concepts());order=covers(rows)
 expected={(('o1','o2','o3'),('a',)),(('o1','o3'),('a','b')),(('o2','o3'),('a','c')),(('o3',),('a','b','c'))};actual={(tuple(r['extent']),tuple(r['intent'])) for r in rows}
 snapshot=encode(ctx.concepts());ctx.add_object('o4',['a']);mutated=encode(ctx.concepts());snapshot_still=snapshot==rows
 measurements=[]
 for n in (100,500,1000,5000):
  before=rss();tracemalloc.start();start=time.perf_counter_ns();c=odis.FormalContext.from_dict(sparse(n));built=time.perf_counter_ns();concepts=encode(c.concepts());done=time.perf_counter_ns();_,peak=tracemalloc.get_traced_memory();tracemalloc.stop();measurements.append({'objects':n,'attributes':32,'incidences':2*n,'density':2/32,'concept_count':len(concepts),'build_latency_ns':built-start,'enumeration_latency_ns':done-built,'python_peak_bytes':peak,'rss_delta_bytes':max(0,rss()-before)})
 api=set(dir(odis.FormalContext));qual={'incremental':{'context_mutation_available':{'value':{'add_object','remove_object','add_attribute','remove_attribute'}<=api,'evidence':['add_object','remove_object','add_attribute','remove_attribute']},'incremental_lattice_maintenance':{'value':False,'evidence':'No update-concepts/lattice API; concepts() is explicitly called again after mutation.'}},'pruned':{'value':False,'lazy_enumeration_available':True,'evidence':'concepts(lazy=True) is a generator but exposes no pruning predicate or support threshold.'},'utility_driven':{'value':False,'evidence':'No utility/cost argument in the FormalContext or concepts API.'},'disk_aware':{'value':False,'serialization_available':{'to_file','from_file'}<=api,'evidence':'Serialization exists, but concept enumeration operates on the in-memory FormalContext.'}}
 integrated,integrated_vals=integrated_hypothesis_context();vals={'expected_lattice_exact':actual==expected,'cover_order_has_four_edges':len(order)==4,'closure_extent':sorted(ctx.extent(['b']))==['o1','o3'],'closure_intent':sorted(ctx.intent(['o1','o3']))==['a','b'],'mutation_changes_recomputed_lattice':mutated!=snapshot and any('o4' in r['extent'] for r in mutated),'pre_mutation_snapshot_remains_valid':snapshot_still,'sparse_runs_complete':len(measurements)==4 and all(m['concept_count']==18 for m in measurements),'qualifications_separate':set(qual)=={'incremental','pruned','utility_driven','disk_aware'},**integrated_vals};assert all(vals.values()),vals
 result={'controlled_context':{'objects':['o1','o2','o3'],'attributes':['a','b','c'],'concepts':rows,'cover_order':order},'mutation':{'operation':'add o4 with {a}','snapshot_before':snapshot,'recomputed_after':mutated,'snapshot_remained_valid':snapshot_still},'sparse_measurements':measurements,'integrated_hypothesis_context':integrated,'operational_qualification':qual,'memory_scope':'Python tracemalloc plus process RSS delta; native Rust allocation attribution is not isolated','validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'controlled_concepts':len(rows),'cover_edges':len(order),'largest_objects':measurements[-1]['objects'],'largest_concepts':measurements[-1]['concept_count'],'integrated_objects':len(integrated['objects']),'integrated_attributes':len(integrated['attributes']),'integrated_concepts':len(integrated['concepts']),'context_mutation':True,'incremental_lattice':False,'pruned':False,'utility_driven':False,'disk_aware':False,'verdict':'GO_FCA_STRUCTURES_WITH_CAPABILITY_GAPS'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'odis-python':importlib.metadata.version('odis-python'),'sparse_design':'32 attributes, 16 repeated disjoint attribute pairs, 2 incidences/object','hyp04_sha256':integrated['source']['results_sha256']},indent=2)+'\n');print('IND-01: exact 4-concept lattice; mutation yes, incremental lattice/pruning/utility/disk no; GO')
if __name__=='__main__':main()
