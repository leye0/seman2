"""Bounded, crash-resistant smoke audit of naturally occurring novel dialogue.

Exact local cleaned texts only. No modification to the corpus/grammar. The
ordinary vector parser is a fallback, but successes are only credited to
dialogue handling when dialogue_scoped=True.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.clean_novel_corpus import load_cleaned, read_manifest
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, extract
from seman_parser.dialogue import quotation_boundaries
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]


def choose_from_whole_book(rows,n):
    if not rows or n<=0:
        return []
    picked=[]
    for i in range(min(n,len(rows))):
        index=((2*i+1)*len(rows))//(2*min(n,len(rows)))
        picked.append(rows[index])
    return picked


def select_quotes(quota,max_tokens):
    by_book={b.ebook_id:b for b in TRAIN_BOOKS}
    entries=[]
    metadata=[]
    for record in read_manifest()["books"]:
        book=by_book[record["ebook_id"]]
        text,info=load_cleaned(book)
        rows,extraction=extract(book,text,length_min=4,length_max=max_tokens)
        valid=[r for r in rows if quotation_boundaries(r["text"])]
        sampled=choose_from_whole_book(valid,quota)
        metadata.append({
            "book":book.title,"author":book.author,"ebook_id":book.ebook_id,
            "clean_sha256":info["sha256"],"eligible":len(rows),
            "quote_bearing_balanced":len(valid),"selected":len(sampled),
            "selection":"spaced over whole cleaned book",
        })
        entries.extend(sampled)
    return entries,metadata


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--wordnet-dir",required=True)
    arg.add_argument("--per-book",type=int,default=10)
    arg.add_argument("--max-tokens",type=int,default=32)
    arg.add_argument("--max-items",type=int,default=20000)
    arg.add_argument("--kbest-work-limit",type=int,default=100000)
    arg.add_argument("--out",type=Path,required=True)
    args=arg.parse_args()
    selected,source=select_quotes(args.per_book,args.max_tokens)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    parser=Parser(resources,cache_size=0,max_items=args.max_items)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    by_book={}
    raw_file=args.out.with_name("cleaned_novel_dialogue_individual.jsonl")
    with raw_file.open("w",encoding="utf8",buffering=1) as out:
        for i,row in enumerate(selected):
            began=perf_counter()
            try:
                lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
                parsed=parser.parse_grammar_lattice(
                    lattice,max_items=args.max_items,
                    kbest_work_limit=args.kbest_work_limit)
                best=parsed.best() if parsed.completed else None
                result={
                    "index":i,"book_id":row["book_id"],"ordinal":row["ordinal"],
                    "sentence":row["text"],"tokens":row["tokens"],
                    "sha256":sha256(row["text"].encode()).hexdigest(),
                    "completed":bool(best),
                    "dialogue_scoped":bool(parsed.stats.get("dialogue_scoped")),
                    "root_rule":best.rule_id if best else None,
                    "forest_budget_exceeded":bool(parsed.stats.get("budget_exceeded")),
                    "kbest_budget_exceeded":bool(parsed.stats.get("kbest_budget_exceeded")),
                    "forest_nodes":parsed.stats.get("forest_nodes",0),
                    "partial_states":parsed.stats.get("partial_states",0),
                }
            except Exception as exc:
                result={"index":i,"book_id":row["book_id"],"ordinal":row["ordinal"],
                        "sentence":row["text"],"completed":False,
                        "dialogue_scoped":False,"error":f"{type(exc).__name__}: {exc}"}
            result["wall_ms"]=round((perf_counter()-began)*1000,2)
            rows.append(result)
            out.write(json.dumps(result,ensure_ascii=False)+"\n")
            if (i+1)%5==0:
                print("DIALOGUE_SMOKE_PROGRESS",json.dumps({
                    "seen":i+1,"recognized":sum(r["dialogue_scoped"] for r in rows),
                    "errors":sum("error" in r for r in rows),
                    "last_wall_ms":result["wall_ms"],
                }),flush=True)
    counts={}
    for meta in source:
        rs=[r for r in rows if r["book_id"]==meta["ebook_id"]]
        counts[str(meta["ebook_id"])]={
            "title":meta["book"],"sample_count":len(rs),
            "dialogue_covered":sum(r["dialogue_scoped"] for r in rs),
            "fallback_complete":sum(r["completed"] and not r["dialogue_scoped"] for r in rs),
            "unparsed":sum(not r["completed"] for r in rs),
            "errors":sum("error" in r for r in rs),
        }
    final={"schema":"cleaned-novel-dialogue-smoke-v1",
           "source":source,"totals":{
               "n":len(rows),"dialogue_covered":sum(r["dialogue_scoped"] for r in rows),
               "fallback_complete":sum(r["completed"] and not r["dialogue_scoped"] for r in rows),
               "unparsed":sum(not r["completed"] for r in rows)},
           "by_book":counts,
           "examples_recognized":[r for r in rows if r["dialogue_scoped"]][:8],
           "examples_unparsed":[r for r in rows if not r["dialogue_scoped"]][:18],
           "notes":[
               "Balanced double quotes only (straight and curly); apostrophes are not delimiters.",
               "Small deterministic smoke cohort; does not estimate corpus-wide coverage.",
               "A fallback parse is NOT evidence that quoted content/speaker was modeled.",
               "No grammar modifications and no sentence-level deadline; work budget is explicit.",
           ]}
    args.out.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("DIALOGUE_SMOKE_FINAL",json.dumps({
        "counts":final["totals"],"by_book":counts,
        "non_dialogue_samples":[{"index":r["index"],
            "book_id":r["book_id"],"sentence":r["sentence"][:200],
            "wall_ms":r["wall_ms"],"completed":r["completed"]}
            for r in final["examples_unparsed"][:8]]
    },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
