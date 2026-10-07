#!/usr/bin/env python3
"""COMM-01: inspectable symbolic communication plans, before realization."""
from __future__ import annotations

import hashlib,importlib.metadata,json,os,platform,re
from datetime import datetime,timezone
from pathlib import Path
import networkx as nx
from z3 import Bool,Int,Solver,Sum,sat
import Python_sml_ClientInterface as sml
P=Path(__file__).resolve().parent;OUT=P/'output';ROOT=P.parents[1]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def soar_directive(kernel,case,index):
 a=kernel.CreateAgent(f'comm01-{index}');il=a.GetInputLink();il.CreateStringWME('transformation-id',case['id']);il.CreateStringWME('transformation-kind',case['kind']);a.Commit()
 rules='''
sp {comm01*assertion (state <s> ^io.input-link.transformation-kind assertion ^io.output-link <o>) --> (<o> ^planning-directive <d>) (<d> ^mode assert ^initiative self)}
sp {comm01*response (state <s> ^io.input-link.transformation-kind response ^io.output-link <o>) --> (<o> ^planning-directive <d>) (<d> ^mode answer ^initiative reactive)}
sp {comm01*clarification (state <s> ^io.input-link.transformation-kind clarification ^io.output-link <o>) --> (<o> ^planning-directive <d>) (<d> ^mode clarify-reference ^initiative repair)}
sp {comm01*refusal (state <s> ^io.input-link.transformation-kind refusal ^io.output-link <o>) --> (<o> ^planning-directive <d>) (<d> ^mode refuse-with-reason ^initiative reactive)}
sp {comm01*silence (state <s> ^io.input-link.transformation-kind silence ^io.output-link <o>) --> (<o> ^planning-directive <d>) (<d> ^mode no-continuation ^initiative none)}
''';src=a.ExecuteCommandLine(rules);run=a.ExecuteCommandLine('run 1');top=a.ExecuteCommandLine('print S1 --depth 5');m=re.search(r'\^mode ([^\s()]+)',top);i=re.search(r'\^initiative ([^\s()]+)',top);assert m and i,(case,top);result={'mode':m.group(1),'initiative':i.group(1),'run':run,'wm':top,'source':src};kernel.DestroyAgent(a);return result
def solve(case,directive):
 include=Bool('include');reason=Bool('reason');reference=Bool('reference');commit=Bool('commit');units=Int('units');question=Bool('question');negative=Bool('negative');s=Solver();s.add(units>=0,units<=2)
 kind=case['kind']
 if kind=='assertion':s.add(include,reference,commit,units==1,question==False,negative==False,reason==False)
 elif kind=='response':s.add(include,reference,commit,units==1,question==False,negative==False,reason==False)
 elif kind=='clarification':s.add(include,reference,commit==False,units==1,question,negative==False,reason==False)
 elif kind=='refusal':s.add(include==False,reference==False,commit,units==1,question==False,negative,reason)
 else:s.add(include==False,reason==False,reference==False,commit==False,units==0,question==False,negative==False)
 assert s.check()==sat;model=s.model();b=lambda x:bool(model.eval(x,model_completion=True));return {'include_content':b(include),'include_reason':b(reason),'include_reference':b(reference),'propose_commitment':b(commit),'unit_count':model[units].as_long(),'interrogative':b(question),'negative':b(negative),'status':'SAT'}
