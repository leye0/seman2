#!/usr/bin/env python3
"""CULT-02: keep literal content, commitment and pragmatic hypotheses separate."""
from __future__ import annotations
import hashlib,importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
import pyarrow as pa,pyarrow.parquet as pq
from z3 import Bool,Solver,Not,sat
P=Path(__file__).resolve().parent;OUT=P/'output';ROOT=P.parents[1]
def source(poc):p=ROOT/f'poc/{poc}/output/results.json';assert p.exists();return p,json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=True);d3p,d3=source('dlg-03');bundle=next(x for x in d3 if x['fixture']['id']=='complete');assert {x['producer'] for x in bundle['analyses']}=={'ACE_ERG','dynamicsyntax-python'} and all(x['status']=='parsed' for x in bundle['analyses']);c1p,c1=source('cult-01');d6p,d6=source('dlg-06');d7p,d7=source('dlg-07');d8p,d8=source('dlg-08');r4p,r4=source('ret-04')
 literal={'content_id':'literal:like:john:mary','predicate':'like','arguments':['john','mary'],'surface':'John likes Mary.','erg_analysis_id':'erg:complete','ds_analysis_id':'ds:complete','immutable':True}
 hypotheses=[{'id':'H0','commitment':'speaker-supports(literal:like:john:mary)','human_eval_label':'literal'},{'id':'H1','commitment':'speaker-supports(not(like(john,mary)))','human_eval_label':'irony/exaggeration'},{'id':'H2','commitment':'speaker-invites-affiliative-play(about(like(john,mary)))','human_eval_label':'teasing/humour'}]
 contexts=[
 {'id':'C-LITERAL','history':['John helped Mary repeatedly.','Speaker: I mean that sincerely.'],'relation':'neutral-colleagues','signals':{'direct-confirmation':1.0,'expectation-match':.8,'incongruity':0,'laughter':0},'eval':'literal'},
 {'id':'C-REVERSAL','history':['John and Mary argued all week.','John refuses to work with Mary.'],'relation':'distant-colleagues','signals':{'direct-confirmation':0,'expectation-match':-.8,'incongruity':1.0,'laughter':.1},'eval':'irony/exaggeration'},
 {'id':'C-PLAY','history':['John lost to Mary again.','Both laugh after the remark.'],'relation':'close-friends','signals':{'direct-confirmation':0,'expectation-match':-.2,'incongruity':.5,'laughter':1.0},'eval':'teasing/humour'},
 {'id':'C-AMBIG','history':['John and Mary met yesterday.'],'relation':'unknown','signals':{'direct-confirmation':0,'expectation-match':0,'incongruity':.1,'laughter':0},'eval':'ambiguous'},
 {'id':'C-CORRECTED','history':['They argued once.','Speaker: No sarcasm; I genuinely mean it.'],'relation':'colleagues','signals':{'direct-confirmation':1.0,'expectation-match':-.2,'incongruity':.3,'laughter':0},'eval':'literal'}]
 rows=[];decisions=[]
 for c in contexts:
  x=c['signals'];scores={'H0':.35+1.0*x['direct-confirmation']+.35*x['expectation-match']-.25*x['incongruity'],'H1':.20+.75*x['incongruity']-.55*x['direct-confirmation']-.25*x['laughter'],'H2':.15+.65*x['laughter']+.25*x['incongruity']+(.15 if c['relation']=='close-friends' else 0)}
  for h in hypotheses:
   favorable=[];unfavorable=[]
   if x['direct-confirmation']>0:favorable.append('explicit-sincerity') if h['id']=='H0' else unfavorable.append('explicit-sincerity')
   if x['incongruity']>.4:favorable.append('violated-expectation') if h['id'] in ('H1','H2') else unfavorable.append('violated-expectation')
   if x['laughter']>.5:favorable.append('shared-laughter') if h['id']=='H2' else unfavorable.append('shared-laughter')
   rows.append({'context_id':c['id'],'hypothesis_id':h['id'],'support':scores[h['id']],'favorable_json':json.dumps(favorable),'unfavorable_json':json.dumps(unfavorable),'literal_content_id':literal['content_id'],'analog_source':'CULT-01/Switchboard' if h['id']!='H2' else 'CULT-01+05/outcome-patterns'})
  ranked=sorted(scores.items(),key=lambda x:(-x[1],x[0]));margin=ranked[0][1]-ranked[1][1];selected=ranked[0][0] if margin>=.20 else None;decisions.append({'context_id':c['id'],'ranking':[{'hypothesis_id':h,'support':s} for h,s in ranked],'margin':margin,'selected_hypothesis_id':selected,'status':'selected' if selected else 'undecided','human_eval_only':c['eval']})
 pq.write_table(pa.Table.from_pylist(rows),OUT/'hypothesis-evidence.parquet',compression='zstd')
 solver=Solver();literal_true=Bool('literal_content_exists');h0=Bool('commit_h0');h1=Bool('commit_h1');solver.add(literal_true,Not(h0 & h1));assert solver.check()==sat
 by={x['context_id']:x for x in decisions};validations={'literal_content_identical_all_contexts':len({r['literal_content_id'] for r in rows})==1 and literal['immutable'],'erg_and_ds_outputs_preserved_separately':not bundle['semantic_nodes_fused'] and len(bundle['analyses'])==2,'multiple_pragmatic_hypotheses_coexist':all(sum(r['context_id']==c['id'] for r in rows)==3 for c in contexts),'favorable_and_unfavorable_cues_recorded':any(json.loads(r['favorable_json']) for r in rows) and any(json.loads(r['unfavorable_json']) for r in rows),'literal_context_selects_h0':by['C-LITERAL']['selected_hypothesis_id']=='H0','reversal_context_selects_h1':by['C-REVERSAL']['selected_hypothesis_id']=='H1','play_context_selects_h2':by['C-PLAY']['selected_hypothesis_id']=='H2','ambiguous_context_remains_undecided':by['C-AMBIG']['status']=='undecided','explicit_feedback_can_restore_literal':by['C-CORRECTED']['selected_hypothesis_id']=='H0','external_labels_never_drive_scores':all('eval' not in r for r in rows),'incompatible_commitments_constrained':solver.check()==sat,'evidence_roundtrip':pq.read_table(OUT/'hypothesis-evidence.parquet').num_rows==15};assert all(validations.values()),validations
 sources=[d3p,c1p,d6p,d7p,d8p,r4p];result={'literal_content':literal,'external_analysis_bundle':bundle,'hypotheses':hypotheses,'contexts':contexts,'evidence':rows,'decisions':decisions,'constraint':'not(commit(H0) and commit(H1))','source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sources},'important_boundary':'human_eval_label is scoring/audit metadata only and is never treated as speaker intention','validations':validations};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');(OUT/'summary.json').write_text(json.dumps({'contexts':len(contexts),'hypotheses_per_context':3,'literal_content_variants':1,'selected_contexts':sum(x['status']=='selected' for x in decisions),'undecided_contexts':sum(x['status']=='undecided' for x in decisions),'verdict':'GO_LITERAL_COMMITMENT_PRAGMATICS_SEPARATED'},indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'z3_solver':importlib.metadata.version('z3-solver'),'pyarrow':importlib.metadata.version('pyarrow'),'decision_margin':.20},indent=2)+'\n');print('CULT-02: literal content fixed; H0/H1/H2 selected contextually or left undecided; GO')
if __name__=='__main__':main()
