#!/usr/bin/env python3
"""DLG-02: inspect Python Dynamic Syntax traces and probe DyLan Java reference."""
import hashlib,importlib.metadata,json,platform,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
import dynamicsyntax
P=Path(__file__).resolve().parent;ROOT=P.parent.parent;O=P/'output'
def tree(t):return [{'address':str(a),'labels':sorted(str(x)for x in n.labels),'complete':n.is_complete()}for a,n in sorted(t.items(),key=lambda x:str(x[0]))]
def spans(text):
 out=[];pos=0
 for token in text.split():
  start=text.lower().find(token.lower(),pos);out.append({'token':token.lower(),'span':[start,start+len(token)]});pos=start+len(token)
 return out
def main():
 fs=json.loads((P/'fixtures.json').read_text());results=[]
 for f in fs:
  t=time.perf_counter();r=dynamicsyntax.parse(f['text'],'ttr',speaker=f['speaker'],trace=True)
  steps=[]
  for label,tr in zip(('initial',)+r.trace_step_labels,r.trace_trees):steps.append({'step':label,'tree':tree(tr)})
  actions=[{'word':a.word,'action':a.action_name,'edge_id':a.edge_id,'before':tree(a.before_tree),'after':tree(a.after_tree)}for a in r.action_steps]
  results.append({'fixture':f,'producer':'dynamicsyntax-python','ok':r.ok,'semantics':str(r.semantics)if r.semantics else None,'incremental_states':steps,'actions':actions,'token_spans':spans(f['text']),'final_tree':tree(r.tree)if r.tree else None,'parse_seconds':time.perf_counter()-t})
 cp=':'.join([str(ROOT/'.local/src/dylan/dist/jar/*'),str(ROOT/'.local/src/dylan/lib/*')]);grammar=ROOT/'.local/src/dylan/resource/2015-english-ttr'
 cmd=['java','-cp',cp,'qmul.ds.SimpleParser',str(grammar)];j=subprocess.run(cmd,text=True,capture_output=True)
 java={'command':cmd,'exit_code':j.returncode,'stdout':j.stdout,'stderr':j.stderr,'checkout_commit':subprocess.run(['git','-C',str(ROOT/'.local/src/dylan'),'rev-parse','HEAD'],text=True,capture_output=True,check=True).stdout.strip(),'compatible_with_checkout_resources':j.returncode==0}
 assert next(x for x in results if x['fixture']['id']=='complete')['ok'];assert all(len(x['incremental_states'])==len(x['fixture']['text'].split())+1 for x in results)
 summary={'fixture_count':len(results),'python_success_count':sum(x['ok']for x in results),'python_failure_count':sum(not x['ok']for x in results),'incremental_trace_count':sum(len(x['incremental_states'])for x in results),'action_count':sum(len(x['actions'])for x in results),'french_success':next(x['ok']for x in results if x['fixture']['language']=='fr'),'dylan_java_exit_code':j.returncode,'implementation_comparison_complete':j.returncode==0,'verdict':'PARTIAL_PYTHON_INCREMENTAL_TRACE_WORKS_DYLAN_REFERENCE_INCOMPATIBLE'}
 O.mkdir(parents=True,exist_ok=True)
 for n,v in [('results.json',results),('dylan-java-probe.json',java),('summary.json',summary),('versions-and-parameters.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'dynamicsyntax':importlib.metadata.version('dynamicsyntax'),'python':platform.python_version(),'grammar':'ttr alias','dylan_jar_sha256':hashlib.sha256((ROOT/'.local/src/dylan/dist/jar/ds.jar').read_bytes()).hexdigest()})]:(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"DLG-02: Python {summary['python_success_count']}/{len(results)}; {summary['incremental_trace_count']} states; DyLan Java exit {j.returncode}")
if __name__=='__main__':main()
