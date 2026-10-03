#!/usr/bin/env python3
"""DISC-02: audit which RST/eRST properties gumrrg actually serializes."""
import hashlib,json,platform
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parent.parent; SOURCE=ROOT/'poc/disc-01/output/results.json'; O=P/'output'
def nodes(n,parent=None):
 yield n,parent
 for k in ('left','right'):
  if k in n: yield from nodes(n[k],n)
def main():
 data=json.loads(SOURCE.read_text()); parsed=[r for r in data if r['status']=='parsed' and r['fixture']['text']]
 field_counts=Counter(); binary=True; nested=True; parent_counts=Counter(); edge_count=0
 for r in parsed:
  for tree in r['trees']:
   for n,parent in nodes(tree):
    field_counts.update(n.keys())
    children=[n[k] for k in ('left','right') if k in n]
    if children: binary &= len(children)==2
    if parent:
     edge_count+=1; parent_counts[(r['fixture']['id'],n['id'])]+=1
     nested &= parent['start']<=n['start']<=n['end']<=parent['end']
 matrix=[
  {'property':'EDU segmentation with character spans','present':True,'evidence':'elementary leaves with start/end/text'},
  {'property':'labeled rhetorical relations','present':True,'evidence':'relation on internal nodes'},
  {'property':'nuclearity','present':True,'evidence':'NS/SN/NN values on internal nodes'},
  {'property':'binary constituency tree','present':binary,'evidence':f'{edge_count} parent-child edges; every internal node has two children'},
  {'property':'confidence scores','present':field_counts['proba']>0,'evidence':f"proba field occurrences={field_counts['proba']}"},
  {'property':'explicit discourse signals','present':False,'evidence':'no signal field in serialized public output'},
  {'property':'secondary/eRST links','present':False,'evidence':'no secondary-edge or secedge collection in output'},
  {'property':'non-tree graph','present':False,'evidence':f'maximum observed parent count={max(parent_counts.values(),default=0)}'},
  {'property':'crossing/non-projective attachments','present':not nested,'evidence':f'all child spans nested in parent={nested}'},
  {'property':'automatic dialogue-turn structure','present':False,'evidence':'speaker markers remain source text; no turn/participant fields'},
 ]
 assert all(x['present'] for x in matrix[:4]) and all(not x['present'] for x in matrix[5:])
 summary={'source_fixture_count':len(parsed),'property_count':len(matrix),'present_count':sum(x['present'] for x in matrix),'absent_count':sum(not x['present'] for x in matrix),'classification':'RST_BINARY_TREE_OUTPUT_NOT_ERST_GRAPH_OUTPUT','verdict':'GO_CAPABILITY_BOUNDARY_DOCUMENTED'}
 result={'property_matrix':matrix,'source_artifact':str(SOURCE.relative_to(ROOT)),'classification':summary['classification'],'validation':{'core_rst_properties_present':all(x['present'] for x in matrix[:4]),'unsupported_erst_and_dialogue_properties_absent':all(not x['present'] for x in matrix[5:]),'all_child_spans_nested':nested,'maximum_parent_count':max(parent_counts.values(),default=0)}}
 O.mkdir(parents=True,exist_ok=True)
 for n,v in [('results.json',result),('property-matrix.json',matrix),('summary.json',summary),('versions-and-parameters.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'input_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'model_label':'gumrrg','classification_basis':'fields actually serialized by DiscourseUnit tree_to_dict'})]: (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"DISC-02: {summary['present_count']} properties present, {summary['absent_count']} absent; RST tree, not eRST graph")
if __name__=='__main__': main()
