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
from research.verbnet_lr.corpus_pipeline import parse_corpus_case, prepare_corpus_input

ROOT=Path(__file__).resolve().parents[1]


def choose_from_whole_book(rows,n):
    if not rows or n<=0:
        return []
    picked=[]
    for i in range(min(n,len(rows))):
        index=((2*i+1)*len(rows))//(2*min(n,len(rows)))
        picked.append(rows[index])
    return picked


def token_length_band(n):
    """Stable bands used by the dialogue research audit."""
    if n <= 8:
        return "04-08"
    if n <= 16:
        return "09-16"
    if n <= 24:
        return "17-24"
    if n <= 32:
        return "25-32"
    return "33+"


def choose_stratified(rows, n):
    """Deterministically spread genuine examples across sentence lengths.

    No synthetic text and no reuse of the same sentence. If one band is
    scarce, fill the gap from other positions in the book.
    """
    bands = ("04-08", "09-16", "17-24", "25-32")
    goal = min(len(rows), max(0, n))
    selected = []
    for i, band in enumerate(bands):
        pool = [r for r in rows if token_length_band(r["tokens"]) == band]
        quota = goal // len(bands) + (i < goal % len(bands))
        selected.extend(choose_from_whole_book(pool, quota))
    if len(selected) < goal:
        used = {r["ordinal"] for r in selected}
        remaining = [r for r in rows if r["ordinal"] not in used]
        selected.extend(choose_from_whole_book(remaining, goal-len(selected)))
    return sorted(selected, key=lambda r: r["ordinal"])


def quote_surface_layout(sentence):
    """Describe visible quote positions, not syntactic/semantic correctness."""
    boundaries = quotation_boundaries(sentence)
    opening = [b for b in boundaries if b.side == "open"]
    closing = [b for b in boundaries if b.side == "close"]
    if not opening or len(opening) != len(closing):
        return "no_balanced_double_quotes"
    if len(opening) > 1:
        return "multiple_quoted_spans"
    before = bool(sentence[:opening[0].start].strip())
    after = bool(sentence[closing[-1].end:].strip())
    if before and after:
        return "narration_on_both_sides"
    if before:
        return "narration_before_quote"
    if after:
        return "narration_after_quote"
    return "quote_only"


def select_quotes(quota,max_tokens,*,stratify_length=False):
    by_book={b.ebook_id:b for b in TRAIN_BOOKS}
    entries=[]
    metadata=[]
    for record in read_manifest()["books"]:
        book=by_book[record["ebook_id"]]
        text,info=load_cleaned(book)
        rows,extraction=extract(book,text,length_min=4,length_max=max_tokens)
        valid=[r for r in rows if quotation_boundaries(
            prepare_corpus_input(r).analysis_text)]
        sampled=(choose_stratified(valid,quota) if stratify_length
                 else choose_from_whole_book(valid,quota))
        metadata.append({
            "book":book.title,"author":book.author,"ebook_id":book.ebook_id,
            "clean_sha256":info["sha256"],"eligible":len(rows),
            "quote_bearing_balanced":len(valid),"selected":len(sampled),
            "selection":("length-stratified, then spaced across the book" if stratify_length
                         else "spaced over whole cleaned book"),
        })
        entries.extend(sampled)
    return entries,metadata


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--wordnet-dir",required=True)
    arg.add_argument("--per-book",type=int,default=10)
    arg.add_argument("--stratify-length",action="store_true")
    arg.add_argument("--max-tokens",type=int,default=32)
    arg.add_argument("--max-items",type=int,default=20000)
    arg.add_argument("--kbest-work-limit",type=int,default=100000)
    arg.add_argument("--out",type=Path,required=True)
    args=arg.parse_args()
    selected,source=select_quotes(args.per_book,args.max_tokens,
                                  stratify_length=args.stratify_length)
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
                prepared,lattice,parsed=parse_corpus_case(
                    parser,row,max_items=args.max_items,
                    kbest_work_limit=args.kbest_work_limit)
                best=parsed.best() if parsed.completed else None
                result={
                    "index":i,"book_id":row["book_id"],"ordinal":row["ordinal"],
                    "sentence":row["text"],"analysis_text":prepared.analysis_text,
                    "tokens":row["tokens"],
                    "length_band":token_length_band(row["tokens"]),
                    "quote_layout":quote_surface_layout(prepared.analysis_text),
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
                        "sentence":row["text"],"tokens":row["tokens"],
                        "length_band":token_length_band(row["tokens"]),
                        "quote_layout":quote_surface_layout(row["text"]),
                        "completed":False,
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
    def breakdown(key):
        summary = {}
        for value in sorted({r[key] for r in rows}):
            cohort = [r for r in rows if r[key] == value]
            summary[value] = {
                "n":len(cohort),
                "dialogue_covered":sum(r["dialogue_scoped"] for r in cohort),
                "fallback_complete":sum(r["completed"] and not r["dialogue_scoped"] for r in cohort),
                "unparsed":sum(not r["completed"] for r in cohort),
                "errors":sum("error" in r for r in cohort),
            }
        return summary

    final={"schema":"cleaned-novel-dialogue-smoke-v2",
           "source":source,"totals":{
               "n":len(rows),"errors":sum("error" in r for r in rows),
                "dialogue_covered":sum(r["dialogue_scoped"] for r in rows),
               "fallback_complete":sum(r["completed"] and not r["dialogue_scoped"] for r in rows),
               "unparsed":sum(not r["completed"] for r in rows)},
           "by_book":counts,
           "by_length_band":breakdown("length_band"),
           "by_quote_layout":breakdown("quote_layout"),
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
        "by_length_band":final["by_length_band"],
        "by_quote_layout":final["by_quote_layout"],
        "non_dialogue_samples":[{"index":r["index"],
            "book_id":r["book_id"],"sentence":r["sentence"][:200],
            "wall_ms":r["wall_ms"],"completed":r["completed"]}
            for r in final["examples_unparsed"][:8]]
    },ensure_ascii=False),flush=True)
    # Preserve the full audit, but NEVER let a caught parser exception be
    # misreported as a green GitHub Actions run.
    errors=[r for r in rows if "error" in r]
    if errors:
        raise RuntimeError(
            f"Dialogue audit encountered {len(errors)} parser errors "
            f"out of {len(rows)} examples; see individual JSONL"
        )


if __name__=="__main__":
    main()
