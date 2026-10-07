#!/usr/bin/env python3
"""DLG-07: inspectable, coherent and reversible ISU update candidates."""
from __future__ import annotations
import copy,hashlib,importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
import z3
P=Path(__file__).resolve().parent;OUT=P/'output';ROOT=P.parents[1]
def empty():return {'facts':{},'qud':{},'pending':{},'history':[]}
def delta(section,key,new,state):return {'section':section,'key':key,'old':copy.deepcopy(state[section].get(key)),'new':copy.deepcopy(new)}
def apply(state,ops,forward=True):
 out=copy.deepcopy(state)
 for op in (ops if forward else reversed(ops)):
  value=op['new'] if forward else op['old'];sec,key=op['section'],op['key']
  if value is None:out[sec].pop(key,None)
  else:out[sec][key]=copy.deepcopy(value)
 return out
def coherent(state,ops):
 candidate=apply(state,ops);solver=z3.Solver();colors={}
 for fact in candidate['facts'].values():
  if fact.get('predicate')=='color' and fact.get('status')=='accepted_for_exchange':
   entity,value=fact['arguments'];colors.setdefault(entity,[]).append(value)
 for entity,values in colors.items():
  symbols={v:i for i,v in enumerate(sorted(set(values)))};x=z3.Int(f'color_{entity}');solver.add(*[x==symbols[v] for v in values])
 status=solver.check();return {'status':str(status).upper(),'consistent':status==z3.sat,'checked_constraint':'one accepted color per entity'}
def candidate(cid,rule,pre,supports,bindings,effects,state,score):
 return {'candidate_id':cid,'rule':rule,'preconditions':pre,'supports':supports,'bindings':bindings,'proposed_effects':effects,'coherence':coherent(state,effects),'score':score}
def integrated_dgb_candidates():
 path=ROOT/'poc/dlg-06/output/results.json';raw=path.read_bytes();upstream=json.loads(raw);sha=hashlib.sha256(raw).hexdigest()
 formal=upstream['integrated_gameboards']['formal_content_gameboard'];pending=formal['pending'][0];state=empty()
 state['history']=[{'source_gameboard_sha256':sha,'move_id':formal['moves'][0]['id'],'pending_id':pending['id']}]
 candidates=[]
 for index,alternative in enumerate(pending['alternatives'],1):
  proposed={'kind':'attributed_formal_content','status':'candidate','source_move_id':formal['moves'][0]['id'],'analysis_ref':alternative['analysis_ref'],'producer':alternative['producer'],'shared_source_observation_ref':formal['moves'][0]['content_record']['shared_source_observation_ref']}
  candidates.append(candidate(f'integrated-c{index}','register-attributed-formal-content',['public move exists','analysis remains attributed'],[formal['moves'][0]['source'],alternative['analysis_ref']],{'producer':alternative['producer']},[delta('pending',f"formal-{alternative['producer']}",proposed,state)],state,.5))
 before=copy.deepcopy(state);after=apply(before,[])
 validations={
  'upstream_dlg06_valid':all(upstream['validations'].values()),
  'one_candidate_per_formal_alternative':len(candidates)==len(pending['alternatives'])==2,
  'actual_analysis_refs_are_supports':{c['supports'][1] for c in candidates}=={a['analysis_ref'] for a in pending['alternatives']},
  'shared_observation_propagated':all(c['proposed_effects'][0]['new']['shared_source_observation_ref']==formal['moves'][0]['content_record']['shared_source_observation_ref'] for c in candidates),
  'unresolved_correspondence_forces_no_selection':pending['unresolved']==['semantic_correspondence'] and before==after,
  'candidates_are_individually_coherent':all(c['coherence']['consistent'] for c in candidates),
 }
 return {'source':{'poc':'DLG-06','results_sha256':sha},'state_before':before,'source_pending_content':pending,'candidates':candidates,'selection':{'candidate_id':None,'reason':'semantic correspondence unresolved; keep attributed alternatives'},'state_after':after},validations
