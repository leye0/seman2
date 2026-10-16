"""Held-out study of full-structure snapping vs existing L-R baseline.

The training source is only completed L-R trees on the dev split, tagged
candidate (not gold). No held-out trees ever enter the pattern index.
A hit proves reusable grammar-licensed topology plus successful re-unification,
not unique grammatical correctness. The test set never trains the cache.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter

from research.verbnet_lr.full_structure_snap import FullStructureSnapIndex
from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]


def quantile(values, fraction):
    if not values:
        return None
    values.sort()
    return round(values[min(len(values)-1,int((len(values)-1)*fraction))],5)


def run(*, wordnet_dir, max_train=60, max_eval=60, repetitions=3):
    corpus=ROOT / "research/verbnet_lr/oracle_cases.jsonl"
    rows=[json.loads(row) for row in corpus.read_text().splitlines() if row.strip()]
    train=[r for r in rows if r.get("split")=="dev"][:max_train]
    evaluation=[r for r in rows if r.get("split")!="dev"][:max_eval]
    resources=ParserResources.from_dir(ROOT / "data",wordnet_dict=wordnet_dir)
    lr=SemanCompiledReader(resources, token_only_lattice=True)
    snap=FullStructureSnapIndex(resources)
    training=Counter()
    for case in train:
        r=lr.parse(case["text"])
        if r.complete:
            lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
            try:
                snap.observe(r.item, lattice=lattice, evidence="candidate")
                training["accepted"]+=1
            except ValueError:
                training["unsupported"]+=1
        else:
            training["incomplete"]+=1
    totals={"lr":[],"snap_recognition":[],"snap_including_lattice":[]}
    case_results=[]
    for case in evaluation:
        lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
        for _ in range(repetitions):
            t=perf_counter()
            hit=snap.match(lattice)
            totals["snap_recognition"].append((perf_counter()-t)*1000)
        t=perf_counter()
        lattice2=build_lattice(case["text"],resources.lexicon,multiword_max=1)
        hit=snap.match(lattice2)
        totals["snap_including_lattice"].append((perf_counter()-t)*1000)
        t=perf_counter()
        baseline=lr.parse(case["text"])
        totals["lr"].append((perf_counter()-t)*1000)
        case_results.append({
            "id":case["id"],"split":case.get("split"),
            "snap_matches":len(hit.matches),
            "snap_incomplete":hit.incomplete,"snap_reason":hit.reason,
            "candidate_templates":hit.candidate_templates,
            "lr_complete":baseline.complete,
            "snap_rule_ids":sorted({m.item.rule_id for m in hit.matches}),
        })
    def metrics(seq):
        return {"p50_ms":quantile(seq[:],.5),"p95_ms":quantile(seq[:],.95),
                "p99_ms":quantile(seq[:],.99)}
    return {
        "schema":"seman2-full-structure-snap-v1",
        "training_source":"dev L-R completed candidate trees (NOT fully verified)",
        "evaluation_source":"non-dev unseen sentences; no online training",
        "training_cases":len(train),"evaluation_cases":len(evaluation),
        "training":dict(training),"index":snap.summary(),
        "recognition":{"hits":sum(bool(r["snap_matches"]) for r in case_results),
                       "multi_structure_hits":sum(r["snap_matches"]>1 for r in case_results),
                       "incomplete":sum(r["snap_incomplete"] for r in case_results),
                       "no_hit":sum(not r["snap_matches"] for r in case_results)},
        "latency":{
            "snap_recognition_warmed_lattice":metrics(totals["snap_recognition"]),
            "snap_including_lexical_lattice":metrics(totals["snap_including_lattice"]),
            "lr_baseline_including_lattice":metrics(totals["lr"]),
        },
        "cases":case_results,
        "limitations":[
            "Only previously observed full trees are indexed; zero hits do not disprove grammaticality.",
            "One-token lexical slots; trailing period and exclamation are excluded like current L-R.",
            "Candidate templates come from L-R and have no independent grammatical verification.",
            "Only one lexical derivation is materialized per matched whole-tree template.",
            "Hard budgets can truncate lookup; such cases are marked incomplete.",
            "No 20-million-template memory or on-disk index performance has been claimed.",
        ]
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--max-train",type=int,default=60)
    p.add_argument("--max-eval",type=int,default=60)
    p.add_argument("--repetitions",type=int,default=3)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    report=run(wordnet_dir=a.wordnet_dir,max_train=a.max_train,
               max_eval=a.max_eval,repetitions=a.repetitions)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("training","index","recognition","latency")},indent=2))
