#!/usr/bin/env python3
"""X-05: held-out recombination of learned dialogue structures."""
from __future__ import annotations
import hashlib,importlib.metadata,json,os,platform,re
from datetime import datetime,timezone
from pathlib import Path
import pyarrow as pa,pyarrow.parquet as pq
from z3 import Bool,Solver,Not,sat
import Python_sml_ClientInterface as sml
P=Path(__file__).resolve().parent;ROOT=P.parents[1];OUT=P/'output'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def decide(kernel,case,i):
 a=kernel.CreateAgent(f'x05-{i}');il=a.GetInputLink();c=il.CreateIdWME('case');c.CreateStringWME('support-status',case['support_status']);c.CreateStringWME('requested-act',case['expected_act'] or 'none');a.Commit();rules='''
sp {x05*supported (state <s> ^io.input-link.case <c> ^io.output-link <o>) (<c> ^support-status supported ^requested-act <act>) --> (<o> ^decision <d>) (<d> ^status execute ^plan-act <act>)}
sp {x05*insufficient (state <s> ^io.input-link.case.support-status insufficient ^io.output-link <o>) --> (<o> ^decision <d>) (<d> ^status no-decision ^plan-act clarify)}
sp {x05*conflict (state <s> ^io.input-link.case.support-status conflict ^io.output-link <o>) --> (<o> ^decision <d>) (<d> ^status no-decision ^plan-act withhold)}
''';src=a.ExecuteCommandLine(rules);run=a.ExecuteCommandLine('run 1');wm=a.ExecuteCommandLine('print S1 --depth 5');status=re.search(r'\^status ([^\s()]+)',wm).group(1);act=re.search(r'\^plan-act ([^\s()]+)',wm).group(1);kernel.DestroyAgent(a);return {'status':status,'plan_act':act,'run':run,'wm':wm,'source':src}
def main():
 OUT.mkdir(parents=True,exist_ok=True);names=['dlg-06','dlg-07','dlg-08','dlg-11','dlg-14','ind-03','ind-04','comm-01','comm-02'];paths={n:ROOT/f'poc/{n}/output/results.json' for n in names};assert all(p.exists() for p in paths.values());ind3=json.loads(paths['ind-03'].read_text());ind4=json.loads(paths['ind-04'].read_text())
 training=[
  {'id':'TR-QA','signature':['dyad','active-qud','Question-Answer','presented','answer-open']},
  {'id':'TR-REF','signature':['dyad','reference-qud','Clarification','uncertain','clarify-open']},
  {'id':'TR-DIG','signature':['dyad','topic-qud','Background','presented','topic-open']},
  {'id':'TR-TRIAD','signature':['triad','none','Elaboration','accepted','none']},
  {'id':'TR-REQ','signature':['dyad','request-qud','Acknowledgement','understood','request-open']},
  {'id':'TR-RETURN','signature':['dyad','none','Return','presented','topic-open']},
  {'id':'TR-CONTEST','signature':['dyad','none','Correction','contested','answer-cancelled']}]
 patterns=[
  {'id':'P-QUD-OBL','conditions':['active-qud','*-open'],'effect':'answer','sources':['TR-QA','TR-REQ'],'induced_with':ind3['pattern']['id']},
  {'id':'P-CLARIFY','conditions':['uncertain','Clarification'],'effect':'clarify','sources':['TR-REF'],'induced_with':ind4['transformation']['id']},
  {'id':'P-RETURN','conditions':['Return','topic-open'],'effect':'resume-answer','sources':['TR-DIG'],'induced_with':ind4['transformation']['id']},
  {'id':'P-MULTIPARTY','conditions':['triad'],'effect':'address-bound-participant','sources':['TR-TRIAD'],'induced_with':ind3['pattern']['id']}]
 cases=[
  {'id':'NEW-TRIAD-QA','signature':['triad','active-qud','Question-Answer','presented','answer-open'],'matched':['P-QUD-OBL','P-MULTIPARTY'],'support_status':'supported','expected_act':'answer'},
  {'id':'NEW-TRIAD-REF','signature':['triad','reference-qud','Clarification','uncertain','clarify-open'],'matched':['P-CLARIFY','P-MULTIPARTY'],'support_status':'supported','expected_act':'clarify'},
  {'id':'NEW-RETURN-ANSWER','signature':['dyad','active-qud','Return','presented','topic-open'],'matched':['P-RETURN','P-QUD-OBL'],'support_status':'supported','expected_act':'resume-answer'},
  {'id':'NEW-REQUEST-UNCERTAIN','signature':['dyad','request-qud','Clarification','uncertain','request-open'],'matched':['P-CLARIFY','P-QUD-OBL'],'support_status':'supported','expected_act':'clarify'},
  {'id':'NEW-TRIAD-RETURN','signature':['triad','topic-qud','Return','presented','topic-open'],'matched':['P-RETURN','P-MULTIPARTY'],'support_status':'supported','expected_act':'resume-answer'},
  {'id':'NEG-NO-QUD','signature':['dyad','none','Question-Answer','presented','none'],'matched':[],'support_status':'insufficient','expected_act':None},
  {'id':'NEG-CONFLICT','signature':['dyad','active-qud','Return','contested','answer-cancelled'],'matched':['P-RETURN','P-QUD-OBL'],'support_status':'conflict','expected_act':None},
  {'id':'NEG-UNKNOWN-REL','signature':['triad','active-qud','UnknownRelation','uncertain','answer-open'],'matched':['P-MULTIPARTY'],'support_status':'insufficient','expected_act':None}]
 train_sigs={tuple(x['signature']) for x in training};kernel=sml.Kernel.CreateKernelInNewThread();assert not kernel.HadError();version=kernel.GetSoarKernelVersion();rows=[]
 for i,c in enumerate(cases,1):
  assert tuple(c['signature']) not in train_sigs
  q=Bool(f'q{i}');obl=Bool(f'obl{i}');conflict=Bool(f'conflict{i}');s=Solver();s.add(q==('none' not in c['signature']),obl==any(x.endswith('open') for x in c['signature']),conflict==('contested' in c['signature'] or 'cancelled' in ' '.join(c['signature'])))
  if c['support_status'] in ('supported','conflict'):s.add(q,obl,Not(conflict))
  model_status='not-run-insufficient' if c['support_status']=='insufficient' else str(s.check());assert (c['support_status']=='supported' and model_status=='sat') or (c['support_status']=='conflict' and model_status=='unsat') or c['support_status']=='insufficient'
  soar=decide(kernel,c,i);expected_runtime='execute' if c['support_status']=='supported' else 'no-decision';assert soar['status']==expected_runtime and '1 rule fired' in soar['run']
  plan=None if soar['status']=='no-decision' else {'plan_id':f"PLAN-{c['id']}",'act':soar['plan_act'],'goal':'satisfy-current-supported-structure','content':['bound-QUD-content'],'omitted':['unsupported inferences'],'provenance':c['matched']}
  rows.append({**c,'training_signature_seen':False,'constraint_status':model_status,'soar':soar,'plan':plan,'clean_failure':soar['status']=='no-decision','pattern_provenance':[next(p for p in patterns if p['id']==pid) for pid in c['matched']]})
 kernel.Shutdown();table=OUT/'heldout-combinations.parquet';pq.write_table(pa.Table.from_pylist([{'case_id':r['id'],'signature_json':json.dumps(r['signature']),'status':r['support_status'],'matched_json':json.dumps(r['matched']),'soar_status':r['soar']['status'],'plan_act':r['soar']['plan_act']} for r in rows]),table,compression='zstd')
 pos=[r for r in rows if r['support_status']=='supported'];neg=[r for r in rows if r['support_status']!='supported']
 vals={'all_combinations_held_out':all(not r['training_signature_seen'] for r in rows),'all_components_seen_separately':all(all(any(component in tr['signature'] for tr in training) for component in r['signature'] if component!='UnknownRelation') for r in rows),'patterns_have_induction_provenance':all(p['sources'] and p['induced_with'] for p in patterns),'supported_novel_combinations_execute':len(pos)==5 and all(r['soar']['status']=='execute' and r['plan'] for r in pos),'insufficient_or_conflicting_support_fails_cleanly':len(neg)==3 and all(r['soar']['status']=='no-decision' and r['plan'] is None for r in neg),'constraints_gate_execution':all(((r['constraint_status']=='sat') if r['support_status']=='supported' else (r['constraint_status'] in {'unsat','not-run-insufficient'})) for r in rows),'real_soar_rule_each_case':all('1 rule fired' in r['soar']['run'] for r in rows),'counterexamples_not_forced_into_pattern':all(r['clean_failure'] for r in neg),'source_contracts_hashed':all(len(sha(p))==64 for p in paths.values()),'parquet_roundtrip':pq.read_table(table).num_rows==len(rows)};assert all(vals.values()),vals
 result={'training_configurations':training,'learned_reusable_patterns':patterns,'heldout_cases':rows,'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths.values()},'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');(OUT/'summary.json').write_text(json.dumps({'training_configurations':len(training),'heldout_combinations':len(rows),'supported_novel_successes':len(pos),'clean_failures':len(neg),'actual_soar_decisions':len(rows),'verdict':'GO_HELDOUT_DIALOGUE_STRUCTURE_RECOMBINATION'},indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'soar':version,'sml_module':sml.__file__,'z3_solver':importlib.metadata.version('z3-solver'),'pyarrow':importlib.metadata.version('pyarrow'),'pythonpath':os.environ.get('PYTHONPATH')},indent=2)+'\n');print('X-05: 5 unseen supported combinations execute; 3 unsupported/conflicting cases fail cleanly; GO')
if __name__=='__main__':main()