def main():
 OUT.mkdir(parents=True,exist_ok=True);state=empty();steps=[]
 def execute(turn,candidates,selected_id,reason):
  nonlocal state
  before=copy.deepcopy(state);selected=next((c for c in candidates if c['candidate_id']==selected_id),None);ops=selected['proposed_effects'] if selected else [];after=apply(before,ops);reverted=apply(after,ops,False)
  steps.append({'turn':turn,'state_before':before,'candidates':candidates,'selection':{'candidate_id':selected_id,'reason':reason},'state_after':after,'reversible_delta':ops,'reverted_state':reverted,'reversal_exact':reverted==before});state=after
 # Ambiguous assertion: two live interpretations, no opaque commitment.
 c1=candidate('c1','assert-content',['speaker identified'],['turn:t1'],{'sense':'financial_bank'},[delta('facts','f-bank-fin',{'predicate':'at','arguments':['speaker','financial_bank'],'status':'proposed','source':'t1'},state)],state,.51)
 c2=candidate('c2','assert-content',['speaker identified'],['turn:t1'],{'sense':'river_bank'},[delta('facts','f-bank-river',{'predicate':'at','arguments':['speaker','river_bank'],'status':'proposed','source':'t1'},state)],state,.49)
 execute({'id':'t1','act':'assertion','raw':'I am at the bank.'},[c1,c2],None,'interpretations too close; retain alternatives')
 # Question opens a QUD.
 q={'question':'color(car-1, ?c)','status':'active','source':'t2'};cq=candidate('c3','raise-qud',['addressee available'],['turn:t2'],{'x':'car-1'},[delta('qud','q-color',q,state)],state,.95);execute({'id':'t2','act':'question','raw':'Quelle couleur est la voiture ?'},[cq],'c3','single coherent update')
 # Answer offers competing values; lexical/context support selects red.
 red={'predicate':'color','arguments':['car-1','red'],'status':'proposed','source':'t3'};crimson={'predicate':'color','arguments':['car-1','crimson'],'status':'proposed','source':'t3'}
 ca=candidate('c4','answer-qud',['q-color active'],['turn:t3','qud:q-color'],{'c':'red'},[delta('facts','f-color',red,state),delta('qud','q-color',{**q,'status':'answered'},state)],state,.83);cb=candidate('c5','answer-qud',['q-color active'],['turn:t3','qud:q-color'],{'c':'crimson'},[delta('facts','f-color',crimson,state),delta('qud','q-color',{**q,'status':'answered'},state)],state,.42);execute({'id':'t3','act':'answer','raw':'Rouge.'},[ca,cb],'c4','best supported coherent binding')
 # Acceptance promotes public status.
 accepted={**state['facts']['f-color'],'status':'accepted_for_exchange','accepted_by':'alice'};cc=candidate('c6','accept-proposal',['fact proposed'],['turn:t4','fact:f-color'],{'fact':'f-color'},[delta('facts','f-color',accepted,state)],state,.99);execute({'id':'t4','act':'acceptance','raw':"D'accord."},[cc],'c6','explicit acceptance')
 # Rejection remains traceable and does not delete the fact.
 contested={**state['facts']['f-color'],'status':'contested','contested_by':'bob'};cr=candidate('c7','reject-content',['fact accessible'],['turn:t5','fact:f-color'],{'fact':'f-color'},[delta('facts','f-color',contested,state)],state,.98);execute({'id':'t5','act':'rejection','raw':'Non, pas rouge.'},[cr],'c7','explicit rejection')
 # Non-understanding creates repair pending, with no guessed interpretation.
 pending={'kind':'clarification_request','target':'t5','status':'open','source':'t6'};cn=candidate('c8','register-non-understanding',['target move accessible'],['turn:t6','turn:t5'],{'target':'t5'},[delta('pending','clarify-t5',pending,state)],state,.97);execute({'id':'t6','act':'non_understanding','raw':'Pardon ?'},[cn],'c8','record failure without inventing content')
 integrated,integrated_vals=integrated_dgb_candidates();vals={'all_candidates_inspectable':all(all(k in c for k in ('rule','preconditions','supports','bindings','proposed_effects','coherence') ) for s in steps for c in s['candidates']),'all_selected_candidates_coherent':all(not s['selection']['candidate_id'] or next(c for c in s['candidates'] if c['candidate_id']==s['selection']['candidate_id'])['coherence']['consistent'] for s in steps),'all_deltas_reverse_exactly':all(s['reversal_exact'] for s in steps),'ambiguous_assertion_has_no_decision':steps[0]['selection']['candidate_id'] is None and steps[0]['state_before']==steps[0]['state_after'],'all_requested_act_types_covered':{s['turn']['act'] for s in steps}=={'assertion','question','answer','acceptance','rejection','non_understanding'},'rejection_preserves_prior_content':state['facts']['f-color']['status']=='contested','nonunderstanding_does_not_guess_content':state['pending']['clarify-t5']['kind']=='clarification_request',**integrated_vals};assert all(vals.values()),vals
 result={'engine':'internal candidate-based Information State Update','steps':steps,'final_state':state,'integrated_dgb_candidates':integrated,'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'turns':len(steps),'candidates':sum(len(s['candidates']) for s in steps),'no_decision_steps':sum(s['selection']['candidate_id'] is None for s in steps),'reversible_deltas':sum(s['reversal_exact'] for s in steps),'integrated_candidates':len(integrated['candidates']),'integrated_selection':integrated['selection']['candidate_id'],'verdict':'GO_INSPECTABLE_REVERSIBLE_ISU'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'z3_solver':importlib.metadata.version('z3-solver'),'historical_references_not_runtime_dependencies':['TRINDIKIT','trindikit.py','GoDiS']},indent=2)+'\n');print('DLG-07: 6 acts, 8 candidates, all selected deltas reversible; GO')
if __name__=='__main__':main()
