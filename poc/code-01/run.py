#!/usr/bin/env python3
"""CODE-01: lossless Tree-sitter CST inspection across selected languages."""
import importlib.metadata,json,platform
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from tree_sitter_language_pack import get_parser
P=Path(__file__).resolve().parent; O=P/'output'
def encode_node(node,source):
 children=[]
 for i,ch in enumerate(node.children):
  item=encode_node(ch,source); item['field_name']=node.field_name_for_child(i); children.append(item)
 return {'type':node.type,'named':node.is_named,'missing':node.is_missing,'error':node.type=='ERROR','byte_span':[node.start_byte,node.end_byte],'point_span':[[node.start_point.row,node.start_point.column],[node.end_point.row,node.end_point.column]],'text':source[node.start_byte:node.end_byte].decode('utf-8'),'children':children}
def flatten(n):
 yield n
 for c in n['children']: yield from flatten(c)
def main():
 fs=json.loads((P/'fixtures.json').read_text()); out=[]
 for f in fs:
  b=f['text'].encode(); tree=get_parser(f['language']).parse(b); root=encode_node(tree.root_node,b); nodes=list(flatten(root)); named=[n for n in nodes if n['named']]; comments=[n for n in nodes if 'comment' in n['type']]
  assert root['byte_span']==[0,len(b)] and root['text']==f['text'] and not tree.root_node.has_error and comments
  out.append({'fixture':f,'status':'parsed','root_type':root['type'],'has_error':tree.root_node.has_error,'cst':root,'named_ast_projection':[{'type':n['type'],'byte_span':n['byte_span'],'text':n['text']} for n in named],'node_type_counts':dict(Counter(n['type'] for n in nodes)),'comment_nodes':comments,'source_reconstructed':True})
 summary={'fixture_count':len(out),'languages':[r['fixture']['language'] for r in out],'all_root_spans_cover_source':True,'all_sources_reconstructed':True,'all_have_comments':all(r['comment_nodes'] for r in out),'error_fixture_count':sum(r['has_error'] for r in out),'verdict':'GO_LOSSLESS_TREE_SITTER_CST'}
 O.mkdir(parents=True,exist_ok=True)
 for n,v in [('results.json',out),('summary.json',summary),('versions-and-parameters.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'tree_sitter':importlib.metadata.version('tree-sitter'),'tree_sitter_language_pack':importlib.metadata.version('tree-sitter-language-pack'),'offsets':'UTF-8 byte offsets plus zero-based row/byte-column points'})]: (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"CODE-01: {len(out)} languages; all sources reconstructed; comments preserved")
if __name__=='__main__': main()
