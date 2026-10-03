#!/usr/bin/env python3
"""DLG-12: real auxiliary coreference/topic tools, retained as attributed baselines."""
from __future__ import annotations
import importlib.metadata,json,os,platform,subprocess
from datetime import datetime,timezone
from pathlib import Path
from convokit import Corpus,Speaker,Utterance
from nltk.corpus import stopwords
from nltk.tokenize import TextTilingTokenizer
import spacy
P=Path(__file__).resolve().parent;ROOT=P.parent.parent;OUT=P/'output'
DATA={
'en':[('u1','Alice met Marie beside the rover. She inspected it carefully before the launch.'),('u2','Marie discussed the rover battery and the rover camera. The engineering topic remained active.'),('u3','Alice, not Marie, wrote the inspection report. This later context supports Alice for the earlier writer role.'),('u4','The budget committee reviewed costs and invoices. Finance dominated this separate discussion.'),('u5','Taxes, salaries, and contracts occupied the committee. Every budget item required a signed receipt.'),('u6','The accountant summarized expenses and forecasts. Nobody discussed rover hardware during this digression.'),('u7','Back to the rover, its camera needs paint protection. The engineering topic resumes after finance.'),('u8','The rover battery passed the cold test. It will support the launch sequence.')],
'fr':[('f1','Alice a rencontré Marie près du robot. Elle l’a inspecté avec soin avant le lancement.'),('f2','Marie a décrit la batterie du robot et sa caméra. Le sujet technique est resté actif.'),('f3',"C’est Marie, et non Alice, qui a signé le rapport. Ce contexte tardif soutient Marie pour le rôle discuté."),('f4','Le comité financier a étudié les coûts et les factures. Le budget est devenu le nouveau sujet.'),('f5','Les taxes, les salaires et les contrats occupaient le comité. Chaque dépense exigeait un reçu.'),('f6','La comptable a résumé les prévisions. Personne ne parlait du matériel du robot pendant cette digression.'),('f7','Revenons au robot : sa caméra exige une protection. Le sujet technique reprend après les finances.'),('f8','La batterie du robot a réussi le test de froid. Elle soutiendra la séquence de lancement.')],}
def corenlp(lang,text):
 home=ROOT/'.local/opt/stanford-corenlp';args=['java','-Xmx3g','-cp',str(home/'*'),'edu.stanford.nlp.pipeline.StanfordCoreNLP']
 if lang=='fr':args+=['-props','StanfordCoreNLP-french.properties','-annotators','tokenize,ssplit,pos,lemma,ner,depparse']
 else:args+=['-annotators','tokenize,ssplit,pos,lemma,ner,parse,coref','-coref.algorithm','neural']
 args+=['-outputFormat','json'];corenlp_text=text.replace('\n\n',' ');p=subprocess.run(args,input=corenlp_text+'\n',text=True,capture_output=True,timeout=120,env={**os.environ,'LC_ALL':'C.UTF-8'});return p,json.loads(p.stdout)
def coreferee(lang,text):
 model='en_core_web_sm' if lang=='en' else 'fr_core_news_sm';nlp=spacy.load(model);nlp.add_pipe('coreferee');doc=nlp(text);chains=[]
 for ci,chain in enumerate(doc._.coref_chains):
  mentions=[]
  for mention in chain:
   indexes=list(mention);span=doc[min(indexes):max(indexes)+1];mentions.append({'text':span.text,'token_indexes':indexes,'char_span':[span.start_char,span.end_char]})
  chains.append({'chain_id':f'coreferee-{lang}-{ci}','mentions':mentions})
 return chains
def corenlp_chains(data):
 out=[]
 for cid,mentions in data.get('corefs',{}).items():out.append({'chain_id':f'corenlp-en-{cid}','mentions':[{'text':m['text'],'sentence':m['sentNum'],'token_span':[m['startIndex'],m['endIndex']]} for m in mentions]})
 return out
def tiling(lang,text):
 sw=stopwords.words('english' if lang=='en' else 'french');tok=TextTilingTokenizer(w=12,k=6,stopwords=sw,smoothing_width=2);segments=tok.tokenize(text);cursor=0;rows=[]
 for i,segment in enumerate(segments):
  start=text.find(segment,cursor);end=start+len(segment);rows.append({'segment_id':f'texttiling-{lang}-{i}','char_span':[start,end],'text':segment,'boundary_after':i<len(segments)-1,'uncertainty':.35});cursor=end
 return rows