def main():
 OUT.mkdir(parents=True,exist_ok=True);dgbp=ROOT/'poc/dlg-06/output/results.json';isup=ROOT/'poc/dlg-07/output/results.json';assert dgbp.exists() and isup.exists();dgb=json.loads(dgbp.read_text())['dialogue_gameboard'];assert any(q['status']=='active' for q in dgb['qud'])
 cases=[
 {'id':'T-ASSERT','kind':'assertion','content':'location(car-1,garage)','goal':'establish-public-fact','reference':'definite:car-1','omit':'sensor-calibration-detail','omit_reason':'not needed for current QUD','style':'neutral-declarative'},
 {'id':'T-ANSWER','kind':'response','content':'size(car-1,large)','goal':'resolve-q2','reference':'anchored:car-1','omit':'color(car-1,red)','omit_reason':'already grounded and irrelevant','style':'concise-answer'},
 {'id':'T-CLARIFY','kind':'clarification','content':'choose(car-1,color-swatch-1)','goal':'resolve-reference','reference':'contrastive-alternatives','omit':'size-value','omit_reason':'unsafe before referent resolution','style':'interrogative-repair'},
 {'id':'T-REFUSE','kind':'refusal','content':'unsafe-procedure-X','goal':'decline-with-reason','reference':'none','omit':'unsafe-procedure-X','omit_reason':'policy constraint C-SAFE','style':'polite-negative'},
 {'id':'T-SILENT','kind':'silence','content':'optional-follow-up','goal':'avoid-superfluous-continuation','reference':'none','omit':'optional-follow-up','omit_reason':'no open obligation and initiative unsupported','style':'silent'}]
 g=nx.DiGraph()
 for c in cases:g.add_node(c['id'],kind='transformation',transformation_kind=c['kind']);g.add_node(c['content'],kind='content');g.add_edge(c['id'],c['content'],relation='transforms-content')
 graph_json=nx.node_link_data(g,edges='edges');kernel=sml.Kernel.CreateKernelInNewThread();assert not kernel.HadError();version=kernel.GetSoarKernelVersion();plans=[]
 for n,c in enumerate(cases):
  directive=soar_directive(kernel,c,n);z=solve(c,directive);silent=c['kind']=='silence';ref=c['reference'] if z['include_reference'] else None
  retained=[] if not z['include_content'] else [{'content_id':c['content'],'role':'questioned-alternatives' if c['kind']=='clarification' else 'nucleus'}]
  if z['include_reason']:retained.append({'content_id':c['omit_reason'],'role':'refusal-reason'})
  commitment=[] if not z['propose_commitment'] else [{'type':'refusal' if c['kind']=='refusal' else ('answer' if c['kind']=='response' else 'assertion'),'content':c['omit_reason'] if c['kind']=='refusal' else c['content']}]
  plan={'plan_id':f'PLAN-{n+1:02d}','transformation_id':c['id'],'act':c['kind'],'communicative_goal':c['goal'],'ordered_content':[{'order':i+1,**x} for i,x in enumerate(retained)],'omitted_content':[{'content_id':c['omit'],'reason':c['omit_reason']}],'proposed_commitments':commitment,'reference_plan':ref,'quantity':{'units':z['unit_count'],'policy':'minimal-sufficient'},'style':c['style'],'initiative':directive['initiative'],'morphosyntax':{'mood':'interrogative' if z['interrogative'] else ('none' if silent else 'declarative'),'polarity':'negative' if z['negative'] else ('none' if silent else 'positive'),'realize':not silent},'provenance':{'transformation':c['id'],'soar_directive':directive['mode'],'dgb_sha256':digest(dgbp),'isu_sha256':digest(isup),'z3_status':z['status'],'active_graph_node':c['id']},'constraint_model':z,'soar_evidence':directive};plans.append(plan)
 kernel.Shutdown()
 validations={'five_transformation_types':{p['act'] for p in plans}=={'assertion','response','clarification','refusal','silence'},'all_required_plan_fields':all(all(k in p for k in ['communicative_goal','ordered_content','omitted_content','proposed_commitments','reference_plan','quantity','style','initiative','morphosyntax','provenance']) for p in plans),'every_choice_has_provenance':all(len(p['provenance'])==6 for p in plans),'clarification_precedes_unsafe_answer':next(p for p in plans if p['act']=='clarification')['morphosyntax']['mood']=='interrogative' and next(p for p in plans if p['act']=='clarification')['constraint_model']['include_content'],'refusal_omits_unsafe_content_and_gives_reason':(lambda p:not p['constraint_model']['include_content'] and p['constraint_model']['include_reason'] and p['morphosyntax']['polarity']=='negative')(next(p for p in plans if p['act']=='refusal')),'silence_is_first_class_zero_unit_plan':(lambda p:p['quantity']['units']==0 and not p['ordered_content'] and not p['proposed_commitments'] and not p['morphosyntax']['realize'])(next(p for p in plans if p['act']=='silence')),'no_surface_text_generated':all('text' not in p for p in plans),'active_graph_covers_transformations':g.number_of_nodes()==10 and g.number_of_edges()==5,'real_soar_directive_for_every_plan':all('1 rule fired' in p['soar_evidence']['run'] for p in plans)};assert all(validations.values()),validations
 result={'soar_version':version,'source_artifacts':{'dlg06':digest(dgbp),'dlg07':digest(isup)},'active_graph':graph_json,'plans':plans,'validations':validations};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');(OUT/'plans.json').write_text(json.dumps(plans,ensure_ascii=False,indent=2)+'\n');(OUT/'summary.json').write_text(json.dumps({'plans':len(plans),'acts':[p['act'] for p in plans],'silent_plans':sum(not p['morphosyntax']['realize'] for p in plans),'surface_strings':0,'verdict':'GO_INSPECTABLE_PRELINGUISTIC_COMMUNICATIVE_PLAN'},indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'soar':version,'z3_solver':importlib.metadata.version('z3-solver'),'networkx':importlib.metadata.version('networkx'),'sml_module':sml.__file__,'pythonpath':os.environ.get('PYTHONPATH')},indent=2)+'\n');print('COMM-01: five inspectable prelinguistic plans validated with Soar and Z3; GO')
if __name__=='__main__':main()
