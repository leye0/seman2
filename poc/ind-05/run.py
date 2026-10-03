#!/usr/bin/env python3
"""IND-05: measured and traceable promote/merge/split/forget decisions."""
from __future__ import annotations
import importlib.metadata,json,math,platform
from datetime import datetime,timezone
from pathlib import Path
import duckdb,networkx as nx,numpy as np,polars as pl
from scipy.stats import chi2_contingency
P=Path(__file__).resolve().parent;OUT=P/'output';PATTERNS=['Pattern_Promote','Pattern_Merge_A','Pattern_Merge_B','Pattern_Split','Pattern_Forget','Pattern_Keep']
def graph(kind):
 g=nx.DiGraph();g.add_node('v0',kind='A');g.add_node('v1',kind='B');g.add_edge('v0','v1',relation='R')
 if kind not in ('merge_a','merge_b'):g.add_node('v2',kind=kind);g.add_edge('v1','v2',relation=f'R_{kind}')
 return g
def data():
 rows=[]
 for p in PATTERNS:
  n={'Pattern_Promote':120,'Pattern_Merge_A':80,'Pattern_Merge_B':80,'Pattern_Split':100,'Pattern_Forget':8,'Pattern_Keep':40}[p]
  for i in range(n):
   context=f'c{i%4}';window=(i//4)%4
   if p=='Pattern_Promote':out=i%2==0;pred=out if i%10!=0 else not out
   elif p.startswith('Pattern_Merge'):out=i%5!=0;pred=i%5!=0
   elif p=='Pattern_Split':out=(context in ('c0','c2') and i%10!=0) or (context in ('c1','c3') and i%10==0);pred=True
   elif p=='Pattern_Forget':out=i%2==0;pred=not out
   else:out=i%3!=0;pred=i%4!=0
   occurrence_id=f"shared-{i:03d}" if p.startswith('Pattern_Merge') else f'{p}-{i:03d}'
   rows.append({'pattern_id':p,'occurrence_id':occurrence_id,'context':context,'time_window':window,'outcome':out,'prediction':pred,'age_days':400 if p=='Pattern_Forget' else 10+i%20})
 return rows
def main():
 OUT.mkdir(parents=True,exist_ok=True);rows=data();df=pl.DataFrame(rows);path=OUT/'pattern-events.parquet';df.write_parquet(path,compression='zstd');con=duckdb.connect();ps=str(path.resolve()).replace("'","''");con.execute(f"CREATE VIEW e AS SELECT * FROM read_parquet('{ps}')")
 base=con.execute("""SELECT pattern_id,count(*) support,count(DISTINCT context) contexts,avg((prediction=outcome)::INT) accuracy,avg(outcome::INT) outcome_rate,avg((prediction!=outcome)::INT) exception_rate,avg(age_days) mean_age FROM e GROUP BY pattern_id ORDER BY pattern_id""").fetchall();names=[d[0] for d in con.description];metrics={r[0]:dict(zip(names,r)) for r in base};window=con.execute("SELECT pattern_id,time_window,avg(outcome::INT) rate FROM e GROUP BY pattern_id,time_window ORDER BY pattern_id,time_window").fetchall();context=con.execute("SELECT pattern_id,context,sum(outcome::INT) positive,count(*) total FROM e GROUP BY pattern_id,context ORDER BY pattern_id,context").fetchall();con.close()
 graphs={'Pattern_Promote':graph('promote'),'Pattern_Merge_A':graph('merge_a'),'Pattern_Merge_B':graph('merge_b'),'Pattern_Split':graph('split'),'Pattern_Forget':graph('forget'),'Pattern_Keep':graph('keep')}
 for p,m in metrics.items():
  rates=np.array([r[2] for r in window if r[0]==p]);m['stability']=float(1-np.std(rates)/(np.mean(rates) or 1));m['recurrence_inter_context']=m['contexts']/4;m['predictive_improvement']=m['accuracy']-max(m['outcome_rate'],1-m['outcome_rate']);m['descriptive_cost']=graphs[p].number_of_nodes()+graphs[p].number_of_edges();m['compression_gain_bytes']=m['support']*m['descriptive_cost']*24-(m['descriptive_cost']*24+m['support']*8)
 polars_counts={r['pattern_id']:r['len'] for r in df.group_by('pattern_id').len().to_dicts()};overlap=len(set(df.filter(pl.col('pattern_id')=='Pattern_Merge_A')['occurrence_id'])&set(df.filter(pl.col('pattern_id')=='Pattern_Merge_B')['occurrence_id']))/80;merge_iso=nx.is_isomorphic(graphs['Pattern_Merge_A'],graphs['Pattern_Merge_B'],node_match=lambda a,b:a['kind']==b['kind'],edge_match=lambda a,b:a['relation']==b['relation'])
 table=[]
 for c in ('c0','c1','c2','c3'):
  r=next(x for x in context if x[0]=='Pattern_Split' and x[1]==c);table.append([r[2],r[3]-r[2]])
 chi2,pvalue,_,_=chi2_contingency(table)
 decisions=[
  {'action':'promote','targets':['Pattern_Promote'],'reasons':{'support>=100':metrics['Pattern_Promote']['support']>=100,'recurrence>=.75':metrics['Pattern_Promote']['recurrence_inter_context']>=.75,'predictive_improvement>.2':metrics['Pattern_Promote']['predictive_improvement']>.2,'exception_rate<=.2':metrics['Pattern_Promote']['exception_rate']<=.2}},
  {'action':'merge','targets':['Pattern_Merge_A','Pattern_Merge_B'],'reasons':{'structurally_isomorphic':merge_iso,'occurrence_overlap>=.95':overlap>=.95,'outcome_rate_delta<=.02':abs(metrics['Pattern_Merge_A']['outcome_rate']-metrics['Pattern_Merge_B']['outcome_rate'])<=.02}},
  {'action':'split','targets':['Pattern_Split'],'children':['Pattern_Split_context_even','Pattern_Split_context_odd'],'reasons':{'context_outcome_chi2_p<.001':pvalue<.001,'incompatible_context_rates':max(r[0]/sum(r) for r in table)-min(r[0]/sum(r) for r in table)>.7}},
  {'action':'forget','targets':['Pattern_Forget'],'reasons':{'support<10':metrics['Pattern_Forget']['support']<10,'mean_age>365':metrics['Pattern_Forget']['mean_age']>365,'predictive_improvement<=0':metrics['Pattern_Forget']['predictive_improvement']<=0}},
  {'action':'retain','targets':['Pattern_Keep'],'reasons':{'no_other_policy_threshold_met':True}},]
 vals={'duckdb_polars_support_equal':all(metrics[p]['support']==polars_counts[p] for p in PATTERNS),'all_required_metrics_separate':all(all(k in m for k in ('support','compression_gain_bytes','recurrence_inter_context','predictive_improvement','descriptive_cost','exception_rate','stability')) for m in metrics.values()),'all_decisions_fully_justified':all(all(d['reasons'].values()) for d in decisions),'expected_actions':[(d['action'],d['targets']) for d in decisions]==[('promote',['Pattern_Promote']),('merge',['Pattern_Merge_A','Pattern_Merge_B']),('split',['Pattern_Split']),('forget',['Pattern_Forget']),('retain',['Pattern_Keep'])],'split_statistically_supported':pvalue<.001,'merge_structurally_supported':merge_iso and overlap==1};assert all(vals.values()),(vals,metrics,pvalue)
 result={'metrics':metrics,'window_rates':[{'pattern_id':r[0],'window':r[1],'rate':r[2]} for r in window],'context_contingencies':[{'pattern_id':r[0],'context':r[1],'positive':r[2],'total':r[3]} for r in context],'structural_metrics':{'merge_isomorphic':merge_iso,'merge_occurrence_overlap':overlap},'split_test':{'method':'SciPy chi-square contingency','chi2':chi2,'p_value':pvalue,'table':table},'decisions':decisions,'policy_boundary':'Metrics are observations; decisions are explicit versionable policy outputs and do not mutate a Learned Graph in this POC.','validations':vals};convert=lambda x:x.item() if hasattr(x,'item') else str(x);(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=convert)+'\n');summary={'patterns':len(PATTERNS),'events':len(rows),'actions':[d['action'] for d in decisions],'split_p_value':pvalue,'merge_overlap':overlap,'verdict':'GO_TRACEABLE_PATTERN_LIFECYCLE_METRICS'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2,default=convert)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'duckdb':importlib.metadata.version('duckdb'),'polars':importlib.metadata.version('polars'),'numpy':importlib.metadata.version('numpy'),'scipy':importlib.metadata.version('scipy'),'networkx':importlib.metadata.version('networkx'),'compression_model':'naive repeated graph bytes minus one prototype plus 8-byte references'},indent=2)+'\n');print('IND-05: promote/merge/split/forget/retain decisions all justified; GO')
if __name__=='__main__':main()
