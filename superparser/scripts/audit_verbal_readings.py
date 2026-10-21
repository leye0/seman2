"""Trace all lexical verb-form and valence alternatives through Parser.parse."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases,classify
from seman_parser.engine import Parser,ParserResources

ROOT=Path(__file__).resolve().parents[1]
VERBAL={"V","COPULA","AUX","AUX-BE","HAVE","MODAL","PARTICLE","PREP"}

def walk(n):
    if n is None:return
    yield n
    for c in n.children:yield from walk(c)

def inspect(parser,case):
    inp,lattice,result=parse_corpus_case(parser,case,max_items=50000,kbest_work_limit=500000)
    selected=result.best()
    spans={}
    for c in lattice.candidates:
        if c.category not in VERBAL:continue
        span=(c.span_start,c.span_end)
        spans.setdefault(span,[]).append({
            "category":c.category,"lemma":c.lemma,"source":c.source,
            "features":c.features.as_dict(),"score":c.score,
            "sense_ids":c.sense_ids,
            "syntactic_constraints":repr(getattr(c,"syntactic_constraints",None)),
        })
    lexical=[{"span":list(span),"surface":lattice.text[span[0]:span[1]],
              "finite_and_ed":({"finite","ed"}<={
                  x["features"].get("vform") for x in alts}),
              "readings":alts} for span,alts in sorted(spans.items())]
    constituents=[{
        "category":n.category,"rule":n.rule_id,
        "span":[n.start,n.end],"surface":lattice.text[n.start:n.end],
        "features":n.features.as_dict(),
        "children":[{"rule":c.rule_id,"category":c.category,
                     "features":c.features.as_dict(),
                     "span":[c.start,c.end]} for c in n.children]
    } for n in walk(selected)
    if n.category=="VP" or n.rule_id in {"clause_np_vp","clause_sub_front"}]
    return {"source":inp.source_text,"analysis":lattice.text,
            "status":classify(result.completed,result.stats),
            "lexical_alternatives":lexical,
            "finite_ed_ambiguity":[x["surface"] for x in lexical if x["finite_and_ed"]],
            "selected_constituents":constituents}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--indices",default="281,365,485")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    cases,_=select_cases(500)
    parser=Parser(ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir),
                  cache_size=0,lexical_left_corner_pruning=True)
    data=[]
    for i in (int(x) for x in args.indices.split(",") if x.strip()):
        if not 0<=i<500:raise ValueError(i)
        row=inspect(parser,cases[i]);row["index"]=i;data.append(row)
        print("VERBAL_PROVENANCE_CASE",json.dumps({
            "index":i,"status":row["status"],
            "finite_ed_ambiguity":row["finite_ed_ambiguity"],
            "lexical_alternatives":len(row["lexical_alternatives"]),
        }),flush=True)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps({"n":len(data),"cases":data},
                                  ensure_ascii=False,indent=2)+"\n",encoding="utf8")
if __name__=="__main__":main()
