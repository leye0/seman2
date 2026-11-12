"""Inspect why the actual anchored dialogue-30 compositions cannot be proven.

This is an instrumentation tool only. The canonical cohort, public parser
and 500-case score remain unchanged. Parsing source subspans here is NOT
counted as a full sentence success.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json

from research.verbnet_lr.corpus_pipeline import prepare_corpus_input
from scripts.audit_anchored_dialogue_30 import WITNESSES
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser, ParserResources


def probe(parser, sentence, goal):
    if not sentence or len(sentence.split()) > 23:
        return {"skipped": "empty_or_long"}
    try:
        if goal == "CLAUSE":
            parsed = parser._parse_vector_text(
                sentence, max_items=12500, kbest_work_limit=125000
            )
        else:
            lattice=parser._lattice_for_text(sentence)
            grammar = (
                parser._dialogue_vector_grammar
                if goal == "SPEECH-TAG" else parser._vector_grammar
            )
            parsed = grammar.parse_lattice(
                lattice, goal_category=goal,
                max_items=12500, kbest_work_limit=125000,
                beam=parser.beam,
            )
        root = parsed.best() if parsed.completed else None
        return {
            "complete": parsed.completed,
            "category": root.category if root else None,
            "rule": root.rule_id if root else None,
            "nodes": parsed.stats.get("structural_root_nodes"),
            "budget": parsed.stats.get("budget_exceeded"),
        }
    except Exception as exc:
        return {"error": type(exc).__name__+": "+str(exc)[:180]}


def inspect(case, parser):
    prepared = prepare_corpus_input(case)
    text=case["source_text"]
    out={
        "source":text,"parts":[],
        "full_source_has_no_synthetic_text":prepared.source_text==text,
    }
    for item in prepared.structural_constituents:
        fn=item["function"]
        if fn not in ("direct_speech","spoken_clause_candidate",
                      "reporting_clause","embedded_quotation"):
            continue
        a,b=item["start"],item["end"]
        fragment=text[a:b]
        if fn in ("direct_speech","embedded_quotation"):
            if len(fragment)>=2:
                fragment=fragment[1:-1]
        if fn=="spoken_clause_candidate":
            fragment=fragment.rstrip(".,!?")
        if fn=="reporting_clause":
            goals=("SPEECH-TAG",)
        elif fn=="embedded_quotation":
            goals=("NP",)
        else:
            goals=("CLAUSE","NP","ADVP","PP")
        out["parts"].append({
            "id":item["id"],"function":fn,"source_span":[a,b],
            "surface":text[a:b],"proof_surface":fragment,
            "probes":{goal:probe(parser,fragment,goal) for goal in goals},
        })
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wordnet-dir",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--indices",default="11,41,56,66,96,137,157,200,222,235,237,384,408,441,445,456,464,466")
    args=p.parse_args()
    selected,_=select_cases(500)
    resources=ParserResources.from_dir(
        Path(__file__).resolve().parents[1]/"data",wordnet_dict=args.wordnet_dir
    )
    parser=Parser(resources,cache_size=0,max_items=50000)
    parser.parse("John opened the box.")
    targeted=set(map(int,args.indices.split(",")))
    rows=[]
    for w in WITNESSES:
        if w.index not in targeted: continue
        row=inspect(selected[w.index],parser)
        row["index"]=w.index
        row["baseline_status"]=w.baseline_status
        rows.append(row)
        print("DIALOGUE_30_PROBE",json.dumps(row,ensure_ascii=True),flush=True)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf8")


if __name__=="__main__":
    main()
