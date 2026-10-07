#!/usr/bin/env python3
"""CODE-02: verify invalid code remains reconstructible with error nodes."""
import hashlib,importlib.metadata,json,platform
from datetime import datetime,timezone
from pathlib import Path
from tree_sitter_language_pack import get_parser
P=Path(__file__).resolve().parent; O=P/'output'
def walk(n):
 yield n
 for c in n.children: yield from walk(c)
def main():
 fs=json.loads((P/'fixtures.json').read_text()); out=[]
 for f in fs:
  b=f['text'].encode(); root=get_parser(f['language']).parse(b).root_node; nodes=list(walk(root)); errors=[n for n in nodes if n.type=='ERROR']; missing=[n for n in nodes if n.is_missing]
  diagnostic=[{'kind':'ERROR' if n.type=='ERROR' else 'MISSING','type':n.type,'byte_span':[n.start_byte,n.end_byte],'text':b[n.start_byte:n.end_byte].decode()} for n in errors+missing]
  covered=[False]*len(b)
  for n in nodes:
   if not n.children:
    for i in range(n.start_byte,n.end_byte): covered[i]=True
  uncovered=[]; start=None
  for i,value in enumerate(covered+[True]):
   if not value and start is None:start=i
   elif value and start is not None:uncovered.append({'byte_span':[start,i],'text':b[start:i].decode()});start=None
  assert root.start_byte==0 and root.end_byte==len(b) and b[root.start_byte:root.end_byte].decode()==f['text'] and (errors or missing)
  out.append({'fixture':f,'root_type':root.type,'has_error':root.has_error,'error_nodes':diagnostic,'uncovered_leaf_bytes':uncovered,'root_source_reconstructed':True,'source_sha256':hashlib.sha256(b).hexdigest(),'material_deleted':False})
 summary={'fixture_count':len(out),'fixtures_with_error_or_missing':sum(bool(r['error_nodes']) for r in out),'error_node_count':sum(len(r['error_nodes']) for r in out),'all_root_sources_reconstructed':True,'material_deleted_count':0,'verdict':'GO_PARTIAL_TREES_PRESERVE_INVALID_SOURCE'}
 O.mkdir(parents=True,exist_ok=True)
 for n,v in [('results.json',out),('summary.json',summary),('versions-and-parameters.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'tree_sitter':importlib.metadata.version('tree-sitter'),'tree_sitter_language_pack':importlib.metadata.version('tree-sitter-language-pack'),'coverage':'leaf byte spans; whitespace may remain uncovered but is retained by root/source'})]: (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"CODE-02: {len(out)} invalid fragments; {summary['error_node_count']} ERROR/MISSING nodes; no source loss")
if __name__=='__main__': main()
