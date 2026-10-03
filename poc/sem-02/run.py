#!/usr/bin/env python3
"""SEM-02: compare graphemic, IPA-string and PanPhon feature distances."""
import importlib.metadata, json, os, platform
from datetime import datetime, timezone
from pathlib import Path
import editdistance, epitran, panphon
from panphon.distance import Distance

P=Path(__file__).resolve().parent; O=P/'output'

def main():
 f=json.loads((P/'fixtures.json').read_text()); d=Distance(); ft=panphon.FeatureTable(); analyzers={}; out=[]
 for x in f:
  if 'ipa_left' in x: a,b=x['ipa_left'],x['ipa_right']; source='controlled_ipa'
  else:
   e=analyzers.setdefault(x['language_script'],epitran.Epitran(x['language_script'])); a,b=e.transliterate(x['left']),e.transliterate(x['right']); source='SEM-01_Epitran_contract'
  sa,sb=ft.ipa_segs(a),ft.ipa_segs(b); unknown_a=''.join(ch for ch in a if ch not in ''.join(sa)); unknown_b=''.join(ch for ch in b if ch not in ''.join(sb))
  feature_d=d.weighted_feature_edit_distance(a,b)
  differences=[]
  for i,(la,lb) in enumerate(zip(ft.word_fts(a),ft.word_fts(b))):
   va,vb=la.numeric(),lb.numeric(); changed=[ft.names[j] for j,(u,v) in enumerate(zip(va,vb)) if u!=v]
   if changed: differences.append({'aligned_index':i,'left_segment':sa[i],'right_segment':sb[i],'changed_features':changed})
  row={**x,'ipa_left':a,'ipa_right':b,'ipa_source':source,'graphemic_distance':editdistance.eval(x['left'],x['right']),'ipa_edit_distance':editdistance.eval(a,b),'panphon_weighted_feature_distance':feature_d,'segments':{'left':sa,'right':sb},'feature_differences_on_positionally_aligned_segments':differences,'unknown_material':{'left':unknown_a,'right':unknown_b},'semantic_identity_inferred':False}
  if x['expected']=='phonology_distinct_from_graphy': assert row['ipa_edit_distance'] < row['graphemic_distance']
  if x['expected']=='unknown_segment_reported': assert unknown_a
  out.append(row)
 assert all(not r['semantic_identity_inferred'] for r in out)
 summary={'fixture_count':len(out),'phonology_vs_graphy_contrast_count':sum(r['ipa_edit_distance']!=r['graphemic_distance'] for r in out),'unknown_segment_cases':sum(bool(r['unknown_material']['left']+r['unknown_material']['right']) for r in out),'semantic_identity_inference_count':0,'verdict':'GO_EXPLAINABLE_FEATURE_DISTANCE_WITH_EXPLICIT_UNKNOWN_SEGMENTS'}
 O.mkdir(parents=True,exist_ok=True)
 for n,v in [('results.json',out),('summary.json',summary),('versions-and-parameters.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'panphon':importlib.metadata.version('panphon'),'epitran':importlib.metadata.version('epitran'),'distance':'PanPhon weighted_feature_edit_distance','alignment_explanation':'position-wise diagnostic; distance remains PanPhon native'})]: (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"SEM-02: {len(out)} pairs; {summary['phonology_vs_graphy_contrast_count']} graphy/phonology contrasts; {summary['unknown_segment_cases']} unknown-segment case")
if __name__=='__main__': main()
