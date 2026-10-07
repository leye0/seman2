#!/usr/bin/env python3
"""SOAR-01: bounded active context represented and read through real SML WMEs."""
from __future__ import annotations
import hashlib,json,os,platform,re,sys
from datetime import datetime,timezone
from pathlib import Path
import pyarrow as pa,pyarrow.parquet as pq
import Python_sml_ClientInterface as sml
P=Path(__file__).resolve().parent;OUT=P/'output';ROOT=P.parents[1]
sys.path.insert(0,str(ROOT))
from seman2_runtime.cognitive_checkpoint_inspection import ancestry,artifact_index,artifacts_of_type,load_verified_session_checkpoint
def walk(identifier,registry=None,ancestors=None):
 registry={} if registry is None else registry
 ancestors=set() if ancestors is None else ancestors;name=identifier.GetIdentifierName()
 if name in ancestors:return {'identifier':name,'cycle_reference':True}
 ancestors=ancestors|{name};children=[]
 for i in range(identifier.GetNumberChildren()):
  w=identifier.GetChild(i);row={'attribute':w.GetAttribute(),'value_type':w.GetValueType(),'time_tag':w.GetTimeTag()}
  if w.IsIdentifier():
   target_name=w.GetValueAsString();target=registry.get(target_name.upper())
   row['value']=walk(target,registry,ancestors) if target is not None else {'identifier':target_name,'unresolved_client_handle':True}
  else:row['value']=w.GetValueAsString()
  children.append(row)
 return {'identifier':name,'children':children}
def leaf_values(tree):
 out=[]
 for c in tree.get('children',[]):
  if isinstance(c['value'],dict):out.extend(leaf_values(c['value']))
  else:out.append((c['attribute'],c['value']))
 return out
def parse_print_wmes(rendered):
 """Extract attribute/value pairs from Soar's own recursive `print` output."""
 return [(m.group(1),m.group(2) if m.group(2) is not None else m.group(3)) for m in re.finditer(r'\^([^\s()]+) (?:\|([^|]*)\||([^\s()]+))',rendered)]
