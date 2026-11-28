"""Paired contextual WSD versus WordNet first-sense baseline.

These hand-written diagnostic contrasts are not an independent standard WSD
test set. Explicit gold POS is used for both systems; scores are not end-to-end.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from nltk.corpus import wordnet
from seman_parser.wsd import WSD

GOLD=Path(__file__).resolve().parents[1]/"research"/"wsd_contrasts_v1.json"

def describe(s):
    return {"id":s.name(),"lexname":s.lexname(),"definition":s.definition()}

def evaluate(model,rows,out):
    totals=Counter()
    results=[]
    for case in rows:
        text,target,lemma,pos=(case[k] for k in ("text","target","lemma","pos"))
        a=text.index(target); b=a+len(target)
        if text.find(target,b)!=-1: raise ValueError("Nonunique target "+case["id"])
        inventory=wordnet.synsets(lemma,pos=pos)
        ids={s.name() for s in inventory}
        classes={s.lexname() for s in inventory}
        # Gold labels are not passed to WSD. Report an invalid annotation
        # separately rather than treating it as a model error or tuning it.
        exact=bool(case["accepted_synsets"])
        exact_valid=exact and set(case["accepted_synsets"])<=ids
        coarse_valid=bool(set(case["accepted_lexnames"])&classes)
        baseline=describe(inventory[0]) if inventory else None
        pred=model.target(text,a,b,lemma,pos)
        if {s["id"] for s in pred["alternatives"]}!=ids:
            raise ValueError("Upstream candidate inventory drift "+case["id"])
        totals["targets"]+=1
        totals["predicted"]+=bool(pred["prediction"])
        totals["exact_gold_valid"]+=exact_valid
        totals["exact_gold_invalid"]+=exact and not exact_valid
        totals["coarse_gold_valid"]+=coarse_valid
        totals["coarse_gold_invalid"]+=not coarse_valid
        scores={}
        for name,p in (("first_sense",baseline),("glossbert",pred["prediction"])):
            scores[name+"_exact"]=(p is not None and p["id"] in case["accepted_synsets"]) if exact_valid else None
            scores[name+"_coarse"]=(p is not None and p["lexname"] in case["accepted_lexnames"]) if coarse_valid else None
            for k in (name+"_exact",name+"_coarse"):
                if scores[k] is not None: totals[k]+=scores[k]
        row={**case,"baseline":baseline,"wsd":pred,"scores":scores,
             "exact_gold_valid":exact_valid,"coarse_gold_valid":coarse_valid}
        results.append(row)
        out.write(json.dumps(row,ensure_ascii=False)+"\n");out.flush()
        print("WSD_CASE",json.dumps({"id":case["id"],"target":target,"text":text,
            "baseline":baseline,"prediction":pred["prediction"],"scores":scores,
            "exact_gold_valid":exact_valid,"coarse_gold_valid":coarse_valid},ensure_ascii=False),flush=True)
    return dict(totals),results

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--cuda",action="store_true")
    args=p.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    cases=json.loads(GOLD.read_text())
    model=WSD(cuda=args.cuda)
    with (args.out_dir/"cases.jsonl").open("w") as f:
        totals,rows=evaluate(model,cases,f)
    report={"provider":model.provenance,"totals":totals,
            "interpretation":"Targeted contrasts with supplied lemma and POS; diagnostic, not full semantic accuracy or proof of improvement to ERG."}
    (args.out_dir/"summary.json").write_text(json.dumps(report,indent=2))
    print("WSD_FINAL",json.dumps(report),flush=True)

if __name__=="__main__":main()
