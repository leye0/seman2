"""Isolate pathological real-novel grammar parsing without disabling it globally.

Diagnostic only; does not alter snap algorithm or training data. Each index
is 0-based in the exact Gutenberg extract used by the 5000-sentence test.
Logs sentence SHA, ordinal and token count (not copyrighted sentences).
Dumps the Python stack every 20 seconds if any sentence gets stuck.
"""
from __future__ import annotations
import argparse, faulthandler, json, hashlib, sys, time, signal
from pathlib import Path
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS,download,extract
from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--wordnet-dir",required=True)
    parser.add_argument("--start",type=int,default=250)
    parser.add_argument("--stop",type=int,default=500)
    args=parser.parse_args()
    faulthandler.enable(file=sys.stderr)
    book=TRAIN_BOOKS[0]
    raw,_=download(book)
    corpus,_=extract(book,raw,length_min=4,length_max=32)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    native=Parser(resources,cache_size=0,max_items=20000)
    print("DIAGNOSTIC",json.dumps({"start":args.start,"stop":args.stop,"version":"1"}),flush=True)
    for i in range(args.start,args.stop):
        row=corpus[i]
        print("BEGIN",json.dumps({"index":i,"ordinal":row["ordinal"],"tokens":row["tokens"],
             "sha256":hashlib.sha256(row["text"].encode()).hexdigest()[:16]}),flush=True)
        started=time.perf_counter()
        faulthandler.dump_traceback_later(20,repeat=True,file=sys.stderr,exit=False)
        try:
            lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
            print("LATTICE",json.dumps({"index":i,"candidates":len(lattice.candidates),
                "elapsed_s":round(time.perf_counter()-started,4)}),flush=True)
            report=native._vector_grammar.parse_lattice(
                lattice,beam=native.beam,max_items=20000,
                goal_category=native.goal_category)
            item=report.best() if report.completed else None
            print("END",json.dumps({"index":i,"elapsed_s":round(time.perf_counter()-started,4),
                "complete":item is not None,
                "stats":{k:report.stats.get(k) for k in (
                    "recognition_ms","best_ms","kbest_ms","forest_nodes",
                    "structural_derivations","partial_states","partial_derivations",
                    "recognition_operations","compact_analyses")}}),flush=True)
        finally:
            faulthandler.cancel_dump_traceback_later()

if __name__=="__main__":
    main()
