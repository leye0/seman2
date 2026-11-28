"""Run independent campaign observations; never turn missing evidence into a rule."""
from __future__ import annotations
import argparse,json,resource
from collections import Counter,defaultdict
from pathlib import Path
from time import perf_counter
from scripts.gap_campaign_sources import load_campaign,read_jsonl,write_jsonl,digest

def write_summary(out,manifest,mode,rows,init,elapsed,extra):
    report={"manifest_sha256":manifest["manifest_sha256"],"mode":mode,"rows":len(rows),
        "initialization_seconds":init,"inference_seconds":elapsed,
        "peak_process_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,**extra}
    write_jsonl(out/"observations.jsonl",rows)
    (out/"summary.json").write_text(json.dumps(report,indent=2))
    print("CAMPAIGN_PROVIDER",json.dumps(report),flush=True)

def envelope(c,**payload):return {"id":c["id"],"cohort":c["cohort"],"source_sha256":c["source_sha256"],**payload}
def native(a,cases,m):
    from seman_parser import Parser
    from hashlib import file_digest
    old={x["case_id"]:x for x in read_jsonl(a.native/"cases.jsonl")}
    for path,expected in [(a.ace,"4e3726a9e017d1e3eaa99fb89b873dfeaac3c0c0bd1989927cef6c42421f57ca"),
        (a.grammar,"2968621bf88d50cffa9ec52c5edead7b16aabff573421f2f97c113e056ff5c82")]:
        with path.open("rb") as f:
            if file_digest(f,"sha256").hexdigest()!=expected:raise ValueError("Native hash mismatch")
    start=perf_counter();rows=[];timing=0
    with (a.out/"ace.stderr.log").open("w") as err,Parser(a.grammar,executable=a.ace,stderr=err) as parser:
        init=perf_counter()-start
        for c in cases:
            reused=c["id"] in old
            if reused:
                row=old[c["id"]]
                if row["source_text"]!=c["text"]:raise ValueError("Reused native text drift")
                whole=row["whole"]
            else:
                t=perf_counter();whole=parser.parse(c["text"]);timing+=perf_counter()-t
            if whole["source_text"]!=c["text"]:raise ValueError("Native source drift")
            flags=[r["quality_flags"] for r in whole["results"]]
            rows.append(envelope(c,reused=reused,status=whole["status"],readings=whole["n_results"],
                at_cap=whole["result_cap_reached"],rank1_flagged=bool(flags and flags[0]),
                all_flagged=bool(flags and all(flags)),native=whole))
            if len(rows)%100==0:print("CAMPAIGN_NATIVE",len(rows),flush=True)
    write_summary(a.out,m,"erg",rows,init,timing,{"reused":1000,"new":1000,"metric":"Coverage and native flags, not grammatical accuracy."})
    if any(x["status"] in {"interface_error","incomplete_native_output"} for x in rows):raise ValueError("Native interface failure")
def score_external(c,report):
    ext=c["external"];checks=[]
    for i,label,k in ext["targets"]:
        frames=[f for f in report["frames"] if any(p["token_span"]==[i,i+1] for p in f["predicates"])]
        hit=any(x["label"]==label and x["token_span"][0]<=k<x["token_span"][1] for f in frames for x in f["arguments"])
        checks.append({"target":[i,label,k],"predicate_found":bool(frames),"hit":hit})
    return checks

def srl(a,cases,m):
    from seman_parser.srl import SRL,project
    start=perf_counter();model=SRL();init=perf_counter()-start;rows=[];timing=0
    for external in (False,True):
        sample=[c for c in cases if ("external" in c)==external]
        for off in range(0,len(sample),8):
            batch=sample[off:off+8];t=perf_counter()
            if external:
                doc=model.backend([c["external"]["tokens"] for c in batch],tasks=["srl"],skip_tasks="tok*")
                if len(doc["srl"])!=len(batch):raise ValueError("SRL batch cardinality")
                reports=[project(" ".join(c["external"]["tokens"]),c["external"]["tokens"],f) for c,f in zip(batch,doc["srl"])]
            else:reports=model.inspect_many([c["text"] for c in batch])
            timing+=perf_counter()-t
            for c,rep in zip(batch,reports):
                rows.append(envelope(c,representation="UD tokens joined by single spaces" if external else "source",
                    report=rep,checks=score_external(c,rep) if external else None))
            if off%160==0:print("CAMPAIGN_SRL",len(rows),flush=True)
    write_summary(a.out,m,"hanlp",rows,init,timing,{"provider":model.provenance,"metric":"Head containment on external gold; otherwise coverage."})

def allen(a,cases,m):
    from scripts.compare_allennlp_srl import MODEL,convert
    from allennlp.predictors.predictor import Predictor
    import allennlp_models.structured_prediction
    start=perf_counter();p=Predictor.from_path(MODEL,predictor_name="semantic_role_labeling",cuda_device=-1);init=perf_counter()-start
    rows=[];timing=0
    for c in cases:
        if "external" not in c:continue
        tokens=c["external"]["tokens"];text=" ".join(tokens)
        t=perf_counter();rep=convert(text,p.predict_tokenized(tokens));timing+=perf_counter()-t
        if [x["text"] for x in rep["tokens"]]!=tokens:raise ValueError("AllenNLP token drift")
        rows.append(envelope(c,representation="UD tokens joined by single spaces",report=rep,checks=score_external(c,rep)))
        if len(rows)%100==0:print("CAMPAIGN_ALLEN",len(rows),flush=True)
    write_summary(a.out,m,"allen",rows,init,timing,{"model":MODEL,"metric":"Same held-out head targets as HanLP; research-only legacy runtime."})

def lexical(a,cases,m):
    import spacy
    from nltk.corpus import wordnet
    from seman_parser.wsd import WSD,UPOS_TO_WN
    from seman_parser.role_resources import RoleResources
    from functools import lru_cache
    start=perf_counter();nlp=spacy.load("en_core_web_sm");resources=RoleResources(a.role_data)
    if wordnet.get_version()!="3.0":raise ValueError("WordNet version drift")
    model=WSD();init=perf_counter()-start;rows=[];timing=0;wsd_time=0
    @lru_cache(maxsize=8192)
    def inventory(lemma,pos):
        ss=wordnet.synsets(lemma,pos=pos)
        return {"senses":len(ss),"verbatlas_mapped":sum(bool(resources.wordnet(s.offset(),"v")["matches"]) for s in ss) if pos=="v" else None}
    for c in cases:
        t=perf_counter();doc=nlp(c["text"])
        tokens=[]
        for tok in doc:
            pos=UPOS_TO_WN.get(tok.pos_)
            if pos is None:continue
            if c["text"][tok.idx:tok.idx+len(tok.text)]!=tok.text:raise ValueError("spaCy span drift")
            tokens.append({"span":[tok.idx,tok.idx+len(tok.text)],"text":tok.text,"lemma":tok.lemma_,
                "pos":pos,**inventory(tok.lemma_,pos)})
        timing+=perf_counter()-t
        evaluation=None
        if "wsd_target" in c:
            target=c["wsd_target"];a0,b0=target["span"];pos=UPOS_TO_WN[target["pos"]]
            if c["text"][a0:b0]!=target["text"]:raise ValueError("WSD source drift")
            t=perf_counter();pred=model.target(c["text"],a0,b0,target["lemma"],pos);wsd_time+=perf_counter()-t
            gold=set(target["gold_keys"])
            # Sense-key identity can use any lemma key of the predicted synset.
            prediction=pred["prediction"];alternatives=pred["alternatives"]
            evaluation={"target":target,"prediction":pred,
                "gold_in_inventory":any(gold.intersection(s["lemma_keys"]) for s in alternatives),
                "hit":bool(prediction and gold.intersection(prediction["lemma_keys"])),
                "first_sense_hit":bool(wordnet.synsets(target["lemma"],pos=pos) and gold.intersection(
                    l.key() for l in wordnet.synsets(target["lemma"],pos=pos)[0].lemmas())),
                "verbatlas":resources.wordnet(prediction["offset"],"v") if prediction and prediction["pos"]=="v" else None}
        rows.append(envelope(c,tokens=tokens,wsd=evaluation))
        if len(rows)%100==0:print("CAMPAIGN_LEXICAL",len(rows),flush=True)
    write_summary(a.out,m,"lexical",rows,init,timing+wsd_time,{"wsd_seconds":wsd_time,"lexical_seconds":timing,
        "provider":model.provenance,"metric":"All-token inventory coverage; one gold WSD target per WSD sentence, supplied lemma/POS."})
def main():
    p=argparse.ArgumentParser();p.add_argument("--mode",choices=["erg","hanlp","allen","lexical"],required=True)
    p.add_argument("--campaign",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    for name in ("native","ace","grammar","role-data"):p.add_argument("--"+name,type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);cases,m=load_campaign(a.campaign)
    {"erg":native,"hanlp":srl,"allen":allen,"lexical":lexical}[a.mode](a,cases,m)
if __name__=="__main__":main()