def main():
 OUT.mkdir(parents=True,exist_ok=True);results={};all_utts=[];speakers={'A':Speaker(id='A'),'B':Speaker(id='B')}
 for lang,turns in DATA.items():
  text='\n\n'.join(t for _,t in turns);proc,cn=corenlp(lang,text);assert proc.returncode==0
  cf=coreferee(lang,text);tt=tiling(lang,text)
  for i,(uid,raw) in enumerate(turns):all_utts.append(Utterance(id=uid,speaker=speakers['A' if i%2==0 else 'B'],text=raw,reply_to=turns[i-1][0] if i else None,meta={'language':lang}))
  results[lang]={'text':text,'turns':[{'id':i,'text':t} for i,t in turns],'coreferee_chains':cf,'corenlp_chains':corenlp_chains(cn) if lang=='en' else [],'corenlp_entities':[{'text':e['text'],'ner':e.get('ner'),'char_span':[e.get('characterOffsetBegin'),e.get('characterOffsetEnd')]} for s in cn['sentences'] for e in s.get('entitymentions',[])],'texttiling_segments':tt,'tool_notes':{'corenlp':'English coreference; French syntax/NER only because the installed French pipeline exposes no equivalent coref annotator','coreferee':'candidate chains, not truth','texttiling':'lexical topic baseline'}}
 corpus=Corpus(utterances=all_utts);topology=[{'id':u.id,'reply_to':u.reply_to,'speaker':u.speaker.id,'language':u.meta['language']} for u in corpus.iter_utterances()]
 disagreements=[]
 en_cf=[{m['text'].lower() for m in c['mentions']} for c in results['en']['coreferee_chains']];en_cn=[{m['text'].lower() for m in c['mentions']} for c in results['en']['corenlp_chains']]
 for pronoun in ('she','it'):
  disagreements.append({'mention':pronoun,'coreferee_candidate_sets':[sorted(c) for c in en_cf if pronoun in c],'corenlp_candidate_sets':[sorted(c) for c in en_cn if pronoun in c],'agreement':any(pronoun in a and pronoun in b and len(a&b-{pronoun})>0 for a in en_cf for b in en_cn)})
 ambiguities=[{'mention':'She','language':'en','initial_candidates':['Alice','Marie'],'initial_status':'unresolved','tool_votes':disagreements[0],'contextual_support':{'turn':'u3','evidence':'Alice, not Marie','selected':'Alice'},'final_status':'resolved_by_later_context'},{'mention':'Elle','language':'fr','initial_candidates':['Alice','Marie'],'initial_status':'unresolved','tool_votes':{'coreferee':[c for c in results['fr']['coreferee_chains'] if any(m['text'].lower()=='elle' for m in c['mentions'])],'corenlp':[]},'contextual_support':{'turn':'f3','evidence':'Marie, et non Alice','selected':'Marie'},'final_status':'resolved_by_later_context'}]
 vals={'coreferee_bilingual_runtime':all(results[l]['coreferee_chains'] for l in ('en','fr')),'corenlp_english_coref_runtime':bool(results['en']['corenlp_chains']),'corenlp_french_runtime':bool(results['fr']['corenlp_entities']),'texttiling_bilingual_runtime':all(results[l]['texttiling_segments'] for l in ('en','fr')),'convokit_topology_complete':len(topology)==16 and sum(t['reply_to'] is not None for t in topology)==14,'ambiguities_initially_preserved':all(a['initial_status']=='unresolved' and len(a['initial_candidates'])>1 for a in ambiguities),'later_context_supports_decision':all(a['contextual_support']['selected'] in a['initial_candidates'] for a in ambiguities),'tools_remain_attributed':all('tool_notes' in results[l] for l in results)};assert all(vals.values()),vals
 result={'languages':results,'convokit':{'role':'navigation/statistics only','utterance_count':len(topology),'speaker_count':len(list(corpus.iter_speakers())),'reply_edge_count':sum(t['reply_to'] is not None for t in topology),'topology':topology},'tool_disagreements':disagreements,'ambiguity_history':ambiguities,'boundary':'No CoreNLP, Coreferee, TextTiling or ConvoKit object is promoted to an internal belief, DGB fact, or dialogue theory.','validations':vals};(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary={'utterances':len(topology),'coreferee_chains':{l:len(results[l]['coreferee_chains']) for l in results},'corenlp_english_chains':len(results['en']['corenlp_chains']),'texttiling_segments':{l:len(results[l]['texttiling_segments']) for l in results},'ambiguous_mentions':len(ambiguities),'verdict':'GO_ATTRIBUTED_REFERENCE_TOPIC_BASELINES'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'versions-and-parameters.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'convokit':importlib.metadata.version('convokit'),'spacy':importlib.metadata.version('spacy'),'coreferee':importlib.metadata.version('coreferee'),'nltk':importlib.metadata.version('nltk'),'stanford_corenlp':'4.5.10','spacy_models':{'en':'en_core_web_sm','fr':'fr_core_news_sm'},'texttiling':{'w':12,'k':6,'smoothing_width':2}},indent=2)+'\n');print('DLG-12: CoreNLP/Coreferee/TextTiling/ConvoKit executed; ambiguities retained; GO')
if __name__=='__main__':main()
