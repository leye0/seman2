#!/usr/bin/env python3
"""SEM-03: explicit weighted finite-state form relations with Pynini."""
import importlib.metadata, json, math, platform
from datetime import datetime, timezone
from pathlib import Path
import pynini
from pynini.lib import pynutil

P=Path(__file__).resolve().parent; O=P/'output'

def weighted(rule): return pynutil.add_weight(pynini.cross(rule['input'],rule['output']),rule['weight'])
def paths(fst): return [{'input':i,'output':o,'weight':float(str(w))} for i,o,w in fst.paths().items()]

def main():
 data=json.loads((P/'fixtures.json').read_text()); rules=data['rules']; by_id={r['id']:r for r in rules}
 machine=pynini.union(*(weighted(r) for r in rules)).optimize(); results=[]
 for q in data['queries']:
  found=paths(pynini.compose(pynini.accep(q['input']),machine))
  for p in found:
   matches=[r for r in rules if r['input']==q['input'] and r['output']==p['output'] and math.isclose(r['weight'],p['weight'],abs_tol=1e-5)]
   assert len(matches)==1
   p.update({'rule_id':matches[0]['id'],'transformation_type':matches[0]['type'],'source_span':[0,len(q['input'])],'semantic_identity_inferred':False,'source_rewritten':False})
  assert len(found)>=q['minimum_paths'] and len(found)<=q.get('maximum_paths',10**9)
  results.append({'query':q,'paths':sorted(found,key=lambda x:(x['weight'],x['output']))})
 comp=data['composition']; first=weighted(by_id[comp['first_rule']]); second=weighted(by_id[comp['second_rule']]); composed=pynini.compose(first,second).optimize(); cp=paths(pynini.compose(pynini.accep(comp['input']),composed));
 assert len(cp)==1 and cp[0]['output']==comp['expected_output'] and math.isclose(cp[0]['weight'],comp['expected_weight'],abs_tol=1e-5)
 O.mkdir(parents=True,exist_ok=True); machine.write(str(O/'form-relations.fst')); composed.write(str(O/'composed-io-expansion.fst'))
 chars=sorted(set(''.join(r['input']+r['output'] for r in rules))); symbols=[{'symbol':'<eps>','label':0}]+[{'symbol':c,'label':i+1} for i,c in enumerate(chars)]
 summary={'rule_count':len(rules),'query_count':len(results),'path_count':sum(len(r['paths']) for r in results),'negative_query_path_count':len(results[-1]['paths']),'composition_passed':True,'semantic_identity_inference_count':0,'source_rewrite_count':0,'verdict':'GO_EXPLICIT_COMPOSABLE_WEIGHTED_FORM_RELATIONS'}
 artifacts={'rules':rules,'queries':results,'composition':{**comp,'paths':cp,'component_weights':[by_id[comp['first_rule']]['weight'],by_id[comp['second_rule']]['weight']]},'symbol_table':symbols}
 for n,v in [('results.json',artifacts),('summary.json',summary),('symbol-table.json',symbols),('versions-and-parameters.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'pynini':importlib.metadata.version('pynini'),'weight_semiring':'tropical','token_type':'UTF-8 byte labels','ontology_status':'formal relation candidates only'})]: (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"SEM-03: {len(rules)} rules; {summary['path_count']} paths; composition io→input/output weight {cp[0]['weight']:.1f}")
if __name__=='__main__': main()
