"""Lexical ambiguity versus packed-forest growth, before parsing.

Research only: these products are bounds on lexical assignments, not
estimates of the number of grammatical analyses.
"""
from __future__ import annotations
import argparse, json, math
from collections import defaultdict
from pathlib import Path
from time import perf_counter_ns
from scripts.benchmark_heavy_sentence_ab import choose_cases, BANDS
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = ("tokens", "category_bits", "syntactic_bits", "candidate_count")

def lexical_ambiguity(lattice):
    spans = defaultdict(list)
    for c in lattice.candidates:
        spans[(c.span_start,c.span_end)].append(c)
    categories = []
    syntactic = []
    missing = 0
    for token in lattice.tokens:
        choices = spans[(token.start,token.end)]
        categories.append(len({c.category for c in choices}))
        syntactic.append(len({c.syntactic_signature() for c in choices}))
        missing += not bool(choices)
    exact = {(t.start,t.end) for t in lattice.tokens}
    return {
        "tokens":len(lattice.tokens),
        "category_bits":sum(math.log2(max(1,n)) for n in categories),
        "syntactic_bits":sum(math.log2(max(1,n)) for n in syntactic),
        "candidate_count":len(lattice.candidates),
        "ambiguous_positions":sum(n>1 for n in categories),
        "missing_exact_spans":missing,
        "non_exact_spans":sum(span not in exact for span in spans),
    }

def auc(records, signal, label):
    ranked = sorted((r[signal],bool(r[label])) for r in records)
    yes = sum(y for _,y in ranked)
    no = len(ranked)-yes
    if not yes or not no:
        return None
    negatives_below = 0
    favorable = 0
    p = 0
    while p < len(ranked):
        q=p+1
        while q < len(ranked) and ranked[q][0]==ranked[p][0]:
            q+=1
        positives_here=sum(int(y) for _,y in ranked[p:q])
        negatives_here=q-p-positives_here
        favorable+=positives_here*(negatives_below+negatives_here/2)
        negatives_below+=negatives_here
        p=q
    return round(favorable/(yes*no),5)

def summary(rows):
    def compare(part):
        return {signal:{
            "forest_budget_auc":auc(part,signal,"budget"),
            "slow_150ms_auc":auc(part,signal,"slow"),
        } for signal in SIGNALS}
    return {
        "count":len(rows),"budget_hits":sum(r["budget"] for r in rows),
        "slow_150ms":sum(r["slow"] for r in rows),
        "overall_auc":compare(rows),
        "by_band":{band:{"n":sum(r["band"]==band for r in rows),
            "auc":compare([r for r in rows if r["band"]==band])}
            for band,_,_ in BANDS},
        "within_book_auc":{str(book):compare([r for r in rows if r["book_id"]==book])
            for book in sorted({r["book_id"] for r in rows})},
        "notes":["No grammar changes; all measurements are before parsing",
            "Log2 products are not packed-forest counts",
            "Cross-token candidates are counted separately, not multiplied",
            "AUC quantifies rank correlation, not causal improvement",
            "Per-book AUC is within-author descriptive evaluation, not a trained held-out predictor",
            "Four authors are too few to establish external generalization"],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--per-book-per-band",type=int,default=16)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    cases,sources=choose_cases(args.per_book_per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    parser=Parser(resources,cache_size=0,max_items=20000)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    with (args.out_dir/"rows.jsonl").open("w",encoding="utf8",buffering=1) as f:
        for i,case in enumerate(cases):
            lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
            feats=lexical_ambiguity(lattice)
            start=perf_counter_ns()
            result=parser.parse_grammar_lattice(lattice,max_items=20000,kbest_work_limit=100000)
            best=result.best() if result.completed else None
            elapsed=(perf_counter_ns()-start)/1e6
            row={"index":i,"book_id":case["book_id"],"band":case["band"],
                "sentence":case["text"],**feats,
                "budget":bool(result.stats.get("budget_exceeded")),
                "slow":elapsed>=150,"parse_ms":round(elapsed,3),
                "completed":best is not None}
            rows.append(row)
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
            if (i+1)%32==0:
                print("LEXICAL_RISK_PROGRESS",json.dumps({"seen":i+1}),flush=True)
    report=summary(rows)
    report["sources"]=sources
    (args.out_dir/"summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("LEXICAL_RISK_FINAL",json.dumps(report),flush=True)

if __name__=="__main__":
    main()
