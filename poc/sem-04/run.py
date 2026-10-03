#!/usr/bin/env python3
"""SEM-04: qualify Phonetisaurus n-best G2P on a reproducible lexicon split."""
import hashlib, importlib.metadata, json, platform, resource, subprocess, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import phonetisaurus

P=Path(__file__).resolve().parent; ROOT=P.parent.parent; O=P/'output'; CMU=ROOT/'.local/share/nltk_data/corpora/cmudict/cmudict'

def load(limit, held):
 lex=defaultdict(list)
 for line in CMU.read_text().splitlines():
  parts=line.split(); word=parts[0].lower(); phones=parts[2:]
  if word.isalpha() and word not in held: lex[word].append(phones)
  if len(lex)>=limit: break
 return dict(lex)

def main():
 cfg=json.loads((P/'fixtures.json').read_text()); held=set(cfg['held_out_words']); lex=load(cfg['training_entry_limit'],held)
 assert held.isdisjoint(lex)
 O.mkdir(parents=True,exist_ok=True); model=O/'phonetisaurus-model.fst'; corpus=O/'phonetisaurus-model.corpus'
 start=time.perf_counter(); before=resource.getrusage(resource.RUSAGE_CHILDREN); phonetisaurus.train(lex,model,corpus); train_s=time.perf_counter()-start; after=resource.getrusage(resource.RUSAGE_CHILDREN)
 start=time.perf_counter(); raw=list(phonetisaurus.predict(cfg['held_out_words'],model,nbest=cfg['nbest'])); predict_s=time.perf_counter()-start
 grouped=defaultdict(list)
 for word,phones in raw: grouped[word].append({'rank':len(grouped[word])+1,'phonemes':phones,'score':None,'alignment':None,'producer':'Phonetisaurus'})
 results=[]
 for word in cfg['held_out_words']:
  candidates=grouped[word]; results.append({'word':word,'in_training_lexicon':word in lex,'candidates':candidates,'candidate_count':len(candidates),'n_best_available':len(candidates)>1,'scores_exposed_by_python_api':False,'candidate_alignments_exposed_by_python_api':False,'per_word_lattice_exposed_by_python_api':False})
 assert all(r['candidate_count']>=2 for r in results)
 summary={'training_lexeme_count':len(lex),'held_out_count':len(results),'all_held_out':all(not r['in_training_lexicon'] for r in results),'all_have_multiple_candidates':all(r['n_best_available'] for r in results),'training_seconds':train_s,'prediction_seconds':predict_s,'child_max_rss_kib':after.ru_maxrss,'model_bytes':model.stat().st_size,'scores_available':False,'alignments_available_for_candidates':False,'per_word_lattice_available':False,'verdict':'PARTIAL_NBEST_WORKS_BUT_API_OMITS_SCORES_ALIGNMENTS_AND_DECODE_LATTICE'}
 versions={'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'phonetisaurus':importlib.metadata.version('phonetisaurus'),'cmudict_sha256':hashlib.sha256(CMU.read_bytes()).hexdigest(),'training_selection':'first alphabetic CMUdict lexemes excluding held-out words','nbest':cfg['nbest'],'model_format':'OpenFst WFST'}
 for n,v in [('results.json',results),('summary.json',summary),('versions-and-parameters.json',versions),('training-lexicon.json',lex)]: (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 print(f"SEM-04: {len(lex)} training lexemes; {len(results)} held out; n-best yes; scores/alignments/decode lattice absent from Python API")
if __name__=='__main__': main()