def main():
 OUT.mkdir(parents=True,exist_ok=True);store=[{'hypothesis_id':'H1','score':.91,'family':'F-A','active_beam':True},{'hypothesis_id':'H2','score':.78,'family':'F-B','active_beam':True},{'hypothesis_id':'H3','score':.73,'family':'F-C','active_beam':False},{'hypothesis_id':'H4','score':.69,'family':'F-A','active_beam':False}];pq.write_table(pa.Table.from_pylist(store),OUT/'persistent-hypotheses.parquet',compression='zstd')
 run01_path=ROOT/'poc/run-01/output/results.json';run01=json.loads(run01_path.read_text());checkpoint=ROOT/'poc/run-01/output/checkpoint-epoch-0/cognitive-session.json';checkpoint_hash=hashlib.sha256(checkpoint.read_bytes()).hexdigest();payload=load_verified_session_checkpoint(checkpoint);artifacts=artifact_index(payload);actual_soar=artifacts_of_type(payload,'soar-control-state')[0];actual_family=artifacts[actual_soar['payload_native']['family_ref']];actual_ancestry=ancestry(artifacts,actual_soar['artifact_id']);actual_active=actual_soar['payload_native']['active_refs'];actual_justification_count=sum(len(artifacts[ref]['justification_ids']) for ref in actual_active);actual={'checkpoint_sha256':checkpoint_hash,'soar_control_artifact_id':actual_soar['artifact_id'],'family_artifact_id':actual_family['artifact_id'],'active_refs':actual_active,'inactive_refs':actual_soar['payload_native']['inactive_refs'],'selection_policy':actual_soar['payload_native']['selection_policy'],'active_context_digest':actual_soar['payload_native']['active_context_digest'],'projected_justification_ref_count':actual_soar['payload_native']['projected_justification_ref_count'],'ancestry_size':len(actual_ancestry),'ancestry_types':sorted({row['artifact_type'] for row in actual_ancestry})}
 kernel=sml.Kernel.CreateKernelInNewThread();assert not kernel.HadError();agent=kernel.CreateAgent('soar01');assert agent and not agent.HadError();version=agent.ExecuteCommandLine('version');il=agent.GetInputLink();context=il.CreateIdWME('active-context');phase=context.CreateStringWME('phase','initial');context.CreateStringWME('goal','G-answer');context.CreateStringWME('provenance','fixture:soar-01')
 graph=context.CreateIdWME('graph-fragment');graph.CreateStringWME('external-id','GF-17');v=graph.CreateIdWME('variable');v.CreateStringWME('external-id','V-x');v.CreateStringWME('type','entity');constraint=graph.CreateIdWME('constraint');constraint.CreateStringWME('external-id','C-distinct');constraint.CreateStringWME('expression','V-x != V-y');retrieved=context.CreateIdWME('retrieved-structure');retrieved.CreateStringWME('external-id','RET-episode-42');retrieved.CreateStringWME('source-store','episodic-parquet')
 justifications={}
 for hid in ('H1','H2'):
  j=context.CreateIdWME('justification');j.CreateStringWME('external-id',f'J-{hid}');j.CreateStringWME('evidence-id',f'E-{hid}');justifications[hid]=j
 beam=context.CreateIdWME('beam');beam.CreateIntWME('bound',2);hypothesis_handles=[]
 for hrow in store[:2]:
  h=beam.CreateIdWME('hypothesis');hypothesis_handles.append(h);h.CreateStringWME('external-id',hrow['hypothesis_id']);h.CreateFloatWME('score',hrow['score']);h.CreateStringWME('family',hrow['family']);h.CreateSharedIdWME('supported-by',justifications[hrow['hypothesis_id']]);h.CreateSharedIdWME('uses-graph',graph)
 agent.Commit();phase_before=phase.GetValueAsString()
 rules='''
sp {soar01*select-initial
 (state <s> ^superstate nil ^io <io>)
 (<io> ^input-link <i> ^output-link <o>)
 (<i> ^active-context <c>) (<c> ^phase initial ^beam <b>)
 (<b> ^hypothesis <h>) (<h> ^external-id H1)
 --> (<o> ^selected-hypothesis H1 ^selection-cycle 1)}
sp {soar01*select-revised
 (state <s> ^superstate nil ^io <io>)
 (<io> ^input-link <i> ^output-link <o>)
 (<i> ^active-context <c>) (<c> ^phase revised ^beam <b>)
 (<b> ^hypothesis <h>) (<h> ^external-id H2)
 --> (<o> ^selected-hypothesis H2 ^selection-cycle 2)}
''';source_result=agent.ExecuteCommandLine(rules);cycle1=agent.ExecuteCommandLine('run 1');agent.SynchronizeOutputLink();output1=agent.GetOutputLink();out1=walk(output1,{output1.GetIdentifierName().upper():output1});input_print_before=agent.ExecuteCommandLine(f"print {il.GetIdentifierName()} --depth 12");phase.Update('revised');phase_after=phase.GetValueAsString();agent.Commit();cycle2=agent.ExecuteCommandLine('run 1');agent.SynchronizeOutputLink();output2=agent.GetOutputLink();out2=walk(output2,{output2.GetIdentifierName().upper():output2});input_print_after=agent.ExecuteCommandLine(f"print {il.GetIdentifierName()} --depth 12");output_print=agent.ExecuteCommandLine(f"print {agent.GetOutputLink().GetIdentifierName()} --depth 4")
 before_leaves=parse_print_wmes(input_print_before);after_leaves=parse_print_wmes(input_print_after);out1_leaves=leaf_values(out1);out2_leaves=leaf_values(out2);kernel_ok=not kernel.HadError();kernel.DestroyAgent(agent);kernel.Shutdown()
 active_ids={v for a,v in after_leaves if a=='external-id' and v in {'H1','H2','H3','H4'}};external_ids={r['hypothesis_id'] for r in store if not r['active_beam']};vals={'real_sml_kernel_and_agent':kernel_ok,'beam_hypotheses_coexist':active_ids=={'H1','H2'},'inactive_alternatives_absent_from_wm':not (external_ids&{v for _,v in after_leaves}),'inactive_alternatives_persisted':external_ids=={'H3','H4'},'only_required_justifications_active':{v for a,v in after_leaves if a=='external-id' and v.startswith('J-')}=={'J-H1','J-H2'},'all_required_kinds_present':all(x in after_leaves for x in [('external-id','GF-17'),('external-id','V-x'),('external-id','C-distinct'),('external-id','RET-episode-42'),('goal','G-answer'),('provenance','fixture:soar-01')]),'cycle1_selected_h1':('selected-hypothesis','H1') in out1_leaves,'cycle2_selected_h2_only':('selected-hypothesis','H2') in out2_leaves and ('selected-hypothesis','H1') not in out2_leaves,'phase_modified_via_sml':phase_before=='initial' and phase_after=='revised' and ('phase','revised') in after_leaves,'rules_fired':('1 rule fired' in cycle1 and '1 rule fired' in cycle2)}
 vals.update({'actual_checkpoint_matches_run01':checkpoint_hash==run01['cognitive_ingestion']['checkpoint_sha256'],'actual_soar_native_projection_verified':actual_soar['status']=='success' and actual_soar['payload_native']['working_memory_verified'] and actual_soar['payload_native']['all_required_refs_observed_in_wm'],'actual_store_not_copied_to_soar':actual_soar['payload_native']['inactive_refs_absent_from_wm'] and not actual_soar['payload_projection']['persistent_store_copied_to_soar'],'actual_active_refs_belong_to_family':set(actual_active)<=set(actual_family['payload_native']['member_refs']),'actual_justifications_projected_exactly':actual_justification_count==actual_soar['payload_native']['projected_justification_ref_count'],'actual_bottom_up_ancestry_present':{'source-record','observation','mrs-analysis','semantic-structure','temporal-constraint-network','constraint-solution','hypothesis-family','soar-control-state'}<=set(actual['ancestry_types'])});assert all(vals.values()),(vals,out1_leaves,out2_leaves)
 result={'soar_version':version,'source_result':source_result,'cycle_traces':[cycle1,cycle2],'input_wmes_before':before_leaves,'input_wmes_after':after_leaves,'output_tree_cycle1':out1,'output_tree_cycle2':out2,'sml_prints':{'input_before':input_print_before,'input_after':input_print_after,'output_after':output_print},'persistent_store':store,'integrated_cognitive_checkpoint':actual,'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'persistent_hypotheses':len(store),'beam_bound':2,'active_hypotheses':sorted(active_ids),'inactive_persistent_hypotheses':sorted(external_ids),'cycle1_selection':'H1','cycle2_selection':'H2','actual_active_hypotheses':len(actual_active),'actual_projected_justifications':actual_justification_count,'verdict':'GO_REAL_SML_BOUNDED_WORKING_MEMORY'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'soar_version_output':version,'sml_module':sml.__file__,'pythonpath':os.environ.get('PYTHONPATH'),'beam_bound':2},indent=2)+'\n');print('SOAR-01: controlled and real cognitive SML active contexts verified; GO')
if __name__=='__main__':main()
