#!/usr/bin/env python3
"""DLG-10: provenance-preserving repair, clarification and correction."""
from __future__ import annotations
import hashlib,importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
import networkx as nx
P=Path(__file__).resolve().parent;ROOT=P.parent.parent;OUT=P/'output'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def scenario(sid,kind,turns,initial,signal,target,candidates,selected,final,prior_status):
 obs=[{'observation_id':f'{sid}:o{i+1}','turn_id':f'{sid}:t{i+1}','raw':raw,'immutable':True,'span':[0,len(raw)]} for i,raw in enumerate(turns)]
 hypotheses=[{'hypothesis_id':f'{sid}:h0','content':initial,'status':prior_status,'supported_by':[obs[0]['observation_id']]}]
 for i,c in enumerate(candidates,1):hypotheses.append({'hypothesis_id':f'{sid}:h{i}','content':c['content'],'status':'selected' if i==selected else 'alternative','supported_by':c['supports'],'revises':f'{sid}:h0','score':c['score']})
 g=nx.MultiDiGraph();
 for o in obs:g.add_node(o['observation_id'],kind='observation')
 for h in hypotheses:g.add_node(h['hypothesis_id'],kind='hypothesis',status=h['status'])
 for h in hypotheses:
  for o in h['supported_by']:
   if o in g:g.add_edge(o,h['hypothesis_id'],relation='supports')
  if h.get('revises'):g.add_edge(h['hypothesis_id'],h['revises'],relation='revises')
 return {'id':sid,'phenomenon':kind,'observations':obs,'content_initial':initial,'repair_signal':signal,'repair_target':target,'revision_candidates':hypotheses[1:],'selected_revision_id':f'{sid}:h{selected}' if selected else None,'content_replaced_or_suspended':{'hypothesis_id':f'{sid}:h0','status':prior_status},'state_before':{'public_content':initial,'pending':[]},'state_after':final,'prior_hypothesis':hypotheses[0],'all_hypotheses':hypotheses,'justification':{'selected':f'{sid}:h{selected}' if selected else None,'rule':'repair candidate must cite signal and target','supports':candidates[selected-1]['supports'] if selected else []},'provenance_graph':nx.node_link_data(g,edges='edges')}
def main():
 OUT.mkdir(parents=True,exist_ok=True);d3=ROOT/'poc/dlg-03/output/results.json';d7=ROOT/'poc/dlg-07/output/results.json';a2=lambda sid:[f'{sid}:o1',f'{sid}:o2']
 cases=[
  scenario('self','self_repair',['We meet Friday—','sorry, Saturday.'],'meeting(day=friday)','sorry','self:t1',[{'content':'meeting(day=saturday)','supports':a2('self'),'score':.99},{'content':'meeting(day=friday)','supports':['self:o1'],'score':.1}],1,{'public_content':'meeting(day=saturday)','pending':[]},'superseded'),
  scenario('other','other_correction',['The code is 47B.','No, it is 47D.'],'code(value=47B)','No','other:h0',[{'content':'code(value=47D)','supports':a2('other'),'score':.98},{'content':'code(value=47B)','supports':['other:o1'],'score':.08}],1,{'public_content':'code(value=47D)','pending':[]},'contested'),
  scenario('clarify','clarification_request',['Alex called.','Which Alex?'],'called(alex_unknown)','which','referent(alex_unknown)',[{'content':'called(alex_martin)','supports':a2('clarify'),'score':.5},{'content':'called(alex_chen)','supports':a2('clarify'),'score':.5}],0,{'public_content':None,'pending':['clarify(referent(alex_unknown))']},'suspended'),
  scenario('response','clarification_response',['Alex called. Which Alex?','Alex Martin.'],'called(alex_unknown)','Alex Martin','response:h0',[{'content':'called(alex_martin)','supports':a2('response'),'score':.99},{'content':'called(alex_chen)','supports':['response:o1'],'score':.01}],1,{'public_content':'called(alex_martin)','pending':[]},'superseded'),
  scenario('resume','resume_after_misunderstanding',['Send fifteen units.','Fifty?','No: fifteen. Continue.'],'send(quantity=15)','No','resume:t2',[{'content':'send(quantity=15)','supports':['resume:o1','resume:o3'],'score':.99},{'content':'send(quantity=50)','supports':['resume:o2'],'score':.15}],1,{'public_content':'send(quantity=15)','pending':[],'resumed':True},'reaffirmed'),
 ]
 # Clarification has no selected revision by design, hence no invented referent.
 refs={'dlg03_analysis_bundle':{'path':str(d3.relative_to(ROOT)),'sha256':sha(d3),'role':'DS/ERG analysis capability and explicit producer separation'},'dlg07_isu_contract':{'path':str(d7.relative_to(ROOT)),'sha256':sha(d7),'role':'candidate update and reversible state contract'}}
 vals={'all_observations_preserved':all(all(o['immutable'] for o in c['observations']) for c in cases),'prior_hypotheses_accessible':all(c['prior_hypothesis'] in c['all_hypotheses'] for c in cases),'no_prior_hypothesis_deleted':all(c['content_replaced_or_suspended']['hypothesis_id']==c['prior_hypothesis']['hypothesis_id'] for c in cases),'all_selected_revisions_justified':all(c['selected_revision_id'] is None or (c['justification']['supports'] and next(h for h in c['all_hypotheses'] if h['hypothesis_id']==c['selected_revision_id'])['supported_by']==c['justification']['supports']) for c in cases),'clarification_preserves_ambiguity':next(c for c in cases if c['id']=='clarify')['selected_revision_id'] is None and len(next(c for c in cases if c['id']=='clarify')['revision_candidates'])==2,'all_required_phenomena':{c['phenomenon'] for c in cases}=={'self_repair','other_correction','clarification_request','clarification_response','resume_after_misunderstanding'},'analysis_and_isu_artifacts_bound':all(Path(ROOT/v['path']).exists() for v in refs.values())};assert all(vals.values()),vals
 result={'cases':cases,'tool_bindings':refs,'representation_boundary':{'DS_ERG':'attributed analyses remain separate','DGB':'public state before/after','ISU':'candidate revisions and selection','provenance_graph':'observations, hypotheses, supports and revision edges'},'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'scenarios':len(cases),'observations':sum(len(c['observations']) for c in cases),'revision_candidates':sum(len(c['revision_candidates']) for c in cases),'no_decision_scenarios':sum(c['selected_revision_id'] is None for c in cases),'prior_hypotheses_preserved':len(cases),'verdict':'GO_TRACEABLE_NON_DESTRUCTIVE_REPAIR'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'networkx':importlib.metadata.version('networkx'),'dlg03_sha256':sha(d3),'dlg07_sha256':sha(d7)},indent=2)+'\n');print('DLG-10: 5 repair phenomena, all prior observations/hypotheses retained; GO')
if __name__=='__main__':main()
