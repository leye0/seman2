"""Timed fair coverage audit on genuine Gutenberg sentences.

All three readers see the SAME one-token lexical lattice. The canonical
vector engine is evaluated with a hard wall-clock deadline *per sentence*
to report (not hide) combinatorial tail failures.
- vector_on_same_lattice: chart grammar recognition + lazy complete tree;
- compiled_lr: the research single-continuation reader;
- production_full_vector: full lexical lattice including multiword, if asked.

This is coverage/latency, NOT gold grammatical accuracy.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
import signal
from time import perf_counter

from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, download, extract, spread_training
from seman_parser.engine import Parser, ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]


class WallTimeout(Exception):
    pass


@contextmanager
def deadline(seconds):
    if seconds<=0:
        yield
        return
    old=signal.getsignal(signal.SIGALRM)
    def expire(_s,_f):
        raise WallTimeout()
    signal.signal(signal.SIGALRM,expire)
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,old)


def quantile(values,fraction):
    if not values:return None
    values=sorted(values)
    idx=(len(values)-1)*fraction
    a=int(idx)
    b=min(a+1,len(values)-1)
    return round(values[a]+(idx-a)*(values[b]-values[a]),3)


def rows(max_tokens,per_band):
    books={}
    for book in TRAIN_BOOKS:
        core,_=download(book)
        eligible,_=extract(book,core,length_min=4,length_max=max_tokens)
        books[book.ebook_id]=eligible
        print("BOOK",book.ebook_id,len(eligible),flush=True)
    bands=[(4,12),(13,18),(19,max_tokens)]
    buckets=defaultdict(list)
    seen=set()
    for sample in spread_training(books,sum(map(len,books.values()))):
        norm=" ".join(sample["text"].casefold().split())
        if norm in seen:continue
        seen.add(norm)
        for start,end in bands:
            band=f"{start:02d}-{end}"
            if start<=sample["tokens"]<=end and len(buckets[band])<per_band:
                buckets[band].append(sample)
                break
        if all(len(buckets[f"{start:02d}-{end}"])>=per_band for start,end in bands):
            break
    samples=[]
    for start,end in bands:
        name=f"{start:02d}-{end}"
        if len(buckets[name])!=per_band:
            raise RuntimeError(f"Insufficient samples for {name}: {len(buckets[name])}")
        samples.extend((name,row) for row in buckets[name])
    return samples


def run(wordnet_dir,*,per_band=50,max_tokens=24,timeout_s=1.5,max_items=30000):
    if per_band<1 or max_tokens<19 or timeout_s<=0 or max_items<1:
        raise ValueError("Invalid configuration")
    samples=rows(max_tokens,per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    vector=Parser(resources,cache_size=0,max_items=max_items)
    lr=SemanCompiledReader(resources,token_only_lattice=True)
    metrics={mode:{"elapsed_ms":[],"counts":Counter(),"by_band":defaultdict(Counter)}
             for mode in ("vector_same_lattice","compiled_lr")}
    divergent=[]
    for i,(band,sample) in enumerate(samples,1):
        text=sample["text"]
        lattice=build_lattice(text,resources.lexicon,multiword_max=1)
        common_candidates={(c.span_start,c.span_end) for c in lattice.candidates}
        uncovered=sum((t.start,t.end) not in common_candidates
                      for t in lattice.tokens if t.text not in (".","!","?"))
        measurements={}
        def parse_vector():
            return vector._vector_grammar.parse_lattice(
                lattice, beam=vector.beam,max_items=vector.max_items,
                goal_category=vector.goal_category)
        def parse_lr():
            return lr.parse(text,lattice=lattice)
        order=(("vector_same_lattice",parse_vector),
               ("compiled_lr",parse_lr))
        if i%2:
            order=tuple(reversed(order))
        for mode,call in order:
            t0=perf_counter()
            try:
                with deadline(timeout_s):
                    report=call()
                complete=bool(report.completed and report.best() is not None) if mode=="vector_same_lattice" else bool(report.complete)
                exhausted=bool(report.stats.get("budget_exceeded",False)) if mode=="vector_same_lattice" else False
                state="complete" if complete else "budget" if exhausted else "incomplete"
            except WallTimeout:
                state="timeout"
            except Exception as exc:
                state="error:"+type(exc).__name__
            ms=(perf_counter()-t0)*1000.
            m=metrics[mode]
            m["elapsed_ms"].append(ms)
            m["counts"][state]+=1
            m["by_band"][band][state]+=1
            m["by_band"][band]["tested"]+=1
            m["by_band"][band]["missing_exact_token_candidates"]+=uncovered
            measurements[mode]=state
        if len(divergent)<20 and (
            measurements["vector_same_lattice"]=="complete")!=(
            measurements["compiled_lr"]=="complete"):
            divergent.append({
                "book_id":sample["book_id"],
                "ordinal":sample["ordinal"],
                "tokens":sample["tokens"],
                "vector":measurements["vector_same_lattice"],
                "lr":measurements["compiled_lr"],
            })
        if i%25==0 or i==len(samples):
            print("PROGRESS "+json.dumps({
                "observed":i,
                "vector":dict(metrics["vector_same_lattice"]["counts"]),
                "compiled_lr":dict(metrics["compiled_lr"]["counts"]),
            },separators=(",",":")),flush=True)
    return {
        "schema":"seman2-identical-lattice-vector-vs-lr-timed-v1",
        "corpus":{"cases":len(samples),"per_band":per_band,
                  "max_tokens":max_tokens,"timeout_s":timeout_s},
        "methods":{},
        "sample_divergences_without_copyright_text":divergent,
        "interpretation":[
            "All engines receive the same lexical candidate lattice, with no multiwords.",
            "Vector grammar is canonical packed forest, not experimental compiled L-R.",
            "Timeouts and item-budget exhaustion are counted separately from grammar rejection.",
            "Missing single-token candidates do not rule out a possible multiword reading.",
            "Completion is NOT independently verified linguistic correctness.",
        ],
    } | {
        "methods":{
            mode:{
                "outcomes":dict(row["counts"]),
                "timings_ms":{
                    "p50":quantile(row["elapsed_ms"],.50),
                    "p75":quantile(row["elapsed_ms"],.75),
                    "p90":quantile(row["elapsed_ms"],.90),
                    "p95":quantile(row["elapsed_ms"],.95),
                },
                "by_length":{band:dict(c) for band,c in row["by_band"].items()},
            }
            for mode,row in metrics.items()
        }
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--per-band",type=int,default=50)
    p.add_argument("--max-tokens",type=int,default=24)
    p.add_argument("--timeout-s",type=float,default=1.5)
    p.add_argument("--max-items",type=int,default=30000)
    args=p.parse_args()
    report=run(args.wordnet_dir,per_band=args.per_band,
               max_tokens=args.max_tokens,timeout_s=args.timeout_s,
               max_items=args.max_items)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print("FINAL "+json.dumps(report,separators=(",",":")),flush=True)


if __name__=="__main__":
    main()
