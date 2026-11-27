"""Reproduce the exact Novel-1000 v3 coverage benchmark with the production ERG engine."""
import argparse
from collections import Counter
from hashlib import file_digest
from pathlib import Path
import json
from seman_parser import Parser
from scripts.novel_sources import pinned_novel_sources
from research.verbnet_lr.corpus_pipeline import parse_corpus_case

def hash_file(path):
    with open(path,"rb") as f:
        return file_digest(f,"sha256").hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ace",type=Path,required=True)
    p.add_argument("--grammar",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--limit",type=int,default=1000)
    p.add_argument("--max-results",type=int,default=10)
    p.add_argument("--timeout",type=int,default=10)
    p.add_argument("--components",action="store_true",help="Separate diagnostic for exposed speech spans")
    args=p.parse_args()
    if not 1<=args.limit<=1000: p.error("limit must be 1..1000")
    manifest,cases=pinned_novel_sources()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    totals=Counter()
    with (args.out_dir/"ace.stderr.log").open("w") as stderr, Parser(args.grammar,executable=args.ace,max_results=args.max_results,timeout=args.timeout,stderr=stderr) as parser:
        control=parser.parse("The dog barks.")
        if control["status"]!="has_native_analysis": raise RuntimeError("Native smoke failed")
        with (args.out_dir/"cases.jsonl").open("w") as f:
            for i,(case_id,case) in enumerate(cases[:args.limit],1):
                prepared,report=parse_corpus_case(parser,case,parse_components=args.components)
                whole=report["whole"]
                totals.update({whole["status"]:1,"returned_analyses":whole["n_results"],"at_result_cap":int(whole["result_cap_reached"])})
                if whole["results"]:
                    totals["rank1_opaque_flag"]+=bool(whole["results"][0]["quality_flags"])
                    totals["all_results_opaque_flag"]+=all(bool(x["quality_flags"]) for x in whole["results"])
                totals["components_evaluated"]+=len(report["component_analyses"])
                f.write(json.dumps({"case_id":case_id,"book_id":case["book_id"],"source_span":case["structural_core_source_span"],**report},ensure_ascii=False,default=str)+"\n")
                f.flush()
                if i%25==0: print("PROGRESS",i,dict(totals),flush=True)
    summary={"manifest_sha256":manifest,"evaluated_cases":args.limit,"complete_corpus":args.limit==1000,
             "grammar_sha256":hash_file(args.grammar),"ace_sha256":hash_file(args.ace),
             "totals":dict(totals),"interpretation":"Native coverage and opacity flags, not accuracy; components never count as full success"}
    (args.out_dir/"summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)
    if totals["interface_error"] or totals["incomplete_native_output"]: raise SystemExit("Native interface failure")

if __name__=="__main__": main()
