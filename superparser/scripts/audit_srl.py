"""Targeted SRL checks plus full frozen 327-dialogue coverage.

Gold targets are intentionally partial and manually specified; report recall,
not F1 or full-frame correctness. No annotation is passed to the model.
"""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
from seman_parser.srl import SRL,MODEL_URL,BASE_URL
from scripts.novel_sources import EXPECTED_MANIFEST

GOLD=Path(__file__).resolve().parents[1]/"research"/"srl_targets_v1.json"

def unique(text,s):
    a=text.index(s)
    if text.find(s,a+len(s))!=-1: raise ValueError("Nonunique gold anchor: "+s)
    return [a,a+len(s)]

def overlap(a,b):
    return a and b and max(a[0],b[0])<min(a[1],b[1])

def evaluate(case,report):
    rows=[]
    for pred,label,arg in case["targets"]:
        p,a=unique(case["text"],pred),unique(case["text"],arg)
        frames=[f for f in report["frames"] if any(x["source_span"]==p for x in f["predicates"])]
        args=[x for f in frames for x in f["arguments"]]
        rows.append({"predicate":pred,"label":label,"argument":arg,"predicate_found":bool(frames),
                     "exact":any(x["label"]==label and x["source_span"]==a for x in args),
                     "overlap":any(x["label"]==label and overlap(x["source_span"],a) for x in args),
                     "observed":[{"label":x["label"],"text":x["source_text"],"span":x["source_span"]} for x in args]})
    return rows

def batches(items,size):
    for i in range(0,len(items),size): yield items[i:i+size]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--model",choices=["large","base"],default="large")
    p.add_argument("--batch-size",type=int,default=8)
    args=p.parse_args()
    if args.batch_size<1: raise ValueError("Positive batch size required")
    baseline=json.loads((args.baseline/"summary.json").read_text())
    if baseline["manifest_sha256"]!=EXPECTED_MANIFEST or baseline["totals"]["dialogues"]!=327:
        raise ValueError("Wrong frozen corpus")
    args.out_dir.mkdir(parents=True,exist_ok=True)
    srl=SRL(model=MODEL_URL if args.model=="large" else BASE_URL)
    gold=json.loads(GOLD.read_text())
    counts=Counter();by_family=defaultdict(Counter)
    with (args.out_dir/"targets.jsonl").open("w") as out:
        for batch in batches(gold,args.batch_size):
            for case,report in zip(batch,srl.inspect_many([c["text"] for c in batch])):
                rows=evaluate(case,report)
                for row in rows:
                    for c in (counts,by_family[case["family"]]):
                        c["targets"]+=1
                        for key in ("predicate_found","exact","overlap"): c[key]+=row[key]
                counts["passages"]+=1
                counts["unmapped_passages"]+=report["alignment"]!="exact"
                result={**case,"report":report,"checks":rows}
                out.write(json.dumps(result,ensure_ascii=False)+"\n");out.flush()
                print("SRL_CASE",json.dumps({"id":case["id"],"text":case["text"],"checks":rows},ensure_ascii=False),flush=True)
    corpus=[]
    with (args.baseline/"graphs.jsonl").open() as f:
        for line in f:
            row=json.loads(line)
            corpus.append((row["case_id"],row["source_text"]))
    if len(corpus)!=327 or len({x[0] for x in corpus})!=327: raise ValueError("Corpus cardinality drift")
    inv=Counter();labels=Counter()
    with (args.out_dir/"dialogues.jsonl").open("w") as out:
        for batch in batches(corpus,args.batch_size):
            for (cid,text),report in zip(batch,srl.inspect_many([t for _,t in batch])):
                inv["passages"]+=1;inv["frames"]+=len(report["frames"])
                inv["has_frames"]+=bool(report["frames"])
                inv["unmapped_passages"]+=report["alignment"]!="exact"
                for f in report["frames"]:
                    inv["unexpected_predicate_count"]+=f["status"]!="one_predicate"
                    inv["arguments"]+=len(f["arguments"])
                    labels.update(x["label"] for x in f["arguments"])
                out.write(json.dumps({"case_id":cid,**report},ensure_ascii=False)+"\n")
            out.flush()
            if inv["passages"]%40==0: print("SRL_PROGRESS",dict(inv),flush=True)
    report={"provider":srl.provenance,"manifest_sha256":EXPECTED_MANIFEST,
            "diagnostic_targets":dict(counts),"by_family":{k:dict(v) for k,v in by_family.items()},
            "corpus_inventory":dict(inv),"role_labels":dict(labels),
            "limitations":"Partial manually annotated targets; exact/overlap recall only, not precision or F1. Corpus inventory is coverage, not accuracy. No ERG changes."}
    (args.out_dir/"summary.json").write_text(json.dumps(report,indent=2))
    print("SRL_FINAL",json.dumps(report),flush=True)

if __name__=="__main__":main()
