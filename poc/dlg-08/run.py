#!/usr/bin/env python3
"""DLG-08: evidence-backed grounding degrees with append-only history."""
from __future__ import annotations
import importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
import networkx as nx
P=Path(__file__).resolve().parent;OUT=P/'output'
ORDER=['produced','perceived','understood','accepted_for_exchange'];PRE={'perceived':'produced','understood':'perceived','accepted_for_exchange':'understood'}
def envelope(i,turn,span,raw):return {'id':i,'input_observation_id':turn,'producer':'seman2 grounding adapter','producer_version':'dlg-08/1','parameters_json':'{}','model':'internal evidence ladder','formalism':'grounding-act/unit','annotation_type':'grounding','raw_value_json':json.dumps(raw,sort_keys=True),'spans':[{'coordinate_system':'turn_utf8_codepoints','start':span[0],'end':span[1],'unit':'codepoint'}],'alternatives_json':[],'constraints_json':[],'score':raw['confidence'],'input_modality':'text','derived_from_text':True,'is_audio_observation':False,'source_artifact':'poc/dlg-08 controlled fixtures','source_selector':turn}
def main():
 OUT.mkdir(parents=True,exist_ok=True);events=[];units={};rejections=[]
 def event(eid,uid,act,actor,for_participants,content,turn,span,confidence,evidence,target=None):
  before=units.get(uid,{}).get('status','unseen');allowed=True;reason='explicit non-monotonic act'
  if act in PRE:
   allowed=before==PRE[act];reason=f"requires prior status {PRE[act]}"
  if act=='produced':allowed=before=='unseen';reason='requires unseen content'
  if act in ('contested','corrected'):allowed=before!='unseen';reason='requires accessible prior content'
  after=act if allowed else before
  row={'event_id':eid,'grounding_unit_id':uid,'act':act,'actor':actor,'participants_concerned':for_participants,'content':content,'turn_id':turn,'span':span,'confidence':confidence,'uncertainty':1-confidence,'evidence':evidence,'target_event_id':target,'status_before':before,'status_after':after,'accepted':allowed,'precondition':reason,'annotation':envelope(f'ann-{eid}',turn,span,{'act':act,'unit':uid,'confidence':confidence})};events.append(row)
  if allowed:units[uid]={'grounding_unit_id':uid,'content':content,'participants':for_participants,'status':after,'current_event_id':eid,'history':[*(units.get(uid,{}).get('history',[])),eid]}
  else:rejections.append({'event_id':eid,'reason':reason,'status_preserved':before})
  return row
 # Acknowledgement reaches exchange acceptance only through all explicit levels.
 event('e1','u-weather','produced','alice',['alice','bob'],'rain(tomorrow)','t1',[0,18],.99,['raw turn t1'])
 event('e2','u-weather','perceived','bob',['alice','bob'],'rain(tomorrow)','t2',[0,2],.95,['acknowledgement oui'],'e1')
 event('e3','u-weather','understood','bob',['alice','bob'],'rain(tomorrow)','t2',[0,2],.88,['relevant acknowledgement'],'e2')
 event('e4','u-weather','accepted_for_exchange','bob',['alice','bob'],'rain(tomorrow)','t2',[0,2],.82,['explicit oui'],'e3')
 # Incomprehension blocks understanding.
 event('e5','u-code','produced','alice',['alice','bob'],'code(47B)','t3',[0,10],.98,['raw turn t3'])
 event('e6','u-code','perceived','bob',['alice','bob'],'code(47B)','t4',[0,8],.9,['response exists'],'e5')
 event('e7','u-code','contested','bob',['alice','bob'],'code(47B)','t4',[0,8],.99,["Je n'ai pas compris"],'e6')
 # Confirmation then correction histories.
 for args in [('e8','produced','alice','meeting(monday)','t5'),('e9','perceived','bob','meeting(monday)','t6'),('e10','understood','bob','meeting(monday)','t6')]:event(args[0],'u-meeting',args[1],args[2],['alice','bob'],args[3],args[4],[0,6],.94,[f'explicit {args[1]}'])
 event('e11','u-meeting','accepted_for_exchange','bob',['alice','bob'],'meeting(monday)','t6',[0,6],.92,['confirmation lundi'],'e10')
 event('e12','u-meeting','corrected','alice',['alice','bob'],'meeting(tuesday)','t7',[0,18],.99,['non, mardi'],'e11')
 # Explicitly attempt and reject a forbidden jump.
 event('e13','u-direct','produced','alice',['alice','bob'],'door(open)','t8',[0,12],.99,['raw mention'])
 event('e14','u-direct','accepted_for_exchange','bob',['alice','bob'],'door(open)','t8',[0,12],.4,['no acceptance evidence'],'e13')
 g=nx.DiGraph();
 for e in events:g.add_node(e['event_id'],act=e['act'],accepted=e['accepted'])
 for e in events:
  if e['target_event_id']:g.add_edge(e['target_event_id'],e['event_id'],relation='grounding_evidence')
 vals={'all_annotations_graph02_shape':all(all(k in e['annotation'] for k in ('producer','producer_version','raw_value_json','spans','source_artifact','source_selector')) for e in events),'history_append_only':all(u['history']==[e['event_id'] for e in events if e['grounding_unit_id']==uid and e['accepted']] for uid,u in units.items()),'direct_mention_to_acceptance_rejected':any(r['event_id']=='e14' for r in rejections) and units['u-direct']['status']=='produced','incomprehension_not_promoted':units['u-code']['status']=='contested','correction_preserves_history':units['u-meeting']['history']==['e8','e9','e10','e11','e12'],'participants_spans_uncertainty_evidence_present':all(e['participants_concerned'] and e['span'][1]>e['span'][0] and 0<=e['uncertainty']<=1 and e['evidence'] for e in events)};assert all(vals.values()),vals
 result={'grounding_acts':events,'grounding_units':list(units.values()),'rejected_promotions':rejections,'evidence_graph':nx.node_link_data(g,edges='edges'),'level_contract':{'monotonic_ladder':ORDER,'non_monotonic_statuses':['contested','corrected'],'rule':'a higher level requires explicit evidence and its immediate predecessor'},'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'acts':len(events),'units':len(units),'rejected_promotions':len(rejections),'corrected_units':sum(u['status']=='corrected' for u in units.values()),'contested_units':sum(u['status']=='contested' for u in units.values()),'verdict':'GO_EVIDENCE_BACKED_GROUNDING'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'networkx':importlib.metadata.version('networkx'),'corpus_status':'controlled fixtures; no reproducible licensed grounding corpus claimed','annotation_contract':'GRAPH-02 field-compatible envelope'},indent=2)+'\n');print('DLG-08: grounding history and forbidden direct promotion validated; GO')
if __name__=='__main__':main()
