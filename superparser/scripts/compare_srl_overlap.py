"""Paired, oracle-only overlap report. No model selection or inference rules."""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path

def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]

def label(a,b):
    return "both" if a and b else "base_only" if a else "large_only" if b else "neither"

def match(row,target):
    i,role,k=target
    return any(any(p[1]=="PRED" and p[2:]==[i,i+1] for p in frame)
        and any(a[1]==role and a[2]<=k<a[3] for a in frame)
        for frame in row["native_srl"])

def compare(base,large):
    bx,lx=(json.loads((d/"summary.json").read_text()) for d in (base,large))
    for key in ("revision","source_sha256"):
        if bx["external"][key]!=lx["external"][key]:
            raise ValueError("External corpus identity mismatch")
    pairs=[(read(d/"external.jsonl"),read(d/"protocols.jsonl")) for d in (base,large)]
    (be,bd),(le,ld)=pairs
    if len(be)!=200 or len(le)!=200 or len(bd)!=30 or len(ld)!=30:
        raise ValueError("Corpus size mismatch")
    external=Counter(); roles=defaultdict(Counter)
    for b,l in zip(be,le):
        if any(b[k]!=l[k] for k in ("id","tokens","targets")):
            raise ValueError("External case mismatch")
        for t in b["targets"]:
            key=label(match(b,t),match(l,t))
            external[key]+=1;roles[t[1]][key]+=1
    diagnostic=Counter(); recoveries=[]
    for b,l in zip(bd,ld):
        if b["case"]!=l["case"]:raise ValueError("Diagnostic case mismatch")
        bs,ls=(r["variants"]["batch8"]["checks"] for r in (b,l))
        if len(bs)!=len(ls):raise ValueError("Diagnostic target mismatch")
        for x,y in zip(bs,ls):
            if any(x[k]!=y[k] for k in ("predicate","label","argument")):
                raise ValueError("Diagnostic target mismatch")
            key=label(x["exact"],y["exact"]);diagnostic[key]+=1
            if key=="base_only":
                recoveries.append({"id":b["case"]["id"],"predicate":x["predicate"],
                    "role":x["label"],"argument":x["argument"]})
    return {"diagnostic":dict(diagnostic),"external":dict(external),
            "external_by_role":{k:dict(v) for k,v in roles.items()},
            "base_only_diagnostic":recoveries,
            "interpretation":"Oracle union of available correct relations, not accuracy of an ensemble. No predictions changed."}

def main():
    p=argparse.ArgumentParser();p.add_argument("--base",type=Path,required=True)
    p.add_argument("--large",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    args=p.parse_args();report=compare(args.base,args.large)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":main()
