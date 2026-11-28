"""Replay all 327 attested dialogues with graph linking and native resumed views."""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from seman_parser import Parser
from seman_parser.dialogue_graph import compose_dialogue
from scripts.novel_sources import EXPECTED_MANIFEST
from scripts.benchmark_native_erg import hash_file

ACE_SHA="4e3726a9e017d1e3eaa99fb89b873dfeaac3c0c0bd1989927cef6c42421f57ca"
ERG_SHA="2968621bf88d50cffa9ec52c5edead7b16aabff573421f2f97c113e056ff5c82"

def key(e):
    return json.dumps(e["signature"],sort_keys=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--ace",type=Path,required=True)
    p.add_argument("--grammar",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    if hash_file(args.ace)!=ACE_SHA or hash_file(args.grammar)!=ERG_SHA:
        raise ValueError("Native tool fingerprint mismatch")
    args.out_dir.mkdir(parents=True,exist_ok=True)
    src_summary=json.loads((args.baseline/"summary.json").read_text())
    if src_summary["manifest_sha256"]!=EXPECTED_MANIFEST or src_summary["overall"]["utterances"]!=327 or src_summary["overall"]["components"]!=630:
        raise ValueError("Wrong dialogue baseline")
    from scripts.novel_sources import pinned_novel_sources
    from research.verbnet_lr.corpus_pipeline import prepare_corpus_input
    manifest,cases=pinned_novel_sources()
    byid={cid:prepare_corpus_input(c) for cid,c in cases}
    totals=Counter()
    witnesses=[]
    seen=set()
    with (args.out_dir/"ace.stderr.log").open("w") as err, Parser(args.grammar,executable=args.ace,stderr=err) as parser, (args.baseline/"dialogues.jsonl").open() as f, (args.out_dir/"graphs.jsonl").open("w") as out:
        for line in f:
            row=json.loads(line)
            cid=row["case_id"]
            if cid in seen: raise ValueError("Duplicate case")
            seen.add(cid)
            prepared=byid[cid]
            text=row["source_text"]
            if prepared.analysis_text!=text or sha256(text.encode()).hexdigest()!=row["whole"]["source_sha256"]:
                raise ValueError("Source drift "+cid)
            parts=prepared.structural_constituents
            components=[{"component_id":c["part"]["id"],"unit_span":[c["part"]["start"],c["part"]["end"]],"analysis":c["analysis"]} for c in row["components"]]
            g=compose_dialogue(text,parts,row["whole"],components,parse=parser.parse)
            if not g: raise ValueError("Missing dialogue graph")
            totals["dialogues"]+=1
            totals["native_readings"]+=len(g["readings"])
            for a in g["attributions"]:
                totals["attributed_quotes"]+=1
                totals["speaker_"+a["status"]]+=1
                totals["speaker_basis_"+a["preferred_basis"]]+=1
            totals["first_person_candidate_edges"]+=sum(e["relation"]=="first_person_speaker_candidate" for e in g["edges"])
            resumed=[v for v in g["views"] if v["kind"]=="resumed_speech"]
            if resumed:
                totals["split_dialogues"]+=1
                totals["resumed_views"]+=len(resumed)
                totals["resumed_view_with_result"]+=sum(bool(v["analysis"]["results"]) for v in resumed)
                totals["resumed_view_with_clear_result"]+=sum(any(not r["quality_flags"] for r in v["analysis"]["results"]) for v in resumed)
                totals["split_dialogues_any_clear_view"]+=int(any(not r["quality_flags"] for v in resumed for r in v["analysis"]["results"]))
                if row["whole_stratum"] in {"all_flagged","no_result"}:
                    totals["split_problematic_whole"]+=1
                    totals["split_problematic_any_clear_view"]+=int(any(not r["quality_flags"] for v in resumed for r in v["analysis"]["results"]))
                totals["interface_failure"]+=sum(v["status"] in {"interface_error","incomplete_native_output"} for v in resumed)
                rds={r["id"]:r for r in g["readings"]}
                whole_edges={key(e) for e in g["native_cross_quote_links"] if e["reading_id"].startswith("whole/")}
                joined=[e for e in g["native_cross_quote_links"] if not e["reading_id"].startswith("whole/") and not rds[e["reading_id"]]["quality_flags"]]
                new=[e for e in joined if key(e) not in whole_edges]
                totals["split_dialogues_native_cross_quote_links"]+=bool(joined)
                totals["split_dialogues_new_cross_quote_links"]+=bool(new)
                if new or cid=="Q3-44":
                    examples=[{"reading_id":e["reading_id"],"signature":e["signature"]} for e in new[:8]]
                    witnesses.append({"case_id":cid,"source_text":text,"whole_stratum":row["whole_stratum"],
                                      "resumed_texts":[v["text"] for v in resumed],"new_native_links":examples})
            out.write(json.dumps({"case_id":cid,"source_text":text,"whole_stratum":row["whole_stratum"],"graph":g},ensure_ascii=False,default=str)+"\n")
            if totals["dialogues"]%50==0: print("GRAPH_PROGRESS",dict(totals),flush=True)
    if totals["dialogues"]!=327 or totals["split_dialogues"]!=49:
        raise ValueError("Dialogue inventory changed")
    summary={"manifest_sha256":manifest,"totals":dict(totals),"witnesses":witnesses,
             "interpretation":"Native links in alternative views and source-grounded candidates, not full semantic correctness."}
    (args.out_dir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print("GRAPH_FINAL",json.dumps({"totals":dict(totals),"witnesses":witnesses[:3]},ensure_ascii=False),flush=True)
    if totals["interface_failure"]: raise SystemExit("Native interface error")

if __name__=="__main__":main()
