"""Paired audit of exact dialogue components against a frozen whole-utterance run.

Measures native output and newly represented lexical anchors, not correctness,
not full-utterance recovery. Original MRS and source-relative offsets retained.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from delphin.codecs import simplemrs
from seman_parser import Parser
from scripts.benchmark_native_erg import hash_file
from scripts.novel_sources import EXPECTED_MANIFEST

KINDS = {"spoken_clause_candidate", "reporting_clause", "narratorial_parenthetical"}
BASELINE_COUNTS = {"has_native_analysis": 957, "returned_analyses": 8450,
                   "rank1_opaque_flag": 164, "all_results_opaque_flag": 107,
                   "no_analysis_returned": 43, "components_evaluated": 0}

def stratum(analysis):
    results = analysis["results"]
    if not results:
        return "no_result"
    if not results[0]["quality_flags"]:
        return "first_clear"
    if any(not r["quality_flags"] for r in results):
        return "first_flagged_alternative_clear"
    return "all_flagged"

def anchors(result, text, offset=0):
    """Only explicit native lexical predicates, not unknown/quoted placeholders.

    Exact source offsets + predicate name, no inferred dependency or role.
    Nonmatching tokenization can yield false additions; retain native evidence.
    """
    mrs = simplemrs.decode(result["mrs"])
    out = set()
    for ep in mrs.rels:
        p = ep.predicate.strip('"')
        if ep.is_quantifier() or not (p.startswith("_") or p == "named"):
            continue
        if p.endswith("_unknown") or not (0 <= ep.cfrom < ep.cto <= len(text)):
            continue
        out.add((ep.cfrom + offset, ep.cto + offset, p))
    return out

def inside(keys, a, b):
    return {k for k in keys if a <= k[0] < k[1] <= b}

def compare_component(whole_first, whole_any, text, part, analysis):
    a,b=part["start"],part["end"]
    if analysis["source_text"] != text[a:b]:
        raise ValueError("Component input differs from exact source span")
    first = set()
    if analysis["results"] and not analysis["results"][0]["quality_flags"]:
        first = anchors(analysis["results"][0],text[a:b],a)
    return {"component_status":stratum(analysis),
            "clear_first_lexical_anchors":sorted(first),
            "new_vs_whole_first":sorted(first-inside(whole_first,a,b)),
            "new_vs_any_whole":sorted(first-inside(whole_any,a,b))}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--ace",type=Path,required=True)
    p.add_argument("--grammar",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    summary=json.loads((args.baseline/"summary.json").read_text())
    if (summary["manifest_sha256"] != EXPECTED_MANIFEST or summary["evaluated_cases"] != 1000
        or not summary["complete_corpus"] or any(summary["totals"].get(k)!=v for k,v in BASELINE_COUNTS.items())
        or summary["ace_sha256"] != hash_file(args.ace) or summary["grammar_sha256"] != hash_file(args.grammar)):
        raise ValueError("Baseline source, coverage or native tool fingerprint changed")
    # Retain every case in the inventory; prioritize problematic dialogues for the audit.
    inventory=Counter()
    selected=[]
    ids=[]
    with (args.baseline/"cases.jsonl").open() as f:
        for line in f:
            row=json.loads(line)
            ids.append(row["case_id"])
            text=row["source_text"]
            whole=row["whole"]
            if text!=whole["source_text"] or sha256(text.encode()).hexdigest()!=whole["source_sha256"]:
                raise ValueError("Baseline source identity changed")
            parts=[c for c in row["source_constituents"] if c["function"] in KINDS]
            st=stratum(whole)
            inventory[("dialogue" if parts else "other")+":"+st]+=1
            if parts:
                selected.append(row)
    if ids!=[f"Q3-{i}" for i in range(1,1001)]:
        raise ValueError("Baseline IDs changed")
    selected.sort(key=lambda r: (stratum(r["whole"])=="first_clear",int(r["case_id"].split("-")[1])))
    by_kind=defaultdict(Counter)
    by_stratum=defaultdict(Counter)
    overall=Counter()
    with (args.out_dir/"ace.stderr.log").open("w") as err, Parser(args.grammar,executable=args.ace,stderr=err) as parser, (args.out_dir/"dialogues.jsonl").open("w") as out:
        for i,row in enumerate(selected,1):
            text=row["source_text"]
            whole=row["whole"]
            st=stratum(whole)
            rs=whole["results"]
            whole_first=anchors(rs[0],text) if rs else set()
            whole_any=set().union(*(anchors(r,text) for r in rs))
            observed=[]
            for part in row["source_constituents"]:
                kind=part["function"]
                if kind not in KINDS:
                    continue
                a,b=part["start"],part["end"]
                if not 0<=a<b<=len(text):
                    raise ValueError("Component span outside source")
                analysis=parser.parse(text[a:b])
                comparison=compare_component(whole_first,whole_any,text,part,analysis)
                flags={"components":1,"component_first_clear":int(comparison["component_status"]=="first_clear"),
                       "component_any_clear":int(any(not r["quality_flags"] for r in analysis["results"])),
                       "component_no_result":int(not analysis["results"]),
                       "component_first_adds_anchor":int(bool(comparison["new_vs_whole_first"])),
                       "component_first_adds_anchor_vs_any":int(bool(comparison["new_vs_any_whole"])),
                       "new_anchor_count_vs_any":len(comparison["new_vs_any_whole"]),
                       "interface_failure":int(analysis["status"] in {"interface_error","incomplete_native_output"})}
                by_kind[kind].update(flags)
                by_stratum[st].update(flags)
                overall.update(flags)
                observed.append({"part":part,"analysis":analysis,**comparison})
            speech=[p for p in observed if p["part"]["function"]=="spoken_clause_candidate"]
            utterance_counts={"utterances":1,"utterances_with_spoken_span":int(bool(speech)),
                 "utterances_with_any_clear_spoken_first":int(any(p["component_status"]=="first_clear" for p in speech)),
                 "utterances_with_all_spoken_first_clear":int(bool(speech) and all(p["component_status"]=="first_clear" for p in speech)),
                 "utterances_with_new_spoken_anchor_vs_first":int(any(p["new_vs_whole_first"] for p in speech)),
                 "utterances_with_new_spoken_anchor_vs_any":int(any(p["new_vs_any_whole"] for p in speech))}
            by_stratum[st].update(utterance_counts)
            overall.update(utterance_counts)
            out.write(json.dumps({"case_id":row["case_id"],"source_text":text,"whole_stratum":st,"whole":whole,
                                  "components":observed},ensure_ascii=False,default=str)+"\n")
            out.flush()
            if i%25==0 or i==len(selected):
                print("DIALOGUE_PROGRESS",i,dict(overall),flush=True)
    report={"manifest_sha256":EXPECTED_MANIFEST,"baseline_inventory":dict(inventory),
            "overall":dict(overall),"by_kind":{k:dict(v) for k,v in by_kind.items()},
            "by_whole_stratum":{k:dict(v) for k,v in by_stratum.items()},
            "interpretation":"Exact-span native output, not semantic accuracy. No fragment is promoted to whole success; new anchors may reflect alternate lexical senses or tokenization."}
    (args.out_dir/"summary.json").write_text(json.dumps(report,indent=2))
    print("DIALOGUE_FINAL",json.dumps(report),flush=True)
    if overall["interface_failure"]:
        raise SystemExit("Component interface errors; inspect artifact")

if __name__=="__main__": main()
