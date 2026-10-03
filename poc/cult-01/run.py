#!/usr/bin/env python3
"""CULT-01: induce anonymous high-level expectations from real Switchboard turns."""
from __future__ import annotations
import hashlib,importlib.metadata,json,platform
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import pyarrow as pa,pyarrow.parquet as pq
P=Path(__file__).resolve().parent;ROOT=P.parent.parent;OUT=P/'output';CORPUS=ROOT/'.local/share/convokit/corpora/switchboard-corpus';UTTS=CORPUS/'utterances.jsonl';CONVS=CORPUS/'conversations.json'
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def symbol(tag):return 'A_'+hashlib.sha256(tag.encode()).hexdigest()[:12]
def split(cid):return 'heldout' if int(hashlib.sha256(cid.encode()).hexdigest()[:8],16)%5==0 else 'train'
def main():
 OUT.mkdir(parents=True,exist_ok=True);meta=json.loads(CONVS.read_text());conversations=defaultdict(list);tag_map={}
 with UTTS.open() as f:
  for line_no,line in enumerate(f,1):
   r=json.loads(line);tags=r.get('meta',{}).get('tag') or [];external=tags[0][1] if tags else 'NO_EXTERNAL_TAG';anon=symbol(external);tag_map[anon]=external;conversations[r['conversation_id']].append({'utterance_id':r['id'],'speaker':r['speaker'],'raw_text':r['text'],'anonymous_act':anon,'external_tag':external,'source_line':line_no})
 train_prefix=Counter();train_next=Counter();global_next=Counter();occurrences=[]
 for cid,turns in conversations.items():
  part=split(cid)
  for i in range(len(turns)-2):
   a,b,c=turns[i:i+3];prefix=(a['anonymous_act'],b['anonymous_act']);row={'conversation_id':cid,'split':part,'topic':meta.get(cid,{}).get('topic_description','UNKNOWN'),'prefix_0':prefix[0],'prefix_1':prefix[1],'actual_next':c['anonymous_act'],'speaker_relation_01':'same' if a['speaker']==b['speaker'] else 'change','speaker_relation_12':'same' if b['speaker']==c['speaker'] else 'change','utterance_ids':[a['utterance_id'],b['utterance_id'],c['utterance_id']],'raw_turns':[a['raw_text'],b['raw_text'],c['raw_text']],'source_lines':[a['source_line'],b['source_line'],c['source_line']]};occurrences.append(row)
   if part=='train':train_prefix[prefix]+=1;train_next[(prefix,c['anonymous_act'])]+=1;global_next[c['anonymous_act']]+=1
 candidates=[]
 for prefix,total in train_prefix.items():
  options=[(nxt,n) for (p,nxt),n in train_next.items() if p==prefix];winner,count=max(options,key=lambda x:x[1]);confidence=count/total
  if total>=500 and confidence>=.38:candidates.append((count,confidence,prefix,winner,total))
 candidates=sorted(candidates,reverse=True)[:12];patterns=[];pattern_lookup={}
 for rank,(count,confidence,prefix,winner,total) in enumerate(candidates,1):
  pid=f'Pattern_High_{rank:03d}';pattern_lookup[prefix]=(pid,winner);rows=[r for r in occurrences if r['split']=='train' and (r['prefix_0'],r['prefix_1'])==prefix];supports=[r for r in rows if r['actual_next']==winner];exceptions=[r for r in rows if r['actual_next']!=winner];role_dist=Counter((r['speaker_relation_01'],r['speaker_relation_12']) for r in supports);topics=Counter(r['topic'] for r in supports);patterns.append({'pattern_id':pid,'anonymous':True,'precondition_sequence':list(prefix),'expected_next':winner,'conditional_probability':confidence,'training_occurrences':total,'support_count':len(supports),'exception_count':len(exceptions),'typical_role_transitions':list(role_dist.most_common(1)[0][0]),'role_transition_distribution':{'|'.join(k):v for k,v in role_dist.items()},'context_topic_count':len(topics),'top_contexts':topics.most_common(8),'transformation':{'before':list(prefix),'after':[*prefix,winner]},'outcome_definition':'actual next anonymous dialogue-act symbol equals expected_next','support_examples':[{'conversation_id':r['conversation_id'],'utterance_ids':r['utterance_ids'],'raw_turns':r['raw_turns'],'source_lines':r['source_lines']} for r in supports[:3]],'exception_examples':[{'conversation_id':r['conversation_id'],'utterance_ids':r['utterance_ids'],'raw_turns':r['raw_turns'],'actual_next':r['actual_next'],'source_lines':r['source_lines']} for r in exceptions[:3]]})
 evidence=[];held=[]
 for r in occurrences:
  match=pattern_lookup.get((r['prefix_0'],r['prefix_1']))
  if not match:continue
  pid,pred=match;ok=r['actual_next']==pred;evidence.append({'pattern_id':pid,'conversation_id':r['conversation_id'],'split':r['split'],'topic':r['topic'],'utterance_id_0':r['utterance_ids'][0],'utterance_id_1':r['utterance_ids'][1],'utterance_id_2':r['utterance_ids'][2],'predicted_next':pred,'actual_next':r['actual_next'],'is_support':ok,'source_line_0':r['source_lines'][0],'source_line_1':r['source_lines'][1],'source_line_2':r['source_lines'][2]})
  if r['split']=='heldout':held.append({**r,'matched_pattern_id':pid,'predicted_next':pred,'correct':ok,'novel_conversation':True})
 pq.write_table(pa.Table.from_pylist(evidence),OUT/'pattern-evidence.parquet',compression='zstd');global_baseline=global_next.most_common(1)[0][0];accuracy=sum(r['correct'] for r in held)/len(held);baseline=sum(r['actual_next']==global_baseline for r in held)/len(held);train_cids={cid for cid in conversations if split(cid)=='train'};held_cids={r['conversation_id'] for r in held}
 artifacts=[]
 for poc in ('ind-03','ind-04','ind-05','ind-06'):
  path=ROOT/'poc'/poc/'output/results.json';artifacts.append({'poc':poc.upper(),'path':str(path.relative_to(ROOT)),'sha256':sha(path)})
 vals={'real_corpus_scale':len(conversations)==1155 and sum(map(len,conversations.values()))==122646,'source_text_and_spans_traceable':all(p['support_examples'] and all(x['raw_turns'] and x['source_lines'] for x in p['support_examples']) for p in patterns),'patterns_induced_not_fixed':len(patterns)>=3,'supports_contexts_exceptions_outcomes_present':all(p['support_count'] and p['exception_count'] and p['context_topic_count'] and p['outcome_definition'] for p in patterns),'roles_sequences_transformations_present':all(p['typical_role_transitions'] and p['precondition_sequence'] and p['transformation'] for p in patterns),'heldout_conversations_disjoint':not (train_cids&held_cids),'heldout_predictions_nonempty':len(held)>100,'model_beats_global_baseline':accuracy>baseline,'external_tags_not_pattern_names':all(p['pattern_id'].startswith('Pattern_High_') for p in patterns),'complete_evidence_table':len(evidence)==sum(p['training_occurrences'] for p in patterns)+len(held),'all_induction_artifacts_bound':len(artifacts)==4};assert all(vals.values()),(vals,len(patterns),len(held),accuracy,baseline)
 result={'corpus':{'name':'Switchboard Dialog Act Corpus via ConvoKit','version':1,'license':'CC BY-NC-SA 3.0 (as recorded by project dependency inventory)','utterance_file':str(UTTS.relative_to(ROOT)),'utterance_file_sha256':sha(UTTS),'conversation_file_sha256':sha(CONVS),'conversation_count':len(conversations),'utterance_count':sum(map(len,conversations.values()))},'anonymization':{'method':'A_ + first 12 hex digits of SHA-256(external SWDA tag)','mapping_for_external_audit_only':tag_map,'mapping_used_as_taxonomy':False},'patterns':patterns,'heldout_evaluation':{'occurrences':len(held),'accuracy':accuracy,'global_majority_baseline_accuracy':baseline,'sample':[{'conversation_id':r['conversation_id'],'topic':r['topic'],'raw_turns':r['raw_turns'],'matched_pattern_id':r['matched_pattern_id'],'predicted_next':r['predicted_next'],'actual_next':r['actual_next'],'correct':r['correct'],'source_lines':r['source_lines']} for r in held[:20]]},'evidence_table':{'path':'output/pattern-evidence.parquet','rows':len(evidence),'sha256':sha(OUT/'pattern-evidence.parquet')},'provenance_inputs':artifacts,'limitations':['SWDA dialogue acts are external observations, not internal cultural concepts.','The POC learns local three-turn expectations; it does not claim a complete model of culture.','Primary tag means the first annotated segment tag of an utterance; all raw segment annotations remain in the source corpus.'],'validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'source':'real Switchboard human conversations','conversations':len(conversations),'utterances':sum(map(len,conversations.values())),'patterns':len(patterns),'evidence_rows':len(evidence),'heldout_occurrences':len(held),'heldout_accuracy':accuracy,'global_baseline_accuracy':baseline,'verdict':'GO_REAL_SWITCHBOARD_ANONYMOUS_HIGH_LEVEL_PATTERNS'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'pyarrow':importlib.metadata.version('pyarrow'),'split':'SHA-256(conversation_id) mod 5; zero held out','minimum_training_prefix_occurrences':500,'minimum_conditional_probability':.38,'maximum_patterns':12},indent=2)+'\n');print(f'CULT-01: real Switchboard {len(conversations)} conversations; {len(patterns)} patterns; heldout {accuracy:.3f}>{baseline:.3f}; GO')
if __name__=='__main__':main()
