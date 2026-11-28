"""Audit native SRL inference protocols and external PropBank head recall.

This is evaluation code only. It neither selects nor modifies production analyses.
"""
import argparse,json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen
from seman_parser.srl import SRL,MODEL_URL,BASE_URL,project,align
from scripts.audit_srl import evaluate,GOLD

UP_REV="b955f2aa8295834fcd0256c131de641116a8443a"
UP_URL=f"https://raw.githubusercontent.com/UniversalPropositions/UP-1.0/{UP_REV}/UP_English-EWT/en_ewt-up-test.conllu"
# The official return.xml inventory has no speech sense. Keep these cases as
# literary diagnostic targets, but don't count them in strict PB-compatible recall.
SPEECH_RETURN={"SRL-017","SRL-021"}

def tokenized_report(model,text,tokens):
    native=model.backend([tokens],tasks=["srl"],skip_tasks="tok*")
    return project(text,tokens,native["srl"][0])

def report_from_native(text,doc):
    tok=[k for k in doc if k=="tok" or k.startswith("tok/")]
    if len(tok)!=1: raise ValueError("Unexpected token output")
    return project(text,doc[tok[0]],doc["srl"])

def signature(report):
    return sorted((p["source_span"],a["label"],a["source_span"])
        for f in report["frames"] for p in f["predicates"] for a in f["arguments"])

def parse_external(raw):
    """UP1 English gold roles projected onto UD heads, not original span gold."""
    cases=[]; excluded=Counter()
    for block in raw.decode("utf-8").strip().split("\n\n"):
        lines=block.splitlines()
        if any(x.startswith("# propbank") for x in lines):
            excluded["missing_or_mismatched_pb"]+=1;continue
        ids=[x.split(" = ",1)[1] for x in lines if x.startswith("# sent_id = ")]
        rows=[x.split("\t") for x in lines if x and not x.startswith("#")]
        if len(ids)!=1 or not rows or any(not x[0].isdigit() or len(x)<11 for x in rows):
            excluded["non_simple_tokens_or_missing_id"]+=1;continue
        if not 5<=len(rows)<=35:
            excluded["length"]+=1;continue
        preds=[i for i,x in enumerate(rows) if x[10]!="_"]
        if not preds or any(len(x)!=11+len(preds) for x in rows):
            excluded["column_mismatch_or_no_predicates"]+=1;continue
        targets=[]
        for j,i in enumerate(preds):
            if rows[i][3]!="VERB" or rows[i][11+j]!="V":continue
            for k,x in enumerate(rows):
                label=x[11+j]
                if label.startswith(("ARG","R-ARG","C-ARG")):
                    targets.append([i,label,k])
        if not targets:excluded["no_eligible_roles"]+=1;continue
        cases.append({"id":ids[0],"tokens":[x[1] for x in rows],"targets":targets})
    cases.sort(key=lambda x:sha256(("up-srl-v1:"+x["id"]).encode()).hexdigest())
    return cases[:200],excluded,len(cases)

def external_report(c,report):
    counts=Counter()
    for i,label,k in c["targets"]:
        frames=[f for f in report["frames"] if any(p["token_span"]==[i,i+1] for p in f["predicates"])]
        counts["targets"]+=1
        counts["predicate_found"]+=bool(frames)
        counts["role_contains_gold_head"]+=any(a["label"]==label and a["token_span"][0]<=k<a["token_span"][1]
            for f in frames for a in f["arguments"])
    return counts

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--model",choices=["large","base"],required=True)
    args=p.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    model=SRL(model=MODEL_URL if args.model=="large" else BASE_URL)
    gold=json.loads(GOLD.read_text())
    raw_batch=[]
    for i in range(0,len(gold),8):
        raw_batch.extend(model.inspect_many([c["text"] for c in gold[i:i+8]]))
    results=Counter(); modes= {}
    with (args.out_dir/"protocols.jsonl").open("w") as out:
        for c,batched in zip(gold,raw_batch):
            t=c["text"]
            single=model.inspect(t)
            raw_single=report_from_native(t,model.backend(t,tasks=["tok","srl"]))
            tokens=[x["text"] for x in single["tokens"]]
            pretokenized=tokenized_report(model,t,tokens)
            # Full task graph is another supported upstream execution protocol.
            full=report_from_native(t,model.backend(t))
            variants={"batch8":batched,"singleton_list":single,"raw_string":raw_single,
                      "pretokenized":pretokenized,"all_tasks":full}
            record={"case":c,"variants":{}}
            for name,report in variants.items():
                counts=modes.setdefault(name,Counter())
                checks=evaluate(c,report)
                counts["targets"]+=len(checks)
                counts["exact"]+=sum(x["exact"] for x in checks)
                counts["predicate_found"]+=sum(x["predicate_found"] for x in checks)
                counts["empty_frames"]+=not bool(report["frames"])
                counts["unmapped"]+=report["alignment"]!="exact"
                if c["id"] not in SPEECH_RETURN:
                    counts["pb_compatible_targets"]+=len(checks)
                    counts["pb_compatible_exact"]+=sum(x["exact"] for x in checks)
                counts["different_from_batch8"]+=signature(report)!=signature(batched)
                record["variants"][name]={"native_srl":report["native_srl"],"checks":checks,
                                         "tokens":report["tokens"]}
            out.write(json.dumps(record,ensure_ascii=False)+"\n");out.flush()
            print("SRL_PROTOCOL",json.dumps({"id":c["id"],"text":t,"variants":{
                n:{"frames":len(v["native_srl"]),"hits":sum(x["exact"] for x in v["checks"])}
                for n,v in record["variants"].items()}},ensure_ascii=False),flush=True)
    with urlopen(UP_URL,timeout=60) as f: raw=f.read()
    selected,excluded,eligible=parse_external(raw)
    if len(selected)!=200: raise ValueError("Incomplete external sample")
    ext=Counter()
    with (args.out_dir/"external.jsonl").open("w") as out:
        for i in range(0,len(selected),8):
            batch=selected[i:i+8]
            doc=model.backend([c["tokens"] for c in batch],tasks=["srl"],skip_tasks="tok*")
            if len(doc["srl"])!=len(batch):raise ValueError("External cardinality mismatch")
            for c,frames in zip(batch,doc["srl"]):
                report=project(" ".join(c["tokens"]),c["tokens"],frames)
                counts=external_report(c,report)
                ext.update(counts);ext["sentences"]+=1
                out.write(json.dumps({**c,"native_srl":frames,"counts":dict(counts)},ensure_ascii=False)+"\n")
            out.flush()
    summary={"provider":model.provenance,"protocols":{k:dict(v) for k,v in modes.items()},
        "external":{"revision":UP_REV,"source_sha256":sha256(raw).hexdigest(),"eligible":eligible,
                    "selection_exclusions":dict(excluded),"counts":dict(ext),
                    "metric":"Projected gold head containment recall, not span F1; upstream training overlap unknown."}}
    (args.out_dir/"summary.json").write_text(json.dumps(summary,indent=2))
    print("SRL_REVIEW_FINAL",json.dumps(summary),flush=True)

if __name__=="__main__":main()
